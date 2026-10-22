"""Health check endpoint module."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter
from smartserve import __version__
from smartserve.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=Dict[str, Any])
async def get_health() -> Dict[str, Any]:
    """Return application health status without leaking sensitive credentials."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "api": "up",
            "vision_pipeline": "standby",
            "database": "configured",
        },
    }
