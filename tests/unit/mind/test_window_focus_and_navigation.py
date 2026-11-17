"""
tests/unit/mind/test_window_focus_and_navigation.py - Stint P2.5.2 Unit Tests.

Verifies:
1. Window focus activation logic in ActionDispatcher._activate_target_window_if_needed.
2. Shell window exclusion (Progman, WorkerW, Shell_TrayWnd) from focus activation.
3. Iconic/minimized window restoration prior to click/type dispatch.
4. Pre-task cursor neutralization helper.
5. Dynamic menu navigation and absence of canned coordinates in UITARS_SYSTEM_PROMPT.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import pytest

from parasite_ai.mind.dual_mind import ActionDispatcher
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT
from parasite_ai.mind.memory import ActionPlan, ActionType
from benchmarks.run_benchmark import reset_cursor_to_neutral


def test_uitars_system_prompt_purges_canned_coordinates() -> None:
    """Verifies that canned taskbar/Start coordinates are completely purged from UITARS_SYSTEM_PROMPT."""
    assert "(24,980)" not in UITARS_SYSTEM_PROMPT
    assert "(24, 980)" not in UITARS_SYSTEM_PROMPT
    assert "(24,1060)" not in UITARS_SYSTEM_PROMPT
    assert "(24, 1060)" not in UITARS_SYSTEM_PROMPT


def test_uitars_system_prompt_contains_dynamic_menu_navigation_rules() -> None:
    """Verifies that dynamic menu navigation rules are explicitly stated in UITARS_SYSTEM_PROMPT."""
    prompt_lower = UITARS_SYSTEM_PROMPT.lower()
    assert "navigate inside it" in prompt_lower
    assert "never click the start button" in prompt_lower
    assert "toggles the menu closed" in prompt_lower
    assert "dynamically" in prompt_lower


def test_activate_target_window_non_windows_safe() -> None:
    """Verifies _activate_target_window_if_needed returns False safely on non-Windows platforms."""
    dispatcher = ActionDispatcher()
    with patch("sys.platform", "linux"):
        assert dispatcher._activate_target_window_if_needed(coords=(500, 500)) is False


def test_activate_target_window_already_foreground() -> None:
    """Verifies that if target window is already the foreground window, it returns True without redundant work."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    with patch("ctypes.windll.user32.WindowFromPoint") as mock_wfp, \
         patch("ctypes.windll.user32.GetAncestor") as mock_ga, \
         patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetForegroundWindow", return_value=12345), \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:
        
        mock_wfp.return_value = 12345
        mock_ga.return_value = 12345

        result = dispatcher._activate_target_window_if_needed(coords=(500, 500))
        assert result is True
        mock_sfw.assert_not_called()


def test_activate_target_window_brings_background_window_to_front() -> None:
    """Verifies that when target coordinates belong to a background window, it brings it to the foreground."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    with patch("ctypes.windll.user32.WindowFromPoint") as mock_wfp, \
         patch("ctypes.windll.user32.GetAncestor") as mock_ga, \
         patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=lambda hwnd, buf, sz: buf.__setattr__("value", "Notepad")), \
         patch("ctypes.windll.user32.IsIconic", return_value=False), \
         patch("ctypes.windll.user32.ShowWindow") as mock_show, \
         patch("ctypes.windll.user32.BringWindowToTop") as mock_top, \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:

        mock_wfp.return_value = 12345
        mock_ga.return_value = 12345

        result = dispatcher._activate_target_window_if_needed(coords=(400, 300))
        assert result is True
        mock_show.assert_called_with(12345, 5)  # SW_SHOW
        mock_top.assert_called_with(12345)
        mock_sfw.assert_called_with(12345)


def test_activate_target_window_restores_minimized_window() -> None:
    """Verifies that an iconic (minimized) background window is restored with SW_RESTORE (9)."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    with patch("ctypes.windll.user32.WindowFromPoint") as mock_wfp, \
         patch("ctypes.windll.user32.GetAncestor") as mock_ga, \
         patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=lambda hwnd, buf, sz: buf.__setattr__("value", "Notepad")), \
         patch("ctypes.windll.user32.IsIconic", return_value=True), \
         patch("ctypes.windll.user32.ShowWindow") as mock_show, \
         patch("ctypes.windll.user32.BringWindowToTop"), \
         patch("ctypes.windll.user32.SetForegroundWindow"):

        mock_wfp.return_value = 12345
        mock_ga.return_value = 12345

        result = dispatcher._activate_target_window_if_needed(coords=(400, 300))
        assert result is True
        mock_show.assert_any_call(12345, 9)  # SW_RESTORE


