"""Table Edge Detection and Perimeter Association Engine.

Detects table rims, perimeter boundaries, and edge segments from either:
1. Deep-learning YOLO table detections with computer vision contour/hull edge extraction.
2. Configured restaurant floor plan table polygons (TableConfig).

Calculates exact perpendicular distance between seated diner contact points and table edges,
identifying which patrons are seated at which specific table edges.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from smartserve.tables.schema import TableConfig
    from smartserve.vision.interfaces import Detection


@dataclass
class TableEdgeSegment:
    """A discrete edge segment along a table's perimeter."""

    p1: tuple[int, int]
    p2: tuple[int, int]
    length_px: float
    midpoint: tuple[int, int]
    edge_index: int
    is_occupied: bool = False
    assigned_patron_id: int | None = None
    closest_dist_px: float = float("inf")
    contact_point_on_edge: tuple[int, int] | None = None


@dataclass
class TableEdgeDetection:
    """Table boundary with localized perimeter edge segments."""

    table_id: str
    label: str
    polygon_vertices: list[tuple[int, int]]  # Absolute pixel (x, y)
    edge_segments: list[TableEdgeSegment] = field(default_factory=list)
    centroid: tuple[int, int] = (0, 0)
    is_auto_detected: bool = False
    confidence: float = 1.0


@dataclass
class PatronEdgeContact:
    """Spatial relationship between a diner and a table edge."""

    track_id: int | None
    class_name: str
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    contact_point: tuple[int, int]  # Bottom center (x, y)
    table_id: str | None = None
    table_label: str | None = None
    nearest_edge_index: int | None = None
    edge_segment: TableEdgeSegment | None = None
    projection_point: tuple[int, int] | None = None
    distance_px: float = float("inf")
    status: str = "UNASSIGNED"  # "SEATED_AT_EDGE", "NEAR_TABLE", "UNASSIGNED"


def distance_point_to_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> tuple[float, tuple[int, int]]:
    """Compute the minimum distance from point (px, py) to line segment (x1, y1)-(x2, y2).

    Returns:
        (distance_in_pixels, closest_point_on_segment)
    """
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = (dx * dx) + (dy * dy)

    if seg_len_sq < 1e-6:
        # Degenerate segment
        return math.hypot(px - x1, py - y1), (int(round(x1)), int(round(y1)))

    # Projection factor t in [0.0, 1.0]
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + (t * dx)
    proj_y = y1 + (t * dy)
    dist = math.hypot(px - proj_x, py - proj_y)

    return dist, (int(round(proj_x)), int(round(proj_y)))


