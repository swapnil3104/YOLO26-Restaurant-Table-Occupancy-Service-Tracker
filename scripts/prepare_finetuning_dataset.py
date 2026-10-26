#!/usr/bin/env python3
"""Dataset preparation and pseudo-labeling pipeline for restaurant CCTV fine-tuning.

Extracts representative frames from restaurant CCTV footage, generates high-recall
diner annotations using multi-scale teacher inference and domain filtering, and organizes
the data into Ultralytics YOLO dataset format (images/train, images/val, labels/train, labels/val, data.yaml).

Usage:
    python scripts/prepare_finetuning_dataset.py --video-dir "Sample Video" --output-dir datasets/restaurant_cctv
    python scripts/prepare_finetuning_dataset.py --sample-interval 20 --teacher-model yolo26s.pt
"""

import argparse
import logging
import random
import sys
from pathlib import Path

import cv2
import yaml

# Ensure project src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_dataset")


def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    sample_interval: int = 20,
    max_frames_per_video: int = 150,
) -> list[Path]:
    """Extract frames from a video file at regular intervals.

    Args:
        video_path: Path to the input video.
        output_dir: Directory where extracted images will be saved.
        sample_interval: Frame step interval (e.g. 20 means 1 frame every 20 frames).
        max_frames_per_video: Maximum number of frames to extract from this video.

    Returns:
        List of saved image file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning(f"Could not open video file: {video_path}")
        return []

    video_stem = (
        video_path.stem.replace(" ", "_").replace("(", "").replace(")", "").replace(".", "_")
    )
    saved_paths: list[Path] = []
    frame_idx = 0
    extracted_count = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if frame_idx % sample_interval == 0:
            frame_filename = f"{video_stem}_f{frame_idx:05d}.jpg"
            save_path = output_dir / frame_filename
            cv2.imwrite(str(save_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            saved_paths.append(save_path)
            extracted_count += 1
            if extracted_count >= max_frames_per_video:
                break

        frame_idx += 1

    cap.release()
    logger.info(f"Extracted {len(saved_paths)} frames from {video_path.name}")
    return saved_paths


def generate_diner_annotations(
    image_paths: list[Path],
    teacher_model_path: str = "yolo26s.pt",
    conf_threshold: float = 0.22,
    imgsz: int = 1280,
    min_box_area_ratio: float = 0.001,
    max_box_area_ratio: float = 0.65,
) -> dict[Path, list[tuple[int, float, float, float, float]]]:
    """Generate YOLO bounding box annotations using high-resolution teacher inference.

    Restaurant CCTV poses challenges: seated diners have lower bodies occluded by table edges,
    leading standard models to output lower confidences (0.22-0.45). Using a low threshold
    at high resolution (1280px) maximizes recall of occluded seated patrons.

    Args:
        image_paths: List of extracted frame paths.
        teacher_model_path: Weights to use for teacher labeling.
        conf_threshold: Confidence threshold for person class.
        imgsz: High-resolution inference size for detecting distant diners.
        min_box_area_ratio: Minimum bbox area as a fraction of image area (filters tiny noise).
        max_box_area_ratio: Maximum bbox area as a fraction of image area (filters false full-screen boxes).

    Returns:
        Mapping from image path to list of normalized YOLO boxes: (cls_id, x_center, y_center, w, h).
    """
    from ultralytics import YOLO

    logger.info(
        f"Loading teacher model '{teacher_model_path}' for auto-labeling (conf={conf_threshold}, imgsz={imgsz})..."
    )
    teacher = YOLO(teacher_model_path)
    annotations_map: dict[Path, list[tuple[int, float, float, float, float]]] = {}

    total_boxes = 0
    for idx, img_path in enumerate(image_paths):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        img_area = float(w * h)

        # Run inference on person class (class 0)
        results = teacher.predict(
            source=img,
            conf=conf_threshold,
            classes=[0],
            imgsz=imgsz,
            verbose=False,
        )

        boxes_for_image: list[tuple[int, float, float, float, float]] = []
        if results and len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = xyxy[:4]

                # Clamp coordinates to image boundaries
                x1 = max(0.0, min(float(w), float(x1)))
                y1 = max(0.0, min(float(h), float(y1)))
                x2 = max(0.0, min(float(w), float(x2)))
                y2 = max(0.0, min(float(h), float(y2)))

                bw = x2 - x1
                bh = y2 - y1
                box_area = bw * bh
                area_ratio = box_area / img_area

                if area_ratio < min_box_area_ratio or area_ratio > max_box_area_ratio:
                    continue

                # Convert to normalized YOLO format: class_id, x_center, y_center, width, height
                xc = (x1 + x2) / (2.0 * w)
                yc = (y1 + y2) / (2.0 * h)
                norm_w = bw / float(w)
                norm_h = bh / float(h)

                # Ensure strict [0, 1] bounds
                xc = max(0.0, min(1.0, xc))
                yc = max(0.0, min(1.0, yc))
                norm_w = max(0.001, min(1.0, norm_w))
                norm_h = max(0.001, min(1.0, norm_h))

                boxes_for_image.append((0, xc, yc, norm_w, norm_h))

        annotations_map[img_path] = boxes_for_image
        total_boxes += len(boxes_for_image)

        if (idx + 1) % 25 == 0 or (idx + 1) == len(image_paths):
            logger.info(
                f"Labeled {idx + 1}/{len(image_paths)} images ({total_boxes} total diner annotations so far)"
            )

    return annotations_map


def build_yolo_dataset(
    annotations_map: dict[Path, list[tuple[int, float, float, float, float]]],
    dataset_dir: Path,
    val_split: float = 0.20,
    seed: int = 42,
) -> Path:
    """Organize images and labels into standard Ultralytics YOLO structure with train/val splits.

    Directory structure:
        dataset_dir/
            ├── data.yaml
            ├── images/
            │   ├── train/
            │   └── val/
            └── labels/
                ├── train/
                └── val/

    Args:
        annotations_map: Mapping of image paths to list of normalized bounding boxes.
        dataset_dir: Destination directory.
        val_split: Proportion of frames to assign to validation split.
        seed: Random seed for deterministic reproducibility.

    Returns:
        Path to generated data.yaml.
    """
    random.seed(seed)
    dataset_dir = dataset_dir.resolve()

    train_img_dir = dataset_dir / "images" / "train"
    val_img_dir = dataset_dir / "images" / "val"
    train_lbl_dir = dataset_dir / "labels" / "train"
    val_lbl_dir = dataset_dir / "labels" / "val"

    for d in (train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir):
        d.mkdir(parents=True, exist_ok=True)

    items = list(annotations_map.items())
    random.shuffle(items)

    num_val = int(len(items) * val_split)
    val_items = items[:num_val]
    train_items = items[num_val:]

    def _write_split(
        split_items: list[tuple[Path, list[tuple[int, float, float, float, float]]]],
        img_dir: Path,
        lbl_dir: Path,
    ) -> int:
        count = 0
        for src_img_path, boxes in split_items:
            dest_img_path = img_dir / src_img_path.name
            dest_lbl_path = lbl_dir / f"{src_img_path.stem}.txt"

            # Copy image
            img_data = cv2.imread(str(src_img_path))
            if img_data is not None:
                cv2.imwrite(str(dest_img_path), img_data)

            # Write YOLO format label file
            with open(dest_lbl_path, "w", encoding="utf-8") as f:
                for cls_id, xc, yc, bw, bh in boxes:
                    f.write(f"{cls_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")
            count += 1
        return count

    n_train = _write_split(train_items, train_img_dir, train_lbl_dir)
    n_val = _write_split(val_items, val_img_dir, val_lbl_dir)

    # Write data.yaml using relative paths for portability
    yaml_path = dataset_dir / "data.yaml"
    data_dict = {
        "path": str(dataset_dir.as_posix()),
        "train": "images/train",
        "val": "images/val",
        "names": {
            0: "person",
        },
    }

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_dict, f, default_flow_style=False, sort_keys=False)

    logger.info("=" * 60)
    logger.info(f"Dataset successfully built at: {dataset_dir}")
    logger.info(f"Train images: {n_train} | Val images: {n_val}")
    logger.info(f"data.yaml location: {yaml_path}")
    logger.info("=" * 60)

    return yaml_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Restaurant CCTV YOLO Fine-tuning Dataset")
    parser.add_argument(
        "--video-dir",
        type=str,
        default="Sample Video",
        help="Directory containing sample CCTV videos",
    )
    parser.add_argument(
        "--raw-images-dir",
        type=str,
        default=None,
        help="Optional directory with existing raw CCTV images",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/restaurant_cctv",
        help="Output dataset directory",
    )
    parser.add_argument(
        "--sample-interval", type=int, default=20, help="Frame step interval for extraction"
    )
    parser.add_argument(
        "--max-frames-per-video", type=int, default=120, help="Max frames to extract per video"
    )
    parser.add_argument(
        "--teacher-model",
        type=str,
        default="yolo26s.pt",
        help="Pretrained model for teacher labeling",
    )
    parser.add_argument(
        "--conf-threshold",
        type=float,
        default=0.22,
        help="Teacher confidence threshold (tuned for seated diners)",
    )
    parser.add_argument("--val-split", type=float, default=0.20, help="Validation split fraction")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    raw_frames_cache = output_dir / "raw_extracted_frames"
    raw_frames_cache.mkdir(parents=True, exist_ok=True)

    extracted_images: list[Path] = []

    # 1. Extract frames from video files
    video_dir = Path(args.video_dir)
    if video_dir.exists():
        video_files = (
            list(video_dir.glob("*.mp4"))
            + list(video_dir.glob("*.avi"))
            + list(video_dir.glob("*.mkv"))
        )
        logger.info(f"Found {len(video_files)} video files in {video_dir}")
        for vf in video_files:
            frames = extract_frames_from_video(
                video_path=vf,
                output_dir=raw_frames_cache,
                sample_interval=args.sample_interval,
                max_frames_per_video=args.max_frames_per_video,
            )
            extracted_images.extend(frames)

    # 2. Add any standalone raw images if provided
    if args.raw_images_dir:
        raw_img_dir = Path(args.raw_images_dir)
        if raw_img_dir.exists():
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                extracted_images.extend(list(raw_img_dir.glob(ext)))

    # Also include sample_cctv_raw.jpg if present in workspace root
    sample_cctv_raw = PROJECT_ROOT / "sample_cctv_raw.jpg"
    if sample_cctv_raw.exists() and sample_cctv_raw not in extracted_images:
        dest_copy = raw_frames_cache / "sample_cctv_raw.jpg"
        img = cv2.imread(str(sample_cctv_raw))
        if img is not None:
            cv2.imwrite(str(dest_copy), img)
            extracted_images.append(dest_copy)

    if not extracted_images:
        logger.error(
            "No images could be extracted or found. Check --video-dir or --raw-images-dir."
        )
        return 1

    logger.info(f"Total raw restaurant frames to annotate: {len(extracted_images)}")

    # 3. Generate diner annotations with teacher model
    annotations_map = generate_diner_annotations(
        image_paths=extracted_images,
        teacher_model_path=args.teacher_model,
        conf_threshold=args.conf_threshold,
        imgsz=1280,
    )

    # 4. Build standard YOLO dataset structure
    yaml_path = build_yolo_dataset(
        annotations_map=annotations_map,
        dataset_dir=output_dir,
        val_split=args.val_split,
    )

    print(
        f"\n[SUCCESS] Dataset prepared. You can now train the model using:\npython scripts/train_restaurant_yolo.py --data {yaml_path}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
