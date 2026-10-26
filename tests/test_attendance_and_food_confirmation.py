"""Automated test suite for Phase 7: Attendance and Food-Delivery Confirmation.

Covers:
- Waiter and manager attendance confirmation endpoints
- Food delivery confirmation endpoint with multiple batch support
- Active table session association enforcement
- Actor authentication and role-based authorization (401/403)
- Idempotency guarantees for repeated submissions
- Event rejection and audit preservation with automatic metric recalculation
- POS and KDS adapter integration
- Timeline endpoint with explicit UI copy distinguishing confirmations from AI estimations
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base, utc_now
from smartserve.database.models import Restaurant, ServiceEvent, Table, User
from smartserve.database.session import get_db
from smartserve.events.schema import (
    AttendanceConfirmationRequest,
    EventSource,
    EventType,
    FoodDeliveryConfirmationRequest,
    ServiceEventCreate,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.main import app


@pytest.fixture
async def confirmation_db():
    """Create isolated SQLite database with seeded restaurant, table, and staff users."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        rest = Restaurant(
            restaurant_id="rest_test",
            name="Test Trattoria",
            timezone="UTC",
        )
        table = Table(
            table_id="table-01",
            restaurant_id="rest_test",
            table_code="T-01",
            capacity=4,
            status="AVAILABLE",
        )
        table_inactive = Table(
            table_id="table-02",
            restaurant_id="rest_test",
            table_code="T-02",
            capacity=2,
            status="AVAILABLE",
        )
        waiter = User(
            user_id="usr_waiter",
            restaurant_id="rest_test",
            username="waiter_sam",
            display_name="Sam Waiter",
            role="WAITER",
            active=True,
        )
        manager = User(
            user_id="usr_manager",
            restaurant_id="rest_test",
            username="mgr_morgan",
            display_name="Morgan Manager",
            role="MANAGER",
            active=True,
        )
        analyst = User(
            user_id="usr_analyst",
            restaurant_id="rest_test",
            username="analyst_ana",
            display_name="Ana Analyst",
            role="ANALYST",
            active=True,
        )
        inactive_user = User(
            user_id="usr_inactive",
            restaurant_id="rest_test",
            username="waiter_inactive",
            display_name="Inactive Waiter",
            role="WAITER",
            active=False,
        )
        session.add_all([rest, table, table_inactive, waiter, manager, analyst, inactive_user])
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.anyio
async def test_waiter_attendance_confirmation_lifecycle(confirmation_db: AsyncSession):
    """Verify authorized waiter can confirm attendance for active session and resolve alerts."""
    t0 = datetime(2026, 10, 22, 18, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_attend_01",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=t0,
        customer_count=2,
    )
    dining_session, _ = await EventDomainService.create_table_session(confirmation_db, sess_in)

    # 1. Candidate vision event should not set first_attendance_at
    cand_ts = t0 + timedelta(seconds=30)
    await EventDomainService.record_event(
        confirmation_db,
        ServiceEventCreate(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=cand_ts,
            source=EventSource.VISION,
            confidence=0.6,
            verification_status=VerificationStatus.CANDIDATE,
        ),
    )
    await confirmation_db.refresh(dining_session)
    assert dining_session.first_attendance_at is None

    # 2. Authorized waiter confirms attendance
    waiter_user = await confirmation_db.get(User, "usr_waiter")
    attend_ts = t0 + timedelta(seconds=90)
    req = AttendanceConfirmationRequest(
        table_id="table-01",
        session_id=dining_session.session_id,
        event_timestamp=attend_ts,
        notes="Greeted guests",
        idempotency_key="idemp_attend_001",
    )
    event, is_dup = await EventDomainService.confirm_attendance(confirmation_db, req, waiter_user)
    assert not is_dup
    assert event.verification_status == VerificationStatus.CONFIRMED.value
    assert event.source == EventSource.WAITER_UI.value

    await confirmation_db.refresh(dining_session)
    assert dining_session.first_attendance_at == attend_ts


