"""
tests/test_memory.py - Automated Unit & Stress Tests for Episodic Working Memory.

Tests vectorized pixel diff calculation, 64-bit dHash perceptual hashing,
bounded ring-buffer eviction, 3-strike failure loop detection, prompt formatting,
and multi-threaded concurrent recording.
"""

from __future__ import annotations

import concurrent.futures
import numpy as np
import pytest

from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    EpisodicMemory,
    StepRecord,
    compute_dhash,
    compute_pixel_diff,
    hamming_distance,
)


def test_compute_pixel_diff_identical_images() -> None:
    frame1 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame2 = np.zeros((200, 200, 3), dtype=np.uint8)
    diff = compute_pixel_diff(frame1, frame2)
    assert diff == 0.0


def test_compute_pixel_diff_completely_inverted() -> None:
    frame1 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame2 = np.full((200, 200, 3), 255, dtype=np.uint8)
    diff = compute_pixel_diff(frame1, frame2)
    assert diff == 1.0


def test_compute_pixel_diff_subregion_change() -> None:
    # 200 x 200 = 40,000 pixels.
    # Change a 20 x 100 region = 2,000 pixels -> 2000 / 40000 = 0.05 (5%)
    frame1 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame2 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame2[0:20, 0:100, :] = 255
    diff = compute_pixel_diff(frame1, frame2)
    assert diff == pytest.approx(0.05, abs=0.001)


def test_compute_pixel_diff_noise_below_threshold() -> None:
    frame1 = np.zeros((200, 200, 3), dtype=np.uint8)
    # Variation of 10 is below default threshold of 15
    frame2 = np.full((200, 200, 3), 10, dtype=np.uint8)
    diff = compute_pixel_diff(frame1, frame2, channel_threshold=15)
    assert diff == 0.0


def test_compute_dhash_determinism_and_distance() -> None:
    # Synthetic image with horizontal gradient
    arr1 = np.zeros((100, 100, 3), dtype=np.uint8)
    for col in range(100):
        arr1[:, col, :] = col * 2

    hash1 = compute_dhash(arr1)
    hash1_repeat = compute_dhash(arr1)
    assert hash1 == hash1_repeat
    assert len(hash1) == 16
    assert hamming_distance(hash1, hash1_repeat) == 0

    # Inverted gradient image
    arr2 = np.zeros((100, 100, 3), dtype=np.uint8)
    for col in range(100):
        arr2[:, col, :] = (99 - col) * 2

    hash2 = compute_dhash(arr2)
    dist = hamming_distance(hash1, hash2)
    assert dist > 0


def test_episodic_memory_capacity_ring_buffer() -> None:
    mem = EpisodicMemory(capacity=10)

    # Insert 15 steps
    for i in range(15):
        mem.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=i + 1),
            success=True,
            screen_diff=0.05,
        )

    assert len(mem) == 10
    recent = mem.get_recent_history(10)
    assert len(recent) == 10
    # First retained item should be step_id 6, last step_id 15
    assert recent[0].step_id == 6
    assert recent[-1].step_id == 15


def test_episodic_memory_step_indexing() -> None:
    mem = EpisodicMemory(capacity=5)
    for i in range(8):
        rec = mem.record_step(
            action=ActionPlan(action=ActionType.WAIT),
            success=True,
            screen_diff=0.0,
        )
        assert rec.step_id == i + 1


def test_3_strike_loop_detector_triggers_on_third_strike() -> None:
    mem = EpisodicMemory(capacity=20, strike_limit=3, screen_diff_threshold=0.02)

    # Strike 1: click with diff = 0.001 (< 0.02)
    rec1 = mem.record_step(
        action=ActionPlan(action=ActionType.CLICK, target_id=1),
        success=True,
        screen_diff=0.001,
    )
    assert rec1.is_strike is True
    assert rec1.consecutive_strikes == 1
    assert mem.is_in_loop() is False

    # Strike 2: type with diff = 0.000 (< 0.02)
    rec2 = mem.record_step(
        action=ActionPlan(action=ActionType.TYPE, text="hello"),
        success=True,
        screen_diff=0.000,
    )
    assert rec2.is_strike is True
    assert rec2.consecutive_strikes == 2
    assert mem.is_in_loop() is False

    # Strike 3: hotkey with failed execution (success=False)
    rec3 = mem.record_step(
        action=ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"]),
        success=False,
        screen_diff=0.000,
    )
    assert rec3.is_strike is True
    assert rec3.consecutive_strikes == 3
    # 3 strikes reached -> loop detector is tripped!
    assert mem.is_in_loop() is True


def test_strike_counter_resets_on_successful_screen_diff() -> None:
    mem = EpisodicMemory(capacity=20, strike_limit=3, screen_diff_threshold=0.02)

    # 2 strikes
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    assert mem.get_consecutive_strikes() == 2

    # 3rd action succeeds with screen_diff 0.04 (>= 0.02)
    rec3 = mem.record_step(
        action=ActionPlan(action=ActionType.CLICK, target_id=2),
        success=True,
        screen_diff=0.04,
    )
    assert rec3.is_strike is False
    assert rec3.consecutive_strikes == 0
    assert mem.get_consecutive_strikes() == 0
    assert mem.is_in_loop() is False


def test_non_interactive_actions_do_not_incur_strikes() -> None:
    mem = EpisodicMemory(capacity=20, strike_limit=3)

    # 1 strike from a click
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    assert mem.get_consecutive_strikes() == 1

    # WAIT action with diff=0.0 does NOT count as strike and does not reset
    rec_wait = mem.record_step(ActionPlan(action=ActionType.WAIT, wait_ms=500), success=True, screen_diff=0.0)
    assert rec_wait.is_strike is False
    assert mem.get_consecutive_strikes() == 1

    # DONE action with diff=0.0
    rec_done = mem.record_step(ActionPlan(action=ActionType.DONE), success=True, screen_diff=0.0)
    assert rec_done.is_strike is False
    assert mem.get_consecutive_strikes() == 1


def test_format_for_prompt_includes_warnings_and_history() -> None:
    mem = EpisodicMemory(capacity=20, strike_limit=3)

    mem.record_step(
        action=ActionPlan(action=ActionType.CLICK, target_id=3),
        success=True,
        screen_diff=0.001,
    )
    mem.record_step(
        action=ActionPlan(action=ActionType.CLICK, target_id=3),
        success=True,
        screen_diff=0.001,
    )
    mem.record_step(
        action=ActionPlan(action=ActionType.CLICK, target_id=3),
        success=True,
        screen_diff=0.001,
    )

    prompt_str = mem.format_for_prompt(n=3)
    assert "### Recent Action History & Visual Outcomes:" in prompt_str
    assert "CLICK target [#3]" in prompt_str
    assert "⚠️ CRITICAL WARNING: Detected cognitive failure loop!" in prompt_str


def test_thread_safety_concurrent_recording() -> None:
    mem = EpisodicMemory(capacity=100)
    num_threads = 10
    steps_per_thread = 50

    def record_batch(thread_idx: int) -> None:
        for s in range(steps_per_thread):
            mem.record_step(
                action=ActionPlan(action=ActionType.CLICK, target_id=thread_idx),
                success=True,
                screen_diff=0.05,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(record_batch, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Total recorded = 500 steps, buffer capped at 100
    assert len(mem) == 100
    history = mem.get_recent_history(100)
    assert len(history) == 100
    # Step IDs must be strictly increasing
    step_ids = [r.step_id for r in history]
    assert step_ids == sorted(step_ids)
    assert len(set(step_ids)) == 100
