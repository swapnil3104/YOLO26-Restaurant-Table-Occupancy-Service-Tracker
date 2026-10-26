"""Abstract integration adapter interfaces for Point-of-Sale (POS) and Kitchen Display Systems (KDS).

Follows Docs/TASKS.md Phase 7, FR-07, and FR-09.
"""

from abc import ABC, abstractmethod
from typing import Any

from smartserve.events.schema import ServiceEventCreate


class BasePOSAdapter(ABC):
    """Abstract adapter defining POS integration capabilities."""

    @abstractmethod
    def ingest_order(self, order_payload: dict[str, Any]) -> ServiceEventCreate:
        """Parse raw POS order data and construct a standardized ServiceEventCreate."""
        raise NotImplementedError

    @abstractmethod
    def ingest_payment(self, payment_payload: dict[str, Any]) -> ServiceEventCreate:
        """Parse POS payment/close-tab data into a standardized ServiceEventCreate."""
        raise NotImplementedError

    @abstractmethod
    def map_table_id(self, external_table_code: str) -> str:
        """Map external POS table identifier or code to internal SmartServe table_id."""
        raise NotImplementedError


class BaseKDSAdapter(ABC):
    """Abstract adapter defining Kitchen Display System (KDS) integration capabilities."""

    @abstractmethod
    def ingest_bump_event(self, bump_payload: dict[str, Any]) -> ServiceEventCreate:
        """Parse KDS ticket/expo bump events into a standardized food delivery ServiceEventCreate."""
        raise NotImplementedError
