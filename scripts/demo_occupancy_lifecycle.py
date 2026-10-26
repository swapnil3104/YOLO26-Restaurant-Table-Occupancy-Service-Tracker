"""Demonstration script for Restaurant Table Occupancy State Machine and Sessions (Phase 4).

Simulates deterministic lifecycle events conforming to RULES.md:
1. Transient passer-by rejected (no false seating).
2. Seating party confirmed (persistent window -> session created).
3. Temporary occlusion recovery (grace period preserves session).
4. Party departure confirmed (vacancy grace expires -> session closed -> cleaning required).
5. Staff cleaning reset (table returns to available).
6. Camera outage resilience (camera drop preserves session, does not falsely vacate).
7. Manager manual override with audit justification.
"""

import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure src is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2
import numpy as np

from smartserve.occupancy.manager import OccupancySessionManager
from smartserve.occupancy.schema import (
    ManagerOverrideRequest,
    OccupancyState,
)
from smartserve.tables.schema import (
    AssociationStatus,
    Point,
    TableConfig,
    TablePolygon,
    TrackAssociation,
)
from smartserve.vision.visualizer import draw_occupancy_state_overlay

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_occupancy_lifecycle")


def create_demo_tables() -> list[TableConfig]:
    """Create sample restaurant tables."""
    return [
        TableConfig(
            id="table-01",
            code="T-01",
            name="Table 1 - Window Booth",
            camera_id="CAM-01",
            capacity=2,
            section="Window",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.08, y=0.15),
                    Point(x=0.36, y=0.15),
                    Point(x=0.36, y=0.45),
                    Point(x=0.08, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-02",
            code="T-02",
            name="Table 2 - Center Booth",
            camera_id="CAM-01",
            capacity=4,
            section="Main Dining",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.64, y=0.15),
                    Point(x=0.92, y=0.15),
                    Point(x=0.92, y=0.45),
                    Point(x=0.64, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-03",
            code="T-03",
            name="Table 3 - Patio Table",
            camera_id="CAM-01",
            capacity=4,
            section="Patio",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.20, y=0.58),
                    Point(x=0.48, y=0.58),
                    Point(x=0.48, y=0.88),
                    Point(x=0.20, y=0.88),
                ]
            ),
        ),
    ]


