"""Unit and integration tests for service timers and rules engine conforming to RULES.md."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base
from smartserve.database.models import (
    Alert,
    Camera,
    Restaurant,
    Table,
    TableSession,
    User,
)
from smartserve.database.session import get_db
from smartserve.events.schema import (
    AlertSeverity,
    AlertStatus,
    DataQuality,
    EventCorrectionRequest,
    EventSource,
    EventType,
    ServiceEventCreate,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.main import app
from smartserve.rules.engine import RulesEngine
from smartserve.rules.thresholds import ServiceThresholds, threshold_manager
from smartserve.rules.timers import SessionTimersCalculator


@pytest.fixture
async def test_db():
    """Create isolated in-memory SQLite async database for test execution."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

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
        rest = Restaurant(
            restaurant_id="rest_01",
            name="Test Trattoria",
            timezone="UTC",
        )
        cam = Camera(
            camera_id="CAM-01",
            restaurant_id="rest_01",
            name="Overhead Camera",
        )
        table = Table(
            table_id="table_1",
            restaurant_id="rest_01",
            table_code="T01",
            capacity=4,
            camera_id="CAM-01",
            region_config={},
        )
        user = User(
            user_id="user_waiter_01",
            restaurant_id="rest_01",
            username="waiter_mario",
            display_name="Mario Rossi",
            role="WAITER",
        )
        session.add_all([rest, cam, table, user])
        await session.commit()
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_thresholds():
    """Ensure tests run with clean default thresholds."""
    default_th = ServiceThresholds(
        first_attendance_warning_sec=180.0,
        first_attendance_critical_sec=300.0,
        food_delivery_warning_sec=900.0,
        food_delivery_critical_sec=1500.0,
        no_interaction_warning_sec=600.0,
        occupancy_warning_sec=7200.0,
        camera_stale_critical_sec=30.0,
    )
    threshold_manager.update_thresholds(default_th)
    yield
    threshold_manager.update_thresholds(default_th)


# ---------------------------------------------------------------------------
# 1. Timer Math & Interval Calculations
# ---------------------------------------------------------------------------


def test_exact_interval_math():
    """Verify exact calculation of T_response, T_food, T_attendance_to_food, T_occupancy."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    t_att = t0 + timedelta(seconds=145)
    t_food = t0 + timedelta(seconds=720)
    t_end = t0 + timedelta(seconds=3600)

    metrics = SessionTimersCalculator.calculate_metrics(
        session_id="SESS-001",
        table_id="table_1",
        started_at=t0,
        ended_at=t_end,
        first_attendance_at=t_att,
        first_food_delivery_at=t_food,
        reference_time=t_end,
    )

    # First response: 145s
    assert metrics.first_response.duration_sec == 145.0
    assert metrics.first_response.is_valid is True
    assert metrics.first_response.is_negative is False

    # Food delivery: 720s
    assert metrics.food_delivery.duration_sec == 720.0
    assert metrics.food_delivery.is_valid is True

    # Attendance to food: 720 - 145 = 575s
    assert metrics.attendance_to_food.duration_sec == 575.0
    assert metrics.attendance_to_food.is_valid is True

    # Occupancy: 3600s
    assert metrics.occupancy_duration.duration_sec == 3600.0
    assert metrics.occupancy_duration.is_valid is True
    assert metrics.has_inconsistencies is False


def test_missing_event_handling_no_fabrication():
    """Verify missing milestones return None and never fabricate fallback values."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    metrics = SessionTimersCalculator.calculate_metrics(
        session_id="SESS-PENDING",
        table_id="table_1",
        started_at=t0,
        ended_at=None,
        first_attendance_at=None,
        first_food_delivery_at=None,
        reference_time=t0 + timedelta(seconds=500),
    )

    assert metrics.first_response.duration_sec is None
    assert metrics.first_response.is_valid is True
    assert metrics.food_delivery.duration_sec is None
    assert metrics.attendance_to_food.duration_sec is None
    assert metrics.occupancy_duration.duration_sec is None

    # In-progress elapsed timers are available
    assert metrics.elapsed_since_seating_sec == 500.0
    assert metrics.elapsed_since_attendance_sec is None
    assert metrics.has_inconsistencies is False


