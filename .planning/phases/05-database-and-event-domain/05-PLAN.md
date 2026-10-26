# Phase 5: Database and Event Domain Plan

## Phase Goal
Implement production-grade relational database infrastructure and event domain architecture using SQLAlchemy 2.0 (asyncio + sync support), Alembic migrations, PostgreSQL & SQLite compatibility, transaction-safe session/event lifecycle operations, idempotent event ingestion, audit trail preservation with event correction semantics, query performance indexes, and disaster recovery procedures as specified in `Docs/PRD.md` Section 8, `Docs/RULES.md` Section 15, and `Docs/TASKS.md`.

## Requirements Covered
- **FR-07: Operational Event Storage & Data Integrity (PRD.md Section 8 & RULES.md)**:
  - Core entities: `Restaurant`, `Camera`, `Table`, `User`, `TableSession`, `ServiceEvent`, `WaiterAssignment`, `Alert`, and `AuditLog`.
  - UTC timestamps across all models; foreign key integrity with explicit cascade policies.
  - Event schemas with source (`VISION`, `WAITER_UI`, `POS`, `MANAGER_OVERRIDE`, `SYSTEM`) and verification status (`CANDIDATE`, `CONFIRMED`, `CORRECTED`, `REJECTED`).
  - Idempotency guarantees: unique `idempotency_key` constraint preventing duplicate operational event persistence on retries.
  - Non-destructive event correction: superseding events link to original records (`supersedes_event_id`), marking previous events as `CORRECTED`/`REJECTED` while preserving complete audit history.
  - Transaction-safe event and session state transitions: atomic updates ensuring session timestamps (`started_at`, `first_attendance_at`, `first_food_delivery_at`, `ended_at`) and status updates stay synchronized with event records.
  - Composite and targeted indexes for rapid querying on `(table_id, event_timestamp)`, `(session_id, event_type)`, `(event_type, event_timestamp)`, `(status, severity)`, and audit logs.
  - Full Alembic migration suite initializing the relational schema from an empty database.
  - Development data backup/restore tooling and instructions for SQLite and PostgreSQL.

## Tasks Breakdown

1. **Database Core Infrastructure (`src/smartserve/database/`)**:
   - `session.py`: Async engine, sessionmaker, dependency injection `get_db()`, SQLite WAL pragma support, sync engine for migrations/tools.
   - `base.py`: DeclarativeBase with UUID helpers, UTC datetime mixins, and serialization utilities.
   - `models.py`: Clean, typed SQLAlchemy 2.0 declarative models for `Restaurant`, `Camera`, `Table`, `User`, `TableSession`, `ServiceEvent`, `WaiterAssignment`, `Alert`, and `AuditLog`.
   - Comprehensive composite indexing and foreign key constraints.

2. **Alembic Migrations Configuration**:
   - `alembic.ini` configuration.
   - `migrations/env.py`: Async/sync migration runner linked with `Base.metadata`.
   - `migrations/script.py.mako`: Migration template.
   - Initial migration `0001_initial_schema.py` creating all tables, indexes, and constraints.

3. **Event Domain & Pydantic Schemas (`src/smartserve/events/`)**:
   - `schema.py`: Pydantic V2 schemas: `EventType`, `EventSource`, `VerificationStatus`, `SessionStatus`, `AlertSeverity`, `AlertStatus`, `UserRole`, `ServiceEventCreate`, `ServiceEventRead`, `EventCorrectionRequest`, `TableSessionRead`, `AlertCreate`, `AlertRead`, `AuditLogRead`.
   - `service.py`: `EventDomainService` implementing:
     - Transaction-safe event recording with atomic session state updates (`create_event`).
     - Idempotent deduplication against `idempotency_key`.
     - Event correction workflow preserving immutable history (`correct_event`).
     - Alert creation, deduplication, and resolution (`create_or_update_alert`).
     - Audit logging on corrections and managerial actions.

4. **Occupancy Manager Integration (`src/smartserve/occupancy/`)**:
   - Extend `OccupancySessionManager` with an optional database persistence bridge (`DatabaseEventSink`), recording state changes and session lifecycles directly into the relational database alongside atomic JSON fallback.

5. **REST API Routes (`src/smartserve/api/routes/events.py` & alerts)**:
   - `POST /api/v1/events`: Ingest operational events with idempotency.
   - `POST /api/v1/events/{event_id}/correct`: Correct an event with reason and audit log.
   - `GET /api/v1/events`: Filtered event query (by table, session, date range, type).
   - `GET /api/v1/sessions`: Query table sessions with event history.
   - `GET /api/v1/alerts`: Query active and acknowledged alerts.
   - `POST /api/v1/alerts/{alert_id}/acknowledge`: Acknowledge alert.
   - `POST /api/v1/alerts/{alert_id}/resolve`: Resolve alert.
   - `GET /api/v1/audit`: Query audit logs.
   - Mount routes into `src/smartserve/main.py`.

6. **Database Management & Backup Tooling**:
   - CLI script `scripts/db_manage.py`: migration execution, database seeding (`seed`), SQLite snapshot backup & restore.
   - Documentation in `Docs/DATABASE_BACKUP_RESTORE.md`.

7. **Automated Verification Test Suite (`tests/test_database_and_events.py`)**:
   - Schema generation from empty database via Alembic / SQLAlchemy metadata.
   - Model constraint tests (foreign keys, non-null, unique table_code per restaurant).
   - Idempotency test (duplicate submission with identical `idempotency_key` yields existing record without duplicates).
   - Event correction test (history preserved, superseded link established, audit log recorded, session timestamp recalculated).
   - Transaction atomicity & rollback verification.
   - REST API endpoint verification for events, corrections, sessions, and alerts.

## Verification Criteria
- [ ] Alembic migrations run cleanly and create full schema from an empty database.
- [ ] Duplicate event submissions with same idempotency key are safely deduplicated.
- [ ] Event corrections retain original records, update verification status, log audit entries, and link superseding records.
- [ ] Transaction rollbacks cleanly leave database untouched upon error.
- [ ] Session lifecycle timestamps (`started_at`, `first_attendance_at`, `first_food_delivery_at`, `ended_at`) synchronize accurately with service events.
- [ ] Database backup and restore commands operate predictably.
- [ ] 100% of test suite (existing 56 tests + new database tests) passes.
