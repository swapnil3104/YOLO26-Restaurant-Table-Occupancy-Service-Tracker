"""REST API endpoints for operational events, corrections, alerts, and audit logs."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.session import get_db
from smartserve.events.schema import (
    AlertCreate,
    AlertRead,
    AttendanceConfirmationRequest,
    AuditLogRead,
    EventCorrectionRequest,
    EventRejectionRequest,
    FoodDeliveryConfirmationRequest,
    ServiceEventCreate,
    ServiceEventRead,
    SessionTimelineRead,
)
from smartserve.events.service import EventDomainService
from smartserve.security.auth import (
    resolve_actor,
)

router = APIRouter(prefix="/api/v1", tags=["Events & Alerts"])


# ---------------------------------------------------------------------------
# Operational Events
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Record an operational service event",
)
async def create_event(
    event_in: ServiceEventCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ingest a new service event.

    Supports idempotent deduplication via `idempotency_key`. If an event with the same
    key was previously recorded, returns the existing record without creating duplicates.
    """
    event, is_duplicate = await EventDomainService.record_event(db, event_in)
    event_read = ServiceEventRead.model_validate(event)
    return {
        "status": "deduplicated" if is_duplicate else "recorded",
        "is_duplicate": is_duplicate,
        "event": event_read.model_dump(),
    }