def test_negative_interval_flagging_without_clamping():
    """Verify negative intervals are flagged with reason and NOT clamped to zero (Rule 8.3)."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    t_att_before_seating = t0 - timedelta(seconds=45)

    metrics = SessionTimersCalculator.calculate_metrics(
        session_id="SESS-ANOMALY",
        table_id="table_1",
        started_at=t0,
        first_attendance_at=t_att_before_seating,
        reference_time=t0 + timedelta(seconds=100),
    )

    # Must NOT clamp to zero
    assert metrics.first_response.duration_sec == -45.0
    assert metrics.first_response.is_valid is False
    assert metrics.first_response.is_negative is True
    assert "Inconsistent interval" in metrics.first_response.anomaly_reason
    assert metrics.has_inconsistencies is True
    assert len(metrics.inconsistencies) > 0


def test_timezone_robustness():
    """Verify calculation robustness across non-UTC and UTC datetimes."""
    ist = timedelta(hours=5, minutes=30)
    t0_utc = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    # 5:30 ahead: 17:30 IST is same instant as 12:00 UTC
    # 17:33 IST is exactly 3 minutes (180s) later
    tz_offset = timezone(ist)
    t_att_offset = datetime(2026, 10, 22, 17, 33, 0, tzinfo=tz_offset)

    metrics = SessionTimersCalculator.calculate_metrics(
        session_id="SESS-TZ",
        table_id="table_1",
        started_at=t0_utc,
        first_attendance_at=t_att_offset,
    )
    assert metrics.first_response.duration_sec == 180.0
    assert metrics.first_response.is_valid is True


# ---------------------------------------------------------------------------
# 2. Threshold Boundaries & Escalation Rules
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_threshold_boundaries_and_escalation(test_db: AsyncSession):
    """Test just-before, exactly-at, deduplication, and WARNING -> CRITICAL escalation."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    session_id = "SESS-THRESH-01"

    # Seed table and session
    await EventDomainService.create_table_session(
        test_db,
        TableSessionCreate(
            session_id=session_id,
            table_id="table_1",
            restaurant_id="rest_01",
            started_at=t0,
            customer_count=2,
            data_quality=DataQuality.CONFIRMED,
        ),
    )

    stmt = select(TableSession).where(TableSession.session_id == session_id)
    session_obj = (await test_db.execute(stmt)).scalar_one()

    # 1. Just before warning threshold: 179s (warning is at 180s)
    res_179 = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=179),
    )
    assert len(res_179["actions"]["created"]) == 0
    assert len(res_179["actions"]["escalated"]) == 0

    # 2. Exactly at warning threshold: 180s -> Alert Created
    res_180 = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=180),
    )
    assert "FIRST_ATTENDANCE_OVERDUE (WARNING)" in res_180["actions"]["created"]

    # Verify alert in DB
    alert_stmt = select(Alert).where(Alert.session_id == session_id)
    alerts = (await test_db.execute(alert_stmt)).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.WARNING.value
    assert alerts[0].status == AlertStatus.ACTIVE.value

    # 3. Just after warning threshold: 181s -> Deduplicated (no new alert created)
    res_181 = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=181),
    )
    assert len(res_181["actions"]["created"]) == 0
    assert len(res_181["actions"]["escalated"]) == 0

    alerts_after_181 = (await test_db.execute(alert_stmt)).scalars().all()
    assert len(alerts_after_181) == 1  # Still exactly 1 alert!

    # 4. Critical threshold boundary: 299s (critical is at 300s) -> No escalation yet
    res_299 = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=299),
    )
    assert len(res_299["actions"]["escalated"]) == 0

    # 5. Exactly at critical threshold: 300s -> Escalated to CRITICAL in-place
    res_300 = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=300),
    )
    assert "FIRST_ATTENDANCE_OVERDUE -> CRITICAL" in res_300["actions"]["escalated"]

    # Verify still exactly 1 alert in DB, but escalated
    alerts_after_300 = (await test_db.execute(alert_stmt)).scalars().all()
    assert len(alerts_after_300) == 1
    assert alerts_after_300[0].severity == AlertSeverity.CRITICAL.value
    assert alerts_after_300[0].metadata_json.get("escalated") is True


