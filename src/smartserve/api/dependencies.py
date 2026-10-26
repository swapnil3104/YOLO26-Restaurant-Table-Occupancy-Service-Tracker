"""Common API dependencies."""

from smartserve.config import Settings, settings
from smartserve.occupancy.manager import OccupancySessionManager
from smartserve.tables.manager import TableLayoutManager

_layout_manager: TableLayoutManager | None = None
_occupancy_manager: OccupancySessionManager | None = None


def get_settings() -> Settings:
    """Dependency provider for application settings."""
    return settings


def get_layout_manager() -> TableLayoutManager:
    """Dependency provider for persistent TableLayoutManager."""
    global _layout_manager
    if _layout_manager is None:
        _layout_manager = TableLayoutManager()
    return _layout_manager


def get_occupancy_manager() -> OccupancySessionManager:
    """Dependency provider for persistent OccupancySessionManager."""
    global _occupancy_manager
    if _occupancy_manager is None:
        _occupancy_manager = OccupancySessionManager()
        # Seed manager with configured tables if any
        layout_mgr = get_layout_manager()
        for t in layout_mgr.list_tables():
            _occupancy_manager.register_table(t.id)
    return _occupancy_manager
