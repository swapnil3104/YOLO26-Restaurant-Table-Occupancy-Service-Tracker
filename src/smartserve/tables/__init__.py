"""Tables package for table configuration, layout management, and spatial association."""

from smartserve.tables.associator import SpatialTableAssociator, point_in_polygon_raycast
from smartserve.tables.edge_detector import (
    PatronEdgeContact,
    TableEdgeDetection,
    TableEdgeDetector,
    TableEdgeSegment,
)
from smartserve.tables.manager import TableLayoutManager, generate_default_tables
from smartserve.tables.schema import (
    AssociationStatus,
    Point,
    TableAssociationResult,
    TableConfig,
    TableLayout,
    TablePolygon,
    TrackAssociation,
)

__all__ = [
    "AssociationStatus",
    "PatronEdgeContact",
    "Point",
    "SpatialTableAssociator",
    "TableAssociationResult",
    "TableConfig",
    "TableEdgeDetection",
    "TableEdgeDetector",
    "TableEdgeSegment",
    "TableLayout",
    "TableLayoutManager",
    "TablePolygon",
    "TrackAssociation",
    "generate_default_tables",
    "point_in_polygon_raycast",
]
