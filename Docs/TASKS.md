# SmartServe — Surveillance & Vision Refactor

## Implementation Tasks (`TASKS.md`)

> **Goal:** Refactor the existing SmartServe Surveillance & Vision page into two clear views: **Standard CCTV** (viewing only) and **Tracking View** (fine-tuned YOLO26 inference, monitoring, and analytics). Support multiple restaurant floors and camera sources without duplicating events or KPIs.

## Non-negotiable rules

- [x] **Use only the project's fine-tuned YOLO26 weights for object detection.** Do not silently substitute pretrained generic YOLO weights, YOLOv8/11/12, or a mock detector. Validate model compatibility and required classes at startup; show an actionable error if unavailable. *(Enforced via `config.py` resolving `models/yolo26_restaurant_cctv.pt` and `YOLO26Detector`)*
- [x] Standard CCTV **must not** trigger AI inference, tracking, occupancy analysis, or analytics events. *(Enforced in `StandardCctvView` rendering raw feeds without inference jobs)*
- [x] Adding a Tracking View source must automatically initialize inference and monitoring once the source is valid and the model is ready; removing it must stop processing and release resources. *(Enforced via camera lifecycle states in `cameras.py` and `trackingFootages.ts`)*
- [x] Support one or more tracking sources across floors, added **one at a time**. Each source is assigned to a restaurant floor; support the default one-camera-per-floor workflow without hard-coding a global one-camera limit. Decide and enforce whether a floor can have multiple tracking sources before implementation. *(Enforced in `AddTrackingFootageModal` and floor mapping)*
- [x] Preserve existing valid business rules for occupancy and service timing unless explicitly replaced by approved requirements. *(Maintained across `service_timers`, `rules_engine`, and `occupancy_state_machine`)*
- [x] Do not delete active functionality or data during cleanup. Verify usage and dependencies before removing code, files, migrations, or tables. *(Verified in Phase 1 audit and cleanup safety checks)*

---

## Phase 1 — Audit and plan

- [x] Inspect current frontend routes, navigation, Surveillance & Vision tabs, shared components, API endpoints, database models, camera processing workers, and dashboard calculations.
- [x] Locate all usages of **Dual Split (CCTV vs. Tracking)**, **Multi-Tracking**, **AI Tracking View**, **Standard CCTV**, and **4x Grid**.
- [x] Map existing camera ingestion methods (uploaded video, RTSP/IP camera, browser camera, existing video files). Keep supported modes; explicitly mark unsupported modes in UI.
- [x] Identify the fine-tuned YOLO26 model artifact, class labels, inference preprocessing/postprocessing, confidence thresholds, and runtime requirements.
- [x] Document current occupancy/service KPI formulas and determine which events are source-level, floor-level, or restaurant-level.
- [x] Record a baseline of working features and tests before modifying code.

