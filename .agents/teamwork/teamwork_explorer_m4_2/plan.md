# Implementation Plan: Features 13 & 14 — Episodic Working Memory & Dual-Mind Cognitive Pipeline

**Author**: `teamwork_explorer_m4_2`  
**Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_2\`  
**Target Files**:
- `parasite_ai/mind/memory.py` (Feature 13: Episodic Working Memory, Screen Diff, 3-Strike Loop Detection)
- `parasite_ai/mind/dual_mind.py` (Feature 14: Dual-Mind Cognitive Pipeline, Persona Engine, Action Dispatcher)
- `tests/test_memory.py` (Automated unit & stress test suite for memory and diff algorithms)
- `tests/test_dual_mind.py` (Automated unit & integration test suite for dual-mind execution)

---

## 1. Executive Summary & Architectural Overview

The core philosophy of ParasiteAI demands that the assistant is 100% visible and operates directly on the user's physical desktop. A physical desktop agent cannot succeed with open-loop execution: clicks may miss, web pages may lag, dialogs may open slowly, and unexpected modal windows may block input.

To achieve robust closed-loop operation without crashing or running in endless futile loops, Milestone M4 introduces:
1. **Feature 13: Episodic Working Memory (`parasite_ai/mind/memory.py`)**:
   - A bounded FIFO ring-buffer storing action history, target descriptors, timestamps, perceptual hashes, and visual diff outcomes.
   - Vectorized screen difference calculation computing exact fractional pixel change before and after actions, coupled with 64-bit difference hashing (`dHash`) for memory-efficient structural comparison.
   - Deterministic 3-Strike Failure Loop Detector: tracks consecutive interactive failures (clicks, typings, hotkeys that result in $< 0.02$ visual diff or logical errors) and trips a panic/strategy switch when 3 consecutive strikes occur.
   - Formatter for feeding recent history directly into LLM prompts.
2. **Feature 14: Dual-Mind Cognitive Pipeline (`parasite_ai/mind/dual_mind.py`)**:
   - **Pass 1: Persona Engine**: generates vivid character monologue, internal thought stream, speech bubble messages, and derives dynamic companion moods (`Curious`, `Focused`, `Cautious`, `Panic-Averted`, `Idle`) and states (`WATCHING`, `THINKING`, `DRIVING`, `OFFLOADING`, `USER_OVERRIDE`, `PROTECTED`).
   - **Pass 2: Action Dispatcher**: takes the character intent, validates Set-of-Mark targets, translates targets to physical desktop coordinates $(x, y)$, validates desktop boundary constraints, and executes physical hands (`MouseDriver`, `KeyboardDriver`) with sub-2ms hardware cancellation token protection.
   - **`DualMindPipeline`**: an orchestrator binding perception, safety guards, Pass 1 reasoning, Pass 2 execution, screen diff verification, and UIBridge telemetry into an atomic step loop.

---

## 2. Feature 13: Episodic Working Memory Architecture (`parasite_ai/mind/memory.py`)

### 2.1 Screen Diff Verification Algorithms

When the assistant acts on the physical desktop (e.g. clicks a button or enters text), the operating system UI responds visually (button presses, drop-down menus appear, cursor blinks, text renders, page navigates). Comparing the visual state before and after action execution confirms action impact.

#### Algorithm 1: Vectorized Pixel Difference Ratio
For two RGB or RGBA frames $I_{\text{pre}}$ and $I_{\text{post}}$ of dimension $W \times H$:
1. Convert frames to NumPy int16 arrays:
   $$\Delta(x, y) = \max_{c \in \{R, G, B\}} |I_{\text{post}}(x, y, c) - I_{\text{pre}}(x, y, c)|$$
2. A pixel $(x, y)$ is classified as changed if $\Delta(x, y) > \tau_{\text{channel}}$, where default $\tau_{\text{channel}} = 15$ (to eliminate compression artifacts and subtle GPU dithering noise).
3. The overall fractional difference is:
   $$\text{diff\_ratio} = \frac{\sum_{x, y} \mathbf{1}_{[\Delta(x, y) > \tau_{\text{channel}}]}}{W \times H}$$
4. If $\text{diff\_ratio} \ge \tau_{\text{diff}}$ (default $\tau_{\text{diff}} = 0.02$ from `VisionConfig.screen_diff_threshold`), the screen state has definitively changed.
5. Execution speed: $< 8\text{ms}$ on standard 1080p frame using NumPy vectorization.

#### Algorithm 2: 64-bit Perceptual Difference Hash (`dHash`)
To track visual state across many steps without storing multi-megabyte uncompressed screenshots in RAM:
1. Downscale the image to an $9 \times 8$ grayscale matrix using bilinear interpolation.
2. For each row $r \in [0..7]$ and column $c \in [0..7]$, compute boolean bit:
   $$b_{8r + c} = (P(c+1, r) > P(c, r))$$
3. Combine 64 boolean bits into a 16-character hexadecimal string.
4. Structural distance between two frames is computed via Hamming distance (count of differing bits $d_H \in [0..64]$).
5. Storage footprint: exactly 16 bytes per frame in memory.

### 2.2 Data Contracts & Models

```python
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import time
from pydantic import BaseModel, ConfigDict, Field

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
```

### 2.3 3-Strike Failure Loop Detector Specification

A loop occurs when the AI agent repeatedly performs actions that fail or produce zero visible change, leading to deadlocks.

**Strike Determination Rules**:
1. **Interactive Action Rule**:
   Only actions that are intended to change UI state are eligible for strikes:
   $$\text{InteractiveActions} = \{\text{CLICK}, \text{DOUBLE\_CLICK}, \text{RIGHT\_CLICK}, \text{CLICK\_AND\_TYPE}, \text{TYPE}, \text{HOTKEY}, \text{SCROLL}\}$$
   Passive or meta actions ($\text{WAIT}, \text{DONE}, \text{OFFLOAD\_WEB\_AI}, \text{PANIC}$) do NOT incur visual change strikes.
2. **Failure Strike Trigger**:
   An action receives a strike (`is_strike = True`) if:
   - Physical execution returned `success = False` (e.g. aborted, target element not found, coordinate out of bounds, driver error), OR
   - The action is in `InteractiveActions` AND observed $\text{screen\_diff} < \tau_{\text{diff}}$ (indicating zero visual response from the desktop).
3. **Consecutive Strikes Counter**:
   - If `is_strike == True`: `consecutive_strikes += 1`.
   - If `is_strike == False` (interactive action succeeded AND $\text{screen\_diff} \ge \tau_{\text{diff}}$): `consecutive_strikes = 0`.
4. **Loop Tripping Condition**:
   - `is_in_loop()` returns `True` if `consecutive_strikes >= 3`.
   - Once tripped, the pipeline detects cognitive deadlock, updates persona mood to `Panic-Averted` or `Cautious`, and triggers strategy reassessment (e.g., re-grounding from scratch, switching to Web AI offload, or asking user for input).

### 2.4 EpisodicMemory Ring-Buffer Specification

```python
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
    ) -> None:
        self.capacity = capacity
        self.screen_diff_threshold = screen_diff_threshold
        self.strike_limit = strike_limit
        self._buffer: collections.deque[StepRecord] = collections.deque(maxlen=capacity)
        self._consecutive_strikes: int = 0
        self._step_counter: int = 0
        self._lock = threading.RLock()

    def record_step(
        self,
        action: ActionPlan,
        success: bool = True,
        screen_diff: float = 0.0,
        user_goal: str = "",
        persona_thought: str = "",
        persona_speech: str = "",
        target_info: Optional[Dict[str, Any]] = None,
        pre_hash: Optional[str] = None,
        post_hash: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> StepRecord:
        ...

    def is_in_loop(self) -> bool:
        """Returns True if consecutive_strikes >= strike_limit."""
        with self._lock:
            return self._consecutive_strikes >= self.strike_limit

    def get_recent_history(self, n: int = 5) -> List[StepRecord]:
        """Returns last n records in chronological order."""
        ...

    def format_for_prompt(self, n: int = 5) -> str:
        """
        Formats recent steps into markdown for LLM context injection.
        Example:
        - [Step 1] CLICK target #3 ('Submit') at (450, 620) -> screen_diff=0.001 (NO CHANGE) [Strike 1/3]
        - [Step 2] CLICK target #3 ('Submit') at (450, 620) -> screen_diff=0.000 (NO CHANGE) [Strike 2/3]
        WARNING: 2 consecutive action strikes!
        """
        ...
```

---

## 3. Feature 14: Dual-Mind Cognitive Pipeline Architecture (`parasite_ai/mind/dual_mind.py`)

### 3.1 Pass 1: Persona Engine (`PersonaEngine`)

**Purpose**: Transform raw perception, memory, and user goals into character monologue, live thought streaming, and dynamic companion moods.

1. **System Prompt Formulation**:
   Uses `config.persona.system_prompt`, injecting:
   - Current user goal.
   - Screen context (active foreground window title, count of detected UI elements, summary of top interactive controls).
   - Episodic memory context (recent actions, outcomes, loop warnings).
2. **Output Decomposition**:
   Decomposes LLM output into:
   - `thought`: Internal stream displayed in the Companion Dock thought area.
   - `speech`: Character dialogue displayed in speech bubbles.
   - `mood`: Derived companion mood badge (`Curious`, `Focused`, `Cautious`, `Panic-Averted`, `Idle`).
3. **Mood & State Derivation Logic**:
   - If `consecutive_strikes >= 2`: Force mood to `Cautious`.
   - If `is_in_loop()`: Force mood to `Panic-Averted`.
   - If protected window: State `PROTECTED`, Mood `Cautious`.
   - If physical hardware interrupt: State `USER_OVERRIDE`, Mood `Curious`.
   - If executing physical hand actions: State `DRIVING`, Mood `Focused`.
   - If planning: State `THINKING`, Mood `Focused`.

### 3.2 Pass 2: Action Dispatcher (`ActionDispatcher`)

**Purpose**: Strictly parse, validate, and execute concrete physical actions using `MouseDriver` and `KeyboardDriver`.

1. **Target Coordinate Resolution**:
   - If `action.target_id` is supplied: Looks up element by ID in `som_elements: List[UIElement]`. Target coordinates are resolved to `(element.center_x, element.center_y)`.
   - If `action.coordinates` is supplied: Uses explicit coordinates `(x, y)`.
   - If both are missing for a target-dependent action (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`): Rejects action gracefully (`success=False`, `error="Target ID or coordinates required"`).
