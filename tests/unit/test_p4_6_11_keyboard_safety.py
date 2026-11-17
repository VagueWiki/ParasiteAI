"""Targeted unit tests for Stint P4.6.11 (0.4.6.11) keyboard lockup prevention & test hardware isolation."""

from __future__ import annotations

import ctypes
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from parasite_ai.config import AppConfig, AppMemoryConfig
from parasite_ai.hands.keyboard import (
    ALL_MODIFIER_AND_LOCK_VKS,
    INPUT_KEYBOARD,
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    KeyboardDriver,
    MockInputBackend,
    VK_LWIN,
    VK_MENU,
    VK_RWIN,
    VK_TAB,
    Win32InputBackend,
)

VK_F4 = 0x73
from parasite_ai.mind.app_memory import AppMemory
from parasite_ai.mind.dual_mind import ActionDispatcher, DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.parasite_protocol import ParasitePlan, ParasitePlanStep
from parasite_ai.mind.plan import StepDirective, StepIntent
from parasite_ai.safety.interrupt_guard import InterruptGuard, LLKHF_UP, VK_CONTROL
from parasite_ai.safety.panic import PanicManager


def test_atomic_hotkey_dispatch_uses_single_send_inputs_and_extended_flags() -> None:
    """hotkey('win', 'r') and hotkey('alt', 'f4') must dispatch atomically with KEYEVENTF_EXTENDEDKEY."""
    backend = MockInputBackend()
    calls: list[int] = []
    orig_send = backend.send_inputs

    def _counting_send(inputs):
        calls.append(len(inputs))
        return orig_send(inputs)

    backend.send_inputs = _counting_send  # type: ignore[method-assign]
    driver = KeyboardDriver(backend=backend)

    assert driver.hotkey("win", "r") is True
    assert calls == [4]
    assert len(driver._held_keys) == 0

    win_down, r_down, r_up, win_up = backend.events
    assert win_down.vk == VK_LWIN
    assert (win_down.flags & KEYEVENTF_EXTENDEDKEY) != 0
    assert (win_down.flags & KEYEVENTF_KEYUP) == 0
    assert r_down.vk == ord("R")
    assert r_up.vk == ord("R") and (r_up.flags & KEYEVENTF_KEYUP) != 0
    assert win_up.vk == VK_LWIN
    assert (win_up.flags & (KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)) == (
        KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP
    )

    backend.clear()
    calls.clear()
    assert driver.hotkey("alt", "f4") is True
    assert calls == [4]
    assert [e.vk for e in backend.events] == [VK_MENU, VK_F4, VK_F4, VK_MENU]
    assert len(driver._held_keys) == 0

    # Exception during send_inputs still cleans up _held_keys and triggers emergency release
    release_calls: list[int] = []
    driver.emergency_release_keys = lambda: release_calls.append(1)  # type: ignore[method-assign]

    def _raising_send(_inputs):
        raise RuntimeError("boom")

    backend.send_inputs = _raising_send  # type: ignore[method-assign]
    try:
        driver.hotkey("ctrl", "a")
    except RuntimeError:
        pass
    assert len(driver._held_keys) == 0
    assert release_calls == [1]


def test_state_checked_emergency_release_on_win32_backend_and_panic_manager() -> None:
    """Win32InputBackend emergency release only releases depressed keys (including Win & Tab) without pulsing idle Alt."""
    fake_user32 = MagicMock()
    depressed_vks = {VK_LWIN, VK_TAB}
    fake_user32.GetAsyncKeyState.side_effect = lambda vk: 0x8000 if vk in depressed_vks else 0
    fake_user32.GetKeyState.return_value = 0
    fake_user32.MapVirtualKeyW.return_value = 0x5B
    fake_user32.SendInput.side_effect = lambda n, arr, sz: n

    with patch("ctypes.windll.user32", fake_user32):
        win_backend = Win32InputBackend()
        driver = KeyboardDriver(backend=win_backend)

        sent_batches: list[list[int]] = []
        orig_send_inputs = win_backend.send_inputs

        def _capture_send(inputs):
            sent_batches.append([inp.u.ki.wVk for inp in inputs])
            return len(inputs)

        win_backend.send_inputs = _capture_send  # type: ignore[method-assign]
        driver.emergency_release_keys()

        assert len(sent_batches) == 1
        released_vks = set(sent_batches[0])
        assert released_vks == {VK_LWIN, VK_TAB}
        assert VK_MENU not in released_vks

    # MockInputBackend with PanicManager must include VK_LWIN, VK_RWIN, VK_TAB on release
    mock_backend = MockInputBackend()
    panic = PanicManager(backend=mock_backend)
    panic.emergency_hardware_release()
    released_mock_vks = {
        ev.vk for ev in mock_backend.events if ev.type == INPUT_KEYBOARD and (ev.flags & KEYEVENTF_KEYUP)
    }
    assert VK_LWIN in released_mock_vks
    assert VK_RWIN in released_mock_vks
    assert VK_TAB in released_mock_vks
    assert set(ALL_MODIFIER_AND_LOCK_VKS).issubset(released_mock_vks)


