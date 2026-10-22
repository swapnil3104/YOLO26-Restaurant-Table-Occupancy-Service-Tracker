# ✅ SmartServe AI — Development Tasks

**Document:** Phase-wise Implementation Checklist  
**Version:** 1.0  
**Status:** Proposed  
**Source of truth:** `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `RULES.md`

## 1. How to Use This Checklist

- Complete tasks in order unless a dependency is explicitly independent.
- Mark a task complete only when its acceptance checks pass.
- Keep model evaluation results and known limitations in `docs/MODEL_EVALUATION.md`.
- Do not treat an unverified visual candidate as a confirmed business event.
- Each phase should end with a runnable demo and documented test results.

## Phase 0 — Repository and Engineering Setup

- [x] Create repository and add `README.md`, `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `TASKS.md`, and `RULES.md`.
- [x] Add `.gitignore` for virtual environments, build outputs, caches, secrets, and local video.
- [x] Add `.env.example` with placeholder values only.
- [x] Define Python and Node versions supported by the selected dependencies.
- [x] Create Python project configuration and dependency lock strategy.
- [x] Add linting/formatting configuration.
- [x] Add a minimal pytest setup.
- [x] Add frontend project scaffold with TypeScript.
- [x] Document local startup commands.

**Acceptance checks**
- [x] A new developer can follow the README to set up the repository.
- [x] No real credentials, private stream URLs, or private video are committed.
- [x] Backend tests run from a documented command.

## Phase 1 — Model and Video Feasibility

- [x] Verify the exact YOLO26 implementation, model weights, license, runtime, and supported hardware.
- [x] Add a detector interface independent of the chosen model package.
- [x] Implement webcam and recorded-video input through OpenCV.
- [x] Add frame timestamp and camera ID metadata.
- [x] Implement person detection output normalization.
- [x] Add configurable confidence threshold and frame sampling.
- [x] Draw optional bounding-box overlays for debugging.
- [x] Measure inference latency and throughput on target hardware.
- [x] Record model/runtime versions and benchmark configuration.
- [x] Document known detection failures on sample footage.

**Acceptance checks**
- [x] The application reads a test video and outputs timestamped person detections.
- [x] Invalid frames and camera failures produce actionable errors.
- [x] A model replacement can be implemented behind the detector interface.
- [x] Benchmark results are recorded with hardware and resolution details.


## Phase 2 — Tracking

- [x] Implement a tracker adapter.
- [x] Evaluate ByteTrack and/or BoT-SORT on representative footage.
- [x] Preserve temporary track IDs across adjacent frames where possible.
- [x] Handle track expiration and short occlusion.
- [x] Add optional trajectory visualization for debugging.
- [x] Record track confidence/quality where supported.
- [x] Create replayable tracking test clips or fixtures.

**Acceptance checks**
- [x] A moving person is tracked through a short clip.
- [x] Track IDs are documented as temporary, not permanent identities.
- [x] Tracker behavior and ID-switch limitations are documented.

## Phase 3 — Table Layout and Association

- [ ] Define table configuration schema with unique table codes.
- [ ] Store regions using normalized coordinates.
- [ ] Build an administrator-facing polygon/rectangle configuration workflow or initial JSON configuration.
- [ ] Render configured regions on the camera preview.
- [ ] Implement point-in-polygon association.
- [ ] Add ambiguity handling for overlapping or nearby regions.
- [ ] Add table capacity and camera association validation.
- [ ] Add test fixtures with multiple adjacent tables.

**Acceptance checks**
- [ ] Configuration survives application restart.
- [ ] A track inside a configured region is associated according to documented rules.
- [ ] Ambiguous tracks can be returned as unassigned rather than forced into a table.

## Phase 4 — Occupancy State Machine and Sessions

- [ ] Implement occupancy states from `RULES.md`.
- [ ] Add configurable occupancy persistence window.
- [ ] Add configurable vacancy grace period.
- [ ] Prevent transient passers-by from immediately occupying a table.
- [ ] Create session IDs and session-start timestamps.
- [ ] Maintain current estimated customer count.
- [ ] Implement possible-vacancy and cleaning-required transitions.
- [ ] Add manager override and correction hooks.
- [ ] Persist state transitions and session events.
- [ ] Build deterministic replay tests for occupancy sequences.

**Acceptance checks**
- [ ] State transitions follow the documented state machine.
- [ ] Brief occlusion does not automatically end an active session.
- [ ] A completed session has valid start/end timestamps.
- [ ] A camera outage does not automatically mark tables vacant.

## Phase 5 — Database and Event Domain

- [ ] Define SQLAlchemy models for restaurants, tables, cameras, users, sessions, events, assignments, alerts, and audit logs.
- [ ] Add Alembic migrations.
- [ ] Define event schemas and enumerated event types.
- [ ] Add source and verification-status fields.
- [ ] Add transaction-safe event/session updates.
- [ ] Implement idempotency for retried event submissions.
- [ ] Implement event correction without destroying original history.
- [ ] Add database indexes for table, session, type, and timestamp queries.
- [ ] Add backup/restore instructions for development data.

**Acceptance checks**
- [ ] Migrations create the schema from an empty database.
- [ ] Duplicate submissions do not create duplicate operational events.
- [ ] Corrections preserve an audit trail.
- [ ] Timestamp and foreign-key validation tests pass.

## Phase 6 — Service Timers and Rules Engine

- [ ] Implement first-response calculation.
- [ ] Implement time-to-first-food-delivery calculation.
- [ ] Implement attendance-to-delivery calculation.
- [ ] Implement occupancy duration.
- [ ] Implement missing-event and invalid-order handling.
- [ ] Implement configurable service thresholds.
- [ ] Add alert lifecycle and deduplication.
- [ ] Add alert acknowledgment and resolution actions.
- [ ] Ensure event correction triggers safe metric/alert recalculation.
- [ ] Add unit tests for threshold boundaries and time zones.

