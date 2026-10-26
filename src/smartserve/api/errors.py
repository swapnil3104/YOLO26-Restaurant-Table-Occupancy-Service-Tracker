"""Standardized API error models and global exception handlers.

Ensures consistent JSON error format across all endpoints and prevents leakage
of sensitive credentials, internals, or stack traces. Adheres to Docs/TASKS.md Phase 8.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from smartserve.security.secrets import sanitize_data

logger = logging.getLogger("smartserve.api.errors")


class ErrorDetail(BaseModel):
    """Detailed error object returned within standardized error envelopes."""

    error_code: str = Field(..., description="Machine-readable error classification")
    message: str = Field(..., description="Human-readable description of the error")
    details: Any = Field(default=None, description="Optional granular field or context details")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the error occurrence",
    )


class ErrorResponse(BaseModel):
    """Standardized top-level error response envelope for all HTTP error codes."""

    success: bool = Field(default=False, description="Always false for error envelopes")
    error: ErrorDetail = Field(..., description="Error payload details")


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construct a standardized JSONResponse from error fields.

    Includes both modern structured 'error' dictionary and Starlette-compatible
    top-level 'detail' string for backward compatibility with existing clients.
    """
    content = {
        "detail": message,
        "success": False,
        "error": {
            "error_code": error_code,
            "message": message,
            "details": sanitize_data(details) if details else None,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Global handler for Starlette/FastAPI HTTPExceptions."""
    error_code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "UNPROCESSABLE_CONTENT",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    error_code = error_code_map.get(exc.status_code, "ERROR")

    # Pass detail directly, or message if structured
    message = str(exc.detail) if isinstance(exc.detail, str) else "An error occurred."
    details = exc.detail if not isinstance(exc.detail, str) else None

    return create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
        details=details,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Global handler for Pydantic request validation errors."""
    clean_errors = []
    for err in exc.errors():
        clean_errors.append(
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "type": err.get("type", "value_error"),
                "message": err.get("msg", "Invalid value"),
            }
        )

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request payload or query validation failed.",
        details=clean_errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global safety net catching unhandled exceptions without leaking stack trace or secrets."""
    logger.exception(
        f"Unhandled exception during request {request.method} {request.url.path}: {exc}"
    )
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please contact the administrator.",
        details=None,
    )
