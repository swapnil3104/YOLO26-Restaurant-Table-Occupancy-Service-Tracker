"""Spatial Table Associator for mapping person detections and tracks to table polygons.

Implements point-in-polygon testing on patron contact anchors, multi-table ambiguity
resolution, track deduplication, and capacity monitoring in accordance with
Docs/RULES.md (Section 5) and Docs/ARCHITECTURE.md (Section 5.5).
"""

import logging
import time
from collections.abc import Sequence

import cv2
import numpy as np

from smartserve.config import settings
from smartserve.tables.schema import (
    AssociationStatus,
    TableAssociationResult,
    TableConfig,
    TrackAssociation,
)
from smartserve.vision.interfaces import Detection

logger = logging.getLogger("smartserve.tables.associator")


def point_in_polygon_raycast(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    """Test whether a 2D point (px, py) is inside a polygon using ray-casting.

    Works for arbitrary convex and concave simple polygons without external dependencies.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if py > min(p1y, p2y):
            if py <= max(p1y, p2y):
                if px <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        xinters = p1x
                    if p1x == p2x or px <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def compute_signed_distance(
    px: float,
    py: float,
    polygon: list[tuple[float, float]],
    scale: float = 1000.0,
) -> float:
    """Compute signed distance from point to polygon boundary using OpenCV.

    Args:
        px: Normalized X coordinate.
        py: Normalized Y coordinate.
        polygon: List of normalized (x, y) coordinates.
        scale: Scaling factor for numerical stability.

    Returns:
        Positive float if point is inside polygon, zero on edge, negative if outside.
        Value is normalized (divided by scale).
    """
    pts = np.array(
        [[int(round(pt[0] * scale)), int(round(pt[1] * scale))] for pt in polygon],
        dtype=np.int32,
    ).reshape((-1, 1, 2))

    test_pt = (float(px * scale), float(py * scale))
    dist = cv2.pointPolygonTest(pts, test_pt, measureDist=True)
    return float(dist / scale)


class SpatialTableAssociator:
    """Associates person detections with configured table polygon regions."""

    def __init__(
        self,
        ambiguity_margin: float | None = None,
        require_anchor_contact: bool = True,
    ):
        """Initialize associator.

        Args:
            ambiguity_margin: Normalized distance threshold for boundary ambiguity.
                              Defaults to settings.TABLE_AMBIGUITY_MARGIN.
            require_anchor_contact: Use bottom_center anchor point (patron seat/floor contact)
                                    as recommended in Rules Section 5.
        """
        self.ambiguity_margin = (
            ambiguity_margin if ambiguity_margin is not None else settings.TABLE_AMBIGUITY_MARGIN
        )
        self.require_anchor_contact = require_anchor_contact

    def associate_detection(
        self,
        detection: Detection,
        tables: Sequence[TableConfig],
    ) -> TrackAssociation:
        """Associate a single detection against a list of active tables.

        Evaluates contact point against each table polygon, scores competing matches,
        and returns an AssociationStatus (ASSOCIATED, AMBIGUOUS, or UNASSIGNED).
        """
        anchor = (
            detection.bbox.bottom_center
            if self.require_anchor_contact
            else detection.bbox.center_point
        )
        px, py = anchor

        inside_matches: list[tuple[TableConfig, float]] = []
        near_matches: list[tuple[TableConfig, float]] = []

        for table in tables:
            poly_tuples = table.polygon.as_tuples()
            # Fast bounding box pre-filter
            t_bbox = table.polygon.bounding_box
            margin = self.ambiguity_margin
            if not (
                (t_bbox.x1 - margin) <= px <= (t_bbox.x2 + margin)
                and (t_bbox.y1 - margin) <= py <= (t_bbox.y2 + margin)
            ):
                continue

            # Calculate signed distance and raycast inclusion
            signed_dist = compute_signed_distance(px, py, poly_tuples)
            is_inside = signed_dist >= 0.0 or point_in_polygon_raycast(px, py, poly_tuples)

            if is_inside:
                inside_matches.append((table, signed_dist))
            elif abs(signed_dist) <= self.ambiguity_margin:
                near_matches.append((table, signed_dist))

        # Case 1: Point is inside multiple tables (overlapping layout polygons)
        if len(inside_matches) > 1:
            # Sort by depth inside polygon
            inside_matches.sort(key=lambda x: x[1], reverse=True)
            deepest_table, deepest_dist = inside_matches[0]
            runner_up_table, runner_up_dist = inside_matches[1]

            # If the deepest table is significantly more contained than the second
            if (deepest_dist - runner_up_dist) > (self.ambiguity_margin * 1.5):
                return TrackAssociation(
                    track_id=detection.track_id,
                    table_id=deepest_table.id,
                    table_code=deepest_table.code,
                    status=AssociationStatus.ASSOCIATED,
                    anchor_point=anchor,
                    confidence=0.85,
                    distance_to_edge=deepest_dist,
                    competing_tables=[t[0].code for t in inside_matches[1:]],
                    reason="Disambiguated by interior polygon distance depth.",
                )

            # Otherwise, competing tables are too close/overlapping -> Ambiguous
            competing = [t[0].code for t in inside_matches]
            return TrackAssociation(
                track_id=detection.track_id,
                table_id=None,
                table_code=None,
                status=AssociationStatus.AMBIGUOUS,
                anchor_point=anchor,
                confidence=0.5,
                distance_to_edge=deepest_dist,
                competing_tables=competing,
                reason=f"Contact point falls within overlapping regions of: {', '.join(competing)}",
            )

        # Case 2: Point is inside exactly one table
        if len(inside_matches) == 1:
            matched_table, dist = inside_matches[0]

            # Check if it is near the boundary of an adjacent competing table
            competing_near = [
                t[0].code
                for t in near_matches
                if t[0].id != matched_table.id and abs(t[1]) <= self.ambiguity_margin
            ]
            if competing_near and dist < self.ambiguity_margin:
                # Falls right on the dividing seam between two adjacent tables
                all_competing = [matched_table.code] + competing_near
                return TrackAssociation(
                    track_id=detection.track_id,
                    table_id=None,
                    table_code=None,
                    status=AssociationStatus.AMBIGUOUS,
                    anchor_point=anchor,
                    confidence=0.5,
                    distance_to_edge=dist,
                    competing_tables=all_competing,
                    reason=f"Contact point on boundary between {matched_table.code} and {', '.join(competing_near)}",
                )

            return TrackAssociation(
                track_id=detection.track_id,
                table_id=matched_table.id,
                table_code=matched_table.code,
                status=AssociationStatus.ASSOCIATED,
                anchor_point=anchor,
                confidence=min(1.0, 0.7 + dist * 5.0),
                distance_to_edge=dist,
            )

        # Case 3: Point is outside all tables, but near multiple adjacent tables within ambiguity margin
        if len(inside_matches) == 0 and len(near_matches) >= 2:
            near_matches.sort(key=lambda x: abs(x[1]))
            closest_dist = abs(near_matches[0][1])
            second_dist = abs(near_matches[1][1])
            if (second_dist - closest_dist) <= self.ambiguity_margin:
                competing = [t[0].code for t in near_matches]
                return TrackAssociation(
                    track_id=detection.track_id,
                    table_id=None,
                    table_code=None,
                    status=AssociationStatus.AMBIGUOUS,
                    anchor_point=anchor,
                    confidence=0.5,
                    distance_to_edge=-closest_dist,
                    competing_tables=competing,
                    reason=f"Contact point in boundary gap between adjacent tables: {', '.join(competing)}",
                )

        # Case 4: Clearly outside all tables
        return TrackAssociation(
            track_id=detection.track_id,
            table_id=None,
            table_code=None,
            status=AssociationStatus.UNASSIGNED,
            anchor_point=anchor,
            confidence=1.0,
            distance_to_edge=None,
            reason="Outside all configured table polygons.",
        )

    def associate_frame(
        self,
        detections: Sequence[Detection],
        tables: Sequence[TableConfig],
        camera_id: str,
        timestamp: float | None = None,
    ) -> TableAssociationResult:
        """Associate all person detections in a frame against camera tables.

        Enforces:
        - Rule 5.5: Do not count one track more than once for a table in the same observation window.
        - Table capacity alerts when associated occupants exceed table capacity.
        - Segregation into associated, ambiguous, and unassigned collections.
        """
        ts = timestamp if timestamp is not None else time.time()
        active_tables = [t for t in tables if t.is_active and t.camera_id == camera_id]
        table_map = {t.id: t for t in active_tables}

        associated_by_table: dict[str, list[TrackAssociation]] = {t.id: [] for t in active_tables}
        ambiguous_tracks: list[TrackAssociation] = []
        unassigned_tracks: list[TrackAssociation] = []

        seen_track_ids: set[int] = set()

        for det in detections:
            # Enforce deduplication: if track_id is already assigned this frame, ignore duplicate
            if det.track_id is not None and det.track_id in seen_track_ids:
                logger.debug(f"Skipping duplicate track_id #{det.track_id} in observation window.")
                continue

            assoc = self.associate_detection(det, active_tables)

            if assoc.status == AssociationStatus.ASSOCIATED and assoc.table_id:
                associated_by_table[assoc.table_id].append(assoc)
                if det.track_id is not None:
                    seen_track_ids.add(det.track_id)
            elif assoc.status == AssociationStatus.AMBIGUOUS:
                ambiguous_tracks.append(assoc)
            else:
                unassigned_tracks.append(assoc)

        # Aggregate counts and check capacities
        table_counts: dict[str, int] = {}
        capacity_warnings: list[str] = []

        for table_id, assocs in associated_by_table.items():
            count = len(assocs)
            table_counts[table_id] = count
            table_cfg = table_map.get(table_id)
            if table_cfg and count > table_cfg.capacity:
                warning_msg = (
                    f"Table {table_cfg.code} exceeds capacity: "
                    f"{count} patrons associated (capacity: {table_cfg.capacity})."
                )
                capacity_warnings.append(warning_msg)
                logger.warning(warning_msg)

        return TableAssociationResult(
            timestamp=ts,
            camera_id=camera_id,
            total_detections=len(detections),
            associated_tracks=associated_by_table,
            ambiguous_tracks=ambiguous_tracks,
            unassigned_tracks=unassigned_tracks,
            table_counts=table_counts,
            capacity_warnings=capacity_warnings,
        )
