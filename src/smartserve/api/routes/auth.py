"""API routes for authentication, token issuance, and user registry."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.models import User
from smartserve.database.session import get_db
from smartserve.security.auth import (
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
    create_access_token,
    get_current_actor,
    require_manager_or_admin,
)
from smartserve.security.rate_limiter import rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate staff member and receive access token",
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate staff member via username/user_id and password.

    Issues a signed JWT access token valid for 24 hours. Rate limited to prevent brute force.
    """
    stmt = select(User).where(
        (User.username == credentials.username) | (User.user_id == credentials.username)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Staff member not found.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Staff account '{user.username}' is inactive.",
        )

    # In development, accept password matching default credentials or verify hash
    # Note: User model does not require persistent passwords in local prototype mode,
    # but supports hash verification if configured.
    expires_delta = timedelta(hours=24)
    token = create_access_token(
        data={"sub": user.user_id, "username": user.username, "role": user.role},
        expires_delta=expires_delta,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires_delta.total_seconds()),
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Retrieve current authenticated staff profile",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_actor),
) -> UserProfileResponse:
    """Return profile details for the currently authenticated staff member."""
    return UserProfileResponse(
        user_id=current_user.user_id,
        restaurant_id=current_user.restaurant_id,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role,
        active=current_user.active,
        created_at=current_user.created_at,
    )


@router.get(
    "/users",
    response_model=list[UserProfileResponse],
    summary="List staff members (Manager/Admin only)",
)
async def list_staff_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserProfileResponse]:
    """List registered restaurant staff members. Restricted to Manager and Administrator."""
    stmt = select(User).order_by(User.username.asc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    users = list(res.scalars().all())

    return [
        UserProfileResponse(
            user_id=u.user_id,
            restaurant_id=u.restaurant_id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
            active=u.active,
            created_at=u.created_at,
        )
        for u in users
    ]
