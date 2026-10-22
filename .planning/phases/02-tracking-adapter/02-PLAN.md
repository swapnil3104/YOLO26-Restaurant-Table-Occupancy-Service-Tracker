# Phase 2: Tracking Adapter Plan

## Phase Goal
Integrate robust multi-object tracking (MOT) supporting ByteTrack and BoT-SORT algorithms via a decoupled `BaseTracker` adapter. Maintain transient track IDs across consecutive frames with occlusion tolerance and trajectory history, provide debug visualization overlays with motion tails, benchmark tracking overhead, document ID-switching and re-identification limitations, and provide deterministic mock tracking fixtures for CI/CD.

## Requirements Covered
- **FR-02: Person Detection & Tracking (Tracking Subsystem)**
  - Concrete tracker implementations adhering to `BaseTracker`:
    - `YOLO26Tracker`: Native integration with Ultralytics tracking engine supporting both ByteTrack (`bytetrack.yaml`) and BoT-SORT (`botsort.yaml`).
    - `ByteTrackAdapter`: Standalone/direct IoU and Kalman association tracker adapter.
    - `MockTracker`: Deterministic synthetic multi-frame tracker for headless testing without heavy dependencies or GPU.
  - Track persistence across short occlusions with configurable max-age / lost-frame tolerance (default: 30 frames / ~6 seconds at 5 FPS).
  - Trajectory history collection (`Dict[int, deque[Tuple[float, float]]]`) storing normalized centroid positions with max history length.
  - Track state and metadata management: track age, hit streak, track confidence, smoothed bottom-center anchor points.
  - Explicit documentation and enforcement of Rule 2 from `Docs/RULES.md`: **A temporary tracking ID is not a permanent person identity.** Track IDs are ephemeral session artifacts, never persistent biometric or facial IDs.
  - Debug visualization in `src/smartserve/vision/visualizer.py`:
    - Track ID badges on bounding boxes.
    - Trajectory path ribbons / breadcrumb tails with fading alpha.
    - Bottom-center ground/table contact point anchor rendering.
  - Tracker evaluation and benchmark report appended to `Docs/MODEL_EVALUATION.md`.
  - Replayable tracking test suite and synthetic trajectory fixtures in `tests/test_vision_tracker.py`.
  - Runnable tracking demo CLI script `scripts/demo_tracking.py`.

## Tasks Breakdown

1. **Tracker Architecture & Implementation (`src/smartserve/vision/tracker.py`)**:
   - `TrackState`: Active, Lost, Removed lifecycle enum.
   - `TrackedObject`: Encapsulates `track_id`, `bbox`, `confidence`, `class_name`, `age`, `hits`, `time_since_update`, and `trajectory` history.
   - `YOLO26Tracker`: Ultralytics model-level tracking adapter delegating to ByteTrack or BoT-SORT with track persistence across sequential frames.
   - `SimpleByteTracker`: Pure-Python / NumPy IoU + velocity Kalman/linear motion association tracker for lightweight CPU-only environments and deterministic tracking.
   - `MockTracker`: Deterministic tracker for unit tests generating synthetic IDs and trajectories across test sequences.
   - Expose tracking configuration options: `tracker_type` (`bytetrack` | `botsort`), `track_buffer` (max lost frames), `match_threshold` (minimum IoU association threshold).

2. **Trajectory History & Persistence**:
   - Maintain bounded sliding window of historical bottom-center contact points for each active track.
   - Track cleanup when `time_since_update > track_buffer`.
   - Track ID counter management and reset capabilities for stream restarts.

3. **Debug Visualization Enhancements (`src/smartserve/vision/visualizer.py`)**:
   - Enhance `draw_detection_overlay` / `draw_tracking_overlay` to render:
     - Color-coded bounding boxes per track ID.
     - Track ID label and confidence header.
     - Breadcrumb trajectory line connecting recent centroid/anchor coordinates.
     - Table contact point (`bottom_center`) highlighted.

4. **Tracking Evaluation & Documentation (`Docs/MODEL_EVALUATION.md`)**:
   - Evaluate ByteTrack vs. BoT-SORT: computational complexity, camera motion sensitivity (BoT-SORT uses camera motion compensation (GMC), ByteTrack uses pure IoU+Kalman).
   - Document ID-switch phenomena in dense restaurant scenes (patrons crossing paths, standing up, waiter tray occlusions).
   - Document privacy compliance: ephemeral IDs only, no re-identification across camera restarts.

5. **Tracking Demonstration & Verification Utility (`scripts/demo_tracking.py`)**:
   - Command-line tool to run video capture + detector + tracker pipeline on a video file or synthetic moving boxes, outputting tracked preview frames or summary statistics.

6. **Comprehensive Automated Test Suite (`tests/test_vision_tracker.py`)**:
   - Test single object straight-line tracking and ID stability across frames.
   - Test temporary occlusion (object disappears for 2-3 frames then reappears) verifying track ID preservation.
   - Test track expiration when object disappears longer than `track_buffer`.
   - Test multi-object crossing with IoU association.
   - Test tracker reset and state clearance.
   - Test integration between `VideoCapturePipeline`, `BaseDetector`, and `BaseTracker`.

## Verification Criteria
- [ ] Pytest suite passes all tracking unit tests without requiring GPU or internet downloads.
- [ ] A synthetic moving object is tracked across consecutive frames with the same track ID.
- [ ] Short occlusion preserves track ID across disappearance window.
- [ ] Visualizer renders colored boxes, track IDs, and trajectory trails cleanly.
- [ ] `Docs/MODEL_EVALUATION.md` contains tracker comparison and documented limitations.
