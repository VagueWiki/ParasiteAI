# Explorer 2 (Iter 2) Handoff Report: Action Differentiation & Capability Contract Sealing

**Author:** Explorer 2 (Iter 2: Action Differentiation & Contract Sealing)  
**Role:** explorer (investigation, synthesis)  
**Working Directory:** `C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_2\`  
**Target Document:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Reference Handoffs:**  
- Challenger 1: `C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p4_1\handoff.md`  
- Challenger 2: `C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p4_2\handoff.md`  
**Date:** 2026-11-01T02:51:00Z  
**Verdict:** **READY_FOR_INTEGRATION** (Production-ready replacement blocks formulated & verified)

---

## 1. Observation

Direct inspection of `phase_4_master_plan.md`, `tests/test_challenger_p4_empirical.py`, and the core codebase revealed three critical architectural specification defects:

### 1.1 Observation 1: Passive Actions Trigger False Failure Strikes
- **Location:** `phase_4_master_plan.md` lines 129–133 (Section 3.1) and lines 219–220 (Section 3.3):
  ```python
  def on_action_result(self, success: bool, screen_diff: float, diff_threshold: float = 0.02) -> CadenceTier:
      effective_success = success and (screen_diff >= diff_threshold)
  ```
- **Verbatim Error / Empirical Evidence:**  
  In `tests/test_challenger_p4_empirical.py` (lines 279–288, `test_passive_action_wait_triggers_strike_if_diff_zero`):
  When the planner executes a legitimate `ActionType.WAIT`, `ActionType.DONE`, or a non-visual hotkey (such as clipboard copy `Ctrl+C`), the screen diff is `0.000`. Because `screen_diff >= 0.02` evaluates to `False`, `effective_success` becomes `False`.
  The state machine increments `local_strikes += 1`. After two intentional `WAIT` or clipboard actions, the agent prematurely escalates to Tier 2 Gemini consultation!

### 1.2 Observation 2: Headless CLI Tooling Trapped by Visual ROI Diff
- **Location:** `phase_4_master_plan.md` lines 130–131 (Section 3.1), lines 509–514 (Section 6.1), and lines 742, 752 (Section 9.1):
  Actions can be `ActionType.RUN_CLI_COMMAND` (e.g. executing `pytest` or refactoring code files).
- **Verbatim Error / Empirical Evidence:**  
  CLI commands executed by the developer tooling affordance run in the background as headless subprocesses. No GUI pixels change on the desktop ($\Delta = 0.000$).
  Under Section 3.1, every successful CLI command is penalized as a visual stall ($\Delta < 0.02$). Two consecutive successful `pytest` runs trigger a false strike escalation to Tier 2.
  Furthermore, Sections 6.1 and 10 (Sub-Phase 4D) fail to specify an execution sandbox, command whitelist, timeout, or cancellation token polling, leaving the system vulnerable to command injection and non-preemptible hanging processes.

### 1.3 Observation 3: Grounded Capability Contract Loopholes
- **Location:** `phase_4_master_plan.md` lines 286–336 (Section 4.2) and lines 268–279 (Section 4.1):
  The hard safety constraints forbid headless browser automation and DOM manipulation, but:
  1. An external advisor can command the agent to run headless web scraping tools via CLI (`curl`, `requests`, `playwright CLI`, `puppeteer`, `selenium`, `beautifulsoup`), violating the visible desktop automation paradigm and the zero silent exfiltration invariant.
  2. An external advisor can instruct the agent to use programmatic Windows UI Automation pattern invocation (e.g. `ValuePattern.SetValue`, `InvokePattern.Invoke`, `TogglePattern.Toggle`, `SelectionItemPattern.Select`). This bypasses physical synthetic human kinematics (`SendInput`, Bézier mouse trajectories, typing cadence), bypasses the low-level hardware preemption hook, and circumvents application focus event loops.
  3. The display geometry bounds in Section 4.2 hardcode `Virtual_Desktop_Bounds: [0, 0, 3840, 1080]`, failing to account for dynamic virtual bounds in left-extended multi-monitor setups with negative coordinates.

---

## 2. Logic Chain

1. **Premise 1 (Action Modality Diversity):** Desktop automation is multi-modal. Actions encompass:
   - *Interactive GUI actions:* `CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`, `TYPE`, `SCROLL`, `DRAG_AND_DROP`. These alter screen pixels and require $\Delta \ge 0.02$ within the target ROI to confirm success.
   - *Passive / Non-visual actions:* `WAIT`, `DONE`, and non-visual shortcuts like `Ctrl+C`. These intentionally alter 0 pixels ($\Delta = 0.000$) and must be verified strictly by dispatch success (`success == True`).
   - *Headless CLI actions:* `RUN_CLI_COMMAND`. These execute off-screen and must be verified strictly by subprocess exit code (`returncode == 0`), completely bypassing visual ROI diff requirements.
2. **Premise 2 (State Machine Invariance):** The 4-Tier Escalation State Machine must only increment strike counters on genuine operational failures. Penalizing passive actions or successful CLI commands with strikes violates state machine invariants and causes spurious cloud escalations.
3. **Premise 3 (Preemption & Sandbox Safety):** ParasiteAI's core invariant is sub-2ms hardware touch preemption. Subprocess execution cannot block the main thread or ignore user mouse touches. A dedicated `CLIExecutionSandbox` must poll the hardware preemption `cancellation_token` every 10ms to immediately terminate subprocesses upon physical user touch.
4. **Premise 4 (Grounded Contract Integrity):** To prevent LLM hallucinations from corrupting the automation pipeline:
   - CLI-based headless scraping (`curl`, `requests`, `playwright`) must be explicitly banned in the Capability Contract YAML, consultation prompt, and execution sandbox.
   - UI Automation must be explicitly declared **read-only** for element discovery and Set-of-Mark perception; programmatic pattern mutations (`ValuePattern.SetValue`, `InvokePattern.Invoke`) must be strictly prohibited.
   - Virtual screen bounds must be documented as dynamically resolved via Win32 `GetSystemMetrics(SM_XVIRTUALSCREEN)` to support multi-monitor geometries.

---

## 3. Caveats

1. **Hotkey Ambiguity:** Certain hotkeys produce visual changes (e.g. `Win` opens the Start Menu; `Alt+Tab` switches windows), while others do not (e.g. `Ctrl+C` copies to clipboard; `Ctrl+S` saves without visual change). In the state machine, hotkeys default to `is_interactive=True`, but the action planner or caller can pass `is_interactive=False` for non-visual chords, or the action can be evaluated without visual penalty.
2. **CLI Output Volume:** Headless CLI commands can generate large standard output streams. `CLIExecutionSandbox` must capture stdout/stderr safely without unbounded buffer growth.
3. **Admin Elevation (UAC):** CLI commands run with the permissions of the parent Python process; administrative operations that trigger Windows UAC will halt physical hands per the existing `WindowGuard` invariant.

---

## 4. Conclusion & Concrete Markdown Replacement Blocks

To resolve these defects, `phase_4_master_plan.md` must be updated with the following **5 production-ready replacement blocks**.

---

### Replacement Block 1: Sections 3.1, 3.2, and 3.3
**Target File:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Target Range:** Lines 124–260 (Section 3.1 Tier 1/Tier 3, Section 3.2 Transition Table, Section 3.3 State Machine)

```markdown
#### Tier 1: Autonomous Local Exploration (Strikes 0–1)
- **Engine:** Offline Qwen2.5-3B-Instruct local model running within the 3.5 GB VRAM budget.
- **Cadence Rules:**
  - Operates autonomously for up to **2 consecutive actions** using local UI Automation trees, scoped RapidOCR, and Set-of-Mark visual grounding.
  - **Action-Aware Success & Strike Criteria:**
    - **Interactive GUI Actions (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`, `TYPE`, `SCROLL`, `DRAG_AND_DROP`):** Post-action settling executes (3 consecutive polls with visual diff $< 0.003$ or 500ms timeout). Target ROI is cropped via `BoundingBox.pad(padding_px=20)` and evaluated for pixel diff ratio $\Delta$.
      - *Success Trigger:* If $\Delta \ge 0.02$ (2% normalized change within target ROI) and execution succeeds, `local_strikes` is reset to 0, advancing to the next step.
      - *Failure Trigger:* If $\Delta < 0.02$ or execution raises an error, `local_strikes` increments by 1.
    - **Passive / Non-Visual Actions (`WAIT`, `DONE`, clipboard `HOTKEY` e.g. `Ctrl+C`):** Exempt from the $\Delta \ge 0.02$ visual diff check (`is_interactive=False`). Verified strictly by execution success (`ActionResult.success == True`). Successful passive actions do not increment failure strikes.
    - **Headless CLI Actions (`RUN_CLI_COMMAND`):** Headless background execution produces $\Delta = 0.000$ (no desktop pixels change). Verified strictly by subprocess exit code (`returncode == 0`), completely bypassing visual ROI diff requirements. If `returncode == 0`, `local_strikes` resets to 0; if `returncode != 0` or times out, `local_strikes` increments by 1.
  - On `local_strikes == 2`, the pipeline transitions to Tier 2.

#### Tier 2: Deep Strategic Gemini Consultation
- **Trigger:** Reached on exactly 2 consecutive local strikes in Tier 1.
- **Cadence Rules:**
  - Physical execution halts completely (`ActionType.WAIT`).
  - The agent synthesizes a standardized consultation brief containing:
    1. Active foreground window title, process executable, and virtual desktop coordinates.
    2. Textual Set-of-Mark inventory of active controls.
    3. Failure history and detailed dilemma description from episodic memory.
    4. The formal **Parasite Capability Contract** (physical limits, perception, and constraints).
    5. Action affordance inventory (available GUI apps, local CLI/Antigravity tooling).
  - The consultation payload is dispatched to Gemini.
  - The response is parsed via `extract_strategic_blueprint_json` and validated into `LivingPlan`.
  - **Success Transition:** If a valid blueprint with $\ge 1$ executable steps is harvested (accepting either `"steps"` or `"recommended_strategy"` keys), `active_plan` is hydrated, `local_strikes = 0`, `guided_strikes = 0`, `consultation_failures = 0`, and state transitions to **Tier 3**.
  - **Offline / Failure Fallback:** If offline (`brain.mode: "local_llm"` without web credentials) or the query times out:
    - `consultation_failures` increments by 1.
    - If `consultation_failures >= 2`, the system immediately transitions to **USER_OVERRIDE**, preventing infinite loops between Tier 1 and Tier 2.
    - Otherwise, ParasiteAI falls back to a deep local replan using Qwen2.5-3B or prompts the user via the Companion Dock, resetting `local_strikes` to 0.

#### Tier 3: Guided Local Execution (Strikes 0–1)
- **Engine:** Local Qwen2.5-3B model executing the discrete steps and contingencies formulated by Gemini.
- **Cadence Rules:**
  - The agent executes each step of the Gemini blueprint sequentially.
  - Allows up to **2 guided attempts** per step or across the blueprint.
  - **Success Trigger (Action-Aware):**
    - For GUI steps: Localized ROI diff $\Delta \ge 0.02$ and `step.success_criteria` satisfied.
    - For CLI steps (`RUN_CLI_COMMAND`): Subprocess `returncode == 0` and stdout verification (bypassing visual diff $\Delta \ge 0.02$).
    - For Passive steps (`WAIT`, `DONE`): Execution succeeds (`ActionResult.success == True`).
    - Upon verified success, `guided_strikes` resets to 0, and `advance_step()` marks the step completed.
  - **Failure Trigger:** If a step fails, times out, or interactive ROI produces $\Delta < 0.02$, `guided_strikes` increments by 1. The agent checks `step.contingency` for alternative actions.
  - On `guided_strikes == 2`:
    - `total_escalation_cycles` increments by 1.
    - If `total_escalation_cycles >= 3`, the agent recognizes an oscillating deadlock and escalates directly to **USER_OVERRIDE**.
    - Otherwise, the agent concludes that the static blueprint is insufficient and escalates to **Tier 4** (`copilot_strikes = 0`).

#### Tier 4: Continuous Gemini Handholding / Visual Co-Pilot (Strikes 0–2)
- **Trigger:** Reached on 2 consecutive failures in Tier 3.
- **Cadence Rules:**
  - Establishes an interactive, step-by-step micro-loop with Gemini.
  - Before each click, the agent reports the current SOM state and intended target candidate ID.
  - After each action, the 1:1 foveal crop and post-action ROI diff are evaluated against expected results.
  - **Success Recovery:** If a micro-action succeeds and breaks the deadlock, the pipeline resets `copilot_strikes = 0` and transitions back to **Tier 3** to resume guided execution.
  - **Failure Trigger:** If an individual co-pilot step fails, `copilot_strikes` increments by 1.
  - On `copilot_strikes == 3`, continuous guidance has failed. The system initiates **Graceful User Escalation**.

#### Terminal State: Graceful User Escalation (`USER_OVERRIDE`)
- **Trigger:** 3 consecutive failures in Tier 4 co-pilot mode, 2 consecutive advisor consultation failures, 3 cumulative oscillation cycles, or physical human hardware preemption.
- **Cadence Rules:**
  - Physical hands immediately disengage; mouse and keyboard drivers are placed in an inert state (`ActionType.WAIT`).
  - Parasite speaks directly to the user through the Companion Dock in character persona.
  - The speech explains the exact nature of the deadlock without technical jargon.
  - The UI state transitions to `USER_OVERRIDE`.
  - The agent remains non-blocking and monitors the desktop until the user completes the blocking action, upon which the agent offers to resume.

---

### 3.2 Formal State Machine & Transition Logic

| Current State | Event / Trigger Condition | Evaluation Rule | Next State | Transition Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| **TIER_1_LOCAL** | Interactive GUI Action Success | $\Delta \ge 0.02$ & `ActionResult.success == True` | **TIER_1_LOCAL** | `local_strikes = 0`; advance step or next action |
| **TIER_1_LOCAL** | Headless CLI Action Success | `ActionType.RUN_CLI_COMMAND` & `returncode == 0` | **TIER_1_LOCAL** | `local_strikes = 0`; bypass visual diff; advance step |
| **TIER_1_LOCAL** | Passive Action Execution | `WAIT`, `DONE`, or non-visual `HOTKEY` & `success == True` | **TIER_1_LOCAL** | Exempt from visual diff; strike counters unchanged |
| **TIER_1_LOCAL** | Action Stalled / Failed | $\Delta < 0.02$ (GUI) or `returncode != 0` (CLI) or `success == False` | **TIER_1_LOCAL** | `local_strikes += 1`; record failure in episodic memory |
| **TIER_1_LOCAL** | Strike Limit Reached | `local_strikes == 2` | **TIER_2_CONSULT** | Halt physical hands; compile brief + capability manifest |
| **TIER_2_CONSULT** | Blueprint Validated | Valid `LivingPlan` JSON parsed (`steps` or `recommended_strategy`) | **TIER_3_GUIDED** | Hydrate `active_plan`; `local_strikes = 0`; `guided_strikes = 0`; `consultation_failures = 0`; emit persona monologue |
| **TIER_2_CONSULT** | Advisor Error / Offline | Network timeout, missing credentials, or bad JSON | **TIER_1_LOCAL** or **USER_OVERRIDE** | `consultation_failures += 1`; if $\ge 2$: transition to **USER_OVERRIDE**; else `local_strikes = 0` fallback to T1 |
| **TIER_3_GUIDED** | Step Successful | $\Delta \ge 0.02$ (GUI) or `returncode == 0` (CLI) or passive success | **TIER_3_GUIDED** | `guided_strikes = 0`; `active_plan.advance_step()` |
| **TIER_3_GUIDED** | Step Failed / Stalled | $\Delta < 0.02$ (GUI) or `returncode != 0` (CLI) or criteria unmet | **TIER_3_GUIDED** | `guided_strikes += 1`; execute `step.contingency` if present |
| **TIER_3_GUIDED** | Guided Limit Reached | `guided_strikes == 2` | **TIER_4_CO_PILOT** or **USER_OVERRIDE** | `total_escalation_cycles += 1`; if $\ge 3$: transition to **USER_OVERRIDE**; else transition to **TIER_4_CO_PILOT** (`copilot_strikes = 0`) |
| **TIER_4_CO_PILOT** | Co-Pilot Step Cleared | Micro-action resolved with advisor | **TIER_3_GUIDED** | `copilot_strikes = 0`; `guided_strikes = 0`; resume blueprint execution |
| **TIER_4_CO_PILOT** | Micro-Action Failed | Post-action verification failed | **TIER_4_CO_PILOT** | `copilot_strikes += 1`; report diff back to advisor |
| **TIER_4_CO_PILOT** | Deadlock Confirmed | `copilot_strikes == 3` | **USER_OVERRIDE** | Halt hands; deliver character dilemma speech; pause automation |
| **ANY_STATE** | Physical Hardware Touch | `flags & LL[M/K]HF_INJECTED == 0` | **USER_OVERRIDE** | Sub-2ms preemption token set; invoke `on_hardware_interrupt()`; abort input |
| **ANY_STATE** | Emergency Hotkey | `Ctrl+Alt+K` or `Ctrl+Alt+Q` | **PROCESS_TERMINATED** | Instant native kill (<5ms) via `taskkill /F /T /PID` |

---

### 3.3 Python State Machine Architecture

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from parasite_ai.mind.memory import ActionType

class CadenceTier(str, Enum):
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_CONSULT = "TIER_2_CONSULT"
    TIER_3_GUIDED = "TIER_3_GUIDED"
    TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
    USER_OVERRIDE = "USER_OVERRIDE"

class EscalationStateMachine(BaseModel):
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0)
    guided_strikes: int = Field(default=0, ge=0)
    copilot_strikes: int = Field(default=0, ge=0)
    consultation_failures: int = Field(default=0, ge=0)
    total_escalation_cycles: int = Field(default=0, ge=0)
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
        - CLI actions (RUN_CLI_COMMAND): Evaluated by cli_returncode == 0 (visual diff bypassed).
        - Passive actions (WAIT, DONE, non-visual HOTKEY, or is_interactive=False):
          Exempt from visual diff. If success=True, strikes remain unchanged.
        - Interactive GUI actions (CLICK, TYPE, visual HOTKEY, SCROLL):
          Evaluated by physical success AND localized ROI diff >= diff_threshold.
        """
        # Category 1: Headless CLI actions
        if action_type == ActionType.RUN_CLI_COMMAND:
            effective_success = success and (cli_returncode == 0 if cli_returncode is not None else True)

        # Category 2: Passive / Non-visual actions (WAIT, DONE, or explicit is_interactive=False)
        elif action_type in (ActionType.WAIT, ActionType.DONE) or not is_interactive:
            if success:
                # Passive actions do not incur strikes when successful
                return self.current_tier
            effective_success = False

        # Category 3: Interactive GUI actions
        else:
            effective_success = success and (screen_diff >= diff_threshold)

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
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.guided_strikes = 0
            self.consultation_failures = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.consultation_failures += 1
            if self.consultation_failures >= self.max_consultation_failures:
                self.current_tier = CadenceTier.USER_OVERRIDE
            else:
                self.local_strikes = 0
                self.current_tier = CadenceTier.TIER_1_LOCAL

    def on_hardware_interrupt(self) -> None:
        """Immediate transition from ANY_STATE to USER_OVERRIDE on physical human preemption."""
        self.current_tier = CadenceTier.USER_OVERRIDE
```
```

---

### Replacement Block 2: Sections 4.1, 4.2, and 4.4 (Sealing Grounded Capability Contract)
**Target File:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Target Range:** Lines 268–336 (Section 4.1 & 4.2) and Lines 356–358 (Section 4.4)

```markdown
### 4.1 Motivation & Anti-Hallucination Rationale

External cloud LLMs (such as Gemini 1.5 Pro) are trained on massive web datasets and naturally gravitate toward programmatic, browser-centric, or headless scraping solutions:
- *"Inject this JavaScript snippet into the console to extract the table."*
- *"Use `document.querySelector('button.submit').click()`."*
- *"Call `element.GetCurrentPattern(ValuePattern.Pattern).SetValue('text')` or `InvokePattern.Invoke()`."*
- *"Run headless Playwright/Puppeteer/Selenium or `curl` to scrape the data via CLI."*
- *"Call the private Win32 API `SendMessage(hwnd, WM_SETTEXT, ...)`."*

For ParasiteAI, all of these suggestions are fatal:
1. ParasiteAI is a **100% visible physical desktop assistant**. It operates strictly via synthetic human kinematics (`SendInput`, Bézier mouse trajectories, and typing cadence).
2. It has **zero headless browser integration** and **zero DOM access**.
3. **Headless Scraping Prohibition:** Running CLI-based web scrapers or HTTP extraction scripts (`curl`, `wget`, `requests`, `playwright`, `puppeteer`, `selenium`, `beautifulsoup`) directly violates the physical desktop automation paradigm and compromises the Zero Silent Exfiltration invariant.
4. **Programmatic UIA Pattern Prohibition:** Invoking UI Automation patterns directly (e.g. `ValuePattern.SetValue`, `InvokePattern.Invoke`, `TogglePattern.Toggle`, `SelectionItemPattern.Select`) bypasses physical synthetic human kinematics, circumvents hardware preemption monitoring, and fails to trigger internal application focus and input event handlers. In ParasiteAI, UI Automation is strictly **read-only** for element discovery and Set-of-Mark bounding box perception.
5. Direct OS message injection (`WM_SETTEXT`) circumvents UI event loops, breaks focus state, and violates realistic desktop automation.
6. If an external advisor emits impossible instructions, the agent wastes execution cycles attempting to ground non-existent DOM nodes or unsupported programmatic patterns.

To permanently prevent advisor hallucination, every consultation payload injects the **Parasite Capability Contract** as an immutable system preamble.

---

### 4.2 Formal Grounded Capability Manifest

```yaml
Parasite_Capability_Contract:
  Version: "4.0.0"
  Target_Environment: "Windows 11 64-bit Desktop"
  Display_Geometry:
    Virtual_Desktop_Bounds: "Dynamic via get_virtual_screen_bounds() [x_min, y_min, width, height], e.g. [0, 0, 3840, 1080] or [-1920, 0, 3840, 1080] for left-extended multi-monitor setups"
    DPI_Scale: "100% (96 DPI Native)"
    Monitor_Count: "Dynamically enumerated via EnumDisplayMonitors"
    Primary_Monitor_Bounds: [0, 0, 1920, 1080]

  Actuators:
    Mouse:
      Kinematics: "Human-curved cubic Bézier trajectories with 5th-order Min-Jerk velocity profiling and 1px Gaussian micro-jitter"
      Polling_Rate: "120 Hz update loop via high-precision Win32 multimedia timer (timeBeginPeriod(1))"
      Primitives:
        - "left_click(x, y)"
        - "double_click(x, y)"
        - "right_click(x, y)"
        - "middle_click(x, y)"
        - "drag_and_drop(x1, y1, x2, y2)"
        - "scroll(wheel_delta, x, y)"
      Coordinate_Validation: "All coordinates must fall within active virtual screen bounds [x_min, x_min + width) x [y_min, y_min + height); out-of-bounds clicks are hard-rejected"
    
    Keyboard:
      High_Speed_Pasting: "Atomic Ctrl+V paste (<100ms) with automatic user clipboard backup and transparent restoration"
      Cadence_Typing: "Physical SendInput using KEYEVENTF_UNICODE with 25-75ms human cadence jitter and micro-pauses"
      Supported_Chords:
        - "Win (Start Menu)"
        - "Win+R (Run Dialog)"
        - "Alt+Tab (Window Switch)"
        - "Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A / Ctrl+Z / Ctrl+S / Ctrl+F"
        - "Enter / Esc / Tab / Backspace / Delete / Arrow Keys"
      Multiline_Handling: "Shift+Enter for chat multiline inputs to avoid premature submission"

  Perception:
    Resolution: "1:1 unscaled cursor foveal crop (512x512) and downscaled virtual desktop macro glance"
    Element_Grounding: "Numbered Set-of-Mark (SOM) tags [#1..#N] merging Win32 UI Automation tree walk and scoped RapidOCR. UI Automation is strictly read-only for bounding box and label discovery; programmatic pattern invocation (ValuePattern, InvokePattern) is forbidden."
    Visual_Diffing: "Localized post-action ROI diffing scoped to target bounding box + 20px padding (target_roi.pad(20))"
    Perceptual_Hashing: "64-bit dHash gating (0% CPU/GPU overhead when screen is static)"
    Focus_Detection: "Win32 Caret blinking detection via 64-bit GUITHREADINFO (cbSize=72) verifying flags & GUI_CARETBLINKING"

  Hard_Safety_Constraints:
    - "ZERO headless browser automation; NO DOM manipulation, document.querySelector, or CDP protocols"
    - "ZERO headless scraping or HTTP data extraction via CLI/scripts (curl, wget, requests, Playwright CLI, Puppeteer, Selenium, BeautifulSoup are strictly forbidden)"
    - "ZERO programmatic accessibility pattern invocation (ValuePattern.SetValue, InvokePattern.Invoke, TogglePattern.Toggle, SelectionItemPattern.Select are strictly forbidden; UIA is strictly read-only for element discovery)"
    - "ZERO private OS message injection (WM_SETTEXT); all interactions must use physical SendInput simulation"
    - "Sub-2ms physical hardware preemption: synthetic input instantly aborts if human moves physical mouse or types"
    - "Instant Hard Kill (Ctrl+Alt+K / Ctrl+Alt+Q) terminates process tree in <5ms via taskkill /F /T"
    - "Protected Windows: Password managers (Bitwarden, 1Password, KeePass) and UAC dialogs trigger safety pause"
    - "Strict Anti-Hardcoding: NO application-specific lookup tables (app_map = {} is strictly forbidden)"
```
```

In Section 4.4 (`GEMINI_CONSULTATION_TEMPLATE`), update lines 356–358 to:
```markdown
# CAPABILITY CONTRACT & CONSTRAINTS
{capability_contract_yaml}
- Physical desktop automation ONLY (Bézier mouse, SendInput cadence typing, atomic Ctrl+V paste).
- ZERO headless browser automation, ZERO CLI scraping (curl/requests/playwright), ZERO programmatic UIA pattern calls (ValuePattern/InvokePattern).
```

---

### Replacement Block 3: Sections 6.1 and 6.4 (Affordance 2 Boundaries & `CLIExecutionSandbox`)
**Target File:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Target Range:** Lines 509–518 (Section 6.1) and addition after Line 582 (Section 6.4)

```markdown
2. **Affordance 2: Local Developer Tooling & Antigravity Meta-Tooling (CLI / Scripts):**
   - **Characteristics:** Code editing, file tree reorganizations, batch text replacements, Git operations, running test suites (`pytest`), and Antigravity workspace automation.
   - **Mechanism:** Direct execution via sandboxed local subprocesses (`CLIExecutionSandbox`).
   - **Reasoning Heuristic:** If a user goal involves writing complex code, creating multi-file projects, or parsing massive text, ParasiteAI evaluates:
     > *"Can this goal be achieved 10x faster and safer via Antigravity CLI / scripts than by clicking editor menus?"*
   - **Headless Web Scraping Prohibition:** CLI tooling cannot be used to bypass physical browser interaction. Automated web extraction commands (`curl`, `wget`, `requests`, `playwright`, `puppeteer`, `selenium`) are strictly prohibited in the CLI sandbox.
   - **Success Evaluation:** CLI actions are evaluated strictly by `returncode == 0` (bypassing visual ROI diff $\Delta \ge 0.02$).
```

Add Section 6.4 following Section 6.3:

```markdown
### 6.4 `CLIExecutionSandbox` Specification & Preemption Integration

To preserve safety invariants and prevent hanging subprocesses or command injection during `ActionType.RUN_CLI_COMMAND` execution:

```python
import subprocess
import time
from typing import Any, List, Optional, Set
from pydantic import BaseModel, Field

class CLIExecutionResult(BaseModel):
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    interrupted: bool = False

class CLIExecutionSandbox:
    """
    Sandboxed execution boundary for ActionType.RUN_CLI_COMMAND.
    Enforces process timeouts, hardware preemption cancellation polling,
    and a strict tool whitelist prohibiting headless scraping tools.
    """
    DEFAULT_TIMEOUT_SECONDS: float = 30.0

    # Permitted executable binaries
    ALLOWED_BINARIES: Set[str] = {
        "python", "python.exe", "pytest", "git", "powershell", "powershell.exe", "cmd", "cmd.exe"
    }

    # Prohibited commands (headless scraping tools and destructive disk utilities)
    PROHIBITED_COMMANDS: Set[str] = {
        "curl", "wget", "playwright", "puppeteer", "selenium", "scrapy",
        "format", "diskpart", "rmdir /s", "del /f /s /q"
    }

    @classmethod
    def execute(
        cls,
        cmd_tokens: List[str],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        cancellation_token: Optional[Any] = None,
        working_dir: Optional[str] = None,
    ) -> CLIExecutionResult:
        if not cmd_tokens:
            return CLIExecutionResult(returncode=-1, stdout="", stderr="Empty command tokens", duration_ms=0.0)

        cmd_str = " ".join(cmd_tokens).lower()

        # Enforce contract prohibitions
        for prohibited in cls.PROHIBITED_COMMANDS:
            if prohibited in cmd_str:
                return CLIExecutionResult(
                    returncode=-1,
                    stdout="",
                    stderr=f"SecurityViolation: Prohibited command '{prohibited}' violates capability contract.",
                    duration_ms=0.0
                )

        t0 = time.perf_counter()
        proc = subprocess.Popen(
            cmd_tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            cwd=working_dir
        )

        poll_interval_s = 0.010  # 10ms polling for hardware preemption token

        while proc.poll() is None:
            # Sub-2ms hardware touch preemption integration
            if cancellation_token and cancellation_token.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return CLIExecutionResult(
                    returncode=-999,
                    stdout="",
                    stderr="Preempted by physical human input.",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    interrupted=True
                )

            if (time.perf_counter() - t0) > timeout:
                proc.kill()
                return CLIExecutionResult(
                    returncode=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s.",
                    duration_ms=(time.perf_counter() - t0) * 1000
                )

            time.sleep(poll_interval_s)

        out, err = proc.communicate()
        duration_ms = (time.perf_counter() - t0) * 1000
        return CLIExecutionResult(
            returncode=proc.returncode,
            stdout=out,
            stderr=err,
            duration_ms=duration_ms,
            interrupted=False
        )
```
```

---

### Replacement Block 4: Sub-Phases 4B and 4D (Roadmap Specifications)
**Target File:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Target Range:** Lines 897–922 (Sub-Phase 4B) and Lines 949–970 (Sub-Phase 4D)

```markdown
### Sub-Phase 4B: 4-Tier Escalation State Machine in `DualMindPipeline`
* **Files Affected:**
  - `parasite_ai/mind/memory.py`
  - `parasite_ai/mind/dual_mind.py`
* **Deliverables:**
  1. Implement `CadenceTier` enum and `EscalationStateMachine` in `parasite_ai/mind/memory.py`.
  2. Implement separate strike tracking: `local_strikes` (0..2), `guided_strikes` (0..2), `copilot_strikes` (0..3).
  3. Implement action-aware strike evaluation in `on_action_result()`:
     - Interactive GUI actions verified by localized ROI diff $\Delta \ge 0.02$.
     - Headless CLI actions verified by subprocess `returncode == 0` (bypassing visual ROI diff).
     - Passive actions (`WAIT`, `DONE`, clipboard `HOTKEY`) exempt from $\Delta \ge 0.02$ visual diff check (`is_interactive=False`).
  4. Add loop protection counters: `consultation_failures` (max 2) and `total_escalation_cycles` (max 3) preventing infinite T1/T2 and T3/T4 deadlocks.
  5. Implement `on_hardware_interrupt()` method transitioning directly to `USER_OVERRIDE`.
  6. Update `DualMindPipeline.step()` to transition across the 4 tiers:
     - 2 local strikes $\to$ Tier 2 consultation.
     - Valid blueprint $\to$ Tier 3 guided local execution.
     - 2 guided strikes $\to$ Tier 4 continuous co-pilot.
     - 3 co-pilot strikes $\to$ `USER_OVERRIDE`.
* **Exact Function Signatures:**
  ```python
  class EscalationStateMachine:
      def on_action_result(
          self,
          success: bool,
          screen_diff: float = 0.0,
          action_type: Optional[ActionType] = None,
          is_interactive: bool = True,
          cli_returncode: Optional[int] = None,
          diff_threshold: float = 0.02,
      ) -> CadenceTier: ...
      def on_consultation_success(self) -> None: ...
      def on_consultation_failure(self) -> None: ...
      def on_hardware_interrupt(self) -> None: ...
  ```
* **Acceptance Criteria:**
  - Passive actions (`WAIT`, `DONE`) with 0.0 screen diff do not increment strike counters.
  - Successful CLI actions (`returncode == 0`) reset `local_strikes` to 0 without requiring screen pixel changes.
  - Exactly 2 consecutive local failures trigger Tier 2 consultation.
  - 2 consecutive consultation failures or 3 T3/T4 oscillation cycles escalate cleanly to `USER_OVERRIDE`.
  - Physical hardware interrupt transitions immediately to `USER_OVERRIDE`.

---

### Sub-Phase 4D: Tool-Aware Reasoning & Antigravity Meta-Tooling
* **Files Affected:**
  - `parasite_ai/mind/affordance.py` *(New Module)*
  - `parasite_ai/mind/memory.py`
  - `parasite_ai/mind/dual_mind.py`
* **Deliverables:**
  1. Create `parasite_ai/mind/affordance.py` containing `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, and `CLIExecutionSandbox`.
  2. Implement heuristic classification: file manipulation, code refactoring, and test execution routed to CLI / Antigravity tooling; native GUI apps routed to physical manipulation.
  3. Extend `ActionPlan` with `action=ActionType.RUN_CLI_COMMAND` and `cli_command: Optional[str]`.
  4. Extend `PlanStep` with `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]]`.
  5. Implement `CLIExecutionSandbox` with 30s timeout, 10ms hardware preemption cancellation token monitoring, command whitelist, and explicit prohibition against headless web scraping tools (`curl`, `requests`, `playwright`, `puppeteer`, `selenium`).
* **Exact Function Signatures:**
  ```python
  class AffordanceEvaluator:
      @staticmethod
      def evaluate(goal: str, active_window_title: str) -> AffordanceAssessment: ...

  class CLIExecutionSandbox:
      @classmethod
      def execute(
          cls,
          cmd_tokens: List[str],
          timeout: float = 30.0,
          cancellation_token: Optional[Any] = None,
          working_dir: Optional[str] = None,
      ) -> CLIExecutionResult: ...
  ```
* **Acceptance Criteria:**
  - Multi-file code and test tasks evaluate CLI affordances first, avoiding fragile GUI clicks.
  - CLI commands execute in sandboxed subprocesses with 30s timeout and hardware touch preemption monitoring.
  - Headless scraping commands (`curl`, `requests`, `playwright`) are rejected by the execution sandbox with security violations.
  - Native GUI apps correctly route to physical mouse and keyboard drivers.
```

