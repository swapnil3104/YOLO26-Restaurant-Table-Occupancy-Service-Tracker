"""Deterministic Table Occupancy State Machine.

Implements RULES.md Section 4 (State Machine, Persistence, Grace Periods, Outages),
Section 5 (Counting & Deduplication), and PRD FR-04, FR-05, FR-06.
"""

import statistics
from collections import deque
from datetime import UTC, datetime
from typing import Any

from smartserve.occupancy.schema import (
    EventSource,
    OccupancyState,
    ServiceStatus,
    StateTransitionEvent,
    TableOccupancyStatus,
    TableSession,
    VerificationStatus,
    get_utc_now,
)


class TableStateMachine:
    """Manages deterministic occupancy state transitions for a single restaurant table."""

    def __init__(
        self,
        table_id: str,
        initial_state: OccupancyState = OccupancyState.AVAILABLE,
        persistence_threshold_sec: float = 5.0,
        vacancy_grace_sec: float = 180.0,
        stale_threshold_sec: float = 30.0,
        require_cleaning_before_available: bool = True,
        count_smoothing_window: int = 5,
    ) -> None:
        self.table_id = table_id
        self.current_state = initial_state
        self.persistence_threshold_sec = persistence_threshold_sec
        self.vacancy_grace_sec = vacancy_grace_sec
        self.stale_threshold_sec = stale_threshold_sec
        self.require_cleaning_before_available = require_cleaning_before_available

        now = get_utc_now()
        self.last_state_change: datetime = now
        self.last_observation_time: datetime | None = None
        self.last_evidence_time: datetime | None = None
        self.evidence_start_time: datetime | None = None
        self.vacancy_start_time: datetime | None = None

        self.active_session: TableSession | None = None
        self.is_stale: bool = False

        self._count_history: deque[int] = deque(maxlen=max(1, count_smoothing_window))
        self._current_track_ids: list[int] = []
        self._estimated_customer_count: int = 0

    @property
    def estimated_customer_count(self) -> int:
        return self._estimated_customer_count

    def _get_smoothed_count(self, raw_count: int) -> int:
        """Apply temporal smoothing to raw person counts to prevent count jitter."""
        self._count_history.append(raw_count)
        if not self._count_history:
            return raw_count
        # Use median to resist single-frame outliers/glitches
        return int(statistics.median(self._count_history))

    def process_observation(
        self,
        associated_tracks: list[int],
        observation_time: datetime,
        camera_healthy: bool = True,
    ) -> list[StateTransitionEvent]:
        """Update table state based on vision tracking contact observations.

        Returns any state transition events generated during this tick.
        """
        if observation_time.tzinfo is None:
            observation_time = observation_time.replace(tzinfo=UTC)

        events: list[StateTransitionEvent] = []

        # Check for camera health and staleness (RULES.md 4.1 & 4.3)
        if not camera_healthy:
            if not self.is_stale:
                self.is_stale = True
            # Freeze state transitions — do NOT vacate tables on camera outage
            return events

        if self.last_observation_time is not None:
            gap = (observation_time - self.last_observation_time).total_seconds()
            if gap > self.stale_threshold_sec:
                self.is_stale = True
                # Stale observation: retain last known state without auto-vacating
                self.last_observation_time = observation_time
                return events

        self.is_stale = False
        self.last_observation_time = observation_time

        # If manually marked OUT_OF_SERVICE, do not automatically transition
        if self.current_state == OccupancyState.OUT_OF_SERVICE:
            return events

        # Deduplicate track IDs (RULES.md 5.5)
        unique_tracks = sorted(set(associated_tracks))
        self._current_track_ids = unique_tracks
        raw_count = len(unique_tracks)
        smoothed_count = self._get_smoothed_count(raw_count)
        self._estimated_customer_count = smoothed_count

        has_occupancy_evidence = raw_count > 0

        if has_occupancy_evidence:
            self.last_evidence_time = observation_time

        # --- State Machine Transitions (RULES.md 4.1) ---

        if self.current_state == OccupancyState.AVAILABLE:
            if has_occupancy_evidence:
                # Evidence begins: transition to POSSIBLY_OCCUPIED
                self.evidence_start_time = observation_time
                event = self._transition_to(
                    to_state=OccupancyState.POSSIBLY_OCCUPIED,
                    timestamp=observation_time,
                    reason="Initial occupancy contact detected",
                    evidence={"raw_tracks": unique_tracks, "count": raw_count},
                )
                events.append(event)

        elif self.current_state == OccupancyState.POSSIBLY_OCCUPIED:
            if has_occupancy_evidence:
                assert self.evidence_start_time is not None
                elapsed_persistence = (observation_time - self.evidence_start_time).total_seconds()
                if elapsed_persistence >= self.persistence_threshold_sec:
                    # Occupancy confirmed: create session!
                    initial_count = max(1, smoothed_count)
                    session = TableSession(
                        table_id=self.table_id,
                        start_time=self.evidence_start_time,
                        estimated_customer_count=initial_count,
                        max_observed_customers=initial_count,
                        active_tracks=unique_tracks,
                        service_status=ServiceStatus.WAITING_FOR_ATTENDANCE,
                    )
                    self.active_session = session

                    event = self._transition_to(
                        to_state=OccupancyState.OCCUPIED,
                        timestamp=observation_time,
                        reason=f"Evidence persisted for {elapsed_persistence:.1f}s >= {self.persistence_threshold_sec}s",
                        evidence={
                            "session_id": session.session_id,
                            "persistence_sec": elapsed_persistence,
                            "tracks": unique_tracks,
                            "count": initial_count,
                        },
                    )
                    events.append(event)
                    self.evidence_start_time = None
            else:
                # Evidence vanished before persistence threshold: transient passer-by!
                event = self._transition_to(
                    to_state=OccupancyState.AVAILABLE,
                    timestamp=observation_time,
                    reason="Evidence disappeared before confirmation window (transient passer-by filtered)",
                    evidence={"raw_tracks": []},
                )
                events.append(event)
                self.evidence_start_time = None

        elif self.current_state == OccupancyState.OCCUPIED:
            if has_occupancy_evidence:
                # Update active session with track data
                if self.active_session:
                    self.active_session.active_tracks = unique_tracks
                    if smoothed_count > 0:
                        self.active_session.estimated_customer_count = smoothed_count
                        self.active_session.max_observed_customers = max(
                            self.active_session.max_observed_customers, smoothed_count
                        )
            else:
                # Evidence vanished: enter POSSIBLY_VACANT grace period
                self.vacancy_start_time = observation_time
                event = self._transition_to(
                    to_state=OccupancyState.POSSIBLY_VACANT,
                    timestamp=observation_time,
                    reason="Occupancy evidence vanished; starting vacancy grace period",
                    evidence={
                        "session_id": self.active_session.session_id
                        if self.active_session
                        else None
                    },
                )
                events.append(event)

        elif self.current_state == OccupancyState.POSSIBLY_VACANT:
            if has_occupancy_evidence:
                # Evidence returned within grace period: cancel vacancy!
                self.vacancy_start_time = None
                event = self._transition_to(
                    to_state=OccupancyState.OCCUPIED,
                    timestamp=observation_time,
                    reason="Evidence reappeared during grace period; active session preserved",
                    evidence={"tracks": unique_tracks, "count": smoothed_count},
                )
                events.append(event)
            else:
                assert self.vacancy_start_time is not None
                elapsed_vacancy = (observation_time - self.vacancy_start_time).total_seconds()
                if elapsed_vacancy >= self.vacancy_grace_sec:
                    # Vacancy confirmed! Close active session
                    closed_session_id = None
                    if self.active_session:
                        self.active_session.close(
                            end_timestamp=self.vacancy_start_time,
                            reason=f"Vacancy grace period expired ({elapsed_vacancy:.1f}s)",
                        )
                        closed_session_id = self.active_session.session_id

                    next_state = (
                        OccupancyState.CLEANING_REQUIRED
                        if self.require_cleaning_before_available
                        else OccupancyState.AVAILABLE
                    )
                    event = self._transition_to(
                        to_state=next_state,
                        timestamp=observation_time,
                        reason=f"Vacancy confirmed after {elapsed_vacancy:.1f}s grace period; session closed",
                        evidence={
                            "closed_session_id": closed_session_id,
                            "vacancy_duration": elapsed_vacancy,
                        },
                    )
                    events.append(event)
                    self.vacancy_start_time = None

        elif self.current_state == OccupancyState.CLEANING_REQUIRED:
            # If customers sit down at an uncleaned table and evidence persists
            if has_occupancy_evidence:
                if self.evidence_start_time is None:
                    self.evidence_start_time = observation_time
                elapsed = (observation_time - self.evidence_start_time).total_seconds()
                if elapsed >= self.persistence_threshold_sec:
                    # New party seated at table
                    initial_count = max(1, smoothed_count)
                    session = TableSession(
                        table_id=self.table_id,
                        start_time=self.evidence_start_time,
                        estimated_customer_count=initial_count,
                        max_observed_customers=initial_count,
                        active_tracks=unique_tracks,
                        service_status=ServiceStatus.WAITING_FOR_ATTENDANCE,
                    )
                    self.active_session = session
                    event = self._transition_to(
                        to_state=OccupancyState.OCCUPIED,
                        timestamp=observation_time,
                        reason="New party seated at table needing cleaning; new session created",
                        evidence={"session_id": session.session_id, "tracks": unique_tracks},
                    )
                    events.append(event)
                    self.evidence_start_time = None
            else:
                self.evidence_start_time = None

        return events

    def _transition_to(
        self,
        to_state: OccupancyState,
        timestamp: datetime,
        reason: str,
        evidence: dict[str, Any] | None = None,
        source: EventSource = EventSource.VISION,
        verification_status: VerificationStatus = VerificationStatus.CONFIRMED,
        actor: str | None = None,
    ) -> StateTransitionEvent:
        """Internal helper to mutate state and return transition event."""
        from_state = self.current_state
        self.current_state = to_state
        self.last_state_change = timestamp

        session_id = self.active_session.session_id if self.active_session else None

        return StateTransitionEvent(
            table_id=self.table_id,
            session_id=session_id,
            from_state=from_state,
            to_state=to_state,
            event_timestamp=timestamp,
            source=source,
            verification_status=verification_status,
            reason=reason,
            actor=actor,
            evidence=evidence or {},
        )

    # --- Manager and Staff Overrides (RULES.md 4.1, 4.3 & PRD FR-04) ---

    def override_state(
        self,
        target_state: OccupancyState,
        actor: str,
        reason: str,
        customer_count: int | None = None,
        timestamp: datetime | None = None,
    ) -> StateTransitionEvent:
        """Manager manual override of table state with audit tracking."""
        now = timestamp or get_utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        # Handle active session closure if moving away from occupied
        if self.current_state in (OccupancyState.OCCUPIED, OccupancyState.POSSIBLY_VACANT):
            if target_state in (
                OccupancyState.AVAILABLE,
                OccupancyState.CLEANING_REQUIRED,
                OccupancyState.OUT_OF_SERVICE,
            ):
                if self.active_session and self.active_session.is_active:
                    self.active_session.close(
                        end_timestamp=now, reason=f"Manager override by {actor}: {reason}"
                    )

        # If manually moving to OCCUPIED from non-occupied, create session if none active
        if target_state == OccupancyState.OCCUPIED and (
            self.active_session is None or not self.active_session.is_active
        ):
            count = customer_count if customer_count is not None else 1
            self.active_session = TableSession(
                table_id=self.table_id,
                start_time=now,
                estimated_customer_count=count,
                max_observed_customers=count,
                service_status=ServiceStatus.WAITING_FOR_ATTENDANCE,
                metadata={"created_by": actor, "override_reason": reason},
            )
            self._estimated_customer_count = count

        # Reset intermediate candidate timers
        self.evidence_start_time = None
        self.vacancy_start_time = None

        return self._transition_to(
            to_state=target_state,
            timestamp=now,
            reason=reason,
            evidence={"manual_override": True, "customer_count": customer_count},
            source=EventSource.MANAGER_UI,
            verification_status=VerificationStatus.CORRECTED,
            actor=actor,
        )

    def mark_cleaned(
        self,
        actor: str,
        reason: str = "Table sanitized and reset",
        timestamp: datetime | None = None,
    ) -> StateTransitionEvent:
        """Staff marks a table as cleaned and ready for service."""
        now = timestamp or get_utc_now()
        return self._transition_to(
            to_state=OccupancyState.AVAILABLE,
            timestamp=now,
            reason=reason,
            source=EventSource.WAITER_UI,
            verification_status=VerificationStatus.CONFIRMED,
            actor=actor,
        )

    def correct_customer_count(
        self, count: int, actor: str, reason: str, timestamp: datetime | None = None
    ) -> None:
        """Manager or waiter manually corrects estimated guest count."""
        now = timestamp or get_utc_now()
        self._estimated_customer_count = count
        self._count_history.clear()
        self._count_history.append(count)

        if self.active_session and self.active_session.is_active:
            self.active_session.estimated_customer_count = count
            self.active_session.max_observed_customers = max(
                self.active_session.max_observed_customers, count
            )
            self.active_session.metadata["last_count_correction"] = {
                "actor": actor,
                "reason": reason,
                "timestamp": now.isoformat(),
                "corrected_count": count,
            }

    def get_status(self, current_time: datetime | None = None) -> TableOccupancyStatus:
        """Generate current snapshot of this table's occupancy status."""
        now = current_time or get_utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        evidence_persistence = 0.0
        if self.current_state == OccupancyState.POSSIBLY_OCCUPIED and self.evidence_start_time:
            evidence_persistence = max(0.0, (now - self.evidence_start_time).total_seconds())

        vacancy_grace_remaining = 0.0
        if self.current_state == OccupancyState.POSSIBLY_VACANT and self.vacancy_start_time:
            elapsed = (now - self.vacancy_start_time).total_seconds()
            vacancy_grace_remaining = max(0.0, self.vacancy_grace_sec - elapsed)

        return TableOccupancyStatus(
            table_id=self.table_id,
            current_state=self.current_state,
            is_stale=self.is_stale,
            active_session=self.active_session,
            estimated_customer_count=self._estimated_customer_count,
            last_state_change=self.last_state_change,
            last_evidence_time=self.last_evidence_time,
            evidence_persistence_sec=round(evidence_persistence, 1),
            vacancy_grace_remaining_sec=round(vacancy_grace_remaining, 1),
            active_track_ids=self._current_track_ids,
        )
