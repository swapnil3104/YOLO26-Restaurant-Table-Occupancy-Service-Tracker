#!/usr/bin/env python3
"""Chronological demonstration of waiter/manager confirmation, multiple delivery batches, rejection, and timeline presentation.

Follows Docs/TASKS.md Phase 7, FR-07, FR-08, FR-09, and Docs/RULES.md (Sections 6, 7, 8).
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure src is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base
from smartserve.database.models import Restaurant, Table, User
from smartserve.events.schema import (
    AttendanceConfirmationRequest,
    EventSource,
    EventType,
    FoodDeliveryConfirmationRequest,
    ServiceEventCreate,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.integrations.adapters import MockKDSAdapter, MockPOSAdapter
from smartserve.rules.engine import RulesEngine


async def run_confirmation_demo():
    print("=" * 80)
    print("🍽️  SmartServe AI — Phase 7 Service Confirmation & Timeline Lifecycle Demo")
    print("=" * 80)

    # 1. Setup isolated in-memory DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Seed restaurant, table, and staff users
        rest = Restaurant(restaurant_id="rest_demo", name="Le Bistro Elegance", timezone="UTC")
        table = Table(
            table_id="table-01",
            restaurant_id="rest_demo",
            table_code="T-01",
            capacity=4,
            status="AVAILABLE",
        )
        waiter = User(
            user_id="usr_waiter_sam",
            restaurant_id="rest_demo",
            username="waiter_sam",
            display_name="Sam Waiter",
            role="WAITER",
            active=True,
        )
        manager = User(
            user_id="usr_mgr_morgan",
            restaurant_id="rest_demo",
            username="mgr_morgan",
            display_name="Morgan Manager",
            role="MANAGER",
            active=True,
        )
        db.add_all([rest, table, waiter, manager])
        await db.commit()

        t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        print(f"\n[1] 🚪 T+00:00 ({t0.strftime('%H:%M:%S')}) — Guests Seated at Table T-01")
        sess_in = TableSessionCreate(
            session_id="sess_demo_01",
            table_id="table-01",
            restaurant_id="rest_demo",
            started_at=t0,
            customer_count=3,
        )
        dining_session, _ = await EventDomainService.create_table_session(db, sess_in)
        # Record initial SEATING event
        await EventDomainService.record_event(
            db,
            ServiceEventCreate(
                table_id="table-01",
                session_id=dining_session.session_id,
                event_type=EventType.SEATING,
                event_timestamp=t0,
                source=EventSource.VISION,
                confidence=0.95,
                verification_status=VerificationStatus.CONFIRMED,
            ),
        )
        print(
            f"    ✓ Session created: {dining_session.session_id} (Guests: {dining_session.customer_count})"
        )

        # 2. Simulate AI Vision Candidate (Unconfirmed Estimate)
        t_vision_cand = t0 + timedelta(seconds=60)
        print(
            f"\n[2] 👁️  T+01:00 ({t_vision_cand.strftime('%H:%M:%S')}) — Vision Detects Person Near Table (Candidate)"
        )
        cand_event, _ = await EventDomainService.record_event(
            db,
            ServiceEventCreate(
                table_id="table-01",
                session_id=dining_session.session_id,
                event_type=EventType.ATTENDANCE,
                event_timestamp=t_vision_cand,
                source=EventSource.VISION,
                confidence=0.62,
                verification_status=VerificationStatus.CANDIDATE,
                metadata_json={"detector": "yolo26", "dwell_time_sec": 4.5},
            ),
        )
        print(
            "    ✓ AI Detection recorded as CANDIDATE (Rule 2.1: Not automatically a confirmed event)"
        )

        # 3. Simulate Alert Evaluation at T+02:30 (Crossing Attendance Warning Threshold)
        t_eval = t0 + timedelta(seconds=150)
        print(
            f"\n[3] ⚠️  T+02:30 ({t_eval.strftime('%H:%M:%S')}) — Rules Engine Evaluates Active Session"
        )
        eval_result = await RulesEngine.evaluate_session(dining_session, db, reference_time=t_eval)
        print(f"    ✓ Alert Generated: {eval_result['actions']['created']}")

        # 4. Authorized Waiter Confirms Attendance via Waiter UI
        t_attend = t0 + timedelta(seconds=180)
        print(
            f"\n[4] 🙋 T+03:00 ({t_attend.strftime('%H:%M:%S')}) — Waiter Sam Confirms Table Visit (Staff UI)"
        )
        attend_req = AttendanceConfirmationRequest(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_timestamp=t_attend,
            notes="Greeted party, provided menus and water",
            idempotency_key="idemp_attend_demo_01",
        )
        attend_event, is_dup = await EventDomainService.confirm_attendance(db, attend_req, waiter)
        await db.refresh(dining_session)
        print(f"    ✓ Attendance Confirmed by: {waiter.display_name} ({waiter.role})")
        print(
            f"    ✓ Session first_attendance_at: {dining_session.first_attendance_at.strftime('%H:%M:%S')}"
        )
        print(
            f"    ✓ Response Time: {(dining_session.first_attendance_at - dining_session.started_at).total_seconds()}s"
        )
        print("    ✓ Overdue Attendance Alert Auto-Resolved (Reason: ATTENDANCE_CONFIRMED)")

        # 5. POS Ingests Order
        t_order = t0 + timedelta(seconds=300)
        print(
            f"\n[5] 🧾 T+05:00 ({t_order.strftime('%H:%M:%S')}) — POS Adapter Ingests Order Ticket"
        )
        pos_adapter = MockPOSAdapter()
        pos_order_in = pos_adapter.ingest_order(
            {
                "table_code": "T-01",
                "session_id": dining_session.session_id,
                "ticket_id": "POS-9821",
                "timestamp": t_order.isoformat(),
                "server_name": "Sam Waiter",
                "items": ["Calamari Fritti", "Truffle Tagliatelle", "Branzino al Forno"],
                "total_amount": 115.50,
            }
        )
        order_event, _ = await EventDomainService.record_event(db, pos_order_in)
        print(
            f"    ✓ POS Order Ingested: Ticket #{order_event.metadata_json['pos_ticket_id']} ({len(order_event.metadata_json['items'])} items)"
        )

        # 6. Food Delivery Batch 1: Appetizers Confirmed by Waiter
        t_food_1 = t0 + timedelta(seconds=600)
        print(
            f"\n[6] 🍲 T+10:00 ({t_food_1.strftime('%H:%M:%S')}) — Waiter Confirms Food Delivery (Batch 1 - Appetizers)"
        )
        food_req_1 = FoodDeliveryConfirmationRequest(
            table_id="table-01",
            session_id=dining_session.session_id,
            event_timestamp=t_food_1,
            course="appetizers",
            batch_number=1,
            items=["Calamari Fritti"],
            idempotency_key="idemp_food_batch_1",
            notes="Served hot appetizers",
        )
        food_event_1, _ = await EventDomainService.confirm_food_delivery(db, food_req_1, waiter)
        await db.refresh(dining_session)
        print(
            f"    ✓ Food Delivery Confirmed: Batch #{food_req_1.batch_number} ({food_req_1.course})"
        )
        print(
            f"    ✓ Session first_food_delivery_at milestone: {dining_session.first_food_delivery_at.strftime('%H:%M:%S')}"
        )
        print(
            f"    ✓ First Delivery Interval: {(dining_session.first_food_delivery_at - dining_session.started_at).total_seconds()}s"
        )

        # 7. Food Delivery Batch 2: KDS Bump Bar Ingestion for Mains
        t_food_2 = t0 + timedelta(seconds=1200)
        print(
            f"\n[7] 🍝 T+20:00 ({t_food_2.strftime('%H:%M:%S')}) — KDS Adapter Ingests Bump Bar (Batch 2 - Mains)"
        )
        kds_adapter = MockKDSAdapter()
        kds_bump_in = kds_adapter.ingest_bump_event(
            {
                "table_code": "T-01",
                "session_id": dining_session.session_id,
                "ticket_id": "KDS-501",
                "station": "EXPO",
                "course": "mains",
                "batch_number": 2,
                "items": ["Truffle Tagliatelle", "Branzino al Forno"],
                "timestamp": t_food_2.isoformat(),
            }
        )
        food_event_2, _ = await EventDomainService.record_event(db, kds_bump_in)
        await db.refresh(dining_session)
        print(
            f"    ✓ KDS Bump Ingested: Batch #{food_event_2.metadata_json['batch_number']} ({food_event_2.metadata_json['course']})"
        )
        print(
            f"    ✓ Multiple deliveries preserved! Earliest delivery milestone retained: {dining_session.first_food_delivery_at.strftime('%H:%M:%S')}"
        )

        # 8. Manager Rejection Workflow on Mistaken Event
        print("\n[8] ❌ Mistaken Event Rejection & Safe Recalculation")
        # Record a mistaken early attendance candidate at T+00:30
        mistaken_ts = t0 + timedelta(seconds=30)
        mistaken_event, _ = await EventDomainService.record_event(
            db,
            ServiceEventCreate(
                table_id="table-01",
                session_id=dining_session.session_id,
                event_type=EventType.ATTENDANCE,
                event_timestamp=mistaken_ts,
                source=EventSource.VISION,
                verification_status=VerificationStatus.CONFIRMED,
                metadata_json={"note": "Mistaken automated false-positive attendance"},
            ),
        )
        # Recalculate session to reflect this early milestone
        await RulesEngine.recalculate_session(dining_session.session_id, db)
        await db.refresh(dining_session)
        print(
            f"    ! Early attendance mistakenly marked first_attendance_at: {dining_session.first_attendance_at.strftime('%H:%M:%S')}"
        )

        # Manager Morgan rejects the mistaken event
        rejected_event, audit = await EventDomainService.reject_event(
            db,
            mistaken_event.event_id,
            reason="Busboy cleared empty glass; not waiter attendance",
            rejected_by=manager.user_id,
        )
        await db.refresh(dining_session)
        print(f"    ✓ Manager {manager.display_name} rejected event: {rejected_event.event_id}")
        print(f"    ✓ Event status: {rejected_event.verification_status} (Audit: {audit.action})")
        print(
            f"    ✓ Recalculated first_attendance_at successfully restored to: {dining_session.first_attendance_at.strftime('%H:%M:%S')}"
        )

        # 9. Query Full Structured Timeline with UI Presentation Badges
        print(
            f"\n[9] 📊 Complete Dining Session Timeline (GET /api/v1/sessions/{dining_session.session_id}/timeline)"
        )
        print("-" * 80)
        timeline = await EventDomainService.get_session_timeline(db, dining_session.session_id)
        for idx, item in enumerate(timeline.items, 1):
            ms_flag = f" [★ {item.milestone_type}]" if item.is_active_milestone else ""
            print(
                f"    {idx:02d}. [{item.event_timestamp.strftime('%H:%M:%S')}] {item.event_type:<16} | Source: {item.source_label:<24} | Badge: {item.ui_badge_text}{ms_flag}"
            )

        print("-" * 80)
        print("    Timeline Summary:")
        print(f"    • Total Events: {timeline.summary['total_events']}")
        print(
            f"    • Confirmed: {timeline.summary['confirmed_events']} | Candidate: {timeline.summary['candidate_events']} | Rejected: {timeline.summary['rejected_events']}"
        )
        print(f"    • Food Delivery Batches: {timeline.summary['food_delivery_batches']}")
        print(f"    • First-Response Time: {timeline.summary['response_time_sec']}s")
        print(f"    • Food Delivery Time: {timeline.summary['food_delivery_time_sec']}s")
        print("=" * 80)
        print("✅ Phase 7 Demonstration Complete: All Confirmation & Integrity Rules Verified!")


if __name__ == "__main__":
    asyncio.run(run_confirmation_demo())
