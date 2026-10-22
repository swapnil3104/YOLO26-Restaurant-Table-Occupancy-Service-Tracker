"""Debug visualization tools for computer vision pipelines.

Draws bounding boxes, confidence tags, contact point anchors, trajectory ribbons,
and telemetry overlays for both object detection and multi-object tracking.
"""

from collections.abc import Sequence

import cv2
import numpy as np

from smartserve.vision.detector import denormalize_box
from smartserve.vision.interfaces import Detection

# Base color palette (BGR format for OpenCV)
COLOR_EMERALD = (80, 200, 120)  # Default person bounding box
COLOR_ANCHOR = (30, 144, 255)  # Orange/DodgerBlue bottom contact point
COLOR_TEXT_BG = (25, 25, 25)  # Dark tag background
COLOR_TEXT_FG = (255, 255, 255)  # White text

# Distinct color palette for tracking IDs
TRACK_COLORS: list[tuple[int, int, int]] = [
    (80, 200, 120),   # Emerald
    (255, 140, 0),    # Dark Orange
    (220, 20, 60),    # Crimson
    (65, 105, 225),   # Royal Blue
    (186, 85, 211),   # Medium Orchid
    (0, 206, 209),    # Dark Turquoise
    (255, 215, 0),    # Gold
    (255, 105, 180),  # Hot Pink
    (124, 252, 0),    # Lawn Green
    (0, 191, 255),    # Deep Sky Blue
]


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
        pixel_points = [
            (int(round(pt[0] * width)), int(round(pt[1] * height)))
            for pt in points
        ]

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
