#!/usr/bin/env python3
"""CLI utility to benchmark vision inference latency and throughput.

Usage:
    python scripts/benchmark_vision.py --mock --frames 100
    python scripts/benchmark_vision.py --model yolo11n.pt --frames 30
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure src is discoverable when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from smartserve.vision.benchmark import benchmark_detector
from smartserve.vision.detector import MockDetector, YOLO26Detector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmartServe Vision Benchmarking Utility")
    parser.add_argument(
        "--model", type=str, default="yolo26s.pt", help="Path or name of YOLO26 model weights"
    )
    parser.add_argument("--frames", type=int, default=30, help="Number of benchmark frames")
    parser.add_argument("--warmup", type=int, default=5, help="Number of warmup iterations")
    parser.add_argument("--width", type=int, default=1280, help="Input frame width")
    parser.add_argument("--height", type=int, default=720, help="Input frame height")
    parser.add_argument("--device", type=str, default=None, help="Device ('cpu', 'cuda', etc.)")
    parser.add_argument(
        "--mock", action="store_true", help="Use MockDetector instead of real model"
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mock:
        print("Initializing MockDetector for baseline benchmark...")
        detector = MockDetector()
    else:
        print(
            f"Initializing YOLO26Detector (model={args.model}, device={args.device or 'auto'})..."
        )
        detector = YOLO26Detector(model_path=args.model, device=args.device)

    print(
        f"Running benchmark on {args.frames} frames ({args.width}x{args.height}) with {args.warmup} warmup frames..."
    )
    result = benchmark_detector(
        detector=detector,
        num_frames=args.frames,
        frame_shape=(args.height, args.width),
        warmup_frames=args.warmup,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("\n" + "=" * 50)
        print(result.to_markdown())
        print("=" * 50)
        print("Hardware:", result.hardware_info)
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