2. **Display Boundary Validation**:
   - Queries desktop screen metrics: $0 \le x < \text{screen\_width}$, $0 \le y < \text{screen\_height}$.
   - Prevents driver coordinate wrapping or ctypes overflow errors.
3. **Physical Hand Invocations**:
   - `CLICK`: `MouseDriver.click(x, y, button="left", cancellation_token=token, preview_reticle=True)`
   - `DOUBLE_CLICK`: `MouseDriver.click(x, y, button="left", clicks=2, cancellation_token=token, preview_reticle=True)`
   - `RIGHT_CLICK`: `MouseDriver.click(x, y, button="right", cancellation_token=token, preview_reticle=True)`
   - `CLICK_AND_TYPE`: `KeyboardDriver.click_and_type(x, y, text=action.text, submit=action.submit, cancellation_token=token, mouse_driver=mouse_driver)`
   - `TYPE`: `KeyboardDriver.type_text(action.text, submit=action.submit, cancellation_token=token)`
   - `HOTKEY`: `KeyboardDriver.hotkey(*action.keys, cancellation_token=token)`
   - `SCROLL`: `MouseDriver.scroll(action.scroll_amount, cancellation_token=token)`
   - `WAIT`: `time.sleep(action.wait_ms / 1000.0)` interruptible by `token.wait(...)`
   - `PANIC`: Signals emergency halt via `PanicManager` or `UIBridge.sig_panic_triggered`.
   - `DONE`: Signals goal completion.
