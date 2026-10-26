"""REST API endpoints for service timers, thresholds, and rules engine."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import ensure_utc, utc_now
from smartserve.database.models import AuditLog, TableSession
from smartserve.database.session import get_db
from smartserve.rules.engine import RulesEngine
from smartserve.rules.thresholds import ServiceThresholds, threshold_manager
from smartserve.rules.timers import SessionMetrics, SessionTimersCalculator
from smartserve.security.auth import resolve_actor

router = APIRouter(prefix="/api/v1", tags=["Service Timers & Rules"])


# ---------------------------------------------------------------------------
# Service Timers Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}/timers",
    response_model=SessionMetrics,
    summary="Get calculated service timers and milestones for a dining session",
)
async def get_session_timers(
    session_id: str,
    reference_time: datetime | None = Query(
        None, description="Optional evaluation timestamp in UTC (defaults to current server time)"
    ),
    db: AsyncSession = Depends(get_db),
) -> SessionMetrics:
    """Retrieve precise service milestone durations, elapsed timers, and validity flags.

    Conforms to RULES.md:
    - Missing milestones return null duration (pending).
    - Inconsistent or negative intervals are flagged with reason and never clamped to zero.
    """
    stmt = select(TableSession).where(TableSession.session_id == session_id)
    res = await db.execute(stmt)
    dining_session = res.scalar_one_or_none()
    if not dining_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TableSession with ID {session_id} not found",
        )

    ref_utc = ensure_utc(reference_time) if reference_time else utc_now()

    metrics = SessionTimersCalculator.calculate_metrics(
        session_id=dining_session.session_id,
        table_id=dining_session.table_id,
        started_at=dining_session.started_at,
        ended_at=dining_session.ended_at,
        first_attendance_at=dining_session.first_attendance_at,
        first_food_delivery_at=dining_session.first_food_delivery_at,
        reference_time=ref_utc,
    )
    return metrics


# ---------------------------------------------------------------------------
# Rules Engine Evaluation
# ---------------------------------------------------------------------------


@router.post(
    "/rules/evaluate",
    response_model=dict[str, Any],
    summary="Evaluate active dining sessions against service thresholds",
)
async def evaluate_rules(
    session_id: str | None = Query(
        None, description="Optional session ID to evaluate only a single session"
    ),
    reference_time: datetime | None = Query(
        None, description="Optional evaluation reference timestamp in UTC"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run rules engine evaluation.

    Checks active sessions against warning and critical thresholds:
    - Deduplicates active alerts (at most one per condition).
    - Escalates existing WARNING alerts to CRITICAL in-place when critical threshold is crossed.
    - Automatically resolves alerts when qualifying milestone events are confirmed.
    - Flags negative or anomalous intervals for managerial review.
    """
    ref_utc = ensure_utc(reference_time) if reference_time else utc_now()

    if session_id:
        stmt = select(TableSession).where(TableSession.session_id == session_id)
        res = await db.execute(stmt)
        dining_session = res.scalar_one_or_none()
        if not dining_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TableSession with ID {session_id} not found",
            )
        eval_result = await RulesEngine.evaluate_session(
            session_obj=dining_session,
            db=db,
            reference_time=ref_utc,
        )
        return {
            "evaluation_time": ref_utc.isoformat(),
            "evaluated_single_session": session_id,
            "result": eval_result,
        }

    summary = await RulesEngine.evaluate_active_sessions(
        db=db,
        reference_time=ref_utc,
    )
    return summary


@router.post(
    "/sessions/{session_id}/recalculate",
    response_model=dict[str, Any],
    summary="Recalculate session milestones and re-evaluate alerts",
)
async def recalculate_session_milestones(
    session_id: str,
    reference_time: datetime | None = Query(None, description="Evaluation reference time"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Safely recalculate session milestone timestamps from eligible operational events."""
    try:
        ref_utc = ensure_utc(reference_time) if reference_time else utc_now()
        result = await RulesEngine.recalculate_session(
            session_id=session_id, db=db, reference_time=ref_utc
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Thresholds Configuration Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/rules/thresholds",
    response_model=ServiceThresholds,
    summary="Get current operational service thresholds",
)
async def get_thresholds() -> ServiceThresholds:
    """Retrieve active warning and critical thresholds for service alerts."""
    return threshold_manager.get_thresholds()


@router.put(
    "/rules/thresholds",
    response_model=ServiceThresholds,
    summary="Update operational service thresholds",
)
async def update_thresholds(
    thresholds_in: ServiceThresholds,
    user_id: str | None = Query(None, description="Manager user ID modifying thresholds"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> ServiceThresholds:
    """Update active service thresholds with validation and audit log recording.

    Restricted to Manager and Administrator roles when actor identification is provided.
    """
    actor_id = x_user_id or user_id
    if actor_id:
        actor = await resolve_actor(db, actor_id)
        if str(actor.role).upper() not in ("MANAGER", "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{actor.username}' with role '{actor.role}' is not authorized to update thresholds. Manager or Admin required.",
            )
        user_id = actor.user_id

    try:
        old_thresholds = threshold_manager.get_thresholds().model_dump()
        updated = threshold_manager.update_thresholds(thresholds_in)

        # Audit log entry for threshold change (RULES.md Section 13)
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE_SERVICE_THRESHOLDS",
            entity_type="service_thresholds",
            entity_id="global",
            timestamp=utc_now(),
            details={
                "old_thresholds": old_thresholds,
                "new_thresholds": updated.model_dump(),
            },
        )
        db.add(audit)
        await db.commit()

        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
