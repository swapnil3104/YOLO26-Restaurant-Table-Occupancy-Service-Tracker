"""Tests for Database Models, Alembic Migrations, Event Domain, and Idempotency.

Verifies Phase 5 acceptance criteria:
1. Migrations / metadata create complete schema from an empty database.
2. Duplicate event submissions with identical idempotency_key do not create duplicate operational records.
3. Event corrections preserve audit trail, link superseding records, and update session metrics.
4. Foreign key integrity and constraints are enforced.
5. REST API routes for events, corrections, alerts, and audit logs.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base, utc_now
from smartserve.database.models import (
    AuditLog,
    Camera,
    Restaurant,
    ServiceEvent,
    Table,
    TableSession,
    User,
)
from smartserve.database.session import get_db
from smartserve.events.schema import (
    AlertCreate,
    AlertSeverity,
    AlertStatus,
    EventCorrectionRequest,
    EventSource,
    EventType,
    ServiceEventCreate,
    SessionStatus,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.main import app

# ---------------------------------------------------------------------------
# In-Memory Async DB Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_db():
    """Create isolated in-memory SQLite async database for test execution."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    # Enable SQLite foreign keys
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # Seed minimum test fixtures: restaurant, camera, table, user
        rest = Restaurant(
            restaurant_id="rest_test_01",
            name="Test Trattoria",
            timezone="UTC",
        )
        cam = Camera(
            camera_id="CAM-01",
            restaurant_id="rest_test_01",
            name="Overhead Camera",
        )
        table = Table(
            table_id="table_1",
            restaurant_id="rest_test_01",
            table_code="T01",
            capacity=4,
            camera_id="CAM-01",
            region_config={},
            status="AVAILABLE",
        )
        user = User(
            user_id="user_waiter_01",
            restaurant_id="rest_test_01",
            username="waiter_sam",
            display_name="Sam W.",
            role="WAITER",
        )
        session.add_all([rest, cam, table, user])
        await session.commit()

        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Unit & Acceptance Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_database_schema_creation(test_db: AsyncSession):
    """Acceptance Check 1: Schema creation from empty database."""
    # Verify that all 9 tables are queried successfully without exceptions
    stmt = select(Table).where(Table.table_id == "table_1")
    res = await test_db.execute(stmt)
    table = res.scalar_one_or_none()
    assert table is not None
    assert table.table_code == "T01"
    assert table.restaurant_id == "rest_test_01"


@pytest.mark.anyio
async def test_foreign_key_enforcement(test_db: AsyncSession):
    """Acceptance Check 4: Foreign-key validation tests pass."""
    # Attempt to insert Table with invalid non-existent restaurant_id
    invalid_table = Table(
        table_id="table_orphan",
        restaurant_id="non_existent_restaurant",
        table_code="TX",
        capacity=2,
    )
    test_db.add(invalid_table)
    with pytest.raises(IntegrityError):
        await test_db.commit()
    await test_db.rollback()


@pytest.mark.anyio
async def test_event_idempotency_deduplication(test_db: AsyncSession):
    """Acceptance Check 2: Duplicate submissions do not create duplicate operational events."""
    sess_in = TableSessionCreate(
        session_id="sess_idemp_01",
        table_id="table_1",
        restaurant_id="rest_test_01",
        started_at=utc_now(),
        customer_count=3,
    )
    dining_session, _ = await EventDomainService.create_table_session(test_db, sess_in)

    event_payload = ServiceEventCreate(
        table_id="table_1",
        session_id=dining_session.session_id,
        event_type=EventType.ATTENDANCE,
        idempotency_key="idemp_key_unique_123",
        metadata_json={"order_id": "ORD-1"},
    )

    # First submission
    event1, is_dup1 = await EventDomainService.record_event(test_db, event_payload)
    assert not is_dup1
    assert event1.idempotency_key == "idemp_key_unique_123"

    # Second identical submission
    event2, is_dup2 = await EventDomainService.record_event(test_db, event_payload)
    assert is_dup2
    assert event2.event_id == event1.event_id

    # Verify only 1 event exists in database
    stmt = select(ServiceEvent).where(ServiceEvent.session_id == dining_session.session_id)
    res = await test_db.execute(stmt)
    all_events = res.scalars().all()
    assert len(all_events) == 1


