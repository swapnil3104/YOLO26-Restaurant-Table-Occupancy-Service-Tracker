"""Tracking worker lifecycle and inference job state manager.

Adheres strictly to Docs/TASKS.md Phase 7:
- Make start/stop operations idempotent and avoid duplicate workers after retries or page refreshes.
- Separate view_only and tracking source modes with backend authorization and strict enforcement.
- Persist source/floor associations, job status, model version, events, and timestamps with consistent time zones.
- Refreshing the UI restores source and floor configuration; worker state matches backend truth.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import generate_uuid, utc_now
from smartserve.database.models import Camera, DetectionEvent, TrackingJob

logger = logging.getLogger(__name__)


class TrackingWorkerException(Exception):
    """Raised when worker operations fail validation or execution gates."""

    pass


class ViewOnlyViolationException(TrackingWorkerException):
    """Raised when an inference or tracking operation is attempted on a view-only source."""

    pass


class ActiveWorkerInfo:
    """In-memory telemetry and control handle for a running camera tracking worker."""

    def __init__(
        self,
        job_id: str,
        camera_id: str,
        model_version: str,
        started_at: datetime,
    ) -> None:
        self.job_id = job_id
        self.camera_id = camera_id
        self.model_version = model_version
        self.started_at = started_at
        self.effective_fps = 30.0
        self.last_event_time = started_at
        self.is_active = True
        self.frame_count = 0


class TrackingWorkerManager:
    """Coordinates camera tracking inference jobs, ensuring idempotency and DB persistence."""

    _instance: TrackingWorkerManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> TrackingWorkerManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._workers: dict[str, ActiveWorkerInfo] = {}
                cls._instance._camera_to_job: dict[str, str] = {}
            return cls._instance

    @property
    def active_workers(self) -> dict[str, ActiveWorkerInfo]:
        return self._workers

    async def start_tracking_job(
        self,
        camera_id: str,
        db: AsyncSession,
        model_version: str = "models/yolo26_restaurant_cctv.pt",
        config_override: dict[str, Any] | None = None,
    ) -> TrackingJob:
        """Start or resume a tracking job for a camera source.

        Idempotency:
        - If an active job already exists for this camera, returns the existing job without
          spawning duplicate workers.
        - Strictly rejects view_only camera feeds with ViewOnlyViolationException.
        """
        # 1. Fetch camera record
        stmt = select(Camera).where(Camera.camera_id == camera_id)
        res = await db.execute(stmt)
        cam = res.scalar_one_or_none()

        if not cam:
            raise TrackingWorkerException(f"Camera source '{camera_id}' not found.")

        # 2. Strict enforcement: view_only sources must NEVER run tracking or inference
        if cam.source_mode == "view_only":
            raise ViewOnlyViolationException(
                f"Camera '{camera_id}' is configured in 'view_only' mode. "
                "Tracking and inference jobs are strictly prohibited on view-only sources."
            )

        # 3. Check for existing active job (idempotent guard)
        stmt_active = (
            select(TrackingJob)
            .where(
                TrackingJob.camera_id == camera_id,
                TrackingJob.status.in_(["MONITORING", "INITIALIZING"]),
            )
            .order_by(TrackingJob.created_at.desc())
        )
        res_active = await db.execute(stmt_active)
        existing_job = res_active.scalars().first()

        now = utc_now()

        if existing_job:
            # Active job already exists — idempotent return without duplicate worker
            if camera_id not in self._camera_to_job:
                self._workers[existing_job.job_id] = ActiveWorkerInfo(
                    job_id=existing_job.job_id,
                    camera_id=camera_id,
                    model_version=existing_job.model_version,
                    started_at=existing_job.started_at or now,
                )
                self._camera_to_job[camera_id] = existing_job.job_id
            return existing_job

        # 4. Create new TrackingJob in DB
        job_id = f"job-{camera_id}-{generate_uuid()[:8]}"
        job = TrackingJob(
            job_id=job_id,
            camera_id=camera_id,
            status="MONITORING",
            model_version=model_version or cam.model_version or "models/yolo26_restaurant_cctv.pt",
            effective_fps=30.0,
            config_json=config_override or {"fps": 30.0, "imgsz": 640},
            created_at=now,
            started_at=now,
        )
        db.add(job)

        # 5. Update Camera state to reflect active monitoring
        cam.tracking_status = "Monitoring"
        cam.inference_status = "ACTIVE"
        cam.camera_health = "HEALTHY"
        cam.processing_job_id = job_id
        cam.effective_fps = 30.0
        cam.last_event_time = now

        await db.commit()
        await db.refresh(job)

        # 6. Register in in-memory worker registry
        worker_info = ActiveWorkerInfo(
            job_id=job_id,
            camera_id=camera_id,
            model_version=job.model_version,
            started_at=now,
        )
        self._workers[job_id] = worker_info
        self._camera_to_job[camera_id] = job_id

        logger.info(
            f"Started tracking job {job_id} for camera {camera_id} (model: {job.model_version})"
        )
        return job

    async def stop_tracking_job(
        self,
        job_id: str,
        db: AsyncSession,
    ) -> TrackingJob:
        """Stop a tracking job idempotently.

        If the job is already STOPPED, returns cleanly without error.
        Updates DB and clears in-memory worker registry.
        """
        stmt = select(TrackingJob).where(TrackingJob.job_id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise TrackingWorkerException(f"Tracking job '{job_id}' not found.")

        now = utc_now()

        # Idempotent check
        if job.status == "STOPPED":
            logger.info(f"Tracking job {job_id} is already stopped.")
            return job

        # Update job record
        job.status = "STOPPED"
        job.stopped_at = now

        # Update associated camera
        stmt_cam = select(Camera).where(Camera.camera_id == job.camera_id)
        res_cam = await db.execute(stmt_cam)
        cam = res_cam.scalar_one_or_none()
        if cam:
            cam.tracking_status = "Stopped"
            cam.inference_status = "IDLE"
            if cam.processing_job_id == job_id:
                cam.processing_job_id = None

        await db.commit()
        await db.refresh(job)

        # Clean up in-memory registry
        if job_id in self._workers:
            del self._workers[job_id]
        if job.camera_id in self._camera_to_job and self._camera_to_job[job.camera_id] == job_id:
            del self._camera_to_job[job.camera_id]

        logger.info(f"Stopped tracking job {job_id} for camera {job.camera_id}")
        return job

    async def stop_camera_jobs(
        self,
        camera_id: str,
        db: AsyncSession,
    ) -> list[str]:
        """Stop all active jobs associated with a camera (e.g. before removal)."""
        stmt = select(TrackingJob).where(
            TrackingJob.camera_id == camera_id,
            TrackingJob.status.in_(["MONITORING", "INITIALIZING"]),
        )
        res = await db.execute(stmt)
        active_jobs = res.scalars().all()

        stopped_ids = []
        for job in active_jobs:
            await self.stop_tracking_job(job.job_id, db)
            stopped_ids.append(job.job_id)

        return stopped_ids

    async def get_tracking_job(
        self,
        job_id: str,
        db: AsyncSession,
    ) -> TrackingJob:
        """Fetch tracking job details from DB."""
        stmt = select(TrackingJob).where(TrackingJob.job_id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise TrackingWorkerException(f"Tracking job '{job_id}' not found.")
        return job

    async def record_detection_event(
        self,
        camera_id: str,
        person_count: int,
        active_tracks: int,
        associations: dict[str, Any],
        detections: list[Any],
        latency_ms: float,
        db: AsyncSession,
        job_id: str | None = None,
    ) -> DetectionEvent:
        """Persist a timestamped computer vision detection event."""
        now = utc_now()
        event_id = f"det-{generate_uuid()}"
        resolved_job_id = job_id or self._camera_to_job.get(camera_id)

        det_event = DetectionEvent(
            detection_id=event_id,
            camera_id=camera_id,
            job_id=resolved_job_id,
            timestamp=now,
            person_count=person_count,
            active_tracks=active_tracks,
            associations_json=associations,
            detections_json=detections,
            latency_ms=latency_ms,
        )
        db.add(det_event)

        # Update worker in-memory telemetry if active
        if resolved_job_id and resolved_job_id in self._workers:
            worker = self._workers[resolved_job_id]
            worker.last_event_time = now
            worker.frame_count += 1

        # Update camera last event timestamp
        stmt_cam = select(Camera).where(Camera.camera_id == camera_id)
        res_cam = await db.execute(stmt_cam)
        cam = res_cam.scalar_one_or_none()
        if cam:
            cam.last_event_time = now

        await db.commit()
        return det_event


# Singleton instance
worker_manager = TrackingWorkerManager()
