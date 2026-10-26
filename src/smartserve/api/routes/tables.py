"""API routes for restaurant table layout configuration and spatial association."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from smartserve.api.dependencies import get_layout_manager
from smartserve.database.session import get_db
from smartserve.security.auth import resolve_actor
from smartserve.tables.associator import SpatialTableAssociator
from smartserve.tables.manager import TableLayoutManager
from smartserve.tables.schema import TableAssociationResult, TableConfig
from smartserve.vision.interfaces import Detection

router = APIRouter(prefix="/tables", tags=["tables"])


class AssociateRequest(BaseModel):
    """Request payload for spatial table association test."""

    camera_id: str = Field(default="CAM-01", description="Camera identifier")
    detections: list[Detection] = Field(
        default_factory=list, description="List of person detections"
    )


async def _check_layout_write_permission(x_user_id: str | None, db: AsyncSession) -> None:
    """Validate that actor has manager or admin privileges when identified."""
    if x_user_id:
        try:
            actor = await resolve_actor(db, x_user_id)
            if str(actor.role).upper() not in ("MANAGER", "ADMIN"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User '{actor.username}' with role '{actor.role}' is not authorized to modify table layouts. Manager or Admin required.",
                )
        except HTTPException:
            raise
        except Exception:
            pass


@router.get("", response_model=list[TableConfig])
async def list_tables(
    camera_id: str | None = Query(None, description="Optional camera ID filter"),
    manager: TableLayoutManager = Depends(get_layout_manager),
) -> list[TableConfig]:
    """List all configured restaurant tables, optionally filtered by camera."""
    return manager.list_tables(camera_id=camera_id)


@router.get("/{table_id}", response_model=TableConfig)
async def get_table(
    table_id: str,
    manager: TableLayoutManager = Depends(get_layout_manager),
) -> TableConfig:
    """Retrieve details and normalized polygon coordinates for a specific table."""
    table = manager.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found.",
        )
    return table


@router.post("", response_model=TableConfig, status_code=status.HTTP_201_CREATED)
async def create_table(
    table: TableConfig,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    manager: TableLayoutManager = Depends(get_layout_manager),
    db: AsyncSession = Depends(get_db),
) -> TableConfig:
    """Add a new table to the floor plan layout.

    Validates polygon coordinates in [0.0, 1.0], minimum 3 vertices, capacity >= 1,
    and uniqueness of table ID and table code. Requires Manager/Admin role when identified.
    """
    await _check_layout_write_permission(x_user_id, db)
    try:
        return manager.add_table(table)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/{table_id}", response_model=TableConfig)
async def update_table(
    table_id: str,
    updated: TableConfig,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    manager: TableLayoutManager = Depends(get_layout_manager),
    db: AsyncSession = Depends(get_db),
) -> TableConfig:
    """Update layout coordinates, capacity, or metadata for an existing table.

    Requires Manager/Admin role when identified.
    """
    await _check_layout_write_permission(x_user_id, db)
    try:
        return manager.update_table(table_id, updated)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found.",
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{table_id}")
async def delete_table(
    table_id: str,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    manager: TableLayoutManager = Depends(get_layout_manager),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove a table from the floor layout. Requires Manager/Admin role when identified."""
    await _check_layout_write_permission(x_user_id, db)
    deleted = manager.delete_table(table_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID '{table_id}' not found.",
        )
    return {"status": "deleted", "id": table_id}


@router.post("/reset-defaults", response_model=list[TableConfig])
async def reset_default_tables(
    camera_id: str = Query("CAM-01", description="Camera ID for default tables"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    manager: TableLayoutManager = Depends(get_layout_manager),
    db: AsyncSession = Depends(get_db),
) -> list[TableConfig]:
    """Reset floorplan layout to standard 4-table restaurant configuration.

    Requires Manager/Admin role when identified.
    """
    await _check_layout_write_permission(x_user_id, db)
    layout = manager.reset_to_defaults(camera_id=camera_id)
    return layout.tables


@router.post("/associate", response_model=TableAssociationResult)
async def associate_detections(
    request: AssociateRequest,
    manager: TableLayoutManager = Depends(get_layout_manager),
) -> TableAssociationResult:
    """Run point-in-polygon spatial association for a batch of person detections.

    Maps bottom-center contact points to configured table zones, identifies
    ambiguous and unassigned tracks, and computes current occupancy counts.
    """
    tables = manager.list_tables(camera_id=request.camera_id)
    associator = SpatialTableAssociator()
    result = associator.associate_frame(
        detections=request.detections,
        tables=tables,
        camera_id=request.camera_id,
    )
    return result