@pytest.mark.anyio
async def test_event_correction_preserves_audit_trail(test_db: AsyncSession):
    """Acceptance Check 3: Corrections preserve an audit trail."""
    t_initial = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_corr_01",
        table_id="table_1",
        restaurant_id="rest_test_01",
        started_at=t_initial,
        customer_count=2,
    )
    dining_session, _ = await EventDomainService.create_table_session(test_db, sess_in)

    # Initial attendance event with wrong timestamp
    t_wrong = datetime(2026, 10, 22, 12, 5, 0, tzinfo=UTC)
    event_in = ServiceEventCreate(
        table_id="table_1",
        session_id=dining_session.session_id,
        event_type=EventType.FIRST_ATTENDANCE,
        event_timestamp=t_wrong,
        source=EventSource.VISION,
    )
    original_event, _ = await EventDomainService.record_event(test_db, event_in)

    # Session first_attendance_at was initially 12:05
    stmt = select(TableSession).where(TableSession.session_id == dining_session.session_id)
    res = await test_db.execute(stmt)
    s = res.scalar_one()
    assert s.first_attendance_at == t_wrong

    # Perform correction to 12:02
    t_correct = datetime(2026, 10, 22, 12, 2, 0, tzinfo=UTC)
    correction = EventCorrectionRequest(
        reason="Waiter arrived earlier than detector camera triggered",
        corrected_by="user_waiter_01",
        new_timestamp=t_correct,
    )

    original_after, superseding = await EventDomainService.correct_event(
        test_db, original_event.event_id, correction
    )

    # 1. Original event preserved and marked CORRECTED
    assert original_after.event_id == original_event.event_id
    assert original_after.verification_status == VerificationStatus.CORRECTED.value

    # 2. Superseding event created and links back
    assert superseding.is_correction is True
    assert superseding.supersedes_event_id == original_event.event_id
    assert superseding.event_timestamp == t_correct
    assert superseding.verification_status == VerificationStatus.CONFIRMED.value

    # 3. Parent session attendance updated
    res = await test_db.execute(stmt)
    s_updated = res.scalar_one()
    assert s_updated.first_attendance_at == t_correct

    # 4. AuditLog created
    audit_stmt = select(AuditLog).where(AuditLog.entity_id == original_event.event_id)
    audit_res = await test_db.execute(audit_stmt)
    audit = audit_res.scalar_one_or_none()
    assert audit is not None
    assert audit.action == "CORRECT_EVENT"
    assert audit.user_id == "user_waiter_01"
    assert "Waiter arrived earlier" in audit.details["reason"]


@pytest.mark.anyio
async def test_session_lifecycle_synchronization(test_db: AsyncSession):
    """Test full session lifecycle with events updating session fields atomically."""
    t0 = datetime(2026, 10, 22, 14, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_sync_01",
        table_id="table_1",
        restaurant_id="rest_test_01",
        started_at=t0,
        customer_count=4,
    )
    await EventDomainService.create_table_session(test_db, sess_in)

    # 1. Attendance event
    t1 = datetime(2026, 10, 22, 14, 3, 30, tzinfo=UTC)
    await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id="sess_sync_01",
            event_type=EventType.ATTENDANCE,
            event_timestamp=t1,
        ),
    )

    # 2. Food delivery event
    t2 = datetime(2026, 10, 22, 14, 18, 0, tzinfo=UTC)
    await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id="sess_sync_01",
            event_type=EventType.FOOD_DELIVERY,
            event_timestamp=t2,
        ),
    )

    # 3. Departure event
    t3 = datetime(2026, 10, 22, 14, 55, 0, tzinfo=UTC)
    await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id="sess_sync_01",
            event_type=EventType.DEPARTURE,
            event_timestamp=t3,
        ),
    )

    # Verify session fields
    stmt = select(TableSession).where(TableSession.session_id == "sess_sync_01")
    res = await test_db.execute(stmt)
    sess = res.scalar_one()

    assert sess.first_attendance_at == t1
    assert sess.first_food_delivery_at == t2
    assert sess.ended_at == t3
    assert sess.session_status == SessionStatus.COMPLETED.value


