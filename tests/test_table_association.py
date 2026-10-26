"""Comprehensive unit and integration tests for Table Layout & Spatial Association (Phase 3)."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from smartserve.api.dependencies import get_layout_manager
from smartserve.main import app
from smartserve.tables.associator import (
    SpatialTableAssociator,
    compute_signed_distance,
    point_in_polygon_raycast,
)
from smartserve.tables.manager import TableLayoutManager
from smartserve.tables.schema import (
    AssociationStatus,
    Point,
    TableConfig,
    TableLayout,
    TablePolygon,
)
from smartserve.vision.interfaces import BoundingBox, Detection
from smartserve.vision.visualizer import (
    draw_spatial_association_overlay,
    draw_table_zones_overlay,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def sample_polygon() -> TablePolygon:
    """Standard rectangular polygon [0.1, 0.1] to [0.4, 0.4]."""
    return TablePolygon(
        vertices=[
            Point(x=0.1, y=0.1),
            Point(x=0.4, y=0.1),
            Point(x=0.4, y=0.4),
            Point(x=0.1, y=0.4),
        ]
    )


@pytest.fixture
def sample_tables(sample_polygon: TablePolygon) -> list[TableConfig]:
    """Pair of adjacent tables for spatial testing."""
    table1 = TableConfig(
        id="table-01",
        code="T-01",
        name="Table 1",
        camera_id="CAM-01",
        capacity=2,
        polygon=sample_polygon,
    )
    table2 = TableConfig(
        id="table-02",
        code="T-02",
        name="Table 2 (Adjacent)",
        camera_id="CAM-01",
        capacity=4,
        polygon=TablePolygon(
            vertices=[
                Point(x=0.41, y=0.1),
                Point(x=0.70, y=0.1),
                Point(x=0.70, y=0.4),
                Point(x=0.41, y=0.4),
            ]
        ),
    )
    return [table1, table2]


@pytest.fixture
def temp_layout_path(tmp_path: Path) -> Path:
    """Isolated temporary path for layout JSON persistence."""
    return tmp_path / "tables.json"


# ==============================================================================
# 1. Schema & Geometry Tests
# ==============================================================================


def test_point_boundary_validation():
    """Verify points must stay strictly within [0.0, 1.0]."""
    p = Point(x=0.5, y=0.5)
    assert p.to_tuple() == (0.5, 0.5)

    with pytest.raises(ValidationError):
        Point(x=-0.1, y=0.5)

    with pytest.raises(ValidationError):
        Point(x=0.5, y=1.2)


def test_polygon_geometry_calculations(sample_polygon: TablePolygon):
    """Verify centroid, bounding box, and shoelace area."""
    assert len(sample_polygon.vertices) == 4
    bbox = sample_polygon.bounding_box
    assert pytest.approx(bbox.x1) == 0.1
    assert pytest.approx(bbox.y1) == 0.1
    assert pytest.approx(bbox.x2) == 0.4
    assert pytest.approx(bbox.y2) == 0.4

    cx, cy = sample_polygon.centroid
    assert pytest.approx(cx) == 0.25
    assert pytest.approx(cy) == 0.25

    # Area of 0.3 x 0.3 rectangle = 0.09
    assert pytest.approx(sample_polygon.area, rel=1e-3) == 0.09


def test_polygon_minimum_vertices():
    """Verify polygons reject fewer than 3 vertices."""
    with pytest.raises(ValueError):
        TablePolygon(vertices=[Point(x=0.1, y=0.1), Point(x=0.2, y=0.2)])


def test_table_config_validation(sample_polygon: TablePolygon):
    """Verify table code normalization and capacity bounds."""
    table = TableConfig(
        id="t-1",
        code=" t-01 ",
        name="Test Table",
        camera_id="CAM-01",
        capacity=4,
        polygon=sample_polygon,
    )
    assert table.code == "T-01"

    with pytest.raises(ValueError):
        TableConfig(
            id="t-2",
            code="",
            name="No Code",
            camera_id="CAM-01",
            capacity=4,
            polygon=sample_polygon,
        )

    with pytest.raises(ValidationError):
        TableConfig(
            id="t-3",
            code="T-03",
            name="Zero Capacity",
            camera_id="CAM-01",
            capacity=0,
            polygon=sample_polygon,
        )


# ==============================================================================
# 2. Persistence & Layout Manager Tests
# ==============================================================================


def test_layout_manager_save_and_reload(temp_layout_path: Path, sample_tables: list[TableConfig]):
    """Verify configuration survives restart and disk persistence."""
    mgr1 = TableLayoutManager(file_path=temp_layout_path)
    mgr1._layout = TableLayout(tables=sample_tables)
    mgr1.save()

    assert temp_layout_path.exists()

    # Re-initialize fresh manager simulating application restart
    mgr2 = TableLayoutManager(file_path=temp_layout_path)
    loaded_tables = mgr2.list_tables()
    assert len(loaded_tables) == 2
    assert loaded_tables[0].code == "T-01"
    assert loaded_tables[1].code == "T-02"


def test_layout_manager_crud(temp_layout_path: Path, sample_polygon: TablePolygon):
    """Verify add, update, delete, and duplicate enforcement."""
    mgr = TableLayoutManager(file_path=temp_layout_path)

    new_table = TableConfig(
        id="table-x",
        code="T-X",
        name="Table X",
        camera_id="CAM-01",
        capacity=3,
        polygon=sample_polygon,
    )
    mgr.add_table(new_table)
    assert mgr.get_table("table-x") is not None
    assert mgr.get_table_by_code("T-X") is not None

    # Duplicate code rejection
    dup = TableConfig(
        id="table-y",
        code="T-X",
        name="Table Y",
        camera_id="CAM-01",
        capacity=2,
        polygon=sample_polygon,
    )
    with pytest.raises(ValueError):
        mgr.add_table(dup)

    # Update
    updated = TableConfig(
        id="table-x",
        code="T-X-NEW",
        name="Table X Updated",
        camera_id="CAM-01",
        capacity=5,
        polygon=sample_polygon,
    )
    res = mgr.update_table("table-x", updated)
    assert res.capacity == 5
    assert res.code == "T-X-NEW"

    # Delete
    deleted = mgr.delete_table("table-x")
    assert deleted is True
    assert mgr.get_table("table-x") is None


# ==============================================================================
# 3. Spatial Association & Point-In-Polygon Tests
# ==============================================================================


def test_raycast_and_signed_distance():
    """Verify point-in-polygon raycasting on inside, outside, and concave corners."""
    # L-shaped polygon
    l_poly = [
        (0.1, 0.1),
        (0.5, 0.1),
        (0.5, 0.3),
        (0.3, 0.3),
        (0.3, 0.5),
        (0.1, 0.5),
    ]
    # Inside horizontal bar
    assert point_in_polygon_raycast(0.2, 0.2, l_poly) is True
    assert compute_signed_distance(0.2, 0.2, l_poly) > 0

    # Inside vertical bar
    assert point_in_polygon_raycast(0.2, 0.4, l_poly) is True

    # In the hollow cutout outside the L
    assert point_in_polygon_raycast(0.4, 0.4, l_poly) is False
    assert compute_signed_distance(0.4, 0.4, l_poly) < 0


def test_patron_clear_association(sample_tables: list[TableConfig]):
    """Verify patron clearly seated inside table polygon is ASSOCIATED."""
    associator = SpatialTableAssociator(ambiguity_margin=0.02)

    # Box bottom-center is at (0.25, 0.30), well inside T-01 [0.1..0.4, 0.1..0.4]
    det = Detection(
        class_name="person",
        confidence=0.9,
        track_id=10,
        bbox=BoundingBox(x1=0.20, y1=0.15, x2=0.30, y2=0.30),
    )

    assoc = associator.associate_detection(det, sample_tables)
    assert assoc.status == AssociationStatus.ASSOCIATED
    assert assoc.table_id == "table-01"
    assert assoc.table_code == "T-01"
    assert assoc.track_id == 10
    assert assoc.confidence > 0.7


def test_patron_unassigned_in_aisle(sample_tables: list[TableConfig]):
    """Verify patron in aisle far outside tables is UNASSIGNED."""
    associator = SpatialTableAssociator(ambiguity_margin=0.02)

    # Bottom-center is at (0.85, 0.85), far outside all tables
    det = Detection(
        class_name="person",
        confidence=0.95,
        track_id=20,
        bbox=BoundingBox(x1=0.80, y1=0.70, x2=0.90, y2=0.85),
    )

    assoc = associator.associate_detection(det, sample_tables)
    assert assoc.status == AssociationStatus.UNASSIGNED
    assert assoc.table_id is None


def test_patron_ambiguous_boundary(sample_tables: list[TableConfig]):
    """Verify patron standing directly on the seam between T-01 and T-02 is AMBIGUOUS."""
    associator = SpatialTableAssociator(ambiguity_margin=0.02)

    # T-01 ends at x=0.40, T-02 begins at x=0.41.
    # Bottom-center at x=0.405, y=0.25 is right in the 0.01 seam.
    det = Detection(
        class_name="person",
        confidence=0.88,
        track_id=30,
        bbox=BoundingBox(x1=0.36, y1=0.15, x2=0.45, y2=0.25),
    )

    assoc = associator.associate_detection(det, sample_tables)
    assert assoc.status == AssociationStatus.AMBIGUOUS
    assert assoc.table_id is None
    assert "T-01" in assoc.competing_tables
    assert "T-02" in assoc.competing_tables


def test_overlapping_tables_ambiguity():
    """Verify overlapping table polygons yield AMBIGUOUS status."""
    t1 = TableConfig(
        id="t-1",
        code="T-1",
        name="Table 1",
        camera_id="CAM-01",
        polygon=TablePolygon(
            vertices=[
                Point(x=0.1, y=0.1),
                Point(x=0.4, y=0.1),
                Point(x=0.4, y=0.4),
                Point(x=0.1, y=0.4),
            ]
        ),
    )
    t2 = TableConfig(
        id="t-2",
        code="T-2",
        name="Table 2 Overlap",
        camera_id="CAM-01",
        polygon=TablePolygon(
            vertices=[
                Point(x=0.3, y=0.1),
                Point(x=0.6, y=0.1),
                Point(x=0.6, y=0.4),
                Point(x=0.3, y=0.4),
            ]
        ),
    )

    associator = SpatialTableAssociator(ambiguity_margin=0.02)
    # Point at (0.35, 0.25) is inside BOTH t1 and t2 equally
    det = Detection(
        class_name="person",
        confidence=0.9,
        track_id=40,
        bbox=BoundingBox(x1=0.30, y1=0.15, x2=0.40, y2=0.25),
    )

    assoc = associator.associate_detection(det, [t1, t2])
    assert assoc.status == AssociationStatus.AMBIGUOUS
    assert len(assoc.competing_tables) == 2


def test_frame_association_deduplication_and_capacity(sample_tables: list[TableConfig]):
    """Verify deduplication of identical track ID and capacity warnings."""
    associator = SpatialTableAssociator(ambiguity_margin=0.02)

    # 3 detections inside Table 1 (Capacity is 2), with one duplicate track_id #1
    detections = [
        Detection(
            class_name="person",
            confidence=0.9,
            track_id=1,
            bbox=BoundingBox(x1=0.15, y1=0.15, x2=0.25, y2=0.25),
        ),
        # Duplicate track #1 (should be deduplicated per Rule 5.5)
        Detection(
            class_name="person",
            confidence=0.8,
            track_id=1,
            bbox=BoundingBox(x1=0.16, y1=0.15, x2=0.26, y2=0.25),
        ),
        # Patron #2
        Detection(
            class_name="person",
            confidence=0.9,
            track_id=2,
            bbox=BoundingBox(x1=0.25, y1=0.15, x2=0.35, y2=0.25),
        ),
        # Patron #3 -> pushes count to 3, exceeding capacity 2
        Detection(
            class_name="person",
            confidence=0.9,
            track_id=3,
            bbox=BoundingBox(x1=0.15, y1=0.25, x2=0.25, y2=0.35),
        ),
    ]

    result = associator.associate_frame(detections, sample_tables, camera_id="CAM-01")

    # Table 1 has 3 distinct patrons (track #1 was not counted twice)
    assert result.table_counts["table-01"] == 3
    # Capacity warning triggered
    assert len(result.capacity_warnings) == 1
    assert "T-01 exceeds capacity" in result.capacity_warnings[0]


# ==============================================================================
# 4. Visualizer Rendering Tests
# ==============================================================================


def test_visualizer_table_overlay_rendering(sample_tables: list[TableConfig]):
    """Verify table overlay renders onto a synthetic frame without exception."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    rendered = draw_table_zones_overlay(
        frame=frame,
        tables=sample_tables,
        table_counts={"table-01": 2, "table-02": 1},
    )

    assert rendered.shape == frame.shape
    assert rendered.dtype == np.uint8
    # Frame should have non-zero pixels from drawing
    assert np.count_nonzero(rendered) > 0


