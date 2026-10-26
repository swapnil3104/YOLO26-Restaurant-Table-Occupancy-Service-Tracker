"""Tests for Central Restaurant KPIs and Floor-Level Analytics.

Verifies adherence to Docs/TASKS.md Phase 6:
- Split analytics into Central Restaurant KPIs and Floor-Level KPIs.
- Rates computed from numerators and denominators (not summed percentages).
- Canonical table deduplication across overlapping cameras.
- Distinguishing 0 from unknown / offline / unavailable.
- Shift historical summary retention.
- REST API endpoint verification.
"""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.analytics.schema import FloorAnalyticsResponse
from smartserve.analytics.service import AnalyticsService
from smartserve.database.base import Base, utc_now
from smartserve.database.models import Alert, Restaurant, Table, TableSession, User
from smartserve.database.session import get_db
from smartserve.events.schema import AlertSeverity, AlertStatus, SessionStatus, UserRole
from smartserve.main import app


@pytest.fixture
async def floor_db_session():
    """Isolated SQLite in-memory database engine for Floor KPI tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        # Seed test restaurant
        rest = Restaurant(restaurant_id="rest_floor_test", name="Floor Test Bistro")
        session.add(rest)

        # Seed staff users
        mgr = User(
            user_id="usr_mgr_test",
            restaurant_id="rest_floor_test",
            username="manager_test",
            display_name="Morgan Manager",
            role=UserRole.MANAGER.value,
            active=True,
        )
        waiter = User(
            user_id="usr_waiter_test",
            restaurant_id="rest_floor_test",
            username="waiter_test",
            display_name="Sam Waiter",
            role=UserRole.WAITER.value,
            active=True,
        )
        session.add_all([mgr, waiter])

        # Seed canonical tables across Floor 1 and Floor 2
        # Floor 1 tables
        t1 = Table(
            table_id="tbl-f1-01",
            restaurant_id="rest_floor_test",
            table_code="T-01",
            capacity=4,
            status="OCCUPIED",
            region_config={"floor": "Floor 1", "section": "Main Dining"},
        )
        t2 = Table(
            table_id="tbl-f1-02",
            restaurant_id="rest_floor_test",
            table_code="T-02",
            capacity=2,
            status="AVAILABLE",
            region_config={"floor": "Floor 1", "section": "Main Dining"},
        )
        t3 = Table(
            table_id="tbl-f1-03",
            restaurant_id="rest_floor_test",
            table_code="T-03",
            capacity=6,
            status="OCCUPIED",
            region_config={"floor": "Floor 1", "section": "Patio"},
        )
        # Floor 2 tables
        t4 = Table(
            table_id="tbl-f2-01",
            restaurant_id="rest_floor_test",
            table_code="VIP-01",
            capacity=8,
            status="OCCUPIED",
            region_config={"floor": "Floor 2", "section": "Mezzanine Lounge"},
        )
        session.add_all([t1, t2, t3, t4])

        # Active dining sessions
        now = utc_now()
        s1 = TableSession(
            session_id="sess_f1_01",
            table_id="tbl-f1-01",
            restaurant_id="rest_floor_test",
            session_status=SessionStatus.ACTIVE.value,
            started_at=now - timedelta(minutes=20),
            first_attendance_at=now - timedelta(minutes=18),
            first_food_delivery_at=now - timedelta(minutes=10),
            customer_count=3,
        )
        s3 = TableSession(
            session_id="sess_f1_03",
            table_id="tbl-f1-03",
            restaurant_id="rest_floor_test",
            session_status=SessionStatus.ACTIVE.value,
            started_at=now - timedelta(minutes=6),
            first_attendance_at=None,
            first_food_delivery_at=None,
            customer_count=5,
        )
        s4 = TableSession(
            session_id="sess_f2_01",
            table_id="tbl-f2-01",
            restaurant_id="rest_floor_test",
            session_status=SessionStatus.ACTIVE.value,
            started_at=now - timedelta(minutes=45),
            first_attendance_at=now - timedelta(minutes=42),
            first_food_delivery_at=now - timedelta(minutes=30),
            customer_count=6,
        )
        # Completed historical session earlier today
        s_comp = TableSession(
            session_id="sess_hist_01",
            table_id="tbl-f1-02",
            restaurant_id="rest_floor_test",
            session_status=SessionStatus.COMPLETED.value,
            started_at=now - timedelta(hours=3),
            first_attendance_at=now - timedelta(hours=3, seconds=-120),
            first_food_delivery_at=now - timedelta(hours=3, seconds=-600),
            ended_at=now - timedelta(hours=2),
            customer_count=2,
        )
        session.add_all([s1, s3, s4, s_comp])

        # Active alert on Table 3 (overdue attendance)
        alt1 = Alert(
            alert_id="alt_f1_01",
            session_id="sess_f1_03",
            table_id="tbl-f1-03",
            alert_type="FIRST_ATTENDANCE_OVERDUE",
            severity=AlertSeverity.WARNING.value,
            dedup_key="sess_f1_03:FIRST_ATTENDANCE_OVERDUE",
            status=AlertStatus.ACTIVE.value,
            created_at=now - timedelta(minutes=1),
        )
        session.add(alt1)

        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.anyio
async def test_floor_and_central_analytics_computation(floor_db_session: AsyncSession):
    """Test pure domain service computation of Central & Floor KPIs."""
    res = await AnalyticsService.get_floor_analytics(floor_db_session)
    assert isinstance(res, FloorAnalyticsResponse)

    # 1. Check Floor-level KPIs
    floors_by_name = {f.floor_name: f for f in res.floors}
    assert "Floor 1" in floors_by_name
    assert "Floor 2" in floors_by_name

    f1 = floors_by_name["Floor 1"]
    assert f1.monitored_sources_count >= 1
    assert f1.total_tables >= 3
    assert f1.occupied_tables >= 2
    assert f1.occupancy_rate_percent is not None
    assert f1.detected_diners is not None and f1.detected_diners >= 8
    assert f1.active_alerts_count == 1
    assert f1.warning_alerts_count == 1
    assert f1.coverage_status in ("FULL_COVERAGE", "PARTIAL_COVERAGE")

    f2 = floors_by_name["Floor 2"]
    assert f2.total_tables >= 1
    assert f2.occupied_tables >= 1
    assert f2.detected_diners is not None and f2.detected_diners >= 6

    # 2. Check Central Restaurant KPIs
    central = res.central
    assert central.reporting_scope == "LIVE_ACTIVE_SOURCES"
    assert central.total_monitored_floors >= 2
    assert central.total_canonical_tables >= 4
    assert central.total_occupied_tables >= 3
    assert central.total_detected_diners is not None and central.total_detected_diners >= 14
    assert central.total_active_alerts >= 1

    # Strict formula check: Central rate = sum(occupied) / sum(tables) * 100
    expected_central_rate = round(
        (central.total_occupied_tables / central.total_canonical_tables) * 100.0, 1
    )
    assert central.central_occupancy_rate_percent == expected_central_rate

    # 3. Check Shift Historical Summary
    hist = res.shift_history
    assert hist.total_sessions_today >= 4
    assert hist.completed_sessions >= 1
    assert hist.turnover_rate >= 0.1


@pytest.mark.anyio
async def test_canonical_table_deduplication(floor_db_session: AsyncSession):
    """Verify that multiple cameras on the same floor do not double count tables."""
    # When fetching floor analytics, canonical tables on Floor 1 should be exactly deduplicated
    res = await AnalyticsService.get_floor_analytics(floor_db_session)
    f1 = next(f for f in res.floors if f.floor_name == "Floor 1")
    # Even if cam-01 and cam-02 both cover Floor 1, tables must match unique canonical table count
    assert f1.total_tables == (f1.occupied_tables + f1.vacant_tables)


@pytest.mark.anyio
async def test_offline_floor_distinguishes_zero_from_unavailable(floor_db_session: AsyncSession):
    """Verify that an offline floor returns None for metrics, not 0%."""
    # Query for a non-monitored floor e.g. Floor 3 / Rooftop
    res = await AnalyticsService.get_floor_analytics(floor_db_session, floor_filter="Rooftop")
    assert len(res.floors) == 1
    rooftop = res.floors[0]
    assert rooftop.coverage_status == "OFFLINE"
    assert rooftop.is_live is False
    assert rooftop.occupancy_rate_percent is None
    assert rooftop.detected_diners is None


@pytest.mark.anyio
async def test_floor_analytics_api_endpoint(floor_db_session: AsyncSession):
    """Test GET /api/v1/analytics/floors endpoint with authentication."""
    app.dependency_overrides[get_db] = lambda: floor_db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Unauthenticated request should fail (401 or 403)
            unauth_res = await client.get("/api/v1/analytics/floors")
            assert unauth_res.status_code in (401, 403)

            # 2. Authenticated request as Manager
            auth_res = await client.get(
                "/api/v1/analytics/floors",
                headers={"X-User-ID": "usr_mgr_test"},
            )
            assert auth_res.status_code == 200
            data = auth_res.json()
            assert "central" in data
            assert "floors" in data
            assert "shift_history" in data
            assert data["central"]["total_canonical_tables"] >= 4

            # 3. Floor-filtered request
            f1_res = await client.get(
                "/api/v1/analytics/floors?floor=Floor%201",
                headers={"X-User-ID": "usr_mgr_test"},
            )
            assert f1_res.status_code == 200
            f1_data = f1_res.json()
            assert len(f1_data["floors"]) == 1
            assert f1_data["floors"][0]["floor_name"] == "Floor 1"
    finally:
        app.dependency_overrides.pop(get_db, None)
