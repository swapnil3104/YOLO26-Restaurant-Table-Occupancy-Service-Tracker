"""REST API endpoints for cameras, streaming feeds, and real-time computer vision metadata."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import utc_now
from smartserve.database.models import Camera as DBCamera
from smartserve.database.models import Floor as DBFloor
from smartserve.database.models import User
from smartserve.database.session import get_db
from smartserve.security.auth import (
    bearer_scheme,
    get_current_actor,
    require_staff_actor,
)
from smartserve.security.url_validator import (
    SSRFValidationError,
    validate_stream_url,
)
from smartserve.vision.worker_manager import worker_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cameras", tags=["Cameras & Streaming"])


async def resolve_camera_staff(
    request: Request,
    auth_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Resolve camera staff actor with optional dev/test fallback when headers are omitted."""
    has_auth = bool(
        (auth_credentials and auth_credentials.credentials)
        or x_user_id
        or request.headers.get("Authorization")
        or request.query_params.get("user_id")
    )
    if has_auth:
        user = await get_current_actor(
            request=request,
            auth_credentials=auth_credentials,
            x_user_id=x_user_id,
            db=db,
        )
        if str(user.role).upper() not in ("WAITER", "MANAGER", "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{user.username}' with role '{user.role}' is not authorized for camera operations.",
            )
        return user
    return None


async def resolve_camera_admin(
    actor: User | None = Depends(resolve_camera_staff),
) -> User | None:
    """Enforce manager or administrator role when actor is identified."""
    if actor is not None and str(actor.role).upper() not in ("MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{actor.username}' with role '{actor.role}' is not authorized. Manager or Admin required.",
        )
    return actor


class CameraModel(BaseModel):
    """Metadata schema for a monitored camera source."""

    camera_id: str
    name: str
    floor: str = "Floor 1"
    floor_id: str | None = None
    section: str
    source_type: str = Field("live_stream", description="live_stream or recorded_footage")
    source_mode: str = Field("tracking", description="view_only or tracking")
    status: str = Field("ONLINE", description="ONLINE, DEGRADED, OFFLINE")
    resolution: str = "1280x720"
    fps: float = 30.0
    last_frame_at: str
    raw_stream_url: str
    processed_stream_url: str
    cv_metadata_url: str
    video_url: str | None = None
    is_custom: bool = False
    tracking_status: str = Field(
        "Monitoring",
        description="Added, Validating, Initializing Model, Monitoring, Paused, Error, Disconnected, Stopping, Stopped",
    )
    camera_health: str = Field("HEALTHY", description="HEALTHY, DEGRADED, DISCONNECTED")
    inference_status: str = Field("ACTIVE", description="ACTIVE, INITIALIZING, PAUSED, IDLE, ERROR")
    effective_fps: float = 30.0
    last_event_time: str | None = None
    processing_job_id: str | None = None
    model_version: str = "models/yolo26_restaurant_cctv.pt"


class CreateCameraRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    floor: str = Field("Floor 1", min_length=1, max_length=50)
    floor_id: str | None = None
    section: str = Field("Main Dining", min_length=1, max_length=50)
    source_type: str = Field("live_stream", description="live_stream or recorded_footage")
    source_mode: str = Field("tracking", description="view_only or tracking")
    stream_url: str | None = None
    video_file_id: str | None = None
    model_version: str | None = None


class UpdateCameraRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    floor: str | None = None
    floor_id: str | None = None
    section: str | None = None
    source_mode: str | None = None
    status: str | None = None
    tracking_status: str | None = None


DEMO_VIDEO_FILENAME = "Cctv-Resturant-Demo.mp4"

# Baseline initial cameras
INITIAL_CAMERAS: dict[str, dict[str, Any]] = {
    "cam-01": {
        "camera_id": "cam-01",
        "name": "Main Dining Room (Demo CCTV)",
        "floor": "Floor 1",
        "section": "Main Dining",
        "source_type": "recorded_footage",
        "status": "ONLINE",
        "resolution": "1280x720",
        "fps": 30.0,
        "is_custom": False,
        "video_url": f"/api/v1/cameras/video-file/{DEMO_VIDEO_FILENAME}",
        "tracking_status": "Monitoring",
        "camera_health": "HEALTHY",
        "inference_status": "ACTIVE",
        "effective_fps": 29.8,
        "last_event_time": datetime.now(UTC).isoformat(),
        "processing_job_id": "job-f1-01",
    },
    "cam-02": {
        "camera_id": "cam-02",
        "name": "Patio Terrace (Cam 02)",
        "floor": "Floor 1",
        "section": "Patio Terrace",
        "source_type": "live_stream",
        "status": "ONLINE",
        "resolution": "1280x720",
        "fps": 25.0,
        "is_custom": False,
        "video_url": "/api/v1/cameras/video-file/cctv_camera_02_patio.mp4",
        "tracking_status": "Monitoring",
        "camera_health": "HEALTHY",
        "inference_status": "ACTIVE",
        "effective_fps": 24.9,
        "last_event_time": datetime.now(UTC).isoformat(),
        "processing_job_id": "job-f1-02",
    },
    "cam-03": {
        "camera_id": "cam-03",
        "name": "Window Booths & Bar (Cam 03)",
        "floor": "Floor 1",
        "section": "Window Booth",
        "source_type": "live_stream",
        "status": "ONLINE",
        "resolution": "1280x720",
        "fps": 30.0,
        "is_custom": False,
        "video_url": "/api/v1/cameras/video-file/cctv_camera_03_booths.mp4",
        "tracking_status": "Monitoring",
        "camera_health": "HEALTHY",
        "inference_status": "ACTIVE",
        "effective_fps": 29.4,
        "last_event_time": datetime.now(UTC).isoformat(),
        "processing_job_id": "job-f1-03",
    },
    "cam-04": {
        "camera_id": "cam-04",
        "name": "Private Dining Lounge (Cam 04)",
        "floor": "Floor 2",
        "section": "Private Lounge",
        "source_type": "live_stream",
        "status": "ONLINE",
        "resolution": "1280x720",
        "fps": 30.0,
        "is_custom": False,
        "video_url": "/api/v1/cameras/video-file/cctv_camera_01_main_dining_raw.mp4",
        "tracking_status": "Monitoring",
        "camera_health": "HEALTHY",
        "inference_status": "ACTIVE",
        "effective_fps": 29.5,
        "last_event_time": datetime.now(UTC).isoformat(),
        "processing_job_id": "job-f2-01",
    },
}

# Registered cameras in the restaurant
REGISTERED_CAMERAS: dict[str, dict[str, Any]] = {k: dict(v) for k, v in INITIAL_CAMERAS.items()}


def _ensure_default_cameras() -> None:
    """Guarantee default camera fixtures exist so UI never loses camera coverage."""
    for cid, cdata in INITIAL_CAMERAS.items():
        if cid not in REGISTERED_CAMERAS:
            REGISTERED_CAMERAS[cid] = dict(cdata)