**Acceptance checks**
- [ ] Calculations use timestamps and return no fabricated value when an event is missing.
- [ ] Negative or inconsistent intervals are flagged.
- [ ] Alert rules produce one active alert per deduplication key/condition.
- [ ] Tests cover just-before, exactly-at, and just-after threshold values.

## Phase 7 — Attendance and Food-Delivery Confirmation

- [ ] Build waiter/manager attendance confirmation endpoint.
- [ ] Build food-delivery confirmation endpoint.
- [ ] Require active session/table association and authorized actor.
- [ ] Record source, actor, event timestamp, and server-recorded timestamp.
- [ ] Support multiple delivery events in one session.
- [ ] Add correction/rejection workflow for mistaken events.
- [ ] Define optional POS/KDS adapter interface without requiring integration for MVP.
- [ ] Add UI copy that distinguishes confirmation from AI estimation.

**Acceptance checks**
- [ ] Authorized users can confirm attendance and delivery.
- [ ] Unauthorized requests are rejected by the backend.
- [ ] Repeated submissions are handled idempotently.
- [ ] Event source and verification status appear in the timeline.

## Phase 8 — FastAPI and Security

- [ ] Add API routers for tables, sessions, events, alerts, analytics, and health.
- [ ] Add request/response schemas and consistent error format.
- [ ] Implement authentication and role-based authorization.
- [ ] Protect configuration changes and exports.
- [ ] Add pagination and date filters to event/report endpoints.
- [ ] Add rate limiting where exposed to untrusted networks.
- [ ] Add CORS configuration for known frontend origins.
- [ ] Add OpenAPI documentation.
- [ ] Ensure secrets are not logged or returned.
- [ ] Add authorization tests for each role.

**Acceptance checks**
- [ ] API routes return documented response schemas.
- [ ] Role checks are enforced server-side.
- [ ] Health endpoint reports application and dependency status without leaking secrets.

## Phase 9 — React Dashboard

- [ ] Create app shell, navigation, and account menu.
- [ ] Implement overview KPI cards.
- [ ] Implement live table grid and filters.
- [ ] Implement table detail timeline.
- [ ] Add attendance and food-delivery confirmation actions.
- [ ] Implement alert list, acknowledgment, and resolution.
- [ ] Implement data freshness and camera health indicators.
- [ ] Add WebSocket updates with REST recovery on reconnect.
- [ ] Implement loading, empty, error, and stale-data states.
- [ ] Add keyboard and contrast checks.
- [ ] Implement role-based visibility while relying on backend authorization for enforcement.

**Acceptance checks**
- [ ] A manager can identify overdue tables and open their details.
- [ ] Live changes appear without a manual page refresh under normal connectivity.
- [ ] Disconnection is visible and stale state is not presented as current certainty.
- [ ] Confirmation actions show success/failure feedback and avoid duplicate clicks.

## Phase 10 — Analytics and Reports

- [ ] Define KPI calculation rules in code and documentation.
- [ ] Implement average and median response times.
- [ ] Implement delay rate and data completeness.
- [ ] Implement table occupancy and turnover reports.
- [ ] Add time-range, table, section, and permitted waiter filters.
- [ ] Include sample sizes and completeness on charts.
- [ ] Implement authorized CSV export.
- [ ] Add report tests against known fixtures.

**Acceptance checks**
- [ ] Dashboard and exported report values match for the same filters.
- [ ] Missing/unverified events are handled according to `RULES.md`.
- [ ] Employee-level data is only available to authorized roles.

## Phase 11 — Reliability, Privacy, and Pilot

- [ ] Add camera reconnect logic and outage alerts.
- [ ] Test database outage and recovery behavior.
- [ ] Test WebSocket reconnect and REST resynchronization.
- [ ] Add structured logs and basic performance metrics.
- [ ] Define event and video retention settings.
- [ ] Review access controls and data minimization.
- [ ] Document camera notice/authorization and incident response procedures.
- [ ] Evaluate on labeled footage from different lighting and occlusion conditions.
- [ ] Measure occupancy, count, tracking, event, and latency metrics.
- [ ] Run controlled pilot with manual event verification.
- [ ] Record false positives, false negatives, and limitations.

**Acceptance checks**
- [ ] Camera loss is visible and does not create false vacancy events.
- [ ] Pilot report includes test setup, data size, measured metrics, and known limitations.
- [ ] Retention and access policies are documented before live deployment.

## 12. Cross-Cutting Definition of Done

A task is done only when:
- [ ] The implementation follows the documented component boundary.
- [ ] Error cases and invalid input are handled.
- [ ] Tests cover normal and important failure paths.
- [ ] Logs do not expose secrets or unnecessary personal data.
- [ ] Documentation/configuration examples are updated.
- [ ] The feature preserves source and verification status for events.
- [ ] UI/API behavior is tested against role permissions where applicable.

## 13. Suggested Release Milestones

| Milestone | Included Phases | Outcome |
|---|---|---|
| M0 — Feasibility | 0–2 | Video ingestion, detection, and tracking demo |
| M1 — Occupancy MVP | 3–4 | Configured tables, occupancy states, sessions |
| M2 — Service Timing | 5–7 | Persisted events, timers, manual confirmations |
| M3 — Dashboard MVP | 8–9 | Secure API and live operations dashboard |
| M4 — Analytics MVP | 10 | Reports, KPIs, and export |
| M5 — Pilot Ready | 11 | Reliability, privacy review, and measured evaluation |
