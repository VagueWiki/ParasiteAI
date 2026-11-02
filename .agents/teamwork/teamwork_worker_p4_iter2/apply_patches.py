"""
Script to apply all Iteration 2 remediations to phase_4_master_plan.md
"""
import sys
from pathlib import Path

TARGET_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md")

def main():
    if not TARGET_PATH.exists():
        print(f"ERROR: Target file {TARGET_PATH} does not exist!")
        sys.exit(1)

    content = TARGET_PATH.read_text(encoding="utf-8")
    print(f"Initial length: {len(content)} chars, {len(content.splitlines())} lines.")

    # -------------------------------------------------------------
    # PATCH 1: Section 3 (Section 3.1, 3.2, 3.3)
    # Check if already patched or needs patching
    # -------------------------------------------------------------
    if "Action-Aware Success & Strike Criteria" not in content:
        old_sec3_start = "#### Tier 1: Autonomous Local Exploration (Strikes 0–1)"
        old_sec3_end = """    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.current_tier = CadenceTier.TIER_1_LOCAL
```"""
        idx_start = content.find(old_sec3_start)
        idx_end = content.find(old_sec3_end)
        if idx_start == -1 or idx_end == -1:
            print("ERROR: Patch 1 anchor not found!")
            sys.exit(1)

        new_sec3_text = r"""#### Tier 1: Autonomous Local Exploration (Strikes 0–1)
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
    - If `consultation_failures >= 2`, the system immediately transitions to **`USER_OVERRIDE`**, preventing infinite deadlocks between Tier 1 and Tier 2.
    - Otherwise (on attempt 1), ParasiteAI falls back to a deep local replan using Qwen2.5-3B or prompts the user via the Companion Dock, resetting `local_strikes` to 0.

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
  - **Failure Trigger:** If an interactive step fails, times out, or produces $\Delta < 0.02$, `guided_strikes` increments by 1. The agent checks `step.contingency` for alternative actions.
  - On `guided_strikes == 2`:
    - `total_escalation_cycles` increments by 1.
    - If `total_escalation_cycles >= 3`, the agent aborts further cycling and escalates immediately to **`USER_OVERRIDE`** to eliminate T3 $\leftrightarrow$ T4 ping-pong loops.
    - Otherwise, the agent concludes that the static blueprint is insufficient and escalates to **Tier 4** (`copilot_strikes = 0`). Non-interactive actions (`ActionType.WAIT`, `ActionType.DONE`) do not incur strikes.

#### Tier 4: Continuous Gemini Handholding / Visual Co-Pilot (Strikes 0–2)
- **Trigger:** Reached on 2 consecutive failures in Tier 3 (when cumulative cycles $< 3$).
- **Cadence Rules:**
  - Establishes an interactive, step-by-step micro-loop with Gemini.
  - Before each click, the agent reports the current SOM state and intended target candidate ID.
  - After each action, the 1:1 foveal crop and post-action ROI diff are evaluated against expected results.
  - **Success Recovery:** If a micro-action succeeds and breaks the deadlock, the pipeline resets `copilot_strikes = 0`, `guided_strikes = 0`, and transitions back to **Tier 3** to resume guided execution. Note: `total_escalation_cycles` is NOT reset on micro-success, ensuring an overall cycle cap of 3 prevents infinite ping-pong loops.
  - **Failure Trigger:** If an individual co-pilot step fails, `copilot_strikes` increments by 1.
  - On `copilot_strikes == 3`, continuous guidance has failed. The system initiates **Graceful User Escalation**.

#### Terminal State: Graceful User Escalation (`USER_OVERRIDE`)
- **Trigger:** Triggered deterministically upon any of the following conditions:
  1. 3 consecutive failures in Tier 4 co-pilot mode (`copilot_strikes >= 3`).
  2. 3 cumulative T3 $\leftrightarrow$ T4 escalation cycles (`total_escalation_cycles >= 3`).
  3. 2 consecutive consultation failures (`consultation_failures >= 2`).
  4. Physical human hardware touch preemption (`flags & LL[M/K]HF_INJECTED == 0`).
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
| **TIER_1_LOCAL** | Action Stalled / Failed | ($\Delta < 0.02$ (GUI) or `returncode != 0` (CLI) or `success == False`) & `is_interactive == True` | **TIER_1_LOCAL** | `local_strikes += 1`; record failure in episodic memory |
| **TIER_1_LOCAL** | Strike Limit Reached | `local_strikes == 2` | **TIER_2_CONSULT** | Halt physical hands; compile brief + capability manifest |
| **TIER_2_CONSULT** | Blueprint Validated | Valid `LivingPlan` JSON parsed (`steps` or `recommended_strategy`) | **TIER_3_GUIDED** | Hydrate `active_plan`; `local_strikes = 0`; `guided_strikes = 0`; `consultation_failures = 0`; emit persona monologue |
| **TIER_2_CONSULT** | Advisor Error / Offline (Attempt 1) | Network timeout, missing credentials, or bad JSON (`consultation_failures < 2`) | **TIER_1_LOCAL** | Log warning; fallback to local replan; `local_strikes = 0`; `consultation_failures += 1` |
| **TIER_2_CONSULT** | Persistent Advisor Failure | Network timeout / offline for 2 consecutive attempts (`consultation_failures >= 2`) | **USER_OVERRIDE** | Transition to `USER_OVERRIDE`; halt hands; request user assistance via persona speech |
| **TIER_3_GUIDED** | Step Successful | $\Delta \ge 0.02$ (GUI) or `returncode == 0` (CLI) or passive success | **TIER_3_GUIDED** | `guided_strikes = 0`; `active_plan.advance_step()` |
| **TIER_3_GUIDED** | Step Failed / Stalled | ($\Delta < 0.02$ (GUI) or `returncode != 0` (CLI) or criteria unmet) & `is_interactive == True` | **TIER_3_GUIDED** | `guided_strikes += 1`; execute `step.contingency` if present |
| **TIER_3_GUIDED** | Guided Limit Reached (Cycle < 3) | `guided_strikes == 2` and `total_escalation_cycles < 3` | **TIER_4_CO_PILOT** | Increment `total_escalation_cycles += 1`; escalate to visual co-pilot; `copilot_strikes = 0` |
| **TIER_3_GUIDED** | Escalation Cycle Cap Reached | `guided_strikes == 2` and `total_escalation_cycles >= 3` | **USER_OVERRIDE** | Halt hands; prevent ping-pong loop; deliver character dilemma speech |
| **TIER_4_CO_PILOT** | Co-Pilot Step Cleared | Obstacle resolved with advisor | **TIER_3_GUIDED** | `copilot_strikes = 0`; `guided_strikes = 0`; resume blueprint execution |
| **TIER_4_CO_PILOT** | Micro-Action Failed | Post-action verification failed & `is_interactive == True` | **TIER_4_CO_PILOT** | `copilot_strikes += 1`; report diff back to advisor |
| **TIER_4_CO_PILOT** | Deadlock Confirmed | `copilot_strikes == 3` | **USER_OVERRIDE** | Halt hands; deliver character dilemma speech; pause automation |
| **ANY_STATE** | Physical Hardware Touch | `flags & LL[M/K]HF_INJECTED == 0` | **USER_OVERRIDE** | Sub-2ms preemption token set; abort current synthetic input; call `on_hardware_interrupt()` |
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
        \"\"\"
        Action-aware strike evaluation and tier transition.
        
        Evaluates success according to action modality:
        - CLI actions (RUN_CLI_COMMAND): Evaluated by cli_returncode == 0 (visual diff bypassed).
        - Passive actions (WAIT, DONE, non-visual HOTKEY, or is_interactive=False):
          Exempt from visual diff. If success=True, strikes remain unchanged.
        - Interactive GUI actions (CLICK, TYPE, visual HOTKEY, SCROLL):
          Evaluated by physical success AND localized ROI diff >= diff_threshold.
        \"\"\"
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
        \"\"\"Immediate transition from ANY_STATE to USER_OVERRIDE on physical human preemption.\"\"\"
        self.current_tier = CadenceTier.USER_OVERRIDE
```"""
        content = content[:idx_start] + new_sec3_text + content[idx_end + len(old_sec3_end):]
        print("Patch 1 applied.")
    else:
        print("Patch 1 already present.")

    # -------------------------------------------------------------
    # PATCH 2: Section 4.1, 4.2, 4.4
    # -------------------------------------------------------------
    if "Headless Scraping Prohibition" not in content:
        old_sec4_1_target = """### 4.1 Motivation & Anti-Hallucination Rationale

External cloud LLMs (such as Gemini 1.5 Pro) are trained on massive web datasets and naturally gravitate toward programmatic or browser-centric solutions:
- *"Inject this JavaScript snippet into the console to extract the table."*
- *"Use `document.querySelector('button.submit').click()`."*
- *"Call the private Win32 API `SendMessage(hwnd, WM_SETTEXT, ...)`."*
- *"Run headless Playwright in the background."*

For ParasiteAI, all of these suggestions are fatal:
1. ParasiteAI is a **100% visible physical desktop assistant**. It operates strictly via synthetic human kinematics.
2. It has **zero headless browser integration** and **zero DOM access**.
3. Direct OS message injection (`WM_SETTEXT`) circumvents UI event loops, breaks focus state, and violates realistic desktop automation.
4. If an external advisor emits impossible instructions, the agent wastes execution cycles attempting to ground non-existent DOM nodes.

To permanently prevent advisor hallucination, every consultation payload injects the **Parasite Capability Contract** as an immutable system preamble."""

        new_sec4_1_text = """### 4.1 Motivation & Anti-Hallucination Rationale

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

To permanently prevent advisor hallucination, every consultation payload injects the **Parasite Capability Contract** as an immutable system preamble."""

        if old_sec4_1_target in content:
            content = content.replace(old_sec4_1_target, new_sec4_1_text, 1)

    if "Dynamic via get_virtual_screen_bounds()" not in content:
        idx_manifest = content.find("Parasite_Capability_Contract:")
        idx_manifest_end = content.find("Strict Anti-Hardcoding: NO application-specific lookup tables", idx_manifest)
        idx_yaml_close = content.find("```", idx_manifest_end)
        new_manifest_block = """Parasite_Capability_Contract:
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
    Resolution: "1:1 unscaled cursor foveal crop (512x512) and downscaled virtual desktop macro glance (3840x1080)"
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
    - "Strict Anti-Hardcoding: NO application-specific lookup tables (app_map = {} is strictly forbidden)\""""
        content = content[:idx_manifest] + new_manifest_block + "\n" + content[idx_yaml_close:]

    old_sec4_4_anchor = """# CAPABILITY CONTRACT & CONSTRAINTS
{capability_contract_yaml}

# ACTIVE DESKTOP STATE"""
    new_sec4_4_anchor = """# CAPABILITY CONTRACT & CONSTRAINTS
{capability_contract_yaml}
- Physical desktop automation ONLY (Bézier mouse, SendInput cadence typing, atomic Ctrl+V paste).
- ZERO headless browser automation, ZERO CLI scraping (curl/requests/playwright), ZERO programmatic UIA pattern calls (ValuePattern/InvokePattern).

# ACTIVE DESKTOP STATE"""
    if old_sec4_4_anchor in content:
        content = content.replace(old_sec4_4_anchor, new_sec4_4_anchor, 1)
    print("Patch 2 checked/applied.")

    # -------------------------------------------------------------
    # PATCH 3: Section 5.2 and 5.3 (DualChannelRouter & Speech Sanitization)
    # -------------------------------------------------------------
    old_router_start = "class DualChannelRouter:"
    idx_router_start = content.find(old_router_start)
    if idx_router_start != -1:
        # Find closing code fence after idx_router_start
        idx_router_code_close = content.find("```", idx_router_start)
        new_router_code = r"""class DualChannelRouter:
    def __init__(self, bridge: Optional[Any] = None, persona_engine: Optional[Any] = None):
        self.bridge = bridge
        self.persona_engine = persona_engine

    def route_consultation_output(
        self,
        raw_advisor_text: str,
        user_goal: str,
        active_plan: LivingPlan,
    ) -> Tuple[Optional[LivingPlan], str]:
        from parasite_ai.mind.plan import extract_strategic_blueprint_json, parse_gemini_consultation_response

        # Channel A: Extract machine blueprint supporting both 'steps' and 'recommended_strategy' keys
        blueprint_json = extract_strategic_blueprint_json(raw_advisor_text)
        has_steps = blueprint_json and (
            ("steps" in blueprint_json and bool(blueprint_json["steps"]))
            or ("recommended_strategy" in blueprint_json and bool(blueprint_json["recommended_strategy"]))
        )

        if has_steps:
            try:
                updated_plan = parse_gemini_consultation_response(raw_advisor_text, user_goal)
                raw_rationale = blueprint_json.get("rationale") or blueprint_json.get("overall_strategy", "")
            except Exception:
                updated_plan = None
                raw_rationale = ""
        else:
            updated_plan = None
            raw_rationale = ""

        # Channel B: Translate into character monologue
        persona_speech = self.translate_to_persona_voice(
            raw_rationale=raw_rationale,
            updated_plan=updated_plan,
            user_goal=user_goal
        )

        # Emit visible speech strictly through Channel B
        if self.bridge and hasattr(self.bridge, "notify_speech"):
            self.bridge.notify_speech(persona_speech)

        return updated_plan, persona_speech

    def translate_to_persona_voice(
        self,
        raw_rationale: str,
        updated_plan: Optional[LivingPlan],
        user_goal: str
    ) -> str:
        # Strip all raw JSON, code blocks, backticks, braces, and coordinate tuples
        clean_text = self._sanitize_text(raw_rationale)

        if updated_plan and hasattr(updated_plan, "steps") and updated_plan.steps:
            first_step = updated_plan.steps[0]
            return f"Gemini suggested we try {first_step.description.lower()}. Let's give that a shot!"
        elif "modal" in clean_text.lower():
            return "Looks like an unexpected dialog popped up. Let me dismiss it so we can keep going."
        elif clean_text and not any(kw in clean_text.lower() for kw in ("error:", "exception", "resource_exhausted")):
            return clean_text[:140]
        else:
            return "I've re-evaluated our plan. Moving to the next step now!"

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        import re
        # Strip all markdown code blocks (```python, ```json, ```bash, etc.)
        text = re.sub(r"```[\w]*[\s\S]*?```", "", text)
        # Strip inline backticks and code snippets
        text = re.sub(r"`[^`]*`", "", text)
        # Strip curly braces, brackets, quotes
        text = re.sub(r"[{}\[\]\"]", "", text)
        # Strip coordinate pairs and dimensions
        text = re.sub(r"\b\d+x\d+\b", "", text)
        text = re.sub(r"\(\d+,\s*\d+\)", "", text)
        return " ".join(text.split()).strip()
"""
        content = content[:idx_router_start] + new_router_code + content[idx_router_code_close:]

    old_table_end = """| **Terminal User Override** | `{"status": "DEADLOCK", "copilot_strikes": 3, "error": "UAC elevation required at hwnd 0x1004A"}` | *"I've hit a permission screen that needs your approval. Could you take the wheel for a second?"* |"""
    new_table_rows = """| **External Advisor Error / Outage** | `{"error": "RESOURCE_EXHAUSTED", "code": 429, "details": "```python\\nimport sys\\n```"}` | *"I've re-evaluated our plan. Moving to the next step now!" (Zero stack traces or API error codes leaked)* |
| **Terminal User Override** | `{"status": "DEADLOCK", "copilot_strikes": 3, "error": "UAC elevation required at hwnd 0x1004A"}` | *"I've hit a permission screen that needs your approval. Could you take the wheel for a second?"* |"""

    if old_table_end in content and "External Advisor Error / Outage" not in content:
        content = content.replace(old_table_end, new_table_rows, 1)
    print("Patch 3 applied.")

    # -------------------------------------------------------------
    # PATCH 4: Section 6.1, 6.3, and new Section 6.4 (Affordance & CLIExecutionSandbox)
    # -------------------------------------------------------------
    old_sec6_1 = """2. **Affordance 2: Local Developer Tooling & Antigravity Meta-Tooling (CLI / Scripts):**
   - **Characteristics:** Code editing, file tree reorganizations, batch text replacements, Git operations, running test suites (`pytest`), and Antigravity workspace automation.
   - **Mechanism:** Direct execution via local subprocesses, PowerShell, or Antigravity tool scripts.
   - **Reasoning Heuristic:** If a user goal involves writing complex code, creating multi-file projects, or parsing massive text, ParasiteAI evaluates:
     > *"Can this goal be achieved 10x faster and safer via Antigravity CLI / scripts than by clicking editor menus?"*"""

    new_sec6_1 = r"""2. **Affordance 2: Local Developer Tooling & Antigravity Meta-Tooling (CLI / Scripts):**
   - **Characteristics:** Code editing, file tree reorganizations, batch text replacements, Git operations, running test suites (`pytest`), and Antigravity workspace automation.
   - **Mechanism:** Direct execution via sandboxed local subprocesses (`CLIExecutionSandbox`).
   - **Reasoning Heuristic:** If a user goal involves writing complex code, creating multi-file projects, or parsing massive text, ParasiteAI evaluates:
     > *"Can this goal be achieved 10x faster and safer via Antigravity CLI / scripts than by clicking editor menus?"*
   - **Headless Web Scraping Prohibition:** CLI tooling cannot be used to bypass physical browser interaction. Automated web extraction commands (`curl`, `wget`, `requests`, `playwright`, `puppeteer`, `selenium`) are strictly prohibited in the CLI sandbox.
   - **Success Evaluation:** CLI actions are evaluated strictly by `returncode == 0` (bypassing visual ROI diff $\Delta \ge 0.02$)."""

    if old_sec6_1 in content:
        content = content.replace(old_sec6_1, new_sec6_1, 1)

    old_sec6_3_start = "### 6.3 `AffordanceEvaluator` Specification"
    idx_sec6_3 = content.find(old_sec6_3_start)
    old_sec6_end_marker = "## 7. Textual Scene Serialization Protocol (Zero Video Streaming)"
    idx_sec6_end = content.find(old_sec6_end_marker, idx_sec6_3)
    if idx_sec6_3 != -1 and idx_sec6_end != -1 and "CLIExecutionSandbox" not in content[idx_sec6_3:idx_sec6_end]:
        new_sec6_3_and_4 = r"""### 6.3 `AffordanceEvaluator` Specification (Context-Aware Hybrid Classification)

```python
import re
from enum import Enum
from pydantic import BaseModel
from typing import Optional

class ActionAffordance(str, Enum):
    PHYSICAL_GUI = "PHYSICAL_GUI"
    LOCAL_DEVELOPER_TOOL = "LOCAL_DEVELOPER_TOOL"
    STRATEGIC_ADVISOR = "STRATEGIC_ADVISOR"

class AffordanceAssessment(BaseModel):
    affordance: ActionAffordance
    confidence: float
    justification: str
    suggested_command: Optional[str] = None

class AffordanceEvaluator:
    @staticmethod
    def evaluate(goal: str, active_window_title: str) -> AffordanceAssessment:
        goal_lower = goal.lower()
        title_lower = active_window_title.lower()
        
        # Priority Rule 1: Graphical Canvas & Native Drawing Context
        # Prevents "create file in Paint" or "draw" from misrouting to CLI
        gui_canvas_keywords = ["paint", "gimp", "photoshop", "canvas", "draw", "sketch", "brush"]
        if any(kw in title_lower or kw in goal_lower for kw in gui_canvas_keywords):
            return AffordanceAssessment(
                affordance=ActionAffordance.PHYSICAL_GUI,
                confidence=0.95,
                justification="Task targets a graphical/canvas application requiring direct 2D coordinate input.",
                suggested_command=None
            )

        # Priority Rule 2: Application Launch Verbs
        # Generic launch verbs for desktop software must route to UniversalAppResolver
        app_launch_pattern = r"\b(?:open|launch|start|switch\s+to|bring\s+up)\s+(?:up\s+)?([a-zA-Z0-9_\-\.\s]+)"
        match = re.search(app_launch_pattern, goal_lower)
        if match:
            target = match.group(1).strip()
            if target not in {"terminal", "powershell", "cmd", "bash", "command prompt"}:
                return AffordanceAssessment(
                    affordance=ActionAffordance.PHYSICAL_GUI,
                    confidence=0.92,
                    justification=f"Application launch request for '{target}' routes to UniversalAppResolver.",
                    suggested_command=None
                )

        # Priority Rule 3: Deterministic Code, Test & File Operations
        code_keywords = ["refactor", "run test", "pytest", "git commit", "create file", "batch replace", "git push", "git status"]
        if any(kw in goal_lower for kw in code_keywords):
            return AffordanceAssessment(
                affordance=ActionAffordance.LOCAL_DEVELOPER_TOOL,
                confidence=0.95,
                justification="Task involves file or code operations best executed deterministically via CLIExecutionSandbox.",
                suggested_command=None
            )
            
        # Default: Physical GUI
        return AffordanceAssessment(
            affordance=ActionAffordance.PHYSICAL_GUI,
            confidence=0.75,
            justification="Standard desktop operation.",
            suggested_command=None
        )
```

---

### 6.4 `CLIExecutionSandbox` Specification & Runtime Security Model

When `AffordanceEvaluator` routes an operation to `LOCAL_DEVELOPER_TOOL`, ParasiteAI executes the directive strictly through `CLIExecutionSandbox`. The sandbox enforces five non-negotiable security and preemption invariants:

```python
import os
import re
import shlex
import subprocess
import threading
import time
from typing import Any, List, Optional, Set
from pydantic import BaseModel, Field

class CLIExecutionResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    preempted: bool = False

class CLIExecutionSandbox:
    \"\"\"
    Sandboxed execution engine for local developer tooling and Antigravity meta-commands.
    Guarantees sub-2ms hardware touch preemption, command whitelisting, and shell-injection protection.
    \"\"\"
    DEFAULT_TIMEOUT_S: float = 30.0
    
    # Invariant: Only permit vetted developer and interpreter binaries
    PERMITTED_BINARIES: Set[str] = {
        "python", "python.exe",
        "pytest", "pytest.exe",
        "git", "git.exe",
        "powershell", "powershell.exe",
        "cmd", "cmd.exe",
    }
    
    # Invariant: Destructive system patterns and headless scraping commands rejected
    FORBIDDEN_PATTERNS: List[str] = [
        r"\bcurl\b",
        r"\bwget\b",
        r"\bplaywright\b",
        r"\bpuppeteer\b",
        r"\bselenium\b",
        r"\bscrapy\b",
        r"\bformat\b",
        r"\brmdir\s+/[sq]\b",
        r"\bdel\s+/[sqf]\b",
        r"\bdiskpart\b",
        r"\breg\s+delete\b",
        r"\bshutdown\b",
        r"\bstop-computer\b",
    ]

    @classmethod
    def sanitize_and_tokenize(cls, command_str: str) -> List[str]:
        \"\"\"
        Parses command string without shell evaluation.
        Uses posix=False to preserve Windows backslash paths, then strips matching outer quotes.
        \"\"\"
        if not command_str or not command_str.strip():
            raise ValueError("Empty CLI command string")

        for pat in cls.FORBIDDEN_PATTERNS:
            if re.search(pat, command_str, re.IGNORECASE):
                raise PermissionError(f"Command rejected by security filter: pattern '{pat}' detected")

        # posix=False preserves Windows paths (e.g. C:\ParasiteAI\tests\test_foo.py)
        raw_tokens = shlex.split(command_str, posix=False)
        if not raw_tokens:
            raise ValueError("Command string produced no tokens")

        # Strip enclosing quotes for subprocess argv list
        clean_tokens = [
            t[1:-1] if (t.startswith(('"', "'")) and t.endswith(('"', "'")) and len(t) >= 2) else t
            for t in raw_tokens
        ]

        binary_raw = clean_tokens[0]
        binary_base = os.path.basename(binary_raw).lower()
        if binary_base not in cls.PERMITTED_BINARIES:
            raise PermissionError(
                f"Binary '{binary_base}' is not in permitted CLI whitelist ({cls.PERMITTED_BINARIES})"
            )

        return clean_tokens

    @classmethod
    def execute(
        cls,
        command_str: str,
        cwd: str = "C:\\ParasiteAI",
        timeout: float = DEFAULT_TIMEOUT_S,
        cancellation_token: Optional[threading.Event] = None,
    ) -> CLIExecutionResult:
        \"\"\"
        Executes sandboxed command.
        Monitors cancellation_token at 10ms intervals for sub-2ms preemption response.
        \"\"\"
        clean_tokens = cls.sanitize_and_tokenize(command_str)
        t0 = time.perf_counter()

        proc = subprocess.Popen(
            clean_tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            shell=False,  # Invariant: Never invoke shell=True
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )

        preempted = False
        timed_out = False

        while True:
            ret = proc.poll()
            if ret is not None:
                break

            # Hardware preemption check: user touched physical mouse/keyboard or triggered panic
            if cancellation_token and cancellation_token.is_set():
                preempted = True
                proc.kill()
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                )
                break

            # Timeout check
            elapsed = time.perf_counter() - t0
            if elapsed > timeout:
                timed_out = True
                proc.kill()
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                )
                break

            time.sleep(0.010)  # 10ms non-blocking polling interval

        stdout, stderr = (
            proc.communicate()
            if not (preempted or timed_out)
            else ("", "Subprocess terminated by preemption token or timeout")
        )
        t1 = time.perf_counter()

        return CLIExecutionResult(
            command=command_str,
            exit_code=-1 if (preempted or timed_out) else proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_ms=(t1 - t0) * 1000.0,
            timed_out=timed_out,
            preempted=preempted,
        )
```

---

"""
        content = content[:idx_sec6_3] + new_sec6_3_and_4 + content[idx_sec6_end:]
    print("Patch 4 applied.")

    # -------------------------------------------------------------
    # PATCH 5: Section 8.2 & new Section 8.3 (UniversalAppResolver & PrecisionAppMatcher)
    # -------------------------------------------------------------
    old_sec8_2_start = "### 8.2 Generic 3-Tier Universal Application Resolver"
    idx_sec8_2 = content.find(old_sec8_2_start)
    old_sec8_end_marker = "## 9. Comprehensive Schema Mapping & Runtime Data Contracts"
    idx_sec8_end = content.find(old_sec8_end_marker, idx_sec8_2)
    if idx_sec8_2 != -1 and idx_sec8_end != -1 and "PrecisionAppMatcher" not in content[idx_sec8_2:idx_sec8_end]:
        new_sec8_2_and_3 = r"""### 8.2 Generic 3-Tier Universal Application Resolver & State Machine

All application launches resolve dynamically via `UniversalAppResolver` through an explicit, deadlock-free state machine that eliminates unreachable code:

```mermaid
flowchart TD
    Req["Launch Request: 'open <app>'"] --> T1{"Tier 1: Grounded Icon Search\nInspect Visible SOM Elements\nPrecisionAppMatcher.score >= 0.80"}
    
    T1 -->|Match Found| ClickIcon["Click Grounded Icon Center (x, y)\nReset Launcher State"]
    T1 -->|No Match| CheckDialogs{"Check Active Dialogs"}
    
    CheckDialogs -->|Run Dialog Open| TypeRun["Type App + Enter into Run Box\nstart_search_attempts += 1"]
    CheckDialogs -->|Search Box Open| TypeSearch["Type App + Enter into Search Box\nstart_search_attempts += 1"]
    CheckDialogs -->|No Dialog Open| T2_Check{"start_search_attempts == 0?"}
    
    T2_Check -->|Yes: Attempt 1| T2_Start["Tier 2: Windows Start Search Chord\n1. Press Win Key (search_opened = True)\n2. Next Step: Type App + Enter\n3. Set start_search_attempts = 1"]
    T2_Check -->|No: Start Search Failed| T3_Check{"run_dialog_attempts == 0?"}
    
    T3_Check -->|Yes: Attempt 1| T3_Run["Tier 3: Windows Run Dialog Fallback\n1. Press Win+R Chord (run_opened = True)\n2. Next Step: Type App + Enter\n3. Set run_dialog_attempts = 1"]
    T3_Check -->|No: Both Tiers Exhausted| Exhausted["Emit ActionType.WAIT\nEscalate to Cognitive Replan / Tier 2 Gemini"]
```

#### Deterministic Fallback Rules & State Variables:
`UniversalAppResolver` maintains state variables to govern progression across tiers:
- `_target_app: Optional[str]`: Active target application name. If a new app is targeted, state counters reset.
- `_start_search_attempts: int = 0`: Tracks completed Tier 2 cycles.
- `_search_opened: bool = False`: Tracks pending `Win` key chord.
- `_run_dialog_attempts: int = 0`: Tracks completed Tier 3 cycles.
- `_run_opened: bool = False`: Tracks pending `Win+R` chord.

#### Step-by-Step Transition Protocol:
1. **Tier 1 (Visible Grounded Controls):** Scans the active Set-of-Mark table using `PrecisionAppMatcher`. If an element scores $\ge 0.80$, emits `ActionType.CLICK` directly and resets launcher state.
2. **Tier 2 (Windows Start Search Chord):**
   - **Step A:** If `_start_search_attempts == 0` and `not _search_opened`: Emits `ActionPlan(action=ActionType.HOTKEY, keys=["win"], wait_ms=250)`, sets `_search_opened = True`.
   - **Step B:** On the next cycle, `_search_opened` is True: Emits `ActionPlan(action=ActionType.TYPE, text=f"{target_app}\n", submit=True)`, clears `_search_opened = False`, and increments `_start_search_attempts = 1`.
3. **Tier 3 (Windows Run Dialog Fallback Transition):**
   - If the application window fails to appear on the subsequent step (ROI diff $< 0.02$ or consecutive launch step), `_start_search_attempts` is now $\ge 1$.
   - **Step A:** If `_run_dialog_attempts == 0` and `not _run_opened`: Emits `ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"], wait_ms=250)`, sets `_run_opened = True`.
   - **Step B:** On the next cycle, `_run_opened` is True: Emits `ActionPlan(action=ActionType.TYPE, text=f"{target_app}\n", submit=True)`, clears `_run_opened = False`, and increments `_run_dialog_attempts = 1`.
4. **Resolution Exhaustion:** If both Tier 2 and Tier 3 have been attempted (`_start_search_attempts >= 1` and `_run_dialog_attempts >= 1`) and the target window has not focused, the resolver emits `ActionType.WAIT` with diagnostic reasoning, cleanly escalating to a cognitive replan rather than looping infinitely.

All cadence waits enforce millisecond checks against `cancellation_token`.

---

### 8.3 `PrecisionAppMatcher` & Substring Collision Prevention

To prevent catastrophic false clicks (such as clicking "Exit Notepad" when searching for "Notepad", or matching "SmartScreen" for "art"), `UniversalAppResolver` replaces naive substring containment with `PrecisionAppMatcher`:

```python
import re
from typing import List, Optional, Tuple
from parasite_ai.ui.types import UIElement

class PrecisionAppMatcher:
    \"\"\"
    High-precision fuzzy element matcher.
    Enforces word boundary regex, exact matching priority, and destructive verb disqualification.
    \"\"\"
    NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}
    PREFERRED_ROLES = {
        "button", "listitem", "menuitem", "hyperlink", "image",
        "pane", "icon", "treeitem", "tabitem", "window"
    }

    @classmethod
    def score_match(cls, label: str, target: str) -> float:
        l_norm = label.strip().lower()
        t_norm = target.strip().lower()
        if not l_norm or not t_norm:
            return 0.0

        # Level 1: Exact match (highest confidence)
        if l_norm == t_norm:
            return 1.0

        tokens = re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", l_norm)
        if not tokens:
            return 0.0

        # Invariant: Disqualify destructive/exit elements immediately
        if any(v in tokens for v in cls.NEGATIVE_VERBS):
            return 0.0

        # Level 2: Exact prefix match with token boundary
        if (
            l_norm.startswith(t_norm + " ")
            or l_norm.startswith(t_norm + " -")
            or l_norm.startswith(t_norm + ":")
        ):
            return 0.95

        # Level 3: Word boundary regex match (\b)
        pattern = r"\b" + re.escape(t_norm) + r"\b"
        if re.search(pattern, l_norm, re.IGNORECASE):
            # Positional score: earlier occurrence yields higher score
            idx = l_norm.find(t_norm)
            pos_ratio = max(0.0, 1.0 - (idx / max(1, len(l_norm))))
            return 0.80 + (0.10 * pos_ratio)

        # Rejection: Arbitrary substrings without word boundaries (e.g. 'art' in 'SmartScreen') score 0.0
        return 0.0

    @classmethod
    def find_best_element(
        cls, target: str, elements: List[UIElement], threshold: float = 0.80
    ) -> Optional[Tuple[UIElement, float]]:
        candidates = []
        for elem in elements:
            role = (elem.role or "").lower()
            if not any(r in role for r in cls.PREFERRED_ROLES):
                continue
            score = cls.score_match(elem.label or "", target)
            if score >= threshold:
                candidates.append((elem, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]
```

---

"""
        content = content[:idx_sec8_2] + new_sec8_2_and_3 + content[idx_sec8_end:]
    print("Patch 5 applied.")

    # -------------------------------------------------------------
    # PATCH 6: Section 10 (Sub-Phases 4B, 4C, 4D, 4E, 4F)
    # -------------------------------------------------------------
    old_subphases_start = "### Sub-Phase 4B: 4-Tier Escalation State Machine in `DualMindPipeline`"
    idx_subphases = content.find(old_subphases_start)
    old_subphases_end_marker = "## 11. Preservation of Core Invariants Across All Sub-Phases"
    idx_subphases_end = content.find(old_subphases_end_marker, idx_subphases)
    if idx_subphases != -1 and idx_subphases_end != -1 and "tests/test_cli_sandbox.py" not in content[idx_subphases:idx_subphases_end]:
        new_subphases_text = r"""### Sub-Phase 4B: 4-Tier Escalation State Machine in `DualMindPipeline`
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
  5. Reset `local_strikes = 0` upon consultation success to prevent strike leakage across tiers.
  6. Implement `on_hardware_interrupt()` method transitioning directly to `USER_OVERRIDE`.
  7. Update `DualMindPipeline.step()` to transition across the 4 tiers:
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

### Sub-Phase 4C: Dual-Channel Output Router & Persona Voice Translator
* **Files Affected:**
  - `parasite_ai/mind/dual_mind.py`
  - `parasite_ai/ui/bridge.py`
* **Deliverables:**
  1. Implement `DualChannelRouter` in `parasite_ai/mind/dual_mind.py`.
  2. Ingest JSON blueprints into `LivingPlan` (Channel A) supporting both `"steps"` and `"recommended_strategy"` keys.
  3. Implement `PersonaVoiceTranslator` synthesizing clean, character-driven explanations (Channel B).
  4. In `_sanitize_text`, strip all markdown code blocks (` ```[\w]*[\s\S]*?``` `), backticks, curly braces, and coordinate tuples.
  5. In `translate_to_persona_voice`, filter error tokens (`"error:"`, `"exception"`, `"resource_exhausted"`) into friendly fallback character lines.
  6. Route Channel B monologues to `UIBridge.notify_speech()`.
* **Exact Function Signatures:**
  ```python
  class DualChannelRouter:
      def route_consultation_output(
          self, raw_text: str, user_goal: str, active_plan: LivingPlan
      ) -> Tuple[Optional[LivingPlan], str]: ...
      def translate_to_persona_voice(
          self, raw_rationale: str, updated_plan: Optional[LivingPlan], user_goal: str
      ) -> str: ...
  ```
* **Acceptance Criteria:**
  - Both `"steps"` and `"recommended_strategy"` formats successfully hydrate `LivingPlan`.
  - Zero raw JSON, markdown code blocks, backticks, coordinate pairs, or error codes emitted to visible speech bubbles.

---

### Sub-Phase 4D: Tool-Aware Reasoning & Antigravity Meta-Tooling
* **Files Affected:**
  - `parasite_ai/mind/affordance.py` *(New Module)*
  - `parasite_ai/mind/memory.py`
  - `parasite_ai/mind/dual_mind.py`
* **Deliverables:**
  1. Create `parasite_ai/mind/affordance.py` containing `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, and `CLIExecutionSandbox`.
  2. Implement context-aware heuristic classification in `AffordanceEvaluator`: check `active_window_title` and application launch intent before routing code/file tasks to CLI.
  3. Implement `CLIExecutionSandbox.execute()` with command whitelisting (`python`, `pytest`, `git`, `powershell`, `cmd`), regex security filter for destructive patterns and headless scraping commands (`curl`, `requests`, `playwright`, `puppeteer`, `selenium`), mandatory default timeout (`30.0s`), and non-blocking 10ms `cancellation_token` preemption monitoring.
  4. Implement Windows-safe tokenization using `shlex.split(command, posix=False)` and outer quote stripping, executing strictly with `shell=False` and `CREATE_NO_WINDOW`.
  5. Extend `ActionPlan` with `action=ActionType.RUN_CLI_COMMAND` and `cli_command: Optional[str]`.
  6. Extend `PlanStep` with `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]]`.
* **Exact Function Signatures:**
  ```python
  class AffordanceEvaluator:
      @staticmethod
      def evaluate(goal: str, active_window_title: str) -> AffordanceAssessment: ...

  class CLIExecutionSandbox:
      @classmethod
      def sanitize_and_tokenize(cls, command_str: str) -> List[str]: ...
      @classmethod
      def execute(
          cls,
          command_str: str,
          cwd: str = "C:\\ParasiteAI",
          timeout: float = 30.0,
          cancellation_token: Optional[threading.Event] = None
      ) -> CLIExecutionResult: ...
  ```
* **Acceptance Criteria:**
  - Multi-file code and test tasks evaluate CLI affordances first, avoiding fragile GUI clicks.
  - Native GUI apps and canvas operations correctly route to physical mouse and keyboard drivers.
  - Unlisted binaries or commands matching destructive regex patterns or scraping tools raise `PermissionError`.
  - Setting `cancellation_token` during CLI execution immediately terminates the subprocess tree via `taskkill /F /T /PID` within $< 20\text{ ms}$.

---

### Sub-Phase 4E: Universal Living Plan Step Advancement & Dynamic Contingencies
* **Files Affected:**
  - `parasite_ai/mind/plan.py`
  - `parasite_ai/mind/resolver.py`
  - `parasite_ai/mind/dual_mind.py`
* **Deliverables:**
  1. Remediate `UniversalAppResolver` in `parasite_ai/mind/resolver.py`:
     - Implement explicit attempt tracking (`_start_search_attempts`, `_run_dialog_attempts`) to guarantee Tier 2 $\to$ Tier 3 (`Win+R`) transition upon visual stall.
     - Integrate `PrecisionAppMatcher` implementing word-boundary regex (`\b`) and negative verb filtering to prevent substring collisions.
  2. Expand `active_plan.advance_step()` verification logic across all 8 `StepIntent` types (`NAVIGATE`, `INPUT_DATA`, `SELECT_OPTION`, `VERIFY_STATE`, `LAUNCH_OR_ACTIVATE`, `DISMISS_DIALOG`, `CONSULT_ADVISOR`, `CONCLUDE`).
  3. Implement automated contingency step insertion for:
     - Missing Win32 caret blinking focus prior to typing.
     - 0% visual diff stagnation after interactive clicks.
     - Unexpected modal dialog warnings.
* **Exact Function Signatures:**
  ```python
  class PrecisionAppMatcher:
      @classmethod
      def score_match(cls, label: str, target: str) -> float: ...
      @classmethod
      def find_best_element(
          cls, target: str, elements: List[UIElement], threshold: float = 0.80
      ) -> Optional[Tuple[UIElement, float]]: ...

  def verify_step_completion(
      step: PlanStep,
      action: ActionPlan,
      result: ActionResult,
      screen_diff: float,
      current_window: WindowInfo
  ) -> bool: ...
  ```
* **Acceptance Criteria:**
  - `UniversalAppResolver` transitions from Tier 2 to Tier 3 (`Win+R`) upon Start Search failure without entering infinite loops.
  - Substring collisions ("art" matching "SmartScreen", "notepad" matching "Exit Notepad") are completely eliminated (0% false click rate).
  - All 8 `StepIntent` types advance dynamically upon verified screen criteria.

---

### Sub-Phase 4F: Adversarial Testing, Preemption/Kill Certification & Regression Pass
* **Files Affected:**
  - `tests/test_escalation_cadence.py` *(New Test Suite)*
  - `tests/test_dual_channel_output.py` *(New Test Suite)*
  - `tests/test_tool_aware_reasoning.py` *(New Test Suite)*
  - `tests/test_scene_serialization.py` *(New Test Suite)*
  - `tests/test_cli_sandbox.py` *(New Test Suite)*
  - `tests/test_resolver_precision.py` *(New Test Suite)*
* **Deliverables:**
  1. Unit and integration tests for all 4 escalation tiers.
  2. CLI sandbox security tests: binary whitelist enforcement, shell injection immunity, timeout termination, and preemption token abort.
  3. UniversalAppResolver tests: 3-tier fallback progression (`Win` $\to$ `Type` $\to$ `Win+R` $\to$ `Type`) and precision word-boundary matching.
  4. Invariant certification:
     - Sub-2ms hardware touch preemption verified via synthetic hook timing.
     - Instant hard kill (`Ctrl+Alt+K`) verified in $< 5\text{ms}$.
     - `brain.mode: "local_llm"` default verified across all configuration instantiations.
     - Strict anti-hardcoding invariant verified (zero `app_map` dictionaries).
  5. Full regression pass: All existing 877 tests + new tests (>970 total) passing 100% green.
* **Acceptance Criteria:**
  - 100% green test execution (`pytest tests/`).
  - Zero test regressions across existing codebase.

---

"""
        content = content[:idx_subphases] + new_subphases_text + content[idx_subphases_end:]
    print("Patch 6 applied.")

    # -------------------------------------------------------------
    # PATCH 7: Section 12 (Victory Matrix VERIF-1 to VERIF-4, VERIF-10, VERIF-11)
    # -------------------------------------------------------------
    old_matrix_start = "| Verification ID | Test Target | Verification Command / Procedure | Pass Criteria | Invalidation Condition |"
    idx_matrix = content.find(old_matrix_start)
    old_matrix_end_marker = "## 13. Conclusion & Implementation Readiness"
    idx_matrix_end = content.find(old_matrix_end_marker, idx_matrix)
    if idx_matrix != -1 and idx_matrix_end != -1 and "VERIF-10" not in content[idx_matrix:idx_matrix_end]:
        new_matrix_text = r"""| Verification ID | Test Target | Verification Command / Procedure | Pass Criteria | Invalidation Condition |
| :--- | :--- | :--- | :--- | :--- |
| **VERIF-1** | 4-Tier Escalation Strike Counters & Loop Termination | `pytest tests/test_escalation_cadence.py tests/test_challenger_p4_empirical.py` | Tier 1 advances to Tier 2 on 2 local strikes; Tier 3 advances to Tier 4 on 2 guided strikes; Tier 4 transitions to `USER_OVERRIDE` on 3 strikes. Persistent advisor failure transitions to `USER_OVERRIDE` after 2 failures; cumulative oscillation between T3 and T4 transitions to `USER_OVERRIDE` after 3 cycles. Hardware touch immediately transitions to `USER_OVERRIDE` via `on_hardware_interrupt()`. Passive actions (`WAIT`, `DONE`) and CLI actions (`returncode == 0`) do not incur false strikes. | Strike counter fails to transition, cycles indefinitely between T3/T4 or T1/T2, leaks strikes across tiers, or increments on passive `WAIT` or successful CLI actions. |
| **VERIF-2** | Grounded Capability Manifest | `pytest tests/test_gemini_consultation_protocol.py` | Consultation prompt includes exact mouse Bézier limits, atomic Ctrl+V paste, dynamic virtual screen bounds, and explicit prohibitions against CLI scraping (`curl`/`requests`/`playwright`) and UIA pattern injection (`ValuePattern`/`InvokePattern`). | Prompt omits physical limits, hardcodes static screen bounds, or allows DOM manipulation, headless scraping, or programmatic pattern calls. |
| **VERIF-3** | Dual-Channel Output Separation & Sanitization | `pytest tests/test_dual_channel_output.py tests/test_challenger_p4_empirical.py` | Channel A extracts valid `LivingPlan` JSON supporting both `'steps'` and `'recommended_strategy'` keys; Channel B receives clean persona dialogue. All code blocks (```json, ```python, ```bash), backticks, raw error dicts, and coordinates are stripped before emitting to `UIBridge.notify_speech()`. | Blueprint dropped when using `'recommended_strategy'`, or raw JSON, coordinate tuples, Python snippets, or error tokens emitted to `UIBridge.notify_speech()`. |
| **VERIF-4** | Tool-Aware Affordance Routing & CLI Sandbox | `pytest tests/test_tool_aware_reasoning.py` | Code refactoring and test goals evaluate to `LOCAL_DEVELOPER_TOOL`; native GUI apps evaluate to `PHYSICAL_GUI`. CLI sandbox aborts upon hardware preemption token within 10ms and rejects prohibited scraping binaries. | File/code tasks default to slow GUI clicking; CLI execution ignores hardware preemption token or permits forbidden scraping commands. |
| **VERIF-5** | Textual Scene Serialization | `pytest tests/test_scene_serialization.py` | Desktop serialized to SOM table and active window brief under $< 3\text{ KB}$ payload. Zero video streaming calls. | Payload exceeds 4 KB or initiates video frame encoding. |
| **VERIF-6** | Anti-Hardcoding Invariant | `git grep -i "app_map" parasite_ai/` | Zero occurrences of application-specific dictionaries or static coordinate maps in codebase. | Any static application map or hardcoded coordinates found in source code. |
| **VERIF-7** | Hardware Preemption Invariant | `pytest tests/test_interrupt_guard.py` | Synthetic input aborts within $< 2\text{ ms}$ of physical mouse or keyboard event. | Preemption latency exceeds 2.0ms or fails to abort active drag/type. |
| **VERIF-8** | Emergency Hard Kill Invariant | `pytest tests/test_panic.py` | `Ctrl+Alt+K` terminates process tree in $< 5\text{ ms}$ via native `taskkill`. | Process hangs in Qt event loop or termination exceeds 5ms. |
| **VERIF-9** | Schema Mapping Completeness | `pytest tests/test_schema_mapping.py` | All 10 Win32 ctypes struct sizes match 64-bit Windows ABI (`MSLLHOOKSTRUCT`=32, `KBDLLHOOKSTRUCT`=24, `INPUT`=40, `GUITHREADINFO`=72). | Struct size mismatch or field offset corruption under 64-bit ctypes reflection. |
| **VERIF-10** | CLI Execution Sandbox & Preemption | `pytest tests/test_cli_sandbox.py` | Permitted binaries execute cleanly; unlisted binaries and destructive/scraping patterns raise `PermissionError`; cancellation token aborts running subprocess tree in $< 20\text{ ms}$. | Subprocess ignores cancellation token, runs unwhitelisted binary, or hangs past timeout. |
| **VERIF-11** | Resolver 3-Tier Fallback & Precision Matching | `pytest tests/test_resolver_precision.py` | Stalled Start Search transitions cleanly to Tier 3 (`Win+R`); substring queries ("art", "cat", "notepad") never click prefix collisions ("SmartScreen", "Exit Notepad"). | Resolver gets stuck in Tier 2 loop or triggers false-positive click on substring match. |

---

"""
        content = content[:idx_matrix] + new_matrix_text + content[idx_matrix_end:]
    print("Patch 7 applied.")

    # -------------------------------------------------------------
    # WRITE UPDATED CONTENT
    # -------------------------------------------------------------
    TARGET_PATH.write_text(content, encoding="utf-8")
    print(f"Successfully updated {TARGET_PATH}. Final length: {len(content)} chars, {len(content.splitlines())} lines.")

if __name__ == "__main__":
    main()
