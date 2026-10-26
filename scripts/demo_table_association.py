"""Demonstration script for Restaurant Table Layout and Spatial Association (Phase 3).

Simulates patrons seated at tables, patrons walking along central aisles, ambiguous
patrons on table boundaries, and capacity limits. Also supports running on live video files
or CCTV streams (such as restaurant footage).
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure src is discoverable when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2
import numpy as np

from smartserve.tables.associator import SpatialTableAssociator
from smartserve.tables.manager import TableLayoutManager
from smartserve.tables.schema import Point, TableConfig, TablePolygon
from smartserve.vision.capture import VideoCapturePipeline
from smartserve.vision.detector import YOLO26Detector
from smartserve.vision.interfaces import BoundingBox, Detection
from smartserve.vision.tracker import SimpleByteTracker
from smartserve.vision.visualizer import draw_spatial_association_overlay

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_table_association")


def create_synthetic_restaurant_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    """Create a stylized floor background frame simulating restaurant ambient lighting."""
    frame = np.full((height, width, 3), (35, 38, 42), dtype=np.uint8)

    # Draw floor tile grid lines for perspective
    for y in range(0, height, 40):
        cv2.line(frame, (0, y), (width, y), (45, 48, 54), 1)
    for x in range(0, width, 40):
        cv2.line(frame, (x, 0), (x, height), (45, 48, 54), 1)

    # Central walkway aisle marking
    aisle_x1 = int(width * 0.42)
    aisle_x2 = int(width * 0.56)
    cv2.rectangle(frame, (aisle_x1, 0), (aisle_x2, height), (40, 44, 50), -1)

    return frame


def run_synthetic_association_demo(output_image_path: str = "demo_table_association.png") -> None:
    """Run the synthetic Table Layout and Spatial Association demonstration."""
    logger.info("Initializing synthetic Restaurant Table Layout...")

    tables = [
        TableConfig(
            id="table-01",
            code="T-01",
            name="Table 1 - Window Booth",
            camera_id="CAM-01",
            capacity=2,
            section="Window Section",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.08, y=0.15),
                    Point(x=0.38, y=0.15),
                    Point(x=0.38, y=0.45),
                    Point(x=0.08, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-02",
            code="T-02",
            name="Table 2 - Center High-top",
            camera_id="CAM-01",
            capacity=4,
            section="Main Dining",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.60, y=0.15),
                    Point(x=0.90, y=0.15),
                    Point(x=0.90, y=0.45),
                    Point(x=0.60, y=0.45),
                ]
            ),
        ),
        TableConfig(
            id="table-03",
            code="T-03",
            name="Table 3 - Family Banquette",
            camera_id="CAM-01",
            capacity=2,
            section="Main Dining",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.08, y=0.55),
                    Point(x=0.38, y=0.55),
                    Point(x=0.38, y=0.88),
                    Point(x=0.08, y=0.88),
                ]
            ),
        ),
        TableConfig(
            id="table-04",
            code="T-04",
            name="Table 4 - Patio Entry (Adjacent)",
            camera_id="CAM-01",
            capacity=4,
            section="Patio",
            polygon=TablePolygon(
                vertices=[
                    Point(x=0.39, y=0.55),
                    Point(x=0.70, y=0.55),
                    Point(x=0.70, y=0.88),
                    Point(x=0.39, y=0.88),
                ]
            ),
        ),
    ]

    associator = SpatialTableAssociator(ambiguity_margin=0.02)

    detections = [
        Detection(
            class_name="person",
            confidence=0.92,
            track_id=1,
            bbox=BoundingBox(x1=0.15, y1=0.20, x2=0.25, y2=0.38),
        ),
        Detection(
            class_name="person",
            confidence=0.89,
            track_id=2,
            bbox=BoundingBox(x1=0.65, y1=0.20, x2=0.75, y2=0.38),
        ),
        Detection(
            class_name="person",
            confidence=0.87,
            track_id=3,
            bbox=BoundingBox(x1=0.76, y1=0.20, x2=0.86, y2=0.38),
        ),
        Detection(
            class_name="person",
            confidence=0.91,
            track_id=4,
            bbox=BoundingBox(x1=0.10, y1=0.60, x2=0.18, y2=0.78),
        ),
        Detection(
            class_name="person",
            confidence=0.88,
            track_id=5,
            bbox=BoundingBox(x1=0.20, y1=0.60, x2=0.28, y2=0.78),
        ),
        Detection(
            class_name="person",
            confidence=0.85,
            track_id=6,
            bbox=BoundingBox(x1=0.29, y1=0.60, x2=0.36, y2=0.78),
        ),
        Detection(
            class_name="person",
            confidence=0.94,
            track_id=7,
            bbox=BoundingBox(x1=0.45, y1=0.25, x2=0.52, y2=0.48),
        ),
        Detection(
            class_name="person",
            confidence=0.86,
            track_id=8,
            bbox=BoundingBox(x1=0.34, y1=0.65, x2=0.43, y2=0.75),
        ),
    ]

    logger.info(f"Running spatial association on {len(detections)} simulated patrons...")
    result = associator.associate_frame(detections, tables, camera_id="CAM-01")

    _print_association_report(result, tables)

    frame = create_synthetic_restaurant_frame()
    rendered = draw_spatial_association_overlay(
        frame=frame,
        tables=tables,
        association_result=result,
        fps=5.0,
        camera_id="CAM-01",
    )

    out_file = Path(output_image_path)
    cv2.imwrite(str(out_file), rendered)
    logger.info(f"Rendered visualization saved to {out_file.resolve()}")


def run_video_table_association(
    source: str,
    output_path: str = "output_annotated_cctv.mp4",
    model_path: str = "yolo11s.pt",
    max_frames: int | None = None,
    camera_id: str = "CAM-01",
) -> None:
    """Run table association on a video file using configured tables and YOLO tracking."""
    logger.info(f"Loading table layout for camera '{camera_id}'...")
    layout_mgr = TableLayoutManager()
    tables = layout_mgr.list_tables(camera_id=camera_id)
    logger.info(f"Loaded {len(tables)} configured tables: {[t.code for t in tables]}")

    logger.info(f"Opening video source: {source}")
    pipeline = VideoCapturePipeline(source=source, camera_id=camera_id, sample_rate_hz=None)
    with pipeline:
        detector = YOLO26Detector(model_path=model_path, confidence_threshold=0.35)
        tracker = SimpleByteTracker(track_buffer=30)
        associator = SpatialTableAssociator(ambiguity_margin=0.02)

        out_writer = None
        frame_idx = 0
        occupancy_history: dict[str, list[int]] = {t.id: [] for t in tables}

        for packet in pipeline.stream_frames():
            frame_idx += 1
            if max_frames and frame_idx > max_frames:
                break

            detections = detector.detect(packet.frame)
            tracked = tracker.update(detections, packet.frame)
            assoc_result = associator.associate_frame(
                tracked, tables, camera_id=camera_id, timestamp=packet.timestamp
            )

            for t in tables:
                occupancy_history[t.id].append(assoc_result.table_counts.get(t.id, 0))

            annotated = draw_spatial_association_overlay(
                frame=packet.frame,
                tables=tables,
                association_result=assoc_result,
                fps=packet.fps or 30.0,
                camera_id=camera_id,
            )

            if out_writer is None and output_path:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_writer = cv2.VideoWriter(output_path, fourcc, packet.fps or 30.0, (w, h))

            if out_writer:
                out_writer.write(annotated)

            if frame_idx % 50 == 0:
                print(f"Frame {frame_idx}: Seated = {assoc_result.table_counts}")

        if out_writer:
            out_writer.release()
            logger.info(f"Annotated video saved to: {Path(output_path).resolve()}")

    print("\n" + "=" * 60)
    print("VIDEO TABLE OCCUPANCY SUMMARY")
    print("=" * 60)
    print(f"Source:         {source}")
    print(f"Total Frames:   {frame_idx}")
    for t in tables:
        counts = occupancy_history.get(t.id, [])
        mean_c = np.mean(counts) if counts else 0.0
        max_c = np.max(counts) if counts else 0
        print(
            f"  • {t.code} ({t.name}): Avg Guests={mean_c:.2f}, Peak={max_c}, Capacity={t.capacity}"
        )
    print("=" * 60 + "\n")


def _print_association_report(result, tables):
    """Format and print spatial association telemetry report."""
    print("\n" + "=" * 60)
    print("SMARTSERVE SPATIAL TABLE ASSOCIATION REPORT")
    print("=" * 60)
    print(f"Total Detections Evaluated: {result.total_detections}")
    print(f"Camera ID:                 {result.camera_id}")
    print("\nTable Occupancy Breakdown:")
    for table in tables:
        count = result.table_counts.get(table.id, 0)
        assocs = result.associated_tracks.get(table.id, [])
        track_ids = [f"#{a.track_id}" for a in assocs if a.track_id]
        print(
            f"  • {table.code} ({table.name}) [Capacity: {table.capacity}]: {count} patrons {track_ids}"
        )

    print("\nAmbiguous Detections (Unassigned to avoid false occupancy):")
    if result.ambiguous_tracks:
        for amb in result.ambiguous_tracks:
            print(
                f"  • Track #{amb.track_id}: Reason='{amb.reason}' Competing={amb.competing_tables}"
            )
    else:
        print("  • None")

    print("\nUnassigned Detections (Passers-by / Aisle):")
    if result.unassigned_tracks:
        for un in result.unassigned_tracks:
            print(
                f"  • Track #{un.track_id}: Anchor=({un.anchor_point[0]:.2f}, {un.anchor_point[1]:.2f})"
            )
    else:
        print("  • None")

    if result.capacity_warnings:
        print("\nCapacity Alerts:")
        for warn in result.capacity_warnings:
            print(f"  [!] {warn}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SmartServe Phase 3 Table Layout & Association Demo"
    )
    parser.add_argument("--source", type=str, default=None, help="Video file or RTSP stream path")
    parser.add_argument("--output", type=str, default=None, help="Output image or video path")
    parser.add_argument("--model", type=str, default="yolo11s.pt", help="YOLO model weights path")
    parser.add_argument("--frames", type=int, default=None, help="Max frames to process")
    parser.add_argument("--camera-id", type=str, default="CAM-01", help="Camera identifier")
    args = parser.parse_args()

    if args.source:
        out = args.output or "output_annotated_cctv.mp4"
        run_video_table_association(
            source=args.source,
            output_path=out,
            model_path=args.model,
            max_frames=args.frames,
            camera_id=args.camera_id,
        )
    else:
        out = args.output or "demo_table_association.png"
        run_synthetic_association_demo(output_image_path=out)
