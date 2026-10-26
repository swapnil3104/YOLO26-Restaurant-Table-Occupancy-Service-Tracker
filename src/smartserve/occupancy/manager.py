"""Session and Persistence Lifecycle Manager for Restaurant Table Occupancy.

Follows RULES.md Sections 3, 4, 8 and PRD FR-04, FR-05, FR-06.
Handles multi-table state orchestration, atomic disk persistence, restart recovery,
and auditable transition logging.
"""

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smartserve.config import settings
from smartserve.occupancy.schema import (
    CustomerCountUpdateRequest,
    ManagerOverrideRequest,
    OccupancyState,
    StateTransitionEvent,
    TableOccupancyStatus,
    TableSession,
    get_utc_now,
)
from smartserve.occupancy.state_machine import TableStateMachine
from smartserve.tables.schema import AssociationStatus, TableAssociationResult, TrackAssociation

logger = logging.getLogger(__name__)


class OccupancySessionManager:
    """Manages table occupancy state machines, active sessions, and persistence."""

    def __init__(
        self,
        sessions_path: str | None = None,
        audit_path: str | None = None,
        persistence_threshold_sec: float | None = None,
        vacancy_grace_sec: float | None = None,
        stale_threshold_sec: float | None = None,
        require_cleaning_before_available: bool | None = None,
        count_smoothing_window: int | None = None,
    ) -> None:
        self.sessions_path = Path(sessions_path or settings.OCCUPANCY_SESSIONS_PATH)
        self.audit_path = Path(audit_path or settings.OCCUPANCY_AUDIT_PATH)
        self.persistence_threshold_sec = (
            persistence_threshold_sec
            if persistence_threshold_sec is not None
            else settings.OCCUPANCY_PERSISTENCE_TIME_SEC
        )
        self.vacancy_grace_sec = (
            vacancy_grace_sec if vacancy_grace_sec is not None else settings.VACANCY_GRACE_SEC
        )
        self.stale_threshold_sec = (
            stale_threshold_sec
            if stale_threshold_sec is not None
            else settings.CAMERA_STALE_THRESHOLD_SEC
        )
        self.require_cleaning_before_available = (
            require_cleaning_before_available
            if require_cleaning_before_available is not None
            else settings.REQUIRE_CLEANING_BEFORE_AVAILABLE
        )
        self.count_smoothing_window = (
            count_smoothing_window
            if count_smoothing_window is not None
            else settings.CUSTOMER_COUNT_SMOOTHING_WINDOW
        )

        self._state_machines: dict[str, TableStateMachine] = {}
        self._completed_sessions: list[TableSession] = []
        self._audit_log: list[StateTransitionEvent] = []

        # Ensure directory exists
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        # Load persisted state if exists
        self.load_persisted_state()

    def register_table(
        self,
        table_id: str,
        initial_state: OccupancyState = OccupancyState.AVAILABLE,
    ) -> TableStateMachine:
        """Register a table with the manager if not already tracked."""
        if table_id not in self._state_machines:
            sm = TableStateMachine(
                table_id=table_id,
                initial_state=initial_state,
                persistence_threshold_sec=self.persistence_threshold_sec,
                vacancy_grace_sec=self.vacancy_grace_sec,
                stale_threshold_sec=self.stale_threshold_sec,
                require_cleaning_before_available=self.require_cleaning_before_available,
                count_smoothing_window=self.count_smoothing_window,
            )
            self._state_machines[table_id] = sm
        return self._state_machines[table_id]

    def register_tables(self, table_ids: list[str]) -> None:
        """Register multiple tables."""
        for tid in table_ids:
            self.register_table(tid)

    def process_associations(
        self,
        associations: list[TrackAssociation],
        frame_timestamp: datetime,
        monitored_table_ids: list[str] | None = None,
        camera_healthy: bool = True,
    ) -> list[StateTransitionEvent]:
        """Process spatial track association results for a frame across all tables.

        Accepts track association list and routes tracks to their respective tables.
        """
        if frame_timestamp.tzinfo is None:
            frame_timestamp = frame_timestamp.replace(tzinfo=UTC)

        # Group valid associated tracks by table_id
        table_to_tracks: dict[str, list[int]] = {}
        for assoc in associations:
            if assoc.status == AssociationStatus.ASSOCIATED and assoc.table_id:
                if assoc.track_id is not None:
                    table_to_tracks.setdefault(assoc.table_id, []).append(assoc.track_id)

        # Tables to evaluate: all registered tables, plus any in monitored_table_ids or seen in associations
        tables_to_check = set(self._state_machines.keys())
        if monitored_table_ids:
            tables_to_check.update(monitored_table_ids)
        tables_to_check.update(table_to_tracks.keys())

        all_events: list[StateTransitionEvent] = []

        for tid in tables_to_check:
            sm = self.register_table(tid)
            tracks = table_to_tracks.get(tid, [])
            new_events = sm.process_observation(
                associated_tracks=tracks,
                observation_time=frame_timestamp,
                camera_healthy=camera_healthy,
            )
            for evt in new_events:
                all_events.append(evt)
                self._record_audit_event(evt)

                # Check if session just closed
                if evt.to_state in (OccupancyState.CLEANING_REQUIRED, OccupancyState.AVAILABLE):
                    if sm.active_session and not sm.active_session.is_active:
                        self._completed_sessions.append(sm.active_session)
                        sm.active_session = None

        if all_events:
            self.save_persisted_state()

        return all_events

    def process_frame_result(
        self,
        result: TableAssociationResult,
        monitored_table_ids: list[str] | None = None,
        camera_healthy: bool = True,
    ) -> list[StateTransitionEvent]:
        """Convenience method to process a full TableAssociationResult."""
        frame_time = datetime.fromtimestamp(result.timestamp, tz=UTC)
        flat_assocs: list[TrackAssociation] = []
        for tracks in result.associated_tracks.values():
            flat_assocs.extend(tracks)
        return self.process_associations(
            associations=flat_assocs,
            frame_timestamp=frame_time,
            monitored_table_ids=monitored_table_ids,
            camera_healthy=camera_healthy,
        )

    # --- Query Methods ---

    def get_table_status(
        self, table_id: str, current_time: datetime | None = None
    ) -> TableOccupancyStatus | None:
        sm = self._state_machines.get(table_id)
        if not sm:
            return None
        return sm.get_status(current_time)

    def get_all_statuses(
        self, current_time: datetime | None = None
    ) -> dict[str, TableOccupancyStatus]:
        return {tid: sm.get_status(current_time) for tid, sm in self._state_machines.items()}

    def get_active_session(self, table_id: str) -> TableSession | None:
        sm = self._state_machines.get(table_id)
        if sm and sm.active_session and sm.active_session.is_active:
            return sm.active_session
        return None

    def get_all_active_sessions(self) -> list[TableSession]:
        sessions: list[TableSession] = []
        for sm in self._state_machines.values():
            if sm.active_session and sm.active_session.is_active:
                sessions.append(sm.active_session)
        return sessions

    def get_session_history(
        self,
        table_id: str | None = None,
        include_active: bool = True,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TableSession]:
        """Return historical and optionally active sessions ordered by start_time descending."""
        sessions: list[TableSession] = list(self._completed_sessions)
        if include_active:
            for sm in self._state_machines.values():
                if sm.active_session:
                    sessions.append(sm.active_session)

        if table_id:
            sessions = [s for s in sessions if s.table_id == table_id]
        if start_time:
            sessions = [s for s in sessions if s.start_time >= start_time]
        if end_time:
            sessions = [s for s in sessions if s.start_time <= end_time]

        sessions.sort(key=lambda s: s.start_time, reverse=True)
        return sessions[offset : offset + limit]

    def get_audit_log(
        self,
        table_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StateTransitionEvent]:
        """Return transition events ordered by event_timestamp descending."""
        events = self._audit_log
        if table_id:
            events = [e for e in events if e.table_id == table_id]
        if start_time:
            events = [e for e in events if e.event_timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.event_timestamp <= end_time]
        events_sorted = sorted(events, key=lambda e: e.event_timestamp, reverse=True)
        return events_sorted[offset : offset + limit]

    # --- Manual & Staff Actions ---

    def override_table_state(
        self,
        table_id: str,
        request: ManagerOverrideRequest,
        timestamp: datetime | None = None,
    ) -> StateTransitionEvent:
        """Manager manual state override with audit trail."""
        sm = self.register_table(table_id)
        event = sm.override_state(
            target_state=request.target_state,
            actor=request.actor,
            reason=request.reason,
            customer_count=request.customer_count,
            timestamp=timestamp,
        )
        self._record_audit_event(event)

        # If session closed, move to completed
        if event.to_state in (
            OccupancyState.AVAILABLE,
            OccupancyState.CLEANING_REQUIRED,
            OccupancyState.OUT_OF_SERVICE,
        ):
            if sm.active_session and not sm.active_session.is_active:
                self._completed_sessions.append(sm.active_session)
                sm.active_session = None

        self.save_persisted_state()
        return event

    def update_customer_count(
        self,
        table_id: str,
        request: CustomerCountUpdateRequest,
        timestamp: datetime | None = None,
    ) -> bool:
        """Staff/manager manual correction of estimated guest count."""
        sm = self._state_machines.get(table_id)
        if not sm:
            return False
        sm.correct_customer_count(
            count=request.customer_count,
            actor=request.actor,
            reason=request.reason,
            timestamp=timestamp,
        )
        self.save_persisted_state()
        return True

    def mark_table_cleaned(
        self,
        table_id: str,
        actor: str,
        reason: str = "Table sanitized and reset",
        timestamp: datetime | None = None,
    ) -> StateTransitionEvent | None:
        """Mark table cleaned and transition to AVAILABLE."""
        sm = self._state_machines.get(table_id)
        if not sm:
            return None
        event = sm.mark_cleaned(actor=actor, reason=reason, timestamp=timestamp)
        self._record_audit_event(event)
        self.save_persisted_state()
        return event

    # --- State Persistence & Recovery (RULES.md Section 4.3) ---

    def _record_audit_event(self, event: StateTransitionEvent) -> None:
        """Append event to in-memory audit log and disk audit file."""
        self._audit_log.append(event)
        try:
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to append to audit log {self.audit_path}: {e}")

    def save_persisted_state(self) -> None:
        """Atomically persist active table states and sessions to disk."""
        data: dict[str, Any] = {
            "saved_at": get_utc_now().isoformat(),
            "tables": {},
            "completed_sessions": [
                s.model_dump(mode="json") for s in self._completed_sessions[-200:]
            ],
        }

        for tid, sm in self._state_machines.items():
            data["tables"][tid] = {
                "current_state": sm.current_state.value,
                "last_state_change": sm.last_state_change.isoformat(),
                "last_evidence_time": sm.last_evidence_time.isoformat()
                if sm.last_evidence_time
                else None,
                "evidence_start_time": sm.evidence_start_time.isoformat()
                if sm.evidence_start_time
                else None,
                "vacancy_start_time": sm.vacancy_start_time.isoformat()
                if sm.vacancy_start_time
                else None,
                "active_session": sm.active_session.model_dump(mode="json")
                if sm.active_session
                else None,
                "estimated_customer_count": sm.estimated_customer_count,
            }

        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=self.sessions_path.parent, prefix="sessions_", suffix=".tmp"
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.sessions_path)
        except Exception as e:
            logger.error(f"Failed to persist occupancy sessions to {self.sessions_path}: {e}")

    def load_persisted_state(self) -> None:
        """Restore active sessions and table states from disk on application restart."""
        # 1. Load audit log if exists
        if self.audit_path.exists():
            try:
                self._audit_log.clear()
                with open(self.audit_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._audit_log.append(StateTransitionEvent.model_validate_json(line))
            except Exception as e:
                logger.warning(f"Could not load audit log {self.audit_path}: {e}")

        # 2. Load sessions and table states
        if not self.sessions_path.exists():
            return

        try:
            with open(self.sessions_path, encoding="utf-8") as f:
                data = json.load(f)

            self._completed_sessions = [
                TableSession.model_validate(s) for s in data.get("completed_sessions", [])
            ]

            tables_data = data.get("tables", {})
            for tid, tdata in tables_data.items():
                sm = self.register_table(
                    table_id=tid,
                    initial_state=OccupancyState(
                        tdata.get("current_state", OccupancyState.AVAILABLE.value)
                    ),
                )
                if tdata.get("last_state_change"):
                    sm.last_state_change = datetime.fromisoformat(tdata["last_state_change"])
                if tdata.get("last_evidence_time"):
                    sm.last_evidence_time = datetime.fromisoformat(tdata["last_evidence_time"])
                if tdata.get("evidence_start_time"):
                    sm.evidence_start_time = datetime.fromisoformat(tdata["evidence_start_time"])
                if tdata.get("vacancy_start_time"):
                    sm.vacancy_start_time = datetime.fromisoformat(tdata["vacancy_start_time"])
                if tdata.get("active_session"):
                    sm.active_session = TableSession.model_validate(tdata["active_session"])
                sm._estimated_customer_count = tdata.get("estimated_customer_count", 0)

            logger.info(
                f"Successfully restored {len(self._state_machines)} tables from {self.sessions_path}"
            )
        except Exception as e:
            logger.error(f"Failed to load persisted occupancy state from {self.sessions_path}: {e}")
