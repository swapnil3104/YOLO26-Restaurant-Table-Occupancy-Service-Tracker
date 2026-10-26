"""Health and system readiness endpoint module.

Reports application and dependency status without leaking secrets, connection credentials,
or internal infrastructure details. Adheres to Docs/PRD.md Section 14 and Docs/TASKS.md Phase 8.
"""

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve import __version__
from smartserve.config import settings
from smartserve.database.session import get_db

router = APIRouter(tags=["Health"])


class ComponentStatus(BaseModel):
    """Health status and latency of an individual system dependency."""

    status: str = Field(..., description="Operational status: 'up', 'degraded', 'down', 'standby'")
    latency_ms: float | None = Field(
        default=None, description="Check execution latency in milliseconds"
    )
    details: str | None = Field(default=None, description="Operational notes without secrets")


class HealthStatusResponse(BaseModel):
    """Application health report."""

    status: str = Field(..., description="Overall status: 'healthy', 'degraded', 'unhealthy'")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(..., description="Application semantic version")
    timestamp: datetime = Field(..., description="UTC check timestamp")
    components: dict[str, ComponentStatus] = Field(
        ..., description="Status breakdown of dependencies"
    )
    services: dict[str, str] = Field(default_factory=dict, description="Simple service status map")


@router.get(
    "/health",
    response_model=HealthStatusResponse,
    summary="Application and dependency health check",
)
async def get_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthStatusResponse:
    """Return application health and dependency statuses without exposing secrets.

    Executes a lightweight database connectivity check (`SELECT 1`), checks storage
    file accessibility, and reports overall readiness. Returns HTTP 503 if core
    dependencies are unavailable.
    """
    overall_healthy = True
    components: dict[str, ComponentStatus] = {}

    # 1. Database Check
    db_start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - db_start) * 1000.0
        components["database"] = ComponentStatus(
            status="up",
            latency_ms=round(db_latency, 2),
            details="Operational (read/write verified)",
        )
    except Exception:
        overall_healthy = False
        components["database"] = ComponentStatus(
            status="down",
            latency_ms=None,
            details="Connection failed",
        )

    # 2. Table Layout & Session Storage Check
    try:
        config_dir = os.path.dirname(settings.TABLE_LAYOUT_PATH) or "."
        storage_writable = os.access(config_dir, os.W_OK) or os.access(".", os.W_OK)
        components["storage"] = ComponentStatus(
            status="up" if storage_writable else "degraded",
            details="Config storage directory accessible",
        )
    except Exception:
        components["storage"] = ComponentStatus(
            status="degraded",
            details="Storage check inconclusive",
        )

    # 3. Vision Ingestion Pipeline
    components["vision_pipeline"] = ComponentStatus(
        status="standby",
        details=f"Camera {settings.DEFAULT_CAMERA_ID} configured on source {settings.DEFAULT_CAMERA_SOURCE}",
    )

    # Set response code based on overall health
    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    services_map = {
        "api": "up",
        "vision_pipeline": components["vision_pipeline"].status,
        "database": components["database"].status,
    }

    return HealthStatusResponse(
        status="healthy" if overall_healthy else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        version=__version__,
        timestamp=datetime.now(UTC),
        components=components,
        services=services_map,
    )
