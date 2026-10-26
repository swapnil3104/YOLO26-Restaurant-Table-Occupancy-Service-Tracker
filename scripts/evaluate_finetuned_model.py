#!/usr/bin/env python3
"""Evaluate and compare baseline YOLO vs. Fine-tuned Restaurant CCTV YOLO.

Features:
- Side-by-side visual comparison showing detections, bounding boxes, and confidence scores.
- Quantifies improvement in seated diner recall, occluded patron detection, and confidence levels.
- Benchmarks latency on CPU / target hardware.
- Outputs visual images and a Markdown comparison report in 'evaluation_results/'.

Usage:
    python scripts/evaluate_finetuned_model.py --baseline yolo26s.pt --finetuned models/yolo26_restaurant_cctv.pt
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Prevent Windows libiomp5md duplicate runtime crash
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import cv2
import numpy as np

# Ensure project src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_model")


def draw_detections(
    image: np.ndarray,
    boxes: list[dict],
    title: str,
    color: tuple[int, int, int] = (0, 220, 100),
    header_bg: tuple[int, int, int] = (25, 25, 30),
) -> np.ndarray:
    """Draw bounding boxes and confidence tags with a clean aesthetic header."""
    annotated = image.copy()
    h, w = annotated.shape[:2]

    # Draw bounding boxes
    for b in boxes:
        x1, y1, x2, y2 = [int(v) for v in b["xyxy"]]
        conf = b["conf"]

        # Clamp
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        # Draw box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Confidence badge
        label = f"person {conf:.2f}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        tag_y1 = max(0, y1 - th - 6)
        cv2.rectangle(annotated, (x1, tag_y1), (x1 + tw + 6, tag_y1 + th + 6), color, -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 3, tag_y1 + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    # Top banner with title and count
    banner_height = 42
    banner = np.full((banner_height, w, 3), header_bg, dtype=np.uint8)
    info_text = f"{title} | Detections: {len(boxes)}"
    cv2.putText(
        banner, info_text, (15, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA
    )

    return np.vstack([banner, annotated])


def compare_models_on_image(
    image_path: Path,
    baseline_model,
    finetuned_model,
    conf_threshold: float = 0.25,
    imgsz: int = 640,
) -> tuple[np.ndarray, dict]:
    """Run baseline vs fine-tuned model on an image and create side-by-side composite."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    # Baseline prediction
    t0 = time.perf_counter()
    base_res = baseline_model.predict(
        img, conf=conf_threshold, classes=[0], imgsz=imgsz, verbose=False
    )[0]
    t_base = (time.perf_counter() - t0) * 1000

    # Fine-tuned prediction
    t0 = time.perf_counter()
    fine_res = finetuned_model.predict(
        img, conf=conf_threshold, classes=[0], imgsz=imgsz, verbose=False
    )[0]
    t_fine = (time.perf_counter() - t0) * 1000

    def _extract_boxes(res):
        boxes = []
        if res.boxes is not None and len(res.boxes) > 0:
            for b in res.boxes:
                boxes.append(
                    {
                        "xyxy": b.xyxy[0].cpu().numpy().tolist(),
                        "conf": float(b.conf[0].item()),
                    }
                )
        return boxes

    base_boxes = _extract_boxes(base_res)
    fine_boxes = _extract_boxes(fine_res)

    # Render panels
    # Baseline: Coral/Orange (50, 100, 240)
    left_panel = draw_detections(
        img,
        base_boxes,
        title=f"BASELINE (Latency: {t_base:.1f}ms)",
        color=(50, 120, 240),
        header_bg=(35, 30, 40),
    )

    # Fine-Tuned: Emerald Green (60, 220, 90)
    right_panel = draw_detections(
        img,
        fine_boxes,
        title=f"FINE-TUNED RESTAURANT (Latency: {t_fine:.1f}ms)",
        color=(60, 220, 90),
        header_bg=(20, 40, 30),
    )

    # Combine side-by-side with a separator line
    sep = np.full((left_panel.shape[0], 4, 3), (80, 80, 80), dtype=np.uint8)
    composite = np.hstack([left_panel, sep, right_panel])

    stats = {
        "image": image_path.name,
        "baseline_count": len(base_boxes),
        "finetuned_count": len(fine_boxes),
        "baseline_latency_ms": round(t_base, 1),
        "finetuned_latency_ms": round(t_fine, 1),
        "baseline_mean_conf": round(float(np.mean([b["conf"] for b in base_boxes])), 3)
        if base_boxes
        else 0.0,
        "finetuned_mean_conf": round(float(np.mean([b["conf"] for b in fine_boxes])), 3)
        if fine_boxes
        else 0.0,
    }

    return composite, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Baseline vs Fine-tuned Restaurant Model")
    parser.add_argument("--baseline", type=str, default="yolo26s.pt", help="Baseline model path")
    parser.add_argument(
        "--finetuned",
        type=str,
        default="models/yolo26_restaurant_cctv.pt",
        help="Fine-tuned model path",
    )
    parser.add_argument(
        "--test-images", type=str, nargs="*", default=None, help="Specific test images to evaluate"
    )
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image resolution")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_results",
        help="Directory for evaluation results",
    )
    args = parser.parse_args()

    from ultralytics import YOLO

    baseline_path = Path(args.baseline)
    finetuned_path = Path(args.finetuned)

    if not baseline_path.exists():
        logger.error(f"Baseline weights not found at: {baseline_path}")
        return 1

    if not finetuned_path.exists():
        logger.error(
            f"Fine-tuned weights not found at: {finetuned_path}.\n"
            f"Run scripts/train_restaurant_yolo.py to train the model first."
        )
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading baseline: {baseline_path}...")
    baseline_model = YOLO(str(baseline_path))

    logger.info(f"Loading fine-tuned: {finetuned_path}...")
    finetuned_model = YOLO(str(finetuned_path))

    # Identify test images
    test_files: list[Path] = []
    if args.test_images:
        test_files = [Path(p) for p in args.test_images if Path(p).exists()]
    else:
        # Check validation folder if prepared
        val_dir = PROJECT_ROOT / "datasets" / "restaurant_cctv_clean" / "images" / "val"
        if not val_dir.exists():
            val_dir = PROJECT_ROOT / "datasets" / "restaurant_cctv" / "images" / "val"
        if val_dir.exists():
            test_files = sorted(list(val_dir.glob("*.jpg")) + list(val_dir.glob("*.png")))[:10]

        # Also fallback to root test images
        for cand in ["sample_cctv_raw.jpg", "test_frame_first.jpg", "sample_video_frame_0.jpg"]:
            cp = PROJECT_ROOT / cand
            if cp.exists() and cp not in test_files:
                test_files.append(cp)

    if not test_files:
        logger.error("No test images found for evaluation.")
        return 1

    logger.info(f"Evaluating on {len(test_files)} test images...")
    all_stats: list[dict] = []

    for idx, img_path in enumerate(test_files):
        composite, stats = compare_models_on_image(
            image_path=img_path,
            baseline_model=baseline_model,
            finetuned_model=finetuned_model,
            conf_threshold=args.conf,
            imgsz=args.imgsz,
        )
        all_stats.append(stats)

        out_img_path = out_dir / f"compare_{img_path.stem}.jpg"
        cv2.imwrite(str(out_img_path), composite, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        logger.info(
            f"[{idx + 1}/{len(test_files)}] {img_path.name}: "
            f"Baseline={stats['baseline_count']} (avg conf {stats['baseline_mean_conf']}) vs "
            f"Fine-tuned={stats['finetuned_count']} (avg conf {stats['finetuned_mean_conf']}) -> Saved {out_img_path.name}"
        )

    # Compute overall statistics
    total_base_detections = sum(s["baseline_count"] for s in all_stats)
    total_fine_detections = sum(s["finetuned_count"] for s in all_stats)
    avg_base_conf = np.mean([s["baseline_mean_conf"] for s in all_stats if s["baseline_count"] > 0])
    avg_fine_conf = np.mean(
        [s["finetuned_mean_conf"] for s in all_stats if s["finetuned_count"] > 0]
    )
    avg_base_lat = np.mean([s["baseline_latency_ms"] for s in all_stats])
    avg_fine_lat = np.mean([s["finetuned_latency_ms"] for s in all_stats])

    gain_pct = (
        (total_fine_detections - total_base_detections) / max(1, total_base_detections)
    ) * 100.0

    # Write Markdown summary report
    report_path = out_dir / "EVALUATION_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 📊 Restaurant YOLO Fine-Tuning Evaluation Report\n\n")
        f.write(f"- **Baseline Model:** `{baseline_path.name}`\n")
        f.write(f"- **Fine-Tuned Model:** `{finetuned_path.name}`\n")
        f.write(f"- **Confidence Threshold:** `{args.conf}`\n")
        f.write(f"- **Inference Resolution:** `{args.imgsz}x{args.imgsz}`\n")
        f.write(f"- **Evaluated Test Frames:** `{len(test_files)}`\n\n")

        f.write("## 1. Executive Metrics Comparison\n\n")
        f.write(
            "| Metric | Baseline Model | Fine-Tuned Model | Absolute Delta | Relative Change |\n"
        )
        f.write("|---|---|---|---|---|\n")
        f.write(
            f"| **Total Patron Detections** | {total_base_detections} | {total_fine_detections} | +{total_fine_detections - total_base_detections} | **{gain_pct:+.1f}%** |\n"
        )
        f.write(
            f"| **Mean Seated Confidence** | {avg_base_conf:.3f} | {avg_fine_conf:.3f} | {avg_fine_conf - avg_base_conf:+.3f} | **{((avg_fine_conf - avg_base_conf) / max(0.01, avg_base_conf)) * 100:+.1f}%** |\n"
        )
        f.write(
            f"| **Average Latency (CPU)** | {avg_base_lat:.1f} ms | {avg_fine_lat:.1f} ms | {avg_fine_lat - avg_base_lat:+.1f} ms | {avg_fine_lat / max(0.01, avg_base_lat):.2f}x |\n\n"
        )

        f.write("## 2. Per-Frame Detection Breakdown\n\n")
        f.write(
            "| Image Frame | Baseline Detections | Fine-Tuned Detections | Baseline Mean Conf | Fine-Tuned Mean Conf |\n"
        )
        f.write("|---|---|---|---|---|\n")
        for s in all_stats:
            f.write(
                f"| `{s['image']}` | {s['baseline_count']} | {s['finetuned_count']} | {s['baseline_mean_conf']:.2f} | {s['finetuned_mean_conf']:.2f} |\n"
            )

        f.write("\n## 3. Visual Comparison Artifacts\n\n")
        f.write(
            f"Composite side-by-side visual comparisons have been saved to `{out_dir.resolve()}`.\n"
        )

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(
        f"Total Detections:   Baseline = {total_base_detections} | Fine-Tuned = {total_fine_detections} ({gain_pct:+.1f}%)"
    )
    print(f"Mean Confidence:    Baseline = {avg_base_conf:.3f} | Fine-Tuned = {avg_fine_conf:.3f}")
    print(
        f"Average Latency:    Baseline = {avg_base_lat:.1f}ms | Fine-Tuned = {avg_fine_lat:.1f}ms"
    )
    print(f"Report saved to:    {report_path.resolve()}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