def test_action_dispatcher_blocks_destructive_hotkeys_on_protected_shell_or_off_monitor() -> None:
    """ActionDispatcher refuses alt+f4/win+down into runner process, Desktop shell, or Monitor 2."""
    cfg = AppConfig()
    cfg.vision.monitor_index = 1
    mock_kbd = MagicMock()
    dispatcher = ActionDispatcher(keyboard_driver=mock_kbd, config=cfg)

    def _build_user32(*, fg_hwnd: int, cls_name: str, title: str, pid: int, rect: tuple[int, int, int, int]):
        u32 = MagicMock()
        u32.GetForegroundWindow.return_value = fg_hwnd
        u32.GetClassNameW.side_effect = lambda h, buf, n: setattr(buf, "value", cls_name) or len(cls_name)
        u32.GetWindowTextW.side_effect = lambda h, buf, n: setattr(buf, "value", title) or len(title)

        def _pid_proc(h, ptr):
            ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ulong)).contents.value = pid
            return 1

        def _rect_proc(h, ptr):
            r = ctypes.cast(ptr, ctypes.POINTER(ctypes.wintypes.RECT)).contents
            r.left, r.top, r.right, r.bottom = rect
            return True

        u32.GetWindowThreadProcessId.side_effect = _pid_proc
        u32.GetWindowRect.side_effect = _rect_proc
        return u32

    # 1. Protected runner process (own PID / benchmark runner title)
    u32_runner = _build_user32(
        fg_hwnd=101,
        cls_name="ConsoleWindowClass",
        title="ParasiteAI Stage P4 Benchmark Runner",
        pid=os.getpid(),
        rect=(100, 100, 900, 700),
    )
    with patch("ctypes.windll.user32", u32_runner):
        res_close = dispatcher.dispatch(ActionPlan(action=ActionType.HOTKEY, keys=["alt", "f4"]), [])
        assert res_close.success is False
        assert "protected" in (res_close.error or "").lower()
        mock_kbd.hotkey.assert_not_called()

    # 2. Windows Desktop shell (Progman)
    u32_shell = _build_user32(
        fg_hwnd=102,
        cls_name="Progman",
        title="Program Manager",
        pid=999999,
        rect=(0, 0, 1920, 1080),
    )
    with patch("ctypes.windll.user32", u32_shell):
        res_min = dispatcher.dispatch(ActionPlan(action=ActionType.HOTKEY, keys=["win", "down"]), [])
        assert res_min.success is False
        assert "shell" in (res_min.error or "").lower()
        mock_kbd.hotkey.assert_not_called()

    # 3. Off-monitor foreground window (Monitor 2: x >= 1920)
    u32_offmon = _build_user32(
        fg_hwnd=103,
        cls_name="Chrome_WidgetWin_1",
        title="IDE Window",
        pid=999999,
        rect=(2000, 50, 3400, 1000),
    )
    with patch("ctypes.windll.user32", u32_offmon), \
         patch("parasite_ai.vision.capture.get_monitor_bounds", return_value=(0, 0, 1920, 1080)):
        res_off = dispatcher.dispatch(ActionPlan(action=ActionType.HOTKEY, keys=["alt", "f4"]), [])
        assert res_off.success is False
        assert "off-monitor" in (res_off.error or "").lower()
        mock_kbd.hotkey.assert_not_called()

        # Global Win+R launch shortcut remains permitted
        mock_kbd.hotkey.return_value = True
        res_win_r = dispatcher.dispatch(ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"]), [])
        assert res_win_r.success is True
        mock_kbd.hotkey.assert_called_once_with("win", "r", cancellation_token=None)


def test_interrupt_guard_rising_edge_callback_and_keyup_handling() -> None:
    """InterruptGuard invokes callback once on rising edge and ignores key-up for touch triggers."""
    cb = MagicMock()
    guard = InterruptGuard(cooldown_seconds=1.0, on_interrupt_callback=cb)

    # Physical key-up alone must NOT signal physical touch
    guard.simulate_event("keyboard", flags=LLKHF_UP, vk_code=VK_CONTROL)
    assert cb.call_count == 0
    assert not guard.is_interrupted()

    # Physical Ctrl down -> sets panic modifier tracking AND signals rising-edge touch once
    guard.simulate_event("keyboard", flags=0, vk_code=VK_CONTROL)
    assert cb.call_count == 1
    assert guard.panic_manager._is_ctrl_down is True

    # Physical Ctrl up -> clears PanicManager modifier state without invoking interrupt callback again
    guard.simulate_event("keyboard", flags=LLKHF_UP, vk_code=VK_CONTROL)
    assert guard.panic_manager._is_ctrl_down is False
    assert cb.call_count == 1

    # Repeated mouse move while already interrupted must NOT re-fire callback until re-armed
    guard.simulate_event("mouse", flags=0, pt=(500, 500))
    assert cb.call_count == 1
    assert guard.interrupt_count == 2


def test_dual_mind_skips_farmed_close_plan_and_suppresses_fulfilled_teardown_guidance(tmp_path) -> None:
    """Single-window teardown goals skip Layer 1.5 farmed plans and suppress stale Alt+F4 guidance once closed."""
    db = tmp_path / "teardown_guard.db"
    mem = AppMemory(AppMemoryConfig(enabled=True, db_path=db), app_version="0.4.6.11")
    close_plan = ParasitePlan(
        selected_program="notepad.exe",
        rationale="Close Notepad with Alt+F4.",
        steps=[
            ParasitePlanStep(
                intent=StepIntent.CONCLUDE,
                description="Send Alt+F4 to close Notepad",
                success_criteria="Notepad closed",
                action=StepDirective(verb="HOTKEY", keys=["alt", "f4"]),
            )
        ],
    )
    pid = mem.store_farmed_plan("Close Notepad", close_plan)
    mem.record_outcome(pid, success=True)

    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = ("Already closed.", ActionPlan(action=ActionType.DONE, reasoning="Done"))

    wg = MagicMock()
    wg.is_safe_to_operate.return_value = True
    wg.get_active_window_info.return_value = SimpleNamespace(
        title="Program Manager", process_name="explorer.exe", rect=(0, 0, 1920, 1080)
    )
    wg.get_active_window.return_value = wg.get_active_window_info.return_value

    cfg = AppConfig(app_memory=AppMemoryConfig(enabled=True, db_path=db))
    pipe = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        window_guard=wg,
        config=cfg,
        app_memory=mem,
    )

    plan = pipe._initialize_or_update_plan("Close Notepad")
    assert pipe._episode_plan_source == "local"
    assert pipe._episode_farmed_plan_id is None

    # Even if an active plan existed with a strategic Alt+F4 step, fulfilled teardown suppresses guidance
    pipe.active_plan = close_plan.to_living_plan("Close Notepad")
    pipe._episode_expected_process = "notepad.exe"
    pipe.goal_verifier = MagicMock()
    pipe.goal_verifier.build_working_memory_snapshot.return_value = (
        "- Target Application Status: notepad is CLOSED / TERMINATED (0 open windows). Teardown goal is fulfilled -> Emit DONE."
    )
    pipe.goal_verifier.verify_goal_state.return_value = SimpleNamespace(verified=True, reason="Closed")

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    pipe.step(user_goal="Close Notepad", screen_frame=frame, grounded_elements=[])
    brain.generate_cua_step.assert_called_once()
    wm_passed = brain.generate_cua_step.call_args.kwargs["working_memory_context"]
    assert "Strategic Advisor Guidance" not in wm_passed
    mem.close()