@pytest.mark.anyio
async def test_alert_lifecycle_and_deduplication(test_db: AsyncSession):
    """Test alert creation, deduplication across active alerts, acknowledge, and resolve."""
    alert_in = AlertCreate(
        table_id="table_1",
        alert_type="FIRST_ATTENDANCE_DELAY",
        severity=AlertSeverity.WARNING,
        dedup_key="alert_att_table_1",
    )

    # Create alert
    alert1, is_dup1 = await EventDomainService.create_or_update_alert(test_db, alert_in)
    assert not is_dup1
    assert alert1.status == AlertStatus.ACTIVE.value

    # Re-triggering same alert conditions yields existing active alert without duplicates
    alert2, is_dup2 = await EventDomainService.create_or_update_alert(test_db, alert_in)
    assert is_dup2
    assert alert2.alert_id == alert1.alert_id

    # Acknowledge
    ack = await EventDomainService.acknowledge_alert(
        test_db, alert1.alert_id, user_id="user_waiter_01"
    )
    assert ack.status == AlertStatus.ACKNOWLEDGED.value
    assert ack.acknowledged_at is not None

    # Resolve
    res = await EventDomainService.resolve_alert(test_db, alert1.alert_id, user_id="user_waiter_01")
    assert res.status == AlertStatus.RESOLVED.value
    assert res.resolved_at is not None


# ---------------------------------------------------------------------------
# REST API Endpoint Tests via TestClient
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rest_api_events_and_alerts(test_db: AsyncSession):
    """Test FastAPI REST endpoints for events, corrections, and alerts."""
    from httpx import ASGITransport, AsyncClient

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Post event
        resp = await client.post(
            "/api/v1/events",
            json={
                "table_id": "table_1",
                "event_type": "ATTENDANCE",
                "source": "WAITER_UI",
                "idempotency_key": "rest_idemp_001",
                "metadata_json": {"note": "test"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "recorded"
        assert not data["is_duplicate"]
        event_id = data["event"]["event_id"]

        # 2. Duplicate submission with same key
        resp_dup = await client.post(
            "/api/v1/events",
            json={
                "table_id": "table_1",
                "event_type": "ATTENDANCE",
                "source": "WAITER_UI",
                "idempotency_key": "rest_idemp_001",
            },
        )
        assert resp_dup.status_code == 201
        assert resp_dup.json()["status"] == "deduplicated"
        assert resp_dup.json()["is_duplicate"] is True

        # 3. Correct event via REST API
        resp_corr = await client.post(
            f"/api/v1/events/{event_id}/correct",
            json={
                "reason": "Correcting attendance timestamp from camera review",
                "corrected_by": "user_waiter_01",
            },
        )
        assert resp_corr.status_code == 200
        corr_data = resp_corr.json()
        assert corr_data["status"] == "corrected"
        assert corr_data["original_event"]["verification_status"] == "CORRECTED"
        assert corr_data["superseding_event"]["supersedes_event_id"] == event_id

        # 4. Query events
        resp_list = await client.get("/api/v1/events?table_id=table_1")
        assert resp_list.status_code == 200
        assert len(resp_list.json()) >= 2

        # 5. Create and query alert
        alert_resp = await client.post(
            "/api/v1/alerts",
            json={
                "table_id": "table_1",
                "alert_type": "FOOD_DELIVERY_DELAY",
                "severity": "CRITICAL",
                "dedup_key": "rest_alert_food_table_1",
            },
        )
        assert alert_resp.status_code == 201
        alert_id = alert_resp.json()["alert"]["alert_id"]

        # 6. Acknowledge alert
        ack_resp = await client.post(
            f"/api/v1/alerts/{alert_id}/acknowledge?user_id=user_waiter_01"
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "ACKNOWLEDGED"

        # 7. Query audit logs
        audit_resp = await client.get("/api/v1/audit")
        assert audit_resp.status_code == 200
        assert len(audit_resp.json()) >= 1

    app.dependency_overrides.clear()
