# Phase 4: Occupancy State Machine and Sessions Summary

**Phase Completed:** Phase 4 — Occupancy State Machine and Sessions  
**Date:** 2026-10-22  
**Status:** Complete  

## Deliverables Completed

1. **Occupancy Schemas & Data Models (`src/smartserve/occupancy/schema.py`)**:
   - `OccupancyState`: Complete 7-state enumeration conforming to `RULES.md` Section 3.1 (`AVAILABLE`, `POSSIBLY_OCCUPIED`, `OCCUPIED`, `POSSIBLY_VACANT`, `CLEANING_REQUIRED`, `OUT_OF_SERVICE`, `UNKNOWN`).
   - `ServiceStatus`: Milestone status enumeration conforming to `RULES.md` Section 3.2 & 9 (`WAITING_FOR_ATTENDANCE`, `ATTENDED`, `WAITING_FOR_FOOD`, `PARTIALLY_SERVED`, `SERVED`, `COMPLETED`, `NEEDS_REVIEW`).
   - `EventSource`: Operational event source taxonomy (`vision`, `waiter_ui`, `manager_ui`, `pos`, `kds`, `system`).
   - `VerificationStatus`: Audit status taxonomy (`CANDIDATE`, `CONFIRMED`, `CORRECTED`, `REJECTED`).
   - `TableSession`: Represents active or completed seating visit with UTC `start_time`, `end_time`, server `recorded_at`, estimated/max customer counts, active track list, duration calculations, and negative duration protection (Rule 8.3).
   - `StateTransitionEvent`: Auditable transition model with source attribution, verification status, actor, and structured evidence.
   - `TableOccupancyStatus`: Real-time table snapshot with current state, staleness flag, persistence timers, remaining vacancy grace, and active tracks.
   - `ManagerOverrideRequest` & `CustomerCountUpdateRequest`: Payloads for staff and manager actions.

2. **Deterministic Table State Machine (`src/smartserve/occupancy/state_machine.py`)**:
   - Implements full state transition table from `RULES.md` Section 4.1:
     - `AVAILABLE` -> `POSSIBLY_OCCUPIED`: Candidate evidence begins; starts confirmation window timer.
     - `POSSIBLY_OCCUPIED` -> `OCCUPIED`: Evidence persists for configured window (default 5.0s); triggers session creation.
     - `POSSIBLY_OCCUPIED` -> `AVAILABLE`: Evidence vanishes before confirmation window (transient passer-by filtered; no session created).
     - `OCCUPIED` -> `POSSIBLY_VACANT`: Evidence drops; starts vacancy grace period timer.
     - `POSSIBLY_VACANT` -> `OCCUPIED`: Evidence reappears within grace period; cancels vacancy candidate and preserves session uninterrupted.
     - `POSSIBLY_VACANT` -> `CLEANING_REQUIRED` / `AVAILABLE`: Grace period expires; confirms vacancy, closes session with valid end timestamp, calculates exact occupancy duration ($T_{end} - T_{seating}$).
     - `CLEANING_REQUIRED` -> `AVAILABLE`: Staff sanitizes and resets table.
     - Any State -> `OUT_OF_SERVICE`: Manager marks table unavailable with required audit justification.
   - Camera Health & Stale Feed Handling:
     - Enforces Rule 2.5 & 4.3: Missing frames or camera disconnect (`camera_healthy=False` or gap > `stale_threshold_sec`) marks state stale (`is_stale=True`), freezing vacancy timers and preventing false table vacancy.
   - Customer Count Temporal Smoothing:
     - Sliding window median filter eliminates single-frame tracking glitches.
     - Deduplicates track IDs in the same frame (Rule 5.5).

3. **Session & Persistence Lifecycle Manager (`src/smartserve/occupancy/manager.py`)**:
   - `OccupancySessionManager`: Orchestrates state machines across all restaurant tables and cameras.
   - Ingests spatial association output from Phase 3 (`process_associations` / `process_frame_result`).
   - Atomic disk persistence to `config/sessions.json` via temporary file swap (`os.replace`).
   - Append-only transition audit log to `config/occupancy_audit.jsonl`.
   - Application restart recovery: Restores active sessions, table states, and completed history without resetting timers.
   - Query APIs: `get_table_status`, `get_all_statuses`, `get_active_session`, `get_all_active_sessions`, `get_session_history`, `get_audit_log`.

4. **Visualizer Overlays (`src/smartserve/vision/visualizer.py`)**:
   - `draw_occupancy_state_overlay()`: Renders state-tinted translucent polygons, solid state perimeter outlines, centroid badges with table code, occupancy state, active session duration ($T_{now} - T_{seating}$), guest count, and top restaurant telemetry summary banner.

5. **REST API Endpoints (`src/smartserve/api/routes/occupancy.py`)**:
   - `GET /api/v1/occupancy`: Current occupancy statuses for all tables.
   - `GET /api/v1/occupancy/{table_id}`: Detailed status and active session for a table.
   - `POST /api/v1/occupancy/{table_id}/override`: Manager manual state override.
   - `POST /api/v1/occupancy/{table_id}/count`: Staff/manager guest count correction.
   - `POST /api/v1/occupancy/{table_id}/cleaned`: Staff marks table sanitized.
   - `GET /api/v1/occupancy/sessions`: Query active and historical sessions.
   - `GET /api/v1/occupancy/audit`: Query transition audit log.
   - `POST /api/v1/occupancy/process-frame`: Test frame association processing.
   - Registered in `src/smartserve/main.py`.

6. **Demonstration Utility (`scripts/demo_occupancy_lifecycle.py`)**:
   - Interactive and batch script simulating full occupancy lifecycle: passerby rejection, seating confirmation, occlusion tolerance, party departure, vacancy grace expiration, staff cleaning reset, camera outage preservation, and manager override.
   - Renders debug visualization frame to `demo_occupancy_lifecycle.png`.

7. **Comprehensive Unit & Integration Test Suite (`tests/test_occupancy_state_machine.py`)**:
   - 14 automated unit, replay, persistence, and REST API tests:
     - `test_table_session_lifecycle`
     - `test_state_transition_event_serialization`
     - `test_transient_passerby_filtered`
     - `test_persistent_seating_creates_session`
     - `test_occlusion_tolerance_preserves_active_session`
     - `test_vacancy_confirmation_and_session_closure`
     - `test_staff_marks_cleaned_returns_to_available`
     - `test_camera_outage_preserves_state_without_vacating`
     - `test_track_deduplication_and_count_smoothing`
     - `test_manager_manual_override_and_audit`
     - `test_manager_process_associations_and_audit_log`
     - `test_manager_persistence_and_restart_recovery`
     - `test_draw_occupancy_state_overlay`
     - `test_occupancy_api_lifecycle`
   - **Total project tests passing:** 56 tests in ~2.9s.
