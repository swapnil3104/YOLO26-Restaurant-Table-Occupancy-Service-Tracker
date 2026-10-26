"""Pydantic V2 schemas for operational event domain, sessions, alerts, and audit."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from smartserve.database.base import utc_now


class EventType(StrEnum):
    """Enumeration of recognized operational table events."""

    SEATING = "SEATING"
    FIRST_ATTENDANCE = "FIRST_ATTENDANCE"
    ATTENDANCE = "ATTENDANCE"
    ORDER_TAKEN = "ORDER_TAKEN"
    FOOD_DELIVERY = "FOOD_DELIVERY"
    DRINK_DELIVERY = "DRINK_DELIVERY"
    BILL_REQUESTED = "BILL_REQUESTED"
    PAYMENT = "PAYMENT"
    DEPARTURE = "DEPARTURE"
    CLEANING_STARTED = "CLEANING_STARTED"
    CLEANING_COMPLETED = "CLEANING_COMPLETED"
    STATE_CHANGE = "STATE_CHANGE"
    COUNT_UPDATE = "COUNT_UPDATE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class EventSource(StrEnum):
    """Source system or human actor originating the event."""

    VISION = "VISION"
    WAITER_UI = "WAITER_UI"
    POS = "POS"
    MANAGER_OVERRIDE = "MANAGER_OVERRIDE"
    SYSTEM = "SYSTEM"


class VerificationStatus(StrEnum):
    """Status indicating event review and validation state."""

    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"


class SessionStatus(StrEnum):
    """Lifecycle state of a dining session."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CANCELLED = "CANCELLED"


class DataQuality(StrEnum):
    """Data reliability grade of session telemetry."""

    CONFIRMED = "CONFIRMED"
    MIXED = "MIXED"
    UNCERTAIN = "UNCERTAIN"


class AlertSeverity(StrEnum):
    """Severity level of operational service alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    """Resolution state of operational alerts."""

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class UserRole(StrEnum):
    """User authorization roles."""

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    WAITER = "WAITER"
    ANALYST = "ANALYST"


# ---------------------------------------------------------------------------
# Pydantic Request / Response Schemas
# ---------------------------------------------------------------------------


class ServiceEventCreate(BaseModel):
    """Payload to record an operational event."""

    table_id: str = Field(..., description="Target table identifier")
    session_id: str | None = Field(None, description="Active session ID, if applicable")
    event_type: EventType = Field(..., description="Operational event type")
    event_timestamp: datetime | None = Field(
        default=None, description="Timestamp of visual/physical occurrence (UTC)"
    )
    source: EventSource = Field(default=EventSource.VISION, description="Event producer")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.CONFIRMED, description="Initial verification status"
    )
    created_by: str | None = Field(None, description="User ID of authoring user")
    idempotency_key: str | None = Field(
        None, description="Client-supplied uniqueness key for idempotent submission"
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary event metadata"
    )


class ServiceEventRead(BaseModel):
    """Serialized representation of a persisted service event."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    session_id: str | None = None
    table_id: str
    event_type: str
    event_timestamp: datetime
    recorded_at: datetime
    source: str
    confidence: float | None = None
    verification_status: str
    created_by: str | None = None
    idempotency_key: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_correction: bool = False
    supersedes_event_id: str | None = None


class EventCorrectionRequest(BaseModel):
    """Request payload to correct an event while preserving audit history."""

    reason: str = Field(..., min_length=3, description="Justification for correction")
    corrected_by: str | None = Field(None, description="User ID performing correction")
    new_timestamp: datetime | None = Field(None, description="Corrected occurrence timestamp")
    new_event_type: EventType | None = Field(None, description="Corrected event type")
    new_metadata: dict[str, Any] | None = Field(None, description="Updated metadata")


class TableSessionCreate(BaseModel):
    """Payload to initialize a dining table session."""

    session_id: str = Field(..., description="Unique session identifier")
    table_id: str = Field(..., description="Table identifier")
    restaurant_id: str = Field(..., description="Restaurant identifier")
    started_at: datetime = Field(default_factory=utc_now, description="Seating timestamp (UTC)")
    customer_count: int | None = Field(None, ge=0, description="Initial guest count")
    data_quality: DataQuality = Field(default=DataQuality.CONFIRMED)