@pytest.mark.anyio
async def test_food_delivery_multiple_batches(confirmation_db: AsyncSession):
    """Verify multiple delivery batches in one session preserve the earliest milestone."""
    t0 = datetime(2026, 10, 22, 19, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_food_multi",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=t0,
    )
    dining_session, _ = await EventDomainService.create_table_session(confirmation_db, sess_in)
    waiter_user = await confirmation_db.get(User, "usr_waiter")

    # Batch 1: Appetizers at T+10m
    t_batch_1 = t0 + timedelta(minutes=10)
    req_1 = FoodDeliveryConfirmationRequest(
        table_id="table-01",
        session_id=dining_session.session_id,
        event_timestamp=t_batch_1,
        course="appetizers",
        batch_number=1,
        items=["Soup", "Bruschetta"],
        idempotency_key="idemp_batch_1",
    )
    ev_1, _ = await EventDomainService.confirm_food_delivery(confirmation_db, req_1, waiter_user)
    await confirmation_db.refresh(dining_session)
    assert dining_session.first_food_delivery_at == t_batch_1

    # Batch 2: Mains at T+25m
    t_batch_2 = t0 + timedelta(minutes=25)
    req_2 = FoodDeliveryConfirmationRequest(
        table_id="table-01",
        session_id=dining_session.session_id,
        event_timestamp=t_batch_2,
        course="mains",
        batch_number=2,
        items=["Steak", "Pasta"],
        idempotency_key="idemp_batch_2",
    )
    ev_2, _ = await EventDomainService.confirm_food_delivery(confirmation_db, req_2, waiter_user)
    await confirmation_db.refresh(dining_session)

    # Earliest milestone must remain batch 1!
    assert dining_session.first_food_delivery_at == t_batch_1

    # Both events must exist in database
    stmt = select(ServiceEvent).where(
        ServiceEvent.session_id == dining_session.session_id,
        ServiceEvent.event_type == EventType.FOOD_DELIVERY.value,
    )
    res = await confirmation_db.execute(stmt)
    food_events = res.scalars().all()
    assert len(food_events) == 2


@pytest.mark.anyio
async def test_rest_api_actor_authorization_and_rejections(confirmation_db: AsyncSession):
    """Verify API rejects unauthorized, non-existent, inactive, and insufficient-role users."""
    t0 = utc_now()
    sess_in = TableSessionCreate(
        session_id="sess_auth_test",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=t0,
    )
    await EventDomainService.create_table_session(confirmation_db, sess_in)

    async def override_get_db():
        yield confirmation_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Missing actor credentials -> 401 Unauthorized
        res_no_auth = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01"},
        )
        assert res_no_auth.status_code == 401

        # 2. Non-existent user -> 401 Unauthorized
        res_unknown = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01"},
            headers={"X-User-ID": "usr_ghost_unknown"},
        )
        assert res_unknown.status_code == 401

        # 3. Inactive user -> 403 Forbidden
        res_inactive = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01"},
            headers={"X-User-ID": "usr_inactive"},
        )
        assert res_inactive.status_code == 403

        # 4. Insufficient role (Analyst cannot confirm attendance) -> 403 Forbidden
        res_analyst = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01"},
            headers={"X-User-ID": "usr_analyst"},
        )
        assert res_analyst.status_code == 403

        # 5. Authorized Waiter succeeds -> 200 OK
        res_waiter = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01", "idempotency_key": "idemp_auth_01"},
            headers={"X-User-ID": "usr_waiter"},
        )
        assert res_waiter.status_code == 200
        assert res_waiter.json()["status"] == "confirmed"

        # 6. Repeated submission with same idempotency_key -> status "deduplicated"
        res_dup = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-01", "idempotency_key": "idemp_auth_01"},
            headers={"X-User-ID": "usr_waiter"},
        )
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "deduplicated"
        assert res_dup.json()["is_duplicate"] is True


@pytest.mark.anyio
async def test_table_without_active_session_rejected(confirmation_db: AsyncSession):
    """Verify attendance or delivery confirmation without an active session returns 400 Bad Request."""

    async def override_get_db():
        yield confirmation_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Table table-02 has no active session
        res = await client.post(
            "/api/v1/events/attendance",
            json={"table_id": "table-02"},
            headers={"X-User-ID": "usr_waiter"},
        )
        assert res.status_code == 400
        assert "no active dining session" in res.json()["detail"].lower()

        res_food = await client.post(
            "/api/v1/events/food-delivery",
            json={"table_id": "table-02"},
            headers={"X-User-ID": "usr_waiter"},
        )
        assert res_food.status_code == 400
        assert "no active dining session" in res_food.json()["detail"].lower()


@pytest.mark.anyio
async def test_event_rejection_workflow_and_recalculation(confirmation_db: AsyncSession):
    """Verify manager rejection of mistaken events and automatic milestone recalculation."""
    t0 = datetime(2026, 10, 22, 20, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_reject_test",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=t0,
    )
    dining_session, _ = await EventDomainService.create_table_session(confirmation_db, sess_in)

    # 1. Mistaken early attendance event at T+30s
    t_mistake = t0 + timedelta(seconds=30)
    ev_mistake, _ = await EventDomainService.record_event(
        confirmation_db,
        ServiceEventCreate(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=t_mistake,
            source=EventSource.VISION,
            verification_status=VerificationStatus.CONFIRMED,
        ),
    )

    # 2. Legitimate waiter attendance at T+3m
    t_legit = t0 + timedelta(minutes=3)
    ev_legit, _ = await EventDomainService.record_event(
        confirmation_db,
        ServiceEventCreate(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=t_legit,
            source=EventSource.WAITER_UI,
            verification_status=VerificationStatus.CONFIRMED,
        ),
    )

    await confirmation_db.refresh(dining_session)
    assert dining_session.first_attendance_at == t_mistake

    async def override_get_db():
        yield confirmation_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Waiter tries to reject -> 403 Forbidden (Only manager/admin permitted)
        res_waiter_reject = await client.post(
            f"/api/v1/events/{ev_mistake.event_id}/reject",
            json={"reason": "Not an actual attendance"},
            headers={"X-User-ID": "usr_waiter"},
        )
        assert res_waiter_reject.status_code == 403

        # Manager Morgan rejects the mistaken event -> 200 OK
        res_mgr_reject = await client.post(
            f"/api/v1/events/{ev_mistake.event_id}/reject",
            json={"reason": "Customer stood up to view art; not waiter interaction"},
            headers={"X-User-ID": "usr_manager"},
        )
        assert res_mgr_reject.status_code == 200
        assert res_mgr_reject.json()["status"] == "rejected"
        assert res_mgr_reject.json()["event"]["verification_status"] == "REJECTED"

    # Refresh session: milestone must be automatically recalculated to legitimate event!
    await confirmation_db.refresh(dining_session)
    assert dining_session.first_attendance_at == t_legit


