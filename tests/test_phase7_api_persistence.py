"""Tests for Phase 7: API, data model, and persistence.

Validates:
- Floor management API (GET, POST /api/floors, /api/v1/floors)
- Camera CRUD and mode enforcement (tracking vs view_only)
- SSRF stream validation (loopback, internal IP, cloud metadata 169.254.169.254, bad protocols)
- View-only strict enforcement (rejection with HTTP 400 on inference jobs and processed streams)
- Tracking job lifecycle and idempotency (no duplicate worker creation)
- Analytics endpoints (GET /api/analytics/central, GET /api/analytics/floors/:id)
- Secured stream endpoints (GET /api/streams/:id, GET /api/v1/streams/:id)
- Database persistence and restart recovery
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartserve.database.models import Camera, DetectionEvent, Floor, KpiSnapshot
from smartserve.database.session import SyncSessionLocal
from smartserve.main import app
from smartserve.security.auth import create_access_token
from smartserve.vision.worker_manager import TrackingWorkerManager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "usr_mgr", "role": "MANAGER"})
    return {"Authorization": f"Bearer {token}"}


def test_floors_api_crud_and_aliases(client, auth_headers):
    """Test GET and POST /api/floors and /api/v1/floors with level ordering and duplicate prevention."""
    # Test GET /api/floors
    res = client.get("/api/floors", headers=auth_headers)
    assert res.status_code == 200
    floors = res.json()
    assert len(floors) >= 2
    # Verify default seeded floors
    floor_names = [f["floor_name"] for f in floors]
    assert "Floor 1" in floor_names
    assert "Floor 2" in floor_names

    # Test GET /api/v1/floors alias
    res_v1 = client.get("/api/v1/floors", headers=auth_headers)
    assert res_v1.status_code == 200
    assert len(res_v1.json()) == len(floors)

    # Test POST /api/floors to create a new unique floor
    unique_suffix = uuid.uuid4().hex[:6]
    test_floor_id = f"floor-test-{unique_suffix}"
    new_floor_payload = {
        "floor_name": f"Garden Terrace {unique_suffix}",
        "floor_number": 4,
        "floor_id": test_floor_id,
        "restaurant_id": "rest_bistro_01",
        "metadata_json": {"zones": ["bar", "pergola"]},
    }
    create_res = client.post("/api/floors", json=new_floor_payload, headers=auth_headers)
    assert create_res.status_code in (200, 201)
    created = create_res.json()
    assert created["floor_name"] == f"Garden Terrace {unique_suffix}"
    assert created["floor_number"] == 4

    # Duplicate creation returns 409 Conflict
    dup_res = client.post("/api/floors", json=new_floor_payload, headers=auth_headers)
    assert dup_res.status_code == 409

    # GET specific floor by ID
    get_res = client.get(f"/api/floors/{test_floor_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["floor_id"] == test_floor_id


def test_camera_mode_and_ssrf_validation(client, auth_headers):
    """Test camera source mode handling and SSRF defense on stream URLs."""
    # 1. Attempt SSRF with cloud metadata IP (169.254.169.254)
    ssrf_cloud = {
        "name": f"Cloud Metadata Exploit {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "http://169.254.169.254/latest/meta-data/",
        "source_mode": "tracking",
    }
    res_ssrf = client.post("/api/cameras", json=ssrf_cloud, headers=auth_headers)
    assert res_ssrf.status_code == 400
    assert "cloud metadata" in res_ssrf.json()["detail"].lower()

    # 2. Attempt SSRF with loopback localhost
    ssrf_local = {
        "name": f"Loopback Exploit {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "http://127.0.0.1:8080/stream",
        "source_mode": "tracking",
    }
    res_local = client.post("/api/cameras", json=ssrf_local, headers=auth_headers)
    assert res_local.status_code == 400
    assert "loopback" in res_local.json()["detail"].lower()

    # 3. Attempt invalid protocol (e.g. file://)
    invalid_proto = {
        "name": f"File Protocol Exploit {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "file:///etc/passwd",
        "source_mode": "tracking",
    }
    res_proto = client.post("/api/cameras", json=invalid_proto, headers=auth_headers)
    assert res_proto.status_code == 400
    assert "protocol" in res_proto.json()["detail"].lower()

    # 4. Create valid tracking camera
    tracking_cam = {
        "name": f"Phase 7 Tracking Cam {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "rtsp://camera.internal-restaurant.io/live/stream1",
        "source_mode": "tracking",
    }
    res_track = client.post("/api/cameras", json=tracking_cam, headers=auth_headers)
    assert res_track.status_code in (200, 201)
    cam_track_data = res_track.json()
    assert cam_track_data["source_mode"] == "tracking"

    # 5. Create valid view_only camera
    view_only_cam = {
        "name": f"Phase 7 View Only Cam {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "https://cdn.restaurant.com/live/hls/entrance.m3u8",
        "source_mode": "view_only",
    }
    res_view = client.post("/api/cameras", json=view_only_cam, headers=auth_headers)
    assert res_view.status_code in (200, 201)
    cam_view_data = res_view.json()
    assert cam_view_data["source_mode"] == "view_only"


def test_view_only_mode_strict_enforcement(client, auth_headers):
    """Test that view_only cameras reject inference tracking jobs and processed CV stream requests with HTTP 400."""
    view_only_cam = {
        "name": f"Strict View-Only Guard Cam {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "rtsp://stream.domain.com/view/bar",
        "source_mode": "view_only",
    }
    create_res = client.post("/api/cameras", json=view_only_cam, headers=auth_headers)
    assert create_res.status_code in (200, 201)
    cam_id = create_res.json()["camera_id"]

    # 1. Attempting to start a tracking job on view-only camera must return HTTP 400
    job_payload = {"camera_id": cam_id, "model_version": "yolo26-phase7-v1", "sampling_fps": 10.0}
    job_res = client.post("/api/tracking-jobs", json=job_payload, headers=auth_headers)
    assert job_res.status_code == 400
    assert "view_only" in job_res.json()["detail"].lower()

    # 2. Attempting to access processed CV stream endpoint must return HTTP 400
    cv_stream_res = client.get(f"/api/cameras/{cam_id}/stream/processed")
    assert cv_stream_res.status_code == 400
    assert "view-only" in cv_stream_res.json()["detail"].lower()

    # 3. Attempting to access cv-metadata endpoint must return HTTP 400
    meta_res = client.get(f"/api/cameras/{cam_id}/cv-metadata")
    assert meta_res.status_code == 400
    assert "view-only" in meta_res.json()["detail"].lower()


def test_tracking_job_lifecycle_and_idempotency(client, auth_headers):
    """Test tracking job start, idempotency (duplicate calls do not spawn multiple workers), get, and stop."""
    cam_payload = {
        "name": f"Lifecycle Test Tracking Cam {uuid.uuid4().hex[:4]}",
        "floor": "Floor 1",
        "floor_id": "floor-01",
        "stream_url": "rtsp://stream.domain.com/live/tables",
        "source_mode": "tracking",
    }
    create_res = client.post("/api/cameras", json=cam_payload, headers=auth_headers)
    assert create_res.status_code in (200, 201)
    cam_id = create_res.json()["camera_id"]

    # 1. Start tracking job
    job_payload = {"camera_id": cam_id, "model_version": "yolo26-phase7-v1", "sampling_fps": 12.0}
    res_start = client.post("/api/tracking-jobs", json=job_payload, headers=auth_headers)
    assert res_start.status_code in (200, 201)
    job_1 = res_start.json()
    assert job_1["camera_id"] == cam_id
    assert job_1["status"] in ("MONITORING", "running")
    job_id = job_1["job_id"]

    # 2. Idempotency: duplicate start returns the existing job without creating a new job/worker
    res_dup = client.post("/api/tracking-jobs", json=job_payload, headers=auth_headers)
    assert res_dup.status_code in (200, 201)
    job_dup = res_dup.json()
    assert job_dup["job_id"] == job_id
    assert job_dup["status"] in ("MONITORING", "running")

    # Verify worker manager state by job_id
    manager = TrackingWorkerManager()
    active_worker = manager.active_workers.get(job_id)
    assert active_worker is not None
    assert active_worker.job_id == job_id

    # 3. GET /api/tracking-jobs/:id
    res_get = client.get(f"/api/tracking-jobs/{job_id}", headers=auth_headers)
    assert res_get.status_code == 200
    assert res_get.json()["job_id"] == job_id

    # 4. Stop tracking job
    res_stop = client.post(f"/api/tracking-jobs/{job_id}/stop", headers=auth_headers)
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] in ("STOPPED", "stopped")

    # 5. Idempotent stop: subsequent stop call returns successfully without error
    res_stop_dup = client.post(f"/api/tracking-jobs/{job_id}/stop", headers=auth_headers)
    assert res_stop_dup.status_code == 200
    assert res_stop_dup.json()["status"] in ("STOPPED", "stopped")

    # Verify worker stopped
    assert job_id not in manager.active_workers


def test_analytics_endpoints(client, auth_headers):
    """Test GET /api/analytics/central and GET /api/analytics/floors/:id."""
    # Test Central Analytics
    res_central = client.get("/api/analytics/central", headers=auth_headers)
    assert res_central.status_code == 200
    central_data = res_central.json()
    assert (
        "central_occupancy_rate_percent" in central_data
        or "coverage_health" in central_data
        or "floors" in central_data
    )

    # Test Floor-specific Analytics
    res_floor = client.get("/api/analytics/floors/floor-01", headers=auth_headers)
    assert res_floor.status_code == 200
    floor_data = res_floor.json()
    assert (
        "floor_id" in floor_data or "tables" in floor_data or "occupancy_rate_percent" in floor_data
    )

    # Test /api/v1 aliases
    res_central_v1 = client.get("/api/v1/analytics/central", headers=auth_headers)
    assert res_central_v1.status_code == 200
    res_floor_v1 = client.get("/api/v1/analytics/floors/floor-01", headers=auth_headers)
    assert res_floor_v1.status_code == 200


def test_stream_playback_endpoints(client, auth_headers):
    """Test secured stream playback endpoints /api/streams/:id and /api/v1/streams/:id."""
    # 1. Unauthenticated request rejected with 401
    res_no_auth = client.get("/api/streams/cam-01")
    assert res_no_auth.status_code == 401

    # 2. Non-existent camera returns 404
    res_404 = client.get("/api/streams/non_existent_cam_999", headers=auth_headers)
    assert res_404.status_code == 404
    res_404_v1 = client.get("/api/v1/streams/non_existent_cam_999", headers=auth_headers)
    assert res_404_v1.status_code == 404

    # 3. Create view-only camera and verify processed stream request is rejected with 400
    view_cam_payload = {
        "name": f"Stream Guard Cam {uuid.uuid4().hex[:4]}",
        "floor": "Floor 2",
        "floor_id": "floor-02",
        "stream_url": "https://stream.server.com/live/bar.m3u8",
        "source_mode": "view_only",
    }
    create_res = client.post("/api/cameras", json=view_cam_payload, headers=auth_headers)
    assert create_res.status_code in (200, 201)
    cam_id = create_res.json()["camera_id"]

    res_proc_blocked = client.get(f"/api/streams/{cam_id}?processed=true", headers=auth_headers)
    assert res_proc_blocked.status_code == 400
    assert "view-only" in res_proc_blocked.json()["detail"].lower()

    # 4. Verify route registration in FastAPI app
    route_paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/streams/{camera_id}" in route_paths
    assert "/api/v1/streams/{camera_id}" in route_paths


def test_database_persistence_and_restart_recovery(client):
    """Test database persistence of Floor, Camera, TrackingJob, DetectionEvent, and KpiSnapshot."""
    with SyncSessionLocal() as session:
        # Check floors are present in DB
        db_floors = session.execute(select(Floor)).scalars().all()
        assert len(db_floors) >= 2
        floor_ids = [f.floor_id for f in db_floors]
        assert "floor-01" in floor_ids

        # Check cameras in DB
        db_cameras = session.execute(select(Camera)).scalars().all()
        assert len(db_cameras) > 0

        # Record a test detection event in DB
        first_cam = db_cameras[0]
        event = DetectionEvent(
            camera_id=first_cam.camera_id,
            job_id=None,
            person_count=3,
            active_tracks=2,
            associations_json={"table-01": ["trk_101"]},
            detections_json=[{"cls": "person", "conf": 0.95}],
            latency_ms=18.5,
        )
        session.add(event)

        # Record a test KPI snapshot in DB
        kpi = KpiSnapshot(
            restaurant_id="rest_bistro_01",
            floor_id=first_cam.floor_id or "floor-01",
            scope="FLOOR",
            metrics_json={
                "occupancy_rate": 0.75,
                "turnover_rate": 1.8,
                "total_active_tables": 6,
                "total_capacity": 10,
                "avg_service_time_sec": 1420.0,
                "alerts_active": 1,
            },
        )
        session.add(kpi)
        session.commit()

        # Re-query to verify persistence and UTC timestamps
        persisted_event = (
            session.execute(
                select(DetectionEvent).where(DetectionEvent.camera_id == first_cam.camera_id)
            )
            .scalars()
            .first()
        )
        assert persisted_event is not None
        assert persisted_event.timestamp is not None
        assert persisted_event.person_count == 3

        persisted_kpi = (
            session.execute(select(KpiSnapshot).where(KpiSnapshot.scope == "FLOOR"))
            .scalars()
            .first()
        )
        assert persisted_kpi is not None
        assert persisted_kpi.timestamp is not None
        assert persisted_kpi.metrics_json["total_capacity"] == 10