4. **Preemption Handling**:
   - If `cancellation_token.is_set()` triggers before or during movement/typing:
     - Driver releases all held keys/mouse buttons immediately.
     - ActionDispatcher returns `ActionResult(success=False, interrupted=True, error="Interrupted by physical human input")`.

### 3.3 End-to-End Orchestrator: `DualMindPipeline`

```python
class DualMindPipeline:
    """
    Coordinates perception, Pass 1 Persona reasoning, Pass 2 Action dispatching,
    screen diff calculation, episodic memory recording, and UI telemetry.
    """
    def __init__(
        self,
        brain_manager: LocalBrainManager,
        memory: EpisodicMemory,
        mouse_driver: Optional[MouseDriver] = None,
        keyboard_driver: Optional[KeyboardDriver] = None,
        screen_grounder: Optional[Any] = None,
        interrupt_guard: Optional[InterruptGuard] = None,
        window_guard: Optional[WindowGuard] = None,
        bridge: Optional[UIBridge] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        ...

    def step(
        self,
        user_goal: str,
        screen_frame: Optional[Any] = None,
        grounded_elements: Optional[List[UIElement]] = None,
    ) -> StepRecord:
        """
        Executes a single closed-loop cognitive cycle:
        1. Safety guard check (WindowGuard, InterruptGuard).
        2. Perception & grounding (if not provided).
        3. Pass 1 Persona monologue generation -> UIBridge speech/thought.
        4. Pass 2 Action planning & validation.
        5. Physical execution with cancellation token -> UIBridge state DRIVING.
        6. Post-action settling and screen diff calculation.
        7. Episodic memory recording and loop detector update.
        """
```

