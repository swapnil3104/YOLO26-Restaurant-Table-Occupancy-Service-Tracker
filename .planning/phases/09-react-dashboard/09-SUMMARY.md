# Phase 9: React Dashboard Summary

## Phase Goal
Implement the responsive, real-time three-page restaurant operations dashboard specified in `Docs/DESIGN.md`, `Docs/PRD.md` (FR-10), and `Docs/TASKS.md` Phase 9, separating raw CCTV surveillance footage, processed computer vision streams, and manager operational controls.

## Key Deliverables Completed

### 1. Backend Camera Streaming & CV Telemetry Service (`src/smartserve/api/routes/cameras.py`)
- Registered 4 restaurant CCTV camera feeds (`cam-01` Main Dining, `cam-02` Patio Terrace, `cam-03` Window Booths, `cam-04` Private Lounge).
- `GET /api/v1/cameras`: Returns metadata, resolution, FPS, and streaming endpoints.
- `GET /api/v1/cameras/{camera_id}`: Returns single camera health and stream URLs.
- `GET /api/v1/cameras/{camera_id}/stream/raw`: MJPEG multipart stream delivering raw CCTV footage without computer vision overlays.
- `GET /api/v1/cameras/{camera_id}/stream/processed`: MJPEG multipart stream annotated with YOLO person bounding boxes, ByteTrack IDs, table polygons, and occupancy states.
- `GET /api/v1/cameras/{camera_id}/snapshot`: Single frame snapshot endpoint for raw and processed feeds.
- `GET /api/v1/cameras/{camera_id}/cv-metadata`: Latest frame CV detection and tracking telemetry (bounding boxes, bottom contact anchors, table associations, model name, inference latency, FPS).
- Mounted `cameras_router` under `/api/v1` in `src/smartserve/main.py`.

### 2. Real-Time Synchronization & WebSocket Broadcast (`src/smartserve/api/websocket.py` & `main.py`)
- Enhanced WebSocket manager with `broadcast_event(event_type, data)` helper for typed operational broadcasts.
- Initial greeting handshake payload sent to newly connected WebSocket clients on `/ws/events`.
- Heartbeat ping/pong and automated reconnection logic in `frontend/src/hooks/useRealtime.ts`.

### 3. Modern Dark Console Aesthetics & Design Tokens (`frontend/src/index.css`)
- Styled in accordance with `Docs/DESIGN.md` Section 9:
  - Deep charcoal and navy surfaces (`#0a0d14`, `#0f1523`, `#141b2d`).
  - Glassmorphic panels with subtle borders and glow accents.
  - High-contrast operational status badges (Vacant, Occupied, Attended, Food Delivered, Cleaning Required, Warning, Critical).
  - Unambiguous verification badges distinguishing confirmed human verification from candidate AI vision estimates and manager overrides.
  - Accessible focus states and custom console scrollbars.

### 4. Shared Application Shell (`frontend/src/components/`)
- `Header.tsx`:
  - SmartServe AI brand with glowing gradient icon.
  - Restaurant location (`Downtown Flagship`) and shift picker (`Dinner Shift 18:00–23:00`).
  - Live system connection indicator (`Live Sync` green pulse, `Connecting...` amber, `Offline` red) with data freshness relative counter.
  - Staff Account & Role Switcher dropdown allowing instant switching between Waiter (`Alex Waiter`), Manager (`Morgan Manager`), and Admin (`Taylor Admin`) to dynamically exercise server-side RBAC.
- `Sidebar.tsx`:
  - Persistent navigation across `/live-camera`, `/camera-track`, and `/dashboard`.
  - Active alert badge count on Dashboard link.
  - Smooth collapsible sidebar drawer.

### 5. Page 1 — Live Camera (`frontend/src/pages/LiveCameraPage.tsx`)
- Displays pure CCTV surveillance video without any computer vision overlays.
- Layout switcher: Single feed (1x), Split screen (2x), Quad grid (4x).
- Camera selector tabs for multi-camera switching.
- Per-panel camera status badge (`ONLINE`, `DEGRADED`, `OFFLINE`), resolution, FPS, and timestamp banner.
- Reconnect and refresh control with fallback snapshot support.

### 6. Page 2 — Camera Track (`frontend/src/pages/CameraTrackPage.tsx`)
- Displays processed camera video stream annotated with YOLO detection and tracking overlays.
- Overlay toggle controls:
  - Person Bounding Boxes
  - Tracking IDs
  - Table Polygons
  - Occupancy Labels
  - Confidence %
- Side Information Panel:
  - Estimated patron count banner.
  - Per-table occupancy status chips with estimated customer counts.
  - Chronological computer vision spatial association events log.
  - Live telemetry HUD (model name `YOLO26-Nano + ByteTrack`, inference latency `14.8ms`, `28.5 FPS`).
  - Explicit technical notice clarifying that track IDs are technical tracking identifiers, not real personal identities.

### 7. Page 3 — Operations Dashboard (`frontend/src/pages/DashboardPage.tsx`)
- KPI Summary Cards:
  - Total Tables, Occupied Tables, Available Tables, Waiting for Attendance, Active Alerts, Camera Health.
- Interactive Floor Grid:
  - Visual cards with table code, capacity, status badge, estimated guest count, occupancy duration timer, and assigned waiter.
  - Search table code or section.
  - Section filter (Main Dining, Patio, Window Booth, Private Lounge).
  - Occupancy state filter (Occupied, Attended, Food Delivered, Vacant, Cleaning Required).
  - Empty search/filter state with reset action.
- Active Alert Queue:
  - Prioritized by severity (`CRITICAL`, `WARNING`, `INFO`).
  - In-place "Acknowledge" and "Resolve" actions with immediate state update.
- Table Detail Drawer:
  - In-depth session details for the selected table.
  - Service Timeline with presentation badges ("Confirmed by Waiter", "AI Vision Estimate", "Manager Override").
  - Role-gated operational confirmation actions:
    - "Confirm Waiter Attendance" (records attendance via `/api/v1/events/attendance`).
    - "Confirm Food Delivery" with course and batch number selector (records delivery via `/api/v1/events/food-delivery`).
    - "Sanitize & Reset to Available" (resets cleaning required tables via `/api/v1/occupancy/{id}/clean`).
- Analytics Summary Modal & CSV Export:
  - Median response time, median food delivery time, average occupancy duration, turnover rate.
  - One-click downloadable privacy-anonymized operational CSV export.

## Verification & Testing
- Automated backend unit and integration tests added in `tests/test_camera_stream_api.py`:
  - `test_list_cameras`: Verifies registered cameras and stream URLs.
  - `test_get_camera_by_id`: Verifies valid camera details and 404 handling.
  - `test_get_camera_snapshot`: Verifies JPEG snapshot generation for raw and processed feeds.
  - `test_get_camera_cv_metadata`: Verifies structured detection, tracking, and table association telemetry.
- **Backend Test Suite Results**: All 90 automated tests passing cleanly in ~5.3s.
- **Frontend Build Verification**: TypeScript and Vite bundle (`tsc && vite build`) compiles with 0 errors (`built in 2.33s`).
