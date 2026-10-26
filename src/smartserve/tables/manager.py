"""Persistent Table Layout Manager for restaurant floor plans.

Handles disk persistence, atomic updates, and CRUD operations for table polygons,
ensuring configurations survive server restarts.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from smartserve.config import settings
from smartserve.tables.schema import Point, TableConfig, TableLayout, TablePolygon

logger = logging.getLogger("smartserve.tables.manager")


def generate_default_tables(camera_id: str = "CAM-01") -> list[TableConfig]:
    """Generate default sample restaurant tables for initial bootstrapping."""
    return [
        TableConfig(
            id="table-01",
            code="T-01",
            name="Table 1 - Window Booth",
            camera_id=camera_id,
            capacity=4,
            section="Window Section",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.08, y=0.15),
                    Point(x=0.38, y=0.15),
                    Point(x=0.38, y=0.45),
                    Point(x=0.08, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-02",
            code="T-02",
            name="Table 2 - Center High-top",
            camera_id=camera_id,
            capacity=2,
            section="Main Dining",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.60, y=0.15),
                    Point(x=0.90, y=0.15),
                    Point(x=0.90, y=0.45),
                    Point(x=0.60, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-03",
            code="T-03",
            name="Table 3 - Family Banquette",
            camera_id=camera_id,
            capacity=6,
            section="Main Dining",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.08, y=0.55),
                    Point(x=0.40, y=0.55),
                    Point(x=0.40, y=0.88),
                    Point(x=0.08, y=0.88),
                ]
            ),
        ),
        TableConfig(
            id="table-04",
            code="T-04",
            name="Table 4 - Patio Entry",
            camera_id=camera_id,
            capacity=4,
            section="Patio",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.58, y=0.55),
                    Point(x=0.90, y=0.55),
                    Point(x=0.90, y=0.88),
                    Point(x=0.58, y=0.88),
                ]
            ),
        ),
    ]


class TableLayoutManager:
    """Manages table layout lifecycle, CRUD operations, and persistent file storage."""

    def __init__(self, file_path: str | Path | None = None):
        """Initialize layout manager.

        Args:
            file_path: Optional path to JSON persistence file. Defaults to settings.TABLE_LAYOUT_PATH.
        """
        self.file_path = Path(file_path or settings.TABLE_LAYOUT_PATH)
        self._layout = TableLayout()
        self.load()

    @property
    def layout(self) -> TableLayout:
        """Return currently loaded layout."""
        return self._layout

    def load(self) -> TableLayout:
        """Load table layout from JSON file. If file does not exist, bootstrap defaults."""
        if not self.file_path.exists():
            logger.info(
                f"Table layout file not found at {self.file_path}. Bootstrapping default layout."
            )
            default_tables = generate_default_tables(camera_id=settings.DEFAULT_CAMERA_ID)
            self._layout = TableLayout(tables=default_tables)
            self.save()
            return self._layout

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
            self._layout = TableLayout.model_validate(data)
            logger.info(f"Loaded {len(self._layout.tables)} tables from {self.file_path}")
        except Exception as e:
            logger.error(
                f"Error loading table layout from {self.file_path}: {e}. Retaining current state."
            )
            raise
        return self._layout

    def save(self) -> None:
        """Atomically persist layout to disk via temporary file rename."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        dump_data = self._layout.model_dump(mode="json")

        # Atomic file write to protect against partial writes on sudden process exit
        temp_dir = self.file_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
            json.dump(dump_data, tmp, indent=2)
            tmp_path = Path(tmp.name)

        try:
            # os.replace is atomic on both POSIX and modern Windows systems
            os.replace(tmp_path, self.file_path)
            logger.debug(f"Saved {len(self._layout.tables)} tables to {self.file_path}")
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def list_tables(self, camera_id: str | None = None) -> list[TableConfig]:
        """List all tables, optionally filtered by camera_id."""
        if camera_id is not None:
            return self._layout.for_camera(camera_id)
        return list(self._layout.tables)

    def get_table(self, table_id: str) -> TableConfig | None:
        """Get table by internal table ID."""
        return self._layout.get_by_id(table_id)

    def get_table_by_code(self, code: str) -> TableConfig | None:
        """Get table by human-facing code."""
        return self._layout.get_by_code(code)

    def add_table(self, table: TableConfig) -> TableConfig:
        """Add a new table. Validates unique ID and unique code."""
        if self._layout.get_by_id(table.id) is not None:
            raise ValueError(f"Table with id '{table.id}' already exists.")
        if self._layout.get_by_code(table.code) is not None:
            raise ValueError(f"Table with code '{table.code}' already exists.")

        self._layout.tables.append(table)
        self.save()
        return table

    def update_table(self, table_id: str, updated: TableConfig) -> TableConfig:
        """Update an existing table."""
        idx = -1
        for i, t in enumerate(self._layout.tables):
            if t.id == table_id:
                idx = i
                break

        if idx == -1:
            raise KeyError(f"Table with id '{table_id}' not found.")

        # Check code uniqueness if code changed
        existing_with_code = self._layout.get_by_code(updated.code)
        if existing_with_code is not None and existing_with_code.id != table_id:
            raise ValueError(f"Table code '{updated.code}' is already used by another table.")

        # Keep original ID
        updated_dict = updated.model_dump()
        updated_dict["id"] = table_id
        final_table = TableConfig.model_validate(updated_dict)

        self._layout.tables[idx] = final_table
        self.save()
        return final_table

    def delete_table(self, table_id: str) -> bool:
        """Delete a table by ID."""
        orig_len = len(self._layout.tables)
        self._layout.tables = [t for t in self._layout.tables if t.id != table_id]
        if len(self._layout.tables) < orig_len:
            self.save()
            return True
        return False

    def reset_to_defaults(self, camera_id: str = "CAM-01") -> TableLayout:
        """Reset table layout to standard default configuration."""
        default_tables = generate_default_tables(camera_id=camera_id)
        self._layout = TableLayout(tables=default_tables)
        self.save()
        return self._layout
