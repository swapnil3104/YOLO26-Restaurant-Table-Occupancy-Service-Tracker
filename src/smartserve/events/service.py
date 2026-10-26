"""Event domain service implementing transaction-safe lifecycle updates, idempotency, and audit trails."""

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import utc_now
from smartserve.database.models import (
    Alert,
    AuditLog,
    ServiceEvent,
    Table,
    TableSession,
    User,
)
from smartserve.events.schema import (
    AlertCreate,
    AlertStatus,
    AttendanceConfirmationRequest,
    EventCorrectionRequest,
    EventSource,
    EventType,
    FoodDeliveryConfirmationRequest,
    ServiceEventCreate,
    SessionStatus,
    SessionTimelineRead,
    TableSessionCreate,
    VerificationStatus,
)


class EventDomainService:
    """Service handling operational event persistence, idempotency, corrections, and alerts."""

    @staticmethod
    async def record_event(
        session: AsyncSession, event_in: ServiceEventCreate
    ) -> tuple[ServiceEvent, bool]:
        """Record an operational event with idempotency guarantees and atomic session updates.

        Returns:
            tuple[ServiceEvent, bool]: (persisted_event, is_duplicate)
        """
        # 1. Idempotency Check
        if event_in.idempotency_key:
            stmt = select(ServiceEvent).where(
                ServiceEvent.idempotency_key == event_in.idempotency_key
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                # Event already recorded via identical idempotency key; return existing without duplicate side effects
                return existing, True

        # 2. Determine occurrence timestamp (visual time)
        event_ts = event_in.event_timestamp or utc_now()

        # 3. Create ServiceEvent ORM instance
        event = ServiceEvent(
            table_id=event_in.table_id,
            session_id=event_in.session_id,
            event_type=event_in.event_type.value,
            event_timestamp=event_ts,
            source=event_in.source.value,
            confidence=event_in.confidence,
            verification_status=event_in.verification_status.value,
            created_by=event_in.created_by,
            idempotency_key=event_in.idempotency_key,
            metadata_json=event_in.metadata_json,
            is_correction=False,
        )
        session.add(event)

        # 4. Atomic Table and Session State Synchronization
        # Update table status if event implies table state change
        table_stmt = select(Table).where(Table.table_id == event_in.table_id)
        table_res = await session.execute(table_stmt)
        table = table_res.scalar_one_or_none()

        if event_in.session_id:
            sess_stmt = select(TableSession).where(TableSession.session_id == event_in.session_id)
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()

            if dining_session:
                event_type_str = event_in.event_type.value

                # Attendance handling: Only eligible CONFIRMED events end first-response timer (RULES.md 6.1)
                if event_type_str in (EventType.FIRST_ATTENDANCE.value, EventType.ATTENDANCE.value):
                    if event_in.verification_status == VerificationStatus.CONFIRMED:
                        if dining_session.first_attendance_at is None:
                            dining_session.first_attendance_at = event_ts
                        from smartserve.rules.engine import RulesEngine

                        await RulesEngine._auto_resolve_alert(
                            db=session,
                            dedup_key=f"{dining_session.session_id}:FIRST_ATTENDANCE_OVERDUE",
                            resolved_at=event_ts,
                            reason="ATTENDANCE_CONFIRMED",
                        )

                # Food delivery handling: Only eligible CONFIRMED events set delivery milestone (RULES.md 7)
                elif event_type_str == EventType.FOOD_DELIVERY.value:
                    if event_in.verification_status == VerificationStatus.CONFIRMED:
                        if dining_session.first_food_delivery_at is None:
                            dining_session.first_food_delivery_at = event_ts
                        from smartserve.rules.engine import RulesEngine

                        await RulesEngine._auto_resolve_alert(
                            db=session,
                            dedup_key=f"{dining_session.session_id}:FOOD_DELIVERY_OVERDUE",
                            resolved_at=event_ts,
                            reason="FOOD_DELIVERY_CONFIRMED",
                        )

                # Customer count update
                elif event_type_str == EventType.COUNT_UPDATE.value:
                    if "customer_count" in event_in.metadata_json:
                        dining_session.customer_count = int(
                            event_in.metadata_json["customer_count"]
                        )

                # Departure / Session completion
                elif event_type_str == EventType.DEPARTURE.value:
                    dining_session.ended_at = event_ts
                    dining_session.session_status = SessionStatus.COMPLETED.value
                    if table:
                        table.status = "CLEANING_REQUIRED"
                    # Auto-resolve remaining active alerts for this session
                    active_alerts_stmt = select(Alert).where(
                        Alert.session_id == dining_session.session_id,
                        Alert.status == AlertStatus.ACTIVE.value,
                    )
                    res_alerts = await session.execute(active_alerts_stmt)
                    for active_alert in res_alerts.scalars().all():
                        active_alert.status = AlertStatus.RESOLVED.value
                        active_alert.resolved_at = event_ts
                        active_alert.metadata_json = {
                            **active_alert.metadata_json,
                            "resolution_reason": "SESSION_COMPLETED",
                        }

        # State change event directly updates table status
        if event_in.event_type == EventType.STATE_CHANGE and table:
            new_state = event_in.metadata_json.get("new_state")
            if new_state:
                table.status = new_state

        await session.commit()
        await session.refresh(event)
        return event, False

    @staticmethod
    async def correct_event(
        session: AsyncSession, event_id: str, correction: EventCorrectionRequest
    ) -> tuple[ServiceEvent, ServiceEvent]:
        """Correct an event without destroying original history (Rule 8.2).

        Returns:
            tuple[ServiceEvent, ServiceEvent]: (original_event, superseding_event)
        """
        # Fetch target event
        stmt = select(ServiceEvent).where(ServiceEvent.event_id == event_id)
        res = await session.execute(stmt)
        original = res.scalar_one_or_none()
        if not original:
            raise ValueError(f"ServiceEvent with ID {event_id} not found")

        old_values = {
            "event_type": original.event_type,
            "event_timestamp": original.event_timestamp.isoformat(),
            "verification_status": original.verification_status,
            "metadata_json": dict(original.metadata_json),
        }

        # Mark original as CORRECTED
        original.verification_status = VerificationStatus.CORRECTED.value

        # Create superseding event
        new_event_type = (
            correction.new_event_type.value if correction.new_event_type else original.event_type
        )
        new_ts = correction.new_timestamp or original.event_timestamp
        new_meta = {
            **original.metadata_json,
            "correction_reason": correction.reason,
            **(correction.new_metadata or {}),
        }

        superseding = ServiceEvent(
            table_id=original.table_id,
            session_id=original.session_id,
            event_type=new_event_type,
            event_timestamp=new_ts,
            source=EventSource.MANAGER_OVERRIDE.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            created_by=correction.corrected_by,
            is_correction=True,
            supersedes_event_id=original.event_id,
            metadata_json=new_meta,
        )
        session.add(superseding)

        # Update parent session if attendance or food delivery timestamp changed
        if original.session_id:
            sess_stmt = select(TableSession).where(TableSession.session_id == original.session_id)
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()

            if dining_session:
                if new_event_type in (EventType.FIRST_ATTENDANCE.value, EventType.ATTENDANCE.value):
                    dining_session.first_attendance_at = new_ts
                elif new_event_type == EventType.FOOD_DELIVERY.value:
                    dining_session.first_food_delivery_at = new_ts
                elif new_event_type == EventType.DEPARTURE.value:
                    dining_session.ended_at = new_ts

        # Create AuditLog record
        audit = AuditLog(
            user_id=correction.corrected_by,
            action="CORRECT_EVENT",
            entity_type="service_event",
            entity_id=original.event_id,
            timestamp=utc_now(),
            details={
                "reason": correction.reason,
                "supersedes_event_id": original.event_id,
                "old_values": old_values,
                "new_values": {
                    "event_type": new_event_type,
                    "event_timestamp": new_ts.isoformat(),
                    "verification_status": VerificationStatus.CONFIRMED.value,
                },
            },
        )
        session.add(audit)

        # Trigger safe session recalculation and rules re-evaluation (RULES.md Section 13)
        if original.session_id:
            from smartserve.rules.engine import RulesEngine

            await RulesEngine.recalculate_session(original.session_id, session)

        await session.commit()
        await session.refresh(original)
        await session.refresh(superseding)
        return original, superseding

    @staticmethod
    async def create_table_session(
        session: AsyncSession, session_in: TableSessionCreate
    ) -> tuple[TableSession, bool]:
        """Create or retrieve a table session transaction-safely."""
        stmt = select(TableSession).where(TableSession.session_id == session_in.session_id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing, True

        new_session = TableSession(
            session_id=session_in.session_id,
            table_id=session_in.table_id,
            restaurant_id=session_in.restaurant_id,
            started_at=session_in.started_at,
            customer_count=session_in.customer_count,
            session_status=SessionStatus.ACTIVE.value,
            data_quality=session_in.data_quality.value,
        )
        session.add(new_session)

        # Ensure table status is updated to OCCUPIED
        table_stmt = select(Table).where(Table.table_id == session_in.table_id)
        table_res = await session.execute(table_stmt)
        table = table_res.scalar_one_or_none()
        if table:
            table.status = "OCCUPIED"

        await session.commit()
        await session.refresh(new_session)
        return new_session, False

    @staticmethod
    async def end_table_session(
        session: AsyncSession, session_id: str, ended_at: datetime | None = None
    ) -> TableSession:
        """Mark a table session as completed and set end timestamp."""
        stmt = select(TableSession).where(TableSession.session_id == session_id)
        res = await session.execute(stmt)
        dining_session = res.scalar_one_or_none()
        if not dining_session:
            raise ValueError(f"TableSession with ID {session_id} not found")

        end_ts = ended_at or utc_now()
        dining_session.ended_at = end_ts
        dining_session.session_status = SessionStatus.COMPLETED.value

        # Update table status to CLEANING_REQUIRED
        table_stmt = select(Table).where(Table.table_id == dining_session.table_id)
        table_res = await session.execute(table_stmt)
        table = table_res.scalar_one_or_none()
        if table:
            table.status = "CLEANING_REQUIRED"

        await session.commit()
        await session.refresh(dining_session)
        return dining_session

    @staticmethod
    async def create_or_update_alert(
        session: AsyncSession, alert_in: AlertCreate
    ) -> tuple[Alert, bool]:
        """Create an operational alert with deduplication across active alerts."""
        # Query active alert with matching dedup_key
        stmt = select(Alert).where(
            Alert.dedup_key == alert_in.dedup_key,
            Alert.status == AlertStatus.ACTIVE.value,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            # Alert already active and deduplicated
            return existing, True

        alert = Alert(
            session_id=alert_in.session_id,
            table_id=alert_in.table_id,
            alert_type=alert_in.alert_type,
            severity=alert_in.severity.value,
            dedup_key=alert_in.dedup_key,
            status=AlertStatus.ACTIVE.value,
            metadata_json=alert_in.metadata_json,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert, False

    @staticmethod
    async def acknowledge_alert(
        session: AsyncSession, alert_id: str, user_id: str | None = None
    ) -> Alert:
        """Acknowledge an active alert."""
        stmt = select(Alert).where(Alert.alert_id == alert_id)
        res = await session.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found")

        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = utc_now()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="ACKNOWLEDGE_ALERT",
            entity_type="alert",
            entity_id=alert_id,
            timestamp=utc_now(),
            details={"alert_type": alert.alert_type, "severity": alert.severity},
        )
        session.add(audit)

        await session.commit()
        await session.refresh(alert)
        return alert

    @staticmethod
    async def resolve_alert(
        session: AsyncSession, alert_id: str, user_id: str | None = None
    ) -> Alert:
        """Resolve an active or acknowledged alert."""
        stmt = select(Alert).where(Alert.alert_id == alert_id)
        res = await session.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found")

        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = utc_now()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="RESOLVE_ALERT",
            entity_type="alert",
            entity_id=alert_id,
            timestamp=utc_now(),
            details={"alert_type": alert.alert_type, "severity": alert.severity},
        )
        session.add(audit)

        await session.commit()
        await session.refresh(alert)
        return alert

    @staticmethod
    async def list_events(
        session: AsyncSession,
        table_id: str | None = None,
        session_id: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ServiceEvent]:
        """Query service events ordered chronologically descending with date and pagination filters."""
        stmt = select(ServiceEvent)
        if table_id:
            stmt = stmt.where(ServiceEvent.table_id == table_id)
        if session_id:
            stmt = stmt.where(ServiceEvent.session_id == session_id)
        if event_type:
            stmt = stmt.where(ServiceEvent.event_type == event_type)
        if start_time:
            stmt = stmt.where(ServiceEvent.event_timestamp >= start_time)
        if end_time:
            stmt = stmt.where(ServiceEvent.event_timestamp <= end_time)
        stmt = stmt.order_by(desc(ServiceEvent.event_timestamp)).offset(offset).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_alerts(
        session: AsyncSession,
        table_id: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        """Query alerts with optional table, status, date, and pagination filtering."""
        stmt = select(Alert)
        if table_id:
            stmt = stmt.where(Alert.table_id == table_id)
        if status:
            stmt = stmt.where(Alert.status == status)
        if start_time:
            stmt = stmt.where(Alert.created_at >= start_time)
        if end_time:
            stmt = stmt.where(Alert.created_at <= end_time)
        stmt = stmt.order_by(desc(Alert.created_at)).offset(offset).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_audit_logs(
        session: AsyncSession,
        entity_type: str | None = None,
        entity_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query audit log entries ordered chronologically descending with date and pagination filters."""
        stmt = select(AuditLog)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if start_time:
            stmt = stmt.where(AuditLog.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(AuditLog.timestamp <= end_time)
        stmt = stmt.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------------------------------------------------
    # Phase 7: Attendance, Delivery Confirmation, Rejection & Timeline
    # -----------------------------------------------------------------------

    @classmethod
    async def confirm_attendance(
        cls,
        session: AsyncSession,
        req: AttendanceConfirmationRequest,
        actor: User,
    ) -> tuple[ServiceEvent, bool]:
        """Confirm waiter attendance for an active table dining session.

        Requires active table session association and authorized staff actor.
        Enforces idempotency and triggers alert auto-resolution.
        """
        # Validate table exists
        table_stmt = select(Table).where(Table.table_id == req.table_id)
        table_res = await session.execute(table_stmt)
        table = table_res.scalar_one_or_none()
        if not table:
            raise ValueError(f"Table '{req.table_id}' not found")

        # Resolve target session
        if req.session_id:
            sess_stmt = select(TableSession).where(TableSession.session_id == req.session_id)
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()
            if not dining_session:
                raise ValueError(f"Session '{req.session_id}' not found")
            if dining_session.table_id != req.table_id:
                raise ValueError(
                    f"Session '{req.session_id}' does not belong to table '{req.table_id}'"
                )
            if dining_session.session_status not in (
                SessionStatus.ACTIVE.value,
                SessionStatus.NEEDS_REVIEW.value,
            ):
                raise ValueError(
                    f"Session '{req.session_id}' is {dining_session.session_status}; "
                    "cannot confirm attendance on an inactive session"
                )
        else:
            # Query active session for table
            sess_stmt = (
                select(TableSession)
                .where(
                    TableSession.table_id == req.table_id,
                    TableSession.session_status.in_(
                        [SessionStatus.ACTIVE.value, SessionStatus.NEEDS_REVIEW.value]
                    ),
                )
                .order_by(desc(TableSession.started_at))
            )
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()
            if not dining_session:
                raise ValueError(
                    f"Table '{req.table_id}' has no active dining session. "
                    "Attendance confirmation requires an active session."
                )

        # Determine source
        source = (
            EventSource.MANAGER_OVERRIDE
            if str(actor.role).upper() in ("MANAGER", "ADMIN")
            else EventSource.WAITER_UI
        )

        event_ts = req.event_timestamp or utc_now()
        is_first = dining_session.first_attendance_at is None

        metadata = {
            "action": "waiter_attendance_confirmed",
            "actor_id": actor.user_id,
            "actor_username": actor.username,
            "actor_role": actor.role,
            "is_first_attendance": is_first,
            **(req.metadata or {}),
        }
        if req.notes:
            metadata["notes"] = req.notes

        event_in = ServiceEventCreate(
            table_id=req.table_id,
            session_id=dining_session.session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=event_ts,
            source=source,
            verification_status=VerificationStatus.CONFIRMED,
            created_by=actor.user_id,
            idempotency_key=req.idempotency_key,
            metadata_json=metadata,
        )

        return await cls.record_event(session, event_in)

    @classmethod
    async def confirm_food_delivery(
        cls,
        session: AsyncSession,
        req: FoodDeliveryConfirmationRequest,
        actor: User,
    ) -> tuple[ServiceEvent, bool]:
        """Confirm food delivery for an active table dining session.

        Supports multiple delivery batches while preserving the earliest delivery milestone.
        Requires active table session association and authorized staff actor.
        """
        table_stmt = select(Table).where(Table.table_id == req.table_id)
        table_res = await session.execute(table_stmt)
        table = table_res.scalar_one_or_none()
        if not table:
            raise ValueError(f"Table '{req.table_id}' not found")

        if req.session_id:
            sess_stmt = select(TableSession).where(TableSession.session_id == req.session_id)
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()
            if not dining_session:
                raise ValueError(f"Session '{req.session_id}' not found")
            if dining_session.table_id != req.table_id:
                raise ValueError(
                    f"Session '{req.session_id}' does not belong to table '{req.table_id}'"
                )
            if dining_session.session_status not in (
                SessionStatus.ACTIVE.value,
                SessionStatus.NEEDS_REVIEW.value,
            ):
                raise ValueError(
                    f"Session '{req.session_id}' is {dining_session.session_status}; "
                    "cannot confirm delivery on an inactive session"
                )
        else:
            sess_stmt = (
                select(TableSession)
                .where(
                    TableSession.table_id == req.table_id,
                    TableSession.session_status.in_(
                        [SessionStatus.ACTIVE.value, SessionStatus.NEEDS_REVIEW.value]
                    ),
                )
                .order_by(desc(TableSession.started_at))
            )
            sess_res = await session.execute(sess_stmt)
            dining_session = sess_res.scalar_one_or_none()
            if not dining_session:
                raise ValueError(
                    f"Table '{req.table_id}' has no active dining session. "
                    "Delivery confirmation requires an active session."
                )

        source = (
            EventSource.MANAGER_OVERRIDE
            if str(actor.role).upper() in ("MANAGER", "ADMIN")
            else EventSource.WAITER_UI
        )

        event_ts = req.event_timestamp or utc_now()
        is_first = dining_session.first_food_delivery_at is None

        metadata = {
            "action": "food_delivery_confirmed",
            "actor_id": actor.user_id,
            "actor_username": actor.username,
            "actor_role": actor.role,
            "course": req.course,
            "batch_number": req.batch_number,
            "items": req.items,
            "is_first_delivery": is_first,
            **(req.metadata or {}),
        }
        if req.notes:
            metadata["notes"] = req.notes

        event_in = ServiceEventCreate(
            table_id=req.table_id,
            session_id=dining_session.session_id,
            event_type=EventType.FOOD_DELIVERY,
            event_timestamp=event_ts,
            source=source,
            verification_status=VerificationStatus.CONFIRMED,
            created_by=actor.user_id,
            idempotency_key=req.idempotency_key,
            metadata_json=metadata,
        )

        return await cls.record_event(session, event_in)

    @classmethod
    async def reject_event(
        cls,
        session: AsyncSession,
        event_id: str,
        reason: str,
        rejected_by: str | None = None,
    ) -> tuple[ServiceEvent, AuditLog]:
        """Reject an incorrect or mistaken event with audit logging and session recalculation.

        Follows RULES.md Section 3.3 and PRD FR-09.
        """
        stmt = select(ServiceEvent).where(ServiceEvent.event_id == event_id)
        res = await session.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            raise ValueError(f"ServiceEvent '{event_id}' not found")

        old_status = event.verification_status
        event.verification_status = VerificationStatus.REJECTED.value
        event.metadata_json = {
            **event.metadata_json,
            "rejection_reason": reason,
            "rejected_by": rejected_by,
            "rejected_at": utc_now().isoformat(),
        }

        audit = AuditLog(
            user_id=rejected_by,
            action="REJECT_EVENT",
            entity_type="service_event",
            entity_id=event.event_id,
            timestamp=utc_now(),
            details={
                "reason": reason,
                "previous_status": old_status,
                "event_type": event.event_type,
                "session_id": event.session_id,
                "table_id": event.table_id,
            },
        )
        session.add(audit)

        # Trigger safe session recalculation
        if event.session_id:
            from smartserve.rules.engine import RulesEngine

            await RulesEngine.recalculate_session(event.session_id, session)

        await session.commit()
        await session.refresh(event)
        await session.refresh(audit)
        return event, audit

    @classmethod
    async def get_session_timeline(
        cls,
        session: AsyncSession,
        session_id: str,
    ) -> SessionTimelineRead:
        """Build ordered chronological session timeline with UI badges and summary metrics."""
        sess_stmt = select(TableSession).where(TableSession.session_id == session_id)
        sess_res = await session.execute(sess_stmt)
        dining_session = sess_res.scalar_one_or_none()
        if not dining_session:
            raise ValueError(f"Session '{session_id}' not found")

        # Fetch table details
        table_stmt = select(Table).where(Table.table_id == dining_session.table_id)
        tbl_res = await session.execute(table_stmt)
        table = tbl_res.scalar_one_or_none()
        table_code = table.table_code if table else None

        # Fetch all events ordered chronologically
        events_stmt = (
            select(ServiceEvent)
            .where(ServiceEvent.session_id == session_id)
            .order_by(ServiceEvent.event_timestamp.asc(), ServiceEvent.recorded_at.asc())
        )
        events_res = await session.execute(events_stmt)
        events = list(events_res.scalars().all())

        # Collect user map for actors
        user_ids = {e.created_by for e in events if e.created_by}
        user_map: dict[str, User] = {}
        if user_ids:
            users_stmt = select(User).where(User.user_id.in_(user_ids))
            users_res = await session.execute(users_stmt)
            for u in users_res.scalars().all():
                user_map[u.user_id] = u

        from smartserve.events.timeline import format_timeline_item

        timeline_items = [format_timeline_item(ev, dining_session, user_map) for ev in events]

        # Compute summary
        total = len(events)
        confirmed = sum(
            1 for e in events if e.verification_status == VerificationStatus.CONFIRMED.value
        )
        candidate = sum(
            1 for e in events if e.verification_status == VerificationStatus.CANDIDATE.value
        )
        rejected = sum(
            1 for e in events if e.verification_status == VerificationStatus.REJECTED.value
        )
        corrected = sum(
            1 for e in events if e.verification_status == VerificationStatus.CORRECTED.value
        )
        food_batches = sum(
            1
            for e in events
            if e.event_type == EventType.FOOD_DELIVERY.value
            and e.verification_status == VerificationStatus.CONFIRMED.value
        )

        response_sec = (
            (dining_session.first_attendance_at - dining_session.started_at).total_seconds()
            if dining_session.first_attendance_at and dining_session.started_at
            else None
        )
        food_delivery_sec = (
            (dining_session.first_food_delivery_at - dining_session.started_at).total_seconds()
            if dining_session.first_food_delivery_at and dining_session.started_at
            else None
        )

        summary = {
            "total_events": total,
            "confirmed_events": confirmed,
            "candidate_events": candidate,
            "rejected_events": rejected,
            "corrected_events": corrected,
            "food_delivery_batches": food_batches,
            "response_time_sec": round(response_sec, 1) if response_sec is not None else None,
            "food_delivery_time_sec": (
                round(food_delivery_sec, 1) if food_delivery_sec is not None else None
            ),
        }

        return SessionTimelineRead(
            session_id=dining_session.session_id,
            table_id=dining_session.table_id,
            table_code=table_code,
            session_status=dining_session.session_status,
            data_quality=dining_session.data_quality,
            started_at=dining_session.started_at,
            ended_at=dining_session.ended_at,
            first_attendance_at=dining_session.first_attendance_at,
            first_food_delivery_at=dining_session.first_food_delivery_at,
            customer_count=dining_session.customer_count,
            items=timeline_items,
            summary=summary,
        )
