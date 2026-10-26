"""Unit tests for Restaurant YOLO Fine-Tuning Pipeline and Dataset Tools."""

import tempfile
from pathlib import Path

import numpy as np
import yaml

from scripts.prepare_finetuning_dataset import build_yolo_dataset
from smartserve.vision.detector import YOLO26Detector, normalize_coordinates


def test_normalize_coordinates_clamping():
    """Verify normalize_coordinates clamps out-of-bounds pixels correctly."""
    # Pixel coordinates slightly outside frame bounds
    bbox = normalize_coordinates(
        x1=-10,
        y1=-5,
        x2=1300,
        y2=750,
        frame_width=1280,
        frame_height=720,
    )
    assert bbox.x1 == 0.0
    assert bbox.y1 == 0.0
    assert bbox.x2 == 1.0
    assert bbox.y2 == 1.0
    assert bbox.is_normalized is True


def test_yolo26_detector_imgsz_configuration():
    """Verify YOLO26Detector initializes and configures custom imgsz resolution."""
    detector = YOLO26Detector(
        model_path="yolo26n.pt",
        confidence_threshold=0.30,
        imgsz=960,
    )
    assert detector.imgsz == 960
    assert detector.confidence_threshold == 0.30
    assert detector.model_path == "yolo26n.pt"


def test_build_yolo_dataset_structure():
    """Verify build_yolo_dataset writes correct directory layout and data.yaml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        raw_images_dir = tmp_path / "raw"
        raw_images_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy image files
        import cv2

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        img1 = raw_images_dir / "frame1.jpg"
        img2 = raw_images_dir / "frame2.jpg"
        img3 = raw_images_dir / "frame3.jpg"
        cv2.imwrite(str(img1), dummy_img)
        cv2.imwrite(str(img2), dummy_img)
        cv2.imwrite(str(img3), dummy_img)

        # Mock annotations map: (cls_id, xc, yc, w, h)
        annotations_map = {
            img1: [(0, 0.5, 0.5, 0.2, 0.4)],
            img2: [(0, 0.3, 0.4, 0.15, 0.35), (0, 0.7, 0.6, 0.1, 0.2)],
            img3: [(0, 0.2, 0.2, 0.1, 0.1)],
        }

        dataset_out = tmp_path / "dataset"
        yaml_path = build_yolo_dataset(
            annotations_map=annotations_map,
            dataset_dir=dataset_out,
            val_split=0.33,
        )

        assert yaml_path.exists()
        assert (dataset_out / "images" / "train").exists()
        assert (dataset_out / "images" / "val").exists()
        assert (dataset_out / "labels" / "train").exists()
        assert (dataset_out / "labels" / "val").exists()

        # Parse generated data.yaml
        with open(yaml_path, encoding="utf-8") as f:
            data_cfg = yaml.safe_load(f)

        assert "train" in data_cfg
        assert "val" in data_cfg
        assert data_cfg["names"][0] == "person"
