# 🔍 Model Feasibility and Evaluation Report

**Document:** Computer Vision & YOLO Evaluation Report  
**Version:** 1.0  
**Phase:** Phase 1 — Model and Video Feasibility  
**Date:** 2026-10-22  
**Status:** Approved  

---

## 1. Executive Summary

This feasibility report defines the model selection, licensing, hardware compatibility, and failure mode analysis for the SmartServe AI detection engine. In accordance with `ARCHITECTURE.md` Section 3.2 and `PRD.md` Section 9, vision detection is strictly decoupled from the core business logic via the `BaseDetector` interface.

Under the target "YOLO26" specification, the system strictly adopts the native **YOLO26** vision architecture released by Ultralytics (`ultralytics>=8.4.0`). YOLO26 introduces native end-to-end NMS-free dual-head inference, elimination of Distribution Focal Loss (DFL), and an optimized CPU runtime designed specifically for real-time edge hardware. The default baseline models are **YOLO26s** (`yolo26s.pt`, 9.5M params) for high-accuracy dining scene evaluation and **YOLO26n** (`yolo26n.pt`, 2.4M params) for ultra-low latency edge devices.

---

## 2. Model Selection and Runtime Compatibility

### 2.1 Specification Matrix

| Parameter | Specification | Notes / Rationale |
|---|---|---|
| **Model Framework** | Ultralytics YOLO26 (`ultralytics>=8.4.0`) | NMS-free native end-to-end architecture, unconstrained regression head, MuSGD optimizer. |
| **Default Weights** | `yolo26s.pt` (Small) | 9.5M parameters; 48.6 mAP; highly accurate detection of occluded seated diners in restaurant scenes. |
| **Edge Nano Weights** | `yolo26n.pt` (Nano) | 2.4M parameters; 40.9 mAP; ~1.7ms latency; optimal for low-power edge CPU/microcontrollers. |
| **Input Resolution** | 1280x720 downscaled / 640x640 letterboxed | Matches standard commercial IP/RTSP streams. |
| **Detection Classes** | Class 0 (`person`) | Strict class filtering; ignores table clutter, chairs, and decor. |
| **Coordinate System** | Normalized `[0.0, 1.0]` | Independent of camera native aspect ratio and resolution changes. |
| **License** | AGPL-3.0 (Ultralytics Open Source) / Enterprise License | Architectural decoupling ensures proprietary business code does not link directly to GPL constraints when deployed over network/service boundaries. |

### 2.2 Hardware Acceleration Matrix

| Hardware Tier | Target Runtime | Expected Latency | Recommended FPS |
|---|---|---|---|
| **Tier 1: Cloud/Server GPU** | NVIDIA T4 / A10 / RTX 4070 (CUDA 12+, TensorRT) | 4–8 ms / frame | 15–30 FPS |
| **Tier 2: Edge AI Box** | NVIDIA Jetson Orin Nano / Orin NX (JetPack 6, TensorRT) | 12–25 ms / frame | 5–10 FPS |
| **Tier 3: Commercial Mini PC** | Intel N100 / Core i5 12th+ (OpenVINO / ONNX CPU) | 35–65 ms / frame | 3–5 FPS |
| **Tier 4: Baseline CPU** | Standard Multi-core x86_64 / ARM64 (PyTorch CPU) | 45–90 ms / frame | 2–5 FPS |

*Note: SmartServe's operational requirement is 3 to 5 FPS per camera for occupancy tracking, well within Tier 3 and Tier 4 throughput limits.*

---

## 3. Decoupling & Interface Architecture

To ensure vendor lock-in avoidance:
1. `BaseDetector` defines the single entry point `detect(frame: np.ndarray) -> List[Detection]`.
2. Detections return normalized `BoundingBox(x1, y1, x2, y2, is_normalized=True)`.
3. Anchor points are derived:
   - `center_point`: `((x1 + x2) / 2, (y1 + y2) / 2)` — used for general movement vector.
   - `bottom_center`: `((x1 + x2) / 2, y2)` — used as the contact point for table polygon association (patron feet/seat ground plane).
4. `MockDetector` provides deterministic synthetic detections for automated CI/CD without downloading 20MB+ model weights.

---

## 4. Known Detection Failure Modes & Mitigation

In restaurant environments, camera feeds present unique visual artifacts:

| Failure Mode | Visual Cause | Mitigation Strategy in SmartServe |
|---|---|---|
| **1. Table Edge Occlusion** | Seated diners have their lower bodies occluded by table surfaces and chairs. | Detection threshold tuned to 0.40–0.45; tracking adapter (Phase 2) maintains track persistence; table association (Phase 3) associates upper-body anchors. |
| **2. Back-Turned Guests** | Head and back visible without facial features. | YOLO person class trained on diverse postures; persistence timer prevents dropped occupancy during orientation shifts. |
| **3. Patron Overlap / Density** | Tightly packed banquette seating causes bounding boxes to overlap. | Bounding box anchor points (`bottom_center`) map to distinct non-overlapping polygon table zones. |
| **4. Ambient Lighting Shifts** | Dim dining moods, candlelight, direct sunlight glare through windows. | Frame normalization in OpenCV capture pipeline; camera auto-exposure monitoring. |
| **5. Staff vs. Patron Ambiguity** | Waiters pausing at tables can temporarily look like seated guests. | Staff attendance confirmation (Phase 7) + short dwell vs. persistent session state machine (Phase 4). |

---

## 5. Verification & Acceptance Criteria (Phase 1)

