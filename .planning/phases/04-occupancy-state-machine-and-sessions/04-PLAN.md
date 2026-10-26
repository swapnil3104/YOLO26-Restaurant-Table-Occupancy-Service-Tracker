# Phase 4: Occupancy State Machine and Sessions Plan

## Phase Goal
Build a deterministic, rule-compliant occupancy state machine with temporal persistence windows, vacancy grace periods, customer count smoothing, session lifecycles, manager override hooks, restart recovery persistence, and debug overlays following `RULES.md` and `PRD.md` (FR-04, FR-05, FR-06).

## Requirements Covered
- **FR-04: Table Occupancy Detection (RULES.md Section 4 & PRD.md)**:
  - Full occupancy states: `AVAILABLE`, `POSSIBLY_OCCUPIED`, `OCCUPIED`, `POSSIBLY_VACANT`, `CLEANING_REQUIRED`, `OUT_OF_SERVICE`, `UNKNOWN`.
  - Temporal persistence confirmation window: transient passers-by do not mark table occupied (e.g., requires evidence for configurable window, default 5.0s).
  - Vacancy grace period: brief occlusions or missing detections do not falsely terminate active sessions (configurable window, default 20s-180s).
  - Missing frames / camera stale handling: Stale camera threshold (30s) prevents inferring table vacancy from camera failures.
- **FR-05: Customer Counting (RULES.md Section 5 & PRD.md)**:
  - Deduplicated track counting per table observation window.
  - Temporal smoothing window (moving window / median) to eliminate frame-to-frame count jitter.
  - Distinction between estimated count and manager-confirmed count.
- **FR-06: Occupancy Session Management (RULES.md Section 4.3 & 8)**:
  - Unique session ID (`sess_{table_id}_{uuid}`).
  - Timestamps stored in UTC: `event_timestamp` (actual visual occurrence) and `recorded_at` (system ingestion).
  - Active session maintains start time, current service status (`WAITING_FOR_ATTENDANCE`), active tracks, and customer count.
  - On vacancy confirmation, session is closed with valid end timestamp and calculated occupancy duration ($T_{end} - T_{seating}$).
  - Restart durability: Active sessions and table states persist to disk (`config/sessions.json`) and recover on restart.
  - Manager overrides and audit trail: Manager state overrides, customer count corrections, and session reopening recorded with actor and reason.
- **Visualizer & REST API**:
  - Overlays with state badges, timers, and count indicators.
  - Full REST API under `/api/v1/occupancy`.
  - Deterministic replay test suite and CLI demonstration script.

## Tasks Breakdown

1. **Occupancy Schemas & Data Models (`src/smartserve/occupancy/schema.py`)**:
   - Enums: `OccupancyState`, `ServiceStatus`, `EventSource`, `VerificationStatus`.
   - Models: `TableSession`, `StateTransitionEvent`, `OccupancySnapshot`, `ManagerOverrideRequest`, `CustomerCountUpdateRequest`.

2. **Deterministic Table State Machine (`src/smartserve/occupancy/state_machine.py`)**:
   - `TableStateMachine`: Manages single-table state transitions following Rule 4.1.
   - Evaluates persistence window for `AVAILABLE` -> `POSSIBLY_OCCUPIED` -> `OCCUPIED`.
   - Filters transient passers-by (`POSSIBLY_OCCUPIED` -> `AVAILABLE`).
   - Evaluates vacancy grace window for `OCCUPIED` -> `POSSIBLY_VACANT` -> `CLEANING_REQUIRED` / `AVAILABLE`.
   - Handles occlusion recovery (`POSSIBLY_VACANT` -> `OCCUPIED`).
   - Handles camera stale/disconnect preserving state without false vacancy.
   - Customer count smoothing via sliding window.
   - Manager override and correction hooks with audit logging.

3. **Session & Persistence Lifecycle Manager (`src/smartserve/occupancy/manager.py`)**:
   - `OccupancySessionManager`: Orchestrates state machines across all configured tables and cameras.
   - Ingests spatial association output from Phase 3 (`TrackAssociation` list).
   - Atomic disk persistence (`config/sessions.json` and audit log `config/occupancy_audit.jsonl`).
   - Application restart recovery: Restores active sessions and table states.
   - Query methods for tables, sessions, and audit records.

4. **Visualizer Overlays (`src/smartserve/vision/visualizer.py`)**:
   - `draw_occupancy_state_overlay()`: Renders state badges (color-coded by state), session duration timer, service status, and estimated guest count above tables.

5. **REST API Endpoints (`src/smartserve/api/routes/occupancy.py`)**:
   - `GET /api/v1/occupancy`: Current table occupancy statuses.
   - `GET /api/v1/occupancy/{table_id}`: Detailed table occupancy state and active session.
   - `POST /api/v1/occupancy/{table_id}/override`: Manager state override.
   - `POST /api/v1/occupancy/{table_id}/count`: Manager customer count correction.
   - `GET /api/v1/occupancy/sessions`: Session history and active sessions.
   - `GET /api/v1/occupancy/audit`: Transition audit log.
   - Register route in `src/smartserve/main.py`.

6. **Demonstration Utility (`scripts/demo_occupancy_lifecycle.py`)**:
   - Deterministic simulation of full table lifecycle: passerby rejection, seating confirmation, occlusion recovery, session closure, cleaning transition, and camera failure preservation.

7. **Comprehensive Unit & Replay Tests (`tests/test_occupancy_state_machine.py`)**:
   - Unit tests for all transitions in Rule 4.1.
   - Deterministic replay tests using stepped virtual timestamps.
   - Occlusion tolerance and camera outage resilience tests.
   - State persistence and restart recovery tests.
   - REST API integration tests.

## Verification Criteria
- [ ] State transitions follow the documented state machine in `RULES.md` Section 4.
- [ ] Brief occlusion does not automatically end an active session.
- [ ] A completed session has valid start/end timestamps and non-negative duration.
- [ ] Camera outage / stale feed does not automatically mark tables vacant.
- [ ] Transient passers-by do not trigger table occupancy sessions.
- [ ] Customer count is smoothed across consecutive observations.
- [ ] Manager overrides and count corrections are logged to audit history.
- [ ] Active sessions survive application restart.
- [ ] 100% of test suite passes.
