import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from smartserve.main import app


@pytest.mark.anyio
async def test_list_cameras():
    """Test GET /api/v1/cameras returns registered camera feeds with stream URLs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/cameras")
        assert resp.status_code == 200
        cameras = resp.json()
        assert isinstance(cameras, list)
        assert len(cameras) >= 4
        cam_ids = [c["camera_id"] for c in cameras]
        assert "cam-01" in cam_ids
        cam1 = next(c for c in cameras if c["camera_id"] == "cam-01")
        assert cam1["status"] == "ONLINE"
        assert "/api/v1/cameras/cam-01/stream/raw" in cam1["raw_stream_url"]
        assert "/api/v1/cameras/cam-01/stream/processed" in cam1["processed_stream_url"]


@pytest.mark.anyio
async def test_get_camera_by_id():
    """Test GET /api/v1/cameras/{id} returns single camera metadata or 404 for unknown."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid camera
        resp = await client.get("/api/v1/cameras/cam-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["camera_id"] == "cam-01"
        assert data["section"] == "Main Dining"

        # Invalid camera
        resp_404 = await client.get("/api/v1/cameras/cam-999")
        assert resp_404.status_code == 404


@pytest.mark.anyio
async def test_get_camera_snapshot():
    """Test GET /api/v1/cameras/{id}/snapshot returns JPEG content."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Raw snapshot
        resp_raw = await client.get("/api/v1/cameras/cam-01/snapshot?processed=false")
        assert resp_raw.status_code == 200
        assert resp_raw.headers["content-type"] == "image/jpeg"
        assert len(resp_raw.content) > 1000

        # Processed snapshot
        resp_proc = await client.get("/api/v1/cameras/cam-01/snapshot?processed=true")
        assert resp_proc.status_code == 200
        assert resp_proc.headers["content-type"] == "image/jpeg"
        assert len(resp_proc.content) > 1000


@pytest.mark.anyio
async def test_get_camera_cv_metadata():
    """Test GET /api/v1/cameras/{id}/cv-metadata returns structured detections and table states."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/cameras/cam-01/cv-metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["camera_id"] == "cam-01"
        assert data["model"] == "YOLO26-Nano + ByteTrack"
        assert "inference_latency_ms" in data
        assert "detections" in data
        assert isinstance(data["detections"], list)
        assert len(data["detections"]) > 0
        assert "tables" in data


@pytest.mark.anyio
async def test_camera_crud_lifecycle():
    """Test creating, renaming, and deleting a CCTV camera feed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create camera
        payload = {
            "name": "Entrance CCTV Test",
            "floor": "Floor 1",
            "section": "Main Foyer",
            "source_type": "live_stream",
            "stream_url": "http://stream.local/cctv1.mjpg",
        }
        create_resp = await client.post("/api/v1/cameras", json=payload)
        assert create_resp.status_code == 201
        created = create_resp.json()
        cam_id = created["camera_id"]
        assert created["name"] == "Entrance CCTV Test"
        assert created["floor"] == "Floor 1"
        assert created["source_type"] == "live_stream"
        assert created["is_custom"] is True

        # 2. Duplicate name validation
        dup_resp = await client.post("/api/v1/cameras", json=payload)
        assert dup_resp.status_code == 400
        assert "already exists" in dup_resp.json()["detail"]

        # 3. Insecure protocol validation
        insecure_payload = {
            "name": "Malicious CCTV",
            "floor": "Floor 1",
            "section": "Kitchen",
            "source_type": "live_stream",
            "stream_url": "file:///etc/passwd",
        }
        bad_proto_resp = await client.post("/api/v1/cameras", json=insecure_payload)
        assert bad_proto_resp.status_code == 400
        assert "Unsupported or insecure stream protocol" in bad_proto_resp.json()["detail"]

        # 4. Rename / update camera
        patch_resp = await client.patch(
            f"/api/v1/cameras/{cam_id}",
            json={"name": "Front Entrance CCTV - Renamed", "floor": "Floor 2"},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["name"] == "Front Entrance CCTV - Renamed"
        assert updated["floor"] == "Floor 2"

        # 5. Delete camera
        del_resp = await client.delete(f"/api/v1/cameras/{cam_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"

        # 6. Verify gone
        get_resp = await client.get(f"/api/v1/cameras/{cam_id}")
        assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_upload_cctv_video_validation():
    """Test file upload validation including allowed extensions and empty file check."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid extension
        files = {"file": ("malicious.exe", b"binarycontent", "application/octet-stream")}
        resp_bad_ext = await client.post("/api/v1/cameras/upload", files=files)
        assert resp_bad_ext.status_code == 400
        assert "Unsupported file type" in resp_bad_ext.json()["detail"]

        # Empty file
        empty_files = {"file": ("test.mp4", b"", "video/mp4")}
        resp_empty = await client.post("/api/v1/cameras/upload", files=empty_files)
        assert resp_empty.status_code == 400
        assert "Uploaded file is empty" in resp_empty.json()["detail"]

        # Valid mock mp4 upload
        dummy_mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
        valid_files = {"file": ("recorded_cctv_feed.mp4", dummy_mp4_bytes, "video/mp4")}
        resp_valid = await client.post("/api/v1/cameras/upload", files=valid_files)
        assert resp_valid.status_code == 200
        data = resp_valid.json()
        assert data["status"] == "success"
        assert data["source_label"] == "RECORDED FOOTAGE (UPLOADED)"
        assert "cctv_" in data["filename"]


@pytest.mark.anyio
async def test_video_file_security_and_traversal():
    """Test video file retrieval and path traversal rejection."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Directory traversal attempt with URL encoded dots
        resp_traversal = await client.get(
            "/api/v1/cameras/video-file/%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        )
        assert resp_traversal.status_code in (400, 404)

        # Direct function call traversal rejection
        from smartserve.api.routes.cameras import get_video_file

        with pytest.raises(HTTPException) as exc_info:
            await get_video_file("../test.mp4")
        assert exc_info.value.status_code == 400
        assert "Invalid video filename" in exc_info.value.detail

        # Nonexistent file
        resp_404 = await client.get("/api/v1/cameras/video-file/nonexistent_sample.mp4")
        assert resp_404.status_code == 404


@pytest.mark.anyio
async def test_tracking_source_multi_floor_lifecycle():
    """Test Phase 4: multi-floor tracking source addition, pause/resume, and safe removal."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Add Floor 2 tracking feed
        payload = {
            "name": "Floor 2 VIP Tracker Test",
            "floor": "Floor 2",
            "section": "VIP Lounge",
            "source_type": "live_stream",
            "stream_url": "http://stream.local/floor2.mjpg",
        }
        res = await client.post("/api/v1/cameras", json=payload)
        assert res.status_code == 201
        data = res.json()
        cam_id = data["camera_id"]
        assert data["floor"] == "Floor 2"
        assert data["tracking_status"] == "Monitoring"
        assert data["camera_health"] == "HEALTHY"
        assert data["inference_status"] == "ACTIVE"

        # 2. Check floors summary endpoint
        floors_resp = await client.get("/api/v1/cameras/floors/summary")
        assert floors_resp.status_code == 200
        floors = floors_resp.json()
        floor_names = [f["floor"] for f in floors]
        assert "Floor 1" in floor_names
        assert "Floor 2" in floor_names

        # 3. Pause tracking source
        pause_resp = await client.post(f"/api/v1/cameras/{cam_id}/pause")
        assert pause_resp.status_code == 200
        assert pause_resp.json()["tracking_status"] == "Paused"
        assert pause_resp.json()["inference_status"] == "PAUSED"

        # 4. Resume tracking source
        resume_resp = await client.post(f"/api/v1/cameras/{cam_id}/resume")
        assert resume_resp.status_code == 200
        assert resume_resp.json()["tracking_status"] == "Monitoring"
        assert resume_resp.json()["inference_status"] == "ACTIVE"

        # 5. Remove source safely, verifying historical data is preserved
        del_resp = await client.delete(f"/api/v1/cameras/{cam_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["historical_data_preserved"] is True
