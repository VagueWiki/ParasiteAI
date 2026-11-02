"""
parasite_ai/mind/memory.py - Episodic Working Memory & Screen Diff Verification.

Tracks recent action execution history in a bounded thread-safe ring-buffer,
computes vectorized visual difference ratios and 64-bit perceptual dHash,
and enforces a deterministic 3-strike failure loop detector.
"""

from __future__ import annotations

import collections
from enum import Enum
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Visual Diff & Perceptual Hash Algorithms
# ---------------------------------------------------------------------------

def compute_pixel_diff(
    frame_a: Optional[np.ndarray],
    frame_b: Optional[np.ndarray],
    channel_threshold: int = 15,
) -> float:
    """
    Computes normalized fractional pixel change ratio in [0.0, 1.0] between two frames.
    A pixel is considered changed if max absolute difference across color channels
    exceeds channel_threshold (default 15, eliminating compression & dithering noise).
    """
    if frame_a is None or frame_b is None:
        return 0.0

    if frame_a.shape != frame_b.shape:
        return 1.0

    if frame_a.size == 0 or frame_b.size == 0:
        return 0.0

    arr_a = frame_a.astype(np.int16)
    arr_b = frame_b.astype(np.int16)

    if arr_a.ndim == 3 and arr_a.shape[2] >= 3:
        diff = np.max(np.abs(arr_a[:, :, :3] - arr_b[:, :, :3]), axis=2)
    else:
        diff = np.abs(arr_a - arr_b)

    changed_pixels = np.count_nonzero(diff > channel_threshold)
    total_pixels = diff.size

    if total_pixels == 0:
        return 0.0

    return float(changed_pixels / total_pixels)


def compute_dhash(image: Union[np.ndarray, Image.Image]) -> str:
    """
    Calculates a 64-bit perceptual difference hash (dHash) returned as a 16-char hex string.
    Downscales to a 9x8 grayscale matrix and compares adjacent horizontal pixel brightness.
    """
    if isinstance(image, np.ndarray):
        if image.size == 0:
            return "0000000000000000"
        pil_img = Image.fromarray(image).convert("L")
    elif isinstance(image, Image.Image):
        pil_img = image.convert("L")
    else:
        return "0000000000000000"

    # Resize to 9 columns x 8 rows
    resized = pil_img.resize((9, 8), Image.Resampling.BILINEAR)
    pixels = np.array(resized, dtype=np.int16)

    # Compute 64 difference bits: pixels[:, 1:] > pixels[:, :-1]
    diff = pixels[:, 1:] > pixels[:, :-1]
    flat_bits = diff.flatten()

    # Convert 64 boolean bits to integer
    hash_val = 0
    for bit in flat_bits:
        hash_val = (hash_val << 1) | int(bit)

    return f"{hash_val:016x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Computes bitwise Hamming distance between two 16-char hexadecimal hashes."""
    try:
        val_a = int(hash_a, 16)
        val_b = int(hash_b, 16)
        return bin(val_a ^ val_b).count("1")
    except Exception:
        return 64


# ---------------------------------------------------------------------------
# Action Plans & Episodic Models
# ---------------------------------------------------------------------------

class CadenceTier(str, Enum):
    """Hierarchical escalation cadence tiers for cognitive execution."""
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_CONSULT = "TIER_2_CONSULT"
    TIER_3_GUIDED = "TIER_3_GUIDED"
    TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
    USER_OVERRIDE = "USER_OVERRIDE"


