"""Timeline generation and UI copy formatting distinguishing confirmation from AI estimation.

Follows Docs/RULES.md (Rules 2.1, 2.3, 2.4, Section 8) and Docs/TASKS.md Phase 7.
"""

from smartserve.database.models import ServiceEvent, TableSession, User
from smartserve.events.schema import (
    EventSource,
    EventType,
    TimelineItemRead,
    VerificationStatus,
)

SOURCE_LABELS: dict[str, str] = {
    EventSource.WAITER_UI.value: "Staff Waiter UI",
    EventSource.MANAGER_OVERRIDE.value: "Manager Override",
    EventSource.VISION.value: "AI Vision System",
    EventSource.POS.value: "POS System Integration",
    "KDS": "Kitchen Display System (KDS)",
    EventSource.SYSTEM.value: "SmartServe System",
}


def build_timeline_item_ui_badge(
    event: ServiceEvent,
    actor_name: str | None,
) -> tuple[str, str]:
    """Generate unambiguous UI badge text and color variant.

    Distinguishes human-verified confirmation from automated or candidate AI estimation.
    Returns:
        tuple[str, str]: (ui_badge_text, ui_badge_variant)
    """
    v_status = event.verification_status
    source = event.source
    actor = actor_name or "Staff"

    if v_status == VerificationStatus.REJECTED.value:
        reason = event.metadata_json.get("rejection_reason", "Mistaken event")
        return f"Rejected: {reason}", "danger"

    if v_status == VerificationStatus.CORRECTED.value:
        reason = event.metadata_json.get("correction_reason", "Superseded")
        return f"Corrected ({reason})", "neutral"

    if source in (EventSource.WAITER_UI.value, "WAITER_UI"):
        return f"Confirmed by Waiter ({actor})", "success"

    if source in (EventSource.MANAGER_OVERRIDE.value, "MANAGER_OVERRIDE"):
        return f"Manager Override ({actor})", "success"

    if source in (EventSource.POS.value, "POS"):
        return "POS Confirmed Order", "info"

    if source in ("KDS", "kds"):
        return "Kitchen Bump Confirmed", "info"

    if source in (EventSource.VISION.value, "VISION"):
        conf = f"{int(event.confidence * 100)}%" if event.confidence is not None else None
        if v_status == VerificationStatus.CONFIRMED.value:
            return f"AI Vision Confirmed{' (' + conf + ')' if conf else ''}", "info"
        return (
            f"AI Vision Estimate (Candidate{' ' + conf if conf else ''} - Unconfirmed)",
            "warning",
        )

    if source in (EventSource.SYSTEM.value, "SYSTEM"):
        return "System Automation", "neutral"

    return f"{source} ({v_status})", "neutral"


def format_timeline_item(
    event: ServiceEvent,
    session: TableSession,
    user_map: dict[str, User] | None = None,
) -> TimelineItemRead:
    """Format an ORM ServiceEvent into a structured TimelineItemRead."""
    user_map = user_map or {}
    actor_user = user_map.get(event.created_by) if event.created_by else None
    actor_name = actor_user.display_name if actor_user else event.created_by

    source_label = SOURCE_LABELS.get(event.source, event.source.replace("_", " ").title())
    badge_text, badge_variant = build_timeline_item_ui_badge(event, actor_name)

    is_confirmed = event.verification_status == VerificationStatus.CONFIRMED.value

    # Check if this event corresponds to active session milestones
    is_active_milestone = False
    milestone_type = None

    if is_confirmed:
        if (
            session.first_attendance_at
            and event.event_timestamp == session.first_attendance_at
            and event.event_type in (EventType.FIRST_ATTENDANCE.value, EventType.ATTENDANCE.value)
        ):
            is_active_milestone = True
            milestone_type = "FIRST_ATTENDANCE"

        elif (
            session.first_food_delivery_at
            and event.event_timestamp == session.first_food_delivery_at
            and event.event_type == EventType.FOOD_DELIVERY.value
        ):
            is_active_milestone = True
            milestone_type = "FIRST_FOOD_DELIVERY"

        elif (
            session.started_at
            and event.event_timestamp == session.started_at
            and event.event_type == EventType.SEATING.value
        ):
            is_active_milestone = True
            milestone_type = "SEATING"

        elif (
            session.ended_at
            and event.event_timestamp == session.ended_at
            and event.event_type == EventType.DEPARTURE.value
        ):
            is_active_milestone = True
            milestone_type = "DEPARTURE"

    return TimelineItemRead(
        event_id=event.event_id,
        event_type=event.event_type,
        event_timestamp=event.event_timestamp,
        recorded_at=event.recorded_at,
        source=event.source,
        source_label=source_label,
        verification_status=event.verification_status,
        is_confirmed=is_confirmed,
        actor_id=event.created_by,
        actor_name=actor_name,
        is_active_milestone=is_active_milestone,
        milestone_type=milestone_type,
        ui_badge_text=badge_text,
        ui_badge_variant=badge_variant,
        metadata_json=event.metadata_json or {},
        is_correction=event.is_correction,
        supersedes_event_id=event.supersedes_event_id,
    )
