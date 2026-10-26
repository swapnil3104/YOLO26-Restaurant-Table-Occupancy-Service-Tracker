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
from smartserve.vision.tracker import (
    MockTracker,
    SimpleByteTracker,
    TrackedObject,
    TrackState,
    YOLO26Tracker,
    calculate_iou,
)
from smartserve.vision.visualizer import (
    draw_detection_overlay,
    draw_spatial_association_overlay,
    draw_table_zones_overlay,
    draw_tracking_overlay,
    get_track_color,
)

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
    "MockTracker",
    "SimpleByteTracker",
    "TrackState",
    "TrackedObject",
    "VideoCaptureError",
    "VideoCapturePipeline",
    "VideoSourceNotFoundError",
    "YOLO26Detector",
    "YOLO26Tracker",
    "benchmark_detector",
    "calculate_iou",
    "denormalize_box",
    "draw_detection_overlay",
    "draw_spatial_association_overlay",
    "draw_table_zones_overlay",
    "draw_tracking_overlay",
    "get_track_color",
    "normalize_coordinates",
]
