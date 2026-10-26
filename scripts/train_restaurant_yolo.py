#!/usr/bin/env python3
"""Fine-tune Ultralytics YOLO specifically for restaurant dining scenes and CCTV camera angles.

Features:
- Adapts pretrained YOLO26/11 weights to seated diner postures and table edge occlusions.
- Configures specialized indoor restaurant augmentations (HSV lighting shifts, table occlusion mixup).
- Fine-tunes with conservative learning rate and warmup to preserve general person features.
- Saves best weights directly to 'models/yolo26_restaurant_cctv.pt' for SmartServe integration.

Usage:
    python scripts/train_restaurant_yolo.py --data datasets/restaurant_cctv/data.yaml --epochs 15
    python scripts/train_restaurant_yolo.py --base-model yolo26s.pt --device cpu --batch 8
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

# Prevent Windows libiomp5md duplicate runtime crash
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Ensure project src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_restaurant_yolo")


def train_restaurant_model(
    data_yaml: Path,
    base_model: str = "yolo26s.pt",
    epochs: int = 15,
    imgsz: int = 640,
    batch: int = 8,
    device: str | None = None,
    output_model_dir: Path = PROJECT_ROOT / "models",
    output_model_name: str = "yolo26_restaurant_cctv.pt",
    patience: int = 10,
    workers: int = 0,
) -> Path:
    """Run Ultralytics YOLO fine-tuning on the restaurant CCTV dataset.

    Args:
        data_yaml: Path to data.yaml dataset definition.
        base_model: Base pretrained model weights (e.g. yolo26s.pt or yolo26n.pt).
        epochs: Number of training epochs.
        imgsz: Training input resolution.
        batch: Batch size.
        device: 'cpu', 'cuda', or None for auto-detection.
        output_model_dir: Directory where final model weights are saved.
        output_model_name: Filename of the saved fine-tuned model.
        patience: Epochs to wait for early stopping.
        workers: DataLoader worker threads.

    Returns:
        Path to the saved best fine-tuned model weights.
    """
    from ultralytics import YOLO

    data_yaml = data_yaml.resolve()
    if not data_yaml.exists():
        fallback = PROJECT_ROOT / "datasets" / "restaurant_cctv_clean" / "data.yaml"
        if fallback.exists():
            data_yaml = fallback
        else:
            raise FileNotFoundError(
                f"data.yaml not found at {data_yaml}. Run prepare_finetuning_dataset.py first."
            )

    output_model_dir.mkdir(parents=True, exist_ok=True)
    target_weights_path = output_model_dir / output_model_name

    logger.info("=" * 60)
    logger.info("Starting Restaurant YOLO Fine-Tuning")
    logger.info(f"Base Model:         {base_model}")
    logger.info(f"Dataset YAML:       {data_yaml}")
    logger.info(f"Epochs:             {epochs}")
    logger.info(f"Image Resolution:   {imgsz}")
    logger.info(f"Batch Size:         {batch}")
    logger.info(f"Device:             {device or 'auto'}")
    logger.info("=" * 60)

    # Load base model
    model = YOLO(base_model)

    start_time = time.time()

    # Train with hyperparameters optimized for indoor dining CCTV:
    # 1. hsv_h, hsv_s, hsv_v: robust to warm ambient lighting, candle glow, dim shadows under tables.
    # 2. degrees=0.0: CCTV ceiling cameras are fixed overhead mounts, no sideways inversion.
    # 3. mosaic=1.0 & mixup=0.1: forces network to learn partially occluded heads, shoulders, and arms.
    # 4. close_mosaic=3: disables mosaic for last 3 epochs for fine localization on table borders.
    # 5. lr0=0.001 (10x lower than scratch training) to avoid catastrophic forgetting of person anatomy.
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=workers,
        patience=patience,
        # Optimizer & learning rate
        optimizer="AdamW",
        lr0=0.0005,
        lrf=0.01,
        warmup_epochs=1.0,
        # Restaurant Domain Augmentation Hyperparameters (disable heavy mosaic to keep clean whole-body detection)
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        degrees=0.0,
        translate=0.05,
        scale=0.1,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        mosaic=0.0,
        mixup=0.0,
        close_mosaic=0,
        # Output project naming
        project=str(PROJECT_ROOT / "runs" / "restaurant_finetune"),
        name="exp",
        exist_ok=True,
        verbose=True,
    )

    elapsed = time.time() - start_time
    logger.info(f"Training completed in {elapsed:.1f}s ({elapsed / 60:.2f} mins)")

    # Locate best.pt
    run_save_dir = (
        Path(model.trainer.save_dir) if hasattr(model, "trainer") and model.trainer else None
    )
    best_pt = None
    if run_save_dir:
        cand_best = run_save_dir / "weights" / "best.pt"
        if cand_best.exists():
            best_pt = cand_best

    if best_pt and best_pt.exists():
        shutil.copy2(str(best_pt), str(target_weights_path))
        logger.info(f"[SUCCESS] Best fine-tuned model saved to: {target_weights_path.resolve()}")
    else:
        # Fallback to export from model if best.pt is elsewhere
        logger.warning(
            f"best.pt not directly located in {run_save_dir}; saving current model state..."
        )
        model.save(str(target_weights_path))

    # Evaluate validation metrics
    logger.info("Running validation evaluation on fine-tuned weights...")
    val_model = YOLO(str(target_weights_path))
    val_metrics = val_model.val(data=str(data_yaml), imgsz=imgsz, device=device, verbose=False)

    summary_data = {
        "base_model": base_model,
        "fine_tuned_model": str(target_weights_path.name),
        "target_weights_path": str(target_weights_path.resolve()),
        "dataset_yaml": str(data_yaml),
        "epochs": epochs,
        "imgsz": imgsz,
        "training_time_seconds": round(elapsed, 1),
        "metrics": {
            "mAP50": round(float(val_metrics.box.map50), 4)
            if hasattr(val_metrics.box, "map50")
            else None,
            "mAP50_95": round(float(val_metrics.box.map), 4)
            if hasattr(val_metrics.box, "map")
            else None,
            "precision": round(float(val_metrics.box.mp), 4)
            if hasattr(val_metrics.box, "mp")
            else None,
            "recall": round(float(val_metrics.box.mr), 4)
            if hasattr(val_metrics.box, "mr")
            else None,
        },
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    summary_file = output_model_dir / "training_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    logger.info(f"Validation Summary:\n{json.dumps(summary_data['metrics'], indent=2)}")
    logger.info(f"Summary saved to: {summary_file}")

    return target_weights_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune YOLO for Restaurant CCTV Dining Scenes")
    default_data = (
        "datasets/restaurant_cctv_clean/data.yaml"
        if (PROJECT_ROOT / "datasets/restaurant_cctv_clean/data.yaml").exists()
        else "datasets/restaurant_cctv/data.yaml"
    )
    parser.add_argument(
        "--data", type=str, default=default_data, help="Path to data.yaml"
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="yolo26s.pt",
        help="Base pretrained weights (yolo26s.pt, yolo26n.pt, yolo11s.pt)",
    )
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference / training image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument(
        "--device", type=str, default=None, help="Device ('cpu', 'cuda', or None for auto)"
    )
    parser.add_argument(
        "--output-name", type=str, default="yolo26_restaurant_cctv.pt", help="Output model filename"
    )
    parser.add_argument("--patience", type=int, default=10, help="Early stopping patience")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path

    try:
        final_model_path = train_restaurant_model(
            data_yaml=data_path,
            base_model=args.base_model,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            output_model_name=args.output_name,
            patience=args.patience,
        )
        print(f"\n[DONE] Model fine-tuning complete!\nWeights: {final_model_path}\n")
        print(
            "To test and compare performance against baseline:\npython scripts/evaluate_finetuned_model.py\n"
        )
        return 0
    except Exception as exc:
        logger.error(f"Training failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
