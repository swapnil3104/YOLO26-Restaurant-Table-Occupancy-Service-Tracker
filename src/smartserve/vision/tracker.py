"""Multi-Object Tracking (MOT) subsystem conforming to BaseTracker.

Implements:
- SimpleByteTracker: Pure-Python/NumPy two-stage IoU and motion association tracker
  (ByteTrack algorithm) for lightweight, deterministic CPU tracking without weight downloads.
- YOLO26Tracker: Native Ultralytics tracking adapter supporting ByteTrack ('bytetrack.yaml')
  and BoT-SORT ('botsort.yaml') engines.
- MockTracker: Deterministic tracker fixture for headless CI/CD and unit testing.

Privacy Notice (Docs/RULES.md Rule 2):
A temporary tracking ID is not a permanent person identity. Track IDs are transient frame-to-frame
association tokens intended solely for table occupancy estimation and dwell timing. They must never
be interpreted as biometric, facial, or permanent customer identities.
"""

import logging
from collections import deque
from enum import StrEnum
from typing import Any

import numpy as np

from smartserve.vision.detector import normalize_coordinates
from smartserve.vision.interfaces import BaseTracker, BoundingBox, Detection

logger = logging.getLogger(__name__)


class TrackState(StrEnum):
    """Lifecycle state of an individual tracked object."""

    NEW = "new"
    ACTIVE = "active"
    LOST = "lost"
    REMOVED = "removed"


def calculate_iou(box_a: BoundingBox, box_b: BoundingBox) -> float:
    """Calculate Intersection-over-Union (IoU) between two bounding boxes.

    Args:
        box_a: First BoundingBox.
        box_b: Second BoundingBox.

    Returns:
        IoU score in range [0.0, 1.0].
    """
    xA = max(box_a.x1, box_b.x1)
    yA = max(box_a.y1, box_b.y1)
    xB = min(box_a.x2, box_b.x2)
    yB = min(box_a.y2, box_b.y2)

    inter_width = max(0.0, xB - xA)
    inter_height = max(0.0, yB - yA)
    inter_area = inter_width * inter_height

    area_a = max(0.0, (box_a.x2 - box_a.x1) * (box_a.y2 - box_a.y1))
    area_b = max(0.0, (box_b.x2 - box_b.x1) * (box_b.y2 - box_b.y1))
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0

    return float(inter_area / union_area)


class TrackedObject:
    """Internal representation of an active, lost, or nascent track."""

    def __init__(
        self,
        track_id: int,
        detection: Detection,
        max_trajectory_length: int = 30,
    ) -> None:
        self.track_id = track_id
        self.class_name = detection.class_name
        self.confidence = detection.confidence
        self.bbox = detection.bbox
        self.state = TrackState.NEW
        self.age = 1
        self.hits = 1
        self.time_since_update = 0
        self.max_trajectory_length = max_trajectory_length

        # Trajectory stores historical bottom-center contact points (cx, y2)
        self.trajectory: deque[tuple[float, float]] = deque(maxlen=max_trajectory_length)
        self.trajectory.append(detection.bbox.bottom_center)

        # Estimated linear velocity (dx, dy) in normalized coords per frame
        self.velocity: tuple[float, float] = (0.0, 0.0)

    def predict(self) -> BoundingBox:
        """Predict bounding box in the next frame based on linear velocity."""
        dx, dy = self.velocity
        new_x1 = max(0.0, min(1.0, self.bbox.x1 + dx))
        new_y1 = max(0.0, min(1.0, self.bbox.y1 + dy))
        new_x2 = max(0.0, min(1.0, self.bbox.x2 + dx))
        new_y2 = max(0.0, min(1.0, self.bbox.y2 + dy))

        return BoundingBox(
            x1=new_x1,
            y1=new_y1,
            x2=new_x2,
            y2=new_y2,
            is_normalized=True,
        )

    def update(self, detection: Detection) -> None:
        """Update track state with a newly matched detection."""
        prev_cx, prev_cy = self.bbox.bottom_center
        new_cx, new_cy = detection.bbox.bottom_center

        # Update velocity with exponential moving average (alpha=0.6)
        inst_dx = new_cx - prev_cx
        inst_dy = new_cy - prev_cy
        self.velocity = (
            0.6 * inst_dx + 0.4 * self.velocity[0],
            0.6 * inst_dy + 0.4 * self.velocity[1],
        )

        self.bbox = detection.bbox
        self.confidence = detection.confidence
        self.class_name = detection.class_name
        self.hits += 1
        self.time_since_update = 0
        self.state = TrackState.ACTIVE
        self.trajectory.append(detection.bbox.bottom_center)

    def mark_missed(self) -> None:
        """Advance time since update when unmatched in the current frame."""
        self.time_since_update += 1
        if self.state == TrackState.ACTIVE:
            self.state = TrackState.LOST


