"""Unit and integration tests for multi-object tracking subsystem."""

import numpy as np
import pytest

from smartserve.vision.interfaces import BaseTracker, BoundingBox, Detection
from smartserve.vision.tracker import (
    MockTracker,
    SimpleByteTracker,
    TrackedObject,
    TrackState,
    calculate_iou,
)
from smartserve.vision.visualizer import draw_tracking_overlay, get_track_color


def test_calculate_iou_scenarios():
    """Test IoU calculation across identical, separated, and partial overlap boxes."""
    # Identical boxes
    box_a = BoundingBox(0.2, 0.2, 0.4, 0.4)
    box_b = BoundingBox(0.2, 0.2, 0.4, 0.4)
    assert pytest.approx(calculate_iou(box_a, box_b), rel=1e-3) == 1.0

    # Non-overlapping boxes
    box_c = BoundingBox(0.6, 0.6, 0.8, 0.8)
    assert calculate_iou(box_a, box_c) == 0.0

    # Half overlap: 50% overlap along one dimension
    # box_a: [0.2, 0.2, 0.4, 0.4], area = 0.04
    # box_d: [0.3, 0.2, 0.5, 0.4], area = 0.04
    # intersection: [0.3, 0.2, 0.4, 0.4], area = 0.02
    # union = 0.04 + 0.04 - 0.02 = 0.06 -> IoU = 0.02 / 0.06 = 0.3333
    box_d = BoundingBox(0.3, 0.2, 0.5, 0.4)
    assert pytest.approx(calculate_iou(box_a, box_d), abs=1e-3) == 0.3333


def test_tracked_object_lifecycle():
    """Verify TrackedObject prediction, update, and miss lifecycle."""
    init_det = Detection("person", 0.90, BoundingBox(0.1, 0.1, 0.2, 0.3))
    obj = TrackedObject(track_id=42, detection=init_det, max_trajectory_length=10)

    assert obj.track_id == 42
    assert obj.state == TrackState.NEW
    assert obj.hits == 1
    assert len(obj.trajectory) == 1

    # Update with shifted position
    next_det = Detection("person", 0.85, BoundingBox(0.12, 0.1, 0.22, 0.3))
    obj.update(next_det)

    assert obj.state == TrackState.ACTIVE
    assert obj.hits == 2
    assert obj.time_since_update == 0
    assert len(obj.trajectory) == 2

    # Miss frame
    obj.mark_missed()
    assert obj.state == TrackState.LOST
    assert obj.time_since_update == 1


def test_simple_bytetracker_single_moving_person():
    """Verify a person moving horizontally maintains a stable track ID."""
    tracker = SimpleByteTracker(
        high_threshold=0.5,
        low_threshold=0.2,
        match_threshold=0.2,
        min_hits=1,
    )

    assigned_ids = []
    # Simulate a person walking from x=0.1 to x=0.5 in steps of 0.05
    for step in range(8):
        x1 = 0.10 + step * 0.04
        x2 = x1 + 0.15
        det = Detection(
            class_name="person",
            confidence=0.85,
            bbox=BoundingBox(x1, 0.20, x2, 0.70),
        )
        tracked = tracker.update([det])
        assert len(tracked) == 1
        assigned_ids.append(tracked[0].track_id)

    # Track ID must remain identical throughout the entire trajectory
    assert len(set(assigned_ids)) == 1
    assert assigned_ids[0] == 1

    trajectories = tracker.get_trajectories()
    assert 1 in trajectories
    assert len(trajectories[1]) == 8


def test_simple_bytetracker_occlusion_tolerance():
    """Verify track ID is preserved across short occlusion (disappears 2 frames, returns)."""
    tracker = SimpleByteTracker(
        high_threshold=0.5,
        low_threshold=0.2,
        match_threshold=0.15,
        track_buffer=5,  # 5 frames grace
        min_hits=1,
    )

    box = BoundingBox(0.3, 0.3, 0.45, 0.65)
    det = Detection("person", 0.88, box)

    # Frame 1: Person appears
    t1 = tracker.update([det])
    assert len(t1) == 1
    original_id = t1[0].track_id

    # Frame 2 & 3: Person temporarily occluded (empty detection list)
    t2 = tracker.update([])
    t3 = tracker.update([])
    assert len(t2) == 0
    assert len(t3) == 0

    # Frame 4: Person reappears near previous position
    reappeared_det = Detection("person", 0.80, BoundingBox(0.32, 0.3, 0.47, 0.65))
    t4 = tracker.update([reappeared_det])
    assert len(t4) == 1
    assert t4[0].track_id == original_id, "Track ID must be preserved across short occlusion"


