"""Service timers and interval calculation module conforming to RULES.md Section 8."""

from datetime import datetime

from pydantic import BaseModel, Field

from smartserve.database.base import ensure_utc, utc_now


class MetricInterval(BaseModel):
    """Represents a computed timing interval with validity flags."""

    duration_sec: float | None = Field(
        default=None,
        description="Elapsed duration in seconds, or None if pending/missing",
    )
    is_valid: bool = Field(
        default=True,
        description="True if the interval was valid and non-negative",
    )
    is_negative: bool = Field(
        default=False,
        description="True if occurrence was before milestone anchor point",
    )
    anomaly_reason: str | None = Field(
        default=None,
        description="Detailed description of inconsistency if invalid",
    )


class SessionMetrics(BaseModel):
    """Calculated operational metrics for a table dining session."""

    session_id: str
    table_id: str
    started_at: datetime
    ended_at: datetime | None = None
    first_attendance_at: datetime | None = None
    first_food_delivery_at: datetime | None = None

    # Computed Milestones (RULES.md Section 8.2)
    first_response: MetricInterval
    food_delivery: MetricInterval
    attendance_to_food: MetricInterval
    occupancy_duration: MetricInterval

    # In-progress elapsed timers (relative to evaluation reference time)
    evaluation_time: datetime
    elapsed_since_seating_sec: float
    elapsed_since_attendance_sec: float | None = None

    # Overall Data Quality & Status
    has_inconsistencies: bool = False
    inconsistencies: list[str] = Field(default_factory=list)


class SessionTimersCalculator:
    """Pure domain calculator for dining session service intervals."""

    @classmethod
    def calculate_metrics(
        cls,
        session_id: str,
        table_id: str,
        started_at: datetime,
        ended_at: datetime | None = None,
        first_attendance_at: datetime | None = None,
        first_food_delivery_at: datetime | None = None,
        reference_time: datetime | None = None,
    ) -> SessionMetrics:
        """Calculate service intervals for a session.

        Conforms strictly to RULES.md:
        - Negative intervals are not silently clamped to zero.
        - Missing events return duration_sec=None (pending).
        - Timestamps are normalized to UTC.
        """
        ref_now = ensure_utc(reference_time or utc_now())
        start_utc = ensure_utc(started_at)
        end_utc = ensure_utc(ended_at) if ended_at else None
        att_utc = ensure_utc(first_attendance_at) if first_attendance_at else None
        food_utc = ensure_utc(first_food_delivery_at) if first_food_delivery_at else None

        inconsistencies: list[str] = []

        # 1. First Response Time: T_attendance - T_seating
        first_response = cls._compute_interval(
            anchor_name="seating",
            anchor_time=start_utc,
            event_name="first_attendance",
            event_time=att_utc,
        )
        if first_response.is_negative:
            inconsistencies.append(
                first_response.anomaly_reason or "Negative first response interval"
            )

        # 2. Food Delivery Time: T_food - T_seating
        food_delivery = cls._compute_interval(
            anchor_name="seating",
            anchor_time=start_utc,
            event_name="first_food_delivery",
            event_time=food_utc,
        )
        if food_delivery.is_negative:
            inconsistencies.append(
                food_delivery.anomaly_reason or "Negative food delivery interval"
            )

        # 3. Attendance to Delivery: T_food - T_attendance
        if att_utc and food_utc:
            attendance_to_food = cls._compute_interval(
                anchor_name="first_attendance",
                anchor_time=att_utc,
                event_name="first_food_delivery",
                event_time=food_utc,
            )
            if attendance_to_food.is_negative:
                inconsistencies.append(
                    attendance_to_food.anomaly_reason or "Food delivery recorded before attendance"
                )
        else:
            attendance_to_food = MetricInterval(
                duration_sec=None,
                is_valid=True,
                is_negative=False,
                anomaly_reason=None,
            )

        # 4. Occupancy Duration: T_end - T_seating
        occupancy_duration = cls._compute_interval(
            anchor_name="seating",
            anchor_time=start_utc,
            event_name="departure/end",
            event_time=end_utc,
        )
        if occupancy_duration.is_negative:
            inconsistencies.append(
                occupancy_duration.anomaly_reason
                or "Negative occupancy duration (end before start)"
            )

        # Elapsed timers
        elapsed_seating = (ref_now - start_utc).total_seconds()
        elapsed_attendance = (ref_now - att_utc).total_seconds() if att_utc else None

        return SessionMetrics(
            session_id=session_id,
            table_id=table_id,
            started_at=start_utc,
            ended_at=end_utc,
            first_attendance_at=att_utc,
            first_food_delivery_at=food_utc,
            first_response=first_response,
            food_delivery=food_delivery,
            attendance_to_food=attendance_to_food,
            occupancy_duration=occupancy_duration,
            evaluation_time=ref_now,
            elapsed_since_seating_sec=elapsed_seating,
            elapsed_since_attendance_sec=elapsed_attendance,
            has_inconsistencies=len(inconsistencies) > 0,
            inconsistencies=inconsistencies,
        )

    @staticmethod
    def _compute_interval(
        anchor_name: str,
        anchor_time: datetime,
        event_name: str,
        event_time: datetime | None,
    ) -> MetricInterval:
        """Compute delta between anchor and event, detecting negative intervals."""
        if event_time is None:
            return MetricInterval(duration_sec=None, is_valid=True, is_negative=False)

        delta_sec = (event_time - anchor_time).total_seconds()
        if delta_sec < 0:
            return MetricInterval(
                duration_sec=delta_sec,  # DO NOT clamp to zero
                is_valid=False,
                is_negative=True,
                anomaly_reason=(
                    f"Inconsistent interval: {event_name} ({event_time.isoformat()}) "
                    f"occurred before {anchor_name} ({anchor_time.isoformat()}) "
                    f"by {abs(delta_sec):.1f}s"
                ),
            )

        return MetricInterval(
            duration_sec=delta_sec,
            is_valid=True,
            is_negative=False,
            anomaly_reason=None,
        )