class SimpleByteTracker(BaseTracker):
    """Pure-Python / NumPy implementation of the ByteTrack multi-object tracking algorithm.

    ByteTrack associates both high-confidence and low-confidence detections in two stages:
    1. First stage: Match high-confidence detections with active tracks using IoU.
    2. Second stage: Match remaining low-confidence detections with unmatched tracks to
       recover tracks suffering from partial occlusion or motion blur.
    """

    def __init__(
        self,
        high_threshold: float = 0.50,
        low_threshold: float = 0.15,
        match_threshold: float = 0.25,
        track_buffer: int = 30,
        min_hits: int = 2,
        max_trajectory_length: int = 30,
    ) -> None:
        """Initialize SimpleByteTracker.

        Args:
            high_threshold: Minimum detection confidence for primary association.
            low_threshold: Lower bound detection confidence for secondary association.
            match_threshold: Minimum IoU overlap required to associate a detection with a track.
            track_buffer: Maximum frames to retain lost tracks before permanent removal (~6s at 5Hz).
            min_hits: Consecutive detections required before a track is confirmed and emitted.
            max_trajectory_length: Number of historical contact points to retain.
        """
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_threshold = match_threshold
        self.track_buffer = track_buffer
        self.min_hits = min_hits
        self.max_trajectory_length = max_trajectory_length

        self._next_id: int = 1
        self._tracks: dict[int, TrackedObject] = {}
        self.frame_count: int = 0

    def reset(self) -> None:
        """Reset tracker state, clearing all tracks and restarting track ID counter."""
        self._next_id = 1
        self._tracks.clear()
        self.frame_count = 0

    def get_trajectories(self) -> dict[int, list[tuple[float, float]]]:
        """Return a mapping of active track IDs to their recent trajectory contact points."""
        return {
            track_id: list(track.trajectory)
            for track_id, track in self._tracks.items()
            if track.state in (TrackState.ACTIVE, TrackState.LOST)
        }

    def update(self, detections: list[Detection], frame: Any = None) -> list[Detection]:
        """Associate detections across frames and assign temporary track IDs.

        Args:
            detections: List of Detection instances from the current frame.
            frame: Optional frame image (unused in SimpleByteTracker, preserved for interface).

        Returns:
            List of confirmed Detections with assigned temporary track_id.
        """
        self.frame_count += 1

        # Advance age on all existing tracks
        for track in self._tracks.values():
            track.age += 1

        # Separate detections into high-confidence and low-confidence pools
        high_dets: list[Detection] = []
        low_dets: list[Detection] = []
        for det in detections:
            if det.confidence >= self.high_threshold:
                high_dets.append(det)
            elif det.confidence >= self.low_threshold:
                low_dets.append(det)

        active_track_ids = [
            t_id
            for t_id, track in self._tracks.items()
            if track.state in (TrackState.ACTIVE, TrackState.LOST, TrackState.NEW)
        ]

        # Stage 1: Associate high-confidence detections with active tracks
        unmatched_dets, unmatched_track_ids = self._associate(
            detection_pool=high_dets,
            track_pool_ids=active_track_ids,
            iou_threshold=self.match_threshold,
        )

        # Stage 2: Associate remaining unmatched tracks with low-confidence detections
        unmatched_low_dets, remaining_unmatched_track_ids = self._associate(
            detection_pool=low_dets,
            track_pool_ids=unmatched_track_ids,
            iou_threshold=self.match_threshold * 0.8,  # Slightly lower IoU tolerance for occluded stage
        )

        # Mark remaining unmatched tracks as missed
        for t_id in remaining_unmatched_track_ids:
            track = self._tracks[t_id]
            track.mark_missed()
            if track.time_since_update > self.track_buffer:
                track.state = TrackState.REMOVED

        # Stage 3: Initiate new tracks for unmatched high-confidence detections
        for det in unmatched_dets:
            new_track = TrackedObject(
                track_id=self._next_id,
                detection=det,
                max_trajectory_length=self.max_trajectory_length,
            )
            # If min_hits is 1, instantly activate; otherwise start in NEW state
            if self.min_hits <= 1:
                new_track.state = TrackState.ACTIVE
            self._tracks[self._next_id] = new_track
            self._next_id += 1

        # Clean up permanently removed tracks
        self._tracks = {
            t_id: track for t_id, track in self._tracks.items() if track.state != TrackState.REMOVED
        }

        # Build output detections for all confirmed active tracks in this frame
        output_detections: list[Detection] = []
        for track in self._tracks.values():
            # Only emit if updated this frame and satisfies min_hits
            if track.time_since_update == 0 and track.hits >= self.min_hits:
                out_det = Detection(
                    class_name=track.class_name,
                    confidence=track.confidence,
                    bbox=track.bbox,
                    track_id=track.track_id,
                    metadata={
                        "track_age": track.age,
                        "track_hits": track.hits,
                        "time_since_update": track.time_since_update,
                        "trajectory_length": len(track.trajectory),
                    },
                )
                output_detections.append(out_det)

        return output_detections

    def _associate(
        self,
        detection_pool: list[Detection],
        track_pool_ids: list[int],
        iou_threshold: float,
    ) -> tuple[list[Detection], list[int]]:
        """Greedy IoU association between detections and predicted track positions.

        Args:
            detection_pool: List of candidate Detections.
            track_pool_ids: List of candidate track IDs.
            iou_threshold: Minimum IoU required for matching.

        Returns:
            Tuple of (unmatched_detections, unmatched_track_ids).
        """
        if not detection_pool or not track_pool_ids:
            return list(detection_pool), list(track_pool_ids)

        # Build predicted bounding boxes for tracks
        track_boxes = [self._tracks[t_id].predict() for t_id in track_pool_ids]

        # Compute cost matrix (IoU)
        num_dets = len(detection_pool)
        num_tracks = len(track_pool_ids)
        iou_matrix = np.zeros((num_dets, num_tracks), dtype=np.float32)

        for d_idx, det in enumerate(detection_pool):
            for t_idx, t_box in enumerate(track_boxes):
                iou_matrix[d_idx, t_idx] = calculate_iou(det.bbox, t_box)

        unmatched_dets = set(range(num_dets))
        unmatched_tracks = set(range(num_tracks))

        # Greedy match from highest IoU down to iou_threshold
        while unmatched_dets and unmatched_tracks:
            # Mask out already matched entries
            valid_mask = np.zeros_like(iou_matrix, dtype=bool)
            for d in unmatched_dets:
                for t in unmatched_tracks:
                    valid_mask[d, t] = True

            valid_ious = np.where(valid_mask, iou_matrix, -1.0)
            max_iou = np.max(valid_ious)

            if max_iou < iou_threshold:
                break

            d_match, t_match = np.unravel_index(np.argmax(valid_ious), valid_ious.shape)
            d_idx = int(d_match)
            t_idx = int(t_match)

            matched_track_id = track_pool_ids[t_idx]
            self._tracks[matched_track_id].update(detection_pool[d_idx])

            unmatched_dets.remove(d_idx)
            unmatched_tracks.remove(t_idx)

        unmatched_detection_list = [detection_pool[i] for i in unmatched_dets]
        unmatched_track_id_list = [track_pool_ids[j] for j in unmatched_tracks]

        return unmatched_detection_list, unmatched_track_id_list


