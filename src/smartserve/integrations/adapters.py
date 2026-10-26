"""Reference POS and KDS adapters for operational event ingestion.

Follows Docs/TASKS.md Phase 7, FR-07, and FR-09.
"""

from datetime import datetime
from typing import Any

from smartserve.database.base import ensure_utc, utc_now
from smartserve.events.schema import (
    EventSource,
    EventType,
    ServiceEventCreate,
    VerificationStatus,
)
from smartserve.integrations.base import BaseKDSAdapter, BasePOSAdapter


class MockPOSAdapter(BasePOSAdapter):
    """Reference POS adapter parsing simulated point-of-sale payloads."""

    def __init__(self, table_mapping: dict[str, str] | None = None) -> None:
        """Initialize with optional external-to-internal table code mapping."""
        self.table_mapping = table_mapping or {
            "T-01": "table-01",
            "T-02": "table-02",
            "T-03": "table-03",
            "T-04": "table-04",
            "T-05": "table-05",
            "T-06": "table-06",
        }

    def map_table_id(self, external_table_code: str) -> str:
        """Map external table code (e.g. 'T-01') to internal table_id ('table-01')."""
        return self.table_mapping.get(external_table_code, external_table_code)

    def ingest_order(self, order_payload: dict[str, Any]) -> ServiceEventCreate:
        """Transform raw POS order ticket payload into ServiceEventCreate."""
        external_table = order_payload.get("table_code") or order_payload.get("table_id")
        if not external_table:
            raise ValueError("POS order payload missing required 'table_code' or 'table_id'")

        internal_table_id = self.map_table_id(str(external_table))
        ticket_id = order_payload.get("ticket_id") or order_payload.get("order_id", "pos_unknown")
        session_id = order_payload.get("session_id")

        ts_raw = order_payload.get("timestamp")
        event_ts = (
            ensure_utc(datetime.fromisoformat(ts_raw)) if isinstance(ts_raw, str) else utc_now()
        )

        idempotency_key = order_payload.get("idempotency_key") or f"pos_order:{ticket_id}"

        return ServiceEventCreate(
            table_id=internal_table_id,
            session_id=session_id,
            event_type=EventType.ORDER_TAKEN,
            event_timestamp=event_ts,
            source=EventSource.POS,
            verification_status=VerificationStatus.CONFIRMED,
            idempotency_key=idempotency_key,
            metadata_json={
                "pos_ticket_id": ticket_id,
                "server_name": order_payload.get("server_name"),
                "items": order_payload.get("items", []),
                "total_amount": order_payload.get("total_amount"),
                "guest_count": order_payload.get("guest_count"),
            },
        )

    def ingest_payment(self, payment_payload: dict[str, Any]) -> ServiceEventCreate:
        """Transform POS payment payload into ServiceEventCreate."""
        external_table = payment_payload.get("table_code") or payment_payload.get("table_id")
        if not external_table:
            raise ValueError("POS payment payload missing required 'table_code' or 'table_id'")

        internal_table_id = self.map_table_id(str(external_table))
        receipt_id = payment_payload.get("receipt_id", "pos_rec_unknown")
        session_id = payment_payload.get("session_id")

        ts_raw = payment_payload.get("timestamp")
        event_ts = (
            ensure_utc(datetime.fromisoformat(ts_raw)) if isinstance(ts_raw, str) else utc_now()
        )

        idempotency_key = payment_payload.get("idempotency_key") or f"pos_payment:{receipt_id}"

        return ServiceEventCreate(
            table_id=internal_table_id,
            session_id=session_id,
            event_type=EventType.PAYMENT,
            event_timestamp=event_ts,
            source=EventSource.POS,
            verification_status=VerificationStatus.CONFIRMED,
            idempotency_key=idempotency_key,
            metadata_json={
                "receipt_id": receipt_id,
                "amount": payment_payload.get("amount"),
                "payment_method": payment_payload.get("payment_method", "CARD"),
            },
        )


class MockKDSAdapter(BaseKDSAdapter):
    """Reference KDS adapter parsing kitchen bump bar events into food delivery events."""

    def __init__(self, table_mapping: dict[str, str] | None = None) -> None:
        self.table_mapping = table_mapping or {
            "T-01": "table-01",
            "T-02": "table-02",
            "T-03": "table-03",
            "T-04": "table-04",
            "T-05": "table-05",
            "T-06": "table-06",
        }

    def map_table_id(self, external_table_code: str) -> str:
        return self.table_mapping.get(external_table_code, external_table_code)

    def ingest_bump_event(self, bump_payload: dict[str, Any]) -> ServiceEventCreate:
        """Transform KDS bump ticket payload into food delivery ServiceEventCreate."""
        external_table = bump_payload.get("table_code") or bump_payload.get("table_id")
        if not external_table:
            raise ValueError("KDS bump payload missing required 'table_code' or 'table_id'")

        internal_table_id = self.map_table_id(str(external_table))
        ticket_id = bump_payload.get("ticket_id", "kds_bump_unknown")
        station = bump_payload.get("station", "EXPO")
        batch_number = bump_payload.get("batch_number", 1)
        session_id = bump_payload.get("session_id")

        ts_raw = bump_payload.get("timestamp")
        event_ts = (
            ensure_utc(datetime.fromisoformat(ts_raw)) if isinstance(ts_raw, str) else utc_now()
        )

        idempotency_key = (
            bump_payload.get("idempotency_key") or f"kds_bump:{ticket_id}:batch_{batch_number}"
        )

        return ServiceEventCreate(
            table_id=internal_table_id,
            session_id=session_id,
            event_type=EventType.FOOD_DELIVERY,
            event_timestamp=event_ts,
            source=EventSource.POS,  # KDS maps to POS/trusted operational integration
            verification_status=VerificationStatus.CONFIRMED,
            idempotency_key=idempotency_key,
            metadata_json={
                "integration": "KDS",
                "kds_ticket_id": ticket_id,
                "station": station,
                "course": bump_payload.get("course"),
                "batch_number": batch_number,
                "items": bump_payload.get("items", []),
                "cook_duration_sec": bump_payload.get("cook_duration_sec"),
            },
        )