@pytest.mark.anyio
async def test_pos_and_kds_integration_routes(confirmation_db: AsyncSession):
    """Verify POS order and KDS bump endpoints map external table codes and ingest events."""
    sess_in = TableSessionCreate(
        session_id="sess_pos_test",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=utc_now(),
    )
    await EventDomainService.create_table_session(confirmation_db, sess_in)

    async def override_get_db():
        yield confirmation_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ingest POS Order
        res_pos = await client.post(
            "/api/v1/integrations/pos/order",
            json={
                "table_code": "T-01",
                "session_id": "sess_pos_test",
                "ticket_id": "POS-1004",
                "items": ["Risotto", "Sparkling Water"],
                "total_amount": 42.0,
            },
        )
        assert res_pos.status_code == 201
        assert res_pos.json()["status"] == "recorded"
        assert res_pos.json()["event"]["table_id"] == "table-01"

        # 2. Ingest KDS Bump (Food Delivery)
        res_kds = await client.post(
            "/api/v1/integrations/kds/bump",
            json={
                "table_code": "T-01",
                "session_id": "sess_pos_test",
                "ticket_id": "KDS-88",
                "course": "mains",
                "batch_number": 1,
                "items": ["Risotto"],
            },
        )
        assert res_kds.status_code == 201
        assert res_kds.json()["status"] == "confirmed"
        assert res_kds.json()["event"]["event_type"] == "FOOD_DELIVERY"


@pytest.mark.anyio
async def test_session_timeline_presentation_and_ui_copy(confirmation_db: AsyncSession):
    """Verify session timeline endpoint returns formatted presentation badges distinguishing AI from staff."""
    t0 = datetime(2026, 10, 22, 21, 0, 0, tzinfo=UTC)
    sess_in = TableSessionCreate(
        session_id="sess_timeline_test",
        table_id="table-01",
        restaurant_id="rest_test",
        started_at=t0,
    )
    dining_session, _ = await EventDomainService.create_table_session(confirmation_db, sess_in)

    # 1. AI Vision Candidate
    await EventDomainService.record_event(
        confirmation_db,
        ServiceEventCreate(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_type=EventType.ATTENDANCE,
            event_timestamp=t0 + timedelta(seconds=60),
            source=EventSource.VISION,
            confidence=0.72,
            verification_status=VerificationStatus.CANDIDATE,
        ),
    )

    # 2. Confirmed Waiter Attendance
    waiter_user = await confirmation_db.get(User, "usr_waiter")
    req = AttendanceConfirmationRequest(
        table_id="table-01",
        session_id=dining_session.session_id,
        event_timestamp=t0 + timedelta(seconds=120),
        idempotency_key="idemp_timeline_01",
    )
    await EventDomainService.confirm_attendance(confirmation_db, req, waiter_user)

    async def override_get_db():
        yield confirmation_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/sessions/{dining_session.session_id}/timeline")
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == dining_session.session_id
        assert data["table_code"] == "T-01"
        assert len(data["items"]) == 2

        # Item 1: Vision Candidate
        item_vision = data["items"][0]
        assert item_vision["verification_status"] == "CANDIDATE"
        assert not item_vision["is_confirmed"]
        assert "AI Vision Estimate (Candidate 72% - Unconfirmed)" in item_vision["ui_badge_text"]
        assert item_vision["ui_badge_variant"] == "warning"

        # Item 2: Confirmed Waiter
        item_staff = data["items"][1]
        assert item_staff["verification_status"] == "CONFIRMED"
        assert item_staff["is_confirmed"]
        assert "Confirmed by Waiter (Sam Waiter)" in item_staff["ui_badge_text"]
        assert item_staff["ui_badge_variant"] == "success"
        assert item_staff["is_active_milestone"] is True
        assert item_staff["milestone_type"] == "FIRST_ATTENDANCE"

        # Summary checks
        assert data["summary"]["total_events"] == 2
        assert data["summary"]["confirmed_events"] == 1
        assert data["summary"]["candidate_events"] == 1
        assert data["summary"]["response_time_sec"] == 120.0