# ---------------------------------------------------------------------------
# 3. Auto-Resolution on Event Ingestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auto_resolution_on_attendance_and_food_delivery(test_db: AsyncSession):
    """Verify confirmed events automatically resolve overdue active alerts."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    session_id = "SESS-AUTORESOLVE-01"

    await EventDomainService.create_table_session(
        test_db,
        TableSessionCreate(
            session_id=session_id,
            table_id="table_1",
            restaurant_id="rest_01",
            started_at=t0,
            customer_count=4,
        ),
    )

    sess_stmt = select(TableSession).where(TableSession.session_id == session_id)
    session_obj = (await test_db.execute(sess_stmt)).scalar_one()

    # Trigger attendance overdue alert (at 200s)
    await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=200),
    )

    att_alert_stmt = select(Alert).where(
        Alert.session_id == session_id,
        Alert.alert_type == "FIRST_ATTENDANCE_OVERDUE",
    )
    att_alert = (await test_db.execute(att_alert_stmt)).scalar_one()
    assert att_alert.status == AlertStatus.ACTIVE.value

    # Waiter confirms attendance at 210s
    t_att = t0 + timedelta(seconds=210)
    await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id=session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=t_att,
            source=EventSource.WAITER_UI,
            verification_status=VerificationStatus.CONFIRMED,
        ),
    )

    # Re-fetch alert -> should be auto-resolved
    att_alert_refreshed = (await test_db.execute(att_alert_stmt)).scalar_one()
    assert att_alert_refreshed.status == AlertStatus.RESOLVED.value
    assert att_alert_refreshed.metadata_json.get("resolution_reason") == "ATTENDANCE_CONFIRMED"

    # Now let food delivery time exceed warning threshold (950s after seating)
    await test_db.refresh(session_obj)
    res_food_eval = await RulesEngine.evaluate_session(
        session_obj=session_obj,
        db=test_db,
        reference_time=t0 + timedelta(seconds=950),
    )
    assert "FOOD_DELIVERY_OVERDUE (WARNING)" in res_food_eval["actions"]["created"]

    food_alert_stmt = select(Alert).where(
        Alert.session_id == session_id,
        Alert.alert_type == "FOOD_DELIVERY_OVERDUE",
    )
    food_alert = (await test_db.execute(food_alert_stmt)).scalar_one()
    assert food_alert.status == AlertStatus.ACTIVE.value

    # Waiter confirms food delivery at 980s
    t_food = t0 + timedelta(seconds=980)
    await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id=session_id,
            event_type=EventType.FOOD_DELIVERY,
            event_timestamp=t_food,
            source=EventSource.WAITER_UI,
            verification_status=VerificationStatus.CONFIRMED,
        ),
    )

    # Re-fetch food alert -> auto-resolved!
    food_alert_refreshed = (await test_db.execute(food_alert_stmt)).scalar_one()
    assert food_alert_refreshed.status == AlertStatus.RESOLVED.value
    assert food_alert_refreshed.metadata_json.get("resolution_reason") == "FOOD_DELIVERY_CONFIRMED"


# ---------------------------------------------------------------------------
# 4. Event Correction Recalculation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_event_correction_triggers_safe_recalculation(test_db: AsyncSession):
    """Verify event correction updates session milestones and recalculates metrics."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    session_id = "SESS-CORRECT-01"

    await EventDomainService.create_table_session(
        test_db,
        TableSessionCreate(
            session_id=session_id,
            table_id="table_1",
            restaurant_id="rest_01",
            started_at=t0,
        ),
    )

    # Ingest attendance recorded with mistaken late timestamp: 12:20 (1200s later)
    mistaken_ts = t0 + timedelta(seconds=1200)
    orig_event, _ = await EventDomainService.record_event(
        test_db,
        ServiceEventCreate(
            table_id="table_1",
            session_id=session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=mistaken_ts,
            source=EventSource.WAITER_UI,
            verification_status=VerificationStatus.CONFIRMED,
        ),
    )

    # Verify session recorded the mistaken attendance
    sess_stmt = select(TableSession).where(TableSession.session_id == session_id)
    sess = (await test_db.execute(sess_stmt)).scalar_one()
    assert sess.first_attendance_at == mistaken_ts

    # Manager corrects the timestamp to actual arrival time: 12:02 (120s later)
    actual_ts = t0 + timedelta(seconds=120)
    await EventDomainService.correct_event(
        test_db,
        orig_event.event_id,
        EventCorrectionRequest(
            reason="Correcting attendance timestamp entered with typo",
            corrected_by="user_waiter_01",
            new_timestamp=actual_ts,
        ),
    )

    # Verify parent session milestone was safely updated
    sess_after = (await test_db.execute(sess_stmt)).scalar_one()
    assert sess_after.first_attendance_at == actual_ts

    # Verify calculated timers reflect the corrected timestamp
    metrics = SessionTimersCalculator.calculate_metrics(
        session_id=sess_after.session_id,
        table_id=sess_after.table_id,
        started_at=sess_after.started_at,
        first_attendance_at=sess_after.first_attendance_at,
    )
    assert metrics.first_response.duration_sec == 120.0
    assert metrics.first_response.is_valid is True


