# Project Roadmap

## Milestone 0: Feasibility & Foundation (Phases 0-2)
- [x] **Phase 0: Repository and Engineering Setup** - Project configs, environment variables, dependencies, test suite, and frontend scaffold.
- [x] **Phase 1: Model and Video Feasibility** - Video ingestion pipeline, OpenCV capture, YOLO detector adapter, frame normalization, inference benchmarking.
- [x] **Phase 2: Tracking Adapter** - ByteTrack / BoT-SORT integration, track persistence across adjacent frames, occlusion tolerance, and track ID limitation handling.


## Milestone 1: Occupancy MVP (Phases 3-4)
- [ ] **Phase 3: Table Layout and Association** - Normalized polygon table coordinates, point-in-polygon association, and ambiguous track handling.
- [ ] **Phase 4: Occupancy State Machine and Sessions** - Temporal occupancy persistence, vacancy grace periods, session management, and guest counting.

## Milestone 2: Service Timing (Phases 5-7)
- [ ] **Phase 5: Database and Event Domain** - SQLAlchemy models, Alembic migrations, event schemas with verification status, and audit logs.
- [ ] **Phase 6: Service Timers and Rules Engine** - Response time calculations, food delivery timers, configurable alert thresholds, and deduplication.
- [ ] **Phase 7: Attendance and Food-Delivery Confirmation** - Waiter and manager confirmation endpoints, actor tracking, and POS/KDS adapter hooks.

## Milestone 3: Dashboard MVP (Phases 8-9)
- [ ] **Phase 8: FastAPI and Security** - REST endpoints, OpenAPI docs, authentication, role-based authorization, and CORS.
- [ ] **Phase 9: React Dashboard** - Interactive floor grid, KPI cards, table timeline, alert handling, and live WebSocket synchronization.

## Milestone 4: Analytics MVP (Phase 10)
- [ ] **Phase 10: Analytics and Reports** - Aggregated KPIs, median response times, turnover rates, section filters, and CSV export.

## Milestone 5: Pilot Ready (Phase 11)
- [ ] **Phase 11: Reliability, Privacy, and Pilot** - Reconnection resilience, privacy verification, benchmark evaluation on test clips, and pilot review.

---

## Phase Details

### Phase 0: Repository and Engineering Setup
**Goal:** Establish clean repository scaffolding, dependencies, configurations, tests, and frontend base.
**Depends on:** None
**Requirements:** FR-01, FR-09
**Success Criteria:**
- [x] Environment configuration and `.env.example` created.
- [x] Python package structure under `src/smartserve` with abstract vision interfaces.
- [x] Frontend scaffold initialized with React, Vite, and TypeScript.
- [x] Backend test suite operational and passing.

### Phase 1: Model and Video Feasibility
**Goal:** Implement resilient video capture, decouple detector interfaces, implement YOLO detector adapter, frame normalization, and benchmark inference performance on target hardware.
**Depends on:** Phase 0
**Requirements:** FR-01, FR-02
**Success Criteria:**
- [x] The application reads a test video and outputs timestamped person detections.
- [x] Invalid frames and camera failures produce actionable errors.
- [x] A model replacement can be implemented behind the detector interface.
- [x] Benchmark results are recorded with hardware and resolution details.


### Phase 2: Tracking Adapter
**Goal:** Integrate multi-object tracking (ByteTrack / BoT-SORT) to maintain track persistence across frames with occlusion tolerance.
**Depends on:** Phase 1
**Requirements:** FR-02
**Success Criteria:**
- [x] A moving person is tracked through a short clip.
- [x] Track IDs are preserved across short occlusions and documented as temporary.
- [x] Tracker behavior and ID-switch limitations are documented.

### Phase 3: Table Layout and Association
**Goal:** Implement normalized polygon table configurations and point-in-polygon association with ambiguity handling.
**Depends on:** Phase 2
**Requirements:** FR-03
**Success Criteria:**
- [ ] Configuration survives application restart.
- [ ] A track inside a configured region is associated according to documented rules.
- [ ] Ambiguous tracks are returned as unassigned rather than forced into a table.

### Phase 4: Occupancy State Machine and Sessions
**Goal:** Build deterministic occupancy state machine, persistence windows, vacancy grace periods, and session lifecycles.
**Depends on:** Phase 3
**Requirements:** FR-04, FR-05
**Success Criteria:**
- [ ] State transitions follow the documented state machine.
- [ ] Brief occlusion does not automatically end an active session.
- [ ] A completed session has valid start/end timestamps.
- [ ] A camera outage does not automatically mark tables vacant.

### Phase 5: Database and Event Domain
**Goal:** Design relational schemas, SQLAlchemy models, Alembic migrations, transaction-safe updates, and audit logging.
**Depends on:** Phase 4
**Requirements:** FR-07
**Success Criteria:**
- [ ] Migrations create the schema from an empty database.
- [ ] Duplicate submissions do not create duplicate operational events.
- [ ] Corrections preserve an audit trail.

### Phase 6: Service Timers and Rules Engine
**Goal:** Compute first attendance, food delivery, and occupancy duration with configurable threshold alerts.
**Depends on:** Phase 5
**Requirements:** FR-06, FR-08
**Success Criteria:**
- [ ] Calculations use timestamps and return no fabricated value when an event is missing.
- [ ] Alert rules produce one active alert per deduplication key/condition.
- [ ] Unit tests cover threshold boundaries.

### Phase 7: Attendance and Food-Delivery Confirmation
**Goal:** Provide waiter and manager confirmation endpoints with source and verification attribution.
**Depends on:** Phase 6
**Requirements:** FR-07
**Success Criteria:**
- [ ] Authorized users can confirm attendance and delivery.
- [ ] Repeated submissions are handled idempotently.
- [ ] Event source and verification status appear in the timeline.

### Phase 8: FastAPI and Security
**Goal:** Implement full REST API endpoints, OpenAPI documentation, authentication, and role-based access control.
**Depends on:** Phase 7
**Requirements:** FR-09
**Success Criteria:**
- [ ] API routes return documented response schemas.
- [ ] Role checks are enforced server-side.
- [ ] Health endpoint reports status without leaking secrets.

### Phase 9: React Dashboard
**Goal:** Build responsive real-time operations dashboard with interactive floor grid, alert tray, and WebSocket updates.
**Depends on:** Phase 8
**Requirements:** FR-10
**Success Criteria:**
- [ ] A manager can identify overdue tables and open details.
- [ ] Live changes appear without manual page refresh.
- [ ] Disconnection and stale state are clearly visible.

### Phase 10: Analytics and Reports
**Goal:** Provide aggregated metrics, median response times, turnover rates, and authorized CSV exports.
**Depends on:** Phase 9
**Requirements:** FR-06, FR-09
**Success Criteria:**
- [ ] Dashboard and exported report values match for the same filters.
- [ ] Employee-level data is restricted to authorized roles.

### Phase 11: Reliability, Privacy, and Pilot
**Goal:** Implement camera reconnect resilience, privacy controls, performance profiling, and pilot verification.
**Depends on:** Phase 10
**Requirements:** FR-01, FR-02, FR-04, FR-09
**Success Criteria:**
- [ ] Camera loss does not create false vacancy events.
- [ ] Pilot report records test setup, measured metrics, and known limitations.
