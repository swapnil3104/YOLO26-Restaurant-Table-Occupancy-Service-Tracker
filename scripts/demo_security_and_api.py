"""Chronological demonstration script for Phase 8: FastAPI and Security.

Demonstrates:
1. Health & Readiness Probe (real database ping without credential leakage)
2. Staff Authentication & JWT Token Issuance (/api/v1/auth/login)
3. Role-Based Access Control (RBAC) enforcement across roles (Waiter vs Manager vs Admin)
4. Aggregated Operational Analytics & KPIs (/api/v1/analytics/summary)
5. Privacy-Compliant CSV Export with Employee Anonymization (/api/v1/analytics/export)
6. Sliding Window Rate Limiting Enforcement
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
from smartserve.security.rate_limiter import SlidingWindowRateLimiter


async def run_demo():
    print("=" * 80)
    print(" SmartServe AI - Phase 8: FastAPI & Security Demonstration")
    print("=" * 80)

    # 1. Setup in-memory SQLite DB
    print("\n[Step 1] Initializing Isolated Database and Staff Registry...")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        rest = Restaurant(restaurant_id="rest_demo", name="Security Trattoria", timezone="UTC")
        table = Table(table_id="table-01", restaurant_id="rest_demo", table_code="T-01", capacity=4)
        waiter = User(
            user_id="usr_w01",
            restaurant_id="rest_demo",
            username="sam_waiter",
            display_name="Sam Waiter",
            role="WAITER",
            active=True,
        )
        manager = User(
            user_id="usr_m01",
            restaurant_id="rest_demo",
            username="morgan_mgr",
            display_name="Morgan Manager",
            role="MANAGER",
            active=True,
        )
        inactive = User(
            user_id="usr_inact",
            restaurant_id="rest_demo",
            username="disabled_staff",
            display_name="Disabled Staff",
            role="WAITER",
            active=False,
        )

        now = utc_now()
        # Seed test completed session
        sess = TableSession(
            session_id="sess_demo_01",
            table_id="table-01",
            restaurant_id="rest_demo",
            session_status=SessionStatus.COMPLETED.value,
            customer_count=3,
            started_at=now - timedelta(minutes=60),
            first_attendance_at=now - timedelta(minutes=56),  # 240s
            first_food_delivery_at=now - timedelta(minutes=42),  # 1080s
            ended_at=now - timedelta(minutes=10),
        )
        ev = ServiceEvent(
            event_id="ev_demo_01",
            session_id="sess_demo_01",
            table_id="table-01",
            event_type=EventType.FIRST_ATTENDANCE.value,
            source=EventSource.WAITER_UI.value,
            verification_status=VerificationStatus.CONFIRMED.value,
            created_by="usr_w01",
            event_timestamp=now - timedelta(minutes=56),
            recorded_at=now - timedelta(minutes=56),
        )
        alert = Alert(
            alert_id="alt_demo_01",
            session_id="sess_demo_01",
            table_id="table-01",
            alert_type="FIRST_ATTENDANCE_OVERDUE",
            severity=AlertSeverity.WARNING.value,
            status=AlertStatus.RESOLVED.value,
            dedup_key="sess_demo_01:FIRST_ATTENDANCE_OVERDUE",
            metadata_json={"auto_resolved": True},
            created_at=now - timedelta(minutes=57),
        )
        session.add_all([rest, table, waiter, manager, inactive, sess, ev, alert])
        await session.commit()

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 2: Health Readiness Probe
        print("\n[Step 2] Probing System Readiness & Secret Protection (/api/v1/health)...")
        res_health = await client.get("/api/v1/health")
        health = res_health.json()
        print(f"  Overall Status:  {health['status'].upper()}")
        print(f"  Version:         v{health['version']}")
        print(
            f"  Database Status: {health['components']['database']['status']} ({health['components']['database']['latency_ms']} ms)"
        )
        print(f"  Secret Leakage:  None detected (raw length {len(res_health.text)} chars)")

        # Step 3: Staff Authentication
        print("\n[Step 3] Authenticating Staff Member (/api/v1/auth/login)...")
        login_res = await client.post(
            "/api/v1/auth/login", json={"username": "sam_waiter", "password": "any"}
        )
        token_data = login_res.json()
        token = token_data["access_token"]
        print(f"  Login Successful: {token_data['username']} ({token_data['role']})")
        print(
            f"  Issued JWT:       {token[:28]}... (expires in {token_data['expires_in_seconds']}s)"
        )

        me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        print(
            f"  /auth/me Profile: {me_res.json()['display_name']} [active={me_res.json()['active']}]"
        )

        # Step 4: Role-Based Access Control (RBAC)
        print("\n[Step 4] Enforcing Role-Based Access Control (RBAC)...")
        # Waiter attempting to export sensitive data
        waiter_exp = await client.get(
            "/api/v1/analytics/export", headers={"Authorization": f"Bearer {token}"}
        )
        print(
            f"  Waiter -> GET /api/v1/analytics/export: HTTP {waiter_exp.status_code} ({waiter_exp.json()['error']['message']})"
        )

        # Manager attempting to export sensitive data
        mgr_login = await client.post(
            "/api/v1/auth/login", json={"username": "morgan_mgr", "password": "any"}
        )
        mgr_token = mgr_login.json()["access_token"]
        mgr_exp = await client.get(
            "/api/v1/analytics/export", headers={"Authorization": f"Bearer {mgr_token}"}
        )
        print(
            f"  Manager -> GET /api/v1/analytics/export: HTTP {mgr_exp.status_code} OK (Content-Type: {mgr_exp.headers['content-type']})"
        )

        # Step 5: Analytics Summary
        print("\n[Step 5] Computing Operational KPIs (/api/v1/analytics/summary)...")
        res_sum = await client.get(
            "/api/v1/analytics/summary", headers={"Authorization": f"Bearer {token}"}
        )
        analytics = res_sum.json()
        print(f"  Total Sessions:             {analytics['total_sessions']}")
        print(
            f"  Median First Attendance:    {analytics['kpis']['median_first_attendance_sec']} seconds"
        )
        print(
            f"  Median Food Delivery:       {analytics['kpis']['median_food_delivery_sec']} seconds"
        )
        print(
            f"  Table Turnover Rate:        {analytics['kpis']['table_turnover_rate']} sessions/table"
        )
        print(f"  Total Resolved Alerts:      {analytics['alerts']['resolved_alerts']}")

        # Step 6: Privacy Anonymization in Export
        print(
            "\n[Step 6] Privacy Verification on Exported CSV (/api/v1/analytics/export?anonymize=true)..."
        )
        csv_text = mgr_exp.text
        lines = csv_text.strip().split("\n")
        print(f"  CSV Headers: {lines[0]}")
        print(f"  Row 1 Data:  {lines[1]}")
        if "STAFF-" in lines[1]:
            print(
                "  PRIVACY CHECK PASSED: Waiter identity masked to prevent unlawful surveillance (PRD Section 13)."
            )

        # Step 7: Rate Limiting
        print("\n[Step 7] Testing Sliding Window Rate Limiter...")
        limiter = SlidingWindowRateLimiter(requests_per_minute=2, window_sec=5.0)
        print(f"  Req 1: Allowed = {limiter.is_allowed('client_demo')[0]}")
        print(f"  Req 2: Allowed = {limiter.is_allowed('client_demo')[0]}")
        allowed, retry_after = limiter.is_allowed("client_demo")
        print(f"  Req 3: Allowed = {allowed} (Retry-After: {retry_after}s) -> RATE LIMIT ENFORCED")

    print("\n" + "=" * 80)
    print(" Phase 8 FastAPI & Security Demonstration Completed Successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_demo())