@router.post(
    "/events/attendance",
    response_model=dict[str, Any],
    summary="Confirm waiter attendance for a table session",
)
async def confirm_attendance(
    payload: AttendanceConfirmationRequest | None = None,
    table_id: str | None = Query(None, description="Target table ID"),
    session_id: str | None = Query(None, description="Active session ID"),
    waiter_id: str | None = Query(None, description="Waiter / Staff user ID"),
    idempotency_key: str | None = Query(None, description="Idempotency key"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record an authorized waiter attendance confirmation for an active table session.

    Enforces active table session association and staff actor role. Idempotent on retries.
    """
    actor_id = (
        x_user_id
        or waiter_id
        or (
            payload.metadata.get("waiter_id") or payload.metadata.get("user_id")
            if payload and payload.metadata
            else None
        )
    )
    actor = await resolve_actor(db, actor_id)
    if str(actor.role).upper() not in ("WAITER", "MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role '{actor.role}' is not authorized to confirm attendance.",
        )

    if payload:
        req = payload
    elif table_id:
        req = AttendanceConfirmationRequest(
            table_id=table_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'table_id' in body or query parameters.",
        )

    try:
        event, is_duplicate = await EventDomainService.confirm_attendance(db, req, actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {
        "status": "deduplicated" if is_duplicate else "confirmed",
        "is_duplicate": is_duplicate,
        "event": ServiceEventRead.model_validate(event).model_dump(),
    }


@router.post(
    "/events/food-delivery",
    response_model=dict[str, Any],
    summary="Confirm food delivery for a table session",
)
async def confirm_food_delivery(
    payload: FoodDeliveryConfirmationRequest | None = None,
    table_id: str | None = Query(None, description="Target table ID"),
    session_id: str | None = Query(None, description="Active session ID"),
    waiter_id: str | None = Query(None, description="Waiter / Staff user ID"),
    course: str | None = Query(None, description="Course name"),
    batch_number: int = Query(1, ge=1, description="Batch number"),
    idempotency_key: str | None = Query(None, description="Idempotency key"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record an authorized food delivery confirmation for an active table session.

    Supports multiple delivery batches while maintaining earliest first-delivery milestone.
    """
    actor_id = (
        x_user_id
        or waiter_id
        or (
            payload.metadata.get("waiter_id") or payload.metadata.get("user_id")
            if payload and payload.metadata
            else None
        )
    )
    actor = await resolve_actor(db, actor_id)
    if str(actor.role).upper() not in ("WAITER", "MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role '{actor.role}' is not authorized to confirm delivery.",
        )

    if payload:
        req = payload
    elif table_id:
        req = FoodDeliveryConfirmationRequest(
            table_id=table_id,
            session_id=session_id,
            course=course,
            batch_number=batch_number,
            idempotency_key=idempotency_key,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'table_id' in body or query parameters.",
        )

    try:
        event, is_duplicate = await EventDomainService.confirm_food_delivery(db, req, actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {
        "status": "deduplicated" if is_duplicate else "confirmed",
        "is_duplicate": is_duplicate,
        "event": ServiceEventRead.model_validate(event).model_dump(),
    }


@router.post(
    "/events/{event_id}/reject",
    response_model=dict[str, Any],
    summary="Reject an incorrect or mistaken event with audit logging",
)
async def reject_event(
    event_id: str,
    rejection: EventRejectionRequest,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reject a mistaken event (restricted to Manager/Admin).

    Marks event REJECTED, writes audit entry, and recalculates session metrics and alerts.
    """
    actor_id = x_user_id or rejection.rejected_by
    actor = await resolve_actor(db, actor_id)
    if str(actor.role).upper() not in ("MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{actor.username}' with role '{actor.role}' is not authorized to reject events. Manager or Admin required.",
        )

    try:
        event, audit = await EventDomainService.reject_event(
            db, event_id, rejection.reason, rejected_by=actor.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "status": "rejected",
        "event": ServiceEventRead.model_validate(event).model_dump(),
        "audit_log": AuditLogRead.model_validate(audit).model_dump(),
    }


@router.post(
    "/events/{event_id}/correct",
    response_model=dict[str, Any],
    summary="Correct an event while preserving audit history",
)
async def correct_event(
    event_id: str,
    correction: EventCorrectionRequest,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Correct a recorded event.

    Preserves original record, marks it CORRECTED, creates a new superseding event,
    updates parent session metrics if applicable, and writes an immutable audit entry.
    """
    actor_id = x_user_id or correction.corrected_by
    actor = await resolve_actor(db, actor_id)
    if str(actor.role).upper() not in ("WAITER", "MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role '{actor.role}' is not authorized to correct events.",
        )
    correction.corrected_by = actor.user_id

    try:
        original, superseding = await EventDomainService.correct_event(db, event_id, correction)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "status": "corrected",
        "original_event": ServiceEventRead.model_validate(original).model_dump(),
        "superseding_event": ServiceEventRead.model_validate(superseding).model_dump(),
    }


@router.get(
    "/sessions/{session_id}/timeline",
    response_model=SessionTimelineRead,
    summary="Retrieve session event timeline with presentation badges",
)
async def get_session_timeline(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionTimelineRead:
    """Retrieve ordered chronological event timeline for a session with UI presentation badges."""
    try:
        return await EventDomainService.get_session_timeline(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/events",
    response_model=list[ServiceEventRead],
    summary="Query service events",
)
async def get_events(
    table_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    start_time: datetime | None = Query(None, description="Filter events after UTC timestamp"),
    end_time: datetime | None = Query(None, description="Filter events before UTC timestamp"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ServiceEventRead]:
    """Retrieve operational service events ordered chronologically descending with optional date filters."""
    events = await EventDomainService.list_events(
        db,
        table_id=table_id,
        session_id=session_id,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [ServiceEventRead.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Operational Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=list[AlertRead],
    summary="List operational alerts",
)
async def get_alerts(
    table_id: str | None = None,
    status: str | None = None,
    start_time: datetime | None = Query(None, description="Filter alerts after UTC timestamp"),
    end_time: datetime | None = Query(None, description="Filter alerts before UTC timestamp"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AlertRead]:
    """List service alerts with optional status, table, date, and pagination filtering."""
    alerts = await EventDomainService.list_alerts(
        db,
        table_id=table_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [AlertRead.model_validate(a) for a in alerts]


@router.post(
    "/alerts",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create or deduplicate an operational alert",
)
async def create_alert(
    alert_in: AlertCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new alert with automatic deduplication across active alerts."""
    alert, is_duplicate = await EventDomainService.create_or_update_alert(db, alert_in)
    return {
        "status": "deduplicated" if is_duplicate else "created",
        "is_duplicate": is_duplicate,
        "alert": AlertRead.model_validate(alert).model_dump(),
    }


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Acknowledge an alert",
)
async def acknowledge_alert(
    alert_id: str,
    user_id: str | None = Query(None, description="Acknowledging user ID"),
    db: AsyncSession = Depends(get_db),
) -> AlertRead:
    """Transition alert to ACKNOWLEDGED state and log audit entry."""
    try:
        alert = await EventDomainService.acknowledge_alert(db, alert_id, user_id)
        return AlertRead.model_validate(alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an alert",
)
async def resolve_alert(
    alert_id: str,
    user_id: str | None = Query(None, description="Resolving user ID"),
    db: AsyncSession = Depends(get_db),
) -> AlertRead:
    """Transition alert to RESOLVED state and log audit entry."""
    try:
        alert = await EventDomainService.resolve_alert(db, alert_id, user_id)
        return AlertRead.model_validate(alert)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------


@router.get(
    "/audit",
    response_model=list[AuditLogRead],
    summary="Query audit log entries",
)
async def get_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    start_time: datetime | None = Query(None, description="Filter audit logs after UTC timestamp"),
    end_time: datetime | None = Query(None, description="Filter audit logs before UTC timestamp"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    """Query immutable audit log entries with date and pagination filters."""
    logs = await EventDomainService.list_audit_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [AuditLogRead.model_validate(log) for log in logs]
