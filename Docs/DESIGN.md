# 🎥 SmartServe AI — Three-Page Website Design Specification

**Document:** Website UX/UI and Functional Requirements  
**Version:** 1.0  
**Status:** Proposed  
**Project:** SmartServe AI — YOLO-Based Restaurant Table Occupancy & Service Timer

---

## 📚 Table of Contents

1. [Project Overview](#1--project-overview)
2. [Design Goals](#2--design-goals)
3. [Website Information Architecture](#3--website-information-architecture)
4. [Shared Application Layout](#4--shared-application-layout)
5. [Page 1 — Live Camera](#5--page-1--live-camera)
6. [Page 2 — Camera Track](#6--page-2--camera-track)
7. [Page 3 — Dashboard](#7--page-3--dashboard)
8. [Navigation and Routes](#8--navigation-and-routes)
9. [Visual Design System](#9--visual-design-system)
10. [Data and Streaming Requirements](#10--data-and-streaming-requirements)
11. [Error, Loading, and Empty States](#11--error-loading-and-empty-states)
12. [Privacy, Accessibility, and Safety](#12--privacy-accessibility-and-safety)
13. [Suggested Technical Architecture](#13--suggested-technical-architecture)
14. [Acceptance Checklist](#14--acceptance-checklist)

---

## 1. 🎯 Project Overview

SmartServe AI is a computer-vision-based restaurant monitoring and service analytics system. The website has three primary pages:

1. **Live Camera** — shows original CCTV footage without computer vision overlays.
2. **Camera Track** — shows processed camera footage with people detection, tracking IDs, table regions, occupancy information, and other computer vision outputs.
3. **Dashboard** — presents restaurant operations, table occupancy, service timers, alerts, and analytics.

The original and processed camera views must remain clearly separated. The Dashboard is the operational overview for restaurant managers.

> **Data principle:** Distinguish confirmed events, AI estimates, and uncertain observations. Never present a model prediction as a verified fact.

## 2. 🧭 Design Goals

- Make camera feeds easy to view and switch between.
- Support split-screen CCTV monitoring.
- Make computer vision activity and tracking behavior understandable.
- Help managers quickly identify tables that need attention.
- Present service timing and alerts in a readable format.
- Show camera health, connection status, and data freshness.
- Use a consistent navigation and visual language across all pages.
- Avoid hardcoded production metrics; live values must come from the backend.

## 3. 🗺️ Website Information Architecture

| Page | Route | Primary purpose |
|---|---|---|
| Live Camera | `/live-camera` | View original CCTV footage |
| Camera Track | `/camera-track` | Inspect processed video and CV outputs |
| Dashboard | `/dashboard` | Monitor table operations and service performance |

### Core navigation

- Live Camera
- Camera Track
- Dashboard

Optional account controls may include the restaurant/shift selector, user profile, help/system status, and sign out. Additional dashboard sections such as Alerts, Analytics, Reports, Cameras & Floor Plan, and Settings may be implemented within the Dashboard experience if required.

## 4. 🧱 Shared Application Layout

All three pages should use the same application shell.

### 4.1 Header

Include:

- SmartServe AI logo and product name.
- Current restaurant or location selector, if multiple locations are supported.
- Current shift selector, if applicable.
- Overall system connection indicator.
- Last-update or data-freshness information where relevant.
- User/account menu.

### 4.2 Sidebar

Use persistent navigation with an active-page indicator:

- 🎥 Live Camera
- 🧠 Camera Track
- 📊 Dashboard

The sidebar may collapse on tablets and smaller screens. On mobile, use a compact navigation drawer or equivalent accessible pattern.

### 4.3 Layout behavior

- Use a desktop-first layout for camera monitoring and tracking.
- Keep controls grouped near the content they affect.
- Maintain readable spacing and clear visual hierarchy.
- Do not use color alone to communicate status; include text and/or icons.
- Preserve the selected camera when moving between pages when possible.

## 5. 🎥 Page 1 — Live Camera

### 5.1 Purpose

Display the original CCTV footage as received from the camera source. This page is for normal surveillance viewing and must not display AI detection boxes, tracking IDs, table polygons, or other computer vision overlays.

### 5.2 Main interface

**Top control bar**
- Page title: `Live Camera`
- Camera selector, such as Camera 01, Camera 02, or Camera 03.
- Layout selector: single feed, two feeds, or four feeds.
- Refresh/reconnect control.
- Full-screen control for a selected feed.
- Optional audio/mute control if the source supports audio.

**Camera feed area**
- Single view: one large video panel.
- Two-camera view: two feeds arranged side by side on desktop.
- Four-camera view: a 2 × 2 grid.
- Each panel shows a camera name, connection state, and timestamp.
- Use a stable aspect ratio and avoid stretching the video.

**Optional camera information**
- Camera identifier.
- Stream state: Connected, Connecting, Disconnected, or Stale.
- Last successfully received frame time.
- Stream resolution or frame rate, if supplied by the backend.

### 5.3 Interactions

- Select a camera from the camera selector.
- Change between single, split-screen, and four-feed layouts.
- Enter or exit full-screen mode.
- Retry a disconnected stream.
- Return to the default layout when needed.

### 5.4 Rules

- Display the original video source, not the annotated inference output.
- Do not imply a camera is live if frames are no longer arriving.
- When the feed is stale, show the last-frame timestamp and a visible stale indicator.
- If a camera is disconnected, show a clear placeholder with the camera name and retry action.
- Never fabricate footage, camera status, timestamps, or camera metrics.

### 5.5 Suggested component inventory

- `LiveCameraPage`
- `CameraSelector`
- `CameraLayoutSelector`
- `CameraFeedGrid`
- `RawCameraPlayer`
- `CameraStatusBadge`
- `StreamTimestamp`
- `FullScreenControl`
- `StreamErrorState`

## 6. 🧠 Page 2 — Camera Track

### 6.1 Purpose

Display the processed camera stream and the computer vision results generated by the detection and tracking pipeline. This page helps a user understand what the CV system detects and how it associates detections across frames.

### 6.2 Main interface

**Top control bar**
- Page title: `Camera Track`
- Camera selector.
- Processing status.
- Start/stop processing control, if the current role is authorized.
- Overlay visibility controls.
- Optional display settings for confidence threshold or tracking visualization, if supported.

**Processed video area**
Show the processed stream with supported overlays, such as:

- Person detection bounding boxes.
- Persistent person tracking IDs.
- Table boundaries or configured regions of interest.
- Table labels (for example, T01, T02, T03).
- Occupancy labels or state markers.
- Customer-count estimates.
- Detection confidence values, when useful.
- Tracking paths or movement trails, if implemented.
- Event markers for supported entry, exit, seating, or vacancy events.

**Side information panel**
- Current detected-person count.
- Per-table occupancy state.
- Estimated customer count per table.
- Recent tracking and occupancy events.
- Model/inference status.
- Last processed frame timestamp.
- Warnings for uncertain detections or stale processing data.

### 6.3 Suggested overlay controls

| Overlay | Description | Default |
|---|---|---|
| Person boxes | Draw person detection boxes | On |
| Tracking IDs | Display stable tracking identifiers | On |
| Table regions | Display configured table boundaries | On |
| Occupancy labels | Display inferred table states | On |
| Confidence | Display model confidence values | Optional |
| Tracking trails | Show recent paths, if implemented | Optional |
| Event markers | Show supported CV event markers | On |

The interface must only offer overlays that the backend actually provides.

### 6.4 Interactions

- Select a camera.
- Toggle supported overlays on and off.
- Select a table region to inspect its current state and related events.
- Review recent detections and event timestamps.
- Start or stop processing when authorized.
- Adjust supported processing settings.
- Navigate to the Live Camera page to compare the raw feed with the processed view.

### 6.5 Computer vision state semantics

Use explicit labels:

- **Detected:** a model returned a detection for the current frame.
- **Tracked:** a detection is associated with a tracking identity across frames.
- **Estimated:** a value, such as customer count or occupancy, is inferred by the system.
- **Confirmed:** an event has been verified according to the application's event-confirmation rules.
- **Uncertain:** the available evidence is ambiguous or insufficient.
- **Stale:** the latest frame or result is older than the configured freshness threshold.

A tracking ID is a technical tracking identifier, not a verified identity of a real person.

### 6.6 Suggested component inventory

- `CameraTrackPage`
- `ProcessedCameraPlayer`
- `DetectionOverlay`
- `TrackingIdLabel`
- `TableRegionOverlay`
- `OccupancyLabel`
- `OverlaySettings`
- `CVSummaryPanel`
- `RecentEventList`
- `InferenceStatus`
- `ConfidenceIndicator`
- `StaleFrameBanner`

## 7. 📊 Page 3 — Dashboard

### 7.1 Purpose

Provide restaurant managers with a quick operational overview: which tables are occupied, which need attention, which service milestones have been confirmed, and whether cameras and data streams are healthy.

### 7.2 Dashboard header

Include:

- Page title: `Dashboard` or `Overview`.
- Restaurant and shift selector, where applicable.
- Last-updated timestamp.
- Data-freshness indicator.
- Date or shift filters if needed.

### 7.3 KPI cards

Recommended cards:

| KPI | Meaning |
|---|---|
| Total Tables | Number of configured tables |
| Occupied Tables | Tables currently considered occupied |
| Available Tables | Tables currently considered available |
| Waiting for Attendance | Tables awaiting first attendance beyond the applicable rule |
| Active Alerts | Unresolved active alerts |
| Camera Health | Connected/healthy camera summary |

KPI values must be supplied by the API. Illustrative development values must be labeled as demo data.

### 7.4 Table status cards

Each table card should display, where available:

- Table code and configured capacity.
- Occupancy status.
- Estimated customer count with an `Estimated` label.
- Occupancy duration.
- First-attendance state and timestamp.
- First-food-delivery state and timestamp.
- Assigned waiter only when known and the viewer is authorized to see it.
- Active alert summary.
- Last-observed timestamp or freshness state.
- A `Details` action.

Suggested table states:

- Available
- Occupied
- Needs Attention
- Uncertain
- Stale Data

Do not infer that a table is available merely because a person is temporarily missing from a frame. Apply the configured vacancy confirmation and grace-period rules.

### 7.5 Filters and search

Provide filters appropriate to the available backend data:

- All tables / a selected table.
- Occupancy state.
- Service state.
- Restaurant section.
- Camera.
- Assigned waiter, for authorized roles only.

Allow users to clear filters and show a useful empty state when no tables match.

### 7.6 Alerts

Show an alert queue ordered by severity and age.

Each alert should include:

- Severity and alert type.
- Table, camera, or system reference.
- Creation time and age.
- Current status.
- Acknowledge or resolve action, if permitted.
- Details explaining the triggering condition.

Rules:

- Deduplicate repeated alerts for the same unresolved condition.
- Keep resolved alerts available for search or history where supported.
- Avoid judgmental labels such as “waiter fault.”
- Require confirmation for destructive actions and a reason for dismissing suspected false positives when policy requires it.

### 7.7 Table detail and service timeline

A table detail view or drawer should include:

- Table code and current occupancy state.
- Estimated guest count, clearly labeled.
- Occupancy duration.
- Timestamped service events.
- Verification status and event source.
- Relevant alert history.
- Permitted actions such as confirming attendance, confirming food delivery, correcting an event, or flagging for review.

Only show actions that are supported by the backend, allowed for the user's role, and valid for the current session state. Corrections must preserve an audit trail instead of silently overwriting history.

### 7.8 Analytics

Recommended metrics:

- First-response time distribution.
- Time to first food delivery.
- Occupancy and table turnover by hour.
- Delay rate against configured thresholds.
- Event completeness and uncertainty rate.

Every chart should identify the metric definition, time range, sample size, and whether it includes estimated or confirmed events.

### 7.9 Reports and camera health

Where supported, include:

- Report type and date range.
- Summary preview.
- CSV export with progress, success, and failure states.
- Camera connection state and last successful frame time.
- Clear system warnings for disconnected cameras or stale data.

### 7.10 Suggested component inventory

- `DashboardPage`
- `DashboardHeader`
- `KpiCard`
- `TableStatusGrid`
- `TableStatusCard`
- `TableStatusBadge`
- `OccupancyTimer`
- `ServiceTimeline`
- `EventVerificationBadge`
- `FilterBar`
- `AlertQueue`
- `AlertDetailDrawer`
- `CameraHealthSummary`
- `AnalyticsPanel`
- `ReportExport`
- `DataFreshnessIndicator`
- `LoadingSkeleton`
- `EmptyState`
- `ErrorState`

## 8. 🧭 Navigation and Routes

Use client-side routing so each page has a direct URL.

| Route | Page | Navigation label |
|---|---|---|
| `/live-camera` | Original CCTV feeds | Live Camera |
| `/camera-track` | Processed CV stream | Camera Track |
| `/dashboard` | Restaurant operations overview | Dashboard |

### Navigation requirements

- Highlight the active page.
- Preserve shared application context where possible.
- Handle unknown routes with a not-found page or redirect.
- Protect manager/admin-only actions through both frontend authorization and backend authorization.
- Do not rely on hidden UI controls as the only security measure.

## 9. 🎨 Visual Design System

### 9.1 Visual direction

Use a modern operations-console aesthetic:

- Dark charcoal or navy surfaces for camera-monitoring pages.
- Neutral, readable dashboard surfaces.
- Restrained accent colors.
- Compact, consistent cards and spacing.
- Strong contrast between video content and controls.
- Clear typography and tabular numerals for timers and KPI values.

A dark theme is a good default for the camera pages because it keeps attention on video feeds. The dashboard may use the same dark theme for consistency or a neutral light theme if that better matches the existing design.

### 9.2 Status semantics

| Meaning | Suggested treatment |
|---|---|
| Normal / Available | Neutral label and icon |
| Processing / In progress | Informational label |
| Needs Attention | Warning label |
| Critical / Disconnected | Critical label |
| Confirmed event | Confirmed badge |
| AI estimate | Estimated badge |
| Uncertain observation | Uncertain badge |
| Stale data | Stale warning with timestamp |

Always use text labels and icons alongside color.

### 9.3 Spacing and responsiveness

Use a consistent spacing scale, such as 4, 8, 12, 16, 24, and 32 px. Keep camera controls accessible without covering important video content.

- **Desktop:** persistent sidebar; camera grid and dashboard multi-column layouts.
- **Tablet:** collapsible sidebar; two-column content where practical.
- **Mobile:** single-column cards and compact navigation. Camera-track editing tools may have a reduced or read-only layout.

## 10. 🔌 Data and Streaming Requirements

### 10.1 Separation of streams

The system must provide a way to distinguish:

1. **Raw stream** for Live Camera.
2. **Processed stream or frames plus detection metadata** for Camera Track.
3. **Normalized operational API data** for Dashboard.

The raw and processed views may originate from the same camera, but the raw view must not inherit the detection overlays.

### 10.2 Suggested camera metadata

```json
{
  "camera_id": "camera_01",
  "name": "Dining Area Camera 01",
  "connection_status": "connected",
  "last_frame_at": "2026-10-22T12:00:00Z",
  "stream_type": "raw"
}
```

This is an illustrative schema only. Use the project's actual API contract and timestamp conventions.

### 10.3 Suggested CV event structure

```json
{
  "camera_id": "camera_01",
  "frame_timestamp": "2026-10-22T12:00:00Z",
  "detections": [
    {
      "class": "person",
      "track_id": "track_12",
      "confidence": 0.94,
      "bbox": [120, 80, 220, 360]
    }
  ],
  "table_regions": [],
  "occupancy_estimates": []
}
```

The bounding-box coordinate convention, confidence range, and table-region schema must be defined by the backend. The values above are examples, not real detections.

### 10.4 Data freshness

- Use server timestamps as the source of truth.
- Show the last observed frame or event time.
- Flag stale data according to configurable thresholds.
- Do not continue to display an old frame as if it were live.
- On a WebSocket disconnect, show connection status and recover from an appropriate API or stream reconnection flow.

### 10.5 Timers and events

- Use authoritative server timestamps for persisted events.
- Local timers may update between server updates for display purposes.
- Do not calculate authoritative historical metrics from rounded display strings.
- Label inferred event candidates separately from confirmed service events.

## 11. ⚠️ Error, Loading, and Empty States

| Condition | Expected UI behavior |
|---|---|
| Camera connecting | Show a connecting indicator |
| Camera disconnected | Show camera name, last frame time, and retry action |
| Stale stream | Show a clear stale warning and last observed timestamp |
| CV processing stopped | Keep raw camera access separate and show processing state |
| No tables configured | Explain that an authorized user must configure the floor plan |
| No active table sessions | Show a calm empty state |
| No active alerts | Show “No active alerts” |
| No matching filter results | Explain that no tables match the current filters |
| Analytics has insufficient data | Explain the limitation and sample requirement |
| API unavailable | Show an error/stale-data banner and retry behavior |
| Export failure | Explain failure and allow a safe retry |

## 12. 🔐 Privacy, Accessibility, and Safety

### Privacy

- Limit access to raw camera footage by role and operational need.
- Avoid exposing unnecessary employee-level information.
- Do not display camera credentials in the UI after secure configuration.
- Apply the project's video retention and access-control policies.
- Record relevant user actions and event corrections in an audit log.

### Accessibility

- Support keyboard navigation.
- Provide visible focus indicators.
- Give every control a meaningful accessible label.
- Use text and icons, not color alone, to communicate state.
- Avoid rapidly flashing alert indicators.
- Ensure timestamps, statuses, and control labels are readable.

### Operational safety

- Treat computer vision results as estimates unless verified.
- Make camera and inference failures visible.
- Avoid automatic operational actions based solely on uncertain detections.
- Enforce permissions and event validation on the backend.

## 13. 🏗️ Suggested Technical Architecture

A suggested implementation stack is:

| Layer | Suggested technology | Responsibility |
|---|---|---|
| Frontend | React + Vite | Three-page web application |
| Styling | Tailwind CSS | Responsive layout and visual system |
| Routing | React Router | Page navigation |
| CV processing | Python + YOLO and tracking pipeline | Detection, tracking, and supported occupancy inference |
| Backend API | Python API service or the project's existing backend | Camera metadata, table states, events, alerts, and reports |
| Streaming | WebRTC, HLS, MJPEG, or another compatible stream method | Deliver raw and processed camera views |
| Live updates | WebSocket or server-sent events, as appropriate | Update status, event lists, and dashboard values |
| Database | Project-selected relational database | Persist table configuration, sessions, events, and audit records |

Choose the streaming method based on the camera source, latency requirements, deployment environment, and browser compatibility. Do not assume that the camera source already exposes a browser-compatible stream.

### High-level data flow

```text
CCTV / Camera Source
        |
        +----------------------> Raw Stream
        |                            |
        |                            v
        |                       Live Camera Page
        |
        v
YOLO Detection + Tracking
        |
        +----------------------> Processed Stream + CV Metadata
        |                            |
        |                            v
        |                       Camera Track Page
        |
        v
Occupancy / Event Processing
        |
        v
Backend API + Database
        |
        +----------------------> Dashboard KPIs
        +----------------------> Table Status and Timers
        +----------------------> Alerts and Analytics
```

This diagram is conceptual. Actual stream routing, model inference, persistence, and event-confirmation behavior must follow the implementation.

## 14. ✅ Acceptance Checklist

### Shared application

- [ ] All three pages are accessible from persistent navigation.
- [ ] Each page has a direct URL.
- [ ] Active navigation state is clear.
- [ ] Layout adapts to desktop, tablet, and mobile.
- [ ] Loading, error, disconnected, and stale states are implemented.

### Live Camera

- [ ] Original CCTV footage is displayed without CV overlays.
- [ ] Single-camera, two-camera, and four-camera layouts work where supported.
- [ ] Camera selection works.
- [ ] Full-screen and reconnect controls work.
- [ ] Disconnected and stale feeds are clearly identified.
- [ ] Timestamps represent actual source or server data.

### Camera Track

- [ ] Processed footage is visually distinct from raw footage.
- [ ] Supported person boxes and tracking IDs are displayed.
- [ ] Table regions and occupancy information are shown when available.
- [ ] Overlay controls only expose implemented features.
- [ ] Estimates, confirmed events, and uncertain observations are distinguished.
- [ ] Processing status and frame freshness are visible.

### Dashboard

- [ ] KPI values come from the backend.
- [ ] Table cards show available occupancy and service information.
- [ ] Estimated customer counts are labeled as estimates.
- [ ] Alerts include severity, time, status, and permitted actions.
- [ ] Table detail includes a timestamped service timeline.
- [ ] Filters and empty states work.
- [ ] Analytics definitions and data ranges are visible.
- [ ] Event corrections preserve audit history.
- [ ] Camera health and stale data are visible.

### Quality and security

- [ ] Role-restricted actions are protected by the backend.
- [ ] Keyboard navigation and contrast are reviewed.
- [ ] Camera credentials are not exposed in the interface.
- [ ] No mock values are presented as live production data.
- [ ] Errors do not silently erase user input or event history.

---

**End of specification.**
