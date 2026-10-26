"""Debug visualization tools for computer vision pipelines.

Draws bounding boxes, confidence tags, contact point anchors, trajectory ribbons,
and telemetry overlays for both object detection and multi-object tracking.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from smartserve.occupancy.schema import TableOccupancyStatus
    from smartserve.tables.schema import TableAssociationResult, TableConfig

from smartserve.vision.detector import denormalize_box
from smartserve.vision.interfaces import Detection

# Base color palette (BGR format for OpenCV)
COLOR_EMERALD = (80, 200, 120)  # Default person bounding box
COLOR_ANCHOR = (30, 144, 255)  # Orange/DodgerBlue bottom contact point
COLOR_TEXT_BG = (25, 25, 25)  # Dark tag background
COLOR_TEXT_FG = (255, 255, 255)  # White text

# Distinct color palette for tracking IDs
TRACK_COLORS: list[tuple[int, int, int]] = [
    (80, 200, 120),  # Emerald
    (255, 140, 0),  # Dark Orange
    (220, 20, 60),  # Crimson
    (65, 105, 225),  # Royal Blue
    (186, 85, 211),  # Medium Orchid
    (0, 206, 209),  # Dark Turquoise
    (255, 215, 0),  # Gold
    (255, 105, 180),  # Hot Pink
    (124, 252, 0),  # Lawn Green
    (0, 191, 255),  # Deep Sky Blue
]

# Table zone and spatial association palette (BGR)
COLOR_TABLE_ZONE = (180, 100, 30)  # Translucent navy/steel
COLOR_TABLE_BORDER = (255, 180, 40)  # Vivid cyan/amber border
COLOR_AMBIGUOUS = (0, 140, 255)  # Amber/orange for ambiguous patrons
COLOR_UNASSIGNED = (140, 140, 140)  # Muted gray for unassigned passers-by
COLOR_CAPACITY_WARN = (40, 40, 240)  # Bright Red for capacity warning
COLOR_ASSOC_LINE = (255, 220, 100)  # Soft cyan link line from patron to table


def get_track_color(track_id: int | None) -> tuple[int, int, int]:
    """Return a deterministic color for a given track ID."""
    if track_id is None:
        return COLOR_EMERALD
    return TRACK_COLORS[abs(int(track_id)) % len(TRACK_COLORS)]


def draw_detection_overlay(
    frame: np.ndarray,
    detections: list[Detection],
    show_labels: bool = True,
    show_confidence: bool = True,
    show_anchors: bool = True,
    show_track_ids: bool = True,
    fps: float | None = None,
    camera_id: str | None = None,
    color: tuple[int, int, int] | None = None,
) -> np.ndarray:
    """Draw bounding boxes and metadata overlays onto a copy of the frame.

    Args:
        frame: OpenCV BGR image array.
        detections: List of Detection instances (normalized coordinates).
        show_labels: Whether to render class names.
        show_confidence: Whether to render confidence percentage.
        show_anchors: Whether to render bottom-center ground contact points.
        show_track_ids: Whether to render track ID if present.
        fps: Optional current FPS to display on top banner.
        camera_id: Optional camera ID to display on top banner.
        color: Primary box color in BGR. If None, uses track color or emerald.

    Returns:
        New image array with debug overlays rendered.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for overlay drawing.")

    out = frame.copy()
    height, width = out.shape[:2]

    # Render each detection
    for det in detections:
        x1, y1, x2, y2 = denormalize_box(det.bbox, width, height)
        box_color = color if color is not None else get_track_color(det.track_id)

        # Draw bounding rectangle
        cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 2)

        # Draw label tag
        label_parts = []
        if show_track_ids and det.track_id is not None:
            label_parts.append(f"#{det.track_id}")
        if show_labels:
            label_parts.append(det.class_name)
        if show_confidence:
            label_parts.append(f"{det.confidence * 100:.0f}%")

        if label_parts:
            label_text = " ".join(label_parts)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

            tag_y1 = max(0, y1 - text_h - 6)
            tag_y2 = y1
            cv2.rectangle(out, (x1, tag_y1), (x1 + text_w + 6, tag_y2), COLOR_TEXT_BG, -1)
            cv2.putText(
                out,
                label_text,
                (x1 + 3, tag_y2 - 4),
                font,
                font_scale,
                COLOR_TEXT_FG,
                thickness,
                lineType=cv2.LINE_AA,
            )

        # Draw bottom-center contact anchor (point-in-polygon association anchor)
        if show_anchors:
            cx, cy2 = det.bbox.bottom_center
            px = int(round(cx * width))
            py = int(round(cy2 * height))
            cv2.circle(out, (px, py), 5, COLOR_ANCHOR, -1)
            cv2.circle(out, (px, py), 7, (255, 255, 255), 1)

    # Optional top telemetry bar
    banner_items = []
    if camera_id:
        banner_items.append(f"CAM: {camera_id}")
    if fps is not None and fps > 0:
        banner_items.append(f"FPS: {fps:.1f}")
    banner_items.append(f"PEOPLE: {len(detections)}")

    if banner_items:
        banner_text = " | ".join(banner_items)
        cv2.putText(
            out,
            banner_text,
            (16, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    return out


def draw_tracking_overlay(
    frame: np.ndarray,
    detections: list[Detection],
    trajectories: dict[int, Sequence[tuple[float, float]]] | None = None,
    show_labels: bool = True,
    show_confidence: bool = True,
    show_anchors: bool = True,
    show_trajectories: bool = True,
    fps: float | None = None,
    camera_id: str | None = None,
) -> np.ndarray:
    """Draw tracking-specific overlays including motion trajectory tails.

    Args:
        frame: OpenCV BGR image array.
        detections: List of tracked Detection instances (with track_id).
        trajectories: Mapping of track_id to sequence of normalized (cx, cy) contact points.
        show_labels: Whether to render class names.
        show_confidence: Whether to render confidence percentage.
        show_anchors: Whether to render contact point anchors.
        show_trajectories: Whether to render breadcrumb trajectory paths.
        fps: Optional current FPS.
        camera_id: Optional camera identifier.

    Returns:
        Frame with tracking overlays rendered.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for tracking overlay drawing.")

    out = draw_detection_overlay(
        frame=frame,
        detections=detections,
        show_labels=show_labels,
        show_confidence=show_confidence,
        show_anchors=show_anchors,
        show_track_ids=True,
        fps=fps,
        camera_id=camera_id,
        color=None,  # Enables per-track color
    )

    if not show_trajectories or not trajectories:
        return out

    height, width = out.shape[:2]

    # Draw trajectory lines for each track
    for track_id, points in trajectories.items():
        if len(points) < 2:
            continue

        color = get_track_color(track_id)
        pixel_points = [(int(round(pt[0] * width)), int(round(pt[1] * height))) for pt in points]

        # Draw motion polyline with breadcrumb dots
        for i in range(1, len(pixel_points)):
            pt_prev = pixel_points[i - 1]
            pt_curr = pixel_points[i]
            # Gradually thin or thicken lines towards the latest point
            thickness = max(1, int(round(1 + 2 * (i / len(pixel_points)))))
            cv2.line(out, pt_prev, pt_curr, color, thickness, lineType=cv2.LINE_AA)

        # Draw small breadcrumbs on trajectory nodes
        for pt in pixel_points[:-1]:
            cv2.circle(out, pt, 2, color, -1)

    return out


def draw_table_zones_overlay(
    frame: np.ndarray,
    tables: Sequence[TableConfig],
    alpha: float = 0.25,
    border_thickness: int = 2,
    table_counts: dict[str, int] | None = None,
    show_labels: bool = True,
) -> np.ndarray:
    """Draw configured restaurant table polygon zones onto the camera frame.

    Renders translucent polygon interiors, contrasting zone borders, and table
    badges displaying table code, capacity, and current occupant counts.

    Args:
        frame: OpenCV BGR image array.
        tables: Sequence of TableConfig objects (normalized coordinates).
        alpha: Transparency level for filled polygon overlay (0.0 to 1.0).
        border_thickness: Thickness of polygon bounding borders.
        table_counts: Optional mapping of table_id to current patron count.
        show_labels: Whether to render table code and capacity tags.

    Returns:
        Frame with table zone overlays rendered.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for table overlay drawing.")

    out = frame.copy()
    overlay = frame.copy()
    height, width = out.shape[:2]

    counts = table_counts or {}

    for table in tables:
        if not table.is_active:
            continue

        # Convert normalized vertices to absolute pixel coordinates
        pts = np.array(
            [[int(round(p.x * width)), int(round(p.y * height))] for p in table.polygon.vertices],
            dtype=np.int32,
        ).reshape((-1, 1, 2))

        # Check capacity status for color tinting
        count = counts.get(table.id, 0)
        is_over_capacity = count > table.capacity
        fill_color = COLOR_CAPACITY_WARN if is_over_capacity else COLOR_TABLE_ZONE
        border_color = (0, 0, 255) if is_over_capacity else COLOR_TABLE_BORDER

        # Draw translucent polygon fill
        cv2.fillPoly(overlay, [pts], fill_color)

    # Blend translucent fill overlay
    cv2.addWeighted(overlay, alpha, out, 1.0 - alpha, 0, out)

    # Draw crisp polygon borders and centroid badges on top of blended frame
    for table in tables:
        if not table.is_active:
            continue

        pts = np.array(
            [[int(round(p.x * width)), int(round(p.y * height))] for p in table.polygon.vertices],
            dtype=np.int32,
        ).reshape((-1, 1, 2))

        count = counts.get(table.id, 0)
        is_over_capacity = count > table.capacity
        border_color = (0, 0, 255) if is_over_capacity else COLOR_TABLE_BORDER

        cv2.polylines(out, [pts], isClosed=True, color=border_color, thickness=border_thickness)

        if show_labels:
            cx, cy = table.polygon.centroid
            px = int(round(cx * width))
            py = int(round(cy * height))

            # Table tag text: "T-01 [2/4p]" or "T-01 (4p)"
            if table.id in counts:
                tag_text = f"{table.code} ({count}/{table.capacity}p)"
            else:
                tag_text = f"{table.code} ({table.capacity}p)"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(tag_text, font, font_scale, thickness)

            bx1 = px - tw // 2 - 4
            by1 = py - th // 2 - 4
            bx2 = px + tw // 2 + 4
            by2 = py + th // 2 + 4

            badge_bg = (30, 30, 160) if is_over_capacity else COLOR_TEXT_BG
            cv2.rectangle(out, (bx1, by1), (bx2, by2), badge_bg, -1)
            cv2.rectangle(out, (bx1, by1), (bx2, by2), border_color, 1)
            cv2.putText(
                out,
                tag_text,
                (bx1 + 4, by2 - 4),
                font,
                font_scale,
                COLOR_TEXT_FG,
                thickness,
                lineType=cv2.LINE_AA,
            )

    return out


def draw_spatial_association_overlay(
    frame: np.ndarray,
    tables: Sequence[TableConfig],
    association_result: TableAssociationResult | None = None,
    detections: list[Detection] | None = None,
    trajectories: dict[int, Sequence[tuple[float, float]]] | None = None,
    fps: float | None = None,
    camera_id: str | None = None,
) -> np.ndarray:
    """Draw comprehensive spatial layout with table polygons, patrons, and association links.

    Highlights:
    - Translucent table polygon floor zones.
    - Assigned patrons with link lines to table centroids.
    - Ambiguous patrons highlighted in amber with warning badges.
    - Unassigned patrons rendered in neutral tones.
    - Capacity warnings if patrons exceed seating limits.

    Args:
        frame: OpenCV BGR image array.
        tables: Sequence of TableConfig objects.
        association_result: Optional TableAssociationResult from SpatialTableAssociator.
        detections: Optional list of raw/tracked detections.
        trajectories: Optional motion history dictionary.
        fps: Optional current FPS.
        camera_id: Optional camera identifier.

    Returns:
        Frame rendered with complete spatial floor and patron tracking overlays.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for spatial association overlay drawing.")

    height, width = frame.shape[:2]
    table_map = {t.id: t for t in tables}
    counts = association_result.table_counts if association_result else None

    # Step 1: Render table zones
    out = draw_table_zones_overlay(
        frame=frame,
        tables=tables,
        table_counts=counts,
        show_labels=True,
    )

    # Step 2: Render motion trajectories if provided
    if trajectories:
        for track_id, points in trajectories.items():
            if len(points) < 2:
                continue
            color = get_track_color(track_id)
            pixel_points = [
                (int(round(pt[0] * width)), int(round(pt[1] * height))) for pt in points
            ]
            for i in range(1, len(pixel_points)):
                cv2.line(out, pixel_points[i - 1], pixel_points[i], color, 1, lineType=cv2.LINE_AA)

    # Step 3: Render patrons and association links
    if association_result:
        # Render assigned patrons
        for table_id, assocs in association_result.associated_tracks.items():
            table = table_map.get(table_id)
            if not table:
                continue

            tcx, tcy = table.polygon.centroid
            t_px, t_py = int(round(tcx * width)), int(round(tcy * height))

            for assoc in assocs:
                ax, ay = assoc.anchor_point
                p_px, p_py = int(round(ax * width)), int(round(ay * height))

                # Link line from patron contact anchor to table centroid
                cv2.line(out, (p_px, p_py), (t_px, t_py), COLOR_ASSOC_LINE, 1, lineType=cv2.LINE_AA)
                cv2.circle(out, (p_px, p_py), 4, COLOR_ANCHOR, -1)

                # Badge label
                badge_text = f"#{assoc.track_id} -> {table.code}" if assoc.track_id else table.code
                cv2.putText(
                    out,
                    badge_text,
                    (p_px + 6, p_py - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    COLOR_TEXT_FG,
                    1,
                    lineType=cv2.LINE_AA,
                )

        # Render ambiguous patrons
        for assoc in association_result.ambiguous_tracks:
            ax, ay = assoc.anchor_point
            p_px, p_py = int(round(ax * width)), int(round(ay * height))
            cv2.circle(out, (p_px, p_py), 6, COLOR_AMBIGUOUS, -1)
            cv2.circle(out, (p_px, p_py), 9, (255, 255, 255), 1)

            competing_str = "/".join(assoc.competing_tables) if assoc.competing_tables else "?"
            tag = (
                f"#{assoc.track_id} AMBIGUOUS ({competing_str})"
                if assoc.track_id
                else f"AMBIGUOUS ({competing_str})"
            )
            cv2.putText(
                out,
                tag,
                (p_px + 8, p_py - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                COLOR_AMBIGUOUS,
                1,
                lineType=cv2.LINE_AA,
            )

        # Render unassigned patrons
        for assoc in association_result.unassigned_tracks:
            ax, ay = assoc.anchor_point
            p_px, p_py = int(round(ax * width)), int(round(ay * height))
            cv2.circle(out, (p_px, p_py), 4, COLOR_UNASSIGNED, -1)

    elif detections:
        # Fallback to rendering standard detection overlays
        out = draw_detection_overlay(
            frame=out,
            detections=detections,
            show_track_ids=True,
            show_anchors=True,
        )

    # Step 4: Top telemetry banner
    banner_items = []
    if camera_id:
        banner_items.append(f"CAM: {camera_id}")
    if fps is not None and fps > 0:
        banner_items.append(f"FPS: {fps:.1f}")
    if association_result:
        banner_items.append(f"DETECTIONS: {association_result.total_detections}")
        total_seated = sum(association_result.table_counts.values())
        banner_items.append(f"SEATED: {total_seated}")
        if association_result.ambiguous_tracks:
            banner_items.append(f"AMBIGUOUS: {len(association_result.ambiguous_tracks)}")

    if banner_items:
        banner_text = " | ".join(banner_items)
        cv2.putText(
            out,
            banner_text,
            (16, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    # Step 5: Capacity alerts banner at bottom
    if association_result and association_result.capacity_warnings:
        warn_text = "ALERT: " + " | ".join(association_result.capacity_warnings)
        cv2.putText(
            out,
            warn_text,
            (16, height - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    return out


# Occupancy state color palette (BGR format for OpenCV)
OCCUPANCY_STATE_COLORS: dict[str, tuple[int, int, int]] = {
    "AVAILABLE": (80, 200, 120),  # Vibrant Emerald
    "POSSIBLY_OCCUPIED": (0, 215, 255),  # Vivid Gold / Amber
    "OCCUPIED": (255, 120, 0),  # Royal Deep Blue / Cyan
    "POSSIBLY_VACANT": (0, 140, 255),  # Bright Orange
    "CLEANING_REQUIRED": (180, 50, 220),  # Purple / Violet
    "OUT_OF_SERVICE": (100, 100, 100),  # Neutral Charcoal
    "UNKNOWN": (0, 0, 220),  # Crimson Red (Stale / Outage)
}


def draw_occupancy_state_overlay(
    frame: np.ndarray,
    tables: Sequence[TableConfig],
    occupancy_statuses: dict[str, TableOccupancyStatus],
    camera_id: str | None = None,
    fps: float | None = None,
    alpha: float = 0.28,
) -> np.ndarray:
    """Render comprehensive restaurant occupancy overlays on video frame.

    Visualizes each table with:
    - State-tinted translucent polygon.
    - Solid state-colored perimeter border.
    - Centroid info badge displaying: Table code, Occupancy state,
      Estimated guest count, active session duration, and service status.
    - Header telemetry summary banner.

    Args:
        frame: OpenCV BGR image array.
        tables: Sequence of configured TableConfig instances.
        occupancy_statuses: Mapping of table_id to TableOccupancyStatus.
        camera_id: Optional camera identifier.
        fps: Optional frame rate.
        alpha: Transparency level for filled polygon zone (0.0 to 1.0).

    Returns:
        Frame with occupancy state overlays drawn.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for occupancy overlay.")

    out = frame.copy()
    height, width = out.shape[:2]
    overlay = out.copy()

    # Step 1: Draw translucent filled polygon zones
    for table in tables:
        if not table.is_active:
            continue
        status = occupancy_statuses.get(table.id)
        state_key = status.current_state.value if status else "AVAILABLE"
        if status and status.is_stale:
            state_key = "UNKNOWN"

        color = OCCUPANCY_STATE_COLORS.get(state_key, (128, 128, 128))
        poly_pts = np.array(
            [(int(round(p.x * width)), int(round(p.y * height))) for p in table.polygon.vertices],
            dtype=np.int32,
        )
        if len(poly_pts) >= 3:
            cv2.fillPoly(overlay, [poly_pts], color)

    cv2.addWeighted(overlay, alpha, out, 1.0 - alpha, 0, out)

    # Step 2: Draw crisp borders and badges
    for table in tables:
        if not table.is_active:
            continue
        status = occupancy_statuses.get(table.id)
        state_key = status.current_state.value if status else "AVAILABLE"
        if status and status.is_stale:
            state_key = "UNKNOWN"

        color = OCCUPANCY_STATE_COLORS.get(state_key, (128, 128, 128))
        poly_pts = np.array(
            [(int(round(p.x * width)), int(round(p.y * height))) for p in table.polygon.vertices],
            dtype=np.int32,
        )
        if len(poly_pts) >= 3:
            # Draw perimeter outline
            cv2.polylines(
                out, [poly_pts], isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA
            )

        # Centroid badge
        cx, cy = table.polygon.centroid
        px, py = int(round(cx * width)), int(round(cy * height))

        # Format badge lines
        lines: list[str] = [f"{table.code} [{state_key}]"]
        if status:
            if status.is_stale:
                lines.append("! STALE FEED !")
            elif status.current_state == "POSSIBLY_OCCUPIED":
                lines.append(f"Verifying... {status.evidence_persistence_sec:.1f}s")
            elif status.current_state == "POSSIBLY_VACANT":
                lines.append(f"Grace: {status.vacancy_grace_remaining_sec:.0f}s left")
            elif status.current_state == "OCCUPIED":
                guest_str = f"{status.estimated_customer_count} Guests"
                if status.active_session:
                    dur_sec = status.active_session.calculate_duration()
                    dur_min = int(dur_sec // 60)
                    dur_rem_s = int(dur_sec % 60)
                    guest_str += f" | {dur_min}m{dur_rem_s:02d}s"
                lines.append(guest_str)
            elif status.current_state == "CLEANING_REQUIRED":
                lines.append("Needs Cleaning")

        # Render badge background box
        line_height = 16
        box_width = 160
        box_height = len(lines) * line_height + 8
        bx1 = max(4, px - box_width // 2)
        by1 = max(4, py - box_height // 2)
        bx2 = min(width - 4, bx1 + box_width)
        by2 = min(height - 4, by1 + box_height)

        cv2.rectangle(out, (bx1, by1), (bx2, by2), (20, 20, 20), -1)
        cv2.rectangle(out, (bx1, by1), (bx2, by2), color, 1)

        for i, text in enumerate(lines):
            text_color = color if i == 0 else (230, 230, 230)
            cv2.putText(
                out,
                text,
                (bx1 + 6, by1 + 16 + (i * line_height)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                text_color,
                1,
                lineType=cv2.LINE_AA,
            )

    # Step 3: Top restaurant telemetry banner
    total_tables = len(tables)
    occupied_count = sum(
        1 for s in occupancy_statuses.values() if s.current_state.value == "OCCUPIED"
    )
    available_count = sum(
        1 for s in occupancy_statuses.values() if s.current_state.value == "AVAILABLE"
    )
    cleaning_count = sum(
        1 for s in occupancy_statuses.values() if s.current_state.value == "CLEANING_REQUIRED"
    )
    total_guests = sum(
        s.estimated_customer_count
        for s in occupancy_statuses.values()
        if s.current_state.value == "OCCUPIED"
    )

    banner_items = []
    if camera_id:
        banner_items.append(f"CAM: {camera_id}")
    if fps is not None and fps > 0:
        banner_items.append(f"FPS: {fps:.1f}")
    banner_items.append(f"TABLES: {total_tables}")
    banner_items.append(f"OCCUPIED: {occupied_count}")
    banner_items.append(f"AVAILABLE: {available_count}")
    if cleaning_count > 0:
        banner_items.append(f"CLEANING: {cleaning_count}")
    banner_items.append(f"TOTAL GUESTS: {total_guests}")

    banner_text = " | ".join(banner_items)
    cv2.putText(
        out,
        banner_text,
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        lineType=cv2.LINE_AA,
    )

    return out


def draw_table_edge_overlay(
    frame: np.ndarray,
    table_detections: Sequence[Any],
    patron_contacts: Sequence[Any],
    fps: float | None = None,
    camera_id: str | None = None,
    show_edge_measurements: bool = True,
) -> np.ndarray:
    """Render high-contrast computer vision visualization of table edges and seated patron contacts.

    Visual Elements:
    - Glowing perimeter polygon lines along all table edges.
    - Vertex node circles at all table corners.
    - Active table edge segments glowing in emerald where seated patrons touch the table edge.
    - Neon trajectory lines linking patron contact points to the nearest table edge point with pixel distances.
    - Telemetry HUD with camera ID, FPS, and table edge occupancy counts.
    """
    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("Invalid frame for table edge overlay drawing.")

    out = frame.copy()
    overlay = frame.copy()
    height, width = out.shape[:2]

    # Colors
    color_edge_normal = (255, 180, 40)  # Vivid cyan/amber
    color_edge_active = (60, 255, 120)  # Neon Emerald
    color_edge_node = (0, 220, 255)  # Yellow-orange vertex node
    color_patron_seated = (60, 220, 100)  # Green for diner at table edge
    color_patron_aisle = (140, 140, 140)  # Gray for passer-by
    color_link_line = (255, 220, 80)  # Cyan link line
    color_hud_bg = (20, 22, 28)

    # Step 1: Draw translucent table fill
    for table in table_detections:
        if len(table.polygon_vertices) >= 3:
            pts = np.array(table.polygon_vertices, dtype=np.int32).reshape((-1, 1, 2))
            has_occupied_edge = any(seg.is_occupied for seg in table.edge_segments)
            fill_tint = (160, 120, 30) if not has_occupied_edge else (40, 140, 60)
            cv2.fillPoly(overlay, [pts], fill_tint)

    cv2.addWeighted(overlay, 0.20, out, 0.80, 0, out)

    # Step 2: Draw table perimeter edges and corner nodes
    for table in table_detections:
        for seg in table.edge_segments:
            seg_color = color_edge_active if seg.is_occupied else color_edge_normal
            thickness = 3 if seg.is_occupied else 2

            # Draw edge line
            cv2.line(out, seg.p1, seg.p2, seg_color, thickness, cv2.LINE_AA)

            # Draw vertex nodes
            cv2.circle(out, seg.p1, 4, color_edge_node, -1)
            cv2.circle(out, seg.p2, 4, color_edge_node, -1)

            # Active edge indicator badge
            if seg.is_occupied and seg.contact_point_on_edge:
                cv2.circle(out, seg.contact_point_on_edge, 6, (0, 255, 255), -1)
                cv2.circle(out, seg.contact_point_on_edge, 8, color_edge_active, 1)

        # Draw Table Label at Centroid
        cx, cy = table.centroid
        occupied_edges_count = sum(1 for s in table.edge_segments if s.is_occupied)
        tag_text = (
            f"{table.label} [Edges: {occupied_edges_count}/{len(table.edge_segments)} occupied]"
        )
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(
            out,
            (cx - tw // 2 - 4, cy - th // 2 - 4),
            (cx + tw // 2 + 4, cy + th // 2 + 4),
            (20, 20, 20),
            -1,
        )
        cv2.rectangle(
            out,
            (cx - tw // 2 - 4, cy - th // 2 - 4),
            (cx + tw // 2 + 4, cy + th // 2 + 4),
            color_edge_normal,
            1,
        )
        cv2.putText(
            out,
            tag_text,
            (cx - tw // 2, cy + th // 2 - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # Step 3: Draw patron contacts and table-edge link lines
    seated_at_edge_count = 0
    walking_count = 0

    for patron in patron_contacts:
        x1, y1, x2, y2 = patron.bbox
        anchor = patron.contact_point
        is_seated = patron.status == "SEATED_AT_EDGE"

        if is_seated:
            seated_at_edge_count += 1
            box_color = color_patron_seated
            status_text = (
                f"Diner #{patron.track_id or 'x'} | Table Edge Contact ({patron.distance_px:.0f}px)"
            )
        elif patron.status == "NEAR_TABLE":
            box_color = (0, 180, 255)
            status_text = (
                f"Patron #{patron.track_id or 'x'} | Near Edge ({patron.distance_px:.0f}px)"
            )
        else:
            walking_count += 1
            box_color = color_patron_aisle
            status_text = f"Patron #{patron.track_id or 'x'} | Aisle"

        # Bounding box
        cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 2)

        # Contact Anchor dot
        cv2.circle(out, anchor, 5, (0, 140, 255), -1)

        # Label badge
        (tw, th), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        tag_y = max(0, y1 - th - 6)
        cv2.rectangle(out, (x1, tag_y), (x1 + tw + 6, tag_y + th + 6), (20, 20, 20), -1)
        cv2.rectangle(out, (x1, tag_y), (x1 + tw + 6, tag_y + th + 6), box_color, 1)
        cv2.putText(
            out,
            status_text,
            (x1 + 3, tag_y + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        # Link line connecting diner contact point to table edge
        if is_seated and patron.projection_point and show_edge_measurements:
            proj = patron.projection_point
            cv2.line(out, anchor, proj, color_link_line, 2, cv2.LINE_AA)
            cv2.circle(out, proj, 4, (0, 255, 255), -1)

            # Measurement distance text midway along the link line
            mid_x = (anchor[0] + proj[0]) // 2
            mid_y = (anchor[1] + proj[1]) // 2
            dist_text = f"{patron.distance_px:.0f}px"
            cv2.putText(
                out,
                dist_text,
                (mid_x + 4, mid_y - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # Step 4: Top Telemetry HUD
    hud_h = 38
    hud = np.full((hud_h, width, 3), color_hud_bg, dtype=np.uint8)
    cam_str = f"CAM: {camera_id or 'CAM-01'}"
    fps_str = f"FPS: {fps:.1f}" if fps else "FPS: 25.0"
    tables_str = f"TABLES: {len(table_detections)}"
    edge_diners_str = f"AT TABLE EDGE: {seated_at_edge_count}"
    aisle_str = f"AISLE: {walking_count}"

    hud_text = f"{cam_str}  |  {fps_str}  |  {tables_str}  |  {edge_diners_str}  |  {aisle_str}"
    cv2.putText(
        hud, hud_text, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1, cv2.LINE_AA
    )
    cv2.line(hud, (0, hud_h - 1), (width, hud_h - 1), (80, 80, 80), 1)

    return np.vstack([hud, out])
