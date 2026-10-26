"""Vision inference benchmarking suite.

Measures detector warmup, throughput (FPS), percentile latencies (p50, p95, p99),
and formats results for engineering and pilot documentation.
"""

import platform
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from smartserve.vision.interfaces import BaseDetector


@dataclass
class BenchmarkResult:
    """Benchmark performance metrics summary."""

    detector_name: str
    total_frames: int
    resolution: tuple[int, int]
    warmup_frames: int
    total_time_sec: float
    fps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    hardware_info: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "detector_name": self.detector_name,
            "total_frames": self.total_frames,
            "resolution": f"{self.resolution[1]}x{self.resolution[0]}",
            "fps": round(self.fps, 2),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "hardware_info": self.hardware_info,
        }

    def to_markdown(self) -> str:
        """Format metrics as a markdown table."""
        lines = [
            f"### Benchmark: {self.detector_name}",
            f"- **Resolution:** {self.resolution[1]}x{self.resolution[0]} ({self.total_frames} frames)",
            f"- **Throughput:** **{self.fps:.1f} FPS**",
            f"- **Mean Latency:** {self.mean_latency_ms:.1f} ms",
            f"- **Median (p50):** {self.p50_latency_ms:.1f} ms",
            f"- **95th Percentile (p95):** {self.p95_latency_ms:.1f} ms",
            f"- **99th Percentile (p99):** {self.p99_latency_ms:.1f} ms",
            f"- **Range:** [{self.min_latency_ms:.1f} ms - {self.max_latency_ms:.1f} ms]",
        ]
        return "\n".join(lines)


def get_system_hardware_info() -> dict[str, str]:
    """Capture current hardware and OS platform specifications."""
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python": platform.python_version(),
    }
    try:
        import torch

        info["torch_version"] = torch.__version__
        info["cuda_available"] = str(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["gpu_device"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch_version"] = "not_installed"

    return info


def benchmark_detector(
    detector: BaseDetector,
    num_frames: int = 50,
    frame_shape: tuple[int, int] = (720, 1280),
    warmup_frames: int = 5,
    test_frame: np.ndarray | None = None,
) -> BenchmarkResult:
    """Run an inference benchmark against a detector.

    Args:
        detector: Detector instance implementing BaseDetector.
        num_frames: Number of timed inference iterations.
        frame_shape: (height, width) for synthetic frame if test_frame is None.
        warmup_frames: Initial runs to discard (GPU cache warmup, JIT compilation).
        test_frame: Specific image array to test against, or None for synthetic.

    Returns:
        BenchmarkResult with computed latency percentiles and FPS.
    """
    if test_frame is None:
        # Create a synthetic 3-channel frame with a colored rectangle simulating a subject
        height, width = frame_shape
        frame = np.full((height, width, 3), 128, dtype=np.uint8)
        # Add high-contrast feature
        frame[int(height * 0.2) : int(height * 0.8), int(width * 0.3) : int(width * 0.7)] = [
            200,
            50,
            50,
        ]
    else:
        frame = test_frame
        height, width = frame.shape[:2]

    # Warmup runs
    for _ in range(max(1, warmup_frames)):
        _ = detector.detect(frame)

    # Timed runs
    latencies_sec: list[float] = []
    total_start = time.perf_counter()

    for _ in range(num_frames):
        start = time.perf_counter()
        _ = detector.detect(frame)
        latencies_sec.append(time.perf_counter() - start)

    total_time_sec = time.perf_counter() - total_start
    latencies_ms = np.array(latencies_sec) * 1000.0

    fps = float(num_frames) / max(total_time_sec, 0.0001)

    return BenchmarkResult(
        detector_name=detector.__class__.__name__,
        total_frames=num_frames,
        resolution=(height, width),
        warmup_frames=warmup_frames,
        total_time_sec=total_time_sec,
        fps=fps,
        mean_latency_ms=float(np.mean(latencies_ms)),
        p50_latency_ms=float(np.percentile(latencies_ms, 50)),
        p95_latency_ms=float(np.percentile(latencies_ms, 95)),
        p99_latency_ms=float(np.percentile(latencies_ms, 99)),
        min_latency_ms=float(np.min(latencies_ms)),
        max_latency_ms=float(np.max(latencies_ms)),
        hardware_info=get_system_hardware_info(),
    )
