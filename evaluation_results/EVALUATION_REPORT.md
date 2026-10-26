# 📊 Restaurant YOLO Fine-Tuning Evaluation Report

- **Baseline Model:** `yolo26s.pt`
- **Fine-Tuned Model:** `yolo26_restaurant_cctv.pt`
- **Confidence Threshold:** `0.25`
- **Inference Resolution:** `640x640`
- **Evaluated Test Frames:** `11`

## 1. Executive Metrics Comparison

| Metric | Baseline Model | Fine-Tuned Model | Absolute Delta | Relative Change |
|---|---|---|---|---|
| **Total Patron Detections** | 57 | 52 | +-5 | **-8.8%** |
| **Mean Seated Confidence** | 0.640 | 0.649 | +0.009 | **+1.3%** |
| **Average Latency (CPU)** | 302.3 ms | 80.6 ms | -221.6 ms | 0.27x |

## 2. Per-Frame Detection Breakdown

| Image Frame | Baseline Detections | Fine-Tuned Detections | Baseline Mean Conf | Fine-Tuned Mean Conf |
|---|---|---|---|---|
| `cctv_frame_00000.jpg` | 2 | 2 | 0.85 | 0.90 |
| `cctv_frame_00150.jpg` | 2 | 2 | 0.73 | 0.69 |
| `cctv_frame_00300.jpg` | 7 | 6 | 0.68 | 0.56 |
| `cctv_frame_00450.jpg` | 4 | 4 | 0.55 | 0.65 |
| `cctv_frame_00600.jpg` | 4 | 4 | 0.54 | 0.63 |
| `Screenshot 2026-10-26 142432.png` | 2 | 2 | 0.79 | 0.89 |
| `Screenshot 2026-10-26 142610.png` | 2 | 2 | 0.82 | 0.85 |
| `Screenshot 2026-10-26 142646.png` | 4 | 4 | 0.60 | 0.65 |
| `sample_cctv_raw.jpg` | 15 | 11 | 0.45 | 0.45 |
| `test_frame_first.jpg` | 3 | 4 | 0.58 | 0.39 |
| `sample_video_frame_0.jpg` | 12 | 11 | 0.46 | 0.46 |

## 3. Visual Comparison Artifacts

Composite side-by-side visual comparisons have been saved to `E:\YOLO26-Restaurant-Table-Occupancy-Service-Tracker\evaluation_results`.
