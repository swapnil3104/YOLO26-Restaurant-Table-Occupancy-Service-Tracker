"""Vision pipeline: ingestion, detection adapters, tracking, and table association."""

from smartserve.vision.benchmark import BenchmarkResult, benchmark_detector
from smartserve.vision.capture import (
    CameraConnectionError,
    CameraStatus,
    FramePacket,
    InvalidFrameError,
    VideoCaptureError,
    VideoCapturePipeline,
    VideoSourceNotFoundError,
)
from smartserve.vision.detector import (
    MockDetector,
    YOLO26Detector,
    denormalize_box,
    normalize_coordinates,
)
from smartserve.vision.interfaces import BaseDetector, BaseTracker, BoundingBox, Detection
from smartserve.vision.visualizer import draw_detection_overlay

__all__ = [
    "BaseDetector",
    "BaseTracker",
    "BenchmarkResult",
    "BoundingBox",
    "CameraConnectionError",
    "CameraStatus",
    "Detection",
    "FramePacket",
    "InvalidFrameError",
    "MockDetector",
    "VideoCaptureError",
    "VideoCapturePipeline",
    "VideoSourceNotFoundError",
    "YOLO26Detector",
    "benchmark_detector",
    "denormalize_box",
    "draw_detection_overlay",
    "normalize_coordinates",
]