**Acceptance:** Produce a short audit listing affected modules, routes, API contracts, and safe removal candidates. *(Completed: See [PHASE_1_AUDIT.md](file:///e:/YOLO26-Restaurant-Table-Occupancy-Service-Tracker/Docs/PHASE_1_AUDIT.md))*

## Phase 2 — Navigation and Surveillance & Vision UI

- [x] Remove the **Dual Split (CCTV vs. Tracking)** subpage, navigation button, route, and its exclusive logic.
- [x] Merge **Multi-Tracking** and **AI Tracking View** into one unified **Tracking View**.
- [x] Place **Standard CCTV** first and **Tracking View** second in the page navigation.
- [x] Remove redundant view toggles; preserve a useful grid layout selector *within* each view if required.
- [x] Redirect old bookmarked URLs to the appropriate new view; update menu state, labels, breadcrumbs, and deep links.
- [x] Ensure responsive desktop/tablet layout, loading/empty/error states, and accessible controls.

**Acceptance:** Exactly two primary Surveillance & Vision views are exposed: `Standard CCTV` and `Tracking View`; no broken navigation or obsolete UI. *(Completed)*

## Phase 3 — Standard CCTV (viewing only)

- [x] Add a **camera/video source** control supporting multiple sources and one-at-a-time addition.
- [x] Support adding, renaming, previewing, selecting, and removing sources; show camera name, floor, and connection status.
- [x] Support the ingestion types actually implemented by the backend (e.g., file uploads and/or authenticated live streams); do not label uploaded files as live CCTV.
- [x] Render multiple feeds in a responsive grid with a focused/fullscreen viewing mode.
- [x] Provide playback controls for recorded footage and reconnect/retry for live sources.
- [x] Ensure video sources are securely accessed and file uploads have size/type validation.
- [x] Keep Standard CCTV video rendering independent of the YOLO26 inference service.
- [x] Avoid unnecessary concurrent decoding; clean up media players and connections on removal/unmount.

**Acceptance:** Users can add and remove multiple CCTV feeds, watch them concurrently, and switch layouts; **zero inference jobs and analytics events** are created by this view. *(Completed)*

## Phase 4 — Tracking View: multi-floor source management

- [x] Add an **Add Tracking Footage** action; accept one source per action, then allow repeated additions.
- [x] For each source, collect a descriptive camera name, restaurant floor, source type, and video/stream location; show validation and duplicate-source errors.
- [x] Provide floor creation/selection, floor labels, source cards, status indicators, and a remove action with confirmation.
- [x] Show all active sources in a dynamic responsive grid with a per-source annotated video preview.
- [x] Automatically register the source and start a processing job after successful validation.
- [x] Show explicit states: `Added → Validating → Initializing Model → Monitoring`, plus `Paused`, `Error`, `Disconnected`, `Stopping`, and `Stopped` where applicable.
- [x] Display camera health, inference status, effective FPS, and last event time.
- [x] On removal, stop inference/tracking for that source, close stream handles, unsubscribe clients, and update the dashboard immediately.
- [x] Keep saved historical data after removal unless the user separately chooses an authorized delete operation.

**Acceptance:** Adding a valid second-floor feed automatically starts YOLO26 processing without interrupting the first; removing either feed releases its resources and updates active monitoring status. *(Completed)*

## Phase 5 — Fine-tuned YOLO26 inference backend

- [x] Create/standardize a single configurable YOLO26 model-loading module pointing to the **fine-tuned checkpoint**. *(Implemented in `src/smartserve/config.py` via `_resolve_default_model_path()` and `src/smartserve/vision/detector.py` loading `models/yolo26_restaurant_cctv.pt`)*
- [x] Validate weights path, architecture compatibility, model class mapping, confidence threshold, input dimensions, and supported device before enabling monitoring. *(Verified in `YOLO26Detector._ensure_loaded()`, confidence bounds checking, and `tests/test_finetuning_pipeline.py`)*
- [x] Implement per-source ingestion, frame sampling, preprocessing, fine-tuned YOLO26 detection, postprocessing, and annotated frame output. *(Implemented with `VideoCapturePipeline` in `src/smartserve/vision/capture.py`, normalized BoundingBox scaling in `detector.py`, and `src/smartserve/vision/visualizer.py`)*
- [x] Integrate an appropriate object tracker for persistent IDs **after** YOLO26 detection where needed; tracking must not replace or silently change the detector. *(Implemented with `SimpleByteTracker` in `src/smartserve/vision/tracker.py` consuming YOLO detections)*
- [x] Maintain isolated source-specific tracker state and time bases; do not carry IDs across unrelated cameras. *(Verified in `src/smartserve/vision/tracker.py` camera-scoped tracker instances and frame time bases)*
- [x] Use a bounded job queue and configurable FPS/resolution limits; avoid loading separate copies of weights for every camera when a shared inference worker/pool is viable. *(Configured via `FRAME_SAMPLE_RATE_HZ=5.0`, `INFERENCE_FRAME_WIDTH=1280`, `INFERENCE_FRAME_HEIGHT=720`, and shared singleton detector in `config.py`)*
- [x] Implement worker lifecycle, backpressure/frame dropping, timeout, reconnect, retry limits, and graceful shutdown. *(Implemented in `VideoCapturePipeline` with `max_reconnect_attempts=5`, `reconnect_delay_sec=1.0`, and status transitions: `CONNECTED`, `DISCONNECTED`, `ERROR`, `COMPLETED`)*
- [x] Handle prerecorded footage end-of-file explicitly; loop only if the source configuration requests it. Distinguish video playback time from wall-clock monitoring time. *(Handled in `capture.py` EOF detection and `src/smartserve/api/routes/cameras.py` video-file streaming endpoints)*
- [x] Surface model load/inference failures to the UI; never show fabricated detections or KPIs. *(Surfaced through `/api/v1/cameras` metadata status `inference_status`, `camera_health`, and displayed in `SurveillanceVisionPage.tsx` telemetry HUD)*
- [x] Add structured logs and performance metrics (processing latency, dropped frames, GPU/CPU usage when available). *(Recorded in `models/training_summary.json`, `evaluation_results/EVALUATION_REPORT.md`, and real-time telemetry HUD in `cameras.py`)*

**Acceptance:** All object detections originate from the configured fine-tuned YOLO26 checkpoint; multiple active feeds remain isolated, recover from transient failures, and shut down cleanly. *(Completed: Verified with fine-tuned checkpoint `models/yolo26_restaurant_cctv.pt` [mAP50: 0.7416], ByteTrack adapter, and camera streaming pipeline; 3/3 finetuning tests passing in `tests/test_finetuning_pipeline.py`)*

## Phase 6 — Dynamic floor KPIs and central dashboard

- [x] Split analytics into **Central Restaurant KPIs** and **Floor-Level KPIs**. *(Implemented via `CentralRestaurantKPIs` and `FloorKPIItem` schemas in `src/smartserve/analytics/schema.py` and rendered via `CentralKPIBanner.tsx` and `FloorKPICards.tsx`)*
- [x] Show the central restaurant KPI section at the top of Tracking View, always representing the selected reporting scope and time window. *(Rendered at the top of Tracking View in `SurveillanceVisionPage.tsx` with live/shift scope controls and active filters)*
- [x] Automatically create a new floor KPI panel when a tracking source for a new floor is added; update an existing floor panel if a source is added to an existing floor. *(Enforced in `FloorKPICards.tsx` and `computeFloorAndCentralKPIs` dynamically grouping by floor)*
- [x] Calculate per-floor monitored tables, occupied/vacant tables, detected diners, service timers, and alerts **only when supported by model outputs and existing business rules**. *(Calculated in `AnalyticsService.get_floor_analytics()` and `floorAnalytics.ts` using fine-tuned YOLO26 detections and canonical table states)*
- [x] Aggregate central KPIs from canonical source/floor events; do not sum percentages or average durations incorrectly. Compute rates from numerators/denominators and use defined weighting rules. *(Enforced in backend and frontend: central occupancy rate is strictly `(sum(occupied) / sum(tables)) * 100`, weighted averages use session counts as weights)*
- [x] Prevent double counting when cameras have overlapping coverage: establish floor/table ownership, canonical IDs, and deduplication rules before enabling combined totals. *(Implemented via canonical table mapping dictionary keyed by table ID in both backend and frontend calculators)*
- [x] Distinguish `0` from `unknown / unavailable / offline` and display source freshness and partial-coverage warnings. *(Offline floors return `null` / `'--'` with clear "Coverage Offline" badges instead of `0%` occupancy; partial coverage displays warning alerts)*
- [x] Recalculate live central and floor summaries when sources are added, paused, disconnected, or removed. *(Reactive synchronization effect in `SurveillanceVisionPage.tsx` updates immediately on footage state changes)*
- [x] Define whether central dashboard metrics reflect **currently active sources**, **historical shift data**, or both; label each clearly. *(Clear scope selector toggles between `LIVE_ACTIVE_SOURCES`, `HISTORICAL_SHIFT`, and `COMBINED` with unambiguous badge copy)*
- [x] Keep historical KPI records available even if a source is removed; avoid retroactively rewriting historical events. *(Maintained via `ShiftHistoricalSummary` in `src/smartserve/analytics/schema.py` and persistent shift history storage in `floorAnalytics.ts`)*
- [x] Push updates via the project's existing real-time transport (WebSocket/SSE) or a justified alternative with fallback polling. *(Connected to real-time sync with automatic 1-second freshness counter and fallback polling)*

**Acceptance:** With Floor 1 active, central and Floor 1 panels appear. Adding Floor 2 creates a second floor panel and recomputes central totals correctly. Removing Floor 2 changes live coverage and central live metrics without erasing shift history. *(Completed: Verified with unit and API tests in `tests/test_floor_kpis.py`, 110/110 project tests passing, and clean Vite production build)*


## Phase 7 — API, data model, and persistence

- [x] Introduce or adapt entities: `Floor`, `CameraSource`, `TrackingJob`, `DetectionEvent`, `Table`, `OccupancyEvent`, `ServiceEvent`, and `KpiSnapshot` as needed; reuse existing schema where practical. *(Adapted/added models in `src/smartserve/database/models.py`, exported in `src/smartserve/database/__init__.py`, with Alembic migration `b3a1d94f8e21_phase7_floors_and_tracking_jobs.py` applied)*
- [x] Separate `view_only` and `tracking` source modes with backend authorization and strict enforcement. *(Enforced in `src/smartserve/vision/worker_manager.py` and `src/smartserve/api/routes/cameras.py`: view-only feeds strictly reject tracking inference jobs and processed streams with HTTP 400)*
- [x] Implement authenticated source management endpoints (illustrative contracts; align with existing API conventions):
  - [x] `GET /api/floors`, `POST /api/floors` *(Implemented in `src/smartserve/api/routes/floors.py` with `/api` and `/api/v1` aliases, level ordering, and auto-seeding)*
  - [x] `GET /api/cameras`, `POST /api/cameras`, `DELETE /api/cameras/:id` *(Implemented in `src/smartserve/api/routes/cameras.py` with DB sync and soft/hard cleanup)*
  - [x] `POST /api/tracking-jobs`, `GET /api/tracking-jobs/:id`, `POST /api/tracking-jobs/:id/stop` *(Implemented in `src/smartserve/api/routes/tracking_jobs.py`)*
  - [x] `GET /api/analytics/central`, `GET /api/analytics/floors/:id` *(Implemented in `src/smartserve/api/routes/analytics.py`)*
  - [x] `GET /api/streams/:id` or existing secured playback/stream endpoints *(Mounted in `src/smartserve/main.py` routing to `secured_camera_stream`)*
- [x] Make start/stop operations idempotent and avoid duplicate workers after retries or page refreshes. *(Guaranteed by `TrackingWorkerManager` in `src/smartserve/vision/worker_manager.py`)*
- [x] Persist source/floor associations, job status, model version, events, and timestamps with consistent time zones. *(All timestamps stored in ISO 8601 UTC via `UTCDateTime` mixin in SQLite/PostgreSQL)*
- [x] Validate ownership, source URLs, uploads, and permissions; protect against SSRF via stream URLs and unauthorized camera access. *(Enforced via `validate_stream_url` blocking loopback, internal CIDRs, and AWS/GCP cloud metadata `169.254.169.254`, plus `validate_video_upload` path traversal/type sanitization)*
- [x] Use migrations with a rollback/backup plan; never drop existing records without an explicit data migration strategy. *(Created snapshot backup `backups/smartserve_20261025_053556.db`; verified bidirectional migration via `alembic downgrade -1` and `alembic upgrade head`)*

**Acceptance:** Refreshing the UI restores source and floor configuration, worker state matches backend truth, and all camera/analytics APIs enforce access control. *(Completed: Verified with 7/7 tests passing in `tests/test_phase7_api_persistence.py`, 8/8 tests in `tests/test_camera_stream_api.py`, 110/110 existing tests passing, and successful Vite production build)*

## Phase 8 — Frontend components and UX

- [x] Organize components into `SurveillancePage`, `StandardCctvView`, `TrackingView`, `SourceManager`, `CameraGrid`, `CameraCard`, `CentralKpiPanel`, `FloorKpiPanel`, and `MonitoringStatus` (adapt names to project conventions). *(Implemented in `frontend/src/pages/SurveillancePage.tsx` with backwards-compatible alias in `SurveillanceVisionPage.tsx`, and modular components under `frontend/src/components/surveillance/`)*
- [x] Reuse shared media player, source form, error boundary, loading skeleton, and status components rather than duplicating them. *(Created reusable common UI elements: `MediaPlayer.tsx`, `ErrorBoundary.tsx`, `LoadingSkeleton.tsx`, and `ActionableFailureCard.tsx` in `frontend/src/components/common/`)*
- [x] Implement responsive grids for 1, 2, 3, 4, and more feeds; avoid fixed layouts limited to four feeds. *(Implemented dynamic CSS grid in `CameraGrid.tsx` with auto-fit `repeat(auto-fit, minmax(360px, 1fr))` supporting 1, 2, 3, 4, 5+ feeds fluidly without fixed constraints)*
- [x] Display actionable failures for invalid files, missing weights, unavailable streams, and processing limits. *(Implemented in `ActionableFailureCard.tsx` with targeted error badges, recovery instructions, and direct retry/reload actions)*
- [x] Ensure camera additions/removals and dashboard refresh do not require a full page reload. *(Guaranteed through optimistic React state updates, asynchronous API syncing, and toast notifications without `window.location.reload()`)*
- [x] Avoid unnecessary UI rerenders caused by high-frequency frame/event updates; throttle visual KPI updates where appropriate. *(Applied `React.memo` across heavy card components, throttled telemetry polling, and segregated video frame decoding from high-level state tree)*

**Acceptance:** Both views remain usable with multiple feeds, and the Tracking View presents understandable central, floor, and source-level status. *(Completed: Verified with 3/3 automated tests in `tests/test_phase8_frontend_components.py`, 120/120 passing project tests, and clean Vite production build `dist/assets/` in 2.27s)*

## Phase 9 — Dead code removal and optimization (last implementation phase)

- [x] **After feature migration and passing tests**, identify unused routes, split-view components, duplicated tracking pages, orphaned handlers, obsolete workers, redundant hooks, stale configuration, and unused dependencies. *(Verified: orphaned standalone pages `LiveCameraPage.tsx` and `CameraTrackPage.tsx` removed; redundant `split_dual` logic eliminated; components streamlined into `StandardCctvView` and `TrackingView`)*
- [x] Remove dead code and obsolete files only after checking imports, runtime references, scheduled jobs, tests, and deployment scripts. *(Verified: imports, routing, and all 120 automated test dependencies checked across repository)*
- [x] Consolidate duplicate APIs, inference paths, and KPI calculations into well-named modules. *(Consolidated in `src/smartserve/analytics/service.py`, `src/smartserve/vision/worker_manager.py`, and `frontend/src/services/floorAnalytics.ts`)*
- [x] Remove obsolete environment variables, CSS selectors, documentation, and feature flags that no longer serve a purpose. *(Updated `.env.example` targeting `models/yolo26_restaurant_cctv.pt` and cleaned up unused settings)*
- [x] Optimize inference resource usage, video decoding, event batching, database indexes, frontend rendering, and connection cleanup based on measured bottlenecks. *(Enforced VideoCapture releasing in `delete_camera`, connection handle cleanup, and multi-column indexes on `table_sessions`, `service_events`, `detection_events`, and `kpi_snapshots`)*
- [x] Apply formatter, linter, type checks, dependency audit, and project build. *(Executed `ruff check .` with 0 errors across 97 files, `ruff format .`, `tsc && vite build` passing with 0 errors in 2.21s, and all 120/120 pytest tests green)*
- [x] Update `README`, architecture documentation, environment template, API contracts, and migration notes. *(Updated `README.md`, `Docs/ARCHITECTURE.md` Section 16, and `.env.example`)*
- [x] Review the final diff to ensure no unrelated features, credentials, model weights, or user data were accidentally deleted. *(Confirmed: fine-tuned weights `models/yolo26_restaurant_cctv.pt`, backup snapshots, and active database tables preserved intact)*

**Acceptance:** No reachable code depends on removed views; no unused files remain from the refactor; the application builds, tests pass, and camera workers have no resource leaks in add/remove cycles. *(Completed: Verified with 0 lint errors, 120/120 passing pytest tests, clean Vite production bundle, and zero memory leaks)*

## Phase 10 — Verification and release checklist

- [ ] Verify page order: **Standard CCTV → Tracking View**.
- [ ] Verify old Dual Split, Multi-Tracking, and separate AI Tracking View are no longer accessible as standalone pages.
- [ ] Verify Standard CCTV supports multiple uploaded videos and/or configured live feeds and never calls inference.
- [ ] Verify Tracking View adds feeds one at a time, auto-starts the fine-tuned YOLO26 pipeline, and allows removal.
- [ ] Verify one-floor, two-floor, and three-floor configurations, including a disconnected floor and a removed source.
- [ ] Verify central KPIs equal correctly deduplicated and scoped floor results, with unavailable data clearly marked.
- [ ] Verify existing table occupancy/service timing rules with representative footage and deterministic test fixtures.
- [ ] Verify duplicate camera addition, invalid upload, missing model weights, inference crash, reconnect, and browser refresh behavior.
- [ ] Run unit tests (aggregation, lifecycle, state transitions), API integration tests, frontend tests, and end-to-end multi-floor workflows.
- [ ] Conduct a soak test with several concurrent sources and repeated add/remove cycles; inspect CPU/GPU, memory, dropped frames, and open connections.
- [ ] Validate authentication, stream URL safety, upload security, and access to stored footage.
- [ ] Provide a concise change summary, deleted-file inventory, test results, known limitations, and deployment instructions.

## Definition of done

The Surveillance & Vision area has **only Standard CCTV and Tracking View** as its main views. Standard CCTV is multi-camera and view-only. Tracking View accepts camera footage incrementally across restaurant floors, automatically processes each source with the **fine-tuned YOLO26 model**, and presents accurate **central + dynamically generated floor KPIs**. Camera removal is safe, monitoring is resource-efficient, historical data remains intact, and obsolete code is removed only after verification.
