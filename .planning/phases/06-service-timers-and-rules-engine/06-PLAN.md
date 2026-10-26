# Phase 6: Service Timers and Rules Engine Plan

## Phase Goal
Implement production-grade service interval calculation engine, configurable threshold rules, alert lifecycle management with automatic escalation and resolution, negative interval / anomaly detection, and event correction recalculation in accordance with `Docs/PRD.md` Section 8, `Docs/RULES.md` Sections 6-10, and `Docs/TASKS.md` Phase 6.

## Requirements Covered
- **FR-06: Service Timing Calculations & Integrity (PRD.md Section 8 & RULES.md Sections 6, 7, 8)**:
  - First-response time: $T_{response} = T_{attendance} - T_{seating}$.
  - Food delivery time: $T_{food} = T_{first\_delivery} - T_{seating}$.
  - Attendance-to-delivery interval: $T_{attendance \rightarrow food} = T_{first\_delivery} - T_{first\_attendance}$.
  - Occupancy duration: $T_{occupancy} = T_{end} - T_{seating}$.
  - Missing-event handling: return `None` (pending) with no fabricated timestamps or fallback to threshold times.
  - Anomaly & negative interval detection: detect $T_{attendance} < T_{seating}$ or $T_{food} < T_{seating}$; flag `is_negative=True`, set `SessionStatus.NEEDS_REVIEW`, and prevent silent clamping to zero.
- **FR-08: Configurable Service Thresholds & Alerts Engine (PRD.md Section 8 & RULES.md Section 10)**:
  - Configurable threshold configurations per restaurant / service type:
    - First attendance overdue (Warning & Critical thresholds).
    - Food delivery overdue (Warning & Critical thresholds).
    - No interaction overdue (Review/Warning).
    - Session occupancy limit exceeded.
  - Alert Deduplication: strict 1-active-alert per `{session_id}:{alert_type}` deduplication key.
  - Alert Escalation: seamless in-place upgrade from `WARNING` to `CRITICAL` when critical threshold is crossed without generating duplicate alerts.
  - Automatic Resolution: qualifying events (attendance, food delivery, session completion) automatically clear/resolve corresponding active alerts with resolution reason (`EVENT_CONFIRMED`).
  - Event Correction Integration: event corrections trigger safe recalculation of session timers, status, and alert states.
  - Multi-timezone robustness: all calculations preserve timezone-aware UTC timestamps.

## Tasks Breakdown

1. **Service Timers Engine (`src/smartserve/rules/timers.py`)**:
   - `SessionTimersCalculator`: Pure domain service computing $T_{response}$, $T_{food}$, $T_{attendance \rightarrow food}$, and $T_{occupancy}$.
   - Validation & anomaly flags (`is_negative`, `is_inconsistent`, `pending_metrics`).
   - Monotonic safety and UTC timestamp validation.

2. **Rules & Thresholds Engine (`src/smartserve/rules/engine.py` & `src/smartserve/rules/thresholds.py`)**:
   - `ServiceThresholds` Pydantic model for configurable warning & critical thresholds.
   - `RulesEngine`: Evaluates active dining sessions against thresholds at `T_{now}` (or custom simulation timestamp).
   - Generates alerts with deduplication keys (`{session_id}:{alert_type}`).
   - Escalates existing `WARNING` alerts to `CRITICAL` without duplicate creation.
   - Auto-resolves overdue alerts when qualifying events are confirmed.
   - Integrates with `EventDomainService` to trigger recalculation upon event corrections.

3. **REST API Endpoints (`src/smartserve/api/routes/rules.py` & updates to `events.py`)**:
   - `GET /api/v1/sessions/{session_id}/timers`: Retrieve precise computed metrics, intervals, and anomaly status for a session.
   - `POST /api/v1/rules/evaluate`: Trigger evaluation of active sessions and return generated/escalated/resolved alert summaries.
   - `GET /api/v1/rules/thresholds`: Read active service thresholds.
   - `PUT /api/v1/rules/thresholds`: Update thresholds with audit logging.
   - Mount router into `src/smartserve/main.py`.

4. **Integration with Database Event Domain (`src/smartserve/events/service.py`)**:
   - Update `record_event` and `correct_event` to invoke rules engine auto-resolution and recalculation.

5. **Chronological Demo Script (`scripts/demo_rules_engine.py`)**:
   - Demonstration script simulating seating, threshold boundary crossing (warning, critical escalation), attendance confirmation auto-resolution, food delivery tracking, and correction recalculation.

6. **Comprehensive Test Suite (`tests/test_service_timers_and_rules.py`)**:
   - Exact interval math ($T_{response}$, $T_{food}$, $T_{attendance \rightarrow food}$, $T_{occupancy}$).
   - Missing event handling (no fabrication).
   - Boundary tests: just-before ($T_{thresh} - 1s$), exactly-at ($T_{thresh}$), just-after ($T_{thresh} + 1s$).
   - Escalation tests: Warning -> Critical.
   - Deduplication verification: single active alert per condition.
   - Auto-resolution on qualifying event arrival.
   - Negative interval flagging without zero clamping.
   - Event correction recalculation and audit integrity.
   - Timezone robustness across non-UTC and UTC datetimes.

## Verification Criteria
- [ ] Timers return exact numeric seconds and return `None` when events are pending.
- [ ] Negative intervals flag anomaly and `SessionStatus.NEEDS_REVIEW` without clamping to zero.
- [ ] Alert evaluation produces at most one active alert per deduplication key.
- [ ] Warning alerts escalate to Critical when critical threshold is crossed without duplicate alerts.
- [ ] Confirmed attendance/food-delivery events automatically resolve active overdue alerts.
- [ ] Event correction triggers safe recalculation of session timers and alert states.
- [ ] 100% of test suite passes cleanly.
