# 📏 SmartServe AI — Operational and Event Rules

**Document:** Occupancy, Event Validation, Timing, and Alert Rules  
**Version:** 1.0  
**Status:** Proposed

## 1. Purpose

This document defines deterministic rules for converting camera observations and staff/POS confirmations into table states, service sessions, metrics, and alerts. Thresholds in this file are **initial defaults for development** and must be configurable per restaurant. They are not universal service standards.

## 2. Fundamental Rules

1. A vision detection is an observation, not automatically a confirmed business event.
2. A temporary tracking ID is not a permanent person identity.
3. A person near a table is not sufficient evidence of waiter attendance.
4. A visual object or tray near a table is not sufficient proof of food delivery.
5. Missing camera frames must not be interpreted as table vacancy.
6. Every operational event must preserve source and verification status.
7. Use event timestamps for duration calculations, not frame counts or dashboard refresh time.
8. Do not fabricate missing timestamps or substitute a threshold time for an actual event time.
9. Corrections must be auditable.
10. Performance metrics are operational indicators and must not independently determine disciplinary outcomes.

## 3. Core Enumerations

### 3.1 Occupancy State

- `AVAILABLE`
- `POSSIBLY_OCCUPIED`
- `OCCUPIED`
- `POSSIBLY_VACANT`
- `CLEANING_REQUIRED`
- `OUT_OF_SERVICE`
- `UNKNOWN` (recommended for stale or untrustworthy observations)

### 3.2 Service Status

- `WAITING_FOR_ATTENDANCE`
- `ATTENDED`
- `WAITING_FOR_FOOD`
- `PARTIALLY_SERVED`
- `SERVED`
- `COMPLETED`
- `NEEDS_REVIEW`

A restaurant may configure which milestones apply to its service model. For example, food delivery is not required for every café or bar workflow.

### 3.3 Event Verification Status

- `CANDIDATE`: generated from uncertain evidence and not yet accepted as a business fact.
- `CONFIRMED`: confirmed by an authorized user or trusted configured integration, or by a separately validated automation policy.
- `CORRECTED`: an authorized correction has been applied; preserve the original event and correction history.
- `REJECTED`: reviewed and rejected as incorrect.

### 3.4 Event Sources

`vision`, `waiter_ui`, `manager_ui`, `pos`, `kds`, `system`.

## 4. Occupancy State Machine

### 4.1 Transition Rules

| Current State | Trigger | Next State | Required Behavior |
|---|---|---|---|
| `AVAILABLE` | Person/table evidence begins | `POSSIBLY_OCCUPIED` | Start candidate persistence timer |
| `POSSIBLY_OCCUPIED` | Evidence persists for configured window | `OCCUPIED` | Create session if none is active |
| `POSSIBLY_OCCUPIED` | Evidence disappears before confirmation | `AVAILABLE` | Discard candidate or retain diagnostic observation |
| `OCCUPIED` | No reliable occupancy evidence | `POSSIBLY_VACANT` | Start vacancy grace timer |
| `POSSIBLY_VACANT` | Occupancy evidence returns | `OCCUPIED` | Cancel vacancy candidate |
| `POSSIBLY_VACANT` | Vacancy condition persists | `CLEANING_REQUIRED` or `AVAILABLE` | Close session; follow cleaning policy |
| Any operational state | Manager marks unavailable | `OUT_OF_SERVICE` | Audit actor and reason |
| `OUT_OF_SERVICE` | Manager reopens table | `AVAILABLE` | Audit change |
| Any state | Camera/data quality becomes untrustworthy | `UNKNOWN` or stale overlay | Do not infer vacancy from missing data |

### 4.2 Initial Occupancy Parameters

| Parameter | Suggested Default | Notes |
|---|---:|---|
| Occupancy confirmation window | 5 seconds | Require persistent evidence; tune using footage |
| Vacancy grace period | 20 seconds | Avoid closing sessions during short occlusion |
| Track missing grace period | 3 seconds | Tracker-specific; not a session end rule |
| Stale camera threshold | 30 seconds | Mark state stale and raise system alert |
| Minimum count smoothing window | 3 observations | Adjust to frame sampling and scene complexity |