class YOLO26Tracker(BaseTracker):
    """Ultralytics YOLO tracking adapter supporting ByteTrack and BoT-SORT engines.

    Wraps the native Ultralytics tracking engine while normalizing coordinate output
    and collecting trajectory breadcrumb histories.
    """

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        tracker_type: str = "bytetrack",
        confidence_threshold: float = 0.45,
        target_classes: list[str] | None = None,
        device: str | None = None,
        max_trajectory_length: int = 30,
    ) -> None:
        """Initialize YOLO26Tracker.

        Args:
            model_path: Path or tag for YOLO weights (e.g., 'yolo11n.pt').
            tracker_type: 'bytetrack' or 'botsort'.
            confidence_threshold: Minimum detection confidence.
            target_classes: Classes to track (default: ['person']).
            device: Compute device ('cpu', 'cuda', 'mps', or None).
            max_trajectory_length: Maximum trajectory points per track ID.
        """
        self.model_path = model_path
        self.tracker_type = tracker_type.lower()
        self.confidence_threshold = float(confidence_threshold)
        self.target_classes = target_classes or ["person"]
        self.device = device
        self.max_trajectory_length = max_trajectory_length

        self.tracker_config = (
            "botsort.yaml" if "bot" in self.tracker_type else "bytetrack.yaml"
        )
        self._model: Any | None = None
        self._trajectories: dict[int, deque[tuple[float, float]]] = {}
        self.frame_count: int = 0

    def _ensure_loaded(self) -> Any:
        """Lazy load the Ultralytics model."""
        if self._model is None:
            try:
                from ultralytics import YOLO

                logger.info("Loading YOLO tracker model %s on device=%s", self.model_path, self.device)
                self._model = YOLO(self.model_path)
            except Exception as e:
                logger.error("Failed to load YOLO model for tracking: %s", e)
                raise RuntimeError(f"YOLO26Tracker model initialization failed: {e}") from e
        return self._model

    def reset(self) -> None:
        """Reset internal tracking state and clear trajectories."""
        self._trajectories.clear()
        self.frame_count = 0
        if self._model is not None:
            try:
                # Reset Ultralytics internal tracker state if available
                if hasattr(self._model, "predictor") and self._model.predictor is not None:
                    if hasattr(self._model.predictor, "trackers"):
                        for trk in self._model.predictor.trackers:
                            if hasattr(trk, "reset"):
                                trk.reset()
            except Exception as e:
                logger.debug("Ultralytics internal tracker reset skipped: %s", e)

    def get_trajectories(self) -> dict[int, list[tuple[float, float]]]:
        """Return copy of active trajectory histories."""
        return {t_id: list(pts) for t_id, pts in self._trajectories.items()}

    def update(self, detections: list[Detection], frame: Any) -> list[Detection]:
        """Track objects through Ultralytics model.track.

        Args:
            detections: Pre-existing detections (optional fallback; model.track re-detects on frame).
            frame: OpenCV image array (numpy.ndarray).

        Returns:
            List of normalized Detections with track_id assigned.
        """
        if frame is None or not isinstance(frame, np.ndarray):
            return []

        model = self._ensure_loaded()
        self.frame_count += 1
        height, width = frame.shape[:2]

        # Execute tracking with persistence across sequential calls
        results = model.track(
            source=frame,
            persist=True,
            tracker=self.tracker_config,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )

        output: list[Detection] = []
        if not results:
            return output

        res = results[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return output

        names = res.names or {}

        for box in boxes:
            cls_id = int(box.cls[0].item()) if box.cls is not None else 0
            cls_name = names.get(cls_id, str(cls_id))

            # Filter for target classes
            if cls_name not in self.target_classes and str(cls_id) not in self.target_classes:
                continue

            conf = float(box.conf[0].item()) if box.conf is not None else 0.0

            # Extract track ID if assigned by tracker
            track_id: int | None = None
            if box.id is not None:
                track_id = int(box.id[0].item())

            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
            norm_bbox = normalize_coordinates(x1, y1, x2, y2, width, height)

            # Record trajectory contact point if track_id is present
            if track_id is not None:
                if track_id not in self._trajectories:
                    self._trajectories[track_id] = deque(maxlen=self.max_trajectory_length)
                self._trajectories[track_id].append(norm_bbox.bottom_center)

            output.append(
                Detection(
                    class_name=cls_name,
                    confidence=conf,
                    bbox=norm_bbox,
                    track_id=track_id,
                    metadata={"tracker": self.tracker_type},
                )
            )

        return output


class MockTracker(BaseTracker):
    """Deterministic synthetic tracker for unit tests and headless environments.

    Assigns stable track IDs based on spatial overlap without requiring model weights.
    """

    def __init__(self, match_iou_threshold: float = 0.20, max_age: int = 15) -> None:
        self.match_iou_threshold = match_iou_threshold
        self.max_age = max_age
        self._next_id: int = 1
        self._active_tracks: dict[int, tuple[BoundingBox, int, deque]] = {}  # id -> (bbox, missed_count, traj)

    def reset(self) -> None:
        """Reset mock tracker."""
        self._next_id = 1
        self._active_tracks.clear()

    def get_trajectories(self) -> dict[int, list[tuple[float, float]]]:
        """Return trajectory histories."""
        return {t_id: list(data[2]) for t_id, data in self._active_tracks.items()}

    def update(self, detections: list[Detection], frame: Any = None) -> list[Detection]:
        """Associate detections with mock track IDs."""
        matched_detections: list[Detection] = []
        matched_track_ids = set()

        for det in detections:
            best_id: int | None = None
            best_iou = self.match_iou_threshold

            for t_id, (t_box, _, _) in self._active_tracks.items():
                if t_id in matched_track_ids:
                    continue
                iou = calculate_iou(det.bbox, t_box)
                if iou >= best_iou:
                    best_iou = iou
                    best_id = t_id

            if best_id is not None:
                matched_track_ids.add(best_id)
                traj = self._active_tracks[best_id][2]
                traj.append(det.bbox.bottom_center)
                self._active_tracks[best_id] = (det.bbox, 0, traj)
                assigned_id = best_id
            else:
                assigned_id = self._next_id
                self._next_id += 1
                matched_track_ids.add(assigned_id)
                new_traj = deque(maxlen=30)
                new_traj.append(det.bbox.bottom_center)
                self._active_tracks[assigned_id] = (det.bbox, 0, new_traj)

            matched_detections.append(
                Detection(
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    track_id=assigned_id,
                    metadata={"mock": True},
                )
            )

        # Increment missed count for unmatched tracks and prune expired
        to_prune = []
        for t_id, (box, missed, traj) in self._active_tracks.items():
            if t_id not in matched_track_ids:
                if missed + 1 > self.max_age:
                    to_prune.append(t_id)
                else:
                    self._active_tracks[t_id] = (box, missed + 1, traj)

        for t_id in to_prune:
            del self._active_tracks[t_id]

        return matched_detections