def run_occupancy_lifecycle_demo(output_image_path: str = "demo_occupancy_lifecycle.png") -> None:
    """Run step-by-step chronological simulation of restaurant occupancy state machine."""
    logger.info("=" * 70)
    logger.info("SmartServe AI - Occupancy State Machine & Sessions Demo (Phase 4)")
    logger.info("=" * 70)

    # Clean up any leftover demo artifacts from previous run
    demo_sessions = Path("config/demo_sessions.json")
    demo_audit = Path("config/demo_audit.jsonl")
    if demo_sessions.exists():
        demo_sessions.unlink()
    if demo_audit.exists():
        demo_audit.unlink()

    tables = create_demo_tables()
    manager = OccupancySessionManager(
        sessions_path=str(demo_sessions),
        audit_path=str(demo_audit),
        persistence_threshold_sec=5.0,
        vacancy_grace_sec=15.0,  # Shortened to 15s for interactive demo
        stale_threshold_sec=30.0,
        require_cleaning_before_available=True,
    )
    for t in tables:
        manager.register_table(t.id)

    base_time = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    current_time = base_time

    def log_step(title: str, t_offset: float) -> None:
        logger.info(f"\n>>> [{current_time.strftime('%H:%M:%S')} (+{t_offset:04.1f}s)] {title}")

    # Step 1: Transient passer-by near T-01
    log_step("STEP 1: Transient person passes beside Table T-01 (track #101)", 0.0)
    passerby_assoc = [
        TrackAssociation(
            track_id=101,
            table_id="table-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.20, 0.30),
        )
    ]
    evts = manager.process_associations(passerby_assoc, current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )

    # Person leaves after 2 seconds (less than 5.0s persistence window)
    current_time += timedelta(seconds=2.0)
    log_step("STEP 1b: Person walked past without staying (2.0s elapsed < 5.0s window)", 2.0)
    evts = manager.process_associations([], current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )
    status = manager.get_table_status("table-01", current_time)
    logger.info(
        f"   -> Table T-01 State: {status.current_state.value} (Session created: {status.active_session is not None})"
    )

    # Step 2: Genuine customer party (2 guests) sits down at T-01
    current_time += timedelta(seconds=5.0)
    log_step("STEP 2: Two patrons sit down at Table T-01 (tracks #201, #202)", 7.0)
    seated_assoc = [
        TrackAssociation(
            track_id=201,
            table_id="table-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.18, 0.32),
        ),
        TrackAssociation(
            track_id=202,
            table_id="table-01",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.25, 0.35),
        ),
    ]
    manager.process_associations(seated_assoc, current_time)

    # 5.5 seconds pass: persistence threshold reached!
    current_time += timedelta(seconds=5.5)
    log_step("STEP 2b: Seating evidence persists for 5.5s >= 5.0s window", 12.5)
    evts = manager.process_associations(seated_assoc, current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )
    status = manager.get_table_status("table-01", current_time)
    session = status.active_session
    assert session is not None
    logger.info(
        f"   -> Session created: ID={session.session_id}, Start={session.start_time.strftime('%H:%M:%S')}, Count={session.estimated_customer_count}"
    )

    # Step 3: Occlusion tolerance (waiter steps in front or brief tracker loss)
    current_time += timedelta(seconds=10.0)
    log_step("STEP 3: Brief occlusion/tracking drop (3.0s)", 22.5)
    evts = manager.process_associations([], current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )

    current_time += timedelta(seconds=3.0)
    log_step("STEP 3b: Patrons re-detected within vacancy grace window", 25.5)
    evts = manager.process_associations(seated_assoc, current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )
    status = manager.get_table_status("table-01", current_time)
    logger.info(
        f"   -> Session preserved! Active: {status.active_session.is_active}, Duration so far: {status.active_session.calculate_duration(current_time):.1f}s"
    )

    # Meal in progress (patrons enjoying meal)
    current_time += timedelta(seconds=10.0)
    manager.process_associations(seated_assoc, current_time)
    current_time += timedelta(seconds=10.0)
    manager.process_associations(seated_assoc, current_time)

    # Step 4: Party departs T-01
    current_time += timedelta(seconds=5.0)
    log_step("STEP 4: Patrons finish meal and leave Table T-01", 50.5)
    evts = manager.process_associations([], current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )

    # Vacancy grace period expires (16.0s elapsed >= 15.0s grace)
    current_time += timedelta(seconds=16.0)
    log_step("STEP 4b: Vacancy grace period expires (16.0s >= 15.0s)", 101.5)
    evts = manager.process_associations([], current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )
    status = manager.get_table_status("table-01", current_time)
    logger.info(f"   -> State: {status.current_state.value}")

    # Check closed session
    history = manager.get_session_history(table_id="table-01")
    if history:
        closed = history[0]
        logger.info(
            f"   -> Completed Session: {closed.session_id}, Duration: {closed.occupancy_duration_sec:.1f}s, End: {closed.end_time.strftime('%H:%M:%S')}"
        )

    # Step 5: Waiter sanitizes and resets T-01
    current_time += timedelta(seconds=10.0)
    log_step("STEP 5: Waiter sanitizes table T-01 and marks ready", 111.5)
    clean_evt = manager.mark_table_cleaned(
        "table-01", actor="waiter_sarah", reason="Table wiped and sanitized", timestamp=current_time
    )
    logger.info(
        f"   -> Event: {clean_evt.table_id} {clean_evt.from_state.value} -> {clean_evt.to_state.value} by {clean_evt.actor}"
    )

    # Step 6: Customer party seated at T-02, then camera feed outage
    current_time += timedelta(seconds=5.0)
    log_step("STEP 6: Party of 3 seated at Table T-02; Camera feed drops!", 71.5)
    party_t2 = [
        TrackAssociation(
            track_id=301,
            table_id="table-02",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.70, 0.30),
        ),
        TrackAssociation(
            track_id=302,
            table_id="table-02",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.80, 0.32),
        ),
        TrackAssociation(
            track_id=303,
            table_id="table-02",
            status=AssociationStatus.ASSOCIATED,
            anchor_point=(0.85, 0.35),
        ),
    ]
    evts = manager.process_associations(party_t2, current_time)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )

    current_time += timedelta(seconds=6.0)
    evts = manager.process_associations(party_t2, current_time)  # Confirms occupancy (6.0s >= 5.0s)
    for e in evts:
        logger.info(
            f"   -> Event: {e.table_id} {e.from_state.value} -> {e.to_state.value} ({e.reason})"
        )

    # Camera failure: healthy = False
    current_time += timedelta(seconds=5.0)
    manager.process_associations([], current_time, camera_healthy=False)
    status_t2 = manager.get_table_status("table-02", current_time)
    logger.info(
        f"   -> Camera outage! T-02 State: {status_t2.current_state.value}, Is Stale: {status_t2.is_stale}, Session active: {status_t2.active_session.is_active}"
    )
    logger.info(
        "   -> (RULES.md 4.1 & 4.3 rule enforced: Missing frames do NOT mark tables vacant)"
    )

    # Step 7: Manager manual override on Table T-03
    log_step("STEP 7: Manager marks Table T-03 OUT_OF_SERVICE (Maintenance)", 137.5)
    override_evt = manager.override_table_state(
        "table-03",
        ManagerOverrideRequest(
            target_state=OccupancyState.OUT_OF_SERVICE,
            reason="Spilled drink, undergoing deep clean and carpet dry",
            actor="manager_john",
        ),
        timestamp=current_time,
    )
    logger.info(
        f"   -> Manager override: {override_evt.table_id} -> {override_evt.to_state.value} by {override_evt.actor}"
    )

    # Render visualization frame
    logger.info("\nGenerating demonstration visualization overlay frame...")
    frame = np.full((720, 1280, 3), (35, 38, 42), dtype=np.uint8)
    for y in range(0, 720, 40):
        cv2.line(frame, (0, y), (1280, y), (45, 48, 54), 1)
    for x in range(0, 1280, 40):
        cv2.line(frame, (x, 0), (x, 720), (45, 48, 54), 1)

    all_statuses = manager.get_all_statuses(current_time)
    rendered = draw_occupancy_state_overlay(
        frame=frame,
        tables=tables,
        occupancy_statuses=all_statuses,
        camera_id="CAM-01",
        fps=5.0,
    )

    cv2.imwrite(output_image_path, rendered)
    logger.info(f"Demonstration image successfully saved to {output_image_path}")
    logger.info("=" * 70)


if __name__ == "__main__":
    run_occupancy_lifecycle_demo()
