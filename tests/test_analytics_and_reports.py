"""Automated test suite for Phase 10: Analytics and Reports.

Covers:
- KPI calculation rules: mean vs. median, delay rate, data completeness, table utilization, turnover rate
- Sample size and data exclusion disclosures adhering to RULES.md Section 14
- Multi-dimensional filters: section, table_id, waiter_id, date ranges
- Multi-dimensional breakdowns: per-table matrix, staff efficiency, 24-hour dining traffic
- Server-side RBAC and staff privacy protections (PRD Section 10.3 & 13)
- Multi-format RFC 4180 CSV exports (sessions, summary, waiters)
- Consistency verification: dashboard summary metrics and exported CSV report values match exactly
"""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base
from smartserve.database.models import Alert, Restaurant, ServiceEvent, Table, TableSession, User
from smartserve.database.session import get_db
from smartserve.events.schema import (
    AlertSeverity,
    AlertStatus,
    EventSource,
    EventType,
    SessionStatus,
    VerificationStatus,
)
from smartserve.main import app
from smartserve.security.auth import create_access_token


@pytest.fixture
async def analytics_test_db():
    """Create isolated SQLite database seeded with multiple sections, tables, waiters, and sessions."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        rest = Restaurant(
            restaurant_id="rest_analytics_01",
            name="Analytics Grand Cafe",
            timezone="UTC",
        )
        session.add(rest)

        # 3 Tables across 2 Sections
        table_window = Table(
            table_id="tbl_win_01",
            restaurant_id="rest_analytics_01",
            table_code="T-WIN-1",
            capacity=2,
            region_config={"section": "Window Section"},
            status="AVAILABLE",
        )
        table_main = Table(
            table_id="tbl_main_01",
            restaurant_id="rest_analytics_01",
            table_code="T-MAIN-1",
            capacity=4,
            region_config={"section": "Main Dining"},
            status="OCCUPIED",
        )
        table_lounge = Table(
            table_id="tbl_lng_01",
            restaurant_id="rest_analytics_01",
            table_code="T-LNG-1",
            capacity=6,
            region_config={"section": "Lounge"},
            status="AVAILABLE",
        )
        session.add_all([table_window, table_main, table_lounge])

        # Staff Users
        waiter1 = User(
            user_id="usr_waiter_alice",
            restaurant_id="rest_analytics_01",
            username="alice_waiter",
            display_name="Alice Waiter",
            role="WAITER",
            active=True,
        )
        waiter2 = User(
            user_id="usr_waiter_bob",
            restaurant_id="rest_analytics_01",
            username="bob_waiter",
            display_name="Bob Waiter",
            role="WAITER",
            active=True,
        )
        manager = User(
            user_id="usr_mgr_clara",
            restaurant_id="rest_analytics_01",
            username="clara_mgr",
            display_name="Clara Manager",
            role="MANAGER",
            active=True,
        )
        admin = User(
            user_id="usr_admin_david",
            restaurant_id="rest_analytics_01",
            username="david_admin",
            display_name="David Admin",
            role="ADMIN",
            active=True,
        )
        session.add_all([waiter1, waiter2, manager, admin])

        # Base timestamp for controlled, deterministic intervals
        base_time = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

        # Session 1: Window Section, handled by Alice
        # Response: 120s (2m), Food: 600s (10m), Duration: 3000s (50m). Completed & On-time.
        s1 = TableSession(
            session_id="sess_01",
            table_id="tbl_win_01",
            restaurant_id="rest_analytics_01",
            session_status=SessionStatus.COMPLETED.value,
            customer_count=2,
            started_at=base_time,
            first_attendance_at=base_time + timedelta(seconds=120),
            first_food_delivery_at=base_time + timedelta(seconds=600),
            ended_at=base_time + timedelta(seconds=3000),
        )
        ev1 = ServiceEvent(
            event_id="ev_01",
            session_id="sess_01",
            table_id="tbl_win_01",
            event_type=EventType.FIRST_ATTENDANCE.value,
            source=EventSource.WAITER_UI.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            event_timestamp=base_time + timedelta(seconds=120),
            created_by="usr_waiter_alice",
        )

        # Session 2: Main Dining, handled by Bob
        # Response: 240s (4m -> delayed > 180s warning), Food: 1200s (20m -> delayed > 900s), Duration: 4000s. Completed.
        s2 = TableSession(
            session_id="sess_02",
            table_id="tbl_main_01",
            restaurant_id="rest_analytics_01",
            session_status=SessionStatus.COMPLETED.value,
            customer_count=4,
            started_at=base_time + timedelta(minutes=15),
            first_attendance_at=base_time + timedelta(minutes=15, seconds=240),
            first_food_delivery_at=base_time + timedelta(minutes=15, seconds=1200),
            ended_at=base_time + timedelta(minutes=15, seconds=4000),
        )
        ev2 = ServiceEvent(
            event_id="ev_02",
            session_id="sess_02",
            table_id="tbl_main_01",
            event_type=EventType.FIRST_ATTENDANCE.value,
            source=EventSource.WAITER_UI.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            event_timestamp=base_time + timedelta(minutes=15, seconds=240),
            created_by="usr_waiter_bob",
        )

        # Session 3: Lounge Section, handled by Alice
        # In-flight active session. Seated 10 min ago. Attendance: 180s (3m). Food delivery: pending (None).
        s3 = TableSession(
            session_id="sess_03",
            table_id="tbl_lng_01",
            restaurant_id="rest_analytics_01",
            session_status=SessionStatus.ACTIVE.value,
            customer_count=5,
            started_at=base_time + timedelta(hours=1),
            first_attendance_at=base_time + timedelta(hours=1, seconds=180),
            first_food_delivery_at=None,
            ended_at=None,
        )
        ev3 = ServiceEvent(
            event_id="ev_03",
            session_id="sess_03",
            table_id="tbl_lng_01",
            event_type=EventType.FIRST_ATTENDANCE.value,
            source=EventSource.WAITER_UI.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            event_timestamp=base_time + timedelta(hours=1, seconds=180),
            created_by="usr_waiter_alice",
        )

        # Session 4: Main Dining. Invalid / Negative interval session.
        # Should be excluded from standard averages per RULES.md Section 14, flagged in sample size.
        s4 = TableSession(
            session_id="sess_04_review",
            table_id="tbl_main_01",
            restaurant_id="rest_analytics_01",
            session_status=SessionStatus.NEEDS_REVIEW.value,
            customer_count=3,
            started_at=base_time + timedelta(hours=2),
            first_attendance_at=base_time + timedelta(hours=2, seconds=-60),  # Negative interval!
            first_food_delivery_at=None,
            ended_at=base_time + timedelta(hours=2, seconds=600),
        )

        session.add_all([s1, ev1, s2, ev2, s3, ev3, s4])

        # Active Alert on Session 2 (Food Delivery Delay)
        alert1 = Alert(
            alert_id="alt_01",
            table_id="tbl_main_01",
            session_id="sess_02",
            alert_type="FOOD_DELIVERY_OVERDUE",
            severity=AlertSeverity.WARNING.value,
            status=AlertStatus.ACTIVE.value,
            dedup_key="sess_02:FOOD_DELIVERY_OVERDUE",
            metadata_json={"message": "Food delivery exceeded warning threshold"},
            created_at=base_time + timedelta(minutes=30),
        )
        session.add(alert1)

        await session.commit()
        yield session


@pytest.mark.anyio
async def test_kpi_calculation_rules_and_metrics(analytics_test_db: AsyncSession):
    """Test KPI calculations, mean vs median, delay rate, data completeness, and sample sizes."""

    async def override_get_db():
        yield analytics_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = create_access_token({"sub": "usr_mgr_clara", "role": "MANAGER"})
        res = await client.get(
            "/api/v1/analytics/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()

        # 4 total sessions
        assert data["total_sessions"] == 4
        assert data["completed_sessions"] == 2
        assert data["active_sessions"] == 1

        kpis = data["kpis"]
        sample_sizes = kpis["sample_sizes"]

        # Sample Sizes (RULES.md Section 14)
        assert sample_sizes["total_sessions"] == 4
        assert (
            sample_sizes["attended_sessions"] == 3
        )  # sess_01 (120s), sess_02 (240s), sess_03 (180s)
        assert sample_sizes["food_delivered_sessions"] == 2  # sess_01 (600s), sess_02 (1200s)
        assert sample_sizes["completed_sessions"] == 2  # sess_01, sess_02
        assert sample_sizes["invalid_or_review_sessions"] == 1  # sess_04_review excluded

        # Response Time: values are [120, 180, 240]
        # Median of [120, 180, 240] = 180.0
        # Mean of [120, 180, 240] = 180.0
        assert kpis["median_first_attendance_sec"] == 180.0
        assert kpis["average_first_attendance_sec"] == 180.0

        # Food Delivery Time: values are [600, 1200]
        # Median = 900.0, Mean = 900.0
        assert kpis["median_food_delivery_sec"] == 900.0
        assert kpis["average_food_delivery_sec"] == 900.0

        # Occupancy Duration: values are [3000, 4000] for completed sessions
        # Median = 3500.0, Mean = 3500.0
        assert kpis["median_occupancy_duration_sec"] == 3500.0
        assert kpis["average_occupancy_duration_sec"] == 3500.0

        # Turnover Rate: 2 completed sessions / 3 monitored tables = 0.67
        assert kpis["table_turnover_rate"] == 0.67

        # Delay Rate: sess_02 breached attendance (>180s) & food (>900s), so 1 out of 4 sessions delayed = 25.0%
        assert kpis["delay_rate_percent"] == 25.0

        # Data Completeness: Both completed sessions (sess_01, sess_02) had both attendance & food confirmed = 100.0%
        assert kpis["data_completeness_percent"] == 100.0

        # Table Utilization: Occupied minutes = (3000 + 4000) / 60 = 116.67 min.
        assert kpis["table_utilization_percent"] > 0.0

        # Alerts summary
        assert data["alerts"]["total_alerts"] == 1
        assert data["alerts"]["active_alerts"] == 1
        assert data["alerts"]["warning_alerts"] == 1


@pytest.mark.anyio
async def test_multi_dimensional_filters(analytics_test_db: AsyncSession):
    """Test filtering by dining section, table_id, and waiter_id."""

    async def override_get_db():
        yield analytics_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = create_access_token({"sub": "usr_mgr_clara", "role": "MANAGER"})

        # 1. Section Filter: 'Window Section' (only sess_01)
        res_sec = await client.get(
            "/api/v1/analytics/summary?section=Window%20Section",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_sec.status_code == 200
        data_sec = res_sec.json()
        assert data_sec["total_sessions"] == 1
        assert data_sec["kpis"]["median_first_attendance_sec"] == 120.0
        assert data_sec["kpis"]["median_food_delivery_sec"] == 600.0

        # 2. Table Filter: 'tbl_lng_01' (only sess_03)
        res_tbl = await client.get(
            "/api/v1/analytics/summary?table_id=tbl_lng_01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_tbl.status_code == 200
        data_tbl = res_tbl.json()
        assert data_tbl["total_sessions"] == 1
        assert data_tbl["active_sessions"] == 1
        assert data_tbl["kpis"]["median_first_attendance_sec"] == 180.0
        assert data_tbl["kpis"]["median_food_delivery_sec"] is None

        # 3. Waiter Filter: 'usr_waiter_bob' (handled sess_02)
        res_waiter = await client.get(
            "/api/v1/analytics/summary?waiter_id=usr_waiter_bob",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_waiter.status_code == 200
        data_waiter = res_waiter.json()
        assert data_waiter["total_sessions"] == 1
        assert data_waiter["kpis"]["median_first_attendance_sec"] == 240.0


@pytest.mark.anyio
async def test_breakdown_reports_tables_waiters_hourly(analytics_test_db: AsyncSession):
    """Test GET /api/v1/analytics/breakdown returning table, waiter, and hourly metrics."""

    async def override_get_db():
        yield analytics_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = create_access_token({"sub": "usr_mgr_clara", "role": "MANAGER"})
        res = await client.get(
            "/api/v1/analytics/breakdown",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()

        # Check Table Performance List
        assert len(data["tables"]) == 3
        table_codes = {t["table_code"] for t in data["tables"]}
        assert "T-WIN-1" in table_codes
        assert "T-MAIN-1" in table_codes
        assert "T-LNG-1" in table_codes

        win_table = next(t for t in data["tables"] if t["table_code"] == "T-WIN-1")
        assert win_table["section"] == "Window Section"
        assert win_table["completed_sessions_count"] == 1
        assert win_table["median_occupancy_sec"] == 3000.0

        # Check Waiter Performance List
        assert len(data["waiters"]) == 2
        alice = next(w for w in data["waiters"] if w["waiter_id"] == "usr_waiter_alice")
        assert alice["staff_name"] == "Alice Waiter"
        assert alice["tables_handled"] == 2
        # Alice attended sess_01 (120s) and sess_03 (180s) -> median = 150.0
        assert alice["median_response_sec"] == 150.0
        assert alice["on_time_attendance_rate"] == 100.0  # neither breached 180s warning
        assert alice["delays_count"] == 0

        bob = next(w for w in data["waiters"] if w["waiter_id"] == "usr_waiter_bob")
        assert bob["staff_name"] == "Bob Waiter"
        assert bob["tables_handled"] == 1
        assert bob["median_response_sec"] == 240.0
        assert bob["on_time_attendance_rate"] == 0.0  # breached 180s threshold
        assert bob["delays_count"] == 1

        # Check Hourly Dining Traffic (24 hours)
        assert len(data["hourly"]) == 24
        # All sessions started at hour 12, 13, 14
        h12 = next(h for h in data["hourly"] if h["hour_of_day"] == 12)
        assert h12["session_count"] == 2  # sess_01 and sess_02


@pytest.mark.anyio
async def test_rbac_and_staff_privacy_controls(analytics_test_db: AsyncSession):
    """Test RBAC restrictions and staff privacy masking (PRD Section 10.3 & 13)."""

    async def override_get_db():
        yield analytics_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Anonymous access rejected with HTTP 401
        res_anon = await client.get("/api/v1/analytics/summary")
        assert res_anon.status_code == 401

        # 2. Waiter Alice querying Bob's individual statistics -> HTTP 403 Forbidden
        alice_token = create_access_token({"sub": "usr_waiter_alice", "role": "WAITER"})
        res_forbidden = await client.get(
            "/api/v1/analytics/summary?waiter_id=usr_waiter_bob",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_forbidden.status_code == 403
        data_err = res_forbidden.json()
        err_msg = data_err.get("detail") or data_err.get("error", {}).get("message", "")
        assert "Waiters may only query their own individual service metrics" in err_msg

        # 3. Waiter Alice querying own statistics -> Allowed HTTP 200
        res_self = await client.get(
            "/api/v1/analytics/summary?waiter_id=usr_waiter_alice",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_self.status_code == 200
        assert res_self.json()["total_sessions"] == 2

        # 4. Waiter inspecting breakdown receives masked staff IDs
        res_brk = await client.get(
            "/api/v1/analytics/breakdown",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_brk.status_code == 200
        waiters = res_brk.json()["waiters"]
        # Alice can see herself, other staff members are masked as STAFF-****
        for w in waiters:
            if w["waiter_id"] != "usr_waiter_alice":
                assert w["waiter_id"].startswith("STAFF-")

        # 5. Export endpoint is strictly restricted to Manager / Admin (HTTP 403 for Waiter)
        res_export_denied = await client.get(
            "/api/v1/analytics/export",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_export_denied.status_code == 403


@pytest.mark.anyio
async def test_csv_export_formats_and_dashboard_consistency(analytics_test_db: AsyncSession):
    """Verify CSV export formats and consistency between dashboard summary and CSV output."""

    async def override_get_db():
        yield analytics_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mgr_token = create_access_token({"sub": "usr_mgr_clara", "role": "MANAGER"})

        # 1. Export Sessions CSV
        res_sess = await client.get(
            "/api/v1/analytics/export?report_type=sessions&anonymize=true",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_sess.status_code == 200
        assert res_sess.headers["content-type"].startswith("text/csv")
        reader = csv.reader(io.StringIO(res_sess.text))
        header = next(reader)
        assert "session_id" in header
        assert "section" in header
        assert "is_delayed" in header
        assert "is_complete" in header
        assert "waiter_staff_id" in header
        rows = list(reader)
        assert len(rows) == 4
        # Verify anonymization masked the waiter ID
        waiter_ids = [
            r[header.index("waiter_staff_id")] for r in rows if r[header.index("waiter_staff_id")]
        ]
        for wid in waiter_ids:
            assert wid.startswith("STAFF-")

        # 2. Export Summary KPI CSV
        res_sum = await client.get(
            "/api/v1/analytics/export?report_type=summary",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_sum.status_code == 200
        sum_reader = csv.reader(io.StringIO(res_sum.text))
        sum_header = next(sum_reader)
        assert sum_header == ["Category", "Metric", "Value", "Unit", "Sample Size / Notes"]
        sum_rows = {r[1]: r[2] for r in sum_reader}

        # Verify values match GET /api/v1/analytics/summary exactly
        res_dash = await client.get(
            "/api/v1/analytics/summary",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        dash_data = res_dash.json()
        assert sum_rows["Total Sessions"] == str(dash_data["total_sessions"])
        assert sum_rows["Completed Sessions"] == str(dash_data["completed_sessions"])
        assert sum_rows["Median First Attendance"] == str(
            dash_data["kpis"]["median_first_attendance_sec"]
        )
        assert sum_rows["Median Food Delivery"] == str(
            dash_data["kpis"]["median_food_delivery_sec"]
        )
        assert sum_rows["Table Turnover Rate"] == str(dash_data["kpis"]["table_turnover_rate"])

        # 3. Export Waiter Performance CSV
        res_waiters = await client.get(
            "/api/v1/analytics/export?report_type=waiters&anonymize=false",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_waiters.status_code == 200
        w_reader = csv.reader(io.StringIO(res_waiters.text))
        w_header = next(w_reader)
        assert "waiter_id" in w_header
        assert "on_time_attendance_rate_percent" in w_header
        w_rows = list(w_reader)
        assert len(w_rows) == 2
        assert any("Alice Waiter" in r for r in w_rows)
        assert any("Bob Waiter" in r for r in w_rows)