def test_activate_target_window_excludes_shell_desktop_and_taskbar() -> None:
    """Verifies that shell desktop windows (Progman, WorkerW, Shell_TrayWnd) are excluded from forced foreground activation."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    for shell_cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        with patch("ctypes.windll.user32.WindowFromPoint") as mock_wfp, \
             patch("ctypes.windll.user32.GetAncestor") as mock_ga, \
             patch("ctypes.windll.user32.IsWindow", return_value=True), \
             patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999), \
             patch("ctypes.windll.user32.GetClassNameW", side_effect=lambda hwnd, buf, sz, cls=shell_cls: buf.__setattr__("value", cls)), \
             patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:

            mock_wfp.return_value = 12345
            mock_ga.return_value = 12345

            result = dispatcher._activate_target_window_if_needed(coords=(100, 100))
            assert result is False
            mock_sfw.assert_not_called()


def test_reset_cursor_to_neutral_executes_safely() -> None:
    """Verifies reset_cursor_to_neutral positions the cursor at screen center (960, 540) on Win32."""
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    with patch("ctypes.windll.user32.SetCursorPos") as mock_scp:
        reset_cursor_to_neutral()
        mock_scp.assert_called_once_with(960, 540)


def test_activate_target_window_preserves_open_start_menu_and_flyouts() -> None:
    """
    Verifies that when an open Start Menu, Search flyout, or popup menu is the foreground window (fg_hwnd),
    _activate_target_window_if_needed returns False and does NOT call SetForegroundWindow on a background window.
    """
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    for flyout_cls in ("OpenShell.CMenuContainer", "DV2ControlHost", "Windows.UI.Core.CoreWindow", "#32768"):
        def _mock_class_name(hwnd: int, buf: object, sz: int, f_cls: str = flyout_cls) -> None:
            if hwnd == 99999:
                setattr(buf, "value", f_cls)
            else:
                setattr(buf, "value", "Chrome_WidgetWin_1")

        with patch("ctypes.windll.user32.WindowFromPoint", return_value=12345), \
             patch("ctypes.windll.user32.GetAncestor", return_value=12345), \
             patch("ctypes.windll.user32.IsWindow", return_value=True), \
             patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999), \
             patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_class_name), \
             patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:

            result = dispatcher._activate_target_window_if_needed(coords=(200, 750))
            assert result is False
            mock_sfw.assert_not_called()


def test_activate_target_window_excludes_taskbar_strip_coords() -> None:
    """Verifies that clicking inside the bottom taskbar strip (y >= 1032) never activates a background window."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    with patch("ctypes.windll.user32.WindowFromPoint") as mock_wfp, \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:
        result = dispatcher._activate_target_window_if_needed(coords=(25, 1055))
        assert result is False
        mock_wfp.assert_not_called()
        mock_sfw.assert_not_called()


def test_relocate_window_to_monitor_already_on_monitor1() -> None:
    """Verifies that windows already centered on Monitor 1 (0 <= cx < 1920) are not moved."""
    from parasite_ai.mind.dual_mind import relocate_window_to_monitor
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    def _mock_rect(hwnd: int, byref_r: object) -> bool:
        r = byref_r._obj
        r.left, r.top, r.right, r.bottom = 200, 150, 1000, 750
        return True

    def _mock_cls(hwnd: int, buf: object, sz: int) -> None:
        setattr(buf, "value", "Notepad")

    with patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_cls), \
         patch("ctypes.windll.user32.GetWindowRect", side_effect=_mock_rect), \
         patch("ctypes.windll.user32.SetWindowPos") as mock_swp:
        assert relocate_window_to_monitor(hwnd=12345, target_mon_idx=1) is False
        mock_swp.assert_not_called()


def test_relocate_window_to_monitor_moves_monitor2_window() -> None:
    """Verifies that windows centered on Monitor 2 (cx >= 1920) are moved onto Monitor 1 via SetWindowPos."""
    from parasite_ai.mind.dual_mind import relocate_window_to_monitor
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    def _mock_rect(hwnd: int, byref_r: object) -> bool:
        r = byref_r._obj
        r.left, r.top, r.right, r.bottom = 2000, 150, 2800, 750  # cx = 2400 (Monitor 2)
        return True

    def _mock_cls(hwnd: int, buf: object, sz: int) -> None:
        setattr(buf, "value", "Chrome_WidgetWin_1")

    with patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_cls), \
         patch("ctypes.windll.user32.GetWindowRect", side_effect=_mock_rect), \
         patch("ctypes.windll.user32.SetWindowPos") as mock_swp, \
         patch("ctypes.windll.user32.BringWindowToTop") as mock_bwt, \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:
        assert relocate_window_to_monitor(hwnd=12345, target_mon_idx=1) is True
        mock_swp.assert_called_once()
        args = mock_swp.call_args[0]
        assert args[0] == 12345
        assert args[2] == 100  # new_x on Monitor 1
        assert args[3] == 100  # new_y on Monitor 1
        mock_bwt.assert_called_once_with(12345)
        mock_sfw.assert_called_once_with(12345)


