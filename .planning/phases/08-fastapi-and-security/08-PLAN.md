# Phase 8: FastAPI and Security Plan

## Phase Goal
Implement production-grade REST API architecture, OpenAPI documentation, authentication, role-based access control (RBAC), consistent error responses, secrets protection, pagination, date filtering, analytics endpoints with CSV export, rate limiting, and CORS configuration in accordance with `Docs/PRD.md` (FR-09, Section 12-14), `Docs/ARCHITECTURE.md` (Section 12), and `Docs/TASKS.md` Phase 8.

## Requirements Covered
- **Authentication & RBAC (PRD Section 12, 14 & TASKS.md Phase 8)**:
  - Token-based authentication and user verification (`POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/users`).
  - Server-side role enforcement across all endpoints (`WAITER`, `MANAGER`, `ADMIN`, `API_CLIENT`).
  - Role-specific gates:
    - Operational actions (attendance, delivery, cleaning, alerts) -> `WAITER`, `MANAGER`, `ADMIN`.
    - Managerial actions (layout changes, table overrides, event rejections, threshold updates) -> `MANAGER`, `ADMIN`.
    - Analytics exports & sensitive employee performance records -> `MANAGER`, `ADMIN`.
- **Consistent Error Format & Schema Validation (TASKS.md Phase 8)**:
  - Standardized error response format (`ErrorResponse` with code, message, details, and UTC timestamp).
  - Global FastAPI exception handlers for `HTTPException`, `RequestValidationError`, and unexpected exceptions.
- **Health & Dependency Monitoring without Secret Leakage (PRD Section 14 & TASKS.md Phase 8)**:
  - Detailed `/api/v1/health` endpoint returning component statuses (database connectivity check via `SELECT 1`, vision pipeline, table storage).
  - Strict sanitization: never expose passwords, connection strings, or secret keys in health checks or logs.
- **Analytics & Export Endpoints (PRD Section 11, 13 & TASKS.md Phase 8)**:
  - `GET /api/v1/analytics/summary`: Aggregated KPIs (median response time, median food delivery time, average occupancy, turnover rate, alert counts).
  - `GET /api/v1/analytics/export`: Streaming CSV export with date range filtering and privacy anonymization (masking staff identities in accordance with Section 13).
- **Pagination & Date Filtering (TASKS.md Phase 8)**:
  - Unified pagination parameters (`limit`, `offset`) and UTC timestamp filters (`start_time`, `end_time`) on events, sessions, alerts, and audit endpoints.
- **Rate Limiting & Network Hardening (TASKS.md Phase 8)**:
  - In-memory rate limiting middleware for sensitive and public routes.
  - Verified CORS policy configured for authorized frontend origins.
- **OpenAPI Documentation & Security Schemes (TASKS.md Phase 8)**:
  - OpenAPI 3.1 configuration with `HTTPBearer` and `ApiKeyAuth` security schemes, comprehensive operation summaries, tags, and request/response models.

## Task Breakdown

1. **Security & Auth Enhancements (`src/smartserve/security/`)**:
   - `src/smartserve/security/auth.py`: Token creation, verification, password hashing, and OpenAPI security dependencies (`HTTPBearer`, `APIKeyHeader`).
   - `src/smartserve/security/rate_limiter.py`: Lightweight token-bucket / sliding-window rate limiting dependency.
   - `src/smartserve/security/secrets.py`: Masking utilities for credentials, database URLs, and environment variables.

2. **Consistent Error Handling (`src/smartserve/api/errors.py`)**:
   - Standard `ErrorResponse` schema.
   - Global exception handlers for `HTTPException`, `RequestValidationError`, and unhandled server errors.

3. **Analytics & Export Domain Service and Router (`src/smartserve/analytics/` & `src/smartserve/api/routes/analytics.py`)**:
   - `src/smartserve/analytics/service.py`: Computes summary KPIs and generates CSV exports with privacy anonymization.
   - `src/smartserve/api/routes/analytics.py`: Exposes `/api/v1/analytics/summary` and `/api/v1/analytics/export` (restricted to MANAGER/ADMIN).

4. **Auth Endpoints Router (`src/smartserve/api/routes/auth.py`)**:
   - `POST /api/v1/auth/login` (or `/token`): Authenticates staff credentials, issues signed access token.
   - `GET /api/v1/auth/me`: Returns profile of authenticated user.
   - `GET /api/v1/auth/users`: Lists staff registry (restricted to MANAGER/ADMIN).

5. **Upgraded Health Endpoint (`src/smartserve/api/routes/health.py`)**:
   - Live database `SELECT 1` ping.
   - Structured `HealthStatusResponse` model reporting service components and version without leaking secrets.

6. **Securing Existing Routes & Adding Pagination / Date Filters**:
   - `tables.py`: Restrict mutating operations (create, update, delete, reset) to `MANAGER` / `ADMIN`.
   - `occupancy.py`: Restrict state overrides to `MANAGER` / `ADMIN`, add date/pagination filters to sessions and audit endpoints.
   - `events.py`: Add date/pagination filters (`start_time`, `end_time`) to events, alerts, and audit logs.
   - `rules.py`: Restrict threshold updates to `MANAGER` / `ADMIN`.

7. **FastAPI Application Setup & OpenAPI Documentation (`src/smartserve/main.py`)**:
   - Mount new routers (`auth_router`, `analytics_router`).
   - Register global exception handlers and rate limiting.
   - Configure OpenAPI tags and security schemes.

8. **Chronological Demo Script (`scripts/demo_security_and_api.py`)**:
   - Demonstrates authentication -> RBAC enforcement (waiter vs manager vs admin vs unauthorized) -> health check -> summary analytics -> privacy-compliant CSV export -> rate limiting.

9. **Comprehensive Verification Suite (`tests/test_fastapi_security.py`)**:
   - Tests for each role and anonymous access across all secured endpoints.
   - Tests for health check secrets sanitization and DB ping.
   - Tests for analytics KPIs and CSV export with anonymization.
   - Tests for pagination and date filtering.
   - Tests for rate limiting and standard error formats.

## Verification Criteria
- [ ] Documented response schemas for all API routes.
- [ ] Server-side role checks enforced: Unauthorized -> 401, Forbidden -> 403.
- [ ] Health endpoint returns status and dependency checks without leaking database credentials or secrets.
- [ ] Analytics summary computes accurate operational KPIs.
- [ ] Export endpoint produces valid CSV with privacy anonymization options and manager/admin gating.
- [ ] Pagination and date range filters work across events, sessions, alerts, and logs.
- [ ] 100% of existing and new automated tests pass cleanly.
