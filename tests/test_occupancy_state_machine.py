"""Comprehensive unit and replay tests for Table Occupancy State Machine and Sessions (Phase 4).

Follows RULES.md Sections 3, 4, 5, 8 and PRD FR-04, FR-05, FR-06.
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from smartserve.main import app
from smartserve.occupancy.manager import OccupancySessionManager
from smartserve.occupancy.schema import (
    EventSource,
    OccupancyState,
    ServiceStatus,
    StateTransitionEvent,
    TableOccupancyStatus,
    TableSession,
    VerificationStatus,
)
from smartserve.occupancy.state_machine import TableStateMachine
from smartserve.tables.schema import (
    AssociationStatus,
    Point,
    TableConfig,
    TablePolygon,
    TrackAssociation,
)
from smartserve.vision.visualizer import draw_occupancy_state_overlay


@pytest.fixture
def sample_table_config() -> TableConfig:
    return TableConfig(
        id="t-01",
        code="T-01",
        name="Window Booth",
        camera_id="CAM-01",
        capacity=4,
        section="Dining",
        polygon=TablePolygon(
            vertices=[
                Point(x=0.1, y=0.1),
                Point(x=0.4, y=0.1),
                Point(x=0.4, y=0.4),
                Point(x=0.1, y=0.4),
            ]
        ),
    )


@pytest.fixture
def temp_manager_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_path = Path(tmpdir) / "sessions.json"
        audit_path = Path(tmpdir) / "audit.jsonl"
        yield sessions_path, audit_path


# --- Task 1: Schema & Model Tests ---


def test_table_session_lifecycle():
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=45, seconds=15)

    session = TableSession(
        table_id="t-01",
        start_time=t0,
        estimated_customer_count=3,
        max_observed_customers=3,
        active_tracks=[10, 11, 12],
    )
    assert session.is_active is True
    assert session.service_status == ServiceStatus.WAITING_FOR_ATTENDANCE
    assert session.calculate_duration(t1) == 2715.0

    # Negative duration protection (Rule 8.3)
    earlier = t0 - timedelta(minutes=5)
    assert session.calculate_duration(earlier) == 0.0

    # Close session
    session.close(end_timestamp=t1, reason="Guests left")
    assert session.is_active is False
    assert session.occupancy_duration_sec == 2715.0
    assert session.metadata.get("close_reason") == "Guests left"


def test_state_transition_event_serialization():
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    evt = StateTransitionEvent(
        table_id="t-01",
        session_id="sess-123",
        from_state=OccupancyState.AVAILABLE,
        to_state=OccupancyState.POSSIBLY_OCCUPIED,
        event_timestamp=t0,
        source=EventSource.VISION,
        verification_status=VerificationStatus.CONFIRMED,
        reason="Contact detected",
        evidence={"tracks": [1, 2]},
    )
    json_str = evt.model_dump_json()
    reloaded = StateTransitionEvent.model_validate_json(json_str)
    assert reloaded.table_id == "t-01"
    assert reloaded.to_state == OccupancyState.POSSIBLY_OCCUPIED
    assert reloaded.evidence["tracks"] == [1, 2]


# --- Task 2: Deterministic State Machine Transitions (Rule 4.1) ---


def test_transient_passerby_filtered():
    """Rule 4.1: Evidence disappears before confirmation window -> reverts to AVAILABLE."""
    sm = TableStateMachine(table_id="t-01", persistence_threshold_sec=5.0)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Tick 1: Passerby enters table zone
    evts = sm.process_observation([101], t0)
    assert len(evts) == 1
    assert evts[0].from_state == OccupancyState.AVAILABLE
    assert evts[0].to_state == OccupancyState.POSSIBLY_OCCUPIED
    assert sm.current_state == OccupancyState.POSSIBLY_OCCUPIED
    assert sm.active_session is None

    # Tick 2: Passerby leaves after 2 seconds (< 5.0s persistence)
    t1 = t0 + timedelta(seconds=2.0)
    evts = sm.process_observation([], t1)
    assert len(evts) == 1
    assert evts[0].from_state == OccupancyState.POSSIBLY_OCCUPIED
    assert evts[0].to_state == OccupancyState.AVAILABLE
    assert sm.current_state == OccupancyState.AVAILABLE
    assert sm.active_session is None


def test_persistent_seating_creates_session():
    """Rule 4.1: Evidence persists for configured window -> transition to OCCUPIED and create session."""
    sm = TableStateMachine(table_id="t-01", persistence_threshold_sec=5.0)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Initial evidence
    sm.process_observation([201, 202], t0)
    assert sm.current_state == OccupancyState.POSSIBLY_OCCUPIED

    # Intermediate tick (3s elapsed)
    t1 = t0 + timedelta(seconds=3.0)
    evts = sm.process_observation([201, 202], t1)
    assert len(evts) == 0
    assert sm.current_state == OccupancyState.POSSIBLY_OCCUPIED

    # Confirmation tick (5.5s elapsed >= 5.0s)
    t2 = t0 + timedelta(seconds=5.5)
    evts = sm.process_observation([201, 202], t2)
    assert len(evts) == 1
    assert evts[0].to_state == OccupancyState.OCCUPIED
    assert sm.current_state == OccupancyState.OCCUPIED

    # Verify session
    assert sm.active_session is not None
    assert sm.active_session.is_active is True
    assert sm.active_session.table_id == "t-01"
    assert sm.active_session.start_time == t0
    assert sm.active_session.estimated_customer_count == 2


def test_occlusion_tolerance_preserves_active_session():
    """Rule 4.1 & FR-04: Brief occlusion enters POSSIBLY_VACANT; recovery returns to OCCUPIED."""
    sm = TableStateMachine(table_id="t-01", persistence_threshold_sec=5.0, vacancy_grace_sec=20.0)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Seat guests
    sm.process_observation([10], t0)
    sm.process_observation([10], t0 + timedelta(seconds=6.0))
    assert sm.current_state == OccupancyState.OCCUPIED
    session = sm.active_session
    assert session is not None

    # Track missing for 3 seconds (brief occlusion)
    t_occ = t0 + timedelta(seconds=15.0)
    evts = sm.process_observation([], t_occ)
    assert len(evts) == 1
    assert evts[0].to_state == OccupancyState.POSSIBLY_VACANT
    assert sm.current_state == OccupancyState.POSSIBLY_VACANT

    # Track reappears at 3s (< 20s grace)
    t_rec = t_occ + timedelta(seconds=3.0)
    evts = sm.process_observation([10], t_rec)
    assert len(evts) == 1
    assert evts[0].to_state == OccupancyState.OCCUPIED
    assert sm.current_state == OccupancyState.OCCUPIED

    # Active session was NOT closed or replaced
    assert sm.active_session is session
    assert sm.active_session.is_active is True


def test_vacancy_confirmation_and_session_closure():
    """Rule 4.1: Vacancy condition persists past grace window -> close session and require cleaning."""
    sm = TableStateMachine(
        table_id="t-01",
        persistence_threshold_sec=5.0,
        vacancy_grace_sec=10.0,
        stale_threshold_sec=60.0,
        require_cleaning_before_available=True,
    )
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Establish occupancy
    sm.process_observation([10], t0)
    sm.process_observation([10], t0 + timedelta(seconds=6.0))
    session = sm.active_session

    # Guests leave
    t_leave = t0 + timedelta(seconds=40.0)
    sm.process_observation([], t_leave)
    assert sm.current_state == OccupancyState.POSSIBLY_VACANT

    # Grace window expires (11.0s >= 10.0s grace)
    t_expired = t_leave + timedelta(seconds=11.0)
    evts = sm.process_observation([], t_expired)
    assert len(evts) == 1
    assert evts[0].to_state == OccupancyState.CLEANING_REQUIRED
    assert sm.current_state == OccupancyState.CLEANING_REQUIRED

    # Session closed with accurate duration (40s - 0s = 40s)
    assert session.is_active is False
    assert session.end_time == t_leave
    assert session.occupancy_duration_sec == 40.0


def test_staff_marks_cleaned_returns_to_available():
    sm = TableStateMachine(table_id="t-01", initial_state=OccupancyState.CLEANING_REQUIRED)
    evt = sm.mark_cleaned(actor="staff_alex", reason="Wiped and sanitized")
    assert sm.current_state == OccupancyState.AVAILABLE
    assert evt.from_state == OccupancyState.CLEANING_REQUIRED
    assert evt.to_state == OccupancyState.AVAILABLE
    assert evt.actor == "staff_alex"


def test_camera_outage_preserves_state_without_vacating():
    """Rule 2.5 & 4.3: Missing camera frames or camera outage must NOT vacate tables."""
    sm = TableStateMachine(table_id="t-01", stale_threshold_sec=30.0)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Seat table
    sm.process_observation([1], t0)
    sm.process_observation([1], t0 + timedelta(seconds=6.0))
    assert sm.current_state == OccupancyState.OCCUPIED

    # Camera failure signal (healthy = False)
    t_fail = t0 + timedelta(seconds=15.0)
    evts = sm.process_observation([], t_fail, camera_healthy=False)
    assert len(evts) == 0
    assert sm.current_state == OccupancyState.OCCUPIED
    assert sm.is_stale is True
    assert sm.active_session.is_active is True

    # Camera feed gap > 30 seconds
    t_stale = t_fail + timedelta(seconds=45.0)
    evts = sm.process_observation([], t_stale, camera_healthy=True)
    assert len(evts) == 0
    assert sm.current_state == OccupancyState.OCCUPIED
    assert sm.is_stale is True


def test_track_deduplication_and_count_smoothing():
    """Rule 5.5: Deduplicate tracks in same frame; smooth count jitter with median window."""
    sm = TableStateMachine(table_id="t-01", count_smoothing_window=3)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    # Frame with duplicate track IDs: [5, 5, 6, 5] -> unique count = 2
    sm.process_observation([5, 5, 6, 5], t0)
    assert sm._current_track_ids == [5, 6]
    assert sm.estimated_customer_count == 2

    # Single-frame flicker: [5, 6, 7, 8, 9] (spike to 5) then back to 2
    sm.process_observation([5, 6, 7, 8, 9], t0 + timedelta(seconds=1.0))
    sm.process_observation([5, 6], t0 + timedelta(seconds=2.0))
    # Median of [2, 5, 2] is 2
    assert sm.estimated_customer_count == 2


def test_manager_manual_override_and_audit():
    sm = TableStateMachine(table_id="t-01", initial_state=OccupancyState.AVAILABLE)
    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    evt = sm.override_state(
        target_state=OccupancyState.OUT_OF_SERVICE,
        actor="manager_eve",
        reason="Broken table leg",
        timestamp=t0,
    )
    assert sm.current_state == OccupancyState.OUT_OF_SERVICE
    assert evt.from_state == OccupancyState.AVAILABLE
    assert evt.to_state == OccupancyState.OUT_OF_SERVICE
    assert evt.actor == "manager_eve"
    assert evt.verification_status == VerificationStatus.CORRECTED


# --- Task 3: OccupancySessionManager & Persistence Recovery ---


def test_manager_process_associations_and_audit_log(temp_manager_files):
    sessions_path, audit_path = temp_manager_files
    mgr = OccupancySessionManager(
        sessions_path=str(sessions_path),
        audit_path=str(audit_path),
        persistence_threshold_sec=3.0,
        vacancy_grace_sec=5.0,
    )
    mgr.register_table("T-01")

    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    assocs = [
        TrackAssociation(
            track_id=1,
            table_id="T-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.2, 0.2),
        ),
        TrackAssociation(
            track_id=2,
            table_id="T-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.3, 0.3),
        ),
    ]

    # Frame 1: Evidence starts
    evts1 = mgr.process_associations(assocs, t0)
    assert len(evts1) == 1
    assert evts1[0].to_state == OccupancyState.POSSIBLY_OCCUPIED

    # Frame 2: Evidence persists past 3.0s -> OCCUPIED
    t1 = t0 + timedelta(seconds=3.5)
    evts2 = mgr.process_associations(assocs, t1)
    assert len(evts2) == 1
    assert evts2[0].to_state == OccupancyState.OCCUPIED

    # Check status
    status = mgr.get_table_status("T-01")
    assert status.current_state == OccupancyState.OCCUPIED
    assert status.active_session is not None
    assert status.active_session.estimated_customer_count == 2

    # Audit log check
    audit_events = mgr.get_audit_log("T-01")
    assert len(audit_events) == 2


def test_manager_persistence_and_restart_recovery(temp_manager_files):
    sessions_path, audit_path = temp_manager_files

    t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    mgr1 = OccupancySessionManager(
        sessions_path=str(sessions_path),
        audit_path=str(audit_path),
        persistence_threshold_sec=2.0,
    )
    mgr1.register_table("T-01")

    # Seat guests at T-01
    assocs = [
        TrackAssociation(
            track_id=1,
            table_id="T-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.2, 0.2),
        )
    ]
    mgr1.process_associations(assocs, t0)
    mgr1.process_associations(assocs, t0 + timedelta(seconds=2.5))
    orig_session = mgr1.get_active_session("T-01")
    assert orig_session is not None
    mgr1.save_persisted_state()

    # Restart: instantiate fresh manager pointing to same disk files
    mgr2 = OccupancySessionManager(
        sessions_path=str(sessions_path),
        audit_path=str(audit_path),
    )
    restored_status = mgr2.get_table_status("T-01")
    assert restored_status is not None
    assert restored_status.current_state == OccupancyState.OCCUPIED
    assert restored_status.active_session is not None
    assert restored_status.active_session.session_id == orig_session.session_id
    assert restored_status.active_session.start_time == orig_session.start_time


# --- Task 4: Visualizer Overlay Test ---


def test_draw_occupancy_state_overlay(sample_table_config):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    status = TableOccupancyStatus(
        table_id="t-01",
        current_state=OccupancyState.OCCUPIED,
        estimated_customer_count=3,
        last_state_change=datetime.now(UTC),
        active_session=TableSession(
            table_id="t-01",
            start_time=datetime.now(UTC) - timedelta(minutes=10),
            estimated_customer_count=3,
        ),
    )
    statuses = {"t-01": status}
    rendered = draw_occupancy_state_overlay(
        frame=frame,
        tables=[sample_table_config],
        occupancy_statuses=statuses,
        camera_id="CAM-01",
        fps=5.0,
    )
    assert isinstance(rendered, np.ndarray)
    assert rendered.shape == (720, 1280, 3)


# --- Task 5: REST API Integration Tests ---


@pytest.mark.anyio
async def test_occupancy_api_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. First ensure table exists in layout
        table_payload = {
            "id": "t-api-01",
            "code": "T-API-01",
            "name": "API Test Table",
            "camera_id": "CAM-01",
            "capacity": 4,
            "section": "Main",
            "polygon": {
                "vertices": [
                    {"x": 0.1, "y": 0.1},
                    {"x": 0.3, "y": 0.1},
                    {"x": 0.3, "y": 0.3},
                    {"x": 0.1, "y": 0.3},
                ]
            },
        }
        await client.post("/api/v1/tables", json=table_payload)

        # 2. Query occupancy list
        resp = await client.get("/api/v1/occupancy")
        assert resp.status_code == 200
        data = resp.json()
        assert "t-api-01" in data

        # 3. Manager override table state to OCCUPIED
        override_payload = {
            "target_state": "OCCUPIED",
            "reason": "Walk-in party seated manually by host",
            "actor": "manager_alice",
            "customer_count": 3,
        }
        resp = await client.post("/api/v1/occupancy/t-api-01/override", json=override_payload)
        assert resp.status_code == 200
        evt = resp.json()
        assert evt["to_state"] == "OCCUPIED"
        assert evt["actor"] == "manager_alice"

        # 4. Check table status has active session
        resp = await client.get("/api/v1/occupancy/t-api-01")
        assert resp.status_code == 200
        t_data = resp.json()
        assert t_data["current_state"] == "OCCUPIED"
        assert t_data["estimated_customer_count"] == 3
        assert t_data["active_session"] is not None

        # 5. Customer count update
        count_payload = {
            "customer_count": 4,
            "reason": "Late arrival joined party",
            "actor": "waiter_bob",
        }
        resp = await client.post("/api/v1/occupancy/t-api-01/count", json=count_payload)
        assert resp.status_code == 200
        assert resp.json()["customer_count"] == 4

        # 6. Override to CLEANING_REQUIRED
        resp = await client.post(
            "/api/v1/occupancy/t-api-01/override",
            json={
                "target_state": "CLEANING_REQUIRED",
                "reason": "Party left and paid",
                "actor": "waiter_bob",
            },
        )
        assert resp.status_code == 200

        # 7. Staff marks cleaned
        resp = await client.post(
            "/api/v1/occupancy/t-api-01/cleaned",
            json={"actor": "busser_sam", "reason": "Bussed and sanitized"},
        )
        assert resp.status_code == 200
        assert resp.json()["to_state"] == "AVAILABLE"

        # 8. Query sessions history
        resp = await client.get("/api/v1/occupancy/sessions?table_id=t-api-01")
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) >= 1
        assert sessions[0]["occupancy_duration_sec"] is not None

        # 9. Query audit log
        resp = await client.get("/api/v1/occupancy/audit?table_id=t-api-01")
        assert resp.status_code == 200
        audit = resp.json()
        assert len(audit) >= 3
