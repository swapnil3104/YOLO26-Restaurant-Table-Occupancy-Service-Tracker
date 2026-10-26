"""Database persistence sink for table occupancy transitions and sessions.

Bridges the vision/occupancy state machine with the relational database domain.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.session import AsyncSessionLocal
from smartserve.events.schema import (
    EventSource,
    EventType,
    ServiceEventCreate,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.occupancy.schema import StateTransitionEvent
from smartserve.occupancy.schema import TableSession as OccupancySession

logger = logging.getLogger(__name__)


class DatabaseOccupancySink:
    """Asynchronously sinks table state machine transitions and sessions into the database."""

    def __init__(self, default_restaurant_id: str = "default-rest-01") -> None:
        self.default_restaurant_id = default_restaurant_id

    async def sync_session_creation(
        self, session: OccupancySession, db_session: AsyncSession | None = None
    ) -> None:
        """Persist newly created active session into database."""

        async def _do_sync(s: AsyncSession) -> None:
            sess_in = TableSessionCreate(
                session_id=session.session_id,
                table_id=session.table_id,
                restaurant_id=self.default_restaurant_id,
                started_at=session.start_time,
                customer_count=session.estimated_customer_count,
            )
            await EventDomainService.create_table_session(s, sess_in)

            # Record initial SEATING event
            event_in = ServiceEventCreate(
                table_id=session.table_id,
                session_id=session.session_id,
                event_type=EventType.SEATING,
                event_timestamp=session.start_time,
                source=EventSource.VISION,
                verification_status=VerificationStatus.CONFIRMED,
                idempotency_key=f"seating_{session.session_id}",
                metadata_json={"customer_count": session.estimated_customer_count},
            )
            await EventDomainService.record_event(s, event_in)

        try:
            if db_session:
                await _do_sync(db_session)
            else:
                async with AsyncSessionLocal() as s:
                    await _do_sync(s)
        except Exception as e:
            logger.error(f"Failed to sync session {session.session_id} creation to DB: {e}")

    async def sync_transition(
        self, transition: StateTransitionEvent, db_session: AsyncSession | None = None
    ) -> None:
        """Record state machine transition into database service_events."""

        async def _do_sync(s: AsyncSession) -> None:
            # Map transition to operational event
            event_type = EventType.STATE_CHANGE
            if transition.to_state.value == "OCCUPIED" and transition.from_state.value in (
                "AVAILABLE",
                "POSSIBLY_OCCUPIED",
            ):
                event_type = EventType.SEATING
            elif transition.to_state.value in (
                "CLEANING_REQUIRED",
                "AVAILABLE",
            ) and transition.from_state.value in (
                "OCCUPIED",
                "POSSIBLY_VACANT",
            ):
                event_type = EventType.DEPARTURE
            elif transition.to_state.value == "CLEANING_STARTED":
                event_type = EventType.CLEANING_STARTED
            elif (
                transition.to_state.value == "AVAILABLE"
                and transition.from_state.value == "CLEANING_REQUIRED"
            ):
                event_type = EventType.CLEANING_COMPLETED

            # Map source
            src_str = transition.source.value.upper()
            source = EventSource.VISION
            if "WAITER" in src_str:
                source = EventSource.WAITER_UI
            elif "MANAGER" in src_str:
                source = EventSource.MANAGER_OVERRIDE
            elif "SYSTEM" in src_str:
                source = EventSource.SYSTEM

            event_in = ServiceEventCreate(
                table_id=transition.table_id,
                session_id=transition.session_id,
                event_type=event_type,
                event_timestamp=transition.timestamp,
                source=source,
                confidence=transition.confidence,
                verification_status=VerificationStatus.CONFIRMED,
                idempotency_key=f"trans_{transition.table_id}_{transition.timestamp.isoformat()}_{transition.to_state.value}",
                metadata_json={
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "reason": transition.reason,
                    "active_tracks": transition.active_tracks,
                },
            )
            await EventDomainService.record_event(s, event_in)

        try:
            if db_session:
                await _do_sync(db_session)
            else:
                async with AsyncSessionLocal() as s:
                    await _do_sync(s)
        except Exception as e:
            logger.error(f"Failed to sync transition for table {transition.table_id} to DB: {e}")
