"""
tests/unit/hands/test_reflex.py - Unit test suite for Layer 0.5 ReflexBurstDispatcher.
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from parasite_ai.config import ReflexConfig
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.hands.reflex import ReflexBurstDispatcher, ReflexBurstResult
from parasite_ai.mind.memory import ActionPlan, ActionType


def test_reflex_dispatcher_empty_or_disabled() -> None:
    """Verifies empty bursts return 0ms success and disabled configs abort cleanly."""
    cfg_disabled = ReflexConfig(enabled=False)
    dispatcher_disabled = ReflexBurstDispatcher(config=cfg_disabled)
    plan = ActionPlan(action=ActionType.BURST, burst_actions=[ActionPlan(action=ActionType.CLICK, coordinates=(100, 100))])
    res_dis = dispatcher_disabled.execute_burst(plan)
    assert res_dis.success is False
    assert "disabled" in (res_dis.error or "").lower()

    cfg_enabled = ReflexConfig(enabled=True)
    dispatcher_enabled = ReflexBurstDispatcher(config=cfg_enabled)
    empty_plan = ActionPlan(action=ActionType.BURST, burst_actions=[])
    res_emp = dispatcher_enabled.execute_burst(empty_plan)
    assert res_emp.success is True
    assert res_emp.total_count == 0
    assert res_emp.executed_count == 0


def test_reflex_dispatcher_multi_click_sequence_simulation() -> None:
    """Verifies 4-click burst executes on simulated MouseDriver in rapid succession."""
    mouse = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
    cfg = ReflexConfig(
        enabled=True,
        max_burst_actions=8,
        inter_action_min_ms=5,
        inter_action_max_ms=10,
        reflex_move_duration_ms=10,
        reflex_dwell_ms=10,
    )
    dispatcher = ReflexBurstDispatcher(mouse_driver=mouse, config=cfg)

    # 4 keypad clicks: 7, *, 8, =
    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(100, 200)),
        ActionPlan(action=ActionType.CLICK, coordinates=(150, 200)),
        ActionPlan(action=ActionType.CLICK, coordinates=(200, 200)),
        ActionPlan(action=ActionType.CLICK, coordinates=(250, 200)),
    ]
    burst_plan = ActionPlan(action=ActionType.BURST, burst_actions=sub_plans)

    res = dispatcher.execute_burst(burst_plan)
    assert res.success is True
    assert res.executed_count == 4
    assert res.total_count == 4
    assert res.interrupted is False
    assert res.aborted_early is False
    assert len(res.resolved_coordinates_list) == 4
    assert res.resolved_coordinates_list[0] == (100, 200)
    assert res.resolved_coordinates_list[3] == (250, 200)

    # In simulation mode, mouse should have moved to each coordinate and clicked
    events = [ev["event"] for ev in mouse.simulation_history]
    assert events.count("mouse_down") == 4
    assert events.count("mouse_up") == 4


def test_reflex_dispatcher_centroid_snapper_hook_per_target() -> None:
    """Verifies target_refiner is called for each sub-action coordinate."""
    mouse = MagicMock()
    mouse.click.return_value = True

    refined_records = []

    def mock_refiner(coords, action):
        refined_records.append(coords)
        return ((coords[0] + 5, coords[1] + 5), None)

    cfg = ReflexConfig(inter_action_min_ms=0, inter_action_max_ms=0)
    dispatcher = ReflexBurstDispatcher(
        mouse_driver=mouse,
        config=cfg,
        target_refiner=mock_refiner,
    )

    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(10, 20)),
        ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(30, 40)),
    ]
    burst = ActionPlan(action=ActionType.BURST, burst_actions=sub_plans)

    res = dispatcher.execute_burst(burst)
    assert res.success is True
    assert res.executed_count == 2
    assert refined_records == [(10, 20), (30, 40)]
    assert res.resolved_coordinates_list == [(15, 25), (35, 45)]


def test_reflex_dispatcher_preemption_cancellation() -> None:
    """Verifies cancellation token aborts burst and triggers emergency release in <2ms."""
    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True
    token = threading.Event()

    cfg = ReflexConfig(inter_action_min_ms=50, inter_action_max_ms=50)
    dispatcher = ReflexBurstDispatcher(mouse_driver=mock_mouse, config=cfg)

    # Pre-set token
    token.set()
    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(10, 20)),
        ActionPlan(action=ActionType.CLICK, coordinates=(30, 40)),
    ]
    burst = ActionPlan(action=ActionType.BURST, burst_actions=sub_plans)

    res = dispatcher.execute_burst(burst, cancellation_token=token)
    assert res.success is False
    assert res.interrupted is True
    assert res.executed_count == 0
    mock_mouse.release_all_buttons.assert_called()


def test_reflex_dispatcher_mid_burst_cancellation() -> None:
    """Verifies hardware touch during inter-action pause immediately aborts remainder."""
    mock_mouse = MagicMock()
    token = threading.Event()

    def side_effect_click(*args, **kwargs):
        # Human touches mouse after first click finishes
        token.set()
        return True

    mock_mouse.click.side_effect = side_effect_click

    cfg = ReflexConfig(inter_action_min_ms=20, inter_action_max_ms=30)
    dispatcher = ReflexBurstDispatcher(mouse_driver=mock_mouse, config=cfg)

    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(10, 20)),
        ActionPlan(action=ActionType.CLICK, coordinates=(30, 40)),
        ActionPlan(action=ActionType.CLICK, coordinates=(50, 60)),
    ]
    burst = ActionPlan(action=ActionType.BURST, burst_actions=sub_plans)

    res = dispatcher.execute_burst(burst, cancellation_token=token)
    assert res.success is False
    assert res.interrupted is True
    assert res.executed_count == 1
    assert mock_mouse.click.call_count == 1
    mock_mouse.release_all_buttons.assert_called()


def test_reflex_dispatcher_early_anomaly_abort() -> None:
    """Verifies target window crash or popup interruption triggers early anomaly abort."""
    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    call_count = 0

    def mock_anomaly():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            return "Target window unexpectedly vanished or crashed"
        return None

    cfg = ReflexConfig(inter_action_min_ms=0, inter_action_max_ms=0, abort_on_window_change=True)
    dispatcher = ReflexBurstDispatcher(
        mouse_driver=mock_mouse,
        config=cfg,
        anomaly_check_fn=mock_anomaly,
    )

    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(10, 20)),
        ActionPlan(action=ActionType.CLICK, coordinates=(30, 40)),
        ActionPlan(action=ActionType.CLICK, coordinates=(50, 60)),
    ]
    burst = ActionPlan(action=ActionType.BURST, burst_actions=sub_plans)

    res = dispatcher.execute_burst(burst)
    assert res.success is False
    assert res.aborted_early is True
    assert "unexpectedly vanished" in (res.abort_reason or "")
    assert res.executed_count == 1
    assert mock_mouse.click.call_count == 1