# ---------------------------------------------------------------------------
# 5. REST API Endpoints Verification
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rules_and_timers_rest_api(test_db: AsyncSession):
    """Verify REST API routes for timers, rules evaluation, and threshold management."""
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    session_id = "SESS-API-01"

    await EventDomainService.create_table_session(
        test_db,
        TableSessionCreate(
            session_id=session_id,
            table_id="table_1",
            restaurant_id="rest_01",
            started_at=t0,
            customer_count=3,
        ),
    )

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Get session timers endpoint
        ref_time = (t0 + timedelta(seconds=120)).isoformat()
        res_timers = await ac.get(
            f"/api/v1/sessions/{session_id}/timers",
            params={"reference_time": ref_time},
        )
        assert res_timers.status_code == 200
        data_timers = res_timers.json()
        assert data_timers["session_id"] == session_id
        assert data_timers["first_response"]["duration_sec"] is None
        assert data_timers["elapsed_since_seating_sec"] == 120.0

        # 2. Trigger rules evaluation endpoint
        eval_ref = (t0 + timedelta(seconds=200)).isoformat()
        res_eval = await ac.post(
            "/api/v1/rules/evaluate",
            params={"reference_time": eval_ref},
        )
        assert res_eval.status_code == 200
        data_eval = res_eval.json()
        assert data_eval["active_sessions_count"] >= 1
        assert data_eval["alerts_created_count"] >= 1

        # 3. Get thresholds endpoint
        res_th = await ac.get("/api/v1/rules/thresholds")
        assert res_th.status_code == 200
        th_data = res_th.json()
        assert th_data["first_attendance_warning_sec"] == 180.0
        assert th_data["first_attendance_critical_sec"] == 300.0

        # 4. Update thresholds with valid payload
        th_data["first_attendance_warning_sec"] = 200.0
        th_data["first_attendance_critical_sec"] = 350.0
        res_put = await ac.put("/api/v1/rules/thresholds", json=th_data)
        assert res_put.status_code == 200
        assert res_put.json()["first_attendance_warning_sec"] == 200.0

        # 5. Update thresholds with invalid hierarchy (critical <= warning)
        th_data["first_attendance_critical_sec"] = 150.0  # Less than warning (200.0)
        res_put_invalid = await ac.put("/api/v1/rules/thresholds", json=th_data)
        assert res_put_invalid.status_code == 422

    app.dependency_overrides.clear()
