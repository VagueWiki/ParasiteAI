"""
parasite_ai/hands/reflex.py - Layer 0.5 Chained Reflex & Muscle Memory Burst Dispatcher.

Executes sub-200ms multi-action compound sequences on CPU without intermediate VLM pauses.
Applies per-target centroid snapping, enforces continuous sub-2ms hardware interrupt preemption,
and monitors target window health for early anomaly aborts.
"""

from __future__ import annotations

import inspect
import logging
import random
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from parasite_ai.config import ReflexConfig

if TYPE_CHECKING:
    from parasite_ai.mind.memory import ActionPlan, ActionType

logger = logging.getLogger(__name__)


class ReflexBurstResult(BaseModel):
    """Execution telemetry and outcome of a compound reflex burst."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    success: bool = True
    interrupted: bool = False
    aborted_early: bool = False
    abort_reason: Optional[str] = None
    executed_count: int = 0
    total_count: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    raw_coordinates_list: List[Optional[Tuple[int, int]]] = Field(default_factory=list)
    resolved_coordinates_list: List[Tuple[int, int]] = Field(default_factory=list)


class ReflexBurstDispatcher:
    """
    Layer 0.5 Chained Reflex Dispatcher:
    Bypasses VLM multi-turn latency for deterministic sequential actions.
    """

    def __init__(
        self,
        mouse_driver: Optional[Any] = None,
        keyboard_driver: Optional[Any] = None,
        config: Optional[ReflexConfig] = None,
        target_refiner: Optional[Callable[[Tuple[int, int], ActionPlan], Tuple[Tuple[int, int], Optional[str]]]] = None,
        coordinate_validator: Optional[Callable[[int, int], bool]] = None,
        dock_evader: Optional[Callable[[Optional[Tuple[int, int]]], bool]] = None,
        window_activator: Optional[Callable[[Optional[Tuple[int, int]]], bool]] = None,
        release_fn: Optional[Callable[[], None]] = None,
        anomaly_check_fn: Optional[Callable[[], Optional[str]]] = None,
    ) -> None:
        self.mouse_driver = mouse_driver
        self.keyboard_driver = keyboard_driver
        self.config = config or ReflexConfig()
        self.target_refiner = target_refiner
        self.coordinate_validator = coordinate_validator
        self.dock_evader = dock_evader
        self.window_activator = window_activator
        self.release_fn = release_fn
        self.anomaly_check_fn = anomaly_check_fn

    def _detect_win32_window_anomaly(
        self,
        bound_hwnd: Optional[int],
    ) -> Optional[str]:
        """Verifies bound target window is still alive, visible, and has not crashed or vanished."""
        if not bound_hwnd or sys.platform != "win32":
            return None
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if not user32.IsWindow(bound_hwnd):
                return f"Target window HWND {bound_hwnd} destroyed or closed mid-burst"
            if not user32.IsWindowVisible(bound_hwnd):
                return f"Target window HWND {bound_hwnd} hidden or minimized mid-burst"
        except Exception as exc:
            logger.debug("[REFLEX ANOMALY] Error checking HWND %s: %s", bound_hwnd, exc)
        return None

    def _emergency_release(self) -> None:
        """Invokes emergency release callback on drivers."""
        if self.release_fn:
            try:
                self.release_fn()
            except Exception:
                pass
        if self.mouse_driver and hasattr(self.mouse_driver, "release_all_buttons"):
            try:
                self.mouse_driver.release_all_buttons()
            except Exception:
                pass
        if self.keyboard_driver and hasattr(self.keyboard_driver, "emergency_release_keys"):
            try:
                self.keyboard_driver.emergency_release_keys()
            except Exception:
                pass

    def _execute_click_sub_action(
        self,
        action: ActionPlan,
        coords: Tuple[int, int],
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        """Dispatches a single fast reflex click/double_click/right_click."""
        if not self.mouse_driver:
            return True

        btn = "left"
        clicks = getattr(action, "clicks", 1) or 1
        act_val = getattr(action.action, "value", str(action.action))
        if act_val == "DOUBLE_CLICK":
            clicks = 2
        elif act_val == "RIGHT_CLICK":
            btn = "right"
            clicks = 1

        move_dur_s = max(0.005, self.config.reflex_move_duration_ms / 1000.0)
        dwell_s = max(0.005, self.config.reflex_dwell_ms / 1000.0)

        # Inspect signature to support both enhanced MouseDriver and mock/stub objects
        sig = inspect.signature(self.mouse_driver.click)
        kwargs: Dict[str, Any] = {
            "x": coords[0],
            "y": coords[1],
            "button": btn,
            "clicks": clicks,
            "cancellation_token": cancellation_token,
        }
        if "preview_reticle" in sig.parameters:
            kwargs["preview_reticle"] = False
        if "move_duration" in sig.parameters:
            kwargs["move_duration"] = move_dur_s
        if "hesitation_s" in sig.parameters:
            kwargs["hesitation_s"] = 0.0
        if "dwell_s" in sig.parameters:
            kwargs["dwell_s"] = dwell_s

        return bool(self.mouse_driver.click(**kwargs))

    def _execute_type_sub_action(
        self,
        action: ActionPlan,
        coords: Optional[Tuple[int, int]],
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        """Dispatches typing or click_and_type during reflex burst."""
        if not self.keyboard_driver:
            return True
        text = action.text or ""
        submit = action.submit
        if coords is not None:
            return bool(
                self.keyboard_driver.click_and_type(
                    x=coords[0],
                    y=coords[1],
                    text=text,
                    submit=submit,
                    cancellation_token=cancellation_token,
                    mouse_driver=self.mouse_driver,
                    clear_first=getattr(action, "clear_first", True),
                )
            )
        return bool(
            self.keyboard_driver.type_text(
                text=text,
                submit=submit,
                cancellation_token=cancellation_token,
            )
        )

    def _execute_hotkey_sub_action(
        self,
        action: ActionPlan,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        """Dispatches keyboard hotkey chord during reflex burst."""
        if not self.keyboard_driver:
            return True
        keys = action.keys or [k.strip() for k in (action.text or "").split("+") if k.strip()]
        if not keys:
            keys = ["enter"]
        return bool(self.keyboard_driver.hotkey(*keys, cancellation_token=cancellation_token))

    def execute_burst(
        self,
        burst_action: ActionPlan,
        cancellation_token: Optional[threading.Event] = None,
        target_hwnd: Optional[int] = None,
    ) -> ReflexBurstResult:
        """
        Executes a sequence of reflex actions in rapid succession.
        """
        start_time = time.monotonic()
        sub_actions = burst_action.burst_actions or []
        total_count = len(sub_actions)

        raw_coords_list: List[Optional[Tuple[int, int]]] = []
        resolved_coords_list: List[Tuple[int, int]] = []

        if not self.config.enabled:
            return ReflexBurstResult(
                success=False,
                error="ReflexBurstDispatcher is disabled in configuration",
                total_count=total_count,
            )

        if not sub_actions:
            return ReflexBurstResult(
                success=True,
                total_count=0,
                duration_ms=0.0,
            )

        cap = min(total_count, self.config.max_burst_actions)
        sub_actions = sub_actions[:cap]

        executed_count = 0
        bound_hwnd = target_hwnd

        # Resolve initial window HWND if none passed
        if not bound_hwnd and sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                bound_hwnd = user32.GetForegroundWindow() or None
            except Exception:
                bound_hwnd = None

        logger.info(
            "[REFLEX BURST START] Dispatching burst of %d sub-actions (cap=%d, bound_hwnd=%s)",
            total_count,
            cap,
            bound_hwnd,
        )

        for idx, act in enumerate(sub_actions):
            # 1. Preemption check (<2ms hot preemption)
            if cancellation_token and cancellation_token.is_set():
                self._emergency_release()
                dur_ms = (time.monotonic() - start_time) * 1000.0
                logger.info("[REFLEX INTERRUPTED] Hardware touch preemption before sub-step %d/%d", idx + 1, cap)
                return ReflexBurstResult(
                    success=False,
                    interrupted=True,
                    executed_count=executed_count,
                    total_count=total_count,
                    duration_ms=dur_ms,
                    error="Interrupted by physical human input",
                    raw_coordinates_list=raw_coords_list,
                    resolved_coordinates_list=resolved_coords_list,
                )

            # 2. Early Anomaly Abort Check
            if self.config.abort_on_window_change:
                anomaly_err = None
                if self.anomaly_check_fn:
                    try:
                        anomaly_err = self.anomaly_check_fn()
                    except Exception as exc:
                        logger.debug("[REFLEX ANOMALY FN ERROR] %s", exc)
                elif bound_hwnd:
                    anomaly_err = self._detect_win32_window_anomaly(bound_hwnd)

                if anomaly_err:
                    self._emergency_release()
                    dur_ms = (time.monotonic() - start_time) * 1000.0
                    logger.warning("[REFLEX ANOMALY ABORT] Aborting burst at sub-step %d/%d: %s", idx + 1, cap, anomaly_err)
                    return ReflexBurstResult(
                        success=False,
                        aborted_early=True,
                        abort_reason=anomaly_err,
                        executed_count=executed_count,
                        total_count=total_count,
                        duration_ms=dur_ms,
                        error=anomaly_err,
                        raw_coordinates_list=raw_coords_list,
                        resolved_coordinates_list=resolved_coords_list,
                    )

            # 3. Coordinate Refinement & Validation
            raw_c = act.coordinates
            raw_coords_list.append(raw_c)
            refined_c = raw_c

            if refined_c is not None:
                if self.target_refiner:
                    refined_c, ref_err = self.target_refiner(refined_c, act)
                    if ref_err:
                        self._emergency_release()
                        dur_ms = (time.monotonic() - start_time) * 1000.0
                        return ReflexBurstResult(
                            success=False,
                            executed_count=executed_count,
                            total_count=total_count,
                            duration_ms=dur_ms,
                            error=ref_err,
                            raw_coordinates_list=raw_coords_list,
                            resolved_coordinates_list=resolved_coords_list,
                        )

                if self.coordinate_validator and not self.coordinate_validator(refined_c[0], refined_c[1]):
                    self._emergency_release()
                    dur_ms = (time.monotonic() - start_time) * 1000.0
                    err = f"Sub-action {idx + 1} coordinates {refined_c} out of screen bounds"
                    return ReflexBurstResult(
                        success=False,
                        executed_count=executed_count,
                        total_count=total_count,
                        duration_ms=dur_ms,
                        error=err,
                        raw_coordinates_list=raw_coords_list,
                        resolved_coordinates_list=resolved_coords_list,
                    )

                resolved_coords_list.append(refined_c)
                if self.dock_evader:
                    self.dock_evader(refined_c)
                if self.window_activator and idx == 0:
                    self.window_activator(refined_c)

            # 4. Dispatch sub-action
            act_ok = True
            act_val = getattr(act.action, "value", str(act.action))
            if act_val in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
                if refined_c is None:
                    act_ok = False
                else:
                    act_ok = self._execute_click_sub_action(act, refined_c, cancellation_token)
            elif act_val in ("TYPE", "CLICK_AND_TYPE"):
                act_ok = self._execute_type_sub_action(act, refined_c, cancellation_token)
            elif act_val == "HOTKEY":
                act_ok = self._execute_hotkey_sub_action(act, cancellation_token)
            elif act_val == "WAIT":
                wait_s = max(0.010, act.wait_ms / 1000.0)
                if cancellation_token:
                    if cancellation_token.wait(timeout=wait_s):
                        act_ok = False
                else:
                    time.sleep(wait_s)

            if not act_ok:
                interrupted = bool(cancellation_token and cancellation_token.is_set())
                self._emergency_release()
                dur_ms = (time.monotonic() - start_time) * 1000.0
                err = "Interrupted by physical human input" if interrupted else f"Sub-action {idx + 1} ({act_val}) failed"
                logger.info("[REFLEX SUB-ACTION FAILED] %s (interrupted=%s)", err, interrupted)
                return ReflexBurstResult(
                    success=False,
                    interrupted=interrupted,
                    executed_count=executed_count,
                    total_count=total_count,
                    duration_ms=dur_ms,
                    error=err,
                    raw_coordinates_list=raw_coords_list,
                    resolved_coordinates_list=resolved_coords_list,
                )

            executed_count += 1

            # 5. Randomized 15-30ms Inter-Action Pause (interruptible)
            if idx < len(sub_actions) - 1:
                min_p = max(0, self.config.inter_action_min_ms)
                max_p = max(min_p, self.config.inter_action_max_ms)
                pause_ms = random.uniform(min_p, max_p)
                pause_s = pause_ms / 1000.0
                if pause_s > 0.0:
                    if cancellation_token and cancellation_token.wait(timeout=pause_s):
                        self._emergency_release()
                        dur_ms = (time.monotonic() - start_time) * 1000.0
                        return ReflexBurstResult(
                            success=False,
                            interrupted=True,
                            executed_count=executed_count,
                            total_count=total_count,
                            duration_ms=dur_ms,
                            error="Interrupted by physical human input during reflex pause",
                            raw_coordinates_list=raw_coords_list,
                            resolved_coordinates_list=resolved_coords_list,
                        )
                    elif not cancellation_token:
                        time.sleep(pause_s)

        dur_ms = (time.monotonic() - start_time) * 1000.0
        logger.info(
            "[REFLEX BURST COMPLETE] Executed %d/%d actions in %.2fms",
            executed_count,
            total_count,
            dur_ms,
        )
        return ReflexBurstResult(
            success=True,
            executed_count=executed_count,
            total_count=total_count,
            duration_ms=dur_ms,
            raw_coordinates_list=raw_coords_list,
            resolved_coordinates_list=resolved_coords_list,
        )
