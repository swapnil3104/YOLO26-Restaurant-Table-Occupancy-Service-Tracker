"""Abstract vision interfaces for detectors and trackers.

Preserves decoupling between specific model packages (Ultralytics / YOLO)
and business logic, satisfying architecture requirements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class BoundingBox:
    """Normalized or absolute bounding box coordinates [x1, y1, x2, y2]."""

    x1: float
    y1: float
    x2: float
    y2: float
    is_normalized: bool = True

    @property
    def center_point(self) -> tuple[float, float]:
        """Return (cx, cy)."""
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> tuple[float, float]:
        """Return (cx, y2) representing person feet / table contact anchor."""
        return ((self.x1 + self.x2) / 2.0, self.y2)


@dataclass
class Detection:
    """Standardized detection observation."""

    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None
    metadata: dict | None = None


class BaseDetector(ABC):
    """Abstract detector interface independent of concrete deep learning frameworks."""

    @abstractmethod
    def detect(self, frame: Any) -> list[Detection]:
        """Run object detection on an input image/frame.

        Args:
            frame: OpenCV image array (numpy.ndarray).

        Returns:
            List of normalized Detection objects.
        """
        pass


class BaseTracker(ABC):
    """Abstract tracker interface for multi-object tracking."""

    @abstractmethod
    def update(self, detections: list[Detection], frame: Any) -> list[Detection]:
        """Associate detections with temporary track IDs across frames.

        Args:
            detections: Detections from the current frame.
            frame: Raw or preprocessed frame.

        Returns:
            List of Detections updated with temporary track_id.
        """
        pass
