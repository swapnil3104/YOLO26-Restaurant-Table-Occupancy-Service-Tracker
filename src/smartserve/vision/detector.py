"""Concrete detector implementations conforming to BaseDetector.

Includes:
- YOLO26Detector: Concrete Ultralytics YOLO adapter with coordinate normalization.
- MockDetector: Deterministic synthetic detector for testing and headless CI.
"""

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np

from smartserve.vision.interfaces import BaseDetector, BoundingBox, Detection

logger = logging.getLogger(__name__)


def normalize_coordinates(
    x1: float, y1: float, x2: float, y2: float, frame_width: int, frame_height: int
) -> BoundingBox:
    """Normalize absolute pixel coordinates to unit range [0.0, 1.0] with clamping.

    Args:
        x1: Left pixel x.
        y1: Top pixel y.
        x2: Right pixel x.
        y2: Bottom pixel y.
        frame_width: Total image width in pixels.
        frame_height: Total image height in pixels.

    Returns:
        Clamped, normalized BoundingBox instance.
    """
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError(
            f"Invalid frame dimensions ({frame_width}x{frame_height}) for normalization."
        )

    # Normalize
    norm_x1 = max(0.0, min(1.0, float(x1) / frame_width))
    norm_y1 = max(0.0, min(1.0, float(y1) / frame_height))
    norm_x2 = max(0.0, min(1.0, float(x2) / frame_width))
    norm_y2 = max(0.0, min(1.0, float(y2) / frame_height))

    # Ensure x1 <= x2 and y1 <= y2
    if norm_x1 > norm_x2:
        norm_x1, norm_x2 = norm_x2, norm_x1
    if norm_y1 > norm_y2:
        norm_y1, norm_y2 = norm_y2, norm_y1

    return BoundingBox(
        x1=norm_x1,
        y1=norm_y1,
        x2=norm_x2,
        y2=norm_y2,
        is_normalized=True,
    )


def denormalize_box(
    bbox: BoundingBox, frame_width: int, frame_height: int
) -> tuple[int, int, int, int]:
    """Convert normalized BoundingBox to absolute pixel integers (x1, y1, x2, y2)."""
    if not bbox.is_normalized:
        return (int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2))

    return (
        int(round(bbox.x1 * frame_width)),
        int(round(bbox.y1 * frame_height)),
        int(round(bbox.x2 * frame_width)),
        int(round(bbox.y2 * frame_height)),
    )


class YOLO26Detector(BaseDetector):
    """Ultralytics YOLO detector adapter with person filtering and normalized output."""

    def __init__(
        self,
        model_path: str = "yolo26s.pt",
        confidence_threshold: float = 0.35,
        target_classes: Sequence[str | int] | None = None,
        device: str | None = None,
        imgsz: int = 640,
    ) -> None:
        """Initialize YOLO26Detector.

        Args:
            model_path: Path to model weights or Ultralytics model tag (e.g. yolo11n.pt).
            confidence_threshold: Minimum detection confidence score (0.0 to 1.0).
            target_classes: Classes to detect. Defaults to ['person'].
            device: Compute device ('cpu', 'cuda:0', 'mps', or None for auto).
            imgsz: Input resolution for inference (default: 640, supports 960, 1280 for distant diners).
        """
        self.model_path = model_path
        self.confidence_threshold = float(confidence_threshold)
        self.target_classes = list(target_classes) if target_classes else ["person"]
        self.device = device
        self.imgsz = int(imgsz)
        self._model: Any | None = None

    def _ensure_loaded(self) -> Any:
        """Lazy load the underlying model."""
        if self._model is None:
            try:
                from pathlib import Path

                from ultralytics import YOLO

                # Resolve model path if not directly found
                resolved_path = Path(self.model_path)
                if not resolved_path.exists():
                    # Check relative to project root or common locations
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    cand = project_root / self.model_path
                    if cand.exists():
                        resolved_path = cand
                    else:
                        cand_models = project_root / "models" / self.model_path
                        if cand_models.exists():
                            resolved_path = cand_models

                logger.info(
                    "Loading YOLO model '%s' on device %s (imgsz=%d)...",
                    str(resolved_path),
                    self.device or "auto",
                    self.imgsz,
                )
                self._model = YOLO(str(resolved_path))
            except Exception as exc:
                logger.error("Failed to load YOLO model from %s: %s", self.model_path, exc)
                raise RuntimeError(
                    f"Could not load YOLO model from '{self.model_path}': {exc}"
                ) from exc
        return self._model

    def detect(self, frame: Any) -> list[Detection]:
        """Run object detection on an OpenCV frame.

        Args:
            frame: OpenCV image array (numpy.ndarray).

        Returns:
            List of normalized Detection objects.

        Raises:
            ValueError: If frame is None, non-array, or has invalid dimensions.
        """
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("Invalid frame passed to detector: frame must be a numpy.ndarray.")

        if frame.ndim < 2 or frame.shape[0] <= 0 or frame.shape[1] <= 0:
            raise ValueError(
                f"Invalid frame dimensions passed to detector: shape is {getattr(frame, 'shape', None)}"
            )

        model = self._ensure_loaded()
        frame_height, frame_width = frame.shape[:2]

        # Run inference with verbose=False
        results = model.predict(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            imgsz=self.imgsz,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results:
            return detections

        result = results[0]
        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            return detections

        # Extract names dictionary
        names_dict = result.names or {}

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            class_name = names_dict.get(cls_id, str(cls_id))

            # Filter for target classes if specified
            if (
                self.target_classes
                and class_name not in self.target_classes
                and cls_id not in self.target_classes
            ):
                continue

            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = xyxy[:4]

            norm_bbox = normalize_coordinates(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                frame_width=frame_width,
                frame_height=frame_height,
            )

            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=conf,
                    bbox=norm_bbox,
                    metadata={
                        "raw_box": [float(x1), float(y1), float(x2), float(y2)],
                        "class_id": cls_id,
                    },
                )
            )

        return detections


class MockDetector(BaseDetector):
    """Deterministic synthetic detector for tests and headless validation."""

    def __init__(self, predefined_detections: list[Detection] | None = None) -> None:
        """Initialize mock detector.

        Args:
            predefined_detections: Fixed detections to return on every call,
                or None to generate a default synthetic person detection.
        """
        self.predefined_detections = predefined_detections

    def detect(self, frame: Any) -> list[Detection]:
        """Return predefined or synthetic detections."""
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("Frame must be a valid numpy.ndarray.")

        if self.predefined_detections is not None:
            return list(self.predefined_detections)

        # Generate a default synthetic centered person detection
        return [
            Detection(
                class_name="person",
                confidence=0.92,
                bbox=BoundingBox(x1=0.35, y1=0.20, x2=0.65, y2=0.85, is_normalized=True),
                metadata={"synthetic": True},
            )
        ]
