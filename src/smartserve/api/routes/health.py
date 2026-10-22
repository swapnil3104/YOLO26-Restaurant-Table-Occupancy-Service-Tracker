"""Health check endpoint module."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from smartserve import __version__
from smartserve.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict[str, Any])
async def get_health() -> dict[str, Any]:
    """Return application health status without leaking sensitive credentials."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "api": "up",
            "vision_pipeline": "standby",
            "database": "configured",
        },
    }
