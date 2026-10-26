"""REST API endpoints for tracking job lifecycle management.

Adheres strictly to Docs/TASKS.md Phase 7:
- Implement authenticated tracking-job endpoints:
  - POST /api/tracking-jobs
  - GET /api/tracking-jobs/:id
  - POST /api/tracking-jobs/:id/stop
- Make start/stop operations idempotent and avoid duplicate workers after retries or page refreshes.
- Separate view_only and tracking source modes with backend authorization and strict enforcement.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.models import TrackingJob, User
from smartserve.database.session import get_db
from smartserve.security.auth import require_staff_actor
from smartserve.vision.worker_manager import (
    TrackingWorkerException,
    ViewOnlyViolationException,
    worker_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tracking Jobs"])


class TrackingJobModel(BaseModel):
    """Schema representing an active or completed tracking job."""

    job_id: str
    camera_id: str
    status: str = Field(..., description="INITIALIZING, MONITORING, PAUSED, STOPPED, ERROR")
    model_version: str
    effective_fps: float = 30.0
    worker_pid: int | None = None
    error_message: str | None = None
    config_json: dict[str, Any] = {}
    created_at: str
    started_at: str | None = None
    stopped_at: str | None = None


class StartTrackingJobRequest(BaseModel):
    """Payload to start or attach to an inference tracking job."""

    camera_id: str = Field(..., description="Camera ID to process")
    model_version: str = Field(
        "models/yolo26_restaurant_cctv.pt", description="YOLO weights checkpoint"
    )
    config_json: dict[str, Any] = Field(
        default_factory=dict, description="Worker configuration override"
    )


@router.post(
    "/tracking-jobs",
    response_model=TrackingJobModel,
    status_code=status.HTTP_201_CREATED,
    summary="Start or attach to a camera tracking job",
)
async def start_tracking_job(
    payload: StartTrackingJobRequest,
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> TrackingJobModel:
    """Start an inference tracking worker for a camera source.

    Idempotent:
    - If an active job already exists for this camera, returns the existing job without creating duplicate workers.
    - Strictly rejects cameras configured in 'view_only' mode with HTTP 400 Bad Request.
    """
    try:
        job = await worker_manager.start_tracking_job(
            camera_id=payload.camera_id,
            db=db,
            model_version=payload.model_version,
            config_override=payload.config_json,
        )
    except ViewOnlyViolationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except TrackingWorkerException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return TrackingJobModel(
        job_id=job.job_id,
        camera_id=job.camera_id,
        status=job.status,
        model_version=job.model_version,
        effective_fps=job.effective_fps,
        worker_pid=job.worker_pid,
        error_message=job.error_message,
        config_json=job.config_json or {},
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        stopped_at=job.stopped_at.isoformat() if job.stopped_at else None,
    )


@router.get(
    "/tracking-jobs/{job_id}",
    response_model=TrackingJobModel,
    summary="Get tracking job status and telemetry",
)
async def get_tracking_job(
    job_id: str,
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> TrackingJobModel:
    """Retrieve current status, model version, and telemetry for a tracking job."""
    try:
        job = await worker_manager.get_tracking_job(job_id=job_id, db=db)
    except TrackingWorkerException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return TrackingJobModel(
        job_id=job.job_id,
        camera_id=job.camera_id,
        status=job.status,
        model_version=job.model_version,
        effective_fps=job.effective_fps,
        worker_pid=job.worker_pid,
        error_message=job.error_message,
        config_json=job.config_json or {},
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        stopped_at=job.stopped_at.isoformat() if job.stopped_at else None,
    )


@router.post(
    "/tracking-jobs/{job_id}/stop",
    response_model=TrackingJobModel,
    summary="Stop a tracking job idempotently",
)
async def stop_tracking_job(
    job_id: str,
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> TrackingJobModel:
    """Stop a tracking job.

    Idempotent: Stopping an already stopped job is safe and does not error.
    Updates worker status, stops inference, and releases monitoring resources.
    """
    try:
        job = await worker_manager.stop_tracking_job(job_id=job_id, db=db)
    except TrackingWorkerException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return TrackingJobModel(
        job_id=job.job_id,
        camera_id=job.camera_id,
        status=job.status,
        model_version=job.model_version,
        effective_fps=job.effective_fps,
        worker_pid=job.worker_pid,
        error_message=job.error_message,
        config_json=job.config_json or {},
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        stopped_at=job.stopped_at.isoformat() if job.stopped_at else None,
    )


@router.get(
    "/tracking-jobs",
    response_model=list[TrackingJobModel],
    summary="List tracking jobs",
)
async def list_tracking_jobs(
    camera_id: str | None = Query(None, description="Optional camera filter"),
    status_filter: str | None = Query(None, alias="status", description="Optional status filter"),
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> list[TrackingJobModel]:
    """List tracking jobs with optional camera or status filtering."""
    stmt = select(TrackingJob).order_by(TrackingJob.created_at.desc())
    if camera_id:
        stmt = stmt.where(TrackingJob.camera_id == camera_id)
    if status_filter:
        stmt = stmt.where(TrackingJob.status == status_filter)

    res = await db.execute(stmt)
    jobs = res.scalars().all()

    return [
        TrackingJobModel(
            job_id=j.job_id,
            camera_id=j.camera_id,
            status=j.status,
            model_version=j.model_version,
            effective_fps=j.effective_fps,
            worker_pid=j.worker_pid,
            error_message=j.error_message,
            config_json=j.config_json or {},
            created_at=j.created_at.isoformat(),
            started_at=j.started_at.isoformat() if j.started_at else None,
            stopped_at=j.stopped_at.isoformat() if j.stopped_at else None,
        )
        for j in jobs
    ]