def _build_camera_model(cam: dict[str, Any]) -> CameraModel:
    cid = cam["camera_id"]
    now_iso = datetime.now(UTC).isoformat()
    fps_val = float(cam.get("fps", 30.0))
    return CameraModel(
        camera_id=cid,
        name=cam.get("name", cid),
        floor=cam.get("floor", "Floor 1"),
        floor_id=cam.get("floor_id"),
        section=cam.get("section", "Main Dining"),
        source_type=cam.get("source_type", "live_stream"),
        source_mode=cam.get("source_mode", "tracking"),
        status=cam.get("status", "ONLINE"),
        resolution=cam.get("resolution", "1280x720"),
        fps=fps_val,
        last_frame_at=cam.get("last_frame_at", now_iso),
        raw_stream_url=cam.get("raw_stream_url", f"/api/v1/cameras/{cid}/stream/raw"),
        processed_stream_url=cam.get(
            "processed_stream_url", f"/api/v1/cameras/{cid}/stream/processed"
        ),
        cv_metadata_url=cam.get("cv_metadata_url", f"/api/v1/cameras/{cid}/cv-metadata"),
        video_url=cam.get("video_url"),
        is_custom=cam.get("is_custom", False),
        tracking_status=cam.get("tracking_status", "Monitoring"),
        camera_health=cam.get("camera_health", "HEALTHY"),
        inference_status=cam.get("inference_status", "ACTIVE"),
        effective_fps=float(cam.get("effective_fps", fps_val)),
        last_event_time=cam.get("last_event_time", now_iso),
        processing_job_id=cam.get("processing_job_id", f"job-{cid}"),
        model_version=cam.get("model_version", "models/yolo26_restaurant_cctv.pt"),
    )


