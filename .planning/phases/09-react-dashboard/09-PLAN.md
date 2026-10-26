# Phase 9: React Dashboard Plan

## Phase Goal
Implement the three-page operations dashboard specified in `Docs/DESIGN.md`, `Docs/PRD.md` (FR-10), and `Docs/TASKS.md` Phase 9, featuring:
1. **Live Camera (`/live-camera`)**: Original raw CCTV feeds without CV overlays, multi-camera split screen (1, 2, 4 feeds), camera selector, connection state, and stale indicators.
2. **Camera Track (`/camera-track`)**: Processed CV stream with YOLO bounding boxes, tracking IDs, table polygons, occupancy labels, overlay visibility controls, side CV summary panel, inference status, and event timestamps.
3. **Dashboard (`/dashboard`)**: Restaurant operations overview with KPI cards, interactive table grid with filters, alert queue with acknowledge/resolve actions, table detail drawer with service timeline, verification badges, attendance and food-delivery confirmation actions, camera health summary, data freshness indicators, and CSV export.
4. **Real-Time Synchronization**: Live updates via WebSocket (`/ws/events`) with automated REST recovery on reconnection, error states, and role-adaptive visibility.

## Requirements Covered
- **Three-Page Architecture & Shared Shell (`Docs/DESIGN.md` Sections 3-8)**:
  - Header: SmartServe AI logo, restaurant selector, shift indicator, connection state, data freshness timestamp, staff profile & role switcher (Waiter, Manager, Admin).
  - Sidebar: Persistent navigation across `/live-camera`, `/camera-track`, and `/dashboard` with responsive drawer.
- **Page 1 — Live Camera (`Docs/DESIGN.md` Section 5 & TASKS.md Phase 9)**:
  - Displays original CCTV footage without CV overlays.
  - Multi-camera layout: single feed, 2-feed split, and 4-feed grid.
  - Connection states: Connected, Connecting, Disconnected, Stale frame indicator.
  - Full-screen and stream refresh/reconnect controls.
- **Page 2 — Camera Track (`Docs/DESIGN.md` Section 6 & TASKS.md Phase 9)**:
  - Processed camera stream with computer vision annotations.
  - Supported overlay toggles: Person boxes, Tracking IDs, Table regions, Occupancy labels, Confidence values.
  - Side information panel: detected person count, per-table occupancy state, estimated customer counts, recent events, and inference latency.
  - Distinction between technical tracking IDs and real person identities.
- **Page 3 — Dashboard (`Docs/DESIGN.md` Section 7 & TASKS.md Phase 9)**:
  - KPI cards: Total Tables, Occupied Tables, Available Tables, Waiting for Attendance, Active Alerts, Camera Health.
  - Table status cards & grid with occupancy states (Available, Occupied, Attended, Food Delivered, Needs Attention, Cleaning Required), occupancy timers, and customer counts labeled as "Estimated".
  - Section, status, and search filters with clear filter actions and responsive empty states.
  - Alert queue ordered by severity with in-place acknowledgment and resolution.
  - Table detail drawer with chronological service timeline, UI verification badges ("Confirmed by Waiter", "AI Vision Estimate", "Manager Override"), and authorized manual attendance/food confirmation actions.
  - Analytics summary preview and authorized CSV export trigger.
- **Streaming & Live Updates (`Docs/DESIGN.md` Section 10 & TASKS.md Phase 9)**:
  - Backend camera streaming router (`src/smartserve/api/routes/cameras.py`) providing camera metadata, raw MJPEG stream, processed MJPEG stream, and latest frame CV metadata.
  - WebSocket connection (`/ws/events`) with heartbeat ping/pong, live broadcast handling, and REST resynchronization upon reconnection.
- **Data Integrity, Privacy, & Accessibility (`Docs/DESIGN.md` Section 12)**:
  - Distinguish confirmed events vs. AI estimates vs. uncertain observations.
  - Role-adaptive visibility (Waiter vs. Manager vs. Admin) backed by server-side authorization.
  - High-contrast visual design tokens, keyboard navigation, and visible focus states.

## Task Breakdown