def test_visualizer_spatial_association_rendering(sample_tables: list[TableConfig]):
    """Verify complete spatial association overlay with links and badges."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    associator = SpatialTableAssociator()
    det = Detection(
        class_name="person",
        confidence=0.9,
        track_id=1,
        bbox=BoundingBox(x1=0.15, y1=0.15, x2=0.25, y2=0.25),
    )
    res = associator.associate_frame([det], sample_tables, camera_id="CAM-01")

    rendered = draw_spatial_association_overlay(
        frame=frame,
        tables=sample_tables,
        association_result=res,
        fps=5.0,
        camera_id="CAM-01",
    )

    assert rendered.shape == frame.shape
    assert np.count_nonzero(rendered) > 0


# ==============================================================================
# 5. REST API Integration Tests
# ==============================================================================


def test_api_tables_crud_and_associate(temp_layout_path: Path):
    """Test REST API table layout management endpoints."""
    # Override layout manager dependency with isolated temporary file
    test_manager = TableLayoutManager(file_path=temp_layout_path)
    app.dependency_overrides[get_layout_manager] = lambda: test_manager

    client = TestClient(app)

    # 1. Reset to defaults
    resp = client.post("/api/v1/tables/reset-defaults?camera_id=CAM-01")
    assert resp.status_code == 200
    tables = resp.json()
    assert len(tables) >= 4

    # 2. List tables
    resp = client.get("/api/v1/tables?camera_id=CAM-01")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4

    # 3. Create a new table
    new_table_payload = {
        "id": "table-api-test",
        "code": "T-99",
        "name": "API Test Table",
        "camera_id": "CAM-01",
        "capacity": 4,
        "section": "VIP Section",
        "is_active": True,
        "polygon": {
            "vertices": [
                {"x": 0.42, "y": 0.20},
                {"x": 0.56, "y": 0.20},
                {"x": 0.56, "y": 0.40},
                {"x": 0.42, "y": 0.40},
            ]
        },
    }
    resp = client.post("/api/v1/tables", json=new_table_payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["code"] == "T-99"

    # 4. Get specific table
    resp = client.get("/api/v1/tables/table-api-test")
    assert resp.status_code == 200
    assert resp.json()["name"] == "API Test Table"

    # 5. Associate test endpoint
    associate_payload = {
        "camera_id": "CAM-01",
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.95,
                "track_id": 55,
                "bbox": {"x1": 0.45, "y1": 0.22, "x2": 0.53, "y2": 0.35, "is_normalized": True},
            }
        ],
    }
    resp = client.post("/api/v1/tables/associate", json=associate_payload)
    assert resp.status_code == 200
    assoc_res = resp.json()
    assert assoc_res["total_detections"] == 1
    assert "table-api-test" in assoc_res["associated_tracks"]
    assert len(assoc_res["associated_tracks"]["table-api-test"]) == 1

    # 6. Delete table
    resp = client.delete("/api/v1/tables/table-api-test")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify 404 after deletion
    resp = client.get("/api/v1/tables/table-api-test")
    assert resp.status_code == 404

    # Clean up override
    app.dependency_overrides.clear()