---

## 4. Interoperability & Integration Matrix

| Integration Point | Interfacing Component | Contract / Interaction |
|---|---|---|
| **Set-of-Mark Grounding** | `ScreenGrounder` (Feature 12) & `UIElement` | `grounded_elements: List[UIElement]` mapped to `target_id` index `1..N`. Elements forwarded to `UIBridge.set_hud_targets()` for GhostHUD rendering. |
| **Visible Browser Offload** | `BrowserOffloader` (Feature 15) | When `action == "OFFLOAD_WEB_AI"`, pipeline delegates reasoning prompt to `offloader.query_web_ai(prompt)`. |
| **Physical Hands** | `MouseDriver` & `KeyboardDriver` | Physical actions pass `cancellation_token` from `InterruptGuard.get_cancellation_token()`. Reticle callback connected to `UIBridge.show_reticle`. |
| **UI Telemetry Hub** | `UIBridge` | Cross-thread signals emitted: `notify_state`, `notify_thought`, `notify_speech`, `notify_telemetry`, `set_hud_targets`, `clear_hud_targets`. |
| **Hardware Preemption** | `InterruptGuard` | If physical input occurs, token fires $<2\text{ms}$. Driver aborts, `DualMindPipeline` transitions UI to `USER_OVERRIDE`. |
| **Sensitive Windows** | `WindowGuard` | Active foreground checked before action. If sensitive, pipeline pauses actions, emits `PROTECTED` state. |

---

## 5. Automated Test Strategy

To verify Features 13 & 14 rigorously without requiring physical display hardware or live GUI windows, all tests execute in headless mode using synthetic PIL/NumPy images, `MockInputBackend`, and mocked LLM/Grounding providers.

### 5.1 Test Suite 1: `tests/test_memory.py` (Episodic Memory & Screen Diff)
1. `test_compute_pixel_diff_identical_images`: Confirms diff ratio is $0.0$ for identical frames.
2. `test_compute_pixel_diff_completely_inverted`: Confirms diff ratio is $1.0$ for inverted frames.
3. `test_compute_pixel_diff_subregion_change`: Synthetic image with known 5% area changed yields $\approx 0.05 \pm 0.005$.
4. `test_compute_pixel_diff_noise_below_threshold`: Pixel variations below channel threshold ($\le 10$) produce diff ratio $0.0$.
5. `test_compute_dhash_determinism_and_distance`: Same image yields identical 64-bit dHash; altered image yields positive Hamming distance.
6. `test_episodic_memory_capacity_ring_buffer`: Inserting 25 steps into a capacity-20 memory retains exactly the 20 most recent steps (FIFO eviction).
7. `test_episodic_memory_step_indexing`: Sequential `step_id` numbering ($1, 2, 3\dots$) across evictions.
8. `test_3_strike_loop_detector_triggers_on_third_strike`: 3 consecutive interactive actions with $\text{screen\_diff} < 0.02$ sets `is_in_loop() == True`.
9. `test_strike_counter_resets_on_successful_screen_diff`: 2 failures followed by 1 successful action with $\text{screen\_diff} \ge 0.02$ resets `consecutive_strikes` to 0.
10. `test_non_interactive_actions_do_not_incur_strikes`: `WAIT` and `DONE` actions with $\text{screen\_diff} = 0.0$ do NOT increment strike count.
11. `test_format_for_prompt_includes_warnings_and_history`: Formatted markdown output includes recent step actions, diffs, and loop strike warning banners.
12. `test_thread_safety_concurrent_recording`: 10 threads recording steps concurrently produce no race conditions or buffer corruption.