These values are examples. Use configuration rather than hard-coding them.

### 4.3 Session Rules

- A table may have at most one active session under normal operation.
- A session begins when occupancy is confirmed or an authorized user confirms seating.
- Store the actual event timestamp and the server-recorded timestamp separately.
- Customer count is an estimate unless manually confirmed.
- A short loss of tracking does not create a new session.
- A session closes only after vacancy confirmation or authorized manager action.
- If a closed table becomes occupied again, create a new session unless a manager explicitly reopens the prior session after correcting a mistaken closure.
- If the application restarts, recover active sessions from persisted state.
- If camera data is stale, retain the last known state with a stale indicator; do not automatically close active sessions.

## 5. Table-to-Person Association Rules

1. Use configured table polygons associated with the correct camera.
2. Prefer an anchor point such as the lower-center of a person box, optionally combined with box overlap.
3. Require temporal persistence before changing occupancy.
4. If a person could belong to multiple adjacent tables, mark the association ambiguous unless a configured tie-break rule has sufficient evidence.
5. Do not count one track more than once for a table in the same observation window.
6. Deduplicate tracks across cameras only if a validated cross-camera association system exists; otherwise treat camera-level tracks separately.
7. Count seated customers only as an estimate unless the scene and association method are validated.
8. If confidence or coverage is insufficient, display `Unknown` or an uncertainty label instead of a precise unsupported count.

## 6. Attendance Event Rules

### 6.1 Eligible First Attendance

The first-response timer ends at the earliest **eligible confirmed attendance event** associated with the active session.

An eligible attendance event must:
- reference the correct active session/table;
- have a valid event timestamp;
- have a supported source and verification status;
- pass duplicate/idempotency checks;
- not be rejected or superseded by a correction.

A waiter UI confirmation or trusted operational integration may confirm attendance. A vision-only approach event should remain a candidate unless a separately evaluated policy explicitly permits automatic confirmation.

### 6.2 Duplicate Attendance

- Store distinct legitimate subsequent interactions if the product needs them.
- Do not replace the first attendance timestamp when another visit is recorded.
- Retried submissions with the same idempotency key must not create duplicate events.

### 6.3 Missing Attendance

If no eligible attendance event exists, first-response time remains pending. An overdue alert may be generated, but the system must not assign the threshold timestamp as if attendance occurred then.

## 7. Food Delivery Rules

- Record each legitimate delivery event, because orders may arrive in multiple batches.
- The first-delivery timestamp is the earliest eligible confirmed delivery event in the session.
- A waiter approaching or carrying an object is not, by itself, confirmed delivery.
- Supported sources may include waiter confirmation, manager confirmation, or a trusted POS/KDS integration.
- Vision-based delivery detection must record confidence and should remain a candidate until the automation policy is validated.
- If delivery is not applicable to a service type, mark it `NOT_APPLICABLE` in the relevant workflow rather than treating it as overdue.
- Corrected/rejected events must be excluded from active metric calculations according to audit rules.
- If an event arrives late, preserve both event occurrence time and ingestion time; recalculate affected metrics safely.

## 8. Timestamp and Duration Rules

### 8.1 Timestamp Storage

- Store timestamps in UTC.
- Display times in the restaurant's configured time zone.
- Use timezone-aware timestamps at API boundaries.
- Record `event_timestamp` (when the event occurred) and `recorded_at` (when the system stored it).
- Do not assume the browser clock is authoritative.

### 8.2 Metric Definitions

Let:
- `T_seating` = confirmed session start timestamp;
- `T_attendance` = first eligible confirmed attendance timestamp;
- `T_food` = first eligible confirmed food-delivery timestamp;
- `T_end` = confirmed session end timestamp.

First-response time:

$$
T_{response} = T_{attendance} - T_{seating}
$$

Time to first food delivery:

$$
T_{food} = T_{first\ delivery} - T_{seating}
$$

Attendance-to-delivery interval:

$$
T_{attendance\rightarrow food} = T_{first\ delivery} - T_{first\ attendance}
$$

