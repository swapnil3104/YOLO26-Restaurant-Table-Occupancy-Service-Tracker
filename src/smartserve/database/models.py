"""SQLAlchemy 2.0 ORM models for restaurant operational event domain."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from smartserve.database.base import Base, TimestampMixin, UTCDateTime, generate_uuid, utc_now

# Use JSON type compatible with both SQLite and PostgreSQL
JSON_TYPE = JSON().with_variant(SQLiteJSON, "sqlite")


class Restaurant(Base):
    """Restaurant establishment entity."""

    __tablename__ = "restaurants"

    restaurant_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    tables: Mapped[list["Table"]] = relationship(
        "Table", back_populates="restaurant", cascade="all, delete-orphan"
    )
    cameras: Mapped[list["Camera"]] = relationship(
        "Camera", back_populates="restaurant", cascade="all, delete-orphan"
    )
    floors: Mapped[list["Floor"]] = relationship(
        "Floor", back_populates="restaurant", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="restaurant", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["TableSession"]] = relationship(
        "TableSession", back_populates="restaurant", cascade="all, delete-orphan"
    )
    kpi_snapshots: Mapped[list["KpiSnapshot"]] = relationship(
        "KpiSnapshot", back_populates="restaurant", cascade="all, delete-orphan"
    )


class Floor(Base):
    """Restaurant floor / level entity."""

    __tablename__ = "floors"

    floor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    floor_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="floors")
    cameras: Mapped[list["Camera"]] = relationship("Camera", back_populates="floor_rel")


class Camera(Base):
    """Vision sensor / camera source feed."""

    __tablename__ = "cameras"

    camera_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("floors.floor_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    floor_name: Mapped[str] = mapped_column(String(64), default="Floor 1", nullable=False)
    section: Mapped[str] = mapped_column(String(64), default="Main Dining", nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), default="live_stream", nullable=False
    )  # live_stream, recorded_footage, WEBCAM, RTSP, VIDEO_FILE, MOCK
    source_mode: Mapped[str] = mapped_column(
        String(32), default="tracking", nullable=False
    )  # view_only, tracking
    stream_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resolution: Mapped[str] = mapped_column(String(32), default="1280x720", nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="ONLINE", nullable=False
    )  # ONLINE, CONNECTED, DISCONNECTED, ERROR, DEGRADED, OFFLINE
    tracking_status: Mapped[str] = mapped_column(
        String(32), default="Monitoring", nullable=False
    )  # Added, Validating, Initializing Model, Monitoring, Paused, Error, Disconnected, Stopping, Stopped
    camera_health: Mapped[str] = mapped_column(
        String(32), default="HEALTHY", nullable=False
    )  # HEALTHY, DEGRADED, DISCONNECTED
    inference_status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False
    )  # ACTIVE, INITIALIZING, PAUSED, IDLE, ERROR
    effective_fps: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    last_event_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str] = mapped_column(
        String(64), default="models/yolo26_restaurant_cctv.pt", nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="cameras")
    floor_rel: Mapped["Floor | None"] = relationship("Floor", back_populates="cameras")
    tables: Mapped[list["Table"]] = relationship("Table", back_populates="camera")
    tracking_jobs: Mapped[list["TrackingJob"]] = relationship(
        "TrackingJob", back_populates="camera", cascade="all, delete-orphan"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="camera", cascade="all, delete-orphan"
    )


# Entity alias for CameraSource
CameraSource = Camera


class Table(Base):
    """Dining table in the restaurant layout."""

    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "table_code", name="uq_restaurant_table_code"),
    )

    table_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    camera_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("cameras.camera_id", ondelete="SET NULL"), nullable=True
    )
    region_config: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="AVAILABLE", nullable=False
    )  # OccupancyState
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="tables")
    camera: Mapped["Camera | None"] = relationship("Camera", back_populates="tables")
    sessions: Mapped[list["TableSession"]] = relationship(
        "TableSession", back_populates="table", cascade="all, delete-orphan"
    )
    events: Mapped[list["ServiceEvent"]] = relationship(
        "ServiceEvent", back_populates="table", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="table")
    assignments: Mapped[list["WaiterAssignment"]] = relationship(
        "WaiterAssignment", back_populates="table"
    )


class User(Base):
    """Restaurant staff member or administrator."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default="WAITER", nullable=False
    )  # ADMIN, MANAGER, WAITER, ANALYST
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="users")
    assignments: Mapped[list["WaiterAssignment"]] = relationship(
        "WaiterAssignment", back_populates="user"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")


class TableSession(Base, TimestampMixin):
    """A dining session at a table from confirmed seating to vacancy."""

    __tablename__ = "table_sessions"
    __table_args__ = (
        Index("ix_table_sessions_table_started", "table_id", "started_at"),
        Index("ix_table_sessions_status_started", "session_status", "started_at"),
    )

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    table_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    customer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_attendance_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_food_delivery_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    session_status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False, index=True
    )  # ACTIVE, COMPLETED, NEEDS_REVIEW, CANCELLED
    data_quality: Mapped[str] = mapped_column(
        String(32), default="CONFIRMED", nullable=False
    )  # CONFIRMED, MIXED, UNCERTAIN

    # Relationships
    table: Mapped["Table"] = relationship("Table", back_populates="sessions")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="sessions")
    events: Mapped[list["ServiceEvent"]] = relationship(
        "ServiceEvent", back_populates="session", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="session")


