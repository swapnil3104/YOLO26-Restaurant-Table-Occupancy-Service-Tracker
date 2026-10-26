"""Occupancy and session schemas, enumerations, and data models.

Follows RULES.md Sections 3, 4, and 8, and PRD FR-04, FR-05, and FR-06.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# pyrefly: ignore[missing-import]
from pydantic import BaseModel, Field, field_validator


class OccupancyState(StrEnum):
    """Core table occupancy states conforming to RULES.md Section 3.1."""

    AVAILABLE = "AVAILABLE"
    POSSIBLY_OCCUPIED = "POSSIBLY_OCCUPIED"
    OCCUPIED = "OCCUPIED"
    POSSIBLY_VACANT = "POSSIBLY_VACANT"
    CLEANING_REQUIRED = "CLEANING_REQUIRED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    UNKNOWN = "UNKNOWN"


class ServiceStatus(StrEnum):
    """Core service milestone statuses conforming to RULES.md Section 3.2 & 9."""

    WAITING_FOR_ATTENDANCE = "WAITING_FOR_ATTENDANCE"
    ATTENDED = "ATTENDED"
    WAITING_FOR_FOOD = "WAITING_FOR_FOOD"
    PARTIALLY_SERVED = "PARTIALLY_SERVED"
    SERVED = "SERVED"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class EventSource(StrEnum):
    """Operational event source conforming to RULES.md Section 3.4."""

    VISION = "vision"
    WAITER_UI = "waiter_ui"
    MANAGER_UI = "manager_ui"
    POS = "pos"
    KDS = "kds"
    SYSTEM = "system"


class VerificationStatus(StrEnum):
    """Event verification status conforming to RULES.md Section 3.3."""

    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"


def get_utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


class TableSession(BaseModel):
    """Occupancy session representing a customer seating visit at a table.

    Follows RULES.md Section 4.3 and 8.
    """

    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}")
    table_id: str
    start_time: datetime
    end_time: datetime | None = None
    recorded_at: datetime = Field(default_factory=get_utc_now)
    estimated_customer_count: int = Field(default=1, ge=0)
    max_observed_customers: int = Field(default=1, ge=0)
    service_status: ServiceStatus = ServiceStatus.WAITING_FOR_ATTENDANCE
    occupancy_duration_sec: float | None = None
    active_tracks: list[int] = Field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start_time", "end_time", "recorded_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    def calculate_duration(self, current_time: datetime | None = None) -> float:
        """Calculate occupancy duration in seconds (T_end - T_seating or T_now - T_seating).

        Rule 8.3: If negative, flag or clamp rather than silently fabricating invalid intervals.
        """
        ref_end = self.end_time if self.end_time is not None else (current_time or get_utc_now())
        duration = (ref_end - self.start_time).total_seconds()
        if duration < 0:
            # Negative duration indicates time sync anomaly
            return 0.0
        return round(duration, 2)

    def close(self, end_timestamp: datetime, reason: str | None = None) -> None:
        """Close this session and record duration."""
        if end_timestamp.tzinfo is None:
            end_timestamp = end_timestamp.replace(tzinfo=UTC)
        self.end_time = end_timestamp
        self.is_active = False
        self.occupancy_duration_sec = self.calculate_duration()
        if reason:
            self.metadata["close_reason"] = reason


class StateTransitionEvent(BaseModel):
    """Auditable state transition event conforming to RULES.md Section 2, 4, and 9."""

    transition_id: str = Field(default_factory=lambda: f"trans_{uuid.uuid4().hex[:12]}")
    table_id: str
    session_id: str | None = None
    from_state: OccupancyState
    to_state: OccupancyState
    event_timestamp: datetime
    recorded_at: datetime = Field(default_factory=get_utc_now)
    source: EventSource = EventSource.VISION
    verification_status: VerificationStatus = VerificationStatus.CONFIRMED
    reason: str | None = None
    actor: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_timestamp", "recorded_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class TableOccupancyStatus(BaseModel):
    """Comprehensive snapshot of a single table's current occupancy state."""

    table_id: str
    current_state: OccupancyState
    is_stale: bool = False
    active_session: TableSession | None = None
    estimated_customer_count: int = 0
    last_state_change: datetime
    last_evidence_time: datetime | None = None
    evidence_persistence_sec: float = 0.0
    vacancy_grace_remaining_sec: float = 0.0
    active_track_ids: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManagerOverrideRequest(BaseModel):
    """Payload for manager manual override of table state."""

    target_state: OccupancyState
    reason: str = Field(..., min_length=3, description="Operational justification for audit trail")
    actor: str = Field(..., min_length=2, description="Manager username or ID")
    customer_count: int | None = Field(default=None, ge=0)


class CustomerCountUpdateRequest(BaseModel):
    """Payload for staff/manager manual correction of customer count."""

    customer_count: int = Field(..., ge=0)
    reason: str = Field(..., min_length=3)
    actor: str = Field(..., min_length=2)


class OccupancySnapshot(BaseModel):
    """All table occupancy states at a given instant."""

    timestamp: datetime = Field(default_factory=get_utc_now)
    tables: dict[str, TableOccupancyStatus] = Field(default_factory=dict)
