# SmartServe — Surveillance & Vision Refactor: Phase 1 Audit & Plan

**Document:** Phase 1 Audit Report  
**Version:** 1.0  
**Status:** Completed  
**Reference Specification:** `Docs/TASKS.md`  
**Date:** October 2026  

---

## Executive Summary

This audit establishes the baseline for refactoring the SmartServe **Surveillance & Vision** module into two distinct, high-performance views:
1. **Standard CCTV** (pure viewing only, zero AI inference or analytics side-effects)
2. **Tracking View** (fine-tuned YOLO26 inference, ByteTrack ID persistence, multi-floor source management, dynamic central & floor KPIs)

All existing code, routes, database models, computer vision pipelines, and frontend components were analyzed against the non-negotiable rules defined in `Docs/TASKS.md`.

---

## 1. Inventory of Current Modules, Routes & Architecture

### 1.1 Frontend Pages and Routes
- `frontend/src/App.tsx`:
  - Active navigation state (`activePage: 'dashboard' | 'cameras' | 'analytics'`).
  - Active page mapping:
    - `'dashboard'` ➔ `<DashboardPage />`
    - `'cameras'` ➔ `<SurveillanceVisionPage />` (labeled "Surveillance & Vision" in `Sidebar.tsx`)
    - `'analytics'` ➔ `<AnalyticsReportsPage />`
- `frontend/src/pages/SurveillanceVisionPage.tsx`:
  - Current monolith (931 lines) containing 4 layout modes:
    - `'split_dual'`: Dual Split (CCTV on left, annotated AI vision stream on right).
    - `'quad_grid'`: 4x Grid displaying 4 hardcoded cameras (`cam-01` to `cam-04`).
    - `'single_vision'`: Full AI Tracking View.
    - `'single_cctv'`: Pure CCTV view.
- `frontend/src/pages/LiveCameraPage.tsx`:
  - 295 lines. Standalone, orphaned CCTV viewer with layout modes `single`, `split`, `grid`. Unreferenced in `App.tsx`.
- `frontend/src/pages/CameraTrackPage.tsx`:
  - 363 lines. Standalone, orphaned CV Tracking viewer with overlay checkboxes (`showPersonBoxes`, `showTrackingIds`, `showTableRegions`, etc.). Unreferenced in `App.tsx`.
- `frontend/src/components/Sidebar.tsx`:
  - Exposes 3 main menu items:
    - `Floor Operations` (`dashboard`)
    - `Surveillance & Vision` (`cameras`)
    - `Performance & Reports` (`analytics`)

### 1.2 Backend API Endpoints
- **Cameras & Video Sources** (`src/smartserve/api/routes/cameras.py`):
  - `GET /api/v1/cameras`: Returns metadata for registered cameras (`cam-01` to `cam-04`).
  - `GET /api/v1/cameras/{id}`: Returns single camera metadata.
  - `GET /api/v1/cameras/{id}/stream/raw`: MJPEG stream without AI overlays.
  - `GET /api/v1/cameras/{id}/stream/processed`: MJPEG stream with YOLO overlays.
  - `GET /api/v1/cameras/{id}/snapshot`: Single JPEG frame snapshot.
  - `GET /api/v1/cameras/{id}/cv-metadata`: Latest frame detections, latency, tracking IDs, table states.
  - `GET /api/v1/cameras/video-sources`: Video source catalog and current user assignments.
  - `POST /api/v1/cameras/video-sources/assign`: Switch assigned video feeds for CCTV and tracking.
- **Tables & Occupancy**:
  - `GET /api/v1/tables`, `GET /api/v1/tables/{id}` (`src/smartserve/api/routes/tables.py`)
  - `GET /api/v1/occupancy/status`, `POST /api/v1/occupancy/override` (`src/smartserve/api/routes/occupancy.py`)