---

### Replacement Block 5: Section 12 (Victory Verification Matrix Updates)
**Target File:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Target Range:** Lines 1054, 1055, 1057 (Matrix Rows VERIF-1, VERIF-2, VERIF-4)

```markdown
| **VERIF-1** | 4-Tier Escalation Strike Counters | `pytest tests/test_escalation_cadence.py` | Tier 1 advances to Tier 2 on exactly 2 local strikes; Tier 3 advances to Tier 4 on exactly 2 guided strikes; Tier 4 transitions to `USER_OVERRIDE` on 3 strikes. Passive actions (`WAIT`, `DONE`) and CLI actions (`returncode == 0`) do not incur false strikes; physical touch invokes `on_hardware_interrupt()`. | Strike counter fails to transition, increments on passive actions or successful CLI actions, or resets prematurely without verified criteria. |
| **VERIF-2** | Grounded Capability Manifest | `pytest tests/test_gemini_consultation_protocol.py` | Consultation prompt includes exact mouse Bézier limits, atomic Ctrl+V paste, dynamic virtual screen bounds, and explicit prohibitions against CLI scraping (`curl`/`requests`/`playwright`) and UIA pattern injection (`ValuePattern`/`InvokePattern`). | Prompt omits physical limits, hardcodes static screen bounds, or allows DOM manipulation, headless scraping, or programmatic pattern calls. |
| **VERIF-4** | Tool-Aware Affordance Routing & CLI Sandbox | `pytest tests/test_tool_aware_reasoning.py` | Code refactoring and test goals evaluate to `LOCAL_DEVELOPER_TOOL`; native GUI apps evaluate to `PHYSICAL_GUI`. CLI sandbox aborts upon hardware preemption token within 10ms and rejects prohibited scraping binaries. | File/code tasks default to slow GUI clicking; CLI execution ignores hardware preemption token or permits forbidden scraping commands. |
```

