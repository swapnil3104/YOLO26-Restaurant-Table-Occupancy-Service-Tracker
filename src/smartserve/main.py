"""Main FastAPI application entrypoint."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from smartserve import __version__
from smartserve.api.routes.health import router as health_router
from smartserve.api.websocket import manager
from smartserve.config import settings

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
    # Startup: verification of dependencies, database connection, etc.
    yield
    # Shutdown: cleanup vision streams and connections
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description="AI-powered restaurant table occupancy and service-timing tracker",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root metadata endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": __version__,
        "status": "operational",
        "docs_url": "/docs",
        "health_url": "/api/v1/health",
    }


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time occupancy and alert broadcasts."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open and receive potential client heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