Occupancy duration:

$$
T_{occupancy} = T_{end} - T_{seating}
$$

### 8.3 Validity Rules

- If any required timestamp is missing, metric is `PENDING` or `N/A`, as appropriate.
- If an interval is negative, flag the event/session for review and exclude the interval from standard aggregates until resolved.
- Do not silently clamp negative intervals to zero.
- Define whether paused, reopened, or corrected sessions are included in reports.
- Store durations as numeric seconds or milliseconds; format for display in the client.
- Use a monotonic clock only for measuring local elapsed processing time, not for cross-system event timestamps.

## 9. Service Status Rules

A suggested default workflow is:

1. Session starts → `WAITING_FOR_ATTENDANCE`.
2. First attendance confirmed → `ATTENDED`.
3. If an order requires food delivery → `WAITING_FOR_FOOD`.
4. Some but not all expected items delivered → `PARTIALLY_SERVED`.
5. Required delivery milestone satisfied → `SERVED`.
6. Session ends and configured workflow is satisfied → `COMPLETED`.
7. Conflicting timestamps, ambiguous session association, or significant data issue → `NEEDS_REVIEW`.

Do not require food-delivery status for workflows where it is not applicable. Keep occupancy state and service status as separate fields; a table may be occupied while its service status is completed or served.

## 10. Alert Rules

### 10.1 Suggested Initial Thresholds

All thresholds must be configurable by restaurant, service type, and optionally shift.

| Alert | Example Threshold | Severity | Clear/Resolve Condition |
|---|---:|---|---|
| First attendance overdue | 3 minutes after seating | Warning | Eligible attendance confirmed or session closed/corrected |
| First attendance critically overdue | 5 minutes after seating | Critical | Same as above; do not duplicate warning endlessly |
| First food delivery overdue | 15 minutes after seating or configured order milestone | Warning | Eligible delivery confirmed, marked not applicable, or session closed |
| No recorded interaction | 10 minutes since last eligible interaction | Review | New eligible interaction or manager resolution |
| Camera stale/disconnected | 30 seconds without a valid frame | Critical/System | Camera health recovers and remains stable |
| Occupancy uncertain | Configurable persistence window | Review | State becomes reliable or manager resolves |
| Data inconsistency | Immediately upon detection | Review | Data corrected or issue explicitly resolved |

These defaults are placeholders for pilot testing, not industry-wide recommendations.

### 10.2 Alert Evaluation

- Evaluate threshold conditions against event timestamps and current server time.
- Create at most one active alert per configured deduplication key (for example, session + alert type + rule version).
- Record rule version and threshold value used when the alert was created.
- Escalate an existing alert if the configured escalation threshold is crossed; do not create a new alert every frame.
- When a qualifying event arrives, re-evaluate and resolve the alert only if the rule's resolution condition is satisfied.
- Allow acknowledgment separately from resolution.
- Manager dismissal must preserve a reason and audit trail when configured.
- Avoid alerting for a service milestone that is not applicable to the session's service type.

### 10.3 Alert Status Lifecycle

`ACTIVE` → `ACKNOWLEDGED` → `RESOLVED`

A rule may resolve an active alert automatically when its condition clears. An acknowledged alert can remain unresolved until the condition clears or an authorized manager resolves it with an appropriate reason.

## 11. Unusual Activity Rules

Potential events include:
- table appears vacant but objects remain;
- unusually long occupancy;
- customer departure appears likely before a service milestone;
- cleaning may be required;
- no interaction recorded for an unusually long period;
- conflict between vision state and POS/manual state.

Rules:
- Create a review flag, not a definitive accusation.
- Record the observed evidence, timestamp, source, and confidence where available.
- Do not infer theft, intent, customer dissatisfaction, or employee negligence from these signals.
- Require human review before taking operational action beyond a low-risk notification.
- Avoid saving image/video evidence unless policy, authorization, and retention controls permit it.

## 12. Customer Count Rules

