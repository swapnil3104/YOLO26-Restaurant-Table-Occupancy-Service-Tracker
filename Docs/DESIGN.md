# 🎨 SmartServe AI — Dashboard Design Specification

**Document:** UX/UI Design and Interaction Specification  
**Version:** 1.0  
**Status:** Proposed  
**Audience:** Frontend developers, designers, and reviewers

## 1. Design Objective

Create a calm, readable restaurant operations dashboard that helps a manager answer three questions quickly:
1. Which tables need attention now?
2. What service milestones have been confirmed or are still pending?
3. Are occupancy and service operations improving over time?

The interface must distinguish **confirmed events**, **AI estimates**, and **uncertain observations**. Do not present model predictions as facts.

## 2. UX Principles

- **At-a-glance first:** urgent service delays and system failures are easy to find.
- **State over decoration:** use clear text labels and icons, not color alone.
- **Evidence and uncertainty:** estimated counts and candidate events are labeled.
- **Fast operations:** attendance confirmation and alert acknowledgment require minimal steps.
- **Auditability:** corrections show who changed an event and when.
- **Privacy by default:** avoid exposing raw video or unnecessary employee-level data.
- **Responsive:** optimize for desktop and tablet; essential controls remain usable on smaller screens.

## 3. Information Architecture

Primary navigation:
- Overview
- Live Tables
- Alerts
- Analytics
- Reports
- Cameras & Floor Plan (admin/manager permission)
- Settings (admin permission)

Account menu:
- Profile
- Help / system status
- Sign out

## 4. Main Dashboard Wireframe

```text
┌─────────────────────────────────────────────────────────────────────┐
│ SmartServe AI             Restaurant / Shift          User ▾         │
├───────────────┬─────────────────────────────────────────────────────┤
│ Overview      │ Overview                              Updated 20:14  │
│ Live Tables   │                                                     │
│ Alerts        │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐ │
│ Analytics     │ │ Tables  │ │Occupied │ │Waiting  │ │ Active      │ │
│ Reports       │ │   18    │ │   12    │ │   3     │ │ Alerts  2   │ │
│ Cameras       │ └─────────┘ └─────────┘ └─────────┘ └─────────────┘ │
│ Settings      │                                                     │
│               │ Filters: [All tables ▾] [Status ▾] [Waiter ▾]       │
│               │                                                     │
│               │ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│               │ │ T01        │ │ T02        │ │ T03        │       │
│               │ │ OCCUPIED   │ │ AVAILABLE  │ │ NEEDS CARE │       │
│               │ │ 3 guests   │ │            │ │ 2 guests   │       │
│               │ │ 00:18:42   │ │            │ │ 00:06 late │       │
│               │ │ Attended ✓ │ │            │ │ Attend ... │       │
│               │ │ [Details]  │ │ [Details]  │ │ [Details]  │       │
│               │ └────────────┘ └────────────┘ └────────────┘       │
│               │                                                     │
│               │ Recent events / alert queue                         │
└───────────────┴─────────────────────────────────────────────────────┘
```

Numbers above are illustrative only. Live values must come from the API.

## 5. Screen Specifications

### 5.1 Overview

**Purpose:** summarize restaurant state and surface urgent issues.

Components:
- Header with restaurant/shift selector and last-update time.
- KPI cards: total tables, occupied, available, waiting for attendance, active alerts.
- Table status distribution.
- Recent event list.
- Alert queue sorted by severity and age.
- Camera health summary.

Interactions:
- Clicking a KPI filters the relevant list.
- Clicking an alert opens its detail drawer.
- Stale data shows a visible “Data may be out of date” message.

### 5.2 Live Tables

**Purpose:** manage the current table state.

Components:
- Search by table code.
- Filters for occupancy, service status, section, waiter, and camera.
- Table cards or compact table view.
- Optional floor-plan view with table status overlays.
- Last update and uncertainty labels.

Table card fields:
- Table code and configured capacity.
- State label.
- Estimated customer count (include “estimated” when inferred).
- Occupancy duration.
- First attendance state/time.
- Food-delivery state/time.
- Assigned waiter or “Unconfirmed”.
- Active alert summary.
- Details action.

### 5.3 Table Detail Drawer/Page

```text
┌──────────────────────────────────────────────┐
│ Table T05                          [Close]    │
│ OCCUPIED · Session active                     │
│ Estimated guests: 4 · Occupancy: 00:45:00     │
├──────────────────────────────────────────────┤
│ Service timeline                              │
│ 20:00  Seating confirmed                      │
│ 20:03  First attendance confirmed             │
│ 20:12  First food delivery confirmed          │
│                                              │
│ Response: 3 min                               │
│ First food: 12 min                            │
│                                              │
│ [Confirm attendance] [Confirm food delivery]  │
│ [Correct event] [Flag for review]             │
├──────────────────────────────────────────────┤
│ Event history / source / verification status  │
└──────────────────────────────────────────────┘
```

Only show actions permitted to the current role and current session state. Confirmation dialogs should include the table, event type, and timestamp being recorded.

### 5.4 Alerts

List columns:
- Severity
- Alert type
- Table/camera/system reference
- Created time and age
- Status
- Acknowledge/resolve action

Behavior:
- Deduplicate repeated alerts for one unresolved condition.
- Keep resolved alerts searchable.
- Require a reason for dismissing a suspected false positive where policy requires it.
- Never label an alert as “waiter fault” or similar judgment.

### 5.5 Analytics

Filters:
- Date range
- Shift
- Section
- Table
- Waiter (authorized roles only)

