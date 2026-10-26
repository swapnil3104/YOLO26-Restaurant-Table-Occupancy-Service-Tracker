"""API routes for operational analytics, KPI summaries, breakdowns, and CSV reports."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.analytics.schema import (
    AnalyticsBreakdownResponse,
    AnalyticsSummaryResponse,
    CentralRestaurantKPIs,
    FloorAnalyticsResponse,
    FloorKPIItem,
)
from smartserve.analytics.service import AnalyticsService
from smartserve.database.models import User
from smartserve.database.session import get_db
from smartserve.events.schema import UserRole
from smartserve.security.auth import require_manager_or_admin, require_staff_actor

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Compute aggregate restaurant service KPIs",
)
async def get_analytics_summary(
    table_id: str | None = Query(None, description="Optional table filter"),
    section: str | None = Query(None, description="Optional dining room section filter"),
    waiter_id: str | None = Query(None, description="Optional waiter filter"),
    start_time: datetime | None = Query(None, description="Start date filter (UTC)"),
    end_time: datetime | None = Query(None, description="End date filter (UTC)"),
    include_estimates: bool = Query(
        False, description="Include unverified candidate AI observations"
    ),
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """Retrieve summarized operational KPIs, response times, turnover, and alert stats.

    Role-aware: Waiters can view general aggregate metrics or filter by their own user ID.
    Attempting to view another specific waiter's performance requires Manager or Admin.
    """
    if (
        current_user.role == UserRole.WAITER.value
        and waiter_id
        and waiter_id != current_user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Waiters may only query their own individual service metrics",
        )

    return await AnalyticsService.get_summary(
        db,
        table_id=table_id,
        section=section,
        waiter_id=waiter_id,
        start_time=start_time,
        end_time=end_time,
        include_estimates=include_estimates,
    )


@router.get(
    "/floors",
    response_model=FloorAnalyticsResponse,
    summary="Compute Central Restaurant KPIs and Floor-Level KPIs",
)
async def get_floor_analytics(
    floor: str | None = Query(
        None, description="Optional floor filter (e.g., 'Floor 1', 'Floor 2', or 'ALL')"
    ),
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> FloorAnalyticsResponse:
    """Retrieve Central Restaurant KPIs and Floor-Level KPIs.

    Adheres strictly to Docs/TASKS.md Phase 6:
    - Split analytics into Central Restaurant KPIs and Floor-Level KPIs.
    - Aggregates central KPIs strictly from numerators/denominators (does NOT sum percentages).
    - Enforces canonical table deduplication (prevents double counting from overlapping camera coverage).
    - Distinguishes 0 from unknown / offline / unavailable (null metrics + clear coverage status).
    - Preserves historical shift stats independently of live camera removal.
    """
    return await AnalyticsService.get_floor_analytics(
        db,
        floor_filter=floor,
    )


@router.get(
    "/central",
    response_model=CentralRestaurantKPIs,
    summary="Compute Central Restaurant KPIs across all monitored floors",
)
async def get_central_analytics(
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> CentralRestaurantKPIs:
    """Retrieve Central Restaurant KPIs across all monitored floors."""
    resp = await AnalyticsService.get_floor_analytics(db, floor_filter="ALL")
    return resp.central


@router.get(
    "/floors/{floor_id}",
    response_model=FloorKPIItem,
    summary="Compute Floor-Level KPIs for a specific floor",
)
async def get_single_floor_analytics(
    floor_id: str,
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> FloorKPIItem:
    """Retrieve Floor-Level KPIs for a specific floor by ID or name."""
    resp = await AnalyticsService.get_floor_analytics(db, floor_filter=floor_id)
    for fl in resp.floors:
        if fl.floor_name.lower() == floor_id.lower() or floor_id.lower() in fl.floor_name.lower():
            return fl
    if resp.floors:
        return resp.floors[0]
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Floor '{floor_id}' not found in monitored floors.",
    )


@router.get(
    "/breakdown",
    response_model=AnalyticsBreakdownResponse,
    summary="Retrieve multi-dimensional performance breakdowns",
)
async def get_analytics_breakdown(
    table_id: str | None = Query(None, description="Optional table filter"),
    section: str | None = Query(None, description="Optional dining room section filter"),
    waiter_id: str | None = Query(None, description="Optional waiter filter"),
    start_time: datetime | None = Query(None, description="Start date filter (UTC)"),
    end_time: datetime | None = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsBreakdownResponse:
    """Retrieve table, staff, and hourly dining distribution reports.

    In accordance with PRD Section 13, employee-level performance data is masked
    for non-managerial staff. Managers and Administrators receive unmasked metrics.
    """
    is_manager_or_admin = current_user.role in (UserRole.MANAGER.value, UserRole.ADMIN.value)
    anonymize_staff = not is_manager_or_admin

    breakdown = await AnalyticsService.get_breakdowns(
        db,
        table_id=table_id,
        section=section,
        waiter_id=waiter_id,
        start_time=start_time,
        end_time=end_time,
        anonymize_staff=anonymize_staff,
    )

    # If waiter is inspecting, show only their own performance row unmasked if matched
    if not is_manager_or_admin:
        filtered_waiters = []
        for w in breakdown.waiters:
            # If matches own user ID hash, or allow self-inspection
            if w.waiter_id == current_user.user_id:
                w.staff_name = current_user.display_name
                filtered_waiters.append(w)
            elif not waiter_id:
                filtered_waiters.append(w)
        breakdown.waiters = filtered_waiters

    return breakdown


@router.get(
    "/export",
    summary="Export session history or reports to CSV with privacy protection",
    response_class=Response,
)
async def export_sessions_csv(
    report_type: str = Query("sessions", description="Report type: sessions, summary, or waiters"),
    table_id: str | None = Query(None, description="Optional table filter"),
    section: str | None = Query(None, description="Optional dining room section filter"),
    waiter_id: str | None = Query(None, description="Optional waiter filter"),
    start_time: datetime | None = Query(None, description="Start date filter (UTC)"),
    end_time: datetime | None = Query(None, description="End date filter (UTC)"),
    anonymize: bool = Query(True, description="Mask employee identifiers for privacy"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export operational reports as downloadable RFC 4180 CSV file.

    Restricted to Manager and Administrator roles. Anonymizes employee identifiers
    by default to maintain compliance with restaurant privacy standards (PRD Section 13).
    Supports 'sessions', 'summary', and 'waiters' report formats.
    """
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    if report_type == "summary":
        csv_content = await AnalyticsService.export_summary_csv(
            db,
            table_id=table_id,
            section=section,
            waiter_id=waiter_id,
            start_time=start_time,
            end_time=end_time,
        )
        filename = f"smartserve_kpi_summary_{timestamp_str}.csv"
    elif report_type == "waiters":
        csv_content = await AnalyticsService.export_waiters_csv(
            db,
            table_id=table_id,
            section=section,
            waiter_id=waiter_id,
            start_time=start_time,
            end_time=end_time,
            anonymize=anonymize,
        )
        filename = f"smartserve_waiters_{timestamp_str}.csv"
    else:
        # Default: sessions report
        csv_content = await AnalyticsService.export_sessions_csv(
            db,
            table_id=table_id,
            section=section,
            waiter_id=waiter_id,
            start_time=start_time,
            end_time=end_time,
            anonymize=anonymize,
        )
        filename = f"smartserve_sessions_{timestamp_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
