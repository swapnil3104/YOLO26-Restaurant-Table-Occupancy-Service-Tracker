"""Tests for detector adapters and coordinate normalization."""

import numpy as np
import pytest

from smartserve.vision.detector import (
    MockDetector,
    YOLO26Detector,
    denormalize_box,
    normalize_coordinates,
)
from smartserve.vision.interfaces import BaseDetector, BoundingBox, Detection
from smartserve.vision.visualizer import draw_detection_overlay


def test_normalize_coordinates_clamping_and_order():
    """Verify normalize_coordinates clamps to [0.0, 1.0] and corrects inverted coordinates."""
    # Standard normal case
    bbox = normalize_coordinates(x1=100, y1=100, x2=200, y2=200, frame_width=1000, frame_height=500)
    assert bbox.x1 == 0.1
    assert bbox.y1 == 0.2
    assert bbox.x2 == 0.2
    assert bbox.y2 == 0.4
    assert bbox.is_normalized is True

    # Out of bounds clamping
    bbox_clamped = normalize_coordinates(x1=-50, y1=-10, x2=1500, y2=800, frame_width=1000, frame_height=500)
    assert bbox_clamped.x1 == 0.0
    assert bbox_clamped.y1 == 0.0
    assert bbox_clamped.x2 == 1.0
    assert bbox_clamped.y2 == 1.0

    # Inverted coordinates (x1 > x2) should be swapped automatically
    bbox_inverted = normalize_coordinates(x1=300, y1=400, x2=100, y2=200, frame_width=1000, frame_height=500)
    assert bbox_inverted.x1 == 0.1
    assert bbox_inverted.x2 == 0.3
    assert bbox_inverted.y1 == 0.4
    assert bbox_inverted.y2 == 0.8


def test_normalize_coordinates_invalid_dimensions():
    """Verify error raised on invalid frame dimensions."""
    with pytest.raises(ValueError):
        normalize_coordinates(10, 10, 50, 50, frame_width=0, frame_height=100)


def test_denormalize_box():
    """Verify denormalize_box produces correct pixel coordinates."""
    bbox = BoundingBox(x1=0.25, y1=0.50, x2=0.75, y2=1.00, is_normalized=True)
    pixels = denormalize_box(bbox, frame_width=800, frame_height=600)
    assert pixels == (200, 300, 600, 600)


def test_mock_detector_interface_compliance():
    """Verify MockDetector adheres strictly to BaseDetector interface."""
    detector = MockDetector()
    assert isinstance(detector, BaseDetector)

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(dummy_frame)

    assert len(detections) > 0
    det = detections[0]
    assert isinstance(det, Detection)
    assert det.class_name == "person"
    assert 0.0 <= det.confidence <= 1.0
    assert det.bbox.is_normalized is True

    # Check anchor calculation
    cx, cy = det.bbox.center_point
    assert 0.0 <= cx <= 1.0
    assert 0.0 <= cy <= 1.0

    cx_ground, ground_y = det.bbox.bottom_center
    assert cx_ground == cx
    assert ground_y == det.bbox.y2


def test_yolo_detector_input_validation():
    """Verify YOLO26Detector rejects invalid frame input with actionable ValueError."""
    detector = YOLO26Detector(model_path="yolo11n.pt")

    with pytest.raises(ValueError, match="numpy.ndarray"):
        detector.detect(None)

    with pytest.raises(ValueError, match="numpy.ndarray"):
        detector.detect("not an array")

    with pytest.raises(ValueError, match="Invalid frame dimensions"):
        detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))


def test_draw_detection_overlay():
    """Verify visualizer renders overlays without mutating original frame."""
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    detections = [
        Detection(
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(x1=0.2, y1=0.2, x2=0.8, y2=0.8, is_normalized=True),
        )
    ]

    overlay = draw_detection_overlay(
        frame=frame,
        detections=detections,
        show_labels=True,
        show_confidence=True,
        show_anchors=True,
        fps=25.0,
        camera_id="CAM-01",
    )

    assert overlay.shape == frame.shape
    # Check that overlay was modified while frame remained all zeros
    assert np.any(overlay > 0)
    assert np.all(frame == 0)
