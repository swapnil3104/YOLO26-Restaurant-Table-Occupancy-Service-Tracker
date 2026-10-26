#!/usr/bin/env python3
"""Database management, seeding, backup, and restore CLI tool for SmartServe AI.

Follows Docs/TASKS.md Phase 5 and Docs/RULES.md Section 15.
"""

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure src is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from smartserve.database.base import utc_now
from smartserve.database.models import (
    Alert,
    AuditLog,
    Camera,
    DetectionEvent,
    Floor,
    KpiSnapshot,
    Restaurant,
    ServiceEvent,
    Table,
    TableSession,
    TrackingJob,
    User,
)
from smartserve.database.session import (
    SyncSessionLocal,
    get_sync_database_url,
)


def seed_database(restaurant_id: str = "rest_bistro_01") -> None:
    """Seed initial development restaurant, tables, cameras, and staff users."""
    print("[*] Seeding database...")
    with SyncSessionLocal() as db:
        # Check if restaurant exists
        rest = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
        if not rest:
            rest = Restaurant(
                restaurant_id=restaurant_id,
                name="Bistro Lumiere",
                timezone="UTC",
                created_at=utc_now(),
            )
            db.add(rest)
            db.flush()
            print(f"  + Created Restaurant: {rest.name} ({rest.restaurant_id})")

        # Floors
        f1 = db.query(Floor).filter(Floor.floor_id == "floor-01").first()
        if not f1:
            f1 = Floor(
                floor_id="floor-01",
                restaurant_id=restaurant_id,
                floor_name="Floor 1",
                floor_number=1,
                is_active=True,
                created_at=utc_now(),
            )
            db.add(f1)
            print("  + Created Floor: Floor 1 (floor-01)")

        f2 = db.query(Floor).filter(Floor.floor_id == "floor-02").first()
        if not f2:
            f2 = Floor(
                floor_id="floor-02",
                restaurant_id=restaurant_id,
                floor_name="Floor 2",
                floor_number=2,
                is_active=True,
                created_at=utc_now(),
            )
            db.add(f2)
            print("  + Created Floor: Floor 2 (floor-02)")
        db.flush()

        # Camera
        cam = db.query(Camera).filter(Camera.camera_id == "CAM-01").first()
        if not cam:
            cam = Camera(
                camera_id="CAM-01",
                restaurant_id=restaurant_id,
                floor_id="floor-01",
                floor_name="Floor 1",
                section="Main Dining",
                name="Main Dining Room Overhead",
                source_type="WEBCAM",
                source_mode="tracking",
                status="CONNECTED",
                created_at=utc_now(),
            )
            db.add(cam)
            print("  + Created Camera: CAM-01")

        # Staff Users
        users_to_seed = [
            ("usr_admin", "admin", "Alex Administrator", "ADMIN"),
            ("usr_mgr", "manager", "Morgan Manager", "MANAGER"),
            ("usr_waiter1", "waiter1", "Sam Waiter", "WAITER"),
            ("usr_waiter2", "waiter2", "Taylor Waiter", "WAITER"),
        ]
        for uid, uname, dname, role in users_to_seed:
            existing_user = db.query(User).filter(User.username == uname).first()
            if not existing_user:
                u = User(
                    user_id=uid,
                    restaurant_id=restaurant_id,
                    username=uname,
                    display_name=dname,
                    role=role,
                    active=True,
                    created_at=utc_now(),
                )
                db.add(u)
                print(f"  + Created User: {uname} ({role})")

        # Tables (Load from config/tables.json if exists)
        tables_cfg_path = Path("config/tables.json")
        table_configs = []
        if tables_cfg_path.exists():
            try:
                with open(tables_cfg_path, encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    if isinstance(cfg_data, dict):
                        table_configs = cfg_data.get("tables", [])
                    elif isinstance(cfg_data, list):
                        table_configs = cfg_data
            except Exception as e:
                print(f"  ! Warning: could not parse tables.json: {e}")

        if not table_configs:
            # Fallback default layout
            table_configs = [
                {
                    "id": "table-01",
                    "code": "T-01",
                    "capacity": 2,
                    "polygon": [[0.08, 0.18], [0.33, 0.18], [0.33, 0.55], [0.08, 0.55]],
                },
                {
                    "id": "table-02",
                    "code": "T-02",
                    "capacity": 2,
                    "polygon": [[0.35, 0.12], [0.58, 0.12], [0.58, 0.48], [0.35, 0.48]],
                },
                {
                    "id": "table-03",
                    "code": "T-03",
                    "capacity": 4,
                    "polygon": [[0.45, 0.3], [0.98, 0.3], [0.98, 0.92], [0.45, 0.92]],
                },
            ]

        for t_info in table_configs:
            tid = t_info.get("id") or t_info.get("table_id")
            tcode = t_info.get("code") or t_info.get("table_code") or str(tid).upper()
            existing_table = db.query(Table).filter(Table.table_id == tid).first()
            if not existing_table:
                tbl = Table(
                    table_id=tid,
                    restaurant_id=restaurant_id,
                    table_code=tcode,
                    capacity=t_info.get("capacity", 4),
                    camera_id="CAM-01",
                    region_config=t_info,
                    status="AVAILABLE",
                    created_at=utc_now(),
                )
                db.add(tbl)
                print(f"  + Created Table: {tbl.table_code} ({tbl.table_id})")

        db.commit()
    print("[SUCCESS] Database seeding complete.")


def backup_database(dest_dir: str = "backups") -> str:
    """Create a timestamped backup copy of SQLite database file."""
    db_url = get_sync_database_url()
    if not db_url.startswith("sqlite:///"):
        print(f"Backup is currently configured for SQLite files. Active DB: {db_url}")
        return ""

    db_path = Path(db_url.replace("sqlite:///", ""))
    if not db_path.exists():
        print(f"[ERROR] Database file {db_path} does not exist to backup.")
        return ""

    backup_folder = Path(dest_dir)
    backup_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{db_path.stem}_{timestamp}.db"
    backup_path = backup_folder / backup_filename

    shutil.copy2(db_path, backup_path)
    print(
        f"[BACKUP] Backup created successfully: {backup_path} ({backup_path.stat().st_size} bytes)"
    )
    return str(backup_path)


def restore_database(backup_file: str) -> bool:
    """Restore SQLite database from a specified backup file."""
    src = Path(backup_file)
    if not src.exists():
        print(f"[ERROR] Backup file not found: {src}")
        return False

    db_url = get_sync_database_url()
    if not db_url.startswith("sqlite:///"):
        print(f"Restore is currently configured for SQLite files. Active DB: {db_url}")
        return False

    target_db = Path(db_url.replace("sqlite:///", ""))

    # Take a safety backup of existing db first
    if target_db.exists():
        safety_path = target_db.with_suffix(
            f".pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        shutil.copy2(target_db, safety_path)
        print(f"  [INFO] Created safety pre-restore backup: {safety_path}")

    shutil.copy2(src, target_db)
    print(f"[SUCCESS] Successfully restored database from {src} to {target_db}")
    return True


def status_database() -> None:
    """Print database statistics and table record counts."""
    from sqlalchemy import func

    from smartserve.database.models import (
        Camera,
        Restaurant,
        Table,
        User,
    )

    print(f"[STATUS] Database Status ({get_sync_database_url()}):")
    with SyncSessionLocal() as db:
        models = [
            ("Restaurants", Restaurant),
            ("Floors", Floor),
            ("Cameras", Camera),
            ("TrackingJobs", TrackingJob),
            ("DetectionEvents", DetectionEvent),
            ("KpiSnapshots", KpiSnapshot),
            ("Users", User),
            ("Tables", Table),
            ("TableSessions", TableSession),
            ("ServiceEvents", ServiceEvent),
            ("Alerts", Alert),
            ("AuditLogs", AuditLog),
        ]
        for label, model in models:
            cnt = db.query(func.count()).select_from(model).scalar()
            print(f"  - {label:17}: {cnt} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartServe Database Management Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Seed
    subparsers.add_parser("seed", help="Seed initial development entities")

    # Backup
    backup_parser = subparsers.add_parser("backup", help="Backup SQLite database to directory")
    backup_parser.add_argument("--dir", default="backups", help="Target backup folder")

    # Restore
    restore_parser = subparsers.add_parser("restore", help="Restore database from snapshot")
    restore_parser.add_argument("--file", required=True, help="Backup file path to restore from")

    # Status
    subparsers.add_parser("status", help="Show database record counts")

    args = parser.parse_args()

    if args.command == "seed":
        seed_database()
    elif args.command == "backup":
        backup_database(dest_dir=args.dir)
    elif args.command == "restore":
        restore_database(args.file)
    elif args.command == "status":
        status_database()


if __name__ == "__main__":
    main()
