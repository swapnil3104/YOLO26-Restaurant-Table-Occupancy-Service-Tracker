"""phase7_floors_and_tracking_jobs

Revision ID: b3a1d94f8e21
Revises: e9e9025ec769
Create Date: 2026-10-25 11:10:00.000000

Adheres strictly to Docs/TASKS.md Phase 7:
- Introduce Floor, CameraSource adaptations, TrackingJob, DetectionEvent, KpiSnapshot.
- Provide upgrade and downgrade migration with rollback plan.
- Never drop existing records without an explicit data migration strategy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "b3a1d94f8e21"
down_revision: str | None = "e9e9025ec769"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create floors table
    op.create_table(
        "floors",
        sa.Column("floor_id", sa.String(length=64), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("floor_name", sa.String(length=128), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "metadata_json",
            sqlite.JSON() if op.get_bind().dialect.name == "sqlite" else sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["restaurant_id"], ["restaurants.restaurant_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("floor_id"),
    )
    with op.batch_alter_table("floors", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_floors_restaurant_id"), ["restaurant_id"], unique=False
        )

    # 2. Alter cameras table to add floor, mode, stream url, and tracking fields
    with op.batch_alter_table("cameras", schema=None) as batch_op:
        batch_op.add_column(sa.Column("floor_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("floor_name", sa.String(length=64), nullable=False, server_default="Floor 1")
        )
        batch_op.add_column(
            sa.Column("section", sa.String(length=64), nullable=False, server_default="Main Dining")
        )
        batch_op.add_column(
            sa.Column(
                "source_mode", sa.String(length=32), nullable=False, server_default="tracking"
            )
        )
        batch_op.add_column(sa.Column("stream_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("video_file_id", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("video_url", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column("resolution", sa.String(length=32), nullable=False, server_default="1280x720")
        )
        batch_op.add_column(sa.Column("fps", sa.Float(), nullable=False, server_default="30.0"))
        batch_op.add_column(
            sa.Column("is_custom", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "tracking_status", sa.String(length=32), nullable=False, server_default="Monitoring"
            )
        )
        batch_op.add_column(
            sa.Column(
                "camera_health", sa.String(length=32), nullable=False, server_default="HEALTHY"
            )
        )
        batch_op.add_column(
            sa.Column(
                "inference_status", sa.String(length=32), nullable=False, server_default="ACTIVE"
            )
        )
        batch_op.add_column(
            sa.Column("effective_fps", sa.Float(), nullable=False, server_default="30.0")
        )
        batch_op.add_column(sa.Column("last_event_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("processing_job_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "model_version",
                sa.String(length=64),
                nullable=False,
                server_default="models/yolo26_restaurant_cctv.pt",
            )
        )
        batch_op.create_foreign_key(
            "fk_cameras_floor_id", "floors", ["floor_id"], ["floor_id"], ondelete="SET NULL"
        )
        batch_op.create_index(batch_op.f("ix_cameras_floor_id"), ["floor_id"], unique=False)

    # 3. Create tracking_jobs table
    op.create_table(
        "tracking_jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="INITIALIZING"),
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=False,
            server_default="models/yolo26_restaurant_cctv.pt",
        ),
        sa.Column("effective_fps", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("worker_pid", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column(
            "config_json",
            sqlite.JSON() if op.get_bind().dialect.name == "sqlite" else sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    with op.batch_alter_table("tracking_jobs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tracking_jobs_camera_id"), ["camera_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tracking_jobs_status"), ["status"], unique=False)

    # 4. Create detection_events table
    op.create_table(
        "detection_events",
        sa.Column("detection_id", sa.String(length=36), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("person_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "associations_json",
            sqlite.JSON() if op.get_bind().dialect.name == "sqlite" else sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "detections_json",
            sqlite.JSON() if op.get_bind().dialect.name == "sqlite" else sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["tracking_jobs.job_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("detection_id"),
    )
    with op.batch_alter_table("detection_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_detection_events_camera_ts", ["camera_id", "timestamp"], unique=False
        )
        batch_op.create_index("ix_detection_events_job_ts", ["job_id", "timestamp"], unique=False)

    # 5. Create kpi_snapshots table
    op.create_table(
        "kpi_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("floor_id", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="CENTRAL"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metrics_json",
            sqlite.JSON() if op.get_bind().dialect.name == "sqlite" else sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"], ["restaurants.restaurant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["floor_id"], ["floors.floor_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    with op.batch_alter_table("kpi_snapshots", schema=None) as batch_op:
        batch_op.create_index("ix_kpi_snapshots_scope_ts", ["scope", "timestamp"], unique=False)
        batch_op.create_index("ix_kpi_snapshots_floor_ts", ["floor_id", "timestamp"], unique=False)


def downgrade() -> None:
    # 1. Drop kpi_snapshots
    with op.batch_alter_table("kpi_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_kpi_snapshots_floor_ts")
        batch_op.drop_index("ix_kpi_snapshots_scope_ts")
    op.drop_table("kpi_snapshots")

    # 2. Drop detection_events
    with op.batch_alter_table("detection_events", schema=None) as batch_op:
        batch_op.drop_index("ix_detection_events_job_ts")
        batch_op.drop_index("ix_detection_events_camera_ts")
    op.drop_table("detection_events")

    # 3. Drop tracking_jobs
    with op.batch_alter_table("tracking_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tracking_jobs_status"))
        batch_op.drop_index(batch_op.f("ix_tracking_jobs_camera_id"))
    op.drop_table("tracking_jobs")

    # 4. Revert cameras alteration
    with op.batch_alter_table("cameras", schema=None) as batch_op:
        batch_op.drop_constraint("fk_cameras_floor_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_cameras_floor_id"))
        batch_op.drop_column("model_version")
        batch_op.drop_column("processing_job_id")
        batch_op.drop_column("last_event_time")
        batch_op.drop_column("effective_fps")
        batch_op.drop_column("inference_status")
        batch_op.drop_column("camera_health")
        batch_op.drop_column("tracking_status")
        batch_op.drop_column("is_custom")
        batch_op.drop_column("fps")
        batch_op.drop_column("resolution")
        batch_op.drop_column("video_url")
        batch_op.drop_column("video_file_id")
        batch_op.drop_column("stream_url")
        batch_op.drop_column("source_mode")
        batch_op.drop_column("section")
        batch_op.drop_column("floor_name")
        batch_op.drop_column("floor_id")

    # 5. Drop floors
    with op.batch_alter_table("floors", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_floors_restaurant_id"))
    op.drop_table("floors")
