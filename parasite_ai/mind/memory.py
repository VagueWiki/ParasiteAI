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
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


def _build_dct_matrix(n: int = 32) -> np.ndarray:
    """Builds an NxN orthonormal 2D DCT-II transform matrix without SciPy."""
    k = np.arange(n, dtype=np.float64)[:, None]
    x = np.arange(n, dtype=np.float64)[None, :]
    scale = np.full((n, 1), np.sqrt(2.0 / n), dtype=np.float64)
    scale[0, 0] = np.sqrt(1.0 / n)
    return scale * np.cos((np.pi * k * (2.0 * x + 1.0)) / (2.0 * n))


_DCT_32: np.ndarray = _build_dct_matrix(32)


def compute_phash(image: Union[np.ndarray, Image.Image]) -> str:
    """
    Calculates a 64-bit DCT perceptual hash (pHash) returned as a 16-char hex string.
    Uses a precomputed 32x32 orthonormal DCT-II matrix on an L-channel LANCZOS resize.
    """
    try:
        if isinstance(image, np.ndarray):
            if image.size == 0 or image.ndim < 2 or image.shape[0] == 0 or image.shape[1] == 0:
                return "0000000000000000"
            pil_img = Image.fromarray(image).convert("L")
        elif isinstance(image, Image.Image):
            if image.width == 0 or image.height == 0:
                return "0000000000000000"
            pil_img = image.convert("L")
        else:
            return "0000000000000000"
    except Exception:
        return "0000000000000000"

    resized = pil_img.resize((32, 32), Image.Resampling.LANCZOS)
    pixels = np.asarray(resized, dtype=np.float64)
    dct = _DCT_32 @ pixels @ _DCT_32.T
    low_freq = dct[:8, :8].flatten()
    median_ac = float(np.median(low_freq[1:]))

    hash_val = 0
    for bit in (low_freq > median_ac):
        hash_val = (hash_val << 1) | int(bool(bit))
    return f"{hash_val:016x}"


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
    DRAG = "DRAG"
    CLICK_AND_TYPE = "CLICK_AND_TYPE"
    TYPE = "TYPE"
    HOTKEY = "HOTKEY"
    SCROLL = "SCROLL"
    MINIMIZE_WINDOW = "MINIMIZE_WINDOW"
    CLOSE_WINDOW = "CLOSE_WINDOW"
    WAIT = "WAIT"
    PANIC = "PANIC"
    OFFLOAD_WEB_AI = "OFFLOAD_WEB_AI"
    DONE = "DONE"
    RUN_CLI_COMMAND = "RUN_CLI_COMMAND"
    BURST = "BURST"


INTERACTIVE_ACTION_TYPES: Set[ActionType] = {
    ActionType.CLICK,
    ActionType.DOUBLE_CLICK,
    ActionType.RIGHT_CLICK,
    ActionType.DRAG,
    ActionType.CLICK_AND_TYPE,
    ActionType.TYPE,
    ActionType.HOTKEY,
    ActionType.SCROLL,
    ActionType.MINIMIZE_WINDOW,
    ActionType.CLOSE_WINDOW,
    ActionType.BURST,
}

# Mapping of common LLM verb variations & synonyms to canonical ActionType enums
VERB_SYNONYMS: Dict[str, ActionType] = {
    # Click variants
    "SELECT": ActionType.CLICK,
    "SELECT MENUITEM": ActionType.CLICK,
    "SELECT_MENUITEM": ActionType.CLICK,
    "LEFT_CLICK": ActionType.CLICK,
    "TAP": ActionType.CLICK,
    "MOUSE_CLICK": ActionType.CLICK,
    "CLICK_ELEMENT": ActionType.CLICK,
    "CHOOSE": ActionType.CLICK,
    # Double click
    "DOUBLE_TAP": ActionType.DOUBLE_CLICK,
    "DBLCLICK": ActionType.DOUBLE_CLICK,
    "LEFT_DOUBLE": ActionType.DOUBLE_CLICK,
    "DOUBLECLICK": ActionType.DOUBLE_CLICK,
    # Right click
    "RIGHT_TAP": ActionType.RIGHT_CLICK,
    "CONTEXT_CLICK": ActionType.RIGHT_CLICK,
    "RIGHT_SINGLE": ActionType.RIGHT_CLICK,
    "RIGHTCLICK": ActionType.RIGHT_CLICK,
    # Drag variants
    "DRAG": ActionType.DRAG,
    "MOUSE_DRAG": ActionType.DRAG,
    "DRAG_AND_DROP": ActionType.DRAG,
    # Type variants
    "TYPE_TEXT": ActionType.TYPE,
    "INPUT": ActionType.TYPE,
    "WRITE": ActionType.TYPE,
    # Hotkey variants
    "PRESS": ActionType.HOTKEY,
    "KEY": ActionType.HOTKEY,
    "KEY_PRESS": ActionType.HOTKEY,
    "KEYPRESS": ActionType.HOTKEY,
    "SHORTCUT": ActionType.HOTKEY,
    # Done variants
    "FINISH": ActionType.DONE,
    "FINISHED": ActionType.DONE,
    "COMPLETE": ActionType.DONE,
    "COMPLETED": ActionType.DONE,
    "STOP": ActionType.DONE,
    # Wait variants
    "PAUSE": ActionType.WAIT,
    "SLEEP": ActionType.WAIT,
    "IDLE": ActionType.WAIT,
    # Burst / compound variants
    "BURST": ActionType.BURST,
    "SEQUENCE": ActionType.BURST,
    "CHAIN": ActionType.BURST,
}


