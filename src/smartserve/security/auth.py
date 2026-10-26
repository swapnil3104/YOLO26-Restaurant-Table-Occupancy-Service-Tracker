"""Authentication and role-based authorization dependencies for SmartServe AI.

Follows Docs/TASKS.md Phase 7-8, FR-09, Docs/ARCHITECTURE.md Section 12,
and Docs/RULES.md Section 6.
"""

import hashlib
import hmac
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.config import settings
from smartserve.database.models import User
from smartserve.database.session import get_db
from smartserve.events.schema import UserRole

logger = logging.getLogger(__name__)

# Security schemes for OpenAPI documentation
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer token (JWT or User ID)")
api_key_header = APIKeyHeader(
    name="X-User-ID", auto_error=False, description="User identifier header"
)

ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# ---------------------------------------------------------------------------
# Password & Token Cryptography
# ---------------------------------------------------------------------------


def hash_password(password: str, salt: str | None = None) -> str:
    """Generate salted SHA-256 password hash."""
    if salt is None:
        salt = settings.SECRET_KEY[:16]
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"{salt}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash representation."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, hash_val = stored_hash.split("$", 1)
    test_hash = hash_password(plain_password, salt=salt)
    return hmac.compare_digest(test_hash, stored_hash)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Safely decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


# ---------------------------------------------------------------------------
# Auth Request/Response Models
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """Access token payload returned upon successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user_id: str
    username: str
    role: str
    display_name: str


class LoginRequest(BaseModel):
    """Credentials required for staff login."""

    username: str = Field(..., min_length=2, description="Staff username or user_id")
    password: str = Field(..., min_length=1, description="Staff password")


class UserProfileResponse(BaseModel):
    """Sanitized user profile response without credentials."""

    user_id: str
    restaurant_id: str
    username: str
    display_name: str
    role: str
    active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# User / Actor Resolution Dependencies
# ---------------------------------------------------------------------------


async def resolve_actor(
    db: AsyncSession,
    user_identifier: str | None,
) -> User:
    """Resolve and validate an actor from any supplied identifier."""
    if not user_identifier:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide staff actor identification.",
        )

    USER_ALIASES: dict[str, str] = {
        "usr_manager_01": "usr_mgr",
        "manager_morgan": "manager",
        "usr_waiter_01": "usr_waiter1",
        "waiter_alex": "waiter1",
        "usr_admin_01": "usr_admin",
        "admin_taylor": "admin",
    }

    stmt = select(User).where(
        (User.user_id == user_identifier) | (User.username == user_identifier)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user and user_identifier in USER_ALIASES:
        aliased = USER_ALIASES[user_identifier]
        stmt = select(User).where((User.user_id == aliased) | (User.username == aliased))
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{user_identifier}' not found in registry.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{user.username}' is inactive.",
        )

    return user


async def get_current_actor(
    request: Request,
    auth_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    user_id_query: str | None = Query(None, alias="user_id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and validate the active staff actor performing the operation.

    Checks:
    1. HTTP Bearer authorization header (JWT decoding with fallback to raw user_id/username).
    2. 'X-User-ID' header.
    3. Query parameters ('user_id', 'waiter_id', 'staff_id').
    Validates user existence and active status in the database.
    """
    user_identifier: str | None = None

    # 1. Bearer Token
    if auth_credentials and auth_credentials.credentials:
        raw_token = auth_credentials.credentials.strip()
        decoded = decode_access_token(raw_token)
        if decoded and "sub" in decoded:
            user_identifier = str(decoded["sub"])
        else:
            # Fallback for plain user identifier passed as Bearer token
            user_identifier = raw_token

    # 2. X-User-ID Header or query parameters
    if not user_identifier:
        user_identifier = (
            x_user_id
            or user_id_query
            or request.query_params.get("waiter_id")
            or request.query_params.get("staff_id")
        )

    # 3. Direct Authorization header inspection if bearer_scheme did not capture
    if not user_identifier:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw = auth_header.replace("Bearer ", "").strip()
            decoded = decode_access_token(raw)
            user_identifier = str(decoded["sub"]) if decoded and "sub" in decoded else raw

    if not user_identifier:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide Bearer token, 'X-User-ID' header, or 'user_id' parameter.",
        )

    USER_ALIASES: dict[str, str] = {
        "usr_manager_01": "usr_mgr",
        "manager_morgan": "manager",
        "usr_waiter_01": "usr_waiter1",
        "waiter_alex": "waiter1",
        "usr_admin_01": "usr_admin",
        "admin_taylor": "admin",
    }

    stmt = select(User).where(
        (User.user_id == user_identifier) | (User.username == user_identifier)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user and user_identifier in USER_ALIASES:
        aliased = USER_ALIASES[user_identifier]
        stmt = select(User).where((User.user_id == aliased) | (User.username == aliased))
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{user_identifier}' not found in registry.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{user.username}' is inactive.",
        )

    return user


async def get_optional_actor(
    request: Request,
    auth_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optional actor resolution that returns None rather than raising 401."""
    try:
        return await get_current_actor(
            request=request,
            auth_credentials=auth_credentials,
            x_user_id=x_user_id,
            db=db,
        )
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Role Enforcement Dependencies
# ---------------------------------------------------------------------------


def require_roles(allowed_roles: Sequence[UserRole | str]) -> Callable[..., Any]:
    """Dependency factory restricting route access to specific user roles."""
    normalized_roles = [
        r.value if isinstance(r, UserRole) else str(r).upper() for r in allowed_roles
    ]

    async def role_checker(
        current_user: User = Depends(get_current_actor),
    ) -> User:
        user_role = str(current_user.role).upper()
        if user_role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"User '{current_user.username}' with role '{user_role}' "
                    f"is not authorized. Required: {normalized_roles}."
                ),
            )
        return current_user

    return role_checker


# Convenient role dependencies
require_staff_actor = require_roles([UserRole.WAITER, UserRole.MANAGER, UserRole.ADMIN])
require_manager_or_admin = require_roles([UserRole.MANAGER, UserRole.ADMIN])
require_admin_actor = require_roles([UserRole.ADMIN])