### 5.2 Test Suite 2: `tests/test_dual_mind.py` (Dual-Mind Cognitive Pipeline)
1. `test_action_plan_validation_click`: Validates `CLICK` with `target_id` and optional coordinates.
2. `test_action_plan_validation_click_and_type`: Validates `CLICK_AND_TYPE` with text and submit flags.
3. `test_action_plan_validation_hotkey`: Validates `HOTKEY` with key list or comma string.
4. `test_action_dispatcher_click_by_target_id`: Dispatches `CLICK` using `target_id=2`; resolves `UIElement.center` `(250, 400)` and invokes `MouseDriver.click`.
5. `test_action_dispatcher_click_and_type`: Dispatches `CLICK_AND_TYPE`; invokes `KeyboardDriver.click_and_type` at resolved coordinates.
6. `test_action_dispatcher_out_of_bounds_rejection`: Coordinates exceeding virtual screen bounds return `success=False` with descriptive validation error.
7. `test_action_dispatcher_cancellation_preemption`: Pre-set `cancellation_token` halts action immediately without calling physical drivers.
8. `test_persona_engine_monologue_and_mood`: Synthesizes prompt and extracts internal thought, external speech, and mood badge.
9. `test_persona_engine_mood_derivation_on_strikes`: When memory has 2 strikes, mood is derived as `Cautious`; when 3 strikes, `Panic-Averted`.
10. `test_dual_mind_pipeline_end_to_end_step`: Full pipeline step: perception -> Pass 1 -> Pass 2 -> Diff -> Memory record.
11. `test_dual_mind_pipeline_sensitive_window_pause`: When `WindowGuard.is_safe_to_operate() == False`, pipeline pauses and sets UI state `PROTECTED`.
12. `test_dual_mind_pipeline_interrupt_guard_override`: When `InterruptGuard.is_interrupted() == True`, pipeline sets UI state `USER_OVERRIDE`.
13. `test_dual_mind_pipeline_loop_break_strategy`: Pipeline detects 3-strike loop and triggers panic or fallback action.
14. `test_dual_mind_pipeline_done_action`: Action `DONE` transitions UI state to `WATCHING` and returns completion.

---

## 6. Implementation Checklist for Worker Agent

- [ ] Create `parasite_ai/mind/memory.py`:
  - [ ] Implement `compute_pixel_diff` and `compute_dhash` / `hamming_distance`.
  - [ ] Implement `ActionType`, `ActionPlan`, `DiffResult`, and `StepRecord` Pydantic models.
  - [ ] Implement `EpisodicMemory` ring buffer with thread-safe `RLock`.
  - [ ] Implement 3-strike failure loop detector and `format_for_prompt`.
- [ ] Create `parasite_ai/mind/dual_mind.py`:
  - [ ] Implement `PersonaEngine` for Pass 1 monologue, thought/speech extraction, and mood derivation.
  - [ ] Implement `ActionDispatcher` for Pass 2 deterministic execution with target resolution and cancellation token checks.
  - [ ] Implement `DualMindPipeline` orchestrating perception, Pass 1, Pass 2, diff verification, memory recording, and UIBridge telemetry.
- [ ] Update `parasite_ai/mind/__init__.py` exporting public classes (`EpisodicMemory`, `ActionPlan`, `ActionType`, `StepRecord`, `PersonaEngine`, `ActionDispatcher`, `DualMindPipeline`, `compute_pixel_diff`, `compute_dhash`).
- [ ] Create `tests/test_memory.py` with 12 unit tests.
- [ ] Create `tests/test_dual_mind.py` with 14 unit tests.
- [ ] Run `uv run pytest` to achieve 100% test pass rate across entire project.
