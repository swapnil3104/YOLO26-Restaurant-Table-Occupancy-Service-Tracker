"""REST API endpoints for POS and KDS operational event ingestion.

Follows Docs/TASKS.md Phase 7, FR-07, and FR-09.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.session import get_db
from smartserve.events.schema import ServiceEventRead
from smartserve.events.service import EventDomainService
from smartserve.integrations.adapters import MockKDSAdapter, MockPOSAdapter

router = APIRouter(prefix="/api/v1/integrations", tags=["POS & KDS Integrations"])

pos_adapter = MockPOSAdapter()
kds_adapter = MockKDSAdapter()


@router.post(
    "/pos/order",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest POS order ticket event",
)
async def ingest_pos_order(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ingest POS order ticket payload with automated table mapping and idempotency."""
    try:
        event_in = pos_adapter.ingest_order(payload)
        event, is_duplicate = await EventDomainService.record_event(db, event_in)
        return {
            "status": "deduplicated" if is_duplicate else "recorded",
            "is_duplicate": is_duplicate,
            "event": ServiceEventRead.model_validate(event).model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/pos/payment",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest POS payment event",
)
async def ingest_pos_payment(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ingest POS payment settlement event."""
    try:
        event_in = pos_adapter.ingest_payment(payload)
        event, is_duplicate = await EventDomainService.record_event(db, event_in)
        return {
            "status": "deduplicated" if is_duplicate else "recorded",
            "is_duplicate": is_duplicate,
            "event": ServiceEventRead.model_validate(event).model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/kds/bump",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest KDS bump bar food delivery event",
)
async def ingest_kds_bump(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ingest KDS bump bar completion event triggering confirmed food delivery."""
    try:
        event_in = kds_adapter.ingest_bump_event(payload)
        event, is_duplicate = await EventDomainService.record_event(db, event_in)
        return {
            "status": "deduplicated" if is_duplicate else "confirmed",
            "is_duplicate": is_duplicate,
            "event": ServiceEventRead.model_validate(event).model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
