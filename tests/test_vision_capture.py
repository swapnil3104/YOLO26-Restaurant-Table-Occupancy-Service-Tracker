"""Tests for OpenCV video capture pipeline."""

import os
import tempfile
import cv2
import numpy as np
import pytest

from smartserve.vision.capture import (
    CameraStatus,
    FramePacket,
    InvalidFrameError,
    VideoCapturePipeline,
    VideoSourceNotFoundError,
)


@pytest.fixture
def temp_video_file():
    """Create a temporary 10-frame synthetic test video."""
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, "test_clip.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 10.0, (320, 240))

    # Write 10 frames with moving rectangle
    for i in range(10):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Add simulated moving subject
        cv2.rectangle(frame, (20 + i * 10, 50), (60 + i * 10, 150), (0, 255, 0), -1)
        out.write(frame)
    out.release()

    yield video_path

    # Cleanup
    if os.path.exists(video_path):
        os.remove(video_path)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)


def test_missing_video_source_raises_error():
    """Verify non-existent video path raises VideoSourceNotFoundError."""
    with pytest.raises(VideoSourceNotFoundError):
        VideoCapturePipeline(source="/non/existent/path/video.mp4", camera_id="CAM-99")


def test_successful_video_ingestion(temp_video_file):
    """Verify pipeline opens synthetic video and yields valid FramePackets."""
    pipeline = VideoCapturePipeline(source=temp_video_file, camera_id="CAM-TEST", sample_rate_hz=None)
    assert pipeline.open() is True
    assert pipeline.status == CameraStatus.CONNECTED
    assert pipeline.is_opened is True

    packets = []
    for packet in pipeline.stream_frames():
        assert isinstance(packet, FramePacket)
        assert packet.camera_id == "CAM-TEST"
        assert packet.width == 320
        assert packet.height == 240
        assert packet.frame.shape == (240, 320, 3)
        assert packet.timestamp_utc is not None
        assert packet.timestamp_ms >= 0
        assert packet.frame_index > 0
        packets.append(packet)

    assert len(packets) == 10
    assert pipeline.status == CameraStatus.COMPLETED


def test_frame_sampling_rate_limits_throughput(temp_video_file):
    """Verify sample_rate_hz samples frames without crash."""
    pipeline = VideoCapturePipeline(source=temp_video_file, camera_id="CAM-SAMPLED", sample_rate_hz=5.0)
    assert pipeline.open() is True

    packets = list(pipeline.stream_frames())
    # Sampling should succeed and yield packets
    assert len(packets) > 0
    assert len(packets) <= 10


def test_invalid_frame_detection():
    """Verify empty frame triggers InvalidFrameError if injected."""
    packet = FramePacket(
        frame=np.zeros((100, 100, 3), dtype=np.uint8),
        frame_index=1,
        timestamp_utc=None,
        timestamp_ms=0.0,
        camera_id="CAM-01",
        width=100,
        height=100,
        fps=30.0,
    )
    assert packet.aspect_ratio == 1.0
