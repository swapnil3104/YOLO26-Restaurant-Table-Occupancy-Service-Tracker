#!/usr/bin/env python3
"""CLI utility to demonstrate and verify the multi-object tracking pipeline.

Can run with synthetic moving targets or real video files/streams.

Usage:
    # Run synthetic tracking demonstration
    python scripts/demo_tracking.py --synthetic --frames 50

    # Run on video file with SimpleByteTracker
    python scripts/demo_tracking.py --source path/to/video.mp4 --tracker byte

    # Run on video with native YOLO26Tracker (ByteTrack / BoT-SORT)
    python scripts/demo_tracking.py --source path/to/video.mp4 --tracker yolo --engine botsort
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# Ensure src is discoverable when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from smartserve.vision.capture import VideoCapturePipeline
from smartserve.vision.detector import MockDetector, YOLO26Detector
from smartserve.vision.interfaces import BoundingBox, Detection
from smartserve.vision.tracker import MockTracker, SimpleByteTracker, YOLO26Tracker
from smartserve.vision.visualizer import draw_tracking_overlay


def run_synthetic_demo(num_frames: int = 50, output_path: str | None = None) -> None:
    """Run tracking demonstration on synthetic frames with moving patrons."""
    print(f"Generating synthetic scenario with 2 moving diners across {num_frames} frames...")
    tracker = SimpleByteTracker(match_threshold=0.2, track_buffer=10, min_hits=1)

    width, height = 1280, 720
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, 5.0, (width, height))

    for frame_idx in range(num_frames):
        # Background frame
        frame = np.full((height, width, 3), 30, dtype=np.uint8)

        # Draw a simulated table region
        cv2.rectangle(frame, (500, 250), (780, 480), (60, 60, 60), -1)
        cv2.putText(frame, "TABLE 1", (580, 365), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (120, 120, 120), 2)

        # Patron A: walking from left to table (x: 0.1 -> 0.45)
        xA = min(0.45, 0.10 + frame_idx * 0.015)
        det_A = Detection(
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(xA, 0.35, xA + 0.10, 0.75),
        )

        # Patron B: standing at table, occluded briefly at frames 20..24
        detections = [det_A]
        if not (20 <= frame_idx <= 24):
            det_B = Detection(
                class_name="person",
                confidence=0.82 if frame_idx < 35 else 0.45,  # Dips confidence
                bbox=BoundingBox(0.55, 0.30, 0.65, 0.70),
            )
            detections.append(det_B)

        tracked_detections = tracker.update(detections, frame)
        trajectories = tracker.get_trajectories()

        # Render overlay
        annotated = draw_tracking_overlay(
            frame=frame,
            detections=tracked_detections,
            trajectories=trajectories,
            fps=5.0,
            camera_id="CAM-SYNTHETIC",
        )

        if writer:
            writer.write(annotated)

        track_summary = [f"ID#{d.track_id} ({d.confidence:.0%})" for d in tracked_detections]
        print(f"Frame {frame_idx:02d}: Active tracks [{', '.join(track_summary)}]")

    if writer:
        writer.release()
        print(f"Saved annotated demo video to {output_path}")

    print("Synthetic tracking demo completed successfully.")


def run_video_demo(
    source: str,
    tracker_type: str = "byte",
    engine: str = "bytetrack",
    model_path: str = "yolo26s.pt",
    max_frames: int = 100,
    output_path: str | None = None,
) -> None:
    """Run detection + tracking on a video source."""
    print(f"Opening video source '{source}' with tracker={tracker_type}...")
    pipeline = VideoCapturePipeline(source=source, sample_rate_hz=5.0)

    if tracker_type == "yolo":
        tracker = YOLO26Tracker(model_path=model_path, tracker_type=engine)
        detector = None  # YOLO26Tracker handles detection + tracking internally
    elif tracker_type == "mock":
        detector = MockDetector()
        tracker = MockTracker()
    else:
        detector = YOLO26Detector(model_path=model_path)
        tracker = SimpleByteTracker()

    writer = None
    frames_processed = 0

    with pipeline:
        for packet in pipeline.stream_frames():
            if frames_processed >= max_frames:
                break

            frame = packet.frame
            if detector is not None:
                raw_dets = detector.detect(frame)
                tracked_dets = tracker.update(raw_dets, frame)
            else:
                tracked_dets = tracker.update([], frame)

            trajectories = tracker.get_trajectories()

            annotated = draw_tracking_overlay(
                frame=frame,
                detections=tracked_dets,
                trajectories=trajectories,
                fps=packet.fps,
                camera_id=packet.camera_id,
            )

            if output_path and writer is None:
                h, w = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_path, fourcc, packet.fps or 5.0, (w, h))

            if writer:
                writer.write(annotated)

            frames_processed += 1
            print(f"Processed frame {packet.frame_index}: {len(tracked_dets)} people tracked.")

    if writer:
        writer.release()
        print(f"Output saved to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartServe Multi-Object Tracking Demo")
    parser.add_argument("--synthetic", action="store_true", help="Run synthetic simulation demo")
    parser.add_argument("--source", type=str, default=None, help="Video source (file or stream)")
    parser.add_argument(
        "--tracker",
        type=str,
        choices=["byte", "yolo", "mock"],
        default="byte",
        help="Tracker implementation",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["bytetrack", "botsort"],
        default="bytetrack",
        help="Tracking engine for YOLO tracker",
    )
    parser.add_argument("--model", type=str, default="yolo26s.pt", help="YOLO26 model path")
    parser.add_argument("--frames", type=int, default=50, help="Maximum frames to process")
    parser.add_argument("--output", type=str, default=None, help="Path to save annotated video")

    args = parser.parse_args()

    if args.synthetic or args.source is None:
        run_synthetic_demo(num_frames=args.frames, output_path=args.output)
    else:
        run_video_demo(
            source=args.source,
            tracker_type=args.tracker,
            engine=args.engine,
            model_path=args.model,
            max_frames=args.frames,
            output_path=args.output,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