class EscalationStateMachine(BaseModel):
    """
    4-Tier Escalation State Machine governing cognitive execution cadence.

    Tiers:
    - TIER_1_LOCAL: Fast offline local exploration (max 2 consecutive local strikes).
    - TIER_2_CONSULT: Deep strategic Gemini consultation upon local deadlock.
    - TIER_3_GUIDED: Guided local execution of strategic blueprint (max 2 guided strikes).
    - TIER_4_CO_PILOT: Continuous visual co-pilot handholding (max 3 strikes).
    - USER_OVERRIDE: Safe terminal state yielding control to human user.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True)

    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0, description="Consecutive failure strikes in Tier 1")
    guided_strikes: int = Field(default=0, ge=0, description="Consecutive failure strikes in Tier 3")
    copilot_strikes: int = Field(default=0, ge=0, description="Consecutive failure strikes in Tier 4")
    consultation_failures: int = Field(default=0, ge=0, description="Consecutive strategic advisor failures")
    total_escalation_cycles: int = Field(default=0, ge=0, description="Cumulative T3 <-> T4 oscillation cycles")
    max_escalation_cycles: int = Field(default=3, description="Maximum T3->T4 escalation cycles before user override.")
    max_consultation_failures: int = Field(default=2, description="Maximum consecutive advisor failures before user override.")

    def on_action_result(
        self,
        success: bool,
        screen_diff: float = 0.0,
        action_type: Optional[ActionType] = None,
        is_interactive: bool = True,
        cli_returncode: Optional[int] = None,
        diff_threshold: float = 0.02,
    ) -> CadenceTier:
        """
        Action-aware strike evaluation and tier transition.

        Evaluates success according to action modality:
        - Category 1: Headless CLI actions (RUN_CLI_COMMAND):
          Evaluated by subprocess returncode == 0 (visual diff bypassed).
        - Category 2: Passive / Non-visual actions (WAIT, DONE, or explicit is_interactive=False):
          Exempt from visual diff check. If success=True, strike counters remain unchanged.
        - Category 3: Interactive GUI actions (CLICK, TYPE, visual HOTKEY, SCROLL):
          Evaluated by physical success AND localized ROI diff >= diff_threshold.
        """
        if self.current_tier == CadenceTier.USER_OVERRIDE:
            return self.current_tier

        # Category 1: Headless CLI actions
        if action_type == ActionType.RUN_CLI_COMMAND:
            effective_success = success and (cli_returncode == 0 if cli_returncode is not None else True)

        # Category 2: Passive / Non-visual actions (WAIT, DONE, or explicit is_interactive=False)
        elif action_type in (ActionType.WAIT, ActionType.DONE) or not is_interactive:
            if success:
                # Passive actions do not incur strikes when successful and do not change tier
                return self.current_tier
            effective_success = False

        # Category 3: Interactive GUI actions
        else:
            effective_success = success and (screen_diff >= diff_threshold)

        # State Transitions based on current tier
        if self.current_tier == CadenceTier.TIER_1_LOCAL:
            if effective_success:
                self.local_strikes = 0
            else:
                self.local_strikes += 1
                if self.local_strikes >= 2:
                    self.current_tier = CadenceTier.TIER_2_CONSULT

        elif self.current_tier == CadenceTier.TIER_3_GUIDED:
            if effective_success:
                self.guided_strikes = 0
            else:
                self.guided_strikes += 1
                if self.guided_strikes >= 2:
                    self.total_escalation_cycles += 1
                    if self.total_escalation_cycles >= self.max_escalation_cycles:
                        self.current_tier = CadenceTier.USER_OVERRIDE
                    else:
                        self.current_tier = CadenceTier.TIER_4_CO_PILOT
                        self.copilot_strikes = 0

        elif self.current_tier == CadenceTier.TIER_4_CO_PILOT:
            if effective_success:
                self.copilot_strikes = 0
                self.guided_strikes = 0
                self.current_tier = CadenceTier.TIER_3_GUIDED
            else:
                self.copilot_strikes += 1
                if self.copilot_strikes >= 3:
                    self.current_tier = CadenceTier.USER_OVERRIDE

        return self.current_tier

    def on_consultation_success(self) -> None:
        """
        Called when strategic advisor returns a valid LivingPlan blueprint.
        Hydrates Tier 3 guided state and resets local strikes to prevent strike leakage.
        """
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.guided_strikes = 0
            self.consultation_failures = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        """
        Called when strategic consultation fails or times out.
        Escalates to USER_OVERRIDE on max_consultation_failures, otherwise returns to Tier 1.
        """
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.consultation_failures += 1
            if self.consultation_failures >= self.max_consultation_failures:
                self.current_tier = CadenceTier.USER_OVERRIDE
            else:
                self.local_strikes = 0
                self.current_tier = CadenceTier.TIER_1_LOCAL

    def on_hardware_interrupt(self) -> None:
        """
        Immediate deterministic transition from ANY_STATE to USER_OVERRIDE
        upon physical human touch preemption.
        """
        self.current_tier = CadenceTier.USER_OVERRIDE

    def reset(self) -> None:
        """Resets the state machine to initial Tier 1 state with all counters zeroed."""
        self.current_tier = CadenceTier.TIER_1_LOCAL
        self.local_strikes = 0
        self.guided_strikes = 0
        self.copilot_strikes = 0
        self.consultation_failures = 0
        self.total_escalation_cycles = 0

    @property
    def current_strikes(self) -> int:
        """Returns the active strike count corresponding to the current tier."""
        if self.current_tier == CadenceTier.TIER_1_LOCAL:
            return self.local_strikes
        elif self.current_tier == CadenceTier.TIER_2_CONSULT:
            return self.consultation_failures
        elif self.current_tier == CadenceTier.TIER_3_GUIDED:
            return self.guided_strikes
        elif self.current_tier == CadenceTier.TIER_4_CO_PILOT:
            return self.copilot_strikes
        return max(self.local_strikes, self.guided_strikes, self.copilot_strikes)


class ActionType(str, Enum):
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    CLICK_AND_TYPE = "CLICK_AND_TYPE"
    TYPE = "TYPE"
    HOTKEY = "HOTKEY"
    SCROLL = "SCROLL"
    WAIT = "WAIT"
    PANIC = "PANIC"
    OFFLOAD_WEB_AI = "OFFLOAD_WEB_AI"
    DONE = "DONE"
    RUN_CLI_COMMAND = "RUN_CLI_COMMAND"


INTERACTIVE_ACTION_TYPES: Set[ActionType] = {
    ActionType.CLICK,
    ActionType.DOUBLE_CLICK,
    ActionType.RIGHT_CLICK,
    ActionType.CLICK_AND_TYPE,
    ActionType.TYPE,
    ActionType.HOTKEY,
    ActionType.SCROLL,
}


class ActionPlan(BaseModel):
    """Structured action command produced by Pass 2 Action Planner."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    action: ActionType = ActionType.WAIT
    target_id: Optional[int] = Field(default=None, description="1-based Set-of-Mark target index.")
    coordinates: Optional[Tuple[int, int]] = Field(default=None, description="Explicit [x, y] coordinates.")
    text: Optional[str] = Field(default=None, description="Text string for typing.")
    submit: bool = Field(default=False, description="Whether to send Enter after typing.")
    keys: Optional[List[str]] = Field(default=None, description="Key list for hotkey chords.")
    clicks: int = Field(default=1, ge=1, le=5)
    scroll_amount: int = Field(default=0, description="Wheel clicks (positive=up, negative=down).")
    wait_ms: int = Field(default=500, ge=0, le=30000)
    reasoning: str = Field(default="", description="Planner justification.")
    cli_command: Optional[str] = Field(default=None, description="CLI command string for headless execution.")


