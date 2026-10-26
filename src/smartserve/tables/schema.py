"""Data models and schemas for table layout and spatial association."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from smartserve.vision.interfaces import BoundingBox


class Point(BaseModel):
    """Normalized 2D point [0.0, 1.0]."""

    x: float = Field(..., ge=0.0, le=1.0, description="Normalized X coordinate")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized Y coordinate")

    def to_tuple(self) -> tuple[float, float]:
        """Return (x, y) tuple."""
        return (self.x, self.y)


class TablePolygon(BaseModel):
    """Normalized polygon zone representing a table's physical area on camera."""

    vertices: list[Point] = Field(..., min_length=3, description="List of at least 3 vertices")

    @field_validator("vertices")
    @classmethod
    def validate_vertices_count(cls, v: list[Point]) -> list[Point]:
        if len(v) < 3:
            raise ValueError("Table polygon must contain at least 3 vertices.")
        return v

    def as_tuples(self) -> list[tuple[float, float]]:
        """Return vertices as list of (x, y) tuples."""
        return [(p.x, p.y) for p in self.vertices]

    @property
    def bounding_box(self) -> BoundingBox:
        """Compute the axis-aligned bounding box enclosing this polygon."""
        xs = [p.x for p in self.vertices]
        ys = [p.y for p in self.vertices]
        return BoundingBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))

    @property
    def centroid(self) -> tuple[float, float]:
        """Compute polygon centroid using polygon geometric moments or vertex mean."""
        pts = self.as_tuples()
        n = len(pts)
        if n == 0:
            return (0.0, 0.0)

        # Polygon centroid calculation (shoelace moments)
        signed_area = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            cross = (x0 * y1) - (x1 * y0)
            signed_area += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross

        signed_area *= 0.5
        if abs(signed_area) < 1e-7:
            # Fallback to arithmetic mean if degenerate
            return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)

        cx = cx / (6.0 * signed_area)
        cy = cy / (6.0 * signed_area)
        return (cx, cy)

    @property
    def area(self) -> float:
        """Compute normalized polygon area using the shoelace formula."""
        pts = self.as_tuples()
        n = len(pts)
        area_sum = 0.0
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            area_sum += (x0 * y1) - (x1 * y0)
        return abs(area_sum) * 0.5


class TableConfig(BaseModel):
    """Configuration for an individual physical restaurant table."""

    id: str = Field(..., description="Stable internal identifier (e.g. 'table-01' or UUID)")
    code: str = Field(..., description="Human-facing table code (e.g. 'T-01', 'T-02')")
    name: str = Field(..., description="Display name / label (e.g. 'Table 1 - Window Booth')")
    camera_id: str = Field(..., description="Camera identifier monitoring this table")
    capacity: int = Field(default=4, ge=1, le=50, description="Maximum seated guest capacity")
    polygon: TablePolygon = Field(..., description="Normalized polygon coordinates")
    section: str = Field(default="Main Dining", description="Restaurant zone or floor section")
    is_active: bool = Field(default=True, description="Whether table is enabled for tracking")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata / notes")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        code_str = v.strip().upper()
        if not code_str:
            raise ValueError("Table code cannot be empty.")
        return code_str


class TableLayout(BaseModel):
    """Collection of configured tables across cameras/sections."""

    tables: list[TableConfig] = Field(default_factory=list)
    version: str = Field(default="1.0")

    def get_by_id(self, table_id: str) -> TableConfig | None:
        """Find table by its internal ID."""
        for t in self.tables:
            if t.id == table_id:
                return t
        return None

    def get_by_code(self, code: str) -> TableConfig | None:
        """Find table by its human-facing code."""
        code_norm = code.strip().upper()
        for t in self.tables:
            if t.code == code_norm:
                return t
        return None

    def for_camera(self, camera_id: str) -> list[TableConfig]:
        """Return active tables mapped to a specific camera."""
        return [t for t in self.tables if t.camera_id == camera_id and t.is_active]


class AssociationStatus(StrEnum):
    """Spatial association result classification."""

    ASSOCIATED = "associated"
    AMBIGUOUS = "ambiguous"
    UNASSIGNED = "unassigned"


class TrackAssociation(BaseModel):
    """Result of associating an individual person detection/track with a table."""

    track_id: int | None = Field(default=None, description="Ephemeral track ID")
    table_id: str | None = Field(default=None, description="Associated table ID")
    table_code: str | None = Field(default=None, description="Associated table code")
    status: AssociationStatus = Field(..., description="Association classification")
    anchor_point: tuple[float, float] = Field(..., description="Evaluated contact point (cx, y2)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Association confidence")
    competing_tables: list[str] = Field(default_factory=list, description="IDs of competing tables")
    distance_to_edge: float | None = Field(
        default=None, description="Signed distance to nearest edge"
    )
    reason: str | None = Field(
        default=None, description="Explanation for ambiguous/unassigned status"
    )


class TableAssociationResult(BaseModel):
    """Batch association result for a video frame."""

    timestamp: float = Field(..., description="Observation timestamp")
    camera_id: str = Field(..., description="Camera identifier")
    total_detections: int = Field(default=0)
    associated_tracks: dict[str, list[TrackAssociation]] = Field(
        default_factory=dict,
        description="Map of table_id to associated track list",
    )
    ambiguous_tracks: list[TrackAssociation] = Field(
        default_factory=list,
        description="Tracks with competing/unclear table association",
    )
    unassigned_tracks: list[TrackAssociation] = Field(
        default_factory=list,
        description="Tracks clearly outside all table regions",
    )
    table_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Map of table_id to current patron count estimate",
    )
    capacity_warnings: list[str] = Field(
        default_factory=list,
        description="Alert messages for tables exceeding configured capacity",
    )