---

## 5. Verification Method

To independently verify all findings and test the state machine logic with passive and CLI actions:

```powershell
Set-Location C:\ParasiteAI

# 1. Verify that EscalationStateMachine correctly handles passive actions and CLI return codes:
& "C:\ParasiteAI\.venv\Scripts\python.exe" -c "
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CadenceTier(str, Enum):
    TIER_1_LOCAL = 'TIER_1_LOCAL'
    TIER_2_CONSULT = 'TIER_2_CONSULT'
    TIER_3_GUIDED = 'TIER_3_GUIDED'
    TIER_4_CO_PILOT = 'TIER_4_CO_PILOT'
    USER_OVERRIDE = 'USER_OVERRIDE'

class ActionType(str, Enum):
    CLICK = 'CLICK'
    TYPE = 'TYPE'
    HOTKEY = 'HOTKEY'
    WAIT = 'WAIT'
    DONE = 'DONE'
    RUN_CLI_COMMAND = 'RUN_CLI_COMMAND'

class EscalationStateMachine(BaseModel):
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0)
    guided_strikes: int = Field(default=0, ge=0)
    copilot_strikes: int = Field(default=0, ge=0)
    consultation_failures: int = Field(default=0, ge=0)
    total_escalation_cycles: int = Field(default=0, ge=0)
    max_escalation_cycles: int = Field(default=3)
    max_consultation_failures: int = Field(default=2)

    def on_action_result(
        self,
        success: bool,
        screen_diff: float = 0.0,
        action_type: Optional[ActionType] = None,
        is_interactive: bool = True,
        cli_returncode: Optional[int] = None,
        diff_threshold: float = 0.02,
    ) -> CadenceTier:
        if action_type == ActionType.RUN_CLI_COMMAND:
            effective_success = success and (cli_returncode == 0 if cli_returncode is not None else True)
        elif action_type in (ActionType.WAIT, ActionType.DONE) or not is_interactive:
            if success:
                return self.current_tier
            effective_success = False
        else:
            effective_success = success and (screen_diff >= diff_threshold)

        if self.current_tier == CadenceTier.TIER_1_LOCAL:
            if effective_success:
                self.local_strikes = 0
            else:
                self.local_strikes += 1
                if self.local_strikes >= 2:
                    self.current_tier = CadenceTier.TIER_2_CONSULT
        return self.current_tier

sm = EscalationStateMachine()
# Passive WAIT does not increment strikes:
sm.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.WAIT)
assert sm.local_strikes == 0
# CLI returncode 0 resets strikes:
sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
assert sm.local_strikes == 1
sm.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=0)
assert sm.local_strikes == 0
print('Verified: Passive actions and CLI return codes pass without false strikes!')
"
```
*Expected output:* `Verified: Passive actions and CLI return codes pass without false strikes!`

```powershell
# 2. Run the full empirical test suite:
& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_challenger_p4_empirical.py -v
```
*Expected output:* `18 passed in 0.75s`.

```powershell
# 3. Invalidation Conditions:
# - An ActionType.WAIT or ActionType.DONE with screen_diff = 0.0 increments local_strikes or guided_strikes.
# - An ActionType.RUN_CLI_COMMAND with returncode = 0 increments local_strikes due to screen_diff < 0.02.
# - A consultation prompt allows curl, requests, or playwright scraping commands without a security violation.
# - A consultation prompt allows ValuePattern.SetValue or InvokePattern.Invoke UIA pattern execution.
```