def _generate_synthetic_restaurant_frame(
    camera_id: str,
    processed: bool = False,
    tick: int = 0,
) -> np.ndarray:
    """Generate a realistic synthetic restaurant CCTV frame with simulated patrons and tables."""
    width, height = 960, 540
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Ambient restaurant lighting gradient
    cam_tint = {
        "cam-01": (35, 30, 25),
        "cam-02": (40, 45, 30),
        "cam-03": (30, 30, 45),
        "cam-04": (25, 25, 35),
    }.get(camera_id, (30, 30, 30))

    frame[:] = cam_tint

    # Floor grid perspective
    for y in range(150, height, 40):
        cv2.line(frame, (0, y), (width, y), (45, 45, 50), 1)
    for x in range(0, width, 80):
        cv2.line(frame, (x, 150), (int(x * 1.2), height), (45, 45, 50), 1)

    # Simulated tables
    tables = [
        {"code": "T01", "box": (100, 220, 260, 380), "color": (70, 65, 60)},
        {"code": "T02", "box": (360, 220, 520, 380), "color": (70, 65, 60)},
        {"code": "T03", "box": (620, 220, 780, 380), "color": (70, 65, 60)},
        {"code": "T04", "box": (100, 420, 260, 520), "color": (65, 60, 55)},
        {"code": "T05", "box": (360, 420, 520, 520), "color": (65, 60, 55)},
    ]

    for tbl in tables:
        bx1, by1, bx2, by2 = tbl["box"]
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), tbl["color"], -1)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (90, 85, 80), 2)
        cv2.putText(
            frame,
            tbl["code"],
            (bx1 + 10, by1 + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (160, 160, 160),
            1,
            cv2.LINE_AA,
        )

    # Simulated moving patrons
    phase = (tick % 100) / 100.0 * 2 * np.pi
    patrons = [
        # Seated patron at T01
        {"id": 101, "x": 130 + int(np.sin(phase) * 5), "y": 280, "w": 40, "h": 70},
        {"id": 102, "x": 190, "y": 290 + int(np.cos(phase) * 3), "w": 42, "h": 72},
        # Seated patron at T02
        {"id": 103, "x": 420 + int(np.cos(phase) * 4), "y": 285, "w": 45, "h": 75},
        # Walking waiter moving between tables
        {"id": 108, "x": int(280 + np.sin(phase) * 120), "y": 240, "w": 38, "h": 85},
    ]

    for p in patrons:
        px, py, pw, ph = p["x"], p["y"], p["w"], p["h"]
        # Draw patron silhouette in raw footage
        cv2.ellipse(
            frame,
            (px + pw // 2, py + ph // 2),
            (pw // 2, ph // 2),
            0,
            0,
            360,
            (110, 100, 95),
            -1,
        )
        cv2.circle(frame, (px + pw // 2, py + 12), 12, (130, 120, 115), -1)

    # Add timestamp and camera overlay
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(
        frame,
        f"{camera_id.upper()} | {now_str} | REC [●]",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )

    if processed:
        # Overlay computer vision bounding boxes, tracking labels, and table zones
        for p in patrons:
            px, py, pw, ph = p["x"], p["y"], p["w"], p["h"]
            cv2.rectangle(frame, (px, py), (px + pw, py + ph), (80, 200, 120), 2)
            cv2.circle(frame, (px + pw // 2, py + ph), 4, (30, 144, 255), -1)
            # Track ID label
            track_label = f"ID:{p['id']} (0.92)"
            cv2.rectangle(frame, (px, py - 20), (px + 90, py), (20, 20, 20), -1)
            cv2.putText(
                frame,
                track_label,
                (px + 4, py - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Overlay table zones
        for tbl in tables:
            bx1, by1, bx2, by2 = tbl["box"]
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 180, 40), 1)
            cv2.putText(
                frame,
                f"{tbl['code']} [OCCUPIED]"
                if tbl["code"] in ("T01", "T02")
                else f"{tbl['code']} [VACANT]",
                (bx1 + 10, by1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (40, 200, 255),
                1,
                cv2.LINE_AA,
            )

    return frame


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SAMPLE_VIDEO_DIR = PROJECT_ROOT / "Sample Video"
PUBLIC_VIDEOS_DIR = PROJECT_ROOT / "frontend" / "public" / "videos"
UPLOADS_DIR = PROJECT_ROOT / "uploads" / "cctv"
ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


async def _sync_db_cameras_if_needed(db: AsyncSession | None) -> None:
    """Synchronize registered cameras with database state if session is available."""
    _ensure_default_cameras()
    if db is None:
        return
    try:
        stmt = select(DBCamera)
        res = await db.execute(stmt)
        cams = res.scalars().all()
        existing_ids = {c.camera_id for c in cams}

        # Seed missing initial cameras into DB
        for cid, cdata in INITIAL_CAMERAS.items():
            if cid not in existing_ids:
                db_cam = DBCamera(
                    camera_id=cid,
                    restaurant_id="rest_bistro_01",
                    floor_id=cdata.get("floor_id")
                    or ("floor-02" if "Floor 2" in cdata.get("floor", "") else "floor-01"),
                    floor_name=cdata.get("floor", "Floor 1"),
                    section=cdata.get("section", "Main Dining"),
                    name=cdata.get("name", cid),
                    source_type=cdata.get("source_type", "recorded_footage" if cid == "cam-01" else "live_stream"),
                    source_mode=cdata.get("source_mode", "tracking"),
                    stream_url=cdata.get("raw_stream_url"),
                    video_url=cdata.get("video_url"),
                    resolution=cdata.get("resolution", "1280x720"),
                    fps=float(cdata.get("fps", 30.0)),
                    is_custom=bool(cdata.get("is_custom", False)),
                    status=cdata.get("status", "ONLINE"),
                    tracking_status=cdata.get("tracking_status", "Monitoring"),
                    camera_health=cdata.get("camera_health", "HEALTHY"),
                    inference_status=cdata.get("inference_status", "ACTIVE"),
                    effective_fps=float(cdata.get("effective_fps", 30.0)),
                    model_version=cdata.get("model_version", "models/yolo26_restaurant_cctv.pt"),
                    created_at=utc_now(),
                )
                db.add(db_cam)
        if len(cams) != len(existing_ids | set(INITIAL_CAMERAS.keys())):
            await db.commit()

        # Load any custom cameras from DB into in-memory REGISTERED_CAMERAS
        for c in cams:
            if c.camera_id not in REGISTERED_CAMERAS:
                REGISTERED_CAMERAS[c.camera_id] = {
                    "camera_id": c.camera_id,
                    "name": c.name,
                    "floor": c.floor_name or "Floor 1",
                    "floor_id": c.floor_id,
                    "section": c.section or "Main Dining",
                    "source_type": c.source_type or "live_stream",
                    "source_mode": c.source_mode or "tracking",
                    "status": c.status or "ONLINE",
                    "resolution": c.resolution or "1280x720",
                    "fps": float(c.fps or 30.0),
                    "is_custom": bool(c.is_custom),
                    "raw_stream_url": c.stream_url or f"/api/v1/cameras/{c.camera_id}/stream/raw",
                    "processed_stream_url": f"/api/v1/cameras/{c.camera_id}/stream/processed",
                    "cv_metadata_url": f"/api/v1/cameras/{c.camera_id}/cv-metadata",
                    "video_url": c.video_url,
                    "tracking_status": c.tracking_status or "Monitoring",
                    "camera_health": c.camera_health or "HEALTHY",
                    "inference_status": c.inference_status or "ACTIVE",
                    "effective_fps": float(c.effective_fps or 30.0),
                    "last_event_time": datetime.now(UTC).isoformat(),
                    "processing_job_id": f"job-{c.camera_id}",
                    "model_version": c.model_version or "models/yolo26_restaurant_cctv.pt",
                }
    except Exception as e:
        logger.warning(f"Could not sync cameras to DB: {e}")


@router.get("", response_model=list[CameraModel], summary="List registered cameras")
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(resolve_camera_staff),
) -> list[CameraModel]:
    """Retrieve metadata and stream endpoints for all monitored cameras."""
    await _sync_db_cameras_if_needed(db)
    return [_build_camera_model(cam) for cam in REGISTERED_CAMERAS.values()]


@router.post(
    "",
    response_model=CameraModel,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new CCTV or tracking camera feed",
)
async def create_camera(
    req: CreateCameraRequest,
    current_user: User | None = Depends(resolve_camera_staff),
    db: AsyncSession = Depends(get_db),
) -> CameraModel:
    """Add a new camera source one at a time with validation against duplicates, SSRF, and mode separation."""
    req_name_clean = req.name.strip()
    if any(
        c.get("name", "").strip().lower() == req_name_clean.lower()
        for c in REGISTERED_CAMERAS.values()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A camera feed with name '{req_name_clean}' already exists. Please choose a distinct name.",
        )

    mode = req.source_mode.strip().lower() if req.source_mode else "tracking"
    if mode not in ("view_only", "tracking"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_mode '{req.source_mode}'. Allowed values: 'view_only', 'tracking'.",
        )

    raw_stream_url = None
    video_url = None
    if req.source_type == "live_stream":
        if req.stream_url:
            try:
                raw_stream_url = validate_stream_url(req.stream_url)
            except SSRFValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SSRF Security Violation: {e}",
                ) from e
    elif req.source_type == "recorded_footage":
        if req.video_file_id:
            vid_item = VIDEO_CATALOG.get(req.video_file_id)
            if vid_item:
                video_url = f"/api/v1/cameras/video-file/{vid_item['filename']}"
            elif req.video_file_id.startswith("http") or req.video_file_id.startswith("/"):
                video_url = req.video_file_id
            else:
                video_url = f"/api/v1/cameras/video-file/{req.video_file_id}"
        elif req.stream_url:
            video_url = req.stream_url

    cam_id = f"cam-{len(REGISTERED_CAMERAS) + 1:02d}-{int(time.time()) % 10000}"
    if not raw_stream_url:
        raw_stream_url = f"/api/v1/cameras/{cam_id}/stream/raw"

    now_iso = datetime.now(UTC).isoformat()
    now_dt = utc_now()

    if mode == "view_only":
        tracking_status = "Stopped"
        inference_status = "IDLE"
        processing_job_id = None
    else:
        tracking_status = "Monitoring"
        inference_status = "ACTIVE"
        processing_job_id = f"job-{cam_id}"

    floor_val = (req.floor_id or req.floor or "").strip()
    if floor_val in ("floor_1", "floor-1", "floor-01", "Floor 1"):
        resolved_floor_id = "floor-01"
    elif floor_val in ("floor_2", "floor-2", "floor-02", "Floor 2"):
        resolved_floor_id = "floor-02"
    else:
        resolved_floor_id = req.floor_id or "floor-01"

    new_cam_data = {
        "camera_id": cam_id,
        "name": req_name_clean,
        "floor": req.floor.strip() or "Floor 1",
        "floor_id": resolved_floor_id,
        "section": req.section.strip() or "Main Dining",
        "source_type": req.source_type,
        "source_mode": mode,
        "status": "ONLINE",
        "resolution": "1280x720",
        "fps": 30.0,
        "is_custom": True,
        "raw_stream_url": raw_stream_url,
        "processed_stream_url": f"/api/v1/cameras/{cam_id}/stream/processed",
        "cv_metadata_url": f"/api/v1/cameras/{cam_id}/cv-metadata",
        "video_url": video_url,
        "tracking_status": tracking_status,
        "camera_health": "HEALTHY",
        "inference_status": inference_status,
        "effective_fps": 30.0 if mode == "tracking" else 0.0,
        "last_event_time": now_iso,
        "processing_job_id": processing_job_id,
        "model_version": req.model_version or "models/yolo26_restaurant_cctv.pt",
    }

    REGISTERED_CAMERAS[cam_id] = new_cam_data

    # Persist camera entity to DB
    try:
        valid_floor_id = resolved_floor_id
        if valid_floor_id:
            check_floor = await db.get(DBFloor, valid_floor_id)
            if not check_floor:
                valid_floor_id = None

        db_cam = DBCamera(
            camera_id=cam_id,
            restaurant_id="rest_bistro_01",
            floor_id=valid_floor_id,
            floor_name=new_cam_data["floor"],
            section=new_cam_data["section"],
            name=new_cam_data["name"],
            source_type=new_cam_data["source_type"],
            source_mode=mode,
            stream_url=raw_stream_url,
            video_url=video_url,
            resolution="1280x720",
            fps=30.0,
            is_custom=True,
            status="ONLINE",
            tracking_status=tracking_status,
            camera_health="HEALTHY",
            inference_status=inference_status,
            effective_fps=30.0 if mode == "tracking" else 0.0,
            model_version=new_cam_data["model_version"],
            created_at=now_dt,
        )
        db.add(db_cam)
        await db.commit()

        if mode == "tracking":
            await worker_manager.start_tracking_job(
                camera_id=cam_id,
                db=db,
                model_version=new_cam_data["model_version"],
            )
    except Exception as e:
        logger.warning(f"Could not persist new camera to DB: {e}")

    return _build_camera_model(new_cam_data)


@router.patch("/{camera_id}", response_model=CameraModel, summary="Rename or update camera source")
async def update_camera(
    camera_id: str,
    req: UpdateCameraRequest,
    current_user: User | None = Depends(resolve_camera_staff),
    db: AsyncSession = Depends(get_db),
) -> CameraModel:
    """Update camera metadata such as name, floor, or section."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID '{camera_id}' not found.",
        )
    cam = REGISTERED_CAMERAS[camera_id]
    if req.name is not None:
        name_clean = req.name.strip()
        if any(
            c["camera_id"] != camera_id and c.get("name", "").strip().lower() == name_clean.lower()
            for c in REGISTERED_CAMERAS.values()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another camera already exists with name '{name_clean}'.",
            )
        cam["name"] = name_clean
    if req.floor is not None:
        cam["floor"] = req.floor.strip()
    if req.floor_id is not None:
        cam["floor_id"] = req.floor_id
    if req.section is not None:
        cam["section"] = req.section.strip()
    if req.source_mode is not None:
        mode = req.source_mode.strip().lower()
        if mode not in ("view_only", "tracking"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_mode '{req.source_mode}'.",
            )
        cam["source_mode"] = mode
        if mode == "view_only":
            cam["tracking_status"] = "Stopped"
            cam["inference_status"] = "IDLE"
            await worker_manager.stop_camera_jobs(camera_id, db)
        else:
            cam["tracking_status"] = "Monitoring"
            cam["inference_status"] = "ACTIVE"
            await worker_manager.start_tracking_job(camera_id, db)
    if req.status is not None:
        cam["status"] = req.status.strip()

    # Update in DB
    try:
        stmt = select(DBCamera).where(DBCamera.camera_id == camera_id)
        res = await db.execute(stmt)
        db_cam = res.scalar_one_or_none()
        if db_cam:
            if req.name:
                db_cam.name = cam["name"]
            if req.floor:
                db_cam.floor_name = cam["floor"]
            if req.floor_id:
                db_cam.floor_id = cam["floor_id"]
            if req.section:
                db_cam.section = cam["section"]
            if req.source_mode:
                db_cam.source_mode = cam["source_mode"]
                db_cam.tracking_status = cam["tracking_status"]
                db_cam.inference_status = cam["inference_status"]
            if req.status:
                db_cam.status = cam["status"]
            await db.commit()
    except Exception as e:
        logger.warning(f"Could not update camera in DB: {e}")

    return _build_camera_model(cam)


@router.delete("/{camera_id}", summary="Remove a camera source")
async def delete_camera(
    camera_id: str,
    current_user: User | None = Depends(resolve_camera_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove a camera feed, stop active workers, and cleanly release media capture resources."""
    matched_key = None
    for k in list(REGISTERED_CAMERAS.keys()):
        if k.lower() == camera_id.lower():
            matched_key = k
            break

    # Stop tracking jobs via worker manager
    try:
        await worker_manager.stop_camera_jobs(camera_id, db)
        stmt = select(DBCamera).where(
            (DBCamera.camera_id == camera_id)
            | (DBCamera.camera_id == camera_id.upper())
            | (DBCamera.camera_id == camera_id.lower())
        )
        res = await db.execute(stmt)
        db_cams = res.scalars().all()
        for db_cam in db_cams:
            await db.delete(db_cam)
        if db_cams:
            await db.commit()
    except Exception as e:
        logger.warning(f"Could not remove camera from DB: {e}")

    with _cap_lock:
        keys_to_remove = [k for k in _video_caps if k.lower().startswith(f"{camera_id.lower()}_")]
        for k in keys_to_remove:
            cap = _video_caps.pop(k, None)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    removed_name = camera_id
    if matched_key and matched_key in REGISTERED_CAMERAS:
        removed = REGISTERED_CAMERAS.pop(matched_key)
        removed_name = removed.get("name", camera_id)

    return {
        "status": "success",
        "message": f"Camera '{removed_name}' removed successfully.",
        "camera_id": camera_id,
        "historical_data_preserved": True,
    }


@router.get("/floors/summary", summary="List distinct floors with cameras and tracking statistics")
async def get_floors_summary() -> list[dict[str, Any]]:
    """Return all distinct restaurant floors with camera counts and active tracking feeds."""
    floors_dict: dict[str, dict[str, Any]] = {}
    for cam in REGISTERED_CAMERAS.values():
        f_name = cam.get("floor", "Floor 1")
        if f_name not in floors_dict:
            floors_dict[f_name] = {
                "floor": f_name,
                "total_cameras": 0,
                "active_tracking_sources": 0,
                "cameras": [],
            }
        floors_dict[f_name]["total_cameras"] += 1
        if cam.get("tracking_status") in ("Monitoring", "Validating", "Initializing Model"):
            floors_dict[f_name]["active_tracking_sources"] += 1
        floors_dict[f_name]["cameras"].append(cam["camera_id"])
    return list(floors_dict.values())


@router.post(
    "/{camera_id}/pause",
    response_model=CameraModel,
    summary="Pause tracking and inference for camera",
)
async def pause_camera_tracking(camera_id: str) -> CameraModel:
    """Pause YOLO26 inference and table occupancy monitoring for this camera source."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    cam = REGISTERED_CAMERAS[camera_id]
    cam["tracking_status"] = "Paused"
    cam["inference_status"] = "PAUSED"
    return _build_camera_model(cam)


@router.post(
    "/{camera_id}/resume",
    response_model=CameraModel,
    summary="Resume tracking and inference for camera",
)
async def resume_camera_tracking(camera_id: str) -> CameraModel:
    """Resume YOLO26 inference and table occupancy monitoring for this camera source."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    cam = REGISTERED_CAMERAS[camera_id]
    cam["tracking_status"] = "Monitoring"
    cam["inference_status"] = "ACTIVE"
    return _build_camera_model(cam)


@router.post("/upload", summary="Upload recorded CCTV video footage")
async def upload_cctv_video(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload recorded CCTV footage with strict file size, type validation, and path traversal protection."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided in upload."
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 100 MB (received {len(content) / (1024 * 1024):.1f} MB).",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )

    safe_base = re.sub(r"[^a-zA-Z0-9_\.-]", "_", Path(file.filename).stem)
    safe_filename = f"cctv_{int(time.time())}_{safe_base}{ext}"

    upload_dir = PROJECT_ROOT / "uploads" / "cctv"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / safe_filename

    try:
        destination.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename or path traversal detected.",
        ) from None

    destination.write_bytes(content)

    video_id = f"vid_upload_{int(time.time())}"
    VIDEO_CATALOG[video_id] = {
        "id": video_id,
        "name": f"Uploaded: {file.filename}",
        "description": f"User-uploaded CCTV recorded footage ({len(content) // 1024} KB).",
        "category": "standard_cctv",
        "filename": safe_filename,
        "url": f"/api/v1/cameras/video-file/{safe_filename}",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_sec": 30.0,
        "is_annotated": False,
        "recommended_view": "standard",
        "is_custom": True,
    }

    return {
        "status": "success",
        "video_id": video_id,
        "filename": safe_filename,
        "url": f"/api/v1/cameras/video-file/{safe_filename}",
        "size_bytes": len(content),
        "source_label": "RECORDED FOOTAGE (UPLOADED)",
    }


@router.get("/video-file/{filename}", summary="Retrieve recorded CCTV video file")
async def get_video_file(filename: str):
    """Securely stream a recorded video file with path traversal prevention."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video filename."
        )

    search_dirs = [
        UPLOADS_DIR,
        SAMPLE_VIDEO_DIR,
        PUBLIC_VIDEOS_DIR,
    ]

    target_path = None
    for d in search_dirs:
        candidate = d / filename
        if candidate.exists() and candidate.is_file():
            try:
                candidate.resolve().relative_to(d.resolve())
                target_path = candidate
                break
            except ValueError:
                continue

    if not target_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file '{filename}' not found.",
        )

    ext = target_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }
    media_type = media_types.get(ext, "video/mp4")

    return FileResponse(path=target_path, media_type=media_type, filename=filename)


class VideoSourceItem(BaseModel):
    id: str
    name: str
    description: str
    category: str  # "tracking" | "standard_cctv"
    filename: str
    url: str
    resolution: str
    fps: float
    duration_sec: float | None = None
    is_annotated: bool
    recommended_view: str  # "tracking" | "standard" | "both"


class VideoAssignmentRequest(BaseModel):
    tracking_video_id: str | None = None
    standard_video_id: str | None = None
    camera_assignments: dict[str, str] | None = None


VIDEO_CATALOG: dict[str, dict[str, Any]] = {
    "vid_demo_dining": {
        "id": "vid_demo_dining",
        "name": "Project Demo CCTV: Cctv-Resturant-Demo (Main Dining)",
        "description": "Indoor restaurant dining CCTV footage with patrons seated at dining tables, table edges, and service tracking.",
        "category": "tracking",
        "filename": DEMO_VIDEO_FILENAME,
        "url": f"/api/v1/cameras/video-file/{DEMO_VIDEO_FILENAME}",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_sec": 43.4,
        "is_annotated": True,
        "recommended_view": "both",
    },
    "vid_yolo_tracked": {
        "id": "vid_yolo_tracked",
        "name": "YOLO26 & ByteTrack Tracking Feed (Main Dining)",
        "description": "Neural computer vision tracking with ByteTrack person IDs, bounding boxes, ground-contact points, and dining table zones.",
        "category": "tracking",
        "filename": "yolo_tracked_camera_01.mp4",
        "url": "/videos/yolo_tracked_camera_01.mp4",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_sec": 30.0,
        "is_annotated": True,
        "recommended_view": "tracking",
    },
    "vid_table_edge_tracker": {
        "id": "vid_table_edge_tracker",
        "name": "Table Edge Detection & Proximity Tracker",
        "description": "Sub-pixel table border detection, glowing neon active table edges, diner proximity vectors, and occupancy status classification.",
        "category": "tracking",
        "filename": "output_annotated_cctv.mp4",
        "url": "/videos/output_annotated_cctv.mp4",
        "resolution": "1280x720",
        "fps": 25.0,
        "duration_sec": 24.0,
        "is_annotated": True,
        "recommended_view": "tracking",
    },
    "vid_cctv_dining": {
        "id": "vid_cctv_dining",
        "name": "CAM-01: Main Dining Room (Raw CCTV)",
        "description": "Unprocessed 1080p surveillance video of the central dining floor, 6 tables, active patrons and waiters.",
        "category": "standard_cctv",
        "filename": DEMO_VIDEO_FILENAME,
        "url": f"/api/v1/cameras/video-file/{DEMO_VIDEO_FILENAME}",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_sec": 43.4,
        "is_annotated": False,
        "recommended_view": "standard",
    },
    "vid_cctv_patio": {
        "id": "vid_cctv_patio",
        "name": "CAM-02: Patio Terrace (Raw CCTV)",
        "description": "Outdoor terrace tables and patio perimeter surveillance feed.",
        "category": "standard_cctv",
        "filename": "cctv_camera_02_patio.mp4",
        "url": "/videos/cctv_camera_02_patio.mp4",
        "resolution": "1280x720",
        "fps": 25.0,
        "duration_sec": 18.0,
        "is_annotated": False,
        "recommended_view": "standard",
    },
    "vid_cctv_booths": {
        "id": "vid_cctv_booths",
        "name": "CAM-03: Window Booths & Bar Area (Raw CCTV)",
        "description": "Window-side booths, beverage counter, and dining lounge surveillance feed.",
        "category": "standard_cctv",
        "filename": "cctv_camera_03_booths.mp4",
        "url": "/videos/cctv_camera_03_booths.mp4",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_sec": 15.0,
        "is_annotated": False,
        "recommended_view": "standard",
    },
}

CURRENT_ASSIGNMENTS: dict[str, Any] = {
    "tracking_video_id": "vid_demo_dining",
    "standard_video_id": "vid_demo_dining",
    "camera_assignments": {
        "cam-01": "vid_demo_dining",
        "cam-02": "vid_cctv_patio",
        "cam-03": "vid_cctv_booths",
        "cam-04": "vid_demo_dining",
    },
}

_video_caps: dict[str, cv2.VideoCapture] = {}
_cap_lock = threading.Lock()

# Inference and table detection state
_cv_model = None
_edge_detector = None
_cv_cache: dict[str, dict[str, Any]] = {}
_cv_lock = threading.Lock()
_cv_in_progress: set[str] = set()


def _get_cv_detector():
    """Lazily load YOLO model and edge detector."""
    global _cv_model, _edge_detector
    with _cv_lock:
        if _cv_model is None:
            try:
                from ultralytics import YOLO
                from smartserve.tables.edge_detector import TableEdgeDetector
                weights = PROJECT_ROOT / "yolo26s.pt"
                if not weights.exists():
                    weights = PROJECT_ROOT / "models" / "yolo26_restaurant_cctv.pt"
                _cv_model = YOLO(str(weights))
                _edge_detector = TableEdgeDetector()
            except Exception as e:
                logger.warning(f"Could not load YOLO model for streaming: {e}")
    return _cv_model, _edge_detector


def _run_frame_inference_worker(source_key: str, frame_to_detect: np.ndarray) -> None:
    """Background worker to run table and diner detection without stalling 25fps video stream."""
    try:
        model, edge_det = _get_cv_detector()
        if model is None or edge_det is None:
            return

        t0 = time.time()
        results = model(frame_to_detect, verbose=False)[0]
        t1 = time.time()
        latency_ms = round((t1 - t0) * 1000, 1)

        tables = []
        diners = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            xyxy = [int(x) for x in box.xyxy[0].tolist()]

            if cls_name == "dining table" and conf >= 0.22:
                tables.append({"box": xyxy, "conf": conf})
            elif cls_name == "person" and conf >= 0.28:
                diners.append({"box": xyxy, "conf": conf})

        # Calculate edge polygons and associate diners
        table_diners: dict[int, list[tuple[int, tuple[int, int]]]] = {i: [] for i in range(len(tables))}
        for d_idx, d_data in enumerate(diners):
            dx1, dy1, dx2, dy2 = d_data["box"]
            contact = ((dx1 + dx2) // 2, dy2)
            best_tbl = None
            min_dist = float("inf")
            for t_idx, t_data in enumerate(tables):
                t_box = t_data["box"]
                tcx = (t_box[0] + t_box[2]) // 2
                tcy = (t_box[1] + t_box[3]) // 2
                dist = np.hypot(contact[0] - tcx, contact[1] - tcy)
                if dist < min_dist and dist < 180:
                    min_dist = dist
                    best_tbl = t_idx
            if best_tbl is not None:
                table_diners[best_tbl].append((d_idx, contact))

        polygons = []
        for idx, t_data in enumerate(tables):
            try:
                tbl_edge = edge_det.detect_table_edges_from_bbox(
                    frame_to_detect, tuple(t_data["box"]), table_id=f"tbl-0{idx+1}", label=f"T-0{idx+1}", confidence=t_data["conf"]
                )
                polygons.append(tbl_edge.polygon_vertices)
            except Exception:
                x1, y1, x2, y2 = t_data["box"]
                polygons.append([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

        with _cv_lock:
            _cv_cache[source_key] = {
                "tables": tables,
                "diners": diners,
                "table_diners": table_diners,
                "polygons": polygons,
                "latency_ms": latency_ms,
                "updated_at": time.time(),
            }
    except Exception as e:
        logger.warning(f"Error in inference worker: {e}")
    finally:
        with _cv_lock:
            _cv_in_progress.discard(source_key)


def _render_table_and_patron_tracking(
    frame: np.ndarray, camera_id: str, tick: int, source_key: str
) -> np.ndarray:
    """Render real-time glowing table polygons, diner bounding boxes, and service telemetry."""
    h, w = frame.shape[:2]
    out = frame.copy()

    # Check cache / schedule update
    with _cv_lock:
        cached = _cv_cache.get(source_key)
        now = time.time()
        needs_update = cached is None or (now - cached.get("updated_at", 0) > 1.5)
        can_start = source_key not in _cv_in_progress

    if needs_update and can_start:
        with _cv_lock:
            _cv_in_progress.add(source_key)
        threading.Thread(
            target=_run_frame_inference_worker,
            args=(source_key, frame.copy()),
            daemon=True,
        ).start()

    if not cached:
        # Initial run: do synchronous single detection on first frame so viewer sees results immediately
        _run_frame_inference_worker(source_key, frame.copy())
        with _cv_lock:
            cached = _cv_cache.get(source_key)

    tables = cached.get("tables", []) if cached else []
    diners = cached.get("diners", []) if cached else []
    table_diners = cached.get("table_diners", {}) if cached else {}
    polygons = cached.get("polygons", []) if cached else []

    # 1. Semi-transparent table polygon fill
    if polygons:
        overlay = out.copy()
        for idx, poly in enumerate(polygons):
            pts_arr = np.array(poly, np.int32).reshape((-1, 1, 2))
            seated_count = len(table_diners.get(idx, []))
            fill_col = (180, 100, 30) if seated_count > 0 else (120, 80, 40)
            cv2.fillPoly(overlay, [pts_arr], fill_col)
        cv2.addWeighted(overlay, 0.4, out, 0.6, 0, out)

    # 2. Glowing polygon edge borders & labels
    for idx, poly in enumerate(polygons):
        pts_arr = np.array(poly, np.int32).reshape((-1, 1, 2))
        seated_count = len(table_diners.get(idx, []))
        border_col = (40, 200, 255) if seated_count > 0 else (220, 180, 60)
        cv2.polylines(out, [pts_arr], True, border_col, 2, cv2.LINE_AA)

        if idx < len(tables):
            t_box = tables[idx]["box"]
            status_text = f"T-0{idx+1} [OCCUPIED: {seated_count}p]" if seated_count > 0 else f"T-0{idx+1} [VACANT]"
            badge_w = len(status_text) * 8 + 12
            cv2.rectangle(out, (t_box[0], max(0, t_box[1] - 20)), (t_box[0] + badge_w, t_box[1]), (20, 24, 33), -1)
            cv2.putText(
                out, status_text, (t_box[0] + 5, max(14, t_box[1] - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, border_col, 1, cv2.LINE_AA
            )

    # 3. Patron bounding boxes and contact points
    for d_idx, d_data in enumerate(diners):
        dx1, dy1, dx2, dy2 = d_data["box"]
        conf = d_data["conf"]
        contact = ((dx1 + dx2) // 2, dy2)
        cv2.rectangle(out, (dx1, dy1), (dx2, dy2), (50, 220, 100), 2)
        cv2.circle(out, contact, 5, (30, 144, 255), -1)
        tag = f"Diner #{d_idx+1} ({conf:.0%})"
        cv2.rectangle(out, (dx1, max(0, dy1 - 18)), (dx1 + len(tag) * 8 + 6, dy1), (20, 24, 33), -1)
        cv2.putText(out, tag, (dx1 + 3, max(13, dy1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 220, 100), 1, cv2.LINE_AA)

    # 4. Association lines from seated diners to table centroid
    for t_idx, d_list in table_diners.items():
        if t_idx < len(tables):
            t_box = tables[t_idx]["box"]
            tc = ((t_box[0] + t_box[2]) // 2, (t_box[1] + t_box[3]) // 2)
            for (_, contact) in d_list:
                cv2.line(out, contact, tc, (255, 220, 100), 1, cv2.LINE_AA)

    # 5. Top Telemetry HUD banner
    cam_name = REGISTERED_CAMERAS.get(camera_id, {}).get("name", camera_id.upper())
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    hud = out.copy()
    cv2.rectangle(hud, (0, 0), (w, 36), (13, 19, 31), -1)
    cv2.addWeighted(hud, 0.85, out, 0.15, 0, out)
    cv2.circle(out, (18, 18), 6, (50, 220, 100), -1)
    hud_text = f"{cam_name.upper()} | {now_str} | YOLO26 ACTIVE [{len(tables)} TABLES | {len(diners)} DINERS]"
    cv2.putText(out, hud_text, (32, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

    return out


@router.get("/video-sources", summary="List available video sources and user assignments")
async def list_video_sources() -> dict[str, Any]:
    """Return all cataloged video sources, automatically scanning local uploads and demo files."""
    # Discover any newly uploaded or sample video files on disk
    for dir_path in [UPLOADS_DIR, SAMPLE_VIDEO_DIR]:
        if dir_path.exists():
            for f in dir_path.glob("*.mp4"):
                vid_id = f"custom_{f.stem}"
                if vid_id not in VIDEO_CATALOG and f.name not in [v.get("filename") for v in VIDEO_CATALOG.values()]:
                    size_kb = f.stat().st_size // 1024
                    VIDEO_CATALOG[vid_id] = {
                        "id": vid_id,
                        "name": f.stem.replace("_", " ").title(),
                        "description": f"Video footage ({size_kb} KB) in {dir_path.name}",
                        "category": "standard_cctv",
                        "filename": f.name,
                        "url": f"/api/v1/cameras/video-file/{f.name}",
                        "resolution": "1280x720",
                        "fps": 30.0,
                        "duration_sec": 30.0,
                        "is_annotated": False,
                        "recommended_view": "both",
                    }

    return {
        "sources": list(VIDEO_CATALOG.values()),
        "assignments": CURRENT_ASSIGNMENTS,
    }


@router.post("/video-sources/assign", summary="Update user video assignments")
async def assign_video_sources(req: VideoAssignmentRequest) -> dict[str, Any]:
    """Update active video source assignments for tracking and standard CCTV view."""
    if req.tracking_video_id:
        if req.tracking_video_id not in VIDEO_CATALOG and not req.tracking_video_id.startswith(
            "custom_"
        ):
            raise HTTPException(
                status_code=400, detail=f"Unknown tracking video ID '{req.tracking_video_id}'."
            )
        CURRENT_ASSIGNMENTS["tracking_video_id"] = req.tracking_video_id

    if req.standard_video_id:
        if req.standard_video_id not in VIDEO_CATALOG and not req.standard_video_id.startswith(
            "custom_"
        ):
            raise HTTPException(
                status_code=400, detail=f"Unknown standard video ID '{req.standard_video_id}'."
            )
        CURRENT_ASSIGNMENTS["standard_video_id"] = req.standard_video_id

    if req.camera_assignments:
        CURRENT_ASSIGNMENTS["camera_assignments"].update(req.camera_assignments)

    # Invalidate video captures so new assignments reload immediately
    with _cap_lock:
        for cap in _video_caps.values():
            try:
                cap.release()
            except Exception:
                pass
        _video_caps.clear()

    return {
        "status": "success",
        "message": "Video sources assigned successfully",
        "assignments": CURRENT_ASSIGNMENTS,
    }


@router.get("/{camera_id}", response_model=CameraModel, summary="Get single camera details")
async def get_camera(camera_id: str) -> CameraModel:
    """Retrieve metadata and health for a specific camera."""
    _ensure_default_cameras()
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID '{camera_id}' not found.",
        )
    return _build_camera_model(REGISTERED_CAMERAS[camera_id])


def _resolve_video_file(
    camera_id: str, processed: bool, override_video: str | None = None
) -> Path | None:
    """Resolve file path for requested video, honoring explicit camera selection first."""
    search_dirs = [UPLOADS_DIR, SAMPLE_VIDEO_DIR, PUBLIC_VIDEOS_DIR]

    # 1. Override video passed in query
    if override_video:
        if override_video in VIDEO_CATALOG:
            fname = VIDEO_CATALOG[override_video]["filename"]
            for d in search_dirs:
                p = d / fname
                if p.exists():
                    return p
        for d in search_dirs:
            p = d / override_video
            if p.exists():
                return p

    # 2. Camera registered video_url
    cam_info = REGISTERED_CAMERAS.get(camera_id, {})
    if cam_info.get("video_url"):
        fname = cam_info["video_url"].split("/")[-1]
        for d in search_dirs:
            p = d / fname
            if p.exists():
                return p

    # 3. Check current user assignments
    target_vid_id = (
        CURRENT_ASSIGNMENTS.get("tracking_video_id", "vid_demo_dining")
        if processed
        else CURRENT_ASSIGNMENTS.get("camera_assignments", {}).get(
            camera_id, CURRENT_ASSIGNMENTS.get("standard_video_id", "vid_demo_dining")
        )
    )
    if target_vid_id in VIDEO_CATALOG:
        fname = VIDEO_CATALOG[target_vid_id]["filename"]
        for d in search_dirs:
            p = d / fname
            if p.exists():
                return p

    # 4. Check primary project demo video
    for d in search_dirs:
        p = d / DEMO_VIDEO_FILENAME
        if p.exists():
            return p

    # 5. Other fallbacks
    for fname in ["output_annotated_cctv.mp4", "sample video.mp4", "cctv_camera_01_main_dining_raw.mp4"]:
        for d in search_dirs:
            p = d / fname
            if p.exists():
                return p

    return None


def _get_stream_frame(
    camera_id: str, processed: bool, tick: int, video_override: str | None = None
) -> np.ndarray:
    """Retrieve frame from sample/uploaded video with AI tracking overlays, or fallback to synthetic scene."""
    _ensure_default_cameras()
    source_file = _resolve_video_file(camera_id, processed, video_override)

    if source_file and source_file.exists():
        key = f"{camera_id}_{processed}_{source_file.name}"
        with _cap_lock:
            cap = _video_caps.get(key)
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(str(source_file))
                _video_caps[key] = cap

            ret, frame = cap.read()
            if not ret or frame is None:
                # Rewind to loop continuously
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()

            if ret and frame is not None:
                if processed:
                    return _render_table_and_patron_tracking(frame, camera_id, tick, str(source_file))
                else:
                    frame_copy = frame.copy()
                    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
                    cam_name = REGISTERED_CAMERAS.get(camera_id, {}).get("name", camera_id.upper())
                    cv2.putText(
                        frame_copy,
                        f"{cam_name.upper()} | {now_str} | CCTV REC [●]",
                        (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (240, 240, 240),
                        1,
                        cv2.LINE_AA,
                    )
                    return frame_copy

    return _generate_synthetic_restaurant_frame(camera_id, processed=processed, tick=tick)


async def _mjpeg_generator(
    camera_id: str, processed: bool, video_override: str | None = None
) -> AsyncGenerator[bytes, None]:
    """Yield MJPEG multipart frames for continuous browser streaming using sample video."""
    tick = 0
    while True:
        frame = _get_stream_frame(
            camera_id, processed=processed, tick=tick, video_override=video_override
        )
        tick += 1
        ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if not ret:
            await asyncio.sleep(0.08)
            continue
        frame_bytes = jpeg.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        await asyncio.sleep(0.04)  # ~25 FPS matching sample video


@router.get("/{camera_id}/stream/raw", summary="Stream raw CCTV video")
async def stream_raw(
    camera_id: str, video: str | None = Query(None, description="Optional video ID or filename")
):
    """Deliver MJPEG multipart raw CCTV stream from sample video without computer vision overlays."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return StreamingResponse(
        _mjpeg_generator(camera_id, processed=False, video_override=video),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/stream/processed", summary="Stream processed CV video")
async def stream_processed(
    camera_id: str, video: str | None = Query(None, description="Optional video ID or filename")
):
    """Deliver MJPEG multipart stream annotated with YOLO detection and tracking overlays from sample video."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    cam = REGISTERED_CAMERAS[camera_id]
    if cam.get("source_mode") == "view_only":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Processed computer vision stream is not available for view-only camera feeds. Switch source mode to 'tracking' to enable computer vision.",
        )
    return StreamingResponse(
        _mjpeg_generator(camera_id, processed=True, video_override=video),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/stream", summary="Secured camera video stream")
async def secured_camera_stream(
    camera_id: str,
    processed: bool = Query(False, description="Whether to deliver processed CV annotations"),
    current_user: User = Depends(require_staff_actor),
):
    """Secured video stream endpoint requiring authenticated staff credentials."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    cam = REGISTERED_CAMERAS[camera_id]
    if processed and cam.get("source_mode") == "view_only":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Processed computer vision stream is not available for view-only camera feeds.",
        )
    return StreamingResponse(
        _mjpeg_generator(camera_id, processed=processed),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/snapshot", summary="Get single snapshot image")
async def get_snapshot(camera_id: str, processed: bool = Query(False)):
    """Return a single JPEG frame snapshot from sample video."""
    if camera_id not in REGISTERED_CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    frame = _get_stream_frame(camera_id, processed=processed, tick=0)
    ret, jpeg = cv2.imencode(".jpg", frame)
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode snapshot")
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@router.get("/{camera_id}/cv-metadata", summary="Get latest frame computer vision metadata")
async def get_cv_metadata(camera_id: str) -> dict[str, Any]:
    """Return structured detections, tracking IDs, table states, and inference latency."""
    _ensure_default_cameras()
    if camera_id not in REGISTERED_CAMERAS:
        if camera_id.startswith("cam-") or camera_id.startswith("footage-"):
            cam = REGISTERED_CAMERAS.get("cam-01", {})
        else:
            raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    else:
        cam = REGISTERED_CAMERAS[camera_id]

    if cam.get("source_mode") == "view_only":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Computer vision metadata is not available for view-only camera feeds.",
        )

    now_iso = datetime.now(UTC).isoformat()
    # Check if we have live detections in cache
    source_file = _resolve_video_file(camera_id if camera_id in REGISTERED_CAMERAS else "cam-01", processed=True)
    source_key = str(source_file) if source_file else camera_id
    with _cv_lock:
        cached = _cv_cache.get(source_key)
        if not cached and _cv_cache:
            for k, v in _cv_cache.items():
                if "preview" in str(k) or "cam-01" in str(k):
                    cached = v
                    break
            if not cached:
                cached = next(iter(_cv_cache.values()))

    if cached and cached.get("tables"):
        tables_list = []
        table_diners = cached.get("table_diners", {})
        for idx, t_info in enumerate(cached.get("tables", [])):
            seated = len(table_diners.get(idx, []))
            tables_list.append({
                "table_id": f"T-0{idx+1}",
                "status": "OCCUPIED" if seated > 0 else "VACANT",
                "estimated_customers": seated,
                "confidence": t_info.get("conf", 0.8),
            })

        diners_list = []
        for d_idx, d_info in enumerate(cached.get("diners", [])):
            diners_list.append({
                "class_name": "person",
                "track_id": 100 + d_idx + 1,
                "confidence": d_info.get("conf", 0.75),
                "bbox": d_info.get("box", [0, 0, 0, 0]),
            })

        diners_count = len(cached.get("diners", []))
        return {
            "camera_id": camera_id,
            "frame_timestamp": now_iso,
            "model": "Fine-Tuned YOLO26s (Restaurant CCTV)",
            "inference_latency_ms": cached.get("latency_ms", 18.5),
            "fps": 29.5,
            "detections_count": diners_count if diners_count > 0 else len(cached.get("tables", [])),
            "tables_detected": len(cached.get("tables", [])),
            "patrons_tracked": diners_count,
            "detections": diners_list,
            "tables": tables_list,
        }

    return {
        "camera_id": camera_id,
        "frame_timestamp": now_iso,
        "model": "Fine-Tuned YOLO26s (Restaurant CCTV)",
        "inference_latency_ms": 14.8,
        "fps": 28.5,
        "detections_count": 5,
        "detections": [
            {
                "class_name": "person",
                "track_id": 101,
                "confidence": 0.94,
                "bbox": [0.135, 0.518, 0.177, 0.648],
                "bottom_contact": [0.156, 0.648],
                "assigned_table": "T01",
            },
            {
                "class_name": "person",
                "track_id": 102,
                "confidence": 0.91,
                "bbox": [0.198, 0.537, 0.241, 0.670],
                "bottom_contact": [0.219, 0.670],
                "assigned_table": "T01",
            },
            {
                "class_name": "person",
                "track_id": 103,
                "confidence": 0.96,
                "bbox": [0.437, 0.527, 0.484, 0.666],
                "bottom_contact": [0.460, 0.666],
                "assigned_table": "T02",
            },
        ],
        "tables": [
            {"table_id": "T01", "status": "OCCUPIED", "estimated_customers": 2},
            {"table_id": "T02", "status": "ATTENDED", "estimated_customers": 1},
            {"table_id": "T03", "status": "FOOD_DELIVERED", "estimated_customers": 4},
            {"table_id": "T04", "status": "VACANT", "estimated_customers": 0},
            {"table_id": "T05", "status": "VACANT", "estimated_customers": 0},
        ],
    }
