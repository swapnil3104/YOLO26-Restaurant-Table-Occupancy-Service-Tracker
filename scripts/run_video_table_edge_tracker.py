#!/usr/bin/env python3
"""Run YOLO and Table Edge Detection on restaurant CCTV video streams.

Features:
- Runs object detection for persons and dining tables on video frames.
- Uses TableEdgeDetector to extract exact table perimeter edges, borders, and corner nodes.
- Tracks patrons with ByteTrack and measures exact pixel distance to nearest table edge.
- Highlights active table edges occupied by seated diners with glowing neon overlays.
- Outputs annotated video to 'Sample Video/output_annotated_cctv.mp4' (auto-streamed by web UI)
  and saves a high-res sample preview screenshot.

Usage:
    python scripts/run_video_table_edge_tracker.py
    python scripts/run_video_table_edge_tracker.py --source "Sample Video/sample video.mp4" --max-frames 150
    python scripts/run_video_table_edge_tracker.py --conf 0.25 --edge-threshold 35
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Prevent Windows libiomp5md duplicate runtime crash
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Ensure project src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import cv2
import numpy as np

from smartserve.tables.edge_detector import TableEdgeDetector
from smartserve.tables.manager import TableLayoutManager
from smartserve.vision.capture import VideoCapturePipeline
from smartserve.vision.interfaces import BoundingBox, Detection
from smartserve.vision.tracker import SimpleByteTracker
from smartserve.vision.visualizer import draw_table_edge_overlay

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("table_edge_tracker")


def run_table_edge_video_pipeline(
    source: str = "Sample Video/Cctv-Resturant-Demo.mp4",
    output_path: str = "Sample Video/output_annotated_cctv.mp4",
    model_path: str = "models/yolo26_restaurant_cctv.pt",
    conf_threshold: float = 0.25,
    max_frames: int | None = 200,
    camera_id: str = "CAM-01",
    edge_contact_threshold_px: float = 40.0,
    table_source: str = "yolo",
    preview_image_path: str = "table_edge_detection_preview.jpg",
) -> None:
    """Run table edge detection and diner tracking on a video stream."""
    from ultralytics import YOLO

    # Resolve paths
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if not source_path.exists():
        # Fallback to any available video in Sample Video directory
        sample_vids = list((PROJECT_ROOT / "Sample Video").glob("*.mp4"))
        if sample_vids:
            source_path = sample_vids[0]
            logger.info(f"Auto-selected video source: {source_path.name}")
        else:
            raise FileNotFoundError(f"Video source not found: {source_path}")

    # Resolve model
    resolved_model = Path(model_path)
    if not resolved_model.exists():
        cand = PROJECT_ROOT / model_path
        if cand.exists():
            resolved_model = cand
        else:
            resolved_model = PROJECT_ROOT / "yolo26s.pt"

    logger.info("=" * 60)
    logger.info("SMARTSERVE TABLE EDGE & DINER TRACKING PIPELINE")
    logger.info(f"Video Source:       {source_path}")
    logger.info(f"Model Weights:      {resolved_model}")
    logger.info(f"Confidence Thresh:  {conf_threshold}")
    logger.info(f"Edge Contact Dist:  {edge_contact_threshold_px} px")
    logger.info(f"Max Frames:         {max_frames or 'Full Video'}")
    logger.info("=" * 60)

    # Load YOLO model
    yolo_model = YOLO(str(resolved_model))

    # Also load generic yolo26s for dining table detection if fine-tuned model is person-only
    table_detector_model = YOLO(str(PROJECT_ROOT / "yolo26s.pt"))

    # Load configured table layout for camera
    layout_mgr = TableLayoutManager()
    configured_tables = layout_mgr.list_tables(camera_id=camera_id)
    logger.info(
        f"Loaded {len(configured_tables)} configured tables from layout manager: {[t.code for t in configured_tables]}"
    )

    edge_detector = TableEdgeDetector(edge_contact_threshold_px=edge_contact_threshold_px)
    tracker = SimpleByteTracker(track_buffer=30)

    pipeline = VideoCapturePipeline(
        source=str(source_path), camera_id=camera_id, sample_rate_hz=None
    )

    out_writer = None
    frame_idx = 0
    total_seated_history = []
    total_tables_history = []

    with pipeline:
        for packet in pipeline.stream_frames():
            frame_idx += 1
            if max_frames and frame_idx > max_frames:
                break

            frame = packet.frame
            h, w = frame.shape[:2]

            # 1. Run Person Detection & Tracking
            person_res = yolo_model.predict(
                frame, conf=conf_threshold, classes=[0], imgsz=640, verbose=False
            )[0]
            person_detections: list[Detection] = []
            if person_res.boxes is not None and len(person_res.boxes) > 0:
                for b in person_res.boxes:
                    xyxy = b.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = xyxy[:4]
                    conf = float(b.conf[0].item())

                    # Normalize bbox
                    norm_bbox = BoundingBox(
                        x1=max(0.0, min(1.0, float(x1) / w)),
                        y1=max(0.0, min(1.0, float(y1) / h)),
                        x2=max(0.0, min(1.0, float(x2) / w)),
                        y2=max(0.0, min(1.0, float(y2) / h)),
                        is_normalized=True,
                    )
                    person_detections.append(
                        Detection(class_name="person", confidence=conf, bbox=norm_bbox)
                    )

            tracked_persons = tracker.update(person_detections, frame)

            # 2. Extract Table Edges based on table_source mode
            table_detections = []
            if table_source in ("layout", "all"):
                table_detections.extend(
                    edge_detector.get_configured_tables_edges(configured_tables, w, h)
                )

            # Auto-detect dining tables directly from video using YOLO (class 60)
            if table_source in ("yolo", "all"):
                table_res = table_detector_model.predict(
                    frame, conf=0.18, classes=[60], imgsz=640, verbose=False
                )[0]
                if table_res.boxes is not None and len(table_res.boxes) > 0:
                    for idx, tb in enumerate(table_res.boxes):
                        t_xyxy = [int(v) for v in tb.xyxy[0].cpu().numpy()[:4]]
                        t_conf = float(tb.conf[0].item())
                        detected_table_edge = edge_detector.detect_table_edges_from_bbox(
                            frame=frame,
                            bbox=tuple(t_xyxy),
                            table_id=f"table-{idx + 1:02d}",
                            label=f"Table {idx + 1}",
                            confidence=t_conf,
                        )
                        table_detections.append(detected_table_edge)

            # 4. Associate patrons to table edges
            patron_contacts = edge_detector.associate_patrons_to_table_edges(
                patrons=tracked_persons,
                table_detections=table_detections,
                frame_width=w,
                frame_height=h,
            )

            seated_count = sum(1 for p in patron_contacts if p.status == "SEATED_AT_EDGE")
            total_seated_history.append(seated_count)
            total_tables_history.append(len(table_detections))

            # 5. Render Table Edge Computer Vision Overlay
            annotated_frame = draw_table_edge_overlay(
                frame=frame,
                table_detections=table_detections,
                patron_contacts=patron_contacts,
                fps=packet.fps or 25.0,
                camera_id=camera_id,
                show_edge_measurements=True,
            )

            # Save preview screenshot of first few frames
            if frame_idx == 10 or (frame_idx == 1 and not Path(preview_image_path).exists()):
                cv2.imwrite(
                    preview_image_path, annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                )
                logger.info(
                    f"Saved live preview screenshot to: {Path(preview_image_path).resolve()}"
                )

            # 6. Initialize video writer if needed
            if out_writer is None and output_path:
                dest_video = Path(output_path)
                if not dest_video.is_absolute():
                    dest_video = PROJECT_ROOT / dest_video
                dest_video.parent.mkdir(parents=True, exist_ok=True)

                out_h, out_w = annotated_frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_writer = cv2.VideoWriter(
                    str(dest_video), fourcc, packet.fps or 25.0, (out_w, out_h)
                )
                logger.info(f"Writing annotated video to: {dest_video.resolve()}")

            if out_writer:
                out_writer.write(annotated_frame)

            if frame_idx % 30 == 0:
                logger.info(
                    f"Frame {frame_idx:04d}: Tables={len(table_detections)} | "
                    f"Seated at Table Edge={seated_count} | Total Patrons={len(patron_contacts)}"
                )

    if out_writer:
        out_writer.release()
        logger.info(f"[SUCCESS] Video rendering complete! Saved to {Path(output_path).resolve()}")

    print("\n" + "=" * 60)
    print("VIDEO TABLE EDGE TRACKING SUMMARY")
    print("=" * 60)
    print(f"Total Frames Processed: {frame_idx}")
    print(f"Average Tables Tracked: {np.mean(total_tables_history):.1f}")
    print(f"Average Seated Guests:  {np.mean(total_seated_history):.1f}")
    print(f"Peak Seated at Edges:   {np.max(total_seated_history) if total_seated_history else 0}")
    print(f"Output Video File:      {Path(output_path).resolve()}")
    print(f"Preview Screenshot:     {Path(preview_image_path).resolve()}")
    print("=" * 60 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run YOLO and Table Edge Detection on Video")
    parser.add_argument(
        "--source",
        type=str,
        default="Sample Video/Cctv-Resturant-Demo.mp4",
        help="Path to video file or RTSP stream",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="Sample Video/output_annotated_cctv.mp4",
        help="Output annotated video path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="models/yolo26_restaurant_cctv.pt",
        help="Path to fine-tuned person weights",
    )
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument(
        "--max-frames", type=int, default=150, help="Max frames to process (None for full video)"
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=40.0,
        help="Pixel distance threshold for table edge contact",
    )
    parser.add_argument(
        "--table-source",
        type=str,
        default="yolo",
        choices=["yolo", "layout", "all"],
        help="Source for tables: 'yolo' (auto-detect), 'layout' (tables.json), or 'all'",
    )
    parser.add_argument("--camera-id", type=str, default="CAM-01", help="Camera identifier")
    args = parser.parse_args()

    try:
        run_table_edge_video_pipeline(
            source=args.source,
            output_path=args.output,
            model_path=args.model,
            conf_threshold=args.conf,
            max_frames=args.max_frames,
            camera_id=args.camera_id,
            edge_contact_threshold_px=args.edge_threshold,
            table_source=args.table_source,
        )
        return 0
    except Exception as exc:
        logger.error(f"Table edge video tracking failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
