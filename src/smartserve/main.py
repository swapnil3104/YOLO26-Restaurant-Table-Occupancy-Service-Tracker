"""Main FastAPI application entrypoint with security, error handling, and OpenAPI documentation."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from smartserve import __version__
from smartserve.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from smartserve.api.routes.analytics import router as analytics_router
from smartserve.api.routes.auth import router as auth_router
from smartserve.api.routes.cameras import router as cameras_router
from smartserve.api.routes.cameras import secured_camera_stream
from smartserve.api.routes.events import router as events_router
from smartserve.api.routes.floors import router as floors_router
from smartserve.api.routes.health import router as health_router
from smartserve.api.routes.occupancy import router as occupancy_router
from smartserve.api.routes.rules import router as rules_router
from smartserve.api.routes.tables import router as tables_router
from smartserve.api.routes.tracking_jobs import router as tracking_jobs_router
from smartserve.api.websocket import manager
from smartserve.config import settings
from smartserve.database.models import User
from smartserve.integrations.routes import router as integrations_router
from smartserve.security.auth import require_staff_actor

# Configure structured logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smartserve")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown routines."""
    logger.info(f"Starting {settings.APP_NAME} v{__version__} ({settings.APP_ENV})")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


TAGS_METADATA = [
    {
        "name": "Authentication",
        "description": "Staff login, token issuance, active identity introspection, and user registry.",
    },
    {
        "name": "Health",
        "description": "Application and dependency readiness probes without secret disclosure.",
    },
    {
        "name": "Cameras & Streaming",
        "description": "CCTV camera feeds, raw and CV-processed MJPEG streams, and real-time computer vision telemetry.",
    },
    {
        "name": "Tables",
        "description": "Polygon floorplan zone configuration, layout persistence, and spatial testing.",
    },
    {
        "name": "Occupancy",
        "description": "Real-time table occupancy state machines, guest counts, and manager overrides.",
    },
    {
        "name": "Events & Alerts",
        "description": "Operational service events, attendance/delivery confirmations, and alert management.",
    },
    {
        "name": "Service Timers & Rules",
        "description": "Response time calculations, food delivery timers, and configurable thresholds.",
    },
    {
        "name": "Analytics & Reports",
        "description": "Aggregated service KPIs, turnover rates, and privacy-compliant CSV exports.",
    },
    {
        "name": "Integrations",
        "description": "Hospitality POS order webhooks and kitchen bump bar (KDS) event ingestion.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "AI-powered restaurant table occupancy and service-timing tracker. "
        "Provides deterministic state tracking, threshold-driven alerting, "
        "and human-in-the-loop service verification."
    ),
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    contact={
        "name": "SmartServe Engineering",
        "email": "engineering@smartserve.local",
    },
    license_info={
        "name": "Proprietary / Pilot Evaluation",
    },
)

# Exception handlers for standardized error envelope
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Retry-After"],
)

# Register routes under /api/v1 (primary API)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(floors_router, prefix="/api/v1")
app.include_router(cameras_router, prefix="/api/v1")
app.include_router(tracking_jobs_router, prefix="/api/v1")
app.include_router(tables_router, prefix="/api/v1")
app.include_router(occupancy_router, prefix="/api/v1")
app.include_router(events_router)
app.include_router(rules_router)
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(integrations_router)

# Also expose illustrative /api aliases aligned with Docs/TASKS.md Phase 7 contracts
app.include_router(floors_router, prefix="/api")
app.include_router(cameras_router, prefix="/api")
app.include_router(tracking_jobs_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")


@app.get(
    "/api/streams/{camera_id}",
    tags=["Cameras & Streaming"],
    summary="Secured camera stream endpoint",
)
@app.get(
    "/api/v1/streams/{camera_id}",
    tags=["Cameras & Streaming"],
    summary="Secured camera stream endpoint",
)
async def get_stream_by_camera_id(
    camera_id: str,
    processed: bool = False,
    current_user: User = Depends(require_staff_actor),
):
    """Secured camera stream endpoint adhering to Docs/TASKS.md Phase 7."""
    return await secured_camera_stream(
        camera_id=camera_id, processed=processed, current_user=current_user
    )


def custom_openapi() -> dict[str, Any]:
    """Inject OpenAPI 3.1 security schemes and global requirements."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # Ensure security schemes are configured in components
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT access token or user identifier.",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-User-ID",
            "description": "Staff User ID or username identification header.",
        },
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint with links to OpenAPI documentation and health."""
    return {
        "app": settings.APP_NAME,
        "version": __version__,
        "status": "operational",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "health_url": "/api/v1/health",
    }


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time occupancy and alert broadcasts."""
    await manager.connect(websocket)
    try:
        await websocket.send_json(
            {"type": "connected", "data": {"app": settings.APP_NAME, "version": __version__}}
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
