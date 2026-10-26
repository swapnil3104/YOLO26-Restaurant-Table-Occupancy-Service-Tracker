# Database Architecture, Backup & Restore Guide

SmartServe AI uses **SQLAlchemy 2.0** with **Alembic** migrations and dual-engine support for **SQLite (WAL mode)** in lightweight/edge deployments and **PostgreSQL** in high-throughput enterprise deployments.

---

## 1. Schema Overview

The relational database architecture is defined in `src/smartserve/database/models.py` and mapped to Alembic migrations in `migrations/versions/`:

| Entity | Primary Key | Key Foreign Keys | Purpose |
|---|---|---|---|
| `restaurants` | `restaurant_id` (UUID) | None | Top-level restaurant tenant metadata & timezone |
| `cameras` | `camera_id` (String) | `restaurant_id` | Vision camera sources and connection status |
| `users` | `user_id` (UUID) | `restaurant_id` | Staff profiles (Admin, Manager, Waiter, Analyst) |
| `tables` | `table_id` (String) | `restaurant_id`, `camera_id` | Physical dining table boundaries and state |
| `table_sessions` | `session_id` (String) | `table_id`, `restaurant_id` | Active and historical dining sessions |
| `service_events` | `event_id` (UUID) | `session_id`, `table_id`, `created_by` | Immutable operational service and vision events |
| `waiter_assignments`| `assignment_id` (UUID) | `user_id`, `table_id` | Staff table and section allocations |
| `alerts` | `alert_id` (UUID) | `session_id`, `table_id` | Operational delay and violation alerts |
| `audit_logs` | `audit_id` (UUID) | `user_id` | Append-only audit trail for edits and overrides |

---

## 2. Data Integrity & Idempotency Rules

- **UTC Timestamps:** All operational timestamps (`event_timestamp`, `started_at`, `ended_at`, `created_at`, `timestamp`) are stored in timezone-aware UTC.
- **Idempotency:** `service_events` enforces a unique constraint on `idempotency_key`. Retried event submissions return the existing record without duplicating business logic side effects.
- **Audit Preservation:** Event corrections mark the original event with `verification_status="CORRECTED"`, link a new superseding event (`supersedes_event_id`), and write an immutable record into `audit_logs`.
- **Foreign Key Cascades:** Deleting a restaurant cascades to tables and cameras; deleting a table cascades to sessions; historical events remain linked or reference audit records.

---

## 3. SQLite Backup and Restore (Development & Edge)

### Automated CLI Tool

The management utility `scripts/db_manage.py` provides snapshot backup and restore:

```bash
# Backup current SQLite database to timestamped snapshot in backups/
python scripts/db_manage.py backup --dir backups

# Inspect record counts across all domain entities
python scripts/db_manage.py status

# Restore from a backup snapshot (automatically creates a safety pre-restore backup)
python scripts/db_manage.py restore --file backups/smartserve_YYYYMMDD_HHMMSS.db
```

### Manual Hot Backup via SQLite CLI

SQLite WAL mode allows hot backups without stopping the application server:

```bash
sqlite3 smartserve.db ".backup 'backups/smartserve_manual.db'"
```

---

## 4. PostgreSQL Backup and Restore (Production)

### Backup (Logical Dump)

```bash
# Logical compressed dump
pg_dump -h <HOST> -U <USER> -F c -b -v -f "smartserve_backup_$(date +%Y%m%d_%H%M%S).dump" <DB_NAME>
```

### Restore

```bash
# Restore into empty or clean database
pg_restore -h <HOST> -U <USER> -d <DB_NAME> -v "smartserve_backup_YYYYMMDD_HHMMSS.dump"
```

---

## 5. Migration Execution

To apply database schema upgrades:

```bash
# Upgrade schema to latest revision
alembic upgrade head

# Check current revision status
alembic current
```