- [x] Abstract detector interface decoupling verified.
- [x] Ultralytics YOLO26/11 runtime verified on Python 3.14 + OpenCV.
- [x] Resilient OpenCV capture with RTSP/video/webcam fallback built.
- [x] Coordinate normalization and boundary clamping enforced.
- [x] Actionable errors generated on invalid frames and missing feeds.

---

## 6. Multi-Object Tracking Evaluation (Phase 2)

### 6.1 Algorithm Comparison: ByteTrack vs. BoT-SORT

| Attribute | ByteTrack (`SimpleByteTracker` / `bytetrack.yaml`) | BoT-SORT (`botsort.yaml`) | SmartServe Recommendation |
|---|---|---|---|
| **Core Association Mechanism** | Two-stage IoU matching: associates high-confidence first, then low-confidence detections to recover occluded targets. | Enhanced Kalman filter + Camera Motion Compensation (GMC) + optional Re-ID appearance features. | **ByteTrack (Default)** for fixed restaurant ceiling cameras; **BoT-SORT** for panning/PTZ cameras. |
| **Computational Overhead** | Minimal (< 1.5 ms / frame on CPU). Pure bounding-box geometry and linear velocity. | Moderate to High (6–18 ms / frame). GMC calculates image feature optical flow (ORB/ECC). | ByteTrack allows running 5+ concurrent camera streams on baseline Intel Mini PCs without dropping frames. |
| **Occlusion Handling** | Recovers targets from low-confidence detections (down to `conf=0.15`) without appearance vectors. | Maintains track trajectories across long occlusions using Re-ID feature banks. | For restaurant dining rooms, static camera geometry makes ByteTrack's spatial IoU + velocity prediction sufficient for >95% of table approaches. |
| **Camera Motion Sensitivity** | Assumes static or slow camera mount. Shaking or PTZ will induce velocity noise. | Robust against camera panning, vibration, and focal changes via GMC. | Restaurant cameras are almost universally fixed ceiling dome mounts; GMC overhead is redundant. |

### 6.2 Known Tracking Failure Modes & Operational Limitations

1. **ID-Switching During Crossings (Diner Crossroads)**:
   - *Phenomenon*: When two guests walk past each other in narrow aisles with high bounding-box overlap (>0.6 IoU), their temporary track IDs may swap.
   - *Impact on SmartServe*: Negligible. SmartServe occupancy logic associates tracks with stationary **table polygons**; whether a walking diner is Track #1 or Track #2 does not alter table occupancy state.
2. **Table Edge and Seating Occlusion**:
   - *Phenomenon*: When a patron sits down, their lower torso and legs are occluded by the tabletop. The detection box height decreases by ~50%, causing an instantaneous center shift.
   - *Mitigation*: Anchor calculations use `bottom_center` grounded at the seat line; ByteTrack's secondary stage prevents track drop when confidence dips during sitting.
3. **Waiter Leaning & Object Occlusion**:
   - *Phenomenon*: Waiters carrying large trays or bending to clear dishes can momentarily overlap with seated diners.
   - *Mitigation*: `track_buffer` (default 30 frames / 6 seconds at 5 Hz) keeps diner track active even if completely hidden for up to 6 seconds.

### 6.3 Privacy Compliance & Identity Protection (Docs/RULES.md Rule 2)

- **Ephemeral Tracking IDs**: Track IDs are transient integer counters strictly scoped to the local camera process.
- **No Biometric or Facial Fingerprints**: Tracks are formed strictly from bounding-box spatial geometry and normalized coordinates. No face recognition, embeddings, or demographic classifiers are computed or stored.
- **No Cross-Camera Identity Persistence**: When a guest leaves Camera 1's field of view and enters Camera 2's coverage, they are assigned a fresh, independent track ID.
- **Auto-Expiry**: Track histories and trajectories are automatically pruned from memory upon track termination (`track.state == REMOVED`).

---

## 7. Custom Restaurant Fine-Tuning & Performance Optimization

### 7.1 Motivation
Generic COCO pretrained models (`yolo26s.pt`, `yolo11s.pt`) exhibit lower recall and depressed confidence scores (often dipping between 0.18–0.32) on seated diners because tabletops occlude the lower body, and moody indoor lighting creates deep shadows.

### 7.2 Dedicated Restaurant Fine-Tuning Pipeline
To resolve weak baseline performance, SmartServe introduces:
1. **Automated Frame Curation & Pseudo-Labeling (`scripts/prepare_finetuning_dataset.py`)**:
   - Samples diverse frames from restaurant CCTV footage.
   - Applies high-resolution (`imgsz=1280`) multi-scale teacher inference with low thresholds (`conf=0.22`) to capture occluded seated patrons.
   - Generates standardized Ultralytics dataset layout (`datasets/restaurant_cctv/`).
2. **Domain-Specific Training (`scripts/train_restaurant_yolo.py`)**:
   - Indoor lighting HSV augmentations (`hsv_s=0.6`, `hsv_v=0.4`) and mixup/mosaic augmentations to simulate table occlusion.
   - Conservative fine-tuning learning rate (`lr0=0.001`) with warmup to preserve general human anatomy representations.
   - Automatically exports production weights to `models/yolo26_restaurant_cctv.pt`.
3. **Comparative Evaluation (`scripts/evaluate_finetuned_model.py`)**:
   - Generates side-by-side visual composites comparing baseline vs. fine-tuned detections.
   - Generates quantitative reports in `evaluation_results/` detailing recall gain, seated diner confidence, and latency.

