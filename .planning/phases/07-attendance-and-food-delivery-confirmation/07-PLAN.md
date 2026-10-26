# Phase 7: Attendance and Food-Delivery Confirmation Plan

## Phase Goal
Implement waiter and manager attendance and food-delivery confirmation workflows, actor authorization and table session validation, idempotent event submission, multiple delivery batch tracking, rejection and correction workflows with automatic metric recalculation, POS/KDS integration adapter interfaces, and timeline presentation with explicit UI copy distinguishing human confirmations from AI estimations in accordance with `Docs/PRD.md` (FR-07, FR-08, FR-09), `Docs/RULES.md` (Sections 3.3, 3.4, 6, 7, 8), and `Docs/TASKS.md` Phase 7.

## Requirements Covered
- **FR-07: Waiter Activity Tracking & Confirmation (PRD.md Section 8 & RULES.md Section 6)**:
  - Waiter/manager attendance confirmation endpoints.
  - Require active table session association: reject confirmations if table has no active session.
  - Enforce actor authorization (WAITER, MANAGER, ADMIN roles; reject UNAUTHORIZED or INACTIVE users).
  - Record `source` (`WAITER_UI`, `MANAGER_OVERRIDE`), `actor` (`created_by`), `event_timestamp` (visual occurrence), and `recorded_at` (server ingestion).
  - Support idempotent submissions via `idempotency_key`.
- **FR-08: First Attendance Milestone & Deduplication (PRD.md Section 8 & RULES.md Section 6.1-6.3)**:
  - First eligible confirmed attendance sets session `first_attendance_at` and auto-resolves `FIRST_ATTENDANCE_OVERDUE` alerts.
  - Subsequent attendance events are recorded for audit/timeline without overwriting `first_attendance_at`.
- **FR-09: Food Delivery Tracking & Multiple Delivery Batches (PRD.md Section 8 & RULES.md Section 7)**:
  - Food delivery confirmation endpoint.
  - Support multiple delivery events per session (appetizers, mains, desserts, batches 1..N).
  - First eligible confirmed delivery sets `first_food_delivery_at` and auto-resolves `FOOD_DELIVERY_OVERDUE` alerts. Subsequent deliveries preserve the initial milestone while enriching the session timeline.
- **Mistaken Event Rejection & Correction Workflow (RULES.md Section 3.3 & Section 8)**:
  - `POST /api/v1/events/{event_id}/reject` allowing MANAGER or ADMIN to reject mistaken candidate or confirmed events with an audit reason.
  - Automatic session recalculation: rejecting an event safely recomputes session milestones (`first_attendance_at`, `first_food_delivery_at`) from remaining eligible confirmed events and re-evaluates active alerts.
  - Preserve immutable audit logging for corrections and rejections.
- **POS / KDS Adapter Interface (Docs/TASKS.md Phase 7)**:
  - Abstract adapter interfaces `BasePOSAdapter` and `BaseKDSAdapter` under `src/smartserve/integrations/`.
  - Reference implementations `MockPOSAdapter` and `MockKDSAdapter` for order/payment ingestion and kitchen bump bar events.
  - Integration webhook endpoints `/api/v1/integrations/pos/order` and `/api/v1/integrations/kds/bump`.
- **Timeline & UI Copy Distinguishing Confirmation from AI Estimation (RULES.md Section 2.1, 2.3, 2.4)**:
  - `GET /api/v1/sessions/{session_id}/timeline` returning structured timeline items.
  - Explicit UI copy badges clearly separating verified staff confirmations from unconfirmed AI vision detections (e.g., "Confirmed by Waiter Sam", "AI Vision Estimate (Candidate)").

## Task Breakdown

1. **Security & Actor Authorization (`src/smartserve/security/auth.py`)**:
   - `get_current_actor` dependency supporting `X-User-ID`, `X-User-Role`, or query/body user identification.
   - Database validation ensuring user exists and is active.
   - Role enforcement helpers: `require_roles([UserRole.WAITER, UserRole.MANAGER, UserRole.ADMIN])` and `require_manager_or_admin`.

2. **Domain Service Enhancements (`src/smartserve/events/service.py`)**:
   - `confirm_attendance`: validates active session for table, enforces actor, records event idempotently, auto-resolves alerts.
   - `confirm_food_delivery`: validates active session, enforces actor, supports batch/course metadata, preserves earliest delivery milestone while logging subsequent events, auto-resolves alerts.
   - `reject_event`: marks event `REJECTED`, creates `AuditLog`, recalculates session milestones and alerts via `RulesEngine.recalculate_session`.
   - `get_session_timeline`: builds ordered timeline with actor display names, active milestone flags, and human-friendly UI copy badges.

3. **POS / KDS Adapter Interfaces (`src/smartserve/integrations/`)**:
   - `base.py`: Abstract `BasePOSAdapter` and `BaseKDSAdapter`.
   - `adapters.py`: `MockPOSAdapter` and `MockKDSAdapter`.
   - `routes.py`: REST endpoints `/api/v1/integrations/pos/order` and `/api/v1/integrations/kds/bump`.

4. **REST API Confirmation & Timeline Endpoints (`src/smartserve/api/routes/events.py` & `src/smartserve/main.py`)**:
   - Enhance `POST /api/v1/events/attendance` with session validation, actor authorization, and request schemas.
   - Enhance `POST /api/v1/events/food-delivery` with session validation, course/batch metadata, and actor authorization.
   - Add `POST /api/v1/events/{event_id}/reject` with manager/admin authorization.
   - Add `GET /api/v1/sessions/{session_id}/timeline` for dashboard display.
   - Mount integrations router into `src/smartserve/main.py`.

5. **Chronological Demo Script (`scripts/demo_confirmations.py`)**:
   - Demonstrates seating -> overdue alert -> authorized waiter attendance confirmation (alert resolved) -> first food delivery (batch 1) -> second food delivery (batch 2) -> mistaken event rejection -> recalculation -> timeline query.

6. **Comprehensive Test Suite (`tests/test_attendance_and_food_confirmation.py`)**:
   - Authorized attendance confirmation.
   - Authorized food delivery confirmation (single and multiple batches).
   - Rejection of unauthorized actor (non-existent user, inactive user, insufficient role).
   - Rejection when table has no active session or wrong table association.
   - Idempotency on repeated submissions.
   - Event rejection workflow with audit trail and session milestone recalculation.
   - POS and KDS adapter event ingestion.
   - Timeline endpoint with UI copy verification.

## Verification Criteria
- [ ] Waiter and manager can confirm attendance and food delivery.
- [ ] Unauthorized requests (missing user, inactive user, or insufficient role) return 401/403.
- [ ] Requests without an active table session return 400 Bad Request.
- [ ] Repeated submissions with same idempotency key are handled idempotently.
- [ ] Multiple food delivery batches in the same session are supported without corrupting the first-delivery milestone.
- [ ] Mistaken events can be rejected by a manager, creating an audit log and triggering automatic metric recalculation.
- [ ] POS/KDS adapter interface cleanly ingests orders and food delivery bumps.
- [ ] Timeline endpoint returns clear UI copy distinguishing human confirmations from AI estimations.
- [ ] 100% of test suite passes cleanly.