def test_relocate_window_to_monitor_excludes_shell_surfaces() -> None:
    """Verifies that shell background surfaces (Progman, WorkerW, Shell_TrayWnd) are never relocated."""
    from parasite_ai.mind.dual_mind import relocate_window_to_monitor
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    for shell_cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        def _mock_cls(hwnd: int, buf: object, sz: int, s_cls: str = shell_cls) -> None:
            setattr(buf, "value", s_cls)

        with patch("ctypes.windll.user32.IsWindow", return_value=True), \
             patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_cls), \
             patch("ctypes.windll.user32.SetWindowPos") as mock_swp:
            assert relocate_window_to_monitor(hwnd=12345, target_mon_idx=1) is False
            mock_swp.assert_not_called()


def test_relocate_window_to_monitor_exempts_benchmark_runner_title() -> None:
    """Verifies that windows specifically titled with benchmark execution phrases are not relocated."""
    from parasite_ai.mind.dual_mind import relocate_window_to_monitor
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    def _mock_cls(hwnd: int, buf: object, sz: int) -> None:
        setattr(buf, "value", "ConsoleWindowClass")

    def _mock_title(hwnd: int, buf: object, sz: int) -> None:
        setattr(buf, "value", "ParasiteAI Stage P3 Benchmark Runner (UI-TARS-1.5-7B Native 1080p)")

    with patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_cls), \
         patch("ctypes.windll.user32.GetWindowTextW", side_effect=_mock_title), \
         patch("ctypes.windll.user32.SetWindowPos") as mock_swp:
        assert relocate_window_to_monitor(hwnd=12345, target_mon_idx=1) is False
        mock_swp.assert_not_called()


def test_get_effective_active_window_handles_frozen_window_info() -> None:
    """Verifies that frozen WindowInfo dataclass instances are replaced cleanly without raising FrozenInstanceError."""
    from parasite_ai.mind.dual_mind import DualMindPipeline
    from parasite_ai.safety.window_guard import WindowInfo

    frozen_win = WindowInfo(
        hwnd=9876,
        title="External Tool",
        class_name="ToolClass",
        process_name="tool.exe",
        process_path="C:\\tools\\tool.exe",
        pid=1234,
        rect=(2200, 150, 3000, 750),  # On Monitor 2
        is_sensitive=False,
        reason="None",
    )

    mock_wg = MagicMock()
    mock_wg.get_active_window.return_value = frozen_win

    pipeline = DualMindPipeline(brain_manager=MagicMock(), window_guard=mock_wg)
    # Set monitor_index to 1 in pipeline config
    pipeline.config = MagicMock()
    pipeline.config.vision.monitor_index = 1

    with patch("parasite_ai.mind.dual_mind.relocate_window_to_monitor", return_value=True), \
         patch("ctypes.windll.user32.GetForegroundWindow", return_value=9876):
        effective = pipeline._get_effective_active_window()
        assert effective is not None
        # Must have updated rect on Monitor 1 without raising FrozenInstanceError
        assert effective.rect[0] == 100
        assert effective.rect[1] == 100
        assert effective.rect[2] > 100
        assert effective.title == "External Tool"


def test_activate_target_window_skips_when_shell_search_process_is_foreground() -> None:
    """Verifies that active Windows Search/Start processes block background window focus stealing."""
    dispatcher = ActionDispatcher()
    if sys.platform != "win32":
        pytest.skip("Win32 ctypes test")

    def _mock_cls(hwnd: int, buf: object, sz: int) -> None:
        setattr(buf, "value", "ApplicationFrameWindow" if hwnd == 99999 else "Chrome_WidgetWin_1")

    with patch("ctypes.windll.user32.WindowFromPoint", return_value=12345), \
         patch("ctypes.windll.user32.GetAncestor", return_value=12345), \
         patch("ctypes.windll.user32.IsWindow", return_value=True), \
         patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999), \
         patch("ctypes.windll.user32.GetClassNameW", side_effect=_mock_cls), \
         patch.object(ActionDispatcher, "_get_process_name_for_hwnd", return_value="searchapp.exe"), \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_sfw:
        result = dispatcher._activate_target_window_if_needed(coords=(112, 965))
        assert result is False
        mock_sfw.assert_not_called()