- Current customer count is an estimate from active tracks associated with a table.
- Apply configurable temporal smoothing to reduce flicker.
- Do not sum raw detections across frames.
- Record count snapshots at a controlled interval rather than on every frame.
- A manual correction should include actor, time, and optional reason.
- Keep the raw estimate and confirmed correction distinguishable for evaluation.
- Do not infer customer identity from count or track ID.

## 13. Event Correction and Audit Rules

- Never silently overwrite an event's source history.
- Store original event, correction actor, correction timestamp, reason, and replacement values.
- Recalculate dependent metrics and alert state when an event changes eligibility.
- Preserve an audit trail for table layout, thresholds, assignments, and permissions changes.
- Limit correction privileges to authorized roles.
- Report corrected events distinctly in audit views.

## 14. Data Quality and Reporting Rules

- Report mean and median separately.
- Include sample size and data completeness for every aggregate.
- Exclude missing or invalid intervals from standard duration averages, and disclose the exclusion.
- Define whether candidate or estimated events are included in exploratory reports; confirmed-only should be the default for official operational metrics.
- Use consistent threshold definitions across dashboard and exported reports.
- Do not compare periods with materially different event coverage without a data-quality warning.
- Table turnover should be reported as completed sessions per table over a stated period, or sessions per table-hour if time-normalized.
- Table utilization denominator includes only time when a table was operational and available for service.

## 15. Failure and Recovery Rules

### Camera failure
- Mark camera disconnected after configured timeout.
- Mark affected states stale/unknown.
- Do not close sessions based solely on missing frames.
- Resume with a reconciliation period after recovery.

### Database failure
- Do not acknowledge event persistence until transaction success is known.
- If using an in-memory queue, bound it and define retry/dead-letter behavior.
- Avoid losing critical manual confirmations silently.

### WebSocket failure
- Client shows disconnected/stale state.
- Reconnect with backoff.
- Fetch authoritative current state through REST after reconnect.

### Application restart
- Recover active sessions and unresolved alerts from persistence.
- Do not generate duplicate sessions or alerts when replaying events.

## 16. Configuration Schema Example

```yaml
occupancy:
  confirmation_seconds: 5
  vacancy_grace_seconds: 20
  stale_camera_seconds: 30
  count_smoothing_observations: 3

service_alerts:
  first_attendance_warning_seconds: 180
  first_attendance_critical_seconds: 300
  first_food_delivery_warning_seconds: 900
  no_interaction_review_seconds: 600
  deduplicate_active_alerts: true

metrics:
  official_reports_confirmed_events_only: true
  show_sample_size: true
  show_data_completeness: true

privacy:
  persist_raw_video: false
  retention_policy_required: true
```

The example is illustrative. Validate configuration on startup, reject invalid or contradictory thresholds, and document precedence if restaurant-, shift-, and table-level settings are supported.

## 17. Test Scenarios

- [ ] A passer-by briefly enters a table region: no confirmed occupancy session is created.
- [ ] Occupancy evidence persists: one session starts with the correct timestamp.
- [ ] Brief occlusion occurs: the session remains active.
- [ ] Vacancy persists beyond grace period: the session closes once.
- [ ] Camera goes offline: table does not become vacant solely due to missing frames.
- [ ] Attendance is confirmed: first-response metric is calculated once.
- [ ] Attendance is missing: metric stays pending while an overdue alert may be active.
- [ ] Food is delivered in two batches: both events are stored and first delivery remains stable.
- [ ] Duplicate webhook/request is received: idempotency prevents duplicate event records.
- [ ] Event timestamp precedes seating: event is flagged for review.
- [ ] A correction invalidates a first-delivery event: metrics and alerts are recalculated and audited.
- [ ] Alert threshold is crossed: one active alert is created, not one per frame.
- [ ] Threshold is met exactly: boundary behavior matches documented comparison semantics.
- [ ] Dashboard reconnects: authoritative state is refetched.

## 18. Rule Change Governance

- Keep thresholds in validated configuration, not scattered constants.
- Record rule/configuration version with alerts and relevant metric snapshots.
- Add tests whenever state transitions or metric definitions change.
- Document changes that affect historical comparability.
- Pilot changes against labeled data before enabling automatic visual confirmation for new event types.
