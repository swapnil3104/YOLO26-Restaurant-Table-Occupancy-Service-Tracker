"""Configurable service thresholds for dining operations."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ServiceThresholds(BaseModel):
    """Configurable timing thresholds for operational alerts (in seconds)."""

    first_attendance_warning_sec: float = Field(
        default=180.0,
        ge=10.0,
        description="Elapsed time before warning alert for first attendance (default: 3 minutes)",
    )
    first_attendance_critical_sec: float = Field(
        default=300.0,
        ge=20.0,
        description="Elapsed time before critical alert for first attendance (default: 5 minutes)",
    )
    food_delivery_warning_sec: float = Field(
        default=900.0,
        ge=60.0,
        description="Elapsed time before warning alert for food delivery (default: 15 minutes)",
    )
    food_delivery_critical_sec: float = Field(
        default=1500.0,
        ge=120.0,
        description="Elapsed time before critical alert for food delivery (default: 25 minutes)",
    )
    no_interaction_warning_sec: float = Field(
        default=600.0,
        ge=60.0,
        description="Elapsed time without interaction before review alert (default: 10 minutes)",
    )
    occupancy_warning_sec: float = Field(
        default=7200.0,
        ge=300.0,
        description="Elapsed table occupancy before alert (default: 2 hours)",
    )
    camera_stale_critical_sec: float = Field(
        default=30.0,
        ge=5.0,
        description="Seconds without valid camera frame before stale alert (default: 30s)",
    )

    def validate_threshold_hierarchy(self) -> None:
        """Ensure critical thresholds are greater than warning thresholds."""
        if self.first_attendance_critical_sec <= self.first_attendance_warning_sec:
            raise ValueError(
                f"first_attendance_critical_sec ({self.first_attendance_critical_sec}) "
                f"must be strictly greater than warning ({self.first_attendance_warning_sec})"
            )
        if self.food_delivery_critical_sec <= self.food_delivery_warning_sec:
            raise ValueError(
                f"food_delivery_critical_sec ({self.food_delivery_critical_sec}) "
                f"must be strictly greater than warning ({self.food_delivery_warning_sec})"
            )


class ThresholdManager:
    """Manages loading, updating, and persisting service threshold configurations."""

    def __init__(self, config_path: str = "config/thresholds.json") -> None:
        self.config_path = Path(config_path)
        self._current_thresholds = self._load()

    def get_thresholds(self) -> ServiceThresholds:
        """Retrieve the current active thresholds."""
        return self._current_thresholds

    def update_thresholds(self, new_thresholds: ServiceThresholds) -> ServiceThresholds:
        """Validate and apply new service thresholds, persisting to disk."""
        new_thresholds.validate_threshold_hierarchy()
        self._current_thresholds = new_thresholds
        self._save()
        return self._current_thresholds

    def _load(self) -> ServiceThresholds:
        """Load thresholds from disk if exists, otherwise return defaults."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                thresholds = ServiceThresholds.model_validate(data)
                thresholds.validate_threshold_hierarchy()
                return thresholds
            except Exception:
                pass
        return ServiceThresholds()

    def _save(self) -> None:
        """Save current thresholds atomically to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.config_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(self._current_thresholds.model_dump(), indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.config_path)


# Global singleton instance
threshold_manager = ThresholdManager()
