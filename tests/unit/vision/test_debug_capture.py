"""
tests/unit/vision/test_debug_capture.py - Stint P4.1.2 Unit Tests.

Verifies DebugScreenshotRecorder creates annotated pre/post step frames without
mutating the input perception frame, prunes oldest episodes beyond max_episodes,
and skips writing frames when sensitive windows are active.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from parasite_ai.vision.debug_capture import DebugScreenshotRecorder


def test_recorder_saves_annotated_pre_and_post_frames(tmp_path: Path) -> None:
    recorder = DebugScreenshotRecorder(base_dir=tmp_path, enabled=True, max_episodes=5)
    ep_dir = recorder.start_episode("Open Calculator and compute 7 * 8")
    assert ep_dir is not None
    assert ep_dir.exists()

    pre = np.zeros((240, 320, 3), dtype=np.uint8)
    post = np.full((240, 320, 3), 64, dtype=np.uint8)
    pre_snapshot = pre.copy()

    saved_path = recorder.save_step_frames(
        pre_frame=pre,
        post_frame=post,
        step_idx=1,
        raw_coords=(100, 120),
        final_coords=(112, 125),
        snap_strategy="uia_point",
        matched_label="Seven",
        optical_tier="ocr_nudge",
        active_window="Calculator",
        action_label="CLICK",
        thought="Click the 7 button",
    )

    # Input frame must remain completely unmutated so bot reasoning never sees overlays
    assert np.array_equal(pre, pre_snapshot)
    assert saved_path == ep_dir / "step_01_pre.jpg"
    assert saved_path.exists() and saved_path.stat().st_size > 0
    post_path = ep_dir / "step_01_post.jpg"
    assert post_path.exists() and post_path.stat().st_size > 0


def test_recorder_prunes_oldest_episodes(tmp_path: Path) -> None:
    recorder = DebugScreenshotRecorder(base_dir=tmp_path, enabled=True, max_episodes=2)
    ep1 = recorder.start_episode("Goal One", episode_id="20261112_000001")
    time.sleep(0.02)
    ep2 = recorder.start_episode("Goal Two", episode_id="20261112_000002")
    time.sleep(0.02)
    ep3 = recorder.start_episode("Goal Three", episode_id="20261112_000003")

    assert ep1 is not None and not ep1.exists()
    assert ep2 is not None and ep2.exists()
    assert ep3 is not None and ep3.exists()


def test_recorder_skips_sensitive_window(tmp_path: Path) -> None:
    recorder = DebugScreenshotRecorder(base_dir=tmp_path, enabled=True, max_episodes=5)
    recorder.start_episode("Sensitive check", episode_id="20261112_000004")

    pre = np.zeros((200, 200, 3), dtype=np.uint8)
    saved = recorder.save_step_frames(
        pre_frame=pre,
        step_idx=1,
        is_sensitive=True,
    )
    assert saved is None
    assert not (tmp_path / "screenshots" / "20261112_000004_sensitive_check" / "step_01_pre.jpg").exists()


def test_recorder_skips_default_data_dir_under_pytest(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_debug_capture.py::test_recorder_skips_default_data_dir_under_pytest")
    recorder = DebugScreenshotRecorder(base_dir="data", enabled=True)
    assert recorder.enabled is False
    assert recorder.start_episode("Should not write") is None


def test_recorder_converts_rgb_to_bgr_and_saves_burst_frames(tmp_path: Path) -> None:
    import cv2

    recorder = DebugScreenshotRecorder(base_dir=tmp_path, enabled=True, max_episodes=5)
    ep_dir = recorder.start_episode("Color and burst", episode_id="20261112_000005")
    assert ep_dir is not None

    # Pure red in RGB: (255, 0, 0)
    pre_rgb = np.zeros((120, 160, 3), dtype=np.uint8)
    pre_rgb[:, :, 0] = 255
    post_rgb = np.zeros((120, 160, 3), dtype=np.uint8)
    post_rgb[:, :, 2] = 255  # Pure blue in RGB

    burst_1 = np.full((120, 160, 3), 100, dtype=np.uint8)
    burst_2 = np.full((120, 160, 3), 200, dtype=np.uint8)

    saved = recorder.save_step_frames(
        pre_frame=pre_rgb,
        post_frame=post_rgb,
        step_idx=1,
        burst_frames=[burst_1, burst_2],
    )
    assert saved is not None
    assert (ep_dir / "step_01_post.jpg").exists()
    assert (ep_dir / "step_01_post_01.jpg").exists()
    assert (ep_dir / "step_01_post_02.jpg").exists()

    # Verify BGR channels in saved post_frame (pure RGB blue -> high B channel, low R channel in BGR)
    loaded_post = cv2.imread(str(ep_dir / "step_01_post.jpg"))
    assert loaded_post is not None
    b, g, r = loaded_post[60, 80]
    assert int(b) > 200 and int(r) < 30

