"""Pydantic schemas for analytics, KPI summaries, and operational reports.

Adheres to Docs/PRD.md Section 10.3, 10.4, 12, 13, and Docs/RULES.md Section 8, 14.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SampleSizeMetrics(BaseModel):
    """Sample sizes and data inclusion metrics adhering to RULES.md Section 14."""

    total_sessions: int = Field(default=0, description="Total sessions matching criteria")
    attended_sessions: int = Field(default=0, description="Sessions with verified first attendance")
    food_delivered_sessions: int = Field(
        default=0, description="Sessions with verified food delivery"
    )
    completed_sessions: int = Field(default=0, description="Sessions concluded and vacated")
    invalid_or_review_sessions: int = Field(
        default=0,
        description="Sessions flagged for review or excluded due to negative/invalid intervals",
    )


class KPIMetrics(BaseModel):
    """Core restaurant operational KPIs."""

    median_first_attendance_sec: float | None = Field(
        default=None, description="Median time in seconds from seating to waiter attendance"
    )
    average_first_attendance_sec: float | None = Field(
        default=None, description="Average time in seconds from seating to waiter attendance"
    )
    median_food_delivery_sec: float | None = Field(
        default=None, description="Median time in seconds from seating to first food delivery"
    )
    average_food_delivery_sec: float | None = Field(
        default=None, description="Average time in seconds from seating to first food delivery"
    )
    median_occupancy_duration_sec: float | None = Field(
        default=None, description="Median session duration in seconds"
    )
    average_occupancy_duration_sec: float | None = Field(
        default=None, description="Average session duration in seconds"
    )
    table_turnover_rate: float = Field(
        default=0.0, description="Average completed sessions per monitored table"
    )
    table_utilization_percent: float = Field(
        default=0.0,
        description="Table occupancy utilization percentage (occupied minutes / available minutes)",
    )
    delay_rate_percent: float = Field(
        default=0.0,
        description="Percentage of eligible sessions with service delays exceeding thresholds",
    )
    data_completeness_percent: float = Field(
        default=0.0,
        description="Percentage of completed sessions with verified attendance and food delivery milestones",
    )
    sample_sizes: SampleSizeMetrics = Field(
        default_factory=SampleSizeMetrics,
        description="Detailed sample size breakdowns and exclusions",
    )


class AlertSummary(BaseModel):
    """Aggregate alert statistics."""

    total_alerts: int = 0
    active_alerts: int = 0
    resolved_alerts: int = 0
    critical_alerts: int = 0
    warning_alerts: int = 0
    auto_resolved_alerts: int = 0


class AnalyticsSummaryResponse(BaseModel):
    """Aggregated operational analytics response."""

    total_sessions: int = Field(default=0, description="Total sessions matching criteria")
    completed_sessions: int = Field(default=0, description="Sessions concluded and vacated")
    active_sessions: int = Field(default=0, description="In-flight active table sessions")
    kpis: KPIMetrics = Field(default_factory=KPIMetrics, description="Computed service timing KPIs")
    alerts: AlertSummary = Field(default_factory=AlertSummary, description="Alert distributions")
    filter_start: datetime | None = Field(default=None, description="Query start timestamp")
    filter_end: datetime | None = Field(default=None, description="Query end timestamp")
    section: str | None = Field(default=None, description="Dining room section filter")
    table_id: str | None = Field(default=None, description="Table filter")


class TablePerformanceItem(BaseModel):
    """Performance metrics for an individual dining table."""

    table_id: str = Field(description="Unique table identifier")
    table_code: str = Field(description="Short human-readable table code (e.g., T-01)")
    section: str = Field(default="Main Dining", description="Dining section or area")
    capacity: int = Field(default=4, description="Configured seat capacity")
    sessions_count: int = Field(default=0, description="Total sessions hosted during period")
    completed_sessions_count: int = Field(default=0, description="Completed sessions")
    median_occupancy_sec: float | None = Field(
        default=None, description="Median session occupancy in seconds"
    )
    average_occupancy_sec: float | None = Field(
        default=None, description="Average session occupancy in seconds"
    )
    turnover_rate: float = Field(default=0.0, description="Completed sessions per period")
    utilization_percent: float = Field(
        default=0.0, description="Table occupancy utilization percentage"
    )
    delays_count: int = Field(
        default=0, description="Count of service threshold breaches on this table"
    )


class WaiterPerformanceItem(BaseModel):
    """Performance analytics for service staff adhering to PRD Section 10.3 & 13."""

    waiter_id: str = Field(description="Staff user identifier (or masked STAFF-****)")
    staff_name: str = Field(description="Staff display name (or Anonymized Staff)")
    tables_handled: int = Field(default=0, description="Distinct sessions/tables attended")
    median_response_sec: float | None = Field(
        default=None, description="Median first response time in seconds"
    )
    average_response_sec: float | None = Field(
        default=None, description="Average first response time in seconds"
    )
    on_time_attendance_rate: float = Field(
        default=100.0, description="Percentage of tables attended within warning threshold"
    )
    delays_count: int = Field(
        default=0, description="Number of attendance delays exceeding warning threshold"
    )
    sample_size: int = Field(default=0, description="Count of evaluated interactions")


class HourlyDistributionItem(BaseModel):
    """Temporal occupancy load across operating hours (PRD Section 10.4)."""

    hour_of_day: int = Field(ge=0, le=23, description="Hour of the day in 24h format (0-23)")
    session_count: int = Field(default=0, description="Number of sessions started in this hour")
    average_occupancy_rate: float = Field(
        default=0.0, description="Average tables occupied during this hour"
    )


class AnalyticsBreakdownResponse(BaseModel):
    """Multi-dimensional analytics reports containing table, staff, and hourly breakdowns."""

    tables: list[TablePerformanceItem] = Field(
        default_factory=list, description="Per-table performance metrics"
    )
    waiters: list[WaiterPerformanceItem] = Field(
        default_factory=list, description="Waiter service analytics"
    )
    hourly: list[HourlyDistributionItem] = Field(
        default_factory=list, description="Hourly dining traffic load"
    )
    filter_start: datetime | None = Field(default=None, description="Query start timestamp")
    filter_end: datetime | None = Field(default=None, description="Query end timestamp")
    section: str | None = Field(default=None, description="Filter section if applied")
    table_id: str | None = Field(default=None, description="Filter table if applied")


class FloorKPIItem(BaseModel):
    """Floor-level operational KPI metrics."""

    floor_name: str = Field(description="Name or identifier of the floor (e.g., Floor 1)")
    monitored_sources_count: int = Field(
        default=0, description="Active cameras assigned to this floor"
    )
    source_ids: list[str] = Field(
        default_factory=list, description="List of camera identifiers on this floor"
    )
    coverage_status: str = Field(
        default="FULL_COVERAGE", description="FULL_COVERAGE, PARTIAL_COVERAGE, OFFLINE, UNKNOWN"
    )
    total_tables: int = Field(
        default=0, description="Canonical table count on this floor (deduplicated)"
    )
    occupied_tables: int = Field(default=0, description="Number of currently occupied tables")
    vacant_tables: int = Field(default=0, description="Number of currently vacant tables")
    occupancy_rate_percent: float | None = Field(
        default=None, description="Occupancy rate percentage (null if coverage is offline)"
    )
    detected_diners: int | None = Field(
        default=None, description="Count of patrons detected by YOLO26 and ByteTrack on this floor"
    )
    active_alerts_count: int = Field(
        default=0, description="Count of active service alerts on this floor"
    )
    critical_alerts_count: int = Field(default=0, description="Count of critical alerts")
    warning_alerts_count: int = Field(default=0, description="Count of warning alerts")
    avg_response_time_sec: float | None = Field(
        default=None, description="Average first attendance response time on this floor"
    )
    avg_food_delivery_sec: float | None = Field(
        default=None, description="Average food delivery time on this floor"
    )
    last_freshness_sec: int | None = Field(
        default=None, description="Elapsed seconds since latest video frame or event"
    )
    is_live: bool = Field(
        default=True, description="True if floor has at least one active live camera"
    )


class CentralRestaurantKPIs(BaseModel):
    """Central restaurant-wide aggregate KPIs across all monitored floors."""

    reporting_scope: str = Field(
        default="LIVE_ACTIVE_SOURCES", description="LIVE_ACTIVE_SOURCES, HISTORICAL_SHIFT, COMBINED"
    )
    total_monitored_floors: int = Field(
        default=0, description="Count of floors with active tracking"
    )
    total_active_sources: int = Field(default=0, description="Total active video/camera sources")
    total_canonical_tables: int = Field(
        default=0, description="Total deduplicated monitored tables across all floors"
    )
    total_occupied_tables: int = Field(default=0, description="Total occupied tables")
    total_vacant_tables: int = Field(default=0, description="Total vacant tables")
    central_occupancy_rate_percent: float | None = Field(
        default=None, description="Rate computed from sum(occupied) / sum(tables) * 100"
    )
    total_detected_diners: int | None = Field(
        default=None,
        description="Deduplicated count of detected patrons across all monitored floors",
    )
    total_active_alerts: int = Field(default=0, description="Total active alerts across all floors")
    critical_alerts_count: int = Field(default=0, description="Total critical alerts")
    warning_alerts_count: int = Field(default=0, description="Total warning alerts")
    weighted_avg_response_time_sec: float | None = Field(
        default=None, description="Session-weighted average first response time"
    )
    weighted_avg_food_delivery_sec: float | None = Field(
        default=None, description="Session-weighted average food delivery time"
    )
    coverage_health: str = Field(
        default="ALL_HEALTHY", description="ALL_HEALTHY, PARTIAL_COVERAGE, DEGRADED, NO_SOURCES"
    )
    coverage_warning: str | None = Field(
        default=None, description="Actionable warning message if coverage is degraded"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="UTC calculation timestamp"
    )


class ShiftHistoricalSummary(BaseModel):
    """Historical shift metrics retained independently of live camera connection state."""

    total_sessions_today: int = Field(
        default=0, description="All dining sessions recorded during this shift"
    )
    completed_sessions: int = Field(default=0, description="Completed dining sessions")
    turnover_rate: float = Field(
        default=0.0, description="Overall table turnover rate (sessions / table)"
    )
    historical_avg_response_sec: float | None = Field(
        default=None, description="Historical average response time"
    )
    historical_avg_delivery_sec: float | None = Field(
        default=None, description="Historical average delivery time"
    )


class FloorAnalyticsResponse(BaseModel):
    """Complete floor and central restaurant KPI payload."""

    central: CentralRestaurantKPIs
    floors: list[FloorKPIItem] = Field(default_factory=list)
    shift_history: ShiftHistoricalSummary