- **Events & Alerts**:
  - `GET /api/v1/events/timeline/{table_id}`, `POST /api/v1/events/confirm` (`src/smartserve/api/routes/events.py`)
  - `GET /api/v1/rules/alerts`, `POST /api/v1/rules/alerts/{id}/ack` (`src/smartserve/api/routes/rules.py`)
- **Analytics & Real-time**:
  - `GET /api/v1/analytics/summary`, `GET /api/v1/analytics/breakdown`, `GET /api/v1/analytics/export` (`src/smartserve/api/routes/analytics.py`)
  - `WS /api/v1/ws/live` (`src/smartserve/api/websocket.py`)

### 1.3 Database Models (`src/smartserve/database/models.py`)
- Existing tables:
  - `restaurants` (`restaurant_id`, `name`, `timezone`)
  - `cameras` (`camera_id`, `restaurant_id`, `name`, `source_type`, `status`, `last_seen_at`)
  - `tables` (`table_id`, `restaurant_id`, `table_code`, `capacity`, `camera_id`, `region_config`, `status`)
  - `users` (`user_id`, `username`, `display_name`, `role`, `active`)
  - `table_sessions` (`session_id`, `table_id`, `restaurant_id`, `started_at`, `ended_at`, `customer_count`, `first_attendance_at`, `first_food_delivery_at`)
  - `service_events` (`event_id`, `table_id`, `session_id`, `event_type`, `source`, `verification_status`, `created_by`, `timestamp`)
  - `alerts` (`alert_id`, `table_id`, `alert_type`, `severity`, `status`, `message`, `dedup_key`)
  - `waiter_assignments`, `audit_logs`
- **Notice on Floor Entity:** No `floors` table currently exists in the relational schema. Tables and cameras currently rely on a loose `section` string (e.g. `"Main Dining"`, `"Patio Terrace"`). Phase 7 will formalize `Floor` or add explicit floor association to `Camera` and `Table`.

---

## 2. Usages of Legacy Views & Safe Removal Candidates

| Target Feature / Mode | Current Location | Usages & Dependencies | Refactor Strategy (Phase 2 & 9) |
|---|---|---|---|
| **Dual Split (CCTV vs. Tracking)** | `SurveillanceVisionPage.tsx` (lines 313–441, mode: `'split_dual'`) | Layout toggle button, dual-pane flex grid rendering `raw_stream_url` and `processed_stream_url` side-by-side. | **Remove completely.** Replace navigation with two top-level views: `Standard CCTV` and `Tracking View`. |
| **Multi-Tracking** | `CameraTrackPage.tsx` (all) & `SurveillanceVisionPage.tsx` | Unrouted standalone page. Shows multi-camera pill selector and inference overlays. | **Merge into Tracking View.** `CameraTrackPage.tsx` is an orphaned candidate for deletion. |
| **AI Tracking View** | `SurveillanceVisionPage.tsx` (lines 752–870, mode: `'single_vision'`) | Fullscreen/focused view of processed AI feed with detection telemetry. | **Promote to primary Tracking View.** Enhance with multi-floor source management, dynamic floor KPI cards, and central metrics. |
| **Standard CCTV** | `SurveillanceVisionPage.tsx` (lines 872–920, mode: `'single_cctv'`) & `LiveCameraPage.tsx` | Mode displaying raw video without annotations. `LiveCameraPage.tsx` is unrouted. | **Promote to primary Standard CCTV View.** Support multi-feed grid, one-at-a-time source addition, fullscreen expand, zero AI jobs. Delete `LiveCameraPage.tsx`. |
| **4x Grid** | `SurveillanceVisionPage.tsx` (lines 592–750, mode: `'quad_grid'`) | Hardcoded 2x2 grid rendering `cam-01` through `cam-04`. | **Replace with dynamic responsive grid.** Allow 1, 2, 3, 4+ feeds in both views; eliminate fixed 4-camera cap. |

---

## 3. Camera Ingestion Mapping & Support Matrix