def test_simple_bytetracker_track_expiration():
    """Verify track expires when missing for longer than track_buffer, getting a new ID later."""
    tracker = SimpleByteTracker(
        high_threshold=0.5,
        match_threshold=0.2,
        track_buffer=3,  # Short buffer: 3 frames
        min_hits=1,
    )

    det = Detection("person", 0.90, BoundingBox(0.2, 0.2, 0.3, 0.5))
    t1 = tracker.update([det])
    id1 = t1[0].track_id

    # Missing for 4 frames (> track_buffer of 3)
    for _ in range(4):
        tracker.update([])

    # Person reappears: should be treated as a new track ID
    t_new = tracker.update([det])
    assert len(t_new) == 1
    id2 = t_new[0].track_id
    assert id2 != id1, "Expired track must yield a new track ID upon return"


def test_simple_bytetracker_low_confidence_recovery():
    """Verify ByteTrack stage 2 recovers a track even when detection confidence drops."""
    tracker = SimpleByteTracker(
        high_threshold=0.6,
        low_threshold=0.2,
        match_threshold=0.2,
        min_hits=1,
    )

    # Frame 1: Strong detection
    det_strong = Detection("person", 0.85, BoundingBox(0.2, 0.2, 0.35, 0.6))
    t1 = tracker.update([det_strong])
    assert len(t1) == 1
    t_id = t1[0].track_id

    # Frame 2: Confidence drops due to partial occlusion / lighting (e.g. 0.30)
    det_weak = Detection("person", 0.30, BoundingBox(0.21, 0.2, 0.36, 0.6))
    t2 = tracker.update([det_weak])
    assert len(t2) == 1
    assert t2[0].track_id == t_id, "Low confidence detection must be recovered via ByteTrack stage 2"


def test_tracker_reset():
    """Verify tracker reset clears internal state and restarts track IDs."""
    tracker = SimpleByteTracker(min_hits=1)
    det = Detection("person", 0.9, BoundingBox(0.1, 0.1, 0.2, 0.3))

    t1 = tracker.update([det])
    assert t1[0].track_id == 1

    tracker.reset()
    assert len(tracker.get_trajectories()) == 0

    t2 = tracker.update([det])
    assert t2[0].track_id == 1, "Track ID counter must reset back to 1"


def test_mock_tracker_interface():
    """Verify MockTracker adheres to BaseTracker contract and preserves IDs."""
    tracker = MockTracker(match_iou_threshold=0.2)
    assert isinstance(tracker, BaseTracker)

    det1 = Detection("person", 0.9, BoundingBox(0.4, 0.4, 0.6, 0.8))
    out1 = tracker.update([det1])
    assert len(out1) == 1
    assert out1[0].track_id == 1

    det2 = Detection("person", 0.85, BoundingBox(0.42, 0.41, 0.62, 0.81))
    out2 = tracker.update([det2])
    assert len(out2) == 1
    assert out2[0].track_id == 1


def test_draw_tracking_overlay_rendering():
    """Verify draw_tracking_overlay executes without error and renders trajectory ribbons."""
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tracked_dets = [
        Detection(
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(0.2, 0.2, 0.4, 0.7),
            track_id=7,
        )
    ]
    trajectories = {
        7: [(0.3, 0.5), (0.3, 0.6), (0.3, 0.7)],
    }

    result = draw_tracking_overlay(
        frame=dummy_frame,
        detections=tracked_dets,
        trajectories=trajectories,
        show_trajectories=True,
        fps=5.0,
        camera_id="CAM-01",
    )

    assert result is not None
    assert result.shape == (480, 640, 3)
    # Check that color was modified from pure black
    assert np.any(result > 0)


def test_get_track_color():
    """Verify track color assignment is deterministic and handles None."""
    c_none = get_track_color(None)
    assert isinstance(c_none, tuple)
    assert len(c_none) == 3

    c1 = get_track_color(1)
    c1_again = get_track_color(1)
    assert c1 == c1_again
