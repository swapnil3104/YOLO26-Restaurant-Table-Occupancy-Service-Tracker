"""REST API endpoints for restaurant floor management.

Adheres strictly to Docs/TASKS.md Phase 7:
- Introduce Floor entity with source/floor associations.
- Implement authenticated endpoints: GET /api/floors, POST /api/floors.
- Persist floor configuration to SQLite/PostgreSQL with consistent time zones.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.database.base import utc_now
from smartserve.database.models import Camera, Floor, Restaurant, User
from smartserve.database.session import get_db
from smartserve.security.auth import require_manager_or_admin, require_staff_actor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Floors"])


class FloorModel(BaseModel):
    """Metadata schema for a restaurant floor."""

    floor_id: str
    restaurant_id: str
    floor_name: str
    floor_number: int
    is_active: bool
    camera_count: int = 0
    metadata_json: dict[str, Any] = {}
    created_at: str


class CreateFloorRequest(BaseModel):
    """Payload to register a new restaurant floor."""

    floor_name: str = Field(
        ..., min_length=1, max_length=128, description="Floor label, e.g. Floor 1, Rooftop"
    )
    floor_id: str | None = Field(
        None, min_length=2, max_length=64, description="Optional custom floor ID"
    )
    floor_number: int = Field(1, ge=-5, le=100, description="Numerical level order")
    restaurant_id: str = Field("rest_bistro_01", description="Restaurant establishment ID")
    metadata_json: dict[str, Any] = Field(default_factory=dict)


async def ensure_default_restaurant_and_floors(db: AsyncSession) -> None:
    """Ensure baseline restaurant and default floors exist in the database."""
    # Check restaurant
    rest_stmt = select(Restaurant).where(Restaurant.restaurant_id == "rest_bistro_01")
    rest_res = await db.execute(rest_stmt)
    rest = rest_res.scalar_one_or_none()
    if not rest:
        rest = Restaurant(
            restaurant_id="rest_bistro_01",
            name="Bistro Lumiere",
            timezone="UTC",
            created_at=utc_now(),
        )
        db.add(rest)
        await db.commit()

    # Check floors
    floor_stmt = select(func.count()).select_from(Floor)
    count_res = await db.execute(floor_stmt)
    count = count_res.scalar_one()

    if count == 0:
        default_floors = [
            Floor(
                floor_id="floor-01",
                restaurant_id="rest_bistro_01",
                floor_name="Floor 1",
                floor_number=1,
                is_active=True,
                created_at=utc_now(),
            ),
            Floor(
                floor_id="floor-02",
                restaurant_id="rest_bistro_01",
                floor_name="Floor 2",
                floor_number=2,
                is_active=True,
                created_at=utc_now(),
            ),
        ]
        db.add_all(default_floors)
        await db.commit()
        logger.info("Seeded default floors: Floor 1, Floor 2")


@router.get(
    "/floors",
    response_model=list[FloorModel],
    summary="List restaurant floors",
)
async def list_floors(
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> list[FloorModel]:
    """List all registered floors with camera counts and active status."""
    await ensure_default_restaurant_and_floors(db)

    stmt = select(Floor).order_by(Floor.floor_number.asc(), Floor.floor_name.asc())
    res = await db.execute(stmt)
    floors = res.scalars().all()

    # Query camera counts grouped by floor_name or floor_id
    cam_stmt = select(Camera.floor_id, Camera.floor_name, func.count(Camera.camera_id)).group_by(
        Camera.floor_id, Camera.floor_name
    )
    cam_res = await db.execute(cam_stmt)
    cam_counts = cam_res.all()

    counts_by_id: dict[str, int] = {}
    counts_by_name: dict[str, int] = {}
    for fid, fname, c in cam_counts:
        if fid:
            counts_by_id[fid] = counts_by_id.get(fid, 0) + c
        if fname:
            counts_by_name[fname] = counts_by_name.get(fname, 0) + c

    result = []
    for f in floors:
        count = counts_by_id.get(f.floor_id) or counts_by_name.get(f.floor_name) or 0
        result.append(
            FloorModel(
                floor_id=f.floor_id,
                restaurant_id=f.restaurant_id,
                floor_name=f.floor_name,
                floor_number=f.floor_number,
                is_active=f.is_active,
                camera_count=count,
                metadata_json=f.metadata_json or {},
                created_at=f.created_at.isoformat()
                if f.created_at
                else datetime.now(UTC).isoformat(),
            )
        )
    return result


@router.post(
    "/floors",
    response_model=FloorModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new floor",
)
async def create_floor(
    payload: CreateFloorRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> FloorModel:
    """Create a new restaurant floor. Requires Manager or Administrator role."""
    await ensure_default_restaurant_and_floors(db)

    # Determine unique floor_id
    floor_id = payload.floor_id
    if not floor_id:
        slug = payload.floor_name.strip().lower().replace(" ", "-")
        floor_id = f"floor-{slug}"

    # Check for duplicate floor_id
    stmt_check = select(Floor).where(Floor.floor_id == floor_id)
    res_check = await db.execute(stmt_check)
    if res_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Floor with ID '{floor_id}' already exists.",
        )

    # Check duplicate floor_name
    stmt_name = select(Floor).where(Floor.floor_name == payload.floor_name.strip())
    res_name = await db.execute(stmt_name)
    if res_name.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Floor with name '{payload.floor_name}' already exists.",
        )

    now = utc_now()
    floor = Floor(
        floor_id=floor_id,
        restaurant_id=payload.restaurant_id,
        floor_name=payload.floor_name.strip(),
        floor_number=payload.floor_number,
        is_active=True,
        metadata_json=payload.metadata_json,
        created_at=now,
    )
    db.add(floor)
    await db.commit()
    await db.refresh(floor)

    logger.info(
        f"Created new floor {floor.floor_id} ({floor.floor_name}) by user {current_user.username}"
    )

    return FloorModel(
        floor_id=floor.floor_id,
        restaurant_id=floor.restaurant_id,
        floor_name=floor.floor_name,
        floor_number=floor.floor_number,
        is_active=floor.is_active,
        camera_count=0,
        metadata_json=floor.metadata_json or {},
        created_at=floor.created_at.isoformat(),
    )


@router.get(
    "/floors/{floor_id}",
    response_model=FloorModel,
    summary="Get single floor details",
)
async def get_floor(
    floor_id: str,
    current_user: User = Depends(require_staff_actor),
    db: AsyncSession = Depends(get_db),
) -> FloorModel:
    """Retrieve details of a single restaurant floor."""
    stmt = select(Floor).where(Floor.floor_id == floor_id)
    res = await db.execute(stmt)
    floor = res.scalar_one_or_none()

    if not floor:
        # Fallback check by name
        stmt_name = select(Floor).where(Floor.floor_name == floor_id)
        res_name = await db.execute(stmt_name)
        floor = res_name.scalar_one_or_none()

    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor '{floor_id}' not found.",
        )

    cam_stmt = select(func.count(Camera.camera_id)).where(
        (Camera.floor_id == floor.floor_id) | (Camera.floor_name == floor.floor_name)
    )
    cam_count = (await db.execute(cam_stmt)).scalar_one()

    return FloorModel(
        floor_id=floor.floor_id,
        restaurant_id=floor.restaurant_id,
        floor_name=floor.floor_name,
        floor_number=floor.floor_number,
        is_active=floor.is_active,
        camera_count=cam_count,
        metadata_json=floor.metadata_json or {},
        created_at=floor.created_at.isoformat()
        if floor.created_at
        else datetime.now(UTC).isoformat(),
    )
