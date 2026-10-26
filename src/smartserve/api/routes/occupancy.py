from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.api.dependencies import get_occupancy_manager
from smartserve.database.models import User
from smartserve.database.session import get_db
from smartserve.occupancy.manager import OccupancySessionManager
from smartserve.occupancy.schema import (
    CustomerCountUpdateRequest,
    ManagerOverrideRequest,
    StateTransitionEvent,
    TableOccupancyStatus,
    TableSession,
)
from smartserve.security.auth import resolve_actor
from smartserve.tables.schema import TableAssociationResult

router = APIRouter(prefix="/occupancy", tags=["occupancy"])


class CleanedTableRequest(BaseModel):
    """Payload for staff marking table sanitized."""

    actor: str = Field(..., min_length=2, description="Staff username or ID")
    reason: str = Field(default="Table sanitized and reset", description="Audit note")


@router.get("", response_model=dict[str, TableOccupancyStatus])
async def get_all_occupancy(
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> dict[str, TableOccupancyStatus]:
    """Retrieve current occupancy states, timers, and active sessions for all monitored tables."""
    return manager.get_all_statuses()


@router.get("/sessions", response_model=list[TableSession])
async def list_sessions(
    table_id: str | None = Query(None, description="Optional table ID filter"),
    include_active: bool = Query(True, description="Whether to include active in-flight sessions"),
    start_time: datetime | None = Query(
        None, description="Filter sessions started after UTC timestamp"
    ),
    end_time: datetime | None = Query(
        None, description="Filter sessions started before UTC timestamp"
    ),
    limit: int = Query(50, ge=1, le=200, description="Max session records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> list[TableSession]:
    """List restaurant customer sessions ordered by start time descending with date and pagination filters."""
    return manager.get_session_history(
        table_id=table_id,
        include_active=include_active,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/audit", response_model=list[StateTransitionEvent])
async def get_audit_trail(
    table_id: str | None = Query(None, description="Optional table ID filter"),
    start_time: datetime | None = Query(None, description="Filter transitions after UTC timestamp"),
    end_time: datetime | None = Query(None, description="Filter transitions before UTC timestamp"),
    limit: int = Query(100, ge=1, le=500, description="Max audit entries to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> list[StateTransitionEvent]:
    """Retrieve auditable history of table state transitions with date and pagination filters."""
    return manager.get_audit_log(
        table_id=table_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/{table_id}", response_model=TableOccupancyStatus)
async def get_table_occupancy(
    table_id: str,
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> TableOccupancyStatus:
    """Retrieve occupancy details, active session, and timers for a specific table."""
    status_obj = manager.get_table_status(table_id)
    if not status_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found in occupancy tracker.",
        )
    return status_obj


@router.post("/{table_id}/override", response_model=StateTransitionEvent)
async def manager_override(
    table_id: str,
    request: ManagerOverrideRequest,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
    db: AsyncSession = Depends(get_db),
) -> StateTransitionEvent:
    """Manager manual override of table state.

    Enforces Manager or Administrator role check when user identification is provided.
    Creates auditable transition event with actor and justification.
    """
    if x_user_id:
        actor = await resolve_actor(db, x_user_id)
        if str(actor.role).upper() not in ("MANAGER", "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{actor.username}' with role '{actor.role}' is not authorized to override table state. Manager or Admin required.",
            )
        request.actor = actor.username
    elif request.actor:
        stmt = select(User).where(
            (User.user_id == request.actor) | (User.username == request.actor)
        )
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if user and str(user.role).upper() not in ("MANAGER", "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{user.username}' with role '{user.role}' is not authorized to override table state. Manager or Admin required.",
            )

    return manager.override_table_state(table_id, request)


@router.post("/{table_id}/count")
async def update_customer_count(
    table_id: str,
    request: CustomerCountUpdateRequest,
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> dict[str, str | int | bool]:
    """Staff/manager manual correction of estimated guest count."""
    success = manager.update_customer_count(table_id, request)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found.",
        )
    return {
        "success": True,
        "table_id": table_id,
        "customer_count": request.customer_count,
        "actor": request.actor,
    }


@router.post("/{table_id}/cleaned", response_model=StateTransitionEvent)
@router.post("/{table_id}/clean", response_model=StateTransitionEvent)
async def mark_table_cleaned(
    table_id: str,
    request: CleanedTableRequest,
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> StateTransitionEvent:
    """Staff marks table as sanitized and reset, transitioning from CLEANING_REQUIRED to AVAILABLE."""
    event = manager.mark_table_cleaned(table_id, actor=request.actor, reason=request.reason)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found.",
        )
    return event


@router.post("/process-frame", response_model=list[StateTransitionEvent])
async def process_frame(
    association_result: TableAssociationResult,
    manager: OccupancySessionManager = Depends(get_occupancy_manager),
) -> list[StateTransitionEvent]:
    """Feed spatial association frame output into occupancy state machines.

    Returns any state transition events triggered during this frame.
    """
    return manager.process_frame_result(association_result)
