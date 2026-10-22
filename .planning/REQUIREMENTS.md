# Requirements Traceability

## Core Functional Requirements (PRD FR-01 to FR-10)
- **FR-01: Video Ingestion & Sampling** - Capture from webcam/RTSP, bounded sampling (5 FPS), auto-reconnect.
- **FR-02: Person Detection & Tracking** - Provider-agnostic detector interface, temporary track ID assignment.
- **FR-03: Table Region Association** - Normalized polygon mapping, point-in-polygon association, handling ambiguity.
- **FR-04: Occupancy State Tracking** - Deterministic state machine (`VACANT`, `OCCUPIED`, `ATTENDED`, `FOOD_DELIVERED`, `PAYMENT_PENDING`, `CLEANING_REQUIRED`, `UNKNOWN`).
- **FR-05: Session Management** - Stable session IDs, guest count estimation, persistence window, and vacancy grace period.
- **FR-06: Service Timing Engine** - First attendance timing, food delivery tracking, alert threshold trigger.
- **FR-07: Operational Confirmation** - Multi-source events (`AI_OBSERVATION`, `STAFF_CONFIRMATION`, `POS_INTEGRATION`).
- **FR-08: Alert Management** - Deduplicated active alerts with acknowledgment/resolution.
- **FR-09: API & Security** - FastAPI REST endpoints, OpenAPI documentation, RBAC.
- **FR-10: Dashboard Interface** - React live operations dashboard with WebSockets.
