# Phase 10: Analytics and Reports Summary

## Phase Goal
Implement comprehensive operational analytics, service timing KPI calculations, section/table breakdown reports, authorized waiter performance metrics, privacy-compliant CSV exports, and a modern interactive Analytics & Reports dashboard view in accordance with `Docs/PRD.md` (FR-06, Section 10.3, 10.4, 12, 13), `Docs/RULES.md` (Section 8, 14), and `Docs/TASKS.md` Phase 10.

## Key Deliverables Completed

### 1. Analytics Domain Schemas (`src/smartserve/analytics/schema.py`)
- **`SampleSizeMetrics`**: Structured sample size reporting (`total_sessions`, `attended_sessions`, `food_delivered_sessions`, `completed_sessions`, `invalid_or_review_sessions`) in strict adherence to `RULES.md` Section 14.
- **`KPIMetrics`**: Extended operational metrics including:
  - Separate `median_first_attendance_sec` and `average_first_attendance_sec`.
  - Separate `median_food_delivery_sec` and `average_food_delivery_sec`.
  - Separate `median_occupancy_duration_sec` and `average_occupancy_duration_sec`.
  - `table_turnover_rate` (completed sessions / monitored tables).
  - `table_utilization_percent` (occupied table-minutes / available table-minutes * 100).
  - `delay_rate_percent` (sessions breaching warning thresholds / total sessions * 100).
  - `data_completeness_percent` (completed sessions with both attendance & food confirmed / completed sessions * 100).
  - `sample_sizes` breakdown and data exclusions disclosure.
- **`TablePerformanceItem`**: Per-table analytics (`table_id`, `table_code`, `section`, `capacity`, `sessions_count`, `completed_sessions_count`, `median_occupancy_sec`, `average_occupancy_sec`, `turnover_rate`, `utilization_percent`, `delays_count`).
- **`WaiterPerformanceItem`**: Per-waiter analytics (`waiter_id`, `staff_name`, `tables_handled`, `median_response_sec`, `average_response_sec`, `on_time_attendance_rate`, `delays_count`, `sample_size`).
- **`HourlyDistributionItem`**: 24-hour distribution of guest seating and dining load (`hour_of_day`, `session_count`, `average_occupancy_rate`).
- **`AnalyticsBreakdownResponse`**: Comprehensive multi-dimensional report container.

### 2. Analytics Domain Service (`src/smartserve/analytics/service.py`)
- Implemented robust mathematical calculation of all service metrics:
  - Exact interval calculation with timezone-aware UTC timestamps.
  - Transparent exclusion of missing, incomplete, and negative/invalid intervals from standard averages without fabricated fallback numbers (`RULES.md` Section 14).
  - Strict deduplication of invalid/review sessions in sample size tracking.
  - Multi-dimensional query filtering: `table_id`, `section`, `waiter_id`, `start_time`, `end_time`, `include_estimates`.
- Implemented `get_breakdowns`:
  - Per-table performance matrix with duration distributions and utilization.
  - Per-waiter efficiency metrics with RBAC-aware staff identity protection.
  - 24-hour dining load histogram for peak hour detection.
- Implemented multi-format RFC 4180 CSV exports:
  - `export_sessions_csv`: Detailed sessions history with section, delay indicators, completeness flags, and privacy-masked waiter IDs (`STAFF-****`).
  - `export_summary_csv`: Executive summary matching dashboard metrics identically for the same filters.
  - `export_waiters_csv`: Waiter efficiency metrics with on-time rates and sample sizes.

### 3. Analytics REST API Endpoints (`src/smartserve/api/routes/analytics.py`)
- `GET /api/v1/analytics/summary`:
  - Enforces `require_staff_actor` (Waiter, Manager, Admin).
  - Prevents Waiters from querying other individual staff members (returns HTTP 403 Forbidden).
  - Supports query filters: `table_id`, `section`, `waiter_id`, `start_time`, `end_time`, `include_estimates`.
- `GET /api/v1/analytics/breakdown`:
  - Returns table performance, staff efficiency, and hourly load distributions.
  - Automatically anonymizes staff identifiers for non-managerial callers (`STAFF-****`), while returning unmasked metrics for Manager and Admin.
- `GET /api/v1/analytics/export`:
  - Restricted to Manager and Administrator (`require_manager_or_admin`).
  - Supports `report_type` (`sessions`, `summary`, `waiters`) with `anonymize=true|false` option.

### 4. Interactive Frontend View (`frontend/src/pages/AnalyticsReportsPage.tsx`)
- Integrated dedicated **Analytics & Reports** navigation into `Sidebar.tsx` and `App.tsx` (`/analytics`).
- Modern dark console UI adhering to `Docs/DESIGN.md` Section 9:
  - **Filter Controls**: Time presets (Today, 24h, 7d, 30d, All Time), Section selector, Table selector, Staff selector (Manager/Admin only), and Confirmed-Only (Official) toggle.
  - **Audit & Data Quality Ribbon**: Real-time sample size disclosures (`Total: N`, `Attended: N`, `Food Delivered: N`, `Completed: N`, `Excluded/Review: N`) and data completeness tracking.
  - **Top KPI Cards**:
    - First Response Time (Mean & Median with threshold status indicator).
    - Food Delivery Time (Mean & Median with target comparison).
    - Table Utilization & Turnover Rate (occupancy capacity % and turns/table).
    - Service Delay Rate (% with active/warning alert counts).
    - Data Completeness & Milestone Reliability.
  - **Tabbed Operational Breakdown**:
    - *Table & Section Performance Matrix*: Capacity, sessions count, completed count, median & average occupancy, turnover, utilization bar, and delays count.
    - *Staff & Waiter Performance Table*: Staff ID, staff name, tables handled, median response time, average response time, on-time attendance rate %, delays count, and sample size with role-based masking.
    - *Hourly Dining Traffic & Peak Rush Chart*: 24-hour visual bar chart highlighting peak dining hours.
  - **Authorized CSV Export Modal**: Direct download links for Detailed Sessions CSV, Executive Summary CSV, and Staff Performance CSV with privacy toggle.

### 5. Automated Verification & Consistency Testing
- Created `tests/test_analytics_and_reports.py` with 5 comprehensive test suites:
  - `test_kpi_calculation_rules_and_metrics`: Verifies mean vs. median math, turnover, utilization, delay rate, data completeness, and RULES.md Section 14 exclusions.
  - `test_multi_dimensional_filters`: Verifies section, table_id, and waiter_id query filtering.
  - `test_breakdown_reports_tables_waiters_hourly`: Verifies table matrix, waiter metrics, and 24h distribution.
  - `test_rbac_and_staff_privacy_controls`: Verifies HTTP 401 unauthenticated, HTTP 403 on waiter-to-waiter inspection, staff masking, and export gate.
  - `test_csv_export_formats_and_dashboard_consistency`: Guarantees exact value matching between dashboard JSON summary and CSV export.
- Test Suite Results:
  - **95 passed, 0 failed** across all backend tests in 5.27s.
  - Frontend TypeScript & Vite compilation verified (`npm run build` succeeds in 2.29s with 0 errors).
