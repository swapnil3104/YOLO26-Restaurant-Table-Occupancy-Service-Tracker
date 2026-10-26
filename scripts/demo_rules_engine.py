"""Chronological demonstration of Service Timers, Rules Engine, and Alert Lifecycles.

Demonstrates:
1. Table seating and session creation (T_seating).
2. Interval evaluation at +120s (under threshold -> no alerts).
3. First attendance warning at +180s (warning threshold reached -> active alert).
4. Escalation at +300s (critical threshold reached -> escalated in-place to CRITICAL, no duplicate).
5. Waiter attendance confirmation at +315s -> alert auto-resolved with ATTENDANCE_CONFIRMED.
6. Food delivery delay at +950s -> FOOD_DELIVERY_OVERDUE warning created.
7. Food delivery confirmation at +980s -> alert auto-resolved with FOOD_DELIVERY_CONFIRMED.
8. Event correction -> manager corrects attendance timestamp, triggers safe recalculation.
9. Guest departure at +3600s -> occupancy duration calculated and session completed.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure src is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from smartserve.database.base import Base
from smartserve.database.models import (
    Alert,
    Camera,
    Restaurant,
    Table,
    TableSession,
    User,
)
from smartserve.events.schema import (
    DataQuality,
    EventCorrectionRequest,
    EventSource,
    EventType,
    ServiceEventCreate,
    TableSessionCreate,
    VerificationStatus,
)
from smartserve.events.service import EventDomainService
from smartserve.rules.engine import RulesEngine
from smartserve.rules.timers import SessionTimersCalculator


async def run_demo():
    print("=" * 78)
    print("  SmartServe AI -- Service Timers & Rules Engine Demonstration (Phase 6)")
    print("=" * 78)

    # In-memory async SQLite engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_maker() as db:
        # 1. Setup seed records
        print("\n[Step 1] Initializing establishment and table...")
        rest = Restaurant(restaurant_id="rest_demo", name="Osteria Del Sole", timezone="UTC")
        cam = Camera(camera_id="CAM-01", restaurant_id="rest_demo", name="Dining Room Front")
        table = Table(
            table_id="tbl_demo_01",
            restaurant_id="rest_demo",
            table_code="T-04",
            capacity=4,
            camera_id="CAM-01",
            region_config={},
        )
        waiter = User(
            user_id="user_waiter_lucia",
            restaurant_id="rest_demo",
            username="lucia_s",
            display_name="Lucia Santoro",
            role="WAITER",
        )
        db.add_all([rest, cam, table, waiter])
        await db.commit()
        print("  [OK] Restaurant, Camera, Table T-04, and Waiter Lucia seeded.")

        # 2. Seating event: T0 = 12:00:00 UTC
        t0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        session_id = "SESS-DEMO-20261022-01"
        print(f"\n[Step 2] Table Seated at {t0.strftime('%H:%M:%S UTC')}")
        await EventDomainService.create_table_session(
            db,
            TableSessionCreate(
                session_id=session_id,
                table_id="tbl_demo_01",
                restaurant_id="rest_demo",
                started_at=t0,
                customer_count=2,
                data_quality=DataQuality.CONFIRMED,
            ),
        )
        print(f"  [OK] Active session created: {session_id}")

        # 3. Elapsed +120s: check rules (warning threshold is 180s)
        t_120 = t0 + timedelta(seconds=120)
        print(f"\n[Step 3] Evaluating rules at +120s ({t_120.strftime('%H:%M:%S')})...")
        sess_stmt = select(TableSession).where(TableSession.session_id == session_id)
        session_obj = (await db.execute(sess_stmt)).scalar_one()

        res_120 = await RulesEngine.evaluate_session(session_obj, db, reference_time=t_120)
        print(f"  Elapsed since seating: {res_120['metrics']['elapsed_since_seating_sec']:.0f}s")
        print(
            f"  Alerts created: {res_120['actions']['created'] or 'None (within normal threshold)'}"
        )

        # 4. Elapsed +180s: first attendance threshold reached (3m warning)
        t_180 = t0 + timedelta(seconds=180)
        print(
            f"\n[Step 4] Evaluating rules at +180s ({t_180.strftime('%H:%M:%S')}) -- Warning Threshold"
        )
        res_180 = await RulesEngine.evaluate_session(session_obj, db, reference_time=t_180)
        print(f"  Alerts created: {res_180['actions']['created']}")
        alerts_now = (
            (await db.execute(select(Alert).where(Alert.session_id == session_id))).scalars().all()
        )
        print(
            f"  Active alert: Type={alerts_now[0].alert_type}, Severity={alerts_now[0].severity}, Status={alerts_now[0].status}"
        )

        # 5. Elapsed +300s: critical attendance threshold reached (5m critical)
        t_300 = t0 + timedelta(seconds=300)
        print(
            f"\n[Step 5] Evaluating rules at +300s ({t_300.strftime('%H:%M:%S')}) -- Critical Threshold"
        )
        res_300 = await RulesEngine.evaluate_session(session_obj, db, reference_time=t_300)
        print(f"  Alerts escalated: {res_300['actions']['escalated']}")
        alerts_esc = (
            (await db.execute(select(Alert).where(Alert.session_id == session_id))).scalars().all()
        )
        print(f"  Alert count in DB: {len(alerts_esc)} (Deduplicated, NOT duplicated!)")
        print(f"  Escalated alert severity: {alerts_esc[0].severity}")

        # 6. Waiter confirms attendance at +315s
        t_att = t0 + timedelta(seconds=315)
        print(
            f"\n[Step 6] Waiter Lucia confirms table attendance at +315s ({t_att.strftime('%H:%M:%S')})"
        )
        ev_att, _ = await EventDomainService.record_event(
            db,
            ServiceEventCreate(
                table_id="tbl_demo_01",
                session_id=session_id,
                event_type=EventType.ATTENDANCE,
                event_timestamp=t_att,
                source=EventSource.WAITER_UI,
                created_by="user_waiter_lucia",
                verification_status=VerificationStatus.CONFIRMED,
            ),
        )
        # Check auto-resolution of alert
        alert_att = (
            (await db.execute(select(Alert).where(Alert.session_id == session_id)))
            .scalars()
            .first()
        )
        print(f"  Attendance alert status: {alert_att.status}")
        print(f"  Resolution reason: {alert_att.metadata_json.get('resolution_reason')}")

        # 7. Food delivery delay at +950s (threshold is 900s)
        t_950 = t0 + timedelta(seconds=950)
        print(f"\n[Step 7] Evaluating food delivery at +950s ({t_950.strftime('%H:%M:%S')})...")
        await db.refresh(session_obj)
        res_food = await RulesEngine.evaluate_session(session_obj, db, reference_time=t_950)
        print(f"  Alerts created: {res_food['actions']['created']}")

        # 8. Food delivery confirmed at +980s
        t_food = t0 + timedelta(seconds=980)
        print(f"\n[Step 8] Food delivered at +980s ({t_food.strftime('%H:%M:%S')})")
        await EventDomainService.record_event(
            db,
            ServiceEventCreate(
                table_id="tbl_demo_01",
                session_id=session_id,
                event_type=EventType.FOOD_DELIVERY,
                event_timestamp=t_food,
                source=EventSource.WAITER_UI,
                verification_status=VerificationStatus.CONFIRMED,
            ),
        )
        food_alert = (
            await db.execute(
                select(Alert).where(
                    Alert.session_id == session_id,
                    Alert.alert_type == "FOOD_DELIVERY_OVERDUE",
                )
            )
        ).scalar_one()
        print(f"  Food alert status: {food_alert.status}")
        print(f"  Resolution reason: {food_alert.metadata_json.get('resolution_reason')}")

        # 9. Manager corrects attendance event (typo: actual arrival was at +150s instead of +315s)
        t_actual_att = t0 + timedelta(seconds=150)
        print(
            f"\n[Step 9] Manager corrects attendance timestamp to {t_actual_att.strftime('%H:%M:%S')} (Event Correction)"
        )
        await EventDomainService.correct_event(
            db,
            ev_att.event_id,
            EventCorrectionRequest(
                reason="Correcting attendance timestamp after manager timeline audit",
                corrected_by="manager_admin",
                new_timestamp=t_actual_att,
            ),
        )
        print(
            "  [OK] Event corrected: original preserved as CORRECTED, superseding event linked, audit log written."
        )

        # 10. Departure event at +3600s
        t_end = t0 + timedelta(seconds=3600)
        print(f"\n[Step 10] Customers depart at +3600s ({t_end.strftime('%H:%M:%S')})")
        await EventDomainService.end_table_session(db, session_id=session_id, ended_at=t_end)

        # 11. Final Session Metrics Summary
        await db.refresh(session_obj)
        metrics = SessionTimersCalculator.calculate_metrics(
            session_id=session_id,
            table_id="tbl_demo_01",
            started_at=session_obj.started_at,
            ended_at=session_obj.ended_at,
            first_attendance_at=session_obj.first_attendance_at,
            first_food_delivery_at=session_obj.first_food_delivery_at,
        )

        print("\n" + "=" * 78)
        print("  FINAL CALCULATED SESSION METRICS (RULES.md Section 8.2)")
        print("=" * 78)
        print(f"  Session ID:              {metrics.session_id}")
        print("  Table:                   T-04")
        print(f"  Seated at:               {metrics.started_at.strftime('%H:%M:%S UTC')}")
        print(
            f"  First Attendance:        {metrics.first_attendance_at.strftime('%H:%M:%S UTC')} (Corrected)"
        )
        print(
            f"  First Food Delivery:     {metrics.first_food_delivery_at.strftime('%H:%M:%S UTC')}"
        )
        print(f"  Departed at:             {metrics.ended_at.strftime('%H:%M:%S UTC')}")
        print("-" * 78)
        print(
            f"  First-Response Time:     {metrics.first_response.duration_sec:.1f}s ({metrics.first_response.duration_sec / 60:.2f} min)"
        )
        print(
            f"  Food Delivery Time:      {metrics.food_delivery.duration_sec:.1f}s ({metrics.food_delivery.duration_sec / 60:.2f} min)"
        )
        print(
            f"  Attendance to Delivery:  {metrics.attendance_to_food.duration_sec:.1f}s ({metrics.attendance_to_food.duration_sec / 60:.2f} min)"
        )
        print(
            f"  Total Dining Duration:   {metrics.occupancy_duration.duration_sec:.1f}s ({metrics.occupancy_duration.duration_sec / 60:.1f} min)"
        )
        print(
            f"  Data Inconsistencies:    {metrics.has_inconsistencies} (Negative intervals: {metrics.first_response.is_negative})"
        )
        print("=" * 78)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_demo())
