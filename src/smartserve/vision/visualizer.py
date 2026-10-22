"""Debug visualization tools for computer vision pipelines.

Draws bounding boxes, confidence tags, contact point anchors, and telemetry overlays.
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np

from smartserve.vision.detector import denormalize_box
from smartserve.vision.interfaces import Detection

# Color palette (BGR format for OpenCV)
COLOR_EMERALD = (80, 200, 120)     # Default person bounding box
COLOR_ANCHOR = (30, 144, 255)      # Orange/DodgerBlue bottom contact point
COLOR_TEXT_BG = (25, 25, 25)       # Dark tag background
COLOR_TEXT_FG = (255, 255, 255)    # White text


def draw_detection_overlay(
    frame: np.ndarray,
    detections: List[Detection],
    show_labels: bool = True,
    show_confidence: bool = True,
    show_anchors: bool = True,
    fps: Optional[float] = None,
    camera_id: Optional[str] = None,
    color: Tuple[int, int, int] = COLOR_EMERALD,
) -> np.ndarray:
    """Draw bounding boxes and metadata overlays onto a copy of the frame.

    Args:
        frame: OpenCV BGR image array.
        detections: List of Detection instances (normalized coordinates).
        show_labels: Whether to render class names.
        show_confidence: Whether to render confidence percentage.
        show_anchors: Whether to render bottom-center ground contact points.
        fps: Optional current FPS to display on top banner.
        camera_id: Optional camera ID to display on top banner.
        color: Primary box color in BGR.

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

        # Draw bounding rectangle
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        # Draw label tag
        label_parts = []
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
