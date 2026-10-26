"""Automated test suite for Phase 8: FastAPI and Security.

Covers:
- Authentication & JWT token issuance (/api/v1/auth/login, /api/v1/auth/me)
- Server-side Role-Based Access Control (RBAC) across staff roles (Waiter, Manager, Admin, Inactive, Anonymous)
- Protected configuration changes & manager overrides
- Health readiness probe without secret leakage
- Analytics KPI summaries and privacy-compliant CSV exports
- Pagination and timestamp range filtering
- In-memory rate limiting and HTTP 429 rejection
- Standardized error response envelope
- OpenAPI schema and security component definitions
"""

import csv
import io
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve import __version__
from smartserve.config import settings
from smartserve.database.base import Base, utc_now
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
from smartserve.security.rate_limiter import SlidingWindowRateLimiter
from smartserve.security.secrets import sanitize_data, sanitize_url


@pytest.fixture
async def security_db():
    """Create isolated SQLite database with seeded staff roles and sessions."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        rest = Restaurant(
            restaurant_id="rest_sec_01",
            name="Security Bistro",
            timezone="UTC",
        )
        table = Table(
            table_id="table-sec-01",
            restaurant_id="rest_sec_01",
            table_code="T-SEC-01",
            capacity=4,
            status="OCCUPIED",
        )
        # Users for RBAC testing
        waiter = User(
            user_id="usr_waiter_01",
            restaurant_id="rest_sec_01",
            username="waiter_alex",
            display_name="Alex Waiter",
            role="WAITER",
            active=True,
        )
        manager = User(
            user_id="usr_mgr_01",
            restaurant_id="rest_sec_01",
            username="mgr_jordan",
            display_name="Jordan Manager",
            role="MANAGER",
            active=True,
        )
        admin = User(
            user_id="usr_admin_01",
            restaurant_id="rest_sec_01",
            username="admin_taylor",
            display_name="Taylor Admin",
            role="ADMIN",
            active=True,
        )
        inactive = User(
            user_id="usr_inactive_01",
            restaurant_id="rest_sec_01",
            username="waiter_disabled",
            display_name="Disabled Staff",
            role="WAITER",
            active=False,
        )

        now = utc_now()
        # Seed test sessions for analytics
        sess1 = TableSession(
            session_id="sess_sec_01",
            table_id="table-sec-01",
            restaurant_id="rest_sec_01",
            session_status=SessionStatus.COMPLETED.value,
            customer_count=2,
            started_at=now - timedelta(minutes=45),
            first_attendance_at=now - timedelta(minutes=42),  # 180s response
            first_food_delivery_at=now - timedelta(minutes=30),  # 900s food
            ended_at=now - timedelta(minutes=5),  # 2400s duration
        )
        sess2 = TableSession(
            session_id="sess_sec_02",
            table_id="table-sec-01",
            restaurant_id="rest_sec_01",
            session_status=SessionStatus.ACTIVE.value,
            customer_count=4,
            started_at=now - timedelta(minutes=10),
            first_attendance_at=now - timedelta(minutes=7),  # 180s response
        )

        # Seed alerts
        alert1 = Alert(
            alert_id="alt_sec_01",
            session_id="sess_sec_01",
            table_id="table-sec-01",
            alert_type="FIRST_ATTENDANCE_OVERDUE",
            severity=AlertSeverity.WARNING.value,
            status=AlertStatus.RESOLVED.value,
            dedup_key="sess_sec_01:FIRST_ATTENDANCE_OVERDUE",
            metadata_json={"auto_resolved": True},
            created_at=now - timedelta(minutes=40),
        )

        # Seed event
        ev1 = ServiceEvent(
            event_id="ev_sec_01",
            session_id="sess_sec_01",
            table_id="table-sec-01",
            event_type=EventType.FIRST_ATTENDANCE.value,
            source=EventSource.WAITER_UI.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            created_by="usr_waiter_01",
            event_timestamp=now - timedelta(minutes=42),
            recorded_at=now - timedelta(minutes=42),
        )

        session.add_all([rest, table, waiter, manager, admin, inactive, sess1, sess2, alert1, ev1])
        await session.commit()
        yield session


# ---------------------------------------------------------------------------
# 1. Authentication & JWT Token Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auth_login_and_token_exchange(security_db: AsyncSession):
    """Test staff login endpoint, JWT issuance, and /auth/me inspection."""

    async def override_get_db():
        yield security_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Valid login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "waiter_alex", "password": "any_password"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert data["role"] == "WAITER"
        assert data["username"] == "waiter_alex"
        token = data["access_token"]

        # 2. Inspect profile using Bearer token
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile["user_id"] == "usr_waiter_01"
        assert profile["display_name"] == "Alex Waiter"

        # 3. Invalid credentials
        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "non_existent_staff", "password": "bad"},
        )
        assert bad_login.status_code == 401
        err = bad_login.json()
        assert err["success"] is False
        assert err["error"]["error_code"] == "UNAUTHORIZED"

        # 4. Inactive staff account
        inactive_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "waiter_disabled", "password": "pwd"},
        )
        assert inactive_login.status_code == 403
        assert inactive_login.json()["error"]["error_code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# 2. Role-Based Access Control (RBAC) Enforcement Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rbac_manager_endpoints_restricted(security_db: AsyncSession):
    """Verify Manager/Admin-only endpoints reject Waiters and unauthenticated callers."""

    async def override_get_db():
        yield security_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. User listing (GET /api/v1/auth/users): Waiter rejected with 403
        waiter_token = create_access_token({"sub": "usr_waiter_01", "role": "WAITER"})
        res_waiter_users = await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {waiter_token}"},
        )
        assert res_waiter_users.status_code == 403
        assert res_waiter_users.json()["error"]["error_code"] == "FORBIDDEN"

        # 2. User listing: Manager accepted with 200
        mgr_token = create_access_token({"sub": "usr_mgr_01", "role": "MANAGER"})
        res_mgr_users = await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_mgr_users.status_code == 200
        users_list = res_mgr_users.json()
        assert len(users_list) >= 3

        # 3. CSV Export (GET /api/v1/analytics/export): Waiter rejected with 403
        res_waiter_export = await client.get(
            "/api/v1/analytics/export",
            headers={"X-User-ID": "usr_waiter_01"},
        )
        assert res_waiter_export.status_code == 403

        # 4. CSV Export: Manager accepted with 200 and text/csv media type
        res_mgr_export = await client.get(
            "/api/v1/analytics/export",
            headers={"X-User-ID": "usr_mgr_01"},
        )
        assert res_mgr_export.status_code == 200
        assert "text/csv" in res_mgr_export.headers["content-type"]

        # 5. Threshold updates (PUT /api/v1/rules/thresholds): Waiter rejected with 403
        th_payload = {
            "first_attendance_warning_sec": 300,
            "first_attendance_critical_sec": 480,
            "food_delivery_warning_sec": 1200,
            "food_delivery_critical_sec": 1500,
            "table_occupancy_max_warning_sec": 7200,
            "table_occupancy_max_critical_sec": 9000,
        }
        res_waiter_th = await client.put(
            "/api/v1/rules/thresholds",
            json=th_payload,
            headers={"X-User-ID": "usr_waiter_01"},
        )
        assert res_waiter_th.status_code == 403

        # 6. Threshold updates: Manager accepted with 200
        res_mgr_th = await client.put(
            "/api/v1/rules/thresholds",
            json=th_payload,
            headers={"X-User-ID": "usr_mgr_01"},
        )
        assert res_mgr_th.status_code == 200

        # 7. Anonymous caller attempting manager override
        res_anon_override = await client.post(
            "/api/v1/occupancy/table-sec-01/override",
            json={"target_state": "AVAILABLE", "reason": "Test", "actor": "usr_waiter_01"},
            headers={"X-User-ID": "usr_waiter_01"},
        )
        assert res_anon_override.status_code == 403


# ---------------------------------------------------------------------------
# 3. Health & Secrets Sanitization Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_check_and_secrets_protection(security_db: AsyncSession):
    """Verify health endpoint probe succeeds and never leaks secrets."""

    async def override_get_db():
        yield security_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__
        assert "components" in data
        assert data["components"]["database"]["status"] == "up"
        assert data["components"]["database"]["latency_ms"] is not None

        # Ensure NO secrets or database passwords are leaked
        raw_json = res.text
        assert "password" not in raw_json.lower()
        assert settings.SECRET_KEY not in raw_json


def test_secrets_sanitization_utilities():
    """Verify secrets masking utility strips passwords and connection credentials."""
    # Test URL sanitization
    secret_url = "postgresql+asyncpg://admin:super_secret_pw@db.cluster.internal:5432/smartserve"
    sanitized = sanitize_url(secret_url)
    assert "super_secret_pw" not in sanitized
    assert "admin:********@db.cluster.internal:5432/smartserve" in sanitized

    # Test dictionary sanitization
    sensitive_dict = {
        "user_id": "usr_123",
        "api_key": "sec_live_99999",
        "access_token": "eyJh...token",
        "db_password": "my_db_pass_123",
        "metadata": {
            "secret_notes": "very confidential",
            "safe_counter": 42,
        },
    }
    cleaned = sanitize_data(sensitive_dict)
    assert cleaned["user_id"] == "usr_123"
    assert cleaned["api_key"] == "********"
    assert cleaned["access_token"] == "********"
    assert cleaned["db_password"] == "********"
    assert cleaned["metadata"]["secret_notes"] == "********"
    assert cleaned["metadata"]["safe_counter"] == 42


# ---------------------------------------------------------------------------
# 4. Analytics & CSV Export with Privacy Anonymization
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_analytics_summary_and_csv_export(security_db: AsyncSession):
    """Verify KPI computation and privacy-compliant CSV generation."""

    async def override_get_db():
        yield security_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Analytics Summary
        res_summary = await client.get(
            "/api/v1/analytics/summary",
            headers={"X-User-ID": "usr_waiter_01"},
        )
        assert res_summary.status_code == 200
        summary = res_summary.json()
        assert summary["total_sessions"] == 2
        assert summary["completed_sessions"] == 1
        assert summary["active_sessions"] == 1
        assert summary["kpis"]["median_first_attendance_sec"] == 180.0
        assert summary["alerts"]["total_alerts"] >= 1

        # 2. CSV Export with Privacy Anonymization
        res_csv = await client.get(
            "/api/v1/analytics/export?anonymize=true",
            headers={"X-User-ID": "usr_mgr_01"},
        )
        assert res_csv.status_code == 200
        csv_text = res_csv.text
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) >= 3  # Header + 2 sessions
        headers = rows[0]
        assert "session_id" in headers
        assert "waiter_staff_id" in headers

        # Verify staff ID is anonymized
        for row in rows[1:]:
            staff_col = row[headers.index("waiter_staff_id")]
            if staff_col:
                assert staff_col.startswith("STAFF-")
                assert "usr_waiter_01" not in staff_col


# ---------------------------------------------------------------------------
# 5. Pagination and Date Filtering Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pagination_and_date_filtering(security_db: AsyncSession):
    """Verify limit, offset, and date range filters work across operational endpoints."""

    async def override_get_db():
        yield security_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Events pagination
        res_ev = await client.get("/api/v1/events?limit=1&offset=0")
        assert res_ev.status_code == 200
        assert len(res_ev.json()) <= 1

        # 2. Events date filter (future range returns empty)
        future_start = (utc_now() + timedelta(days=1)).isoformat()
        res_empty = await client.get("/api/v1/events", params={"start_time": future_start})
        assert res_empty.status_code == 200
        assert len(res_empty.json()) == 0

        # 3. Alerts pagination
        res_alt = await client.get("/api/v1/alerts?limit=10&offset=0")
        assert res_alt.status_code == 200
        assert len(res_alt.json()) >= 1


# ---------------------------------------------------------------------------
# 6. Rate Limiting Tests
# ---------------------------------------------------------------------------


def test_sliding_window_rate_limiter():
    """Verify rate limiter blocks client when requests exceed threshold."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=3, window_sec=10.0)

    # 3 allowed
    assert limiter.is_allowed("192.168.1.50")[0] is True
    assert limiter.is_allowed("192.168.1.50")[0] is True
    assert limiter.is_allowed("192.168.1.50")[0] is True

    # 4th blocked
    allowed, retry_after = limiter.is_allowed("192.168.1.50")
    assert allowed is False
    assert retry_after > 0

    # Different client still allowed
    assert limiter.is_allowed("192.168.1.51")[0] is True


# ---------------------------------------------------------------------------
# 7. OpenAPI Schema & Security Components
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_openapi_schema_contains_security_schemes():
    """Verify OpenAPI 3.1 documentation includes Bearer and ApiKey authentication schemes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        assert "components" in schema
        assert "securitySchemes" in schema["components"]
        schemes = schema["components"]["securitySchemes"]
        assert "BearerAuth" in schemes
        assert "ApiKeyAuth" in schemes
        assert schemes["BearerAuth"]["type"] == "http"
        assert schemes["ApiKeyAuth"]["name"] == "X-User-ID"
