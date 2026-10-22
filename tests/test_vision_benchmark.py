"""Tests for vision benchmarking suite."""


from smartserve.vision.benchmark import BenchmarkResult, benchmark_detector
from smartserve.vision.detector import MockDetector


def test_benchmark_detector_with_mock():
    """Verify benchmark_detector executes successfully with MockDetector."""
    detector = MockDetector()
    result = benchmark_detector(
        detector=detector,
        num_frames=10,
        frame_shape=(240, 320),
        warmup_frames=2,
    )

    assert isinstance(result, BenchmarkResult)
    assert result.total_frames == 10
    assert result.fps > 0.0
    assert result.mean_latency_ms >= 0.0
    assert result.p50_latency_ms >= 0.0
    assert result.p95_latency_ms >= 0.0
    assert result.p99_latency_ms >= 0.0
    assert result.min_latency_ms <= result.max_latency_ms

    # Check dictionary conversion
    d = result.to_dict()
    assert "fps" in d
    assert "mean_latency_ms" in d
    assert "hardware_info" in d

    # Check markdown conversion
    md = result.to_markdown()
    assert "### Benchmark:" in md
    assert "Throughput:" in md