class ServiceEvent(Base):
    """Discrete operational event occurring during table service lifecycle."""

    __tablename__ = "service_events"
    __table_args__ = (
        Index("ix_service_events_table_ts", "table_id", "event_timestamp"),
        Index("ix_service_events_session_type", "session_id", "event_type"),
        Index("ix_service_events_type_ts", "event_type", "event_timestamp"),
        UniqueConstraint("idempotency_key", name="uq_service_events_idempotency_key"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("table_sessions.session_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    table_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SEATING, FIRST_ATTENDANCE, ATTENDANCE, ORDER_TAKEN, FOOD_DELIVERY, ...
    event_timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), default="VISION", nullable=False
    )  # VISION, WAITER_UI, POS, MANAGER_OVERRIDE, SYSTEM
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(32), default="CANDIDATE", nullable=False
    )  # CANDIDATE, CONFIRMED, CORRECTED, REJECTED
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supersedes_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("service_events.event_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    session: Mapped["TableSession | None"] = relationship("TableSession", back_populates="events")
    table: Mapped["Table"] = relationship("Table", back_populates="events")
    creator: Mapped["User | None"] = relationship("User")
    superseded_by: Mapped[list["ServiceEvent"]] = relationship(
        "ServiceEvent", backref="superseded_event", remote_side=[event_id]
    )


class WaiterAssignment(Base):
    """Assignment of a staff member to a table or section."""

    __tablename__ = "waiter_assignments"

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    section_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="assignments")
    table: Mapped["Table | None"] = relationship("Table", back_populates="assignments")


class Alert(Base):
    """Operational alert raised for timing violations or anomalies."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_severity", "status", "severity"),)

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("table_sessions.session_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    table_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("tables.table_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(32), default="WARNING", nullable=False
    )  # INFO, WARNING, CRITICAL
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False, index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False, index=True
    )  # ACTIVE, ACKNOWLEDGED, RESOLVED
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships
    session: Mapped["TableSession | None"] = relationship("TableSession", back_populates="alerts")
    table: Mapped["Table | None"] = relationship("Table", back_populates="alerts")


class AuditLog(Base):
    """Append-only audit trail for administrative changes, corrections, and overrides."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False, index=True
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")


class TrackingJob(Base):
    """Inference and tracking job lifecycle state."""

    __tablename__ = "tracking_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    camera_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("cameras.camera_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="INITIALIZING", nullable=False, index=True
    )  # INITIALIZING, MONITORING, PAUSED, STOPPED, ERROR
    model_version: Mapped[str] = mapped_column(
        String(64), default="models/yolo26_restaurant_cctv.pt", nullable=False
    )
    effective_fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    worker_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="tracking_jobs")
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="job", cascade="all, delete-orphan"
    )


class DetectionEvent(Base):
    """Timestamped computer vision detection and track event."""

    __tablename__ = "detection_events"
    __table_args__ = (
        Index("ix_detection_events_camera_ts", "camera_id", "timestamp"),
        Index("ix_detection_events_job_ts", "job_id", "timestamp"),
    )

    detection_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("cameras.camera_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("tracking_jobs.job_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False, index=True
    )
    person_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_tracks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    associations_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    detections_json: Mapped[list[Any]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="detection_events")
    job: Mapped["TrackingJob | None"] = relationship(
        "TrackingJob", back_populates="detection_events"
    )


class KpiSnapshot(Base):
    """Persisted periodic or point-in-time KPI snapshot."""

    __tablename__ = "kpi_snapshots"
    __table_args__ = (
        Index("ix_kpi_snapshots_scope_ts", "scope", "timestamp"),
        Index("ix_kpi_snapshots_floor_ts", "floor_id", "timestamp"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("floors.floor_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(32), default="CENTRAL", nullable=False
    )  # CENTRAL, FLOOR, SHIFT
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False, index=True
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships
    floor: Mapped["Floor | None"] = relationship("Floor")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="kpi_snapshots")


# Entity alias for OccupancyEvent (reusing ServiceEvent domain)
OccupancyEvent = ServiceEvent