1. **Backend Camera Streaming & CV Metadata Service (`src/smartserve/api/routes/cameras.py`)**:
   - `GET /api/v1/cameras`: Return registered cameras with status, resolution, FPS, and stream endpoints.
   - `GET /api/v1/cameras/{camera_id}`: Return single camera health and configuration.
   - `GET /api/v1/cameras/{camera_id}/stream/raw`: MJPEG stream delivering raw video frames.
   - `GET /api/v1/cameras/{camera_id}/stream/processed`: MJPEG stream delivering processed frames annotated with YOLO bounding boxes, tracking IDs, and table polygons.
   - `GET /api/v1/cameras/{camera_id}/cv-metadata`: Return latest frame detections, tracks, table states, and telemetry.
   - Mount `cameras_router` into `src/smartserve/main.py`.

2. **WebSocket Real-time Broadcast Enhancement (`src/smartserve/api/websocket.py` & `main.py`)**:
   - Wire event creation, alert status changes, and occupancy transitions to `manager.broadcast()`.
   - Provide periodic status heartbeat payload over `/ws/events`.

3. **Frontend Design Tokens & Styling (`frontend/src/index.css`)**:
   - Modern dark console aesthetic matching `Docs/DESIGN.md` Section 9.
   - High contrast status badges, glassmorphism panels, responsive layout classes, and accessibility focus rings.

4. **Frontend Architecture & Navigation (`frontend/src/`)**:
   - Client-side navigation supporting `/live-camera`, `/camera-track`, and `/dashboard`.
   - Shared Header with system connection indicator, data freshness counter, and staff role switcher.
   - Shared Sidebar with active route indicator and mobile collapse.

5. **Page 1: Live Camera (`frontend/src/pages/LiveCameraPage.tsx`)**:
   - Multi-camera layout switcher (1x, 2x, 4x grid).
   - Camera selector and fullscreen controls.
   - Camera connection badge (ONLINE, CONNECTING, STALE, DISCONNECTED) and frame timestamp.
   - Raw video player with reconnect retry action.

6. **Page 2: Camera Track (`frontend/src/pages/CameraTrackPage.tsx`)**:
   - Processed video player with live stream.
   - Overlay toggle controls: Person boxes, Tracking IDs, Table regions, Occupancy labels, Confidence.
   - Side CV Summary Panel: Detected persons count, per-table occupancy, recent tracking events, inference latency banner.

7. **Page 3: Operations Dashboard (`frontend/src/pages/DashboardPage.tsx`)**:
   - KPI Summary Cards: Total Tables, Occupied, Available, Overdue Attendance, Active Alerts, Camera Status.
   - Interactive Table Grid & Cards: status colors, occupancy duration timer, estimated customer count, assigned waiter, active alert indicator.
   - Filter bar: Section filter, Occupancy Status filter, Search by table code.
   - Alert Queue: list with severity badges, trigger time, table link, acknowledge and resolve buttons.
   - Table Detail Drawer: deep dive with session details, service timeline with presentation badges, manual attendance confirmation button, food delivery confirmation button with batch selector, and table cleaning reset.
   - Analytics Preview & CSV Export modal/button.

8. **Automated Verification & Demonstration**:
   - Unit and integration tests for camera API endpoints (`tests/test_camera_stream_api.py`).
   - Frontend TypeScript compilation and bundle verification (`npm run build`).
   - All tests passing cleanly.

## Verification Criteria
- [ ] Backend camera endpoints return camera metadata, raw MJPEG stream, processed MJPEG stream, and CV metadata.
- [ ] Live Camera page renders raw CCTV feeds in 1, 2, and 4 camera layouts with connection badges and timestamps.
- [ ] Camera Track page renders processed footage with overlay toggles and side summary panel.
- [ ] Dashboard displays live KPIs, table grid, alert queue, and table detail drawer.
- [ ] Table detail drawer displays service timeline with verification badges and allows attendance/food confirmation.
- [ ] Alert queue supports acknowledging and resolving alerts.
- [ ] WebSocket syncs state live, and UI shows connection status and data freshness.
- [ ] Frontend builds with zero TypeScript or Vite compilation errors (`npm run build`).
- [ ] 100% of backend tests pass cleanly.