| Ingestion Mode | Backend Support | Frontend Status | Action Required |
|---|---|---|---|
| **Local Video Files (`.mp4`, `.avi`)** | Fully supported in `capture.py` (`VideoCapturePipeline`) and `cameras.py` (`Sample Video/`, `public/videos/`). | Video catalog modal partially implemented. | **Keep & Standardize.** Provide explicit file picker and local file preview. Distinguish recorded footage from live CCTV. |
| **Uploaded Video Files** | Not yet implemented in backend (no multipart upload endpoint). | UI upload modal started (`AddTrackingFootageModal`). | **Implement endpoint in Phase 7:** `POST /api/v1/cameras/upload` with size limits (max 200MB) and extension validation (`.mp4`, `.mov`). |
| **RTSP / IP Camera Streams** | Supported in `capture.py` (`rtsp://` handled via OpenCV `VideoCapture`). | Stream URL fields exist in video catalog. | **Keep.** Support authenticating RTSP streams (`rtsp://user:pass@host:port/h264`). Add connection timeout & reconnect loop. |
| **Local Webcam Device Index (`0, 1`)** | Supported in `capture.py` (`source=0` via OpenCV). | Not exposed cleanly in UI. | **Support for local testing only.** Clearly label as local test sensor. |
| **Browser Camera (getUserMedia / WebRTC)** | Unsupported in backend pipeline. | Inconsistent references in early docs. | **Explicitly mark unsupported** in UI to prevent user confusion. |

---

## 4. Fine-Tuned YOLO26 Model & Runtime Requirements

### 4.1 Checkpoint & Model Artifacts
- **Primary Model Checkpoint:** `models/yolo26_restaurant_cctv.pt` (File size: ~20.3 MB).
- **Base Architecture:** `yolo26s.pt` (Ultralytics YOLO small variant).
- **Fine-Tuning Configuration:** Documented in `models/training_summary.json` and `Docs/MODEL_FINETUNING.md`:
  - **Dataset:** `datasets/restaurant_cctv/data.yaml` (restaurant surveillance footage with occluded diners).
  - **Classes:** Single class `0: person` (specifically dining patrons and service staff seated or moving around tables).
  - **Performance:** `mAP50 = 0.7416`, `mAP50-95 = 0.413`, `Precision = 0.6761`, `Recall = 0.6786`.
- **Pretrained Fallback Weights:** `yolo26s.pt`, `yolo26n.pt` in project root.
- **Rule Enforcement:** Phase 5 will enforce that detection uses strictly `models/yolo26_restaurant_cctv.pt` or configured YOLO26 weights. Substituting generic mock detectors in production is strictly prohibited.

### 4.2 Inference Preprocessing & Postprocessing
- **Input Dimensions:** `INFERENCE_IMGSZ = 640` (640x640 letterbox). Supports `960` or `1280` for high-ceiling/distant feeds.
- **Coordinate System:** Absolute pixel bounding boxes from inference are normalized to unit range `[0.0, 1.0]` using `normalize_coordinates()` in `src/smartserve/vision/detector.py`.
- **Ground-Contact Calculation:** Bottom-center point of bounding box `( (x1+x2)/2, y2 )` is computed for point-in-polygon dining table association (`src/smartserve/tables/association.py`).
- **Confidence Threshold:** `0.28` (fine-tuned checkpoint exhibits high precision on partially occluded diners down to 0.25–0.30; standard 0.45 threshold drops too many seated patrons).
- **Tracking:** ByteTrack (`smartserve.vision.tracker.ByteTrackAdapter`) provides persistent track IDs across temporary table/patron occlusions.

---

## 5. KPI & Event Domain Hierarchy

To satisfy the non-negotiable rules for multi-floor and multi-camera operations, events and calculations are strictly partitioned into three scopes:

```
┌────────────────────────────────────────────────────────┐
│ 1. Restaurant-Level (Central Restaurant KPIs)          │
│    - Total Monitored Tables (sum across floors)        │
│    - Total Occupied Tables & Overall Occupancy Rate %  │
│    - Total Active Diners Count                         │
│    - Central Delay Rate % & Data Completeness %        │
│    - Weighted Median Attendance & Delivery Times       │
└───────────────────────────┬────────────────────────────┘
                            │ Aggregates (canonical deduplicated)
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. Floor-Level KPIs (Per-Floor Panels)                 │
│    - Floor Monitored Tables & Table Occupancy State    │
│    - Active Seated Diners on Floor                     │
│    - Floor Service Timers & Pending Alerts             │
│    - Floor Table Turnover Rate                         │
└───────────────────────────┬────────────────────────────┘
                            │ Ingests from
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. Source-Level Stream Telemetry                       │
│    - Camera Health (CONNECTED / DEGRADED / OFFLINE)    │
│    - Inference Latency (ms) & Effective FPS            │
│    - Per-Frame Bounding Boxes & ByteTrack IDs          │
│    - Table Edge Proximity & Bottom-Contact Points      │
└────────────────────────────────────────────────────────┘
```

### 5.1 Canonical KPI Formulas (`src/smartserve/analytics/service.py`)
1. **First Attendance Time:** `first_attendance_at - session.started_at` (Warning threshold: 300 sec / 5 min).
2. **Food Delivery Time:** `first_food_delivery_at - session.started_at` (Warning threshold: 1200 sec / 20 min).
3. **Occupancy Duration:** `ended_at - session.started_at` (Max threshold: 7200 sec / 2 hours).
4. **Table Utilization %:** `(Total Occupied Table-Minutes / (Window Minutes * Monitored Tables)) * 100`.
5. **Delay Rate %:** `(Delayed Sessions Count / Total Sessions) * 100`.
6. **Data Completeness %:** `(Sessions with Verified Attendance & Delivery / Total Completed Sessions) * 100`.
7. **Aggregation Guardrail:** Central restaurant KPIs must **never average percentages or medians directly**. Rates must be recalculated from raw numerators and denominators across active floors.

---

## 6. Baseline Verification & Action Plan

### 6.1 Baseline Test Results
- **Backend Test Suite (`pytest`):**
  - **102 passed** (all unit/integration tests green).
  - Passing modules: `test_fastapi_security`, `test_table_association`, `test_occupancy_state_machine`, `test_service_timers_and_rules`, `test_database_and_events`, `test_analytics_and_reports`, `test_finetuning_pipeline`, `test_table_edge_detector`, `test_vision_tracker`, `test_vision_detector`, `test_vision_capture`.
- **Frontend Build (`npm run build`):**
  - Currently blocked by missing placeholder files `AddTrackingFootageModal.tsx` and `trackingFootages.ts`, and outdated props in `App.tsx`.
  - Phase 2 will clean up navigation, remove obsolete files/code, and resolve build errors.

### 6.2 Safe Removal Candidates
1. `frontend/src/pages/LiveCameraPage.tsx` (Obsolete, unrouted).
2. `frontend/src/pages/CameraTrackPage.tsx` (Obsolete, unrouted).
3. `layoutMode === 'split_dual'` block in `frontend/src/pages/SurveillanceVisionPage.tsx`.
4. Hardcoded `quad_grid` 4-camera fixed array in `SurveillanceVisionPage.tsx`.
5. Unused imports and broken mock references in `App.tsx` and `DashboardPage.tsx`.

---

## 7. Next Steps: Phase 2 Execution Plan
- **Phase 2:** Redesign navigation and Surveillance & Vision UI into two primary views:
  1. `Standard CCTV` (viewing only)
  2. `Tracking View` (fine-tuned YOLO26 inference & monitoring)
- Remove `Dual Split` subpage, route, and exclusive logic.
- Place `Standard CCTV` first and `Tracking View` second.
- Support responsive multi-camera grids beyond 4 feeds.
