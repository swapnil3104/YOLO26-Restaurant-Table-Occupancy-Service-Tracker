# Phase 1: Model and Video Feasibility Plan

## Phase Goal
Implement resilient video capture with OpenCV, build a decoupled detection architecture supporting YOLO models (with fallback and mock modes), normalize person detections to unit coordinates `[0.0, 1.0]`, implement debug visualization overlays, benchmark latency and throughput, and document model evaluation results.

## Requirements Covered
- **FR-01: Video Ingestion & Sampling**
  - OpenCV capture for video file, webcam, and RTSP stream.
  - Bounded frame sampling rate (default 5 Hz) with monotonic timestamping.
  - Camera metadata encapsulation (`FramePacket`).
  - Actionable error handling for invalid frames, missing source, and stream EOF.
- **FR-02: Person Detection & Tracking (Detection Subsystem)**
  - Abstract `BaseDetector` interface compliance.
  - Concrete `YOLO26Detector` implementing Ultralytics YOLO with configurable model weights (`yolo11n.pt` / `yolo8n.pt`).
  - Configurable confidence threshold, target classes (`person`), and device selection (`cpu`, `cuda`, `mps`).
  - Normalized bounding boxes (`BoundingBox(x1, y1, x2, y2, is_normalized=True)`).
  - Calculated anchor points: center `(cx, cy)` and ground/table contact point `(cx, y2)`.
  - Debug visualization utility with bounding boxes, confidence labels, and anchor dots.
  - Robust inference benchmarking script capturing latency (p50, p95, p99), FPS, and resource utilization.
  - Comprehensive documentation in `Docs/MODEL_EVALUATION.md`.

## Tasks Breakdown
1. **Model & Architecture Evaluation Document (`Docs/MODEL_EVALUATION.md`)**:
   - Document YOLO26 runtime specification, Ultralytics engine compatibility, model licensing (AGPL-3.0 / Enterprise), weights selection, and target hardware matrix.
   - Document known detection failure modes (severe table occlusion, back-turned patrons, low-light seating, waiter/guest disambiguation limitations).
2. **Video Capture Subsystem (`src/smartserve/vision/capture.py`)**:
   - `FramePacket` dataclass: `frame`, `frame_index`, `timestamp_ms`, `timestamp_utc`, `camera_id`, `width`, `height`, `fps`.
   - `VideoCapturePipeline`: thread-safe / generator-based capture from file or stream, rate-limiting to `FRAME_SAMPLE_RATE_HZ`, graceful degradation on read errors.
3. **Detection Subsystem (`src/smartserve/vision/detector.py`)**:
   - Concrete `YOLO26Detector` inheriting from `BaseDetector`.
   - `MockDetector` for deterministic unit testing without deep learning weight downloads.
   - Coordinate normalization to `[0.0, 1.0]` relative to frame resolution.
   - Anchors: `center_point` and `bottom_center` (ground contact).
4. **Debug Visualization Overlay (`src/smartserve/vision/visualizer.py`)**:
   - `draw_detection_overlay`: render labeled bounding boxes, confidence tags, contact point indicators, and performance overlay (FPS/timestamp).
5. **Inference Benchmarking Tool (`scripts/benchmark_vision.py` & `src/smartserve/vision/benchmark.py`)**:
   - Synthetic frame generation and sample video benchmarking.
   - Computes warmup time, mean latency, p50, p95, p99 latency, and effective FPS.
6. **Comprehensive Test Suite (`tests/test_vision_capture.py`, `tests/test_vision_detector.py`)**:
   - Tests for video capture with mock/synthetic video generator.
   - Tests for coordinate normalization and boundary clamps.
   - Tests for invalid frames and error handling.
   - Tests for detector interface contract compliance.
