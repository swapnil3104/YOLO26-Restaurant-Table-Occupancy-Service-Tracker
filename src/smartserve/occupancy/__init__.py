"""Occupancy state machine and session management package."""

from smartserve.occupancy.manager import OccupancySessionManager
from smartserve.occupancy.schema import (
    CustomerCountUpdateRequest,
    EventSource,
    ManagerOverrideRequest,
    OccupancySnapshot,
    OccupancyState,
    ServiceStatus,
    StateTransitionEvent,
    TableOccupancyStatus,
    TableSession,
    VerificationStatus,
    get_utc_now,
)
from smartserve.occupancy.state_machine import TableStateMachine

__all__ = [
    "CustomerCountUpdateRequest",
    "EventSource",
    "ManagerOverrideRequest",
    "OccupancySessionManager",
    "OccupancySnapshot",
    "OccupancyState",
    "ServiceStatus",
    "StateTransitionEvent",
    "TableOccupancyStatus",
    "TableSession",
    "TableStateMachine",
    "VerificationStatus",
    "get_utc_now",
]
