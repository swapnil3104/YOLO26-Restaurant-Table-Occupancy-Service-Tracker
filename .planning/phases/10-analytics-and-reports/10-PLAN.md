# Phase 10: Analytics and Reports Plan

## Phase Goal
Implement comprehensive operational analytics, service timing KPI calculations, section/table breakdown reports, authorized waiter performance metrics, privacy-compliant CSV exports, and a modern interactive Analytics & Reports dashboard view in accordance with `Docs/PRD.md` (FR-06, Section 10.3, 10.4, 12, 13), `Docs/RULES.md` (Section 8, 14), and `Docs/TASKS.md` Phase 10.

## Requirements Covered
- **KPI Calculation Rules & Metric Definitions (`Docs/RULES.md` Section 8.2, 14 & PRD Section 12)**:
  - Separate reporting of mean and median for First Response Time ($T_{response} = T_{attendance} - T_{seating}$), Time to First Food Delivery ($T_{food} = T_{first\ delivery} - T_{seating}$), and Occupancy Duration ($T_{occupancy} = T_{end} - T_{seating}$).
  - Table Turnover Rate: completed sessions per monitored table over the evaluated period.
  - Table Utilization: $\frac{\sum T_{occupancy}}{\text{Operating Window Minutes} \times N_{tables}} \times 100$.
  - Service Delay Rate: $\frac{\text{Eligible Sessions with Response or Delivery Exceeding Threshold}}{\text{Eligible Sessions}} \times 100$.
  - Data Completeness: $\frac{\text{Sessions With Required Confirmed Events}}{\text{Eligible Sessions}} \times 100$.
  - Sample size disclosure ($N_{total}$, $N_{attended}$, $N_{food}$, $N_{completed}$, $N_{invalid}$) and transparent exclusion of invalid/missing intervals without fabricated fallback numbers.
  - Confirmed-only events for official operational metrics by default (`include_estimates=false`).
- **Breakdown Reports & Filters (`Docs/PRD.md` Section 10.3, 10.4 & TASKS.md Phase 10)**:
  - Section & Table breakdown: sessions served, average occupancy duration, turnover, utilization, and delay counts.
  - Waiter Performance breakdown: tables handled, median response time, average response time, on-time attendance rate, delays count, and sample size.
  - Peak hours occupancy distribution.
  - Multi-dimensional filters: `table_id`, `section`, `waiter_id`, `start_time`, `end_time`, and `include_estimates`.
- **Role-Based Access Control & Staff Privacy (`Docs/PRD.md` Section 13 & TASKS.md Phase 10)**:
  - Employee-level performance data is restricted to `MANAGER` and `ADMIN` roles. Waiters can only view aggregate or their own performance.
  - Anonymization option masking employee identifiers (`STAFF-****`) by default on exports and unprivileged views.
- **Authorized CSV Exports (`Docs/TASKS.md` Phase 10)**:
  - Export sessions history CSV with full timestamps, metrics, delay flags, and completeness flags.
  - Export summary KPI report CSV.
  - Export waiter performance CSV (strictly Manager/Admin or anonymized).
  - Guarantee that dashboard and exported report metrics match identically for the same filters.
- **Frontend Analytics & Reports View (`Docs/DESIGN.md` Section 3, 9 & PRD Section 10.3, 10.4)**:
  - Dedicated "Analytics & Reports" navigation link and page (`/analytics`) in the application shell.
  - KPI cards with mean/median toggles, unit formatting, and threshold badges.
  - Interactive filter bar (time preset, section, table, waiter).
  - Sample size and data completeness banner.
  - Performance tables with sorting and responsive cards.
  - CSV download triggers with anonymization toggle.
- **Automated Verification**:
  - Comprehensive unit and integration tests against known fixtures (`tests/test_analytics_and_reports.py`).
  - Frontend TypeScript build verification (`npm run build`).

## Task Breakdown

1. **Analytics Schema Expansion (`src/smartserve/analytics/schema.py`)**:
   - Add `SampleSizeMetrics` model: `total_sessions`, `attended_sessions`, `food_delivered_sessions`, `completed_sessions`, `invalid_or_review_sessions`.
   - Update `KPIMetrics` model: include `median_occupancy_duration_sec`, `table_utilization_percent`, `delay_rate_percent`, `data_completeness_percent`, and `sample_sizes`.
   - Add `TablePerformanceItem` model: per-table analytics (`table_id`, `table_code`, `section`, `capacity`, `sessions_count`, `average_occupancy_sec`, `turnover_rate`, `utilization_percent`, `delays_count`).
   - Add `WaiterPerformanceItem` model: per-waiter analytics (`waiter_id`, `waiter_name`, `tables_handled`, `median_response_sec`, `average_response_sec`, `on_time_attendance_rate`, `delays_count`, `sample_size`).
   - Add `HourlyDistributionItem` model: hour-of-day session load.
   - Add `AnalyticsBreakdownResponse` model: container for comprehensive reports.

2. **Analytics Domain Service Enhancement (`src/smartserve/analytics/service.py`)**:
   - Implement enhanced `get_summary` with exact metric math, sample sizes, delay rate, data completeness, table utilization, and section/waiter filtering.
   - Implement `get_breakdowns`: computes table breakdown, waiter breakdown (with RBAC enforcement and masking), and hourly distribution.
   - Implement enhanced CSV exports:
     - `export_sessions_csv`: with section, delay indicators, and completeness flags.
     - `export_summary_csv`: high-level KPI and performance report.
     - `export_waiters_csv`: waiter metrics with privacy masking.

3. **Analytics API Routes Upgrade (`src/smartserve/api/routes/analytics.py`)**:
   - Update `GET /api/v1/analytics/summary` to support `section`, `waiter_id`, and `include_estimates` query parameters.
   - Add `GET /api/v1/analytics/breakdown`: returns comprehensive table, waiter, and hourly breakdown models (restricted/masked by role).
   - Update `GET /api/v1/analytics/export`: support `report_type` (`sessions`, `summary`, `waiters`) with filter parameters and role authorization.

4. **Frontend API & Types Updates (`frontend/src/types/index.ts` & `frontend/src/services/api.ts`)**:
   - Define TypeScript interfaces matching backend models (`AnalyticsSummary`, `TablePerformanceItem`, `WaiterPerformanceItem`, `HourlyDistributionItem`, `AnalyticsBreakdown`).
   - Add API client methods: `fetchAnalyticsSummary(filters)`, `fetchAnalyticsBreakdown(filters)`, `getExportReportUrl(type, filters)`.

5. **Frontend Analytics & Reports Page (`frontend/src/pages/AnalyticsReportsPage.tsx`)**:
   - Build a full-screen, responsive analytics dashboard with dark theme glassmorphism.
   - Top KPI cards with mean/median display and status indicators.
   - Filter bar for time range (Today, 24h, 7d, 30d, All), section, table, and waiter.
   - Data completeness and sample size audit ribbon.
   - Tabbed or split view: Table & Section Performance, Staff Performance, and Hourly Traffic.
   - CSV export modal / actions.
   - Wire into `Sidebar.tsx` and `App.tsx` under route `/analytics`.

6. **Test Suite & Verification**:
   - Create `tests/test_analytics_and_reports.py` testing calculations, mean vs. median, delay rate, data completeness, exclusions, filters, RBAC, and CSV export equivalence.
   - Run full test suite with `pytest`.
   - Run frontend build with `npm run build`.
   - Update `ROADMAP.md`, `STATE.md`, and `Docs/TASKS.md`.
