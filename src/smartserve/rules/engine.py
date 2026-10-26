"""Rules engine for dining session monitoring, alert deduplication, escalation, and resolution."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import ensure_utc, utc_now
from smartserve.database.models import Alert, ServiceEvent, TableSession
from smartserve.events.schema import (
    AlertSeverity,
    AlertStatus,
    EventType,
    SessionStatus,
    VerificationStatus,
)
from smartserve.rules.thresholds import ServiceThresholds, threshold_manager
from smartserve.rules.timers import SessionMetrics, SessionTimersCalculator


class RulesEngine:
    """Evaluates dining sessions against business rules, manages alert lifecycles."""

    @classmethod
    async def evaluate_session(
        cls,
        session_obj: TableSession,
        db: AsyncSession,
        thresholds: ServiceThresholds | None = None,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single table session against service thresholds.

        Returns:
            dict[str, Any] with evaluated metrics and alert actions taken.
        """
        thresholds = thresholds or threshold_manager.get_thresholds()
        ref_time = ensure_utc(reference_time or utc_now())

        # 1. Compute timing intervals
        metrics: SessionMetrics = SessionTimersCalculator.calculate_metrics(
            session_id=session_obj.session_id,
            table_id=session_obj.table_id,
            started_at=session_obj.started_at,
            ended_at=session_obj.ended_at,
            first_attendance_at=session_obj.first_attendance_at,
            first_food_delivery_at=session_obj.first_food_delivery_at,
            reference_time=ref_time,
        )

        actions: dict[str, list[str]] = {
            "created": [],
            "escalated": [],
            "resolved": [],
        }

        # 2. Check for negative intervals / anomalies (RULES.md Section 8.3 & 10.1)
        if metrics.has_inconsistencies:
            session_obj.session_status = SessionStatus.NEEDS_REVIEW.value
            inconsistency_key = f"{session_obj.session_id}:DATA_INCONSISTENCY"
            created, _ = await cls._create_or_dedup_alert(
                db=db,
                session_id=session_obj.session_id,
                table_id=session_obj.table_id,
                alert_type="DATA_INCONSISTENCY",
                severity=AlertSeverity.CRITICAL,
                dedup_key=inconsistency_key,
                metadata={
                    "inconsistencies": metrics.inconsistencies,
                    "first_response_sec": metrics.first_response.duration_sec,
                    "food_delivery_sec": metrics.food_delivery.duration_sec,
                },
            )
            if created:
                actions["created"].append("DATA_INCONSISTENCY")

        # 3. Handle Active Sessions
        if session_obj.session_status == SessionStatus.ACTIVE.value:
            # -------------------------------------------------------------
            # A. Attendance Threshold Check
            # -------------------------------------------------------------
            attendance_key = f"{session_obj.session_id}:FIRST_ATTENDANCE_OVERDUE"
            if session_obj.first_attendance_at is None:
                elapsed_attendance = metrics.elapsed_since_seating_sec
                if elapsed_attendance >= thresholds.first_attendance_critical_sec:
                    # Critical threshold crossed
                    status_change = await cls._trigger_or_escalate_alert(
                        db=db,
                        session_id=session_obj.session_id,
                        table_id=session_obj.table_id,
                        alert_type="FIRST_ATTENDANCE_OVERDUE",
                        target_severity=AlertSeverity.CRITICAL,
                        dedup_key=attendance_key,
                        metadata={
                            "elapsed_sec": round(elapsed_attendance, 1),
                            "threshold_sec": thresholds.first_attendance_critical_sec,
                            "rule": "first_attendance_critically_overdue",
                        },
                    )
                    if status_change == "created":
                        actions["created"].append("FIRST_ATTENDANCE_OVERDUE (CRITICAL)")
                    elif status_change == "escalated":
                        actions["escalated"].append("FIRST_ATTENDANCE_OVERDUE -> CRITICAL")

                elif elapsed_attendance >= thresholds.first_attendance_warning_sec:
                    # Warning threshold crossed
                    status_change = await cls._trigger_or_escalate_alert(
                        db=db,
                        session_id=session_obj.session_id,
                        table_id=session_obj.table_id,
                        alert_type="FIRST_ATTENDANCE_OVERDUE",
                        target_severity=AlertSeverity.WARNING,
                        dedup_key=attendance_key,
                        metadata={
                            "elapsed_sec": round(elapsed_attendance, 1),
                            "threshold_sec": thresholds.first_attendance_warning_sec,
                            "rule": "first_attendance_overdue",
                        },
                    )
                    if status_change == "created":
                        actions["created"].append("FIRST_ATTENDANCE_OVERDUE (WARNING)")
            else:
                # Attendance confirmed: auto-resolve any active attendance alert
                resolved = await cls._auto_resolve_alert(
                    db=db,
                    dedup_key=attendance_key,
                    resolved_at=session_obj.first_attendance_at,
                    reason="ATTENDANCE_CONFIRMED",
                )
                if resolved:
                    actions["resolved"].append("FIRST_ATTENDANCE_OVERDUE")

            # -------------------------------------------------------------
            # B. Food Delivery Threshold Check
            # -------------------------------------------------------------
            food_key = f"{session_obj.session_id}:FOOD_DELIVERY_OVERDUE"
            if session_obj.first_food_delivery_at is None:
                elapsed_food = metrics.elapsed_since_seating_sec
                if elapsed_food >= thresholds.food_delivery_critical_sec:
                    status_change = await cls._trigger_or_escalate_alert(
                        db=db,
                        session_id=session_obj.session_id,
                        table_id=session_obj.table_id,
                        alert_type="FOOD_DELIVERY_OVERDUE",
                        target_severity=AlertSeverity.CRITICAL,
                        dedup_key=food_key,
                        metadata={
                            "elapsed_sec": round(elapsed_food, 1),
                            "threshold_sec": thresholds.food_delivery_critical_sec,
                            "rule": "food_delivery_critically_overdue",
                        },
                    )
                    if status_change == "created":
                        actions["created"].append("FOOD_DELIVERY_OVERDUE (CRITICAL)")
                    elif status_change == "escalated":
                        actions["escalated"].append("FOOD_DELIVERY_OVERDUE -> CRITICAL")

                elif elapsed_food >= thresholds.food_delivery_warning_sec:
                    status_change = await cls._trigger_or_escalate_alert(
                        db=db,
                        session_id=session_obj.session_id,
                        table_id=session_obj.table_id,
                        alert_type="FOOD_DELIVERY_OVERDUE",
                        target_severity=AlertSeverity.WARNING,
                        dedup_key=food_key,
                        metadata={
                            "elapsed_sec": round(elapsed_food, 1),
                            "threshold_sec": thresholds.food_delivery_warning_sec,
                            "rule": "food_delivery_overdue",
                        },
                    )
                    if status_change == "created":
                        actions["created"].append("FOOD_DELIVERY_OVERDUE (WARNING)")
            else:
                # Food delivery confirmed: auto-resolve active delivery alert
                resolved = await cls._auto_resolve_alert(
                    db=db,
                    dedup_key=food_key,
                    resolved_at=session_obj.first_food_delivery_at,
                    reason="FOOD_DELIVERY_CONFIRMED",
                )
                if resolved:
                    actions["resolved"].append("FOOD_DELIVERY_OVERDUE")

            # -------------------------------------------------------------
            # C. Maximum Occupancy Threshold Check
            # -------------------------------------------------------------
            occ_key = f"{session_obj.session_id}:OCCUPANCY_OVERDUE"
            if metrics.elapsed_since_seating_sec >= thresholds.occupancy_warning_sec:
                status_change = await cls._trigger_or_escalate_alert(
                    db=db,
                    session_id=session_obj.session_id,
                    table_id=session_obj.table_id,
                    alert_type="OCCUPANCY_OVERDUE",
                    target_severity=AlertSeverity.WARNING,
                    dedup_key=occ_key,
                    metadata={
                        "elapsed_sec": round(metrics.elapsed_since_seating_sec, 1),
                        "threshold_sec": thresholds.occupancy_warning_sec,
                    },
                )
                if status_change == "created":
                    actions["created"].append("OCCUPANCY_OVERDUE")

        elif session_obj.session_status in (
            SessionStatus.COMPLETED.value,
            SessionStatus.CANCELLED.value,
        ):
            # Session finished: resolve any remaining active alerts for this session
            active_alerts_stmt = select(Alert).where(
                Alert.session_id == session_obj.session_id,
                Alert.status == AlertStatus.ACTIVE.value,
            )
            res = await db.execute(active_alerts_stmt)
            for alert in res.scalars().all():
                alert.status = AlertStatus.RESOLVED.value
                alert.resolved_at = session_obj.ended_at or ref_time
                alert.metadata_json = {
                    **alert.metadata_json,
                    "resolution_reason": f"SESSION_{session_obj.session_status}",
                }
                actions["resolved"].append(alert.alert_type)

        await db.commit()

        return {
            "session_id": session_obj.session_id,
            "metrics": metrics.model_dump(),
            "actions": actions,
        }

    @classmethod
    async def evaluate_active_sessions(
        cls,
        db: AsyncSession,
        thresholds: ServiceThresholds | None = None,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluate all active table sessions against service rules."""
        thresholds = thresholds or threshold_manager.get_thresholds()
        ref_time = ensure_utc(reference_time or utc_now())

        stmt = select(TableSession).where(TableSession.session_status == SessionStatus.ACTIVE.value)
        res = await db.execute(stmt)
        active_sessions = res.scalars().all()

        results = []
        total_created = 0
        total_escalated = 0
        total_resolved = 0

        for session in active_sessions:
            eval_res = await cls.evaluate_session(
                session_obj=session,
                db=db,
                thresholds=thresholds,
                reference_time=ref_time,
            )
            results.append(eval_res)
            total_created += len(eval_res["actions"]["created"])
            total_escalated += len(eval_res["actions"]["escalated"])
            total_resolved += len(eval_res["actions"]["resolved"])

        return {
            "evaluation_time": ref_time.isoformat(),
            "active_sessions_count": len(active_sessions),
            "alerts_created_count": total_created,
            "alerts_escalated_count": total_escalated,
            "alerts_resolved_count": total_resolved,
            "session_results": results,
        }

    @classmethod
    async def recalculate_session(
        cls,
        session_id: str,
        db: AsyncSession,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Safely recalculate session milestone timestamps from eligible operational events.

        Excludes CORRECTED and REJECTED events according to RULES.md Section 6.1 & 13.
        """
        ref_time = ensure_utc(reference_time or utc_now())

        sess_stmt = select(TableSession).where(TableSession.session_id == session_id)
        sess_res = await db.execute(sess_stmt)
        dining_session = sess_res.scalar_one_or_none()
        if not dining_session:
            raise ValueError(f"TableSession with ID {session_id} not found")

        # Query all eligible confirmed events for this session
        events_stmt = (
            select(ServiceEvent)
            .where(
                ServiceEvent.session_id == session_id,
                ServiceEvent.verification_status.in_(
                    [VerificationStatus.CONFIRMED.value, VerificationStatus.CANDIDATE.value]
                ),
            )
            .order_by(ServiceEvent.event_timestamp.asc())
        )
        events_res = await db.execute(events_stmt)
        events = events_res.scalars().all()

        # Find earliest eligible confirmed attendance
        earliest_attendance = None
        for ev in events:
            if ev.verification_status == VerificationStatus.CONFIRMED.value and ev.event_type in (
                EventType.FIRST_ATTENDANCE.value,
                EventType.ATTENDANCE.value,
            ):
                earliest_attendance = ev.event_timestamp
                break

        # Find earliest eligible confirmed food delivery
        earliest_food = None
        for ev in events:
            if (
                ev.verification_status == VerificationStatus.CONFIRMED.value
                and ev.event_type == EventType.FOOD_DELIVERY.value
            ):
                earliest_food = ev.event_timestamp
                break

        # Update milestones on TableSession
        dining_session.first_attendance_at = earliest_attendance
        dining_session.first_food_delivery_at = earliest_food

        # Re-evaluate session rules
        eval_result = await cls.evaluate_session(
            session_obj=dining_session,
            db=db,
            reference_time=ref_time,
        )
        return eval_result

    # -----------------------------------------------------------------------
    # Internal Alert Helpers (Deduplication, Escalation, Auto-Resolution)
    # -----------------------------------------------------------------------

    @staticmethod
    async def _trigger_or_escalate_alert(
        db: AsyncSession,
        session_id: str,
        table_id: str,
        alert_type: str,
        target_severity: AlertSeverity,
        dedup_key: str,
        metadata: dict[str, Any],
    ) -> str:
        """Trigger a new alert or escalate an existing active alert in-place (no duplicates).

        Returns:
            'none', 'created', or 'escalated'
        """
        stmt = select(Alert).where(
            Alert.dedup_key == dedup_key,
            Alert.status == AlertStatus.ACTIVE.value,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            # Check if escalation is required (WARNING -> CRITICAL)
            if (
                existing.severity == AlertSeverity.WARNING.value
                and target_severity == AlertSeverity.CRITICAL
            ):
                existing.severity = AlertSeverity.CRITICAL.value
                existing.metadata_json = {
                    **existing.metadata_json,
                    **metadata,
                    "escalated": True,
                    "escalated_at": utc_now().isoformat(),
                }
                return "escalated"
            return "none"

        # No active alert exists with this dedup key -> create new alert
        new_alert = Alert(
            session_id=session_id,
            table_id=table_id,
            alert_type=alert_type,
            severity=target_severity.value,
            dedup_key=dedup_key,
            status=AlertStatus.ACTIVE.value,
            metadata_json=metadata,
        )
        db.add(new_alert)
        return "created"

    @staticmethod
    async def _create_or_dedup_alert(
        db: AsyncSession,
        session_id: str,
        table_id: str,
        alert_type: str,
        severity: AlertSeverity,
        dedup_key: str,
        metadata: dict[str, Any],
    ) -> tuple[bool, Alert]:
        """Create an alert if not already active for this dedup_key."""
        stmt = select(Alert).where(
            Alert.dedup_key == dedup_key,
            Alert.status == AlertStatus.ACTIVE.value,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return False, existing

        alert = Alert(
            session_id=session_id,
            table_id=table_id,
            alert_type=alert_type,
            severity=severity.value,
            dedup_key=dedup_key,
            status=AlertStatus.ACTIVE.value,
            metadata_json=metadata,
        )
        db.add(alert)
        return True, alert

    @staticmethod
    async def _auto_resolve_alert(
        db: AsyncSession,
        dedup_key: str,
        resolved_at: datetime | None,
        reason: str,
    ) -> bool:
        """Resolve active alert for the given dedup key if currently active."""
        stmt = select(Alert).where(
            Alert.dedup_key == dedup_key,
            Alert.status == AlertStatus.ACTIVE.value,
        )
        res = await db.execute(stmt)
        alert = res.scalar_one_or_none()
        if alert:
            alert.status = AlertStatus.RESOLVED.value
            alert.resolved_at = resolved_at or utc_now()
            alert.metadata_json = {
                **alert.metadata_json,
                "resolution_reason": reason,
                "auto_resolved": True,
            }
            return True
        return False
