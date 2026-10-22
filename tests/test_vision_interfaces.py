"""Tests for vision interfaces and data structures."""

from smartserve.vision.interfaces import BaseDetector, BoundingBox, Detection


class MockDetector(BaseDetector):
    """Test double for BaseDetector."""

    def detect(self, frame):
        return [
            Detection(
                class_name="person",
                confidence=0.88,
                bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.3, y2=0.8, is_normalized=True),
            )
        ]


def test_bounding_box_calculations():
    """Verify center and bottom_center calculations."""
    box = BoundingBox(x1=0.1, y1=0.2, x2=0.3, y2=0.8)
    cx, cy = box.center_point
    assert cx == 0.2
    assert cy == 0.5

    bx, by = box.bottom_center
    assert bx == 0.2
    assert by == 0.8


def test_mock_detector_contract():
    """Verify mock detector adheres to BaseDetector contract."""
    detector = MockDetector()
    results = detector.detect(None)
    assert len(results) == 1
    assert results[0].class_name == "person"
    assert results[0].confidence == 0.88
