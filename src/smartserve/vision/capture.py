"""Video capture pipeline using OpenCV.

Supports local video files, webcams, and RTSP streams with rate limiting,
metadata enrichment (timestamps, camera ID), and actionable error handling.
"""

import logging
import os
import time
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraStatus(StrEnum):
    """Camera connection status."""

    UNINITIALIZED = "UNINITIALIZED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"


class VideoCaptureError(Exception):
    """Base error for video capture failures."""

    pass


class VideoSourceNotFoundError(VideoCaptureError):
    """Raised when a video file or stream endpoint cannot be found."""

    pass


class CameraConnectionError(VideoCaptureError):
    """Raised when camera connection fails or disconnects repeatedly."""

    pass


class InvalidFrameError(VideoCaptureError):
    """Raised when a captured frame is corrupt, empty, or has invalid dimensions."""

    pass


@dataclass
class FramePacket:
    """Standard container for an ingested video frame with operational metadata."""

    frame: np.ndarray
    frame_index: int
    timestamp_utc: datetime
    timestamp_ms: float
    camera_id: str
    width: int
    height: int
    fps: float

    @property
    def aspect_ratio(self) -> float:
        """Calculate width-to-height aspect ratio."""
        return self.width / max(self.height, 1)


class VideoCapturePipeline:
    """Robust OpenCV video capture pipeline with sampling and reconnect logic."""

    def __init__(
        self,
        source: str | int,
        camera_id: str = "CAM-01",
        sample_rate_hz: float | None = 5.0,
        max_reconnect_attempts: int = 5,
        reconnect_delay_sec: float = 1.0,
    ) -> None:
        """Initialize the capture pipeline.

        Args:
            source: Video file path, RTSP URL, or integer device index (e.g. 0).
            camera_id: Identifier for the camera feed.
            sample_rate_hz: Target sampling rate in Hz (e.g. 5.0 for 5 FPS).
                None means process every frame at native source rate.
            max_reconnect_attempts: Maximum reconnect attempts on disconnect.
            reconnect_delay_sec: Delay between reconnection attempts in seconds.
        """
        self.source = source
        self.camera_id = camera_id
        self.sample_rate_hz = sample_rate_hz
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay_sec = reconnect_delay_sec

        self._cap: cv2.VideoCapture | None = None
        self._status = CameraStatus.UNINITIALIZED
        self._frame_count = 0
        self._last_sampled_timestamp = 0.0
        self._is_file = isinstance(source, str) and not source.startswith(
            ("rtsp://", "http://", "https://")
        )

        # Validate file existence early if source is a local path
        if self._is_file and not os.path.exists(str(source)):
            raise VideoSourceNotFoundError(
                f"Video file not found at path: {source}. Please verify the file path."
            )

    @property
    def status(self) -> CameraStatus:
        """Return current camera status."""
        return self._status

    @property
    def is_opened(self) -> bool:
        """Return whether underlying capture device is open."""
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> bool:
        """Open the video capture source.

        Returns:
            True if opened successfully, False otherwise.

        Raises:
            CameraConnectionError: If unable to open the camera stream after attempts.
        """
        attempt = 0
        while attempt < max(1, self.max_reconnect_attempts):
            attempt += 1
            logger.info(
                "Connecting to camera %s (source: %s, attempt %d/%d)...",
                self.camera_id,
                self.source,
                attempt,
                self.max_reconnect_attempts,
            )

            # Handle integer webcam vs string RTSP/file
            source_arg = (
                int(self.source)
                if isinstance(self.source, str) and self.source.isdigit()
                else self.source
            )
            self._cap = cv2.VideoCapture(source_arg)

            if self._cap.isOpened():
                self._status = CameraStatus.CONNECTED
                logger.info(
                    "Camera %s connected successfully. Resolution: %dx%d @ %.1f FPS",
                    self.camera_id,
                    int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    self._cap.get(cv2.CAP_PROP_FPS),
                )
                return True

            self._status = CameraStatus.DISCONNECTED
            if attempt < self.max_reconnect_attempts:
                time.sleep(self.reconnect_delay_sec)

        self._status = CameraStatus.ERROR
        raise CameraConnectionError(
            f"Failed to open camera source '{self.source}' for camera {self.camera_id} "
            f"after {self.max_reconnect_attempts} attempts."
        )

    def read_frame(self) -> FramePacket | None:
        """Read the next frame with rate-limiting and metadata tagging.

        Returns:
            FramePacket if a valid frame was read and passed sampling filter,
            None if the frame was skipped due to sampling rate or stream ended.

        Raises:
            CameraConnectionError: If the stream is unexpectedly closed.
            InvalidFrameError: If the read frame is empty or corrupt.
        """
        if not self.is_opened:
            self.open()

        assert self._cap is not None

        # Loop to find the next frame that matches the sampling criteria
        while True:
            ret, frame = self._cap.read()
            now_mono = time.monotonic()
            now_utc = datetime.now(UTC)

            if not ret or frame is None:
                # Distinguish between file EOF and stream disconnect
                if self._is_file:
                    self._status = CameraStatus.COMPLETED
                    logger.info("Video file %s completed (EOF).", self.source)
                    return None
                else:
                    self._status = CameraStatus.DISCONNECTED
                    logger.warning("Camera stream %s lost signal.", self.camera_id)
                    raise CameraConnectionError(
                        f"Camera stream {self.camera_id} disconnected unexpectedly while reading."
                    )

            if frame.size == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
                raise InvalidFrameError(
                    f"Camera {self.camera_id} returned corrupt/empty frame (shape: {frame.shape})."
                )

            self._frame_count += 1

            # Apply frame sampling rate if configured
            if self.sample_rate_hz is not None and self.sample_rate_hz > 0:
                interval_sec = 1.0 / self.sample_rate_hz
                if (now_mono - self._last_sampled_timestamp) < interval_sec:
                    # Skip frame to adhere to sample rate
                    continue

            self._last_sampled_timestamp = now_mono
            video_time_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)
            fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

            height, width = frame.shape[:2]
            return FramePacket(
                frame=frame,
                frame_index=self._frame_count,
                timestamp_utc=now_utc,
                timestamp_ms=video_time_ms if video_time_ms > 0 else (now_mono * 1000.0),
                camera_id=self.camera_id,
                width=width,
                height=height,
                fps=fps,
            )

    def stream_frames(self) -> Generator[FramePacket, None, None]:
        """Yield sampled FramePackets until stream ends or is stopped.

        Yields:
            FramePacket instances.
        """
        try:
            while True:
                packet = self.read_frame()
                if packet is None:
                    if self._status == CameraStatus.COMPLETED:
                        break
                    continue
                yield packet
        finally:
            self.release()

    def release(self) -> None:
        """Release underlying camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._status != CameraStatus.COMPLETED:
            self._status = CameraStatus.DISCONNECTED
        logger.info("Camera %s resources released.", self.camera_id)