Charts and summaries:
- First-response time distribution.
- Time to first food delivery.
- Occupancy and table turnover by hour.
- Delay rate by threshold.
- Event completeness and uncertainty rate.

Every chart must include its metric definition, time range, sample size, and whether it includes estimated or confirmed events.

### 5.6 Reports

- Report type and date range selector.
- Preview of summary metrics.
- CSV export.
- Export progress, success, and failure states.
- Authorization check on the server.
- Export metadata with creation timestamp and filters.

### 5.7 Cameras & Floor Plan

- Camera list with status, last frame, and error message.
- Table region editor with polygon points.
- Preview overlay on the current camera frame.
- Save/cancel controls and validation warnings.
- Region coordinates stored normalized to frame dimensions.
- Camera credentials never displayed after initial secure configuration.

### 5.8 Settings

- Service thresholds.
- Occupancy confirmation and vacancy grace periods.
- Notification preferences.
- User and role management.
- Data retention settings.
- Audit log access.

High-impact settings should explain their effect and be audited after save.

## 6. Design System

### 6.1 Visual Direction

Use a modern operations-console aesthetic: neutral surfaces, clear typography, restrained accent color, compact data cards, and strong spacing. Avoid overly decorative gradients or color-heavy cards that compete with service alerts.

### 6.2 Semantic Status Tokens

| Meaning | Suggested Token | Usage |
|---|---|---|
| Normal/available | `status-neutral` | Available table, normal system state |
| In progress | `status-info` | Active session, processing |
| Needs attention | `status-warning` | Approaching or exceeding threshold |
| Critical | `status-critical` | Critical overdue event or camera failure |
| Confirmed | `event-confirmed` | Confirmed event marker |
| Estimated | `event-estimated` | Vision-derived estimate |
| Uncertain | `event-uncertain` | Ambiguous or stale state |

Use text labels and icons with color. Validate color contrast; do not rely on color alone.

### 6.3 Typography

- Use a readable sans-serif system font stack.
- Use tabular numerals for timers and KPI values.
- Keep headings compact and consistent.
- Avoid tiny text for timestamps, event sources, and uncertainty labels.

### 6.4 Spacing and Layout

- Use a consistent spacing scale (for example, 4, 8, 12, 16, 24, 32 px).
- Keep card padding consistent.
- Prefer a responsive grid with a minimum usable card width.
- Use sticky table headers only when lists are long enough to benefit.

### 6.5 Component Inventory

- `AppShell`
- `SidebarNavigation`
- `TopBar`
- `KpiCard`
- `TableStatusCard`
- `TableStatusBadge`
- `OccupancyTimer`
- `ServiceTimeline`
- `EventVerificationBadge`
- `AlertListItem`
- `AlertDetailDrawer`
- `FilterBar`
- `DateRangePicker`
- `CameraHealthBadge`
- `EmptyState`
- `LoadingSkeleton`
- `ErrorState`
- `ConfirmActionDialog`
- `DataFreshnessIndicator`
- `MetricDefinitionTooltip`

## 7. Interaction Rules

- Destructive actions require confirmation.
- Attendance and delivery confirmation should be one or two intentional steps.
- Do not silently overwrite an event; corrections create an audit entry.
- Disable duplicate submissions while a request is in progress.
- On API failure, show a clear error and preserve form input where safe.
- On WebSocket disconnect, show connection state and recover from REST data.
- Timers may update locally between server events, but persisted timestamps remain authoritative.
- If camera data is stale, show the last observed timestamp and avoid implying that the current table state is certain.

## 8. Accessibility Requirements

- All controls support keyboard navigation.
- Inputs have visible labels and accessible error messages.
- Status is conveyed with text and iconography, not color alone.
- Focus indicators are visible.
- Tables and charts include accessible labels or summary text.
- Avoid rapid flashing for alerts; use a stable visual priority indicator.

## 9. Responsive Behavior

- Desktop: sidebar plus multi-column table grid.
- Tablet: collapsible navigation and two-column table grid.
- Small screen: single-column cards, compact filters, alert priority at top.
- Keep confirmation controls usable without horizontal scrolling.
- The camera/floor-plan editor is best supported on desktop and should provide a clear fallback on smaller devices.

## 10. UI Data Contracts

The frontend should consume normalized API responses. A table view model should include:
- `table_id`, `table_code`, `occupancy_state`;
- `estimated_customer_count` and count confidence/quality;
- `active_session_id`;
- `session_started_at`;
- `first_attendance_at` and verification status;
- `first_food_delivery_at` and verification status;
- `assigned_waiter_display_name` only when authorized and known;
- `active_alerts`;
- `last_observed_at` and `data_freshness`.

The UI must not calculate authoritative historical metrics from rounded display strings. Use API-provided timestamps and numeric durations.

## 11. Loading, Empty, and Error States

- No tables configured: prompt an authorized user to configure the floor plan.
- No active sessions: show a calm empty state, not an error.
- No alerts: show “No active alerts”.
- Camera disconnected: show the affected camera and last successful frame time.
- Analytics lacks sufficient data: explain the minimum sample requirement.
- API unavailable: retain a clear stale-data banner and provide retry behavior.

## 12. Design Acceptance Checklist

- [ ] A manager can identify overdue tables quickly.
- [ ] Confirmed, estimated, and uncertain events are visually distinct.
- [ ] Table detail shows a timestamped service timeline.
- [ ] Users can filter tables and alerts.
- [ ] Role-restricted actions are not exposed as usable controls.
- [ ] Stale camera data is obvious.
- [ ] Keyboard navigation and contrast are reviewed.
- [ ] Empty, loading, and failure states are implemented.
- [ ] Corrections and confirmations show their effect and audit context.