class TableEdgeDetector:
    """Extracts table perimeter edges and associates patrons to table edges."""

    def __init__(
        self,
        edge_contact_threshold_px: float = 35.0,
        edge_proximity_threshold_px: float = 65.0,
    ) -> None:
        """Initialize TableEdgeDetector.

        Args:
            edge_contact_threshold_px: Max distance to classify diner as seated at the table edge.
            edge_proximity_threshold_px: Max distance to classify diner as standing near table.
        """
        self.edge_contact_threshold_px = float(edge_contact_threshold_px)
        self.edge_proximity_threshold_px = float(edge_proximity_threshold_px)

    def extract_edges_from_polygon(
        self,
        vertices: Sequence[tuple[int, int]],
        table_id: str,
        label: str,
        is_auto_detected: bool = False,
        confidence: float = 1.0,
    ) -> TableEdgeDetection:
        """Convert a sequence of polygon vertices into a TableEdgeDetection with perimeter segments."""
        n = len(vertices)
        if n < 3:
            raise ValueError("Polygon must contain at least 3 vertices.")

        segments: list[TableEdgeSegment] = []
        cx = sum(p[0] for p in vertices) // n
        cy = sum(p[1] for p in vertices) // n

        for i in range(n):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % n]
            length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            midpoint = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)

            segments.append(
                TableEdgeSegment(
                    p1=p1,
                    p2=p2,
                    length_px=length,
                    midpoint=midpoint,
                    edge_index=i,
                )
            )

        return TableEdgeDetection(
            table_id=table_id,
            label=label,
            polygon_vertices=list(vertices),
            edge_segments=segments,
            centroid=(cx, cy),
            is_auto_detected=is_auto_detected,
            confidence=confidence,
        )

    def detect_table_edges_from_bbox(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        table_id: str,
        label: str = "Detected Table",
        confidence: float = 1.0,
    ) -> TableEdgeDetection:
        """Extract physical tabletop edges from a bounding box using Canny and convex hull."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        bw = x2 - x1
        bh = y2 - y1

        if bw < 20 or bh < 20:
            # Fallback to simple rectangle
            rect_verts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            return self.extract_edges_from_polygon(rect_verts, table_id, label, True, confidence)

        crop = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 35, 110)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 0.05 * (bw * bh):
                hull = cv2.convexHull(largest)
                peri = cv2.arcLength(hull, True)
                poly = cv2.approxPolyDP(hull, 0.035 * peri, True)

                if len(poly) >= 4:
                    vertices = [(int(p[0][0] + x1), int(p[0][1] + y1)) for p in poly]
                    return self.extract_edges_from_polygon(
                        vertices, table_id, label, True, confidence
                    )

        # Fallback to bbox rectangle vertices
        rect_verts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return self.extract_edges_from_polygon(rect_verts, table_id, label, True, confidence)

    def get_configured_tables_edges(
        self,
        tables: Sequence[TableConfig],
        width: int,
        height: int,
    ) -> list[TableEdgeDetection]:
        """Convert configured TableConfig polygons into TableEdgeDetection instances."""
        results: list[TableEdgeDetection] = []
        for t in tables:
            if not t.is_active:
                continue
            verts = [
                (int(round(p.x * width)), int(round(p.y * height))) for p in t.polygon.vertices
            ]
            results.append(
                self.extract_edges_from_polygon(
                    vertices=verts,
                    table_id=t.id,
                    label=f"{t.code} ({t.name})",
                    is_auto_detected=False,
                    confidence=1.0,
                )
            )
        return results

    def associate_patrons_to_table_edges(
        self,
        patrons: Sequence[Detection],
        table_detections: Sequence[TableEdgeDetection],
        frame_width: int,
        frame_height: int,
    ) -> list[PatronEdgeContact]:
        """Calculate contact between each patron anchor point and nearest table edge."""
        results: list[PatronEdgeContact] = []

        for p in patrons:
            # Denormalize bbox
            x1 = int(round(p.bbox.x1 * frame_width))
            y1 = int(round(p.bbox.y1 * frame_height))
            x2 = int(round(p.bbox.x2 * frame_width))
            y2 = int(round(p.bbox.y2 * frame_height))

            # Bottom center anchor (ground / seat line)
            anchor_x = (x1 + x2) // 2
            anchor_y = y2

            best_dist = float("inf")
            best_table: TableEdgeDetection | None = None
            best_segment: TableEdgeSegment | None = None
            best_proj: tuple[int, int] | None = None

            # Test against all table edge segments
            for table in table_detections:
                for seg in table.edge_segments:
                    dist, proj = distance_point_to_segment(
                        px=anchor_x,
                        py=anchor_y,
                        x1=seg.p1[0],
                        y1=seg.p1[1],
                        x2=seg.p2[0],
                        y2=seg.p2[1],
                    )
                    if dist < best_dist:
                        best_dist = dist
                        best_table = table
                        best_segment = seg
                        best_proj = proj

            # Determine contact status
            if best_dist <= self.edge_contact_threshold_px and best_table and best_segment:
                status = "SEATED_AT_EDGE"
                best_segment.is_occupied = True
                best_segment.assigned_patron_id = p.track_id
                best_segment.closest_dist_px = min(best_segment.closest_dist_px, best_dist)
                best_segment.contact_point_on_edge = best_proj
            elif best_dist <= self.edge_proximity_threshold_px and best_table:
                status = "NEAR_TABLE"
            else:
                status = "UNASSIGNED"

            results.append(
                PatronEdgeContact(
                    track_id=p.track_id,
                    class_name=p.class_name,
                    bbox=(x1, y1, x2, y2),
                    contact_point=(anchor_x, anchor_y),
                    table_id=best_table.table_id if best_table else None,
                    table_label=best_table.label if best_table else None,
                    nearest_edge_index=best_segment.edge_index if best_segment else None,
                    edge_segment=best_segment,
                    projection_point=best_proj,
                    distance_px=round(best_dist, 1),
                    status=status,
                )
            )

        return results
