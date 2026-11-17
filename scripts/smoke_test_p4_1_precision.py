"""
scripts/smoke_test_p4_1_precision.py - Stint P4.1 / P4.1.1 Live Desktop Hardware Smoke Probe.

MUST be run in an interactive Windows desktop session (via run_smoke_probe_p4_1.bat).
Launches Windows Calculator, relocates it to the target monitor if needed, intentionally
offsets coordinates toward button borders of keys '7', '8', '9', dispatches clicks via
ActionDispatcher (exercising both UIA-bbox and CUA O(1) uia_point snapping + PreClickOpticalVerifier
+ HumanCurve MouseDriver), and verifies '789' via Win32 UIA CalculatorResults.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parasite_ai.config import load_config
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.main import setup_logging
from parasite_ai.mind.dual_mind import ActionDispatcher, relocate_window_to_monitor
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder

logger = logging.getLogger(__name__)


def _emit(msg: str, level: str = "info") -> None:
    print(msg)
    if level == "error":
        logger.error(msg)
    else:
        logger.info(msg)


def _find_and_relocate_calculator(target_monitor_index: int) -> bool:
    """Locates the Windows Calculator UWP window and ensures it resides on target monitor."""
    if sys.platform != "win32":
        return False
    try:
        import uiautomation as auto

        calc_win = auto.WindowControl(searchDepth=2, ClassName="ApplicationFrameWindow", SubName="Calculator")
        if not calc_win.Exists(0, 0):
            calc_win = auto.WindowControl(searchDepth=2, SubName="Calculator")
        if calc_win.Exists(0, 0):
            hwnd = getattr(calc_win, "NativeWindowHandle", 0)
            if hwnd:
                relocate_window_to_monitor(int(hwnd), target_monitor_index)
            try:
                calc_win.SetActive()
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def _read_calculator_display() -> str:
    """Reads the UWP Calculator display text via AutomationId='CalculatorResults'."""
    if sys.platform != "win32":
        return ""
    try:
        import uiautomation as auto

        calc_win = auto.WindowControl(searchDepth=2, ClassName="ApplicationFrameWindow")
        if calc_win.Exists(0, 0):
            res_ctrl = calc_win.TextControl(searchDepth=6, AutomationId="CalculatorResults")
            if res_ctrl.Exists(0, 0):
                return (res_ctrl.Name or "").replace(",", "").strip()
    except Exception:
        pass
    return ""


def _extract_digit_buttons(elements: list) -> dict:
    """Finds UIA Button controls for digits '7', '8', '9'."""
    name_map = {"7": ("7", "seven"), "8": ("8", "eight"), "9": ("9", "nine")}
    digits = {}
    for d, aliases in name_map.items():
        match = next(
            (
                e
                for e in elements
                if e.role == "Button" and (e.label or "").strip().lower() in aliases
            ),
            None,
        )
        if match is not None:
            digits[d] = match
    return digits


def main() -> int:
    cfg = load_config()
    log_path = setup_logging(cfg)
    _emit(f"[P4.1 SMOKE] Logging initialized -> {log_path}")

    capturer = ScreenCapture(
        backend=cfg.vision.capture_backend,
        monitor_index=cfg.vision.monitor_index,
    )
    grounder = ScreenGrounder(config=cfg.vision, capturer=capturer)
    mouse = MouseDriver(config=cfg.hands.mouse, preview_reticle_ms=0, simulation_mode=False)
    dispatcher = ActionDispatcher(mouse_driver=mouse, config=cfg, enable_uia_point_probe=True)

    guard = InterruptGuard(config=cfg.safety)
    guard.start()

    _emit("[P4.1 SMOKE] Launching Windows Calculator...")
    subprocess.Popen(["calc.exe"])

    try:
        elements = []
        digits = {}
        deadline = time.perf_counter() + 5.0
        relocated_once = False
        while time.perf_counter() < deadline:
            found_calc = _find_and_relocate_calculator(cfg.vision.monitor_index)
            if found_calc and not relocated_once:
                time.sleep(0.2)
                relocated_once = True

            elements = grounder.ground(lazy=True)
            digits = _extract_digit_buttons(elements)
            if len(digits) == 3:
                break

            # Fallback to single full foreground walk if lazy UWP subtree hasn't settled yet
            elements = grounder.ground(lazy=False)
            digits = _extract_digit_buttons(elements)
            if len(digits) == 3:
                break

            time.sleep(0.35)

        if len(digits) != 3:
            missing = [d for d in ("7", "8", "9") if d not in digits]
            _emit(f"[ERROR] Could not locate Calculator buttons {missing} in UIA tree within 5.0s (elements={len(elements)}).", level="error")
            return 1

        frame = capturer.capture_screen()
        token = guard.get_cancellation_token()

        # Verify O(1) uia_point non-destructively before clicking, and also test live CUA click on '8'
        for d in ("7", "8", "9"):
            elem = digits[d]
            # Deliberately aim 3px inside the left border (edge-clipping simulation)
            edge_x = elem.x + 3
            edge_y = elem.center_y
            use_cua_probe = d == "8"
            step_elements = [] if use_cua_probe else elements
            mode_tag = "CUA/uia_point" if use_cua_probe else "uia_bbox"

            _emit(
                f"[P4.1 SMOKE] Button '{d}' [{mode_tag}] bbox=({elem.x},{elem.y},{elem.width}x{elem.height}) "
                f"center=({elem.center_x},{elem.center_y}) | Firing edge-clipped click at ({edge_x},{edge_y})..."
            )
            action = ActionPlan(
                action=ActionType.CLICK,
                coordinates=(edge_x, edge_y),
                reasoning=f"Click the '{d}' button on Calculator",
            )
            res = dispatcher.dispatch(
                action=action,
                som_elements=step_elements,
                cancellation_token=token,
                frame=frame,
                cua_mode=use_cua_probe,
            )
            _emit(f"  -> Dispatched at resolved={res.resolved_coordinates}, success={res.success}")
            if not res.success:
                _emit(f"[ERROR] Dispatch failed: {res.error}", level="error")
                return 1
            time.sleep(0.18)
            frame = capturer.capture_screen()

        time.sleep(0.25)
        display_text = _read_calculator_display()
        display_hit = "789" in display_text
        if not display_hit:
            # Secondary fallback check via ScreenGrounder UIA walk
            post_elements = grounder.ground(lazy=True)
            display_hit = any("789" in (e.label or "").replace(",", "") for e in post_elements)
            if not display_text and display_hit:
                display_text = next((e.label for e in post_elements if "789" in (e.label or "").replace(",", "")), "")

        _emit(f"[P4.1 SMOKE] Calculator display ('CalculatorResults'): {display_text!r} | contains '789': {display_hit}")
        return 0 if display_hit else 1
    finally:
        guard.stop()


if __name__ == "__main__":
    raise SystemExit(main())
