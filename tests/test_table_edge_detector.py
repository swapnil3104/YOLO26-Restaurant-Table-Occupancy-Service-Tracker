"""Unit tests for TableEdgeDetector and table edge perimeter tracking."""

import numpy as np

from smartserve.tables.edge_detector import (
    TableEdgeDetector,
    distance_point_to_segment,
)
from smartserve.vision.interfaces import BoundingBox, Detection
from smartserve.vision.visualizer import draw_table_edge_overlay


def test_distance_point_to_segment():
    """Verify perpendicular and endpoint distance calculations."""
    # Horizontal segment from (10, 20) to (50, 20)
    # Point at (30, 25) -> distance is 5, projection at (30, 20)
    dist, proj = distance_point_to_segment(30, 25, 10, 20, 50, 20)
    assert abs(dist - 5.0) < 1e-4
    assert proj == (30, 20)

    # Point past right endpoint at (60, 20) -> distance is 10, projection at (50, 20)
    dist, proj = distance_point_to_segment(60, 20, 10, 20, 50, 20)
    assert abs(dist - 10.0) < 1e-4
    assert proj == (50, 20)


def test_extract_edges_from_polygon():
    """Verify polygon decomposition into discrete edge segments."""
    detector = TableEdgeDetector()
    rect_verts = [(100, 100), (300, 100), (300, 200), (100, 200)]
    table_edge = detector.extract_edges_from_polygon(
        vertices=rect_verts,
        table_id="T01",
        label="Table 1",
    )

    assert table_edge.table_id == "T01"
    assert len(table_edge.edge_segments) == 4
    assert table_edge.centroid == (200, 150)

    # Top edge: (100, 100) -> (300, 100)
    top_edge = table_edge.edge_segments[0]
    assert top_edge.p1 == (100, 100)
    assert top_edge.p2 == (300, 100)
    assert top_edge.length_px == 200.0
    assert top_edge.midpoint == (200, 100)


def test_patron_edge_contact_association():
    """Verify seated diner edge contact and aisle passer-by classification."""
    detector = TableEdgeDetector(edge_contact_threshold_px=30.0, edge_proximity_threshold_px=60.0)
    rect_verts = [(100, 100), (300, 100), (300, 200), (100, 200)]
    table = detector.extract_edges_from_polygon(rect_verts, "T01", "Table 1")

    # Patron 1: Seated right at the bottom edge (200, 208) -> within 8px
    patron_seated = Detection(
        class_name="person",
        confidence=0.9,
        track_id=1,
        bbox=BoundingBox(x1=0.18, y1=0.15, x2=0.22, y2=0.208, is_normalized=True),
    )

    # Patron 2: Walking in aisle far away (450, 450)
    patron_aisle = Detection(
        class_name="person",
        confidence=0.85,
        track_id=2,
        bbox=BoundingBox(x1=0.43, y1=0.40, x2=0.47, y2=0.45, is_normalized=True),
    )

    contacts = detector.associate_patrons_to_table_edges(
        patrons=[patron_seated, patron_aisle],
        table_detections=[table],
        frame_width=1000,
        frame_height=1000,
    )

    assert len(contacts) == 2

    # Verify Patron 1 seated at edge
    c1 = contacts[0]
    assert c1.status == "SEATED_AT_EDGE"
    assert c1.table_id == "T01"
    assert c1.distance_px <= 30.0
    assert c1.edge_segment is not None
    assert c1.edge_segment.is_occupied is True

    # Verify Patron 2 in aisle
    c2 = contacts[1]
    assert c2.status == "UNASSIGNED"
    assert c2.distance_px > 60.0


def test_draw_table_edge_overlay_rendering():
    """Verify draw_table_edge_overlay generates output frame with HUD."""
    detector = TableEdgeDetector()
    rect_verts = [(100, 100), (300, 100), (300, 200), (100, 200)]
    table = detector.extract_edges_from_polygon(rect_verts, "T01", "Table 1")

    patron = Detection(
        class_name="person",
        confidence=0.9,
        track_id=10,
        bbox=BoundingBox(x1=0.18, y1=0.15, x2=0.22, y2=0.21, is_normalized=True),
    )

    contacts = detector.associate_patrons_to_table_edges(
        patrons=[patron],
        table_detections=[table],
        frame_width=800,
        frame_height=600,
    )

    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    rendered = draw_table_edge_overlay(
        frame=frame,
        table_detections=[table],
        patron_contacts=contacts,
        fps=25.0,
        camera_id="CAM-01",
    )

    # Frame height has HUD added (600 + 38 = 638)
    assert rendered.shape == (638, 800, 3)
