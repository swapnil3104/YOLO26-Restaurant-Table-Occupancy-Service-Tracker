# Phase 1: Model and Video Feasibility Summary

**Phase Completed:** Phase 1 — Model and Video Feasibility  
**Date:** 2026-10-22  
**Status:** Complete  

## Deliverables Completed
1. **Model & Architecture Evaluation (`Docs/MODEL_EVALUATION.md`)**:
   - Documented the YOLO26 moniker binding to Ultralytics modern YOLO runtime (`yolo11n.pt` / `yolo8n.pt`).
   - Defined hardware tiers and throughput requirements (3–5 FPS operational minimum).
   - Documented restaurant camera failure modes (seated occlusion, back-facing patrons, lighting shifts) and their mitigations.
2. **Resilient Video Capture Pipeline (`src/smartserve/vision/capture.py`)**:
   - Built `VideoCapturePipeline` supporting local video files, webcams, and RTSP streams.
   - Enriched frames with `FramePacket` metadata: UTC timestamps, millisecond positions, camera IDs, resolution, and native FPS.
   - Built rate-limiting based on `FRAME_SAMPLE_RATE_HZ` to throttle ingestion without pipeline lag.
   - Actionable exceptions: `VideoSourceNotFoundError`, `CameraConnectionError`, `InvalidFrameError`.
3. **Decoupled Detection Engine (`src/smartserve/vision/detector.py`)**:
   - `YOLO26Detector`: Concrete adapter for Ultralytics YOLO with lazy weight loading and person class filtering.
   - `MockDetector`: Deterministic synthetic detector for headless CI and isolated unit testing.
   - `normalize_coordinates()`: Unit-interval `[0.0, 1.0]` coordinate normalization with boundary clamping.
   - `denormalize_box()`: Pixel coordinate conversion for display overlays.
   - Standardized anchor points: `center_point` and `bottom_center` (ground contact anchor for table polygons).
4. **Debug Visualization Overlay (`src/smartserve/vision/visualizer.py`)**:
   - `draw_detection_overlay()`: Renders labeled boxes, confidence percentages, ground contact dots, and FPS/camera telemetry banner.
5. **Vision Benchmarking CLI & Library (`src/smartserve/vision/benchmark.py`, `scripts/benchmark_vision.py`)**:
   - Timed benchmark collecting warmup latency, mean, p50, p95, and p99 percentiles, and throughput FPS.
   - Automatic platform hardware detection (OS, Python, PyTorch version, CUDA status).
   - JSON and Markdown table export options.
6. **Automated Test Suite (`tests/test_vision_capture.py`, `tests/test_vision_detector.py`, `tests/test_vision_benchmark.py`)**:
   - 17 unit tests passing with 100% success covering synthetic video reading, coordinate clamping, error handling, mock detection, and benchmark calculations.

## Next Phase
**Phase 2: Tracking Adapter** — Integration of ByteTrack / BoT-SORT to maintain temporary track IDs across frames and survive brief visual occlusions.