class ActionPlan(BaseModel):
    """Structured action command produced by Pass 2 Action Planner or UI-TARS Parser."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    action: ActionType = ActionType.WAIT
    target_id: Optional[int] = Field(default=None, description="1-based Set-of-Mark target index.")
    coordinates: Optional[Tuple[int, int]] = Field(default=None, description="Explicit [x, y] coordinates.")
    end_coordinates: Optional[Tuple[int, int]] = Field(default=None, description="Explicit [x, y] end coordinates for DRAG.")
    text: Optional[str] = Field(default=None, description="Text string for typing.")
    submit: bool = Field(default=False, description="Whether to send Enter after typing.")
    clear_first: bool = Field(default=True, description="Whether to clear existing text before typing.")
    keys: Optional[List[str]] = Field(default=None, description="Key list for hotkey chords.")
    clicks: int = Field(default=1, ge=1, le=5)
    scroll_amount: int = Field(default=0, description="Wheel clicks (positive=up, negative=down).")
    wait_ms: int = Field(default=500, ge=0, le=30000)
    reasoning: str = Field(default="", description="Planner justification.")
    cli_command: Optional[str] = Field(default=None, description="CLI command string for headless execution.")
    burst_actions: Optional[List[ActionPlan]] = Field(default=None, description="Ordered sub-actions for BURST execution.")

    @model_validator(mode="before")
    @classmethod
    def _coerce_null_fields(cls, data: Any) -> Any:
        """Coerces explicit null fields and normalizes verb synonyms from LLM output to valid ActionPlan."""
        if isinstance(data, dict):
            cleaned = dict(data)
            defaults: Dict[str, Any] = {
                "action": ActionType.WAIT,
                "submit": False,
                "clear_first": True,
                "clicks": 1,
                "scroll_amount": 0,
                "wait_ms": 500,
                "reasoning": "",
            }
            for k, default_val in defaults.items():
                if k in cleaned and cleaned[k] is None:
                    cleaned[k] = default_val

            # Handle and normalize action string
            raw_act = cleaned.get("action")
            if isinstance(raw_act, str):
                act_norm = raw_act.strip().upper()
                # 1. Direct ActionType match
                matched_action: Optional[ActionType] = None
                for member in ActionType:
                    if act_norm == member.value:
                        matched_action = member
                        break
                # 2. Synonym table lookup
                if matched_action is None:
                    if act_norm in VERB_SYNONYMS:
                        matched_action = VERB_SYNONYMS[act_norm]
                    elif act_norm.startswith("SELECT "):
                        matched_action = ActionType.CLICK
                # 3. Graceful fallback on unrecognized verb
                if matched_action is not None:
                    cleaned["action"] = matched_action
                else:
                    logger.warning("Unrecognized ActionPlan verb '%s'; coercing to ActionType.WAIT", raw_act)
                    cleaned["action"] = ActionType.WAIT
                    existing_reason = cleaned.get("reasoning", "")
                    cleaned["reasoning"] = f"{existing_reason} [Unrecognized verb: {raw_act}]".strip()

            # Also handle string booleans like "false"/"true" if emitted by small models
            for bool_key in ("submit", "clear_first"):
                val = cleaned.get(bool_key)
                if isinstance(val, str):
                    cleaned[bool_key] = val.strip().lower() in ("true", "1", "yes")
            return cleaned
        return data


ActionPlan.model_rebuild()


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
    pre_window: Optional[str] = None
    post_window: Optional[str] = None
    screen_size: Tuple[int, int] = (1920, 1080)

    def to_summary(self, duration_sec: float = 0.0) -> StepRecordSummary:
        """Projects this detailed step record into a compact summary for episode receipts."""
        label = None
        if self.target_info:
            label = self.target_info.get("label") or self.target_info.get("name")
        burst_count = len(self.action.burst_actions) if self.action.burst_actions else None
        return StepRecordSummary(
            step_id=self.step_id,
            action_type=self.action.action.value,
            target_id=self.action.target_id,
            target_label=label,
            coordinates=self.action.coordinates,
            text=self.action.text,
            keys=self.action.keys,
            success=self.success,
            screen_diff=self.screen_diff,
            error_message=self.error_message,
            duration_sec=duration_sec,
            burst_count=burst_count,
        )


class StepRecordSummary(BaseModel):
    """Compact summary of a single action step for episode receipt telemetry."""
    model_config = ConfigDict(extra="ignore")

    step_id: int
    action_type: str
    target_id: Optional[int] = None
    target_label: Optional[str] = None
    coordinates: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    success: bool
    screen_diff: float
    error_message: Optional[str] = None
    duration_sec: float = 0.0
    burst_count: Optional[int] = None


class EpisodeReceipt(BaseModel):
    """Machine-readable receipt certifying the final outcome and metrics of a goal episode."""
    model_config = ConfigDict(extra="ignore")

    goal: str
    success: bool
    claimed_done: bool = False
    total_steps: int
    max_steps: int = 15
    duration_sec: float
    exit_reason: str  # "DONE", "MAX_STEPS", "PANIC", "LOOP_STAGNATION", "ERROR", "TIMEOUT", "IN_PROGRESS"
    step_latencies_sec: List[float] = Field(default_factory=list)
    total_strikes: int = 0
    highest_tier_reached: str = "TIER_1_LOCAL"
    hardware_interrupt_count: int = 0
    final_active_window: Optional[Dict[str, str]] = None
    steps: List[StepRecordSummary] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    plan_source: str = "local"
    skill_id: Optional[str] = None
    farmed_plan_id: Optional[int] = None
    fast_path_steps: int = 0
    parasite_invocations: int = 0
    parasite_status: Optional[str] = None
    veto_count: int = 0
    fast_path_abort_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_claimed_done(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "claimed_done" not in data:
                # If model exited with DONE or success is True, claimed_done is True
                exit_reason = data.get("exit_reason", "")
                data["claimed_done"] = (exit_reason == "DONE") or bool(data.get("success", False))
        return data

    @property
    def terminal_reason(self) -> str:
        return self.exit_reason

    @property
    def steps_executed(self) -> int:
        return self.total_steps

    @property
    def total_duration_sec(self) -> float:
        return self.duration_sec

    @property
    def step_trace(self) -> List[StepRecordSummary]:
        return self.steps

    def to_json(self, indent: int = 2) -> str:
        """Serializes receipt to indented JSON string."""
        return self.model_dump_json(indent=indent)

    def save(self, path: Union[str, Path]) -> None:
        """Atomically writes receipt to specified file path, creating parent directories as needed."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f"{p.suffix}.tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        tmp.replace(p)


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
        pre_window: Optional[str] = None,
        post_window: Optional[str] = None,
        screen_size: Tuple[int, int] = (1920, 1080),
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
                pre_window=pre_window,
                post_window=post_window,
                screen_size=screen_size,
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

    @property
    def history(self) -> List[StepRecord]:
        """Returns a thread-safe chronological snapshot of buffered StepRecords."""
        with self._lock:
            return list(self._buffer)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

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
            all_records = list(self._buffer)
            if not all_records:
                return "No previous actions recorded in this session."

            history = all_records[-n:] if n < len(all_records) else all_records
            older_records = all_records[:-n] if n < len(all_records) else []

            lines = ["### Recent Action History & Visual Outcomes:"]

            # Milestone compression for earlier steps beyond the detailed window
            if older_records:
                milestones: List[str] = []
                for o_rec in older_records:
                    o_act = o_rec.action
                    o_status = "SUCCESS" if o_rec.success else "FAILED"
                    o_act_desc = o_act.action.value
                    if o_act.action == ActionType.HOTKEY and o_act.keys:
                        o_act_desc += f" [{'+'.join(o_act.keys)}]"
                    elif o_act.action in (ActionType.TYPE, ActionType.CLICK_AND_TYPE) and o_act.text:
                        short_text = (o_act.text[:15] + "…") if len(o_act.text) > 15 else o_act.text
                        o_act_desc += f" '{short_text}'"
                        if o_act.submit:
                            o_act_desc += " [Enter]"
                    elif o_act.action in (ActionType.CLICK, ActionType.DOUBLE_CLICK, ActionType.RIGHT_CLICK):
                        if o_rec.target_info and (o_rec.target_info.get("label") or o_rec.target_info.get("name")):
                            lbl = o_rec.target_info.get("label") or o_rec.target_info.get("name")
                            o_act_desc += f" on '{lbl}'"
                        elif o_act.target_id is not None:
                            o_act_desc += f" target [#{o_act.target_id}]"
                    elif o_act.action == ActionType.BURST and o_act.burst_actions:
                        o_act_desc += f" [{len(o_act.burst_actions)} sub-actions]"

                    dest = ""
                    if o_rec.post_window:
                        # Extract short window title
                        w_short = o_rec.post_window.split(" (")[0]
                        dest = f" -> {w_short}"
                    milestones.append(f"#{o_rec.step_id} {o_act_desc} ({o_status}{dest})")

                start_id = older_records[0].step_id
                end_id = older_records[-1].step_id
                id_range = f"Step #{start_id}" if start_id == end_id else f"Steps #{start_id}-#{end_id}"
                lines.append(f"- Completed Milestones ({id_range}): {'; '.join(milestones)}")

            for rec in history:
                act = rec.action
                target_desc = ""
                if act.target_id is not None:
                    target_desc = f" target [#{act.target_id}]"
                elif act.coordinates:
                    cx, cy = act.coordinates
                    target_desc = f" at ({cx}, {cy})"

                if rec.target_info:
                    role = rec.target_info.get("role")
                    label = rec.target_info.get("label") or rec.target_info.get("name")
                    if role and label:
                        target_desc += f" on {role} '{label}'"
                    elif label:
                        target_desc += f" on '{label}'"

                text_desc = f' text="{act.text}"' if act.text else ""
                if act.keys:
                    text_desc += f" keys={act.keys}"
                if act.action in (ActionType.TYPE, ActionType.CLICK_AND_TYPE):
                    text_desc += " (Enter pressed)" if act.submit else " (Enter NOT pressed)"
                if act.action == ActionType.BURST and act.burst_actions:
                    sub_types = [sub.action.value for sub in act.burst_actions]
                    text_desc += f" [actions: {', '.join(sub_types)}]"

                diff_pct = f"{rec.screen_diff * 100:.1f}%"
                status_str = "SUCCESS" if rec.success else "FAILED"
                strike_str = f" [Strike {rec.consecutive_strikes}/{self.strike_limit}]" if rec.is_strike else ""
                if rec.is_strike:
                    if rec.screen_diff >= self.screen_diff_threshold:
                        outcome_tag = (
                            " [LOOP STRIKE - repeated/oscillating cycle; stop repeating and emit "
                            "finished() if goal is complete or choose a different action]"
                        )
                    else:
                        outcome_tag = " [NO SCREEN CHANGE - try an alternative action, keyboard shortcut, or double-click]"
                else:
                    outcome_tag = " [Screen changed]"
                reason_tag = f" | Reason: {rec.error_message}" if rec.error_message else ""

                window_tag = ""
                if rec.pre_window and rec.post_window and rec.pre_window != rec.post_window:
                    window_tag = f" | Window: {rec.pre_window} -> {rec.post_window}"
                elif rec.post_window:
                    window_tag = f" | Window: {rec.post_window}"

                thought_tag = ""
                if rec.persona_thought:
                    clean_thought = " ".join(rec.persona_thought.split())
                    if len(clean_thought) > 90:
                        clean_thought = clean_thought[:87] + "..."
                    thought_tag = f' | Thought: "{clean_thought}"'

                lines.append(
                    f"- Step #{rec.step_id}: {act.action.value}{target_desc}{text_desc} "
                    f"-> Screen Diff: {diff_pct} ({status_str}){strike_str}{outcome_tag}{reason_tag}{window_tag}{thought_tag}"
                )

            if self._consecutive_strikes >= self.strike_limit:
                lines.append(
                    f"\n⚠️ CRITICAL WARNING: Detected cognitive failure loop! "
                    f"Last {self._consecutive_strikes} interactive actions produced no visual change. "
                    f"You MUST change your strategy or re-ground the desktop before acting!"
                )
            elif self._consecutive_strikes > 0:
                last_rec = all_records[-1]
                if last_rec.is_strike and last_rec.screen_diff >= self.screen_diff_threshold:
                    lines.append(
                        f"\nNotice: {self._consecutive_strikes} consecutive loop strike(s) detected. "
                        f"[WARNING: Repeated/alternating action cycle detected; stop repeating that cycle. "
                        f"If the requested task is already complete on screen emit finished(), otherwise pick a new approach.]"
                    )
                else:
                    lines.append(
                        f"\nNotice: {self._consecutive_strikes} consecutive action strike(s) detected. "
                        f"[WARNING: Last action produced NO screen change. Do NOT repeat the same action; "
                        f"try an alternative approach, keyboard shortcut, or double-click instead.]"
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