class TableSessionRead(BaseModel):
    """Serialized representation of a dining table session."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    table_id: str
    restaurant_id: str
    started_at: datetime
    ended_at: datetime | None = None
    customer_count: int | None = None
    first_attendance_at: datetime | None = None
    first_food_delivery_at: datetime | None = None
    session_status: str
    data_quality: str
    created_at: datetime
    updated_at: datetime
    events: list[ServiceEventRead] = Field(default_factory=list)


class AlertCreate(BaseModel):
    """Payload to create an operational alert."""

    table_id: str | None = None
    session_id: str | None = None
    alert_type: str = Field(..., description="Alert classification")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    dedup_key: str = Field(..., description="Key used to deduplicate active alerts")
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AlertRead(BaseModel):
    """Serialized representation of an operational alert."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    session_id: str | None = None
    table_id: str | None = None
    alert_type: str
    severity: str
    dedup_key: str
    created_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    status: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AuditLogRead(BaseModel):
    """Serialized audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    user_id: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 7 Confirmation, Rejection, and Timeline Schemas
# ---------------------------------------------------------------------------


class AttendanceConfirmationRequest(BaseModel):
    """Staff payload confirming waiter attendance at a dining table."""

    table_id: str = Field(..., description="Target table identifier")
    session_id: str | None = Field(
        None, description="Active session ID (if omitted, looked up automatically)"
    )
    event_timestamp: datetime | None = Field(
        None, description="Timestamp of attendance occurrence (UTC)"
    )
    idempotency_key: str | None = Field(
        None, description="Client-supplied uniqueness key for idempotent submission"
    )
    notes: str | None = Field(None, description="Optional staff notes or interaction details")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")


class FoodDeliveryConfirmationRequest(BaseModel):
    """Staff payload confirming food delivery to a dining table."""

    table_id: str = Field(..., description="Target table identifier")
    session_id: str | None = Field(
        None, description="Active session ID (if omitted, looked up automatically)"
    )
    event_timestamp: datetime | None = Field(
        None, description="Timestamp of delivery occurrence (UTC)"
    )
    course: str | None = Field(
        None, description="Course classification (e.g., appetizers, mains, desserts, drinks)"
    )
    batch_number: int = Field(
        default=1, ge=1, description="Delivery batch sequence for multi-batch orders"
    )
    items: list[str] = Field(
        default_factory=list, description="Delivered items or ticket line items"
    )
    idempotency_key: str | None = Field(
        None, description="Client-supplied uniqueness key for idempotent submission"
    )
    notes: str | None = Field(None, description="Optional delivery notes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")


class EventRejectionRequest(BaseModel):
    """Payload to reject a mistaken or incorrect event with mandatory audit justification."""

    reason: str = Field(
        ..., min_length=3, description="Justification explaining why event is rejected"
    )
    rejected_by: str | None = Field(None, description="User ID performing the rejection")


class TimelineItemRead(BaseModel):
    """Serialized timeline event with human-readable attribution and UI presentation badge."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str
    event_timestamp: datetime
    recorded_at: datetime
    source: str
    source_label: str
    verification_status: str
    is_confirmed: bool
    actor_id: str | None = None
    actor_name: str | None = None
    is_active_milestone: bool = False
    milestone_type: str | None = None
    ui_badge_text: str
    ui_badge_variant: str  # "success", "warning", "info", "danger", "neutral"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_correction: bool = False
    supersedes_event_id: str | None = None


class SessionTimelineRead(BaseModel):
    """Serialized chronological timeline representation for a table dining session."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    table_id: str
    table_code: str | None = None
    session_status: str
    data_quality: str
    started_at: datetime
    ended_at: datetime | None = None
    first_attendance_at: datetime | None = None
    first_food_delivery_at: datetime | None = None
    customer_count: int | None = None
    items: list[TimelineItemRead] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