class DiffResult(BaseModel):
    """Result of screen difference calculation between pre- and post-action frames."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    pixel_diff_ratio: float = 0.0
    pre_hash: Optional[str] = None
    post_hash: Optional[str] = None
    hamming_distance: int = 0
    is_changed: bool = False
    threshold_used: float = 0.02


class StepRecord(BaseModel):
    """Comprehensive episodic record of a single action step."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    step_id: int
    timestamp: float = Field(default_factory=time.time)
    user_goal: str = ""
    persona_thought: str = ""
    persona_speech: str = ""
    action: ActionPlan
    target_info: Optional[Dict[str, Any]] = None
    pre_hash: Optional[str] = None
    post_hash: Optional[str] = None
    screen_diff: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    is_strike: bool = False
    consecutive_strikes: int = 0
    tier_level: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL, description="Active escalation tier level")


# ---------------------------------------------------------------------------
# Episodic Memory Ring-Buffer & 3-Strike Loop Detector
# ---------------------------------------------------------------------------

class EpisodicMemory:
    """
    Thread-safe bounded ring-buffer tracking recent agent actions,
    perceptual hashes, diff ratios, and 3-strike failure loops.
    """

    def __init__(
        self,
        capacity: int = 20,
        screen_diff_threshold: float = 0.02,
        strike_limit: int = 3,
        escalation_sm: Optional[EscalationStateMachine] = None,
    ) -> None:
        self.capacity = capacity
        self.screen_diff_threshold = screen_diff_threshold
        self.strike_limit = strike_limit
        self.escalation_sm = escalation_sm or EscalationStateMachine()
        self._buffer: collections.deque[StepRecord] = collections.deque(maxlen=capacity)
        self._consecutive_strikes: int = 0
        self._step_counter: int = 0
        self._lock = threading.RLock()

    def record_step(
        self,
        action: Union[ActionPlan, Dict[str, Any]],
        success: bool = True,
        screen_diff: float = 0.0,
        user_goal: str = "",
        persona_thought: str = "",
        persona_speech: str = "",
        target_info: Optional[Dict[str, Any]] = None,
        pre_hash: Optional[str] = None,
        post_hash: Optional[str] = None,
        error_message: Optional[str] = None,
        tier_level: Optional[CadenceTier] = None,
    ) -> StepRecord:
        """
        Records an executed step into the episodic ring buffer, evaluates strike eligibility,
        and updates the failure loop detector.
        """
        with self._lock:
            if isinstance(action, dict):
                parsed_action = ActionPlan.model_validate(action)
            elif isinstance(action, ActionPlan):
                parsed_action = action
            else:
                parsed_action = ActionPlan()

            # Strike evaluation
            is_strike = False
            if parsed_action.action in INTERACTIVE_ACTION_TYPES:
                # Interactive action strike if physical execution failed OR screen did not change
                if not success or screen_diff < self.screen_diff_threshold:
                    is_strike = True
                    self._consecutive_strikes += 1
                else:
                    self._consecutive_strikes = 0
            else:
                # Meta / passive actions (WAIT, DONE, OFFLOAD_WEB_AI, PANIC) do not incur strikes
                # and do not reset active strikes
                is_strike = False

            resolved_tier = tier_level or self.escalation_sm.current_tier
            self._step_counter += 1
            step_record = StepRecord(
                step_id=self._step_counter,
                user_goal=user_goal,
                persona_thought=persona_thought,
                persona_speech=persona_speech,
                action=parsed_action,
                target_info=target_info,
                pre_hash=pre_hash,
                post_hash=post_hash,
                screen_diff=screen_diff,
                success=success,
                error_message=error_message,
                is_strike=is_strike,
                consecutive_strikes=self._consecutive_strikes,
                tier_level=resolved_tier,
            )

            self._buffer.append(step_record)
            return step_record

    def is_in_loop(self) -> bool:
        """Returns True if consecutive failure strikes reach or exceed strike_limit."""
        with self._lock:
            return self._consecutive_strikes >= self.strike_limit

    def get_consecutive_strikes(self) -> int:
        """Returns current count of consecutive failure strikes."""
        with self._lock:
            return self._consecutive_strikes

    def reset_loop_detector(self, reset_escalation: bool = False) -> None:
        """Manually resets the consecutive strikes failure counter."""
        with self._lock:
            self._consecutive_strikes = 0
            if reset_escalation:
                self.escalation_sm.reset()

    def get_recent_history(self, n: int = 5) -> List[StepRecord]:
        """Returns the most recent n step records in chronological order."""
        with self._lock:
            items = list(self._buffer)
            return items[-n:] if n < len(items) else items

    def format_for_prompt(self, n: int = 5) -> str:
        """
        Formats recent action history into markdown suitable for LLM prompt context,
        including failure strike warnings if loops are developing.
        """
        with self._lock:
            history = self.get_recent_history(n)
            if not history:
                return "No previous actions recorded in this session."

            lines = ["### Recent Action History & Visual Outcomes:"]
            for rec in history:
                act = rec.action
                target_desc = ""
                if act.target_id is not None:
                    target_desc = f" target [#{act.target_id}]"
                elif act.coordinates:
                    target_desc = f" at {act.coordinates}"

                text_desc = f' text="{act.text}"' if act.text else ""
                diff_pct = f"{rec.screen_diff * 100:.1f}%"
                status_str = "SUCCESS" if rec.success else "FAILED"
                strike_str = f" [Strike {rec.consecutive_strikes}/{self.strike_limit}]" if rec.is_strike else ""

                lines.append(
                    f"- Step #{rec.step_id}: {act.action.value}{target_desc}{text_desc} "
                    f"-> Screen Diff: {diff_pct} ({status_str}){strike_str}"
                )

            if self._consecutive_strikes >= self.strike_limit:
                lines.append(
                    f"\n⚠️ CRITICAL WARNING: Detected cognitive failure loop! "
                    f"Last {self._consecutive_strikes} interactive actions produced no visual change. "
                    f"You MUST change your strategy or re-ground the desktop before acting!"
                )
            elif self._consecutive_strikes > 0:
                lines.append(
                    f"\nNotice: {self._consecutive_strikes} consecutive action strike(s) detected."
                )

            return "\n".join(lines)

    def clear(self) -> None:
        """Clears all episodic history and resets strike counters."""
        with self._lock:
            self._buffer.clear()
            self._consecutive_strikes = 0
            self._step_counter = 0
            self.escalation_sm.reset()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
