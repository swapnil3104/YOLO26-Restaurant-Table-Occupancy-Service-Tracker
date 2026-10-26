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

- [x] Define table configuration schema with unique table codes.
- [x] Store regions using normalized coordinates.
- [x] Build an administrator-facing polygon/rectangle configuration workflow or initial JSON configuration.
- [x] Render configured regions on the camera preview.
- [x] Implement point-in-polygon association.
- [x] Add ambiguity handling for overlapping or nearby regions.
- [x] Add table capacity and camera association validation.
- [x] Add test fixtures with multiple adjacent tables.

**Acceptance checks**
- [x] Configuration survives application restart.
- [x] A track inside a configured region is associated according to documented rules.
- [x] Ambiguous tracks can be returned as unassigned rather than forced into a table.

## Phase 4 — Occupancy State Machine and Sessions

- [x] Implement occupancy states from `RULES.md`.
- [x] Add configurable occupancy persistence window.
- [x] Add configurable vacancy grace period.
- [x] Prevent transient passers-by from immediately occupying a table.
- [x] Create session IDs and session-start timestamps.
- [x] Maintain current estimated customer count.
- [x] Implement possible-vacancy and cleaning-required transitions.
- [x] Add manager override and correction hooks.
- [x] Persist state transitions and session events.
- [x] Build deterministic replay tests for occupancy sequences.

**Acceptance checks**
- [x] State transitions follow the documented state machine.
- [x] Brief occlusion does not automatically end an active session.
- [x] A completed session has valid start/end timestamps.
- [x] A camera outage does not automatically mark tables vacant.

## Phase 5 — Database and Event Domain

- [x] Define SQLAlchemy models for restaurants, tables, cameras, users, sessions, events, assignments, alerts, and audit logs.
- [x] Add Alembic migrations.
- [x] Define event schemas and enumerated event types.
- [x] Add source and verification-status fields.
- [x] Add transaction-safe event/session updates.
- [x] Implement idempotency for retried event submissions.
- [x] Implement event correction without destroying original history.
- [x] Add database indexes for table, session, type, and timestamp queries.
- [x] Add backup/restore instructions for development data.

**Acceptance checks**
- [x] Migrations create the schema from an empty database.
- [x] Duplicate submissions do not create duplicate operational events.
- [x] Corrections preserve an audit trail.
- [x] Timestamp and foreign-key validation tests pass.

## Phase 6 — Service Timers and Rules Engine

- [x] Implement first-response calculation.
- [x] Implement time-to-first-food-delivery calculation.
- [x] Implement attendance-to-delivery calculation.
- [x] Implement occupancy duration.
- [x] Implement missing-event and invalid-order handling.
- [x] Implement configurable service thresholds.
- [x] Add alert lifecycle and deduplication.
- [x] Add alert acknowledgment and resolution actions.
- [x] Ensure event correction triggers safe metric/alert recalculation.
- [x] Add unit tests for threshold boundaries and time zones.

**Acceptance checks**
- [x] Calculations use timestamps and return no fabricated value when an event is missing.
- [x] Negative or inconsistent intervals are flagged.
- [x] Alert rules produce one active alert per deduplication key/condition.
- [x] Tests cover just-before, exactly-at, and just-after threshold values.

## Phase 7 — Attendance and Food-Delivery Confirmation

- [x] Build waiter/manager attendance confirmation endpoint.
- [x] Build food-delivery confirmation endpoint.
- [x] Require active session/table association and authorized actor.
- [x] Record source, actor, event timestamp, and server-recorded timestamp.
- [x] Support multiple delivery events in one session.
- [x] Add correction/rejection workflow for mistaken events.
- [x] Define optional POS/KDS adapter interface without requiring integration for MVP.
- [x] Add UI copy that distinguishes confirmation from AI estimation.

**Acceptance checks**
- [x] Authorized users can confirm attendance and delivery.
- [x] Unauthorized requests are rejected by the backend.
- [x] Repeated submissions are handled idempotently.
- [x] Event source and verification status appear in the timeline.

## Phase 8 — FastAPI and Security

- [x] Add API routers for tables, sessions, events, alerts, analytics, and health.
- [x] Add request/response schemas and consistent error format.
- [x] Implement authentication and role-based authorization.
- [x] Protect configuration changes and exports.
- [x] Add pagination and date filters to event/report endpoints.
- [x] Add rate limiting where exposed to untrusted networks.
- [x] Add CORS configuration for known frontend origins.
- [x] Add OpenAPI documentation.
- [x] Ensure secrets are not logged or returned.
- [x] Add authorization tests for each role.

**Acceptance checks**
- [x] API routes return documented response schemas.
- [x] Role checks are enforced server-side.
- [x] Health endpoint reports application and dependency status without leaking secrets.

## Phase 9 — React Dashboard

- [x] Go through DESIGN.md file before proceeding with react dashboard  
- [x] Create app shell, navigation, and account menu.
- [x] Implement overview KPI cards.
- [x] Implement live table grid and filters.
- [x] Implement table detail timeline.
- [x] Add attendance and food-delivery confirmation actions.
- [x] Implement alert list, acknowledgment, and resolution.
- [x] Implement data freshness and camera health indicators.
- [x] Add WebSocket updates with REST recovery on reconnect.
- [x] Implement loading, empty, error, and stale-data states.
- [x] Add keyboard and contrast checks.
- [x] Implement role-based visibility while relying on backend authorization for enforcement.

**Acceptance checks**
- [x] A manager can identify overdue tables and open their details.
- [x] Live changes appear without a manual page refresh under normal connectivity.
- [x] Disconnection is visible and stale state is not presented as current certainty.
- [x] Confirmation actions show success/failure feedback and avoid duplicate clicks.

## Phase 10 — Analytics and Reports

- [x] Define KPI calculation rules in code and documentation.
- [x] Implement average and median response times.
- [x] Implement delay rate and data completeness.
- [x] Implement table occupancy and turnover reports.
- [x] Add time-range, table, section, and permitted waiter filters.
- [x] Include sample sizes and completeness on charts.
- [x] Implement authorized CSV export.
- [x] Add report tests against known fixtures.

**Acceptance checks**
- [x] Dashboard and exported report values match for the same filters.
- [x] Missing/unverified events are handled according to `RULES.md`.
- [x] Employee-level data is only available to authorized roles.

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
