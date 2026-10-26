# 🎯 Restaurant CCTV Model Fine-Tuning Guide

**Document:** Custom YOLO Fine-Tuning for Restaurant Dining & Seated Patron Detection  
**Version:** 1.0  
**Phase:** Vision Optimization & Model Performance  
**Status:** Operational  

---

## 1. Why Standard Pretrained Models Perform Weakly in Restaurants

Off-the-shelf COCO-pretrained object detectors (including stock YOLOv8, YOLO11, and YOLO26) are primarily trained on upright people standing in open spaces with standard daylighting. In restaurant environments, cameras present specific visual hurdles that lead to poor recall:

| Challenge | Visual Manifestation in Restaurant CCTV | Pretrained Model Weakness | Fine-Tuning Solution |
|---|---|---|---|
| **Table Edge Occlusion** | 50%–70% of a diner's lower body is occluded by tabletops and booth partitions. | Confidence drops significantly (to 0.18–0.32), falling below standard thresholds (`0.35`–`0.45`). | Trained with **mixup and mosaic** augmentations simulating tabletop occlusion. |
| **Overhead Angled Angles** | Ceilings mounts present foreshortened heads, shoulders, and seated torsos. | Pretrained feature heads expect standard ground-level perspective. | Specialized dataset captures perspective foreshortening from ceiling mounts. |
| **Dim Atmospheric Lighting** | Candlelight, warm incandescent bulbs, and window glare. | False negatives in deep booth shadows and contrast blowouts. | **HSV augmentation** (`hsv_s=0.6`, `hsv_v=0.4`) simulates moody dining lighting shifts. |
| **Crowded Banquettes** | Multiple patrons sitting shoulder-to-shoulder at the same table. | Bounding box suppression or merged boxes. | Fine-tuned dual-head unconstrained regression head separates adjacent seated diners. |

---

## 2. End-to-End Fine-Tuning Pipeline

The fine-tuning pipeline consists of three automated tools:

```
┌─────────────────────────────────┐
│ 1. CCTV Video / Footage Input   │  (Sample Video/*.mp4 or live CCTV streams)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ scripts/prepare_finetuning_dataset.py  │  - Extracts diverse frames (1 fps sampling)
└────────────────┬────────────────┘  - Multi-scale high-recall teacher pseudo-labeling
                 │                    - Builds Ultralytics YOLO dataset format
                 ▼
┌─────────────────────────────────┐
│ datasets/restaurant_cctv/       │  ├── images/ (train, val)
│   ├── data.yaml                 │  └── labels/ (train, val)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ scripts/train_restaurant_yolo.py│  - Restaurant domain augmentations (HSV, mixup)
└────────────────┬────────────────┘  - Conservative learning rate (lr0=0.001)
                 │                    - Exports best weights to models/yolo26_restaurant_cctv.pt
                 ▼
┌─────────────────────────────────┐
│ scripts/evaluate_finetuned_model.py│ - Side-by-side visual comparison (Baseline vs Fine-Tuned)
└─────────────────────────────────┘ - Quantitative recall gain & seated confidence report
```

---

## 3. Quickstart Guide

### Step 1: Prepare the Dataset from Video Footage

Extract and auto-label frames from your restaurant CCTV clips:

```bash
python scripts/prepare_finetuning_dataset.py \
    --video-dir "Sample Video" \
    --output-dir datasets/restaurant_cctv \
    --sample-interval 20 \
    --max-frames-per-video 80 \
    --teacher-model yolo26s.pt \
    --conf-threshold 0.22
```

- `--sample-interval 20`: Samples 1 frame every 20 frames (~1.2 fps) to ensure frame variety.
- `--conf-threshold 0.22`: Uses high-sensitivity teacher inference to capture occluded seated patrons.
- Output: Standard YOLO dataset under `datasets/restaurant_cctv/` with `data.yaml`.

---

### Step 2: Run Fine-Tuning

Fine-tune the model with restaurant-specific augmentations:

```bash
python scripts/train_restaurant_yolo.py \
    --data datasets/restaurant_cctv/data.yaml \
    --base-model yolo26s.pt \
    --epochs 15 \
    --batch 8 \
    --imgsz 640 \
    --output-name yolo26_restaurant_cctv.pt
```

Key Training Hyperparameters:
- `lr0=0.001`: 10× lower than scratch training to retain general human anatomy features while adapting to seated postures.
- `hsv_h=0.015, hsv_s=0.6, hsv_v=0.4`: Robustness against mood lighting and shadows.
- `mosaic=1.0, mixup=0.1`: Teaches model to recognize partially hidden diners.
- `close_mosaic=3`: Disables mosaic during final epochs for precise bounding box boundaries.
- Best weights are automatically saved to `models/yolo26_restaurant_cctv.pt`.

---

### Step 3: Evaluate and Compare Against Baseline

Run side-by-side visual and quantitative evaluation:

```bash
python scripts/evaluate_finetuned_model.py \
    --baseline yolo26s.pt \
    --finetuned models/yolo26_restaurant_cctv.pt \
    --conf 0.25 \
    --output-dir evaluation_results
```

Outputs:
1. `evaluation_results/compare_*.jpg`: Side-by-side composite images comparing baseline detections (left) vs fine-tuned detections (right).
2. `evaluation_results/EVALUATION_REPORT.md`: Quantitative report showing total detections, recall gain percentage, mean seated confidence, and latency.

---

## 4. Enabling the Fine-Tuned Model in SmartServe

Once trained, activate the fine-tuned model in SmartServe in either of two ways:

### Option A: Via Environment File (`.env`)
```bash
MODEL_WEIGHTS_PATH=models/yolo26_restaurant_cctv.pt
DETECTION_CONFIDENCE_THRESHOLD=0.28
```

### Option B: In Python Code (`src/smartserve/config.py`)
```python
from smartserve.vision.detector import YOLO26Detector

# Use fine-tuned weights with optional higher resolution for distant tables
detector = YOLO26Detector(
    model_path="models/yolo26_restaurant_cctv.pt",
    confidence_threshold=0.28,
    imgsz=640, # Or 960/1280 for very large dining halls
)
```

---

## 5. Adding New CCTV Cameras or Footage

When onboarding a new restaurant location with different interior design or camera angles:
1. Copy 1–2 minutes of sample video into `Sample Video/` or a custom directory.
2. Re-run `scripts/prepare_finetuning_dataset.py --video-dir "path/to/videos"`.
3. Re-run `scripts/train_restaurant_yolo.py --epochs 10`.
4. Run `scripts/evaluate_finetuned_model.py` to inspect the results.
