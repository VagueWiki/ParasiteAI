"""
parasite_ai/mind/plan.py - Dynamic Living Plan & Strategic Consultation Protocol.

Implements Section 2 and Section 3 of the Unified Cognitive Architecture:
- StepIntent semantic taxonomy & StepStatus lifecycle
- PlanStep & LivingPlan Pydantic models with step advancement & contingency insertion
- Structured Gemini Strategic Consultation Prompt Formatter
- Resilient Balanced-Brace JSON Blueprint Extractor & Parser
"""

from __future__ import annotations

from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, Field

from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier

if TYPE_CHECKING:
    from parasite_ai.ui.types import UIElement
    from parasite_ai.safety.window_guard import WindowInfo
    from parasite_ai.mind.dual_mind import ActionResult

logger = logging.getLogger(__name__)


class StepIntent(str, Enum):
    """Semantic intent taxonomy for strategic living plan steps."""
    LAUNCH_OR_ACTIVATE = "LAUNCH_OR_ACTIVATE"
    NAVIGATE = "NAVIGATE"
    INPUT_DATA = "INPUT_DATA"
    SELECT_OPTION = "SELECT_OPTION"
    VERIFY_STATE = "VERIFY_STATE"
    DISMISS_DIALOG = "DISMISS_DIALOG"
    CONSULT_ADVISOR = "CONSULT_ADVISOR"
    CONCLUDE = "CONCLUDE"


class StepStatus(str, Enum):
    """Lifecycle status of a plan step."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class PlanStep(BaseModel):
    """Represents a discrete verifiable milestone within a LivingPlan."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    step_id: int = Field(ge=1, description="1-based unique step index")
    intent: StepIntent = Field(description="Semantic intent verb")
    description: str = Field(description="Human/AI-interpretable action directive")
    target_description: Optional[str] = Field(default=None, description="Visual/UI target hint")
    success_criteria: str = Field(description="Verifiable screen condition for completion")
    rationale: str = Field(default="", description="Strategic justification for this step")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Execution status")
    contingency: Optional[str] = Field(default=None, description="Handling instructions if blocked")
    tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = Field(
        default=None, description="Routed execution affordance"
    )


class LivingPlan(BaseModel):
    """
    Adaptive, multi-stage living plan representation.
    Tracks active strategy, pending/completed steps, and contingency branches.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True)

    user_goal: str = Field(description="Original user objective")
    overall_strategy: str = Field(default="", description="High-level rationale & strategic diagnosis")
    steps: List[PlanStep] = Field(default_factory=list, description="Ordered plan steps")
    current_step_id: int = Field(default=1, ge=1, description="Pointer to active step")
    replan_count: int = Field(default=0, ge=0, description="Number of replans executed")
    consulted_gemini: bool = Field(default=False, description="Whether strategic Gemini advice was used")
    escalation_tier: CadenceTier = Field(
        default=CadenceTier.TIER_1_LOCAL, description="Active escalation cadence tier"
    )
    tier_strikes: int = Field(default=0, ge=0, description="Active failure strike count in current tier")
    needs_clarification: bool = Field(default=False, description="Whether advisor requested clarification")
    clarification_question: Optional[str] = Field(default=None, description="Question asked by advisor")

    def get_current_step(self) -> Optional[PlanStep]:
        """Returns the PlanStep matching current_step_id, or None if not found."""
        for step in self.steps:
            if step.step_id == self.current_step_id:
                return step
        return None

    def advance_step(self) -> Optional[PlanStep]:
        """
        Marks current step COMPLETED, advances current_step_id to next pending step.
        Returns the new active PlanStep, or None if all steps are completed.
        """
        current = self.get_current_step()
        current_idx = -1
        if current:
            current.status = StepStatus.COMPLETED
            for idx, s in enumerate(self.steps):
                if s.step_id == current.step_id:
                    current_idx = idx
                    break

        next_step: Optional[PlanStep] = None
        # First check pending steps located after current step in the execution list
        if current_idx != -1:
            for s in self.steps[current_idx + 1:]:
                if s.status == StepStatus.PENDING:
                    next_step = s
                    break

        # Fallback to any remaining pending step
        if next_step is None:
            for s in self.steps:
                if s.status == StepStatus.PENDING and s.step_id != self.current_step_id:
                    next_step = s
                    break

        if next_step is not None:
            self.current_step_id = next_step.step_id
            next_step.status = StepStatus.IN_PROGRESS
            return next_step

        return None

    def mark_step_failed(self, step_id: Optional[int] = None, reason: str = "") -> None:
        """Marks specified step (or current step) as FAILED and records reason."""
        target_id = step_id if step_id is not None else self.current_step_id
        for step in self.steps:
            if step.step_id == target_id:
                step.status = StepStatus.FAILED
                if reason:
                    if step.contingency:
                        step.contingency = f"{step.contingency}; Failure: {reason}"
                    else:
                        step.contingency = f"Failure: {reason}"
                break

    def insert_contingency_step(self, step: PlanStep) -> None:
        """Injects a dynamic contingency step immediately following current step."""
        self.replan_count += 1
        insert_idx = len(self.steps)
        for idx, s in enumerate(self.steps):
            if s.step_id == self.current_step_id:
                insert_idx = idx + 1
                break
        self.steps.insert(insert_idx, step)

    def insert_caret_contingency(self, target_desc: Optional[str] = None) -> PlanStep:
        """Injects a contingency step to focus an input field when caret focus is unacquired."""
        next_id = max([s.step_id for s in self.steps], default=0) + 1
        contingency_step = PlanStep(
            step_id=next_id,
            intent=StepIntent.NAVIGATE,
            description=f"Click to focus {target_desc or 'input field'} and acquire blinking caret",
            target_description=target_desc,
            success_criteria="Caret focus acquired and active",
            rationale="Caret focus unacquired prior to typing; restoring caret via click",
            contingency="Retry typing once caret is acquired",
        )
        self.insert_contingency_step(contingency_step)
        return contingency_step

    def insert_stagnation_contingency(self, step: Optional[PlanStep] = None) -> PlanStep:
        """Injects a contingency step to re-ground and retry an action after 0% diff visual stagnation."""
        next_id = max([s.step_id for s in self.steps], default=0) + 1
        target_desc = step.target_description if step else None
        contingency_step = PlanStep(
            step_id=next_id,
            intent=StepIntent.NAVIGATE,
            description=f"Re-ground and retry action for {target_desc or 'target'} after visual stagnation",
            target_description=target_desc,
            success_criteria="Screen diff >= 0.02 indicating UI response",
            rationale="Action produced 0% visual difference; re-grounding coordinates",
            contingency="Escalate to Tier 2 Gemini consultation if stagnation persists",
        )
        self.insert_contingency_step(contingency_step)
        return contingency_step

    def insert_modal_dialog_contingency(self, dialog_label: str) -> PlanStep:
        """Injects a contingency step to dismiss an unexpected blocking modal dialog."""
        next_id = max([s.step_id for s in self.steps], default=0) + 1
        contingency_step = PlanStep(
            step_id=next_id,
            intent=StepIntent.DISMISS_DIALOG,
            description=f"Dismiss blocking dialog: {dialog_label}",
            target_description=dialog_label,
            success_criteria="Dialog dismissed and main window accessible",
            rationale="Unexpected modal dialog blocking workflow execution",
            contingency="Press Escape or click Close/Cancel if dialog cannot be confirmed",
        )
        self.insert_contingency_step(contingency_step)
        return contingency_step

    def is_completed(self) -> bool:
        """Returns True if all steps are completed or skipped."""
        if not self.steps:
            return False
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    def to_prompt_context(self) -> str:
        """Renders plan status into a clean summary for LLM context prompts."""
        lines = [
            f"Goal: {self.user_goal}",
            f"Strategy: {self.overall_strategy or 'Dynamic execution'}",
            f"Plan Progress (Active Step: {self.current_step_id}):",
        ]
        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                mark = "✓"
            elif step.step_id == self.current_step_id:
                mark = "→"
            elif step.status == StepStatus.FAILED:
                mark = "✗"
            else:
                mark = " "
            lines.append(f"  [{mark}] Step {step.step_id}: {step.intent.value} — {step.description} ({step.status.value})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Strategic Gemini Consultation Protocol Formatters & Parsers
# ---------------------------------------------------------------------------

class GroundedCapabilityContract(BaseModel):
    """
    Formal Pydantic representation of the Parasite Physical Capability Contract.
    Injected as system preamble during strategic Gemini consultations.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True)

    version: str = Field(default="4.0.0")
    target_environment: str = Field(default="Windows 11 64-bit Desktop")
    virtual_desktop_bounds: Tuple[int, int, int, int] = Field(
        default=(0, 0, 3840, 1080),
        description="Dynamic virtual screen bounds [x_min, y_min, width, height]"
    )
    dpi_scale: str = Field(default="100% (96 DPI Native)")
    monitor_count_desc: str = Field(default="Dynamically enumerated via EnumDisplayMonitors")
    primary_monitor_bounds: Tuple[int, int, int, int] = Field(default=(0, 0, 1920, 1080))
    actuators_mouse: Dict[str, Any] = Field(
        default_factory=lambda: {
            "kinematics": "Human-curved cubic Bézier trajectories with 5th-order Min-Jerk velocity profiling and 1px Gaussian micro-jitter",
            "polling_rate": "120 Hz update loop via high-precision Win32 multimedia timer (timeBeginPeriod(1))",
            "primitives": [
                "left_click(x, y)", "double_click(x, y)", "right_click(x, y)",
                "middle_click(x, y)", "drag_and_drop(x1, y1, x2, y2)", "scroll(wheel_delta, x, y)"
            ],
            "coordinate_validation": "All coordinates must fall within active virtual screen bounds; out-of-bounds clicks are hard-rejected",
        }
    )
    actuators_keyboard: Dict[str, Any] = Field(
        default_factory=lambda: {
            "high_speed_pasting": "Atomic Ctrl+V paste (<100ms) with automatic user clipboard backup and transparent restoration",
            "cadence_typing": "Physical SendInput using KEYEVENTF_UNICODE with 25-75ms human cadence jitter and micro-pauses",
            "supported_chords": [
                "Win (Start Menu)", "Win+R (Run Dialog)", "Alt+Tab (Window Switch)",
                "Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A / Ctrl+Z / Ctrl+S / Ctrl+F",
                "Enter / Esc / Tab / Backspace / Delete / Arrow Keys"
            ],
            "multiline_handling": "Shift+Enter for chat multiline inputs to avoid premature submission",
        }
    )
    perception: Dict[str, Any] = Field(
        default_factory=lambda: {
            "resolution": "1:1 unscaled cursor foveal crop (512x512) and downscaled virtual desktop macro glance (3840x1080)",
            "element_grounding": "Numbered Set-of-Mark (SOM) tags [#1..#N] merging Win32 UI Automation tree walk and scoped RapidOCR. UI Automation is strictly read-only for bounding box and label discovery; programmatic pattern invocation (ValuePattern, InvokePattern) is forbidden.",
            "visual_diffing": "Localized post-action ROI diffing scoped to target bounding box + 20px padding (target_roi.pad(20))",
            "perceptual_hashing": "64-bit dHash gating (0% CPU/GPU overhead when screen is static)",
            "focus_detection": "Win32 Caret blinking detection via 64-bit GUITHREADINFO (cbSize=72) verifying flags & GUI_CARETBLINKING",
        }
    )
    hard_safety_constraints: List[str] = Field(
        default_factory=lambda: [
            "ZERO headless browser automation; NO DOM manipulation, document.querySelector, or CDP protocols",
            "ZERO headless scraping or HTTP data extraction via CLI/scripts (curl, wget, requests, playwright, puppeteer, selenium, beautifulsoup are strictly forbidden)",
            "ZERO programmatic accessibility pattern invocation (ValuePattern.SetValue, InvokePattern.Invoke, TogglePattern.Toggle, SelectionItemPattern.Select are strictly forbidden; UIA is strictly read-only for element discovery)",
            "ZERO private OS message injection (WM_SETTEXT); all interactions must use physical SendInput simulation",
            "Sub-2ms physical hardware preemption: synthetic input instantly aborts if human moves physical mouse or types",
            "Instant Hard Kill (Ctrl+Alt+K / Ctrl+Alt+Q) terminates process tree in <5ms via taskkill /F /T",
            "Protected Windows: Password managers (Bitwarden, 1Password, KeePass) and UAC dialogs trigger safety pause",
            "Strict Anti-Hardcoding: NO application-specific lookup tables (app_map = {} is strictly forbidden)",
        ]
    )

    def to_yaml_manifest(self) -> str:
        vx, vy, vw, vh = self.virtual_desktop_bounds
        vx_max = vx + vw
        vy_max = vy + vh
        prim_lines = "\n".join(f'        - "{p}"' for p in self.actuators_mouse["primitives"])
        chord_lines = "\n".join(f'        - "{c}"' for c in self.actuators_keyboard["supported_chords"])
        constraint_lines = "\n".join(f'    - "{c}"' for c in self.hard_safety_constraints)

        return f"""Parasite_Capability_Contract:
  Version: "{self.version}"
  Target_Environment: "{self.target_environment}"
  Display_Geometry:
    Virtual_Desktop_Bounds: "Dynamic via get_virtual_screen_bounds() [{vx}, {vy}, {vw}, {vh}]"
    DPI_Scale: "{self.dpi_scale}"
    Monitor_Count: "{self.monitor_count_desc}"
    Primary_Monitor_Bounds: [{self.primary_monitor_bounds[0]}, {self.primary_monitor_bounds[1]}, {self.primary_monitor_bounds[2]}, {self.primary_monitor_bounds[3]}]

  Actuators:
    Mouse:
      Kinematics: "{self.actuators_mouse['kinematics']}"
      Polling_Rate: "{self.actuators_mouse['polling_rate']}"
      Primitives:
{prim_lines}
      Coordinate_Validation: "All coordinates must fall within active virtual screen bounds [{vx}, {vx_max}) x [{vy}, {vy_max}); out-of-bounds clicks are hard-rejected"

    Keyboard:
      High_Speed_Pasting: "{self.actuators_keyboard['high_speed_pasting']}"
      Cadence_Typing: "{self.actuators_keyboard['cadence_typing']}"
      Supported_Chords:
{chord_lines}
      Multiline_Handling: "{self.actuators_keyboard['multiline_handling']}"

  Perception:
    Resolution: "{self.perception['resolution']}"
    Element_Grounding: "{self.perception['element_grounding']}"
    Visual_Diffing: "{self.perception['visual_diffing']}"
    Perceptual_Hashing: "{self.perception['perceptual_hashing']}"
    Focus_Detection: "{self.perception['focus_detection']}"

  Hard_Safety_Constraints:
{constraint_lines}"""


def build_grounded_capability_manifest(vbounds: Optional[Tuple[int, int, int, int]] = None) -> str:
    """
    Constructs the formatted YAML Grounded Capability Contract with dynamic screen bounds.
    Queries active virtual screen metrics or uses provided vbounds.
    """
    if vbounds is None:
        try:
            from parasite_ai.vision.capture import get_virtual_screen_bounds
            vx, vy, vw, vh = get_virtual_screen_bounds()
        except Exception:
            vx, vy, vw, vh = 0, 0, 3840, 1080
    else:
        vx, vy, vw, vh = vbounds

    contract = GroundedCapabilityContract(virtual_desktop_bounds=(vx, vy, vw, vh))
    return contract.to_yaml_manifest()


def serialize_textual_scene_brief(
    elements: Optional[List[Any]] = None,
    window_info: Optional[Any] = None,
    recent_diff: float = 0.0,
    caret_active: bool = False,
    active_tier: str = "TIER_1_LOCAL -> TIER_2_CONSULT",
    consecutive_strikes: int = 2,
    recent_dhash: str = "0000000000000000",
    max_elements: int = 25,
) -> str:
    """
    Serializes desktop scene into compact Active Window Brief YAML + Set-of-Mark Markdown table.
    Guarantees total payload is strictly under 3 KB (3072 bytes) of pure text without video streaming.
    """
    if window_info is not None:
        title = getattr(window_info, "title", "Desktop") or "Desktop"
        process_name = getattr(window_info, "process_name", "explorer.exe") or "explorer.exe"
        hwnd = getattr(window_info, "hwnd", 0)
        rect = getattr(window_info, "rect", (0, 0, 1920, 1080))
        if len(rect) >= 4:
            win_x, win_y = int(rect[0]), int(rect[1])
            win_w = max(0, int(rect[2]) - int(rect[0]))
            win_h = max(0, int(rect[3]) - int(rect[1]))
        else:
            win_x, win_y, win_w, win_h = 0, 0, 1920, 1080
    else:
        title = "Desktop"
        process_name = "explorer.exe"
        hwnd = 0
        win_x, win_y, win_w, win_h = 0, 0, 1920, 1080

    caret_status = "Active (Blinking)" if caret_active else "Inactive / Hidden"

    brief_header = f"""Active_Window_Brief:
  Title: "{title}"
  Process_Name: "{process_name}"
  HWND: {hwnd}
  Bounds: [{win_x}, {win_y}, {win_w}, {win_h}]
  Monitor: "Primary (Monitor 1)"
  Caret_Status: "{caret_status}"
  Recent_Diff_Ratio: {recent_diff:.4f}
  Recent_dHash: "{recent_dhash}"
  Consecutive_Strikes: {consecutive_strikes}
  Active_Tier: "{active_tier}"
"""

    table_lines = [
        "Textual_Set_of_Mark_Inventory:",
        "| ID | Control Type | Label / Accessible Name | Bounding Box [x, y, w, h] | Center (x, y) | Source | Flags |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    elem_list = elements or []
    included = 0
    total_elems = len(elem_list)

    # Budget: brief_header is ~350 bytes. We budget up to 2800 bytes for table to guarantee < 3072 bytes.
    max_table_bytes = 2800 - len(brief_header.encode("utf-8"))
    current_table_bytes = sum(len(line.encode("utf-8")) + 1 for line in table_lines)

    for idx, elem in enumerate(elem_list, start=1):
        if included >= max_elements:
            break

        elem_id = getattr(elem, "id", idx)
        role = getattr(elem, "role", "Element") or "Element"
        label = (getattr(elem, "label", "") or "").replace("\n", " ").replace("|", "/").strip()
        if not label:
            label = "Unnamed Control"
        label_quoted = f'"{label[:32]}"'

        x = getattr(elem, "x", 0)
        y = getattr(elem, "y", 0)
        w = getattr(elem, "width", 0)
        h = getattr(elem, "height", 0)
        cx = getattr(elem, "center_x", x + w // 2)
        cy = getattr(elem, "center_y", y + h // 2)
        source = (getattr(elem, "source", "UIA") or "UIA").upper()

        flags_list = []
        if getattr(elem, "is_active_window", True):
            flags_list.append("ACTIVE")
        if caret_active and str(role).lower() in ("edit", "document", "combobox"):
            flags_list.append("CARET")
        flags = ", ".join(flags_list) if flags_list else "ENABLED"

        row = f"| #{elem_id} | {role} | {label_quoted} | [{x}, {y}, {w}, {h}] | ({cx}, {cy}) | {source} | {flags} |"
        row_bytes = len(row.encode("utf-8")) + 1

        # Check if adding this row would exceed table budget (leaving 100 bytes for truncation line)
        if current_table_bytes + row_bytes > max_table_bytes - 100:
            break

        table_lines.append(row)
        current_table_bytes += row_bytes
        included += 1

    if total_elems == 0:
        table_lines.append("| None | None | \"No interactive controls detected\" | [0, 0, 0, 0] | (0, 0) | N/A | NONE |")
    elif total_elems > included:
        omitted = total_elems - included
        table_lines.append(f"[Truncated: {omitted} additional elements omitted to preserve <3KB budget]")

    result = brief_header + "\n" + "\n".join(table_lines)
    return result


def format_gemini_consultation_prompt(
    user_goal: str = "",
    elements: Optional[List[Any]] = None,
    window_info: Optional[Any] = None,
    dilemma: str = "",
    recent_history: str = "",
    *,
    goal: Optional[str] = None,
    active_window_title: Optional[str] = None,
    process_name: Optional[str] = None,
    open_apps_summary: Optional[str] = None,
    visual_scene_summary: Optional[str] = None,
    dilemma_description: Optional[str] = None,
    caret_active: bool = False,
    recent_diff: float = 0.0,
    current_step_intent: str = "NAVIGATE",
    current_step_description: str = "Execute next planned action",
    available_tools: str = "Antigravity CLI, python, pytest, git, powershell",
    **kwargs: Any,
) -> str:
    """
    Formats the standardized Strategic Gemini Consultation Brief embedding the
    Grounded Capability Contract, textual Set-of-Mark scene brief, and LivingPlan schema.
    """
    clean_goal = (user_goal or goal or "").strip()
    clean_dilemma = (dilemma or dilemma_description or "").strip() or "Initial plan formulation"

    if window_info is not None:
        win_title = getattr(window_info, "title", "Desktop") or "Desktop"
        win_proc = getattr(window_info, "process_name", "explorer.exe") or "explorer.exe"
        win_hwnd = getattr(window_info, "hwnd", 0)
        rect = getattr(window_info, "rect", (0, 0, 1920, 1080))
        if len(rect) >= 4:
            win_x, win_y = int(rect[0]), int(rect[1])
            win_w = max(0, int(rect[2]) - int(rect[0]))
            win_h = max(0, int(rect[3]) - int(rect[1]))
        else:
            win_x, win_y, win_w, win_h = 0, 0, 1920, 1080
    else:
        win_title = (active_window_title or "").strip() or "Desktop"
        win_proc = (process_name or "").strip() or "explorer.exe"
        win_hwnd = 0
        win_x, win_y, win_w, win_h = 0, 0, 1920, 1080

    clean_open_apps = (open_apps_summary or "").strip() or "None"
    clean_visual_scene = (visual_scene_summary or "").strip() or "Default desktop view"
    clean_history = (recent_history or "").strip() or "No prior actions recorded"

    capability_manifest = build_grounded_capability_manifest()
    scene_brief = serialize_textual_scene_brief(
        elements=elements,
        window_info=window_info,
        recent_diff=recent_diff,
        caret_active=caret_active,
    )
    caret_status_text = "Active (Blinking)" if caret_active else "Inactive / Hidden"

    prompt = f"""[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]
You are the Strategic Cognitive Advisor for ParasiteAI, a 100% visible, desktop-native Windows 11 AI companion.

# CAPABILITY CONTRACT & CONSTRAINTS
{capability_manifest}
- Physical desktop automation ONLY (Bézier mouse, SendInput cadence typing, atomic Ctrl+V paste).
- ZERO headless browser automation, ZERO CLI scraping (curl/requests/playwright), ZERO programmatic UIA pattern calls (ValuePattern/InvokePattern).

# ACTIVE DESKTOP STATE
- Foreground Window: "{win_title}" (Process: "{win_proc}", HWND: {win_hwnd})
- Active Window: {win_title} ({win_proc})
- Window Bounds: [{win_x}, {win_y}, {win_w}, {win_h}] on Virtual Desktop [0, 0, 3840, 1080]
- Caret Focus: {caret_status_text}
- Available Developer Tools: {available_tools}
- Visible Applications: {clean_open_apps}
- Visual Scene Observation: {clean_visual_scene}

# TEXTUAL SET-OF-MARK (SOM) INVENTORY
{scene_brief}

# CURRENT GOAL & FAILURE DILEMMA
- User Goal: {clean_goal}
- Active Plan Step: {current_step_intent} - "{current_step_description}"
- Current Dilemma / Status: {clean_dilemma}
- Failure Reason: {clean_dilemma}
- Recent Action History:
{clean_history}

# INSTRUCTIONS
Analyze the desktop state, SOM inventory, and failure history. Formulate an actionable, step-by-step LivingPlan blueprint that ParasiteAI can execute physically.
Return your response strictly as a single JSON object inside a ```json ... ``` codeblock matching this schema:

{{
  "rationale": "Clear, concise diagnostic explanation of why the previous action failed and what strategy is required.",
  "recommended_strategy": [
    {{
      "step_id": 1,
      "intent": "LAUNCH_OR_ACTIVATE | NAVIGATE | INPUT_DATA | SELECT_OPTION | VERIFY_STATE | DISMISS_DIALOG | CONSULT_ADVISOR | CONCLUDE",
      "description": "Concrete physical instruction.",
      "target_description": "Descriptive name matching an SOM element or window control.",
      "success_criteria": "Verifiable desktop change (e.g. 'File menu expands' or 'Caret appears in search box').",
      "rationale": "Why this step is necessary.",
      "contingency": "What to do if this specific step produces 0% visual diff."
    }}
  ]
}}"""
    return prompt


# Backward compatibility alias for the raw template string
GEMINI_CONSULTATION_TEMPLATE = format_gemini_consultation_prompt(
    goal="{goal}",
    active_window_title="{active_window_title}",
    process_name="{process_name}",
    open_apps_summary="{open_apps_summary}",
    visual_scene_summary="{visual_scene_summary}",
    dilemma_description="{dilemma_description}",
)


def _clean_json_candidate(candidate: str) -> Optional[Dict[str, Any]]:
    """Attempts to parse JSON candidate, with fallback stripping trailing commas."""
    candidate_str = candidate.strip()
    try:
        parsed = json.loads(candidate_str)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Resilience: Clean trailing commas before object/array closing braces
    try:
        sanitized = re.sub(r',\s*([}\]])', r'\1', candidate_str)
        parsed = json.loads(sanitized)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return None


def _is_strategic_blueprint(parsed: Any) -> bool:
    """Checks whether parsed dictionary contains strategic blueprint keys."""
    if not isinstance(parsed, dict):
        return False
    return "recommended_strategy" in parsed or "steps" in parsed or "rationale" in parsed or "need_clarification" in parsed


def _extract_balanced_json(text: str) -> Optional[Dict[str, Any]]:
    """Scans text for balanced-brace JSON objects containing strategic blueprint keys."""
    n = len(text)
    i = 0
    while i < n:
        if text[i] == '{':
            depth = 0
            in_string = False
            escape = False
            start = i
            for j in range(i, n):
                char = text[j]
                if in_string:
                    if escape:
                        escape = False
                    elif char == '\\':
                        escape = True
                    elif char == '"':
                        in_string = False
                else:
                    if char == '"':
                        in_string = True
                    elif char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = text[start : j + 1]
                            parsed = _clean_json_candidate(candidate)
                            if parsed and _is_strategic_blueprint(parsed):
                                return parsed
                            break
        i += 1
    return None


def extract_strategic_blueprint_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Resilient balanced-brace extractor for strategic plan JSON blueprints.
    Extracts dictionaries containing 'recommended_strategy', 'steps', or 'rationale'.
    Supports raw JSON, markdown ```json ... ``` blocks, and conversational text.
    """
    if not text or not isinstance(text, str):
        return None

    # Pass 1: Direct JSON parsing
    parsed = _clean_json_candidate(text)
    if parsed and _is_strategic_blueprint(parsed):
        return parsed

    # Pass 2: Markdown fence extraction
    fence_pattern = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        content = match.group(1).strip()
        parsed = _clean_json_candidate(content)
        if parsed and _is_strategic_blueprint(parsed):
            return parsed
        # Fallback to balanced-brace scan inside the fenced content
        inner = _extract_balanced_json(content)
        if inner and _is_strategic_blueprint(inner):
            return inner

    # Pass 3: Balanced-brace depth scan across entire string
    return _extract_balanced_json(text)


INTENT_FALLBACK_MAP = {
    "LAUNCH": StepIntent.LAUNCH_OR_ACTIVATE,
    "ACTIVATE": StepIntent.LAUNCH_OR_ACTIVATE,
    "OPEN": StepIntent.LAUNCH_OR_ACTIVATE,
    "NAVIGATE": StepIntent.NAVIGATE,
    "CLICK": StepIntent.NAVIGATE,
    "MOVE": StepIntent.NAVIGATE,
    "INPUT": StepIntent.INPUT_DATA,
    "TYPE": StepIntent.INPUT_DATA,
    "WRITE": StepIntent.INPUT_DATA,
    "INPUT_DATA": StepIntent.INPUT_DATA,
    "SELECT": StepIntent.SELECT_OPTION,
    "CHOOSE": StepIntent.SELECT_OPTION,
    "SELECT_OPTION": StepIntent.SELECT_OPTION,
    "VERIFY": StepIntent.VERIFY_STATE,
    "CHECK": StepIntent.VERIFY_STATE,
    "VERIFY_STATE": StepIntent.VERIFY_STATE,
    "DISMISS": StepIntent.DISMISS_DIALOG,
    "CLOSE": StepIntent.DISMISS_DIALOG,
    "DISMISS_DIALOG": StepIntent.DISMISS_DIALOG,
    "CONSULT": StepIntent.CONSULT_ADVISOR,
    "CONSULT_ADVISOR": StepIntent.CONSULT_ADVISOR,
    "CONCLUDE": StepIntent.CONCLUDE,
    "FINISH": StepIntent.CONCLUDE,
    "DONE": StepIntent.CONCLUDE,
}


class ConsultationClarificationNeeded(Exception):
    """Raised when advisor requests multi-turn clarification before finalizing plan."""
    def __init__(self, question: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(f"Advisor requested clarification: {question}")
        self.question = question
        self.context = context or {}


def is_clarification_response(raw_text: str) -> Tuple[bool, Optional[str]]:
    """Checks whether Gemini response requested clarification rather than returning a plan."""
    data = extract_strategic_blueprint_json(raw_text)
    if data and data.get("need_clarification") is True:
        return True, str(data.get("question", "")).strip() or "Clarification required"
    return False, None


def resolve_clarification_query(
    question: str,
    window_info: Optional[Any] = None,
    elements: Optional[List[Any]] = None,
) -> str:
    """
    Synthesizes clarification context for advisor:
    1. Inspects modal/dialog status if question mentions dialog/modal/popup.
    2. Identifies matching SOM candidate tags and coordinates if ambiguous controls mentioned.
    """
    q_lower = (question or "").lower()
    responses = []

    if any(k in q_lower for k in ("modal", "dialog", "popup", "pane", "window")):
        is_sensitive = getattr(window_info, "is_sensitive", False) if window_info else False
        title = getattr(window_info, "title", "Unknown") if window_info else "Unknown"
        responses.append(f"Window '{title}' is an active foreground window (sensitive={is_sensitive}).")

    if elements:
        candidates = []
        for elem in elements:
            label = getattr(elem, "label", "") or ""
            role = getattr(elem, "role", "") or ""
            elem_id = getattr(elem, "id", 0)
            cx = getattr(elem, "center_x", 0)
            cy = getattr(elem, "center_y", 0)
            for word in q_lower.split():
                if len(word) >= 4 and (word in label.lower() or word in role.lower()):
                    candidates.append(f"[#{elem_id}] {role} '{label}' at ({cx}, {cy})")
                    break
        if candidates:
            responses.append(f"Matching candidates found on screen: {'; '.join(candidates[:5])}.")

    if not responses:
        responses.append("No additional modal or element disambiguation anomalies detected.")

    return " ".join(responses)


def parse_gemini_consultation_response(raw_text: str, user_goal: str) -> LivingPlan:
    """
    Parses raw Gemini text into a validated LivingPlan.
    Raises ValueError if no valid blueprint can be extracted.
    """
    data = extract_strategic_blueprint_json(raw_text)
    if not data:
        preview = (raw_text[:200] + "...") if raw_text and len(raw_text) > 200 else raw_text
        raise ValueError(f"Failed to extract strategic blueprint from Gemini response: {preview}")

    # Multi-turn clarification hook (handling "need_clarification": true)
    if data.get("need_clarification") is True:
        question = str(data.get("question", "")).strip() or "Additional UI context required by advisor"
        clarification_step = PlanStep(
            step_id=1,
            intent=StepIntent.CONSULT_ADVISOR,
            description=f"Clarification requested: {question}",
            target_description="Active Desktop Context",
            success_criteria="Advisor clarification answered and strategic blueprint hydrated",
            rationale=question,
            status=StepStatus.IN_PROGRESS,
            contingency="Inspect Win32 window style (WS_POPUP / IsModal) and disambiguate SOM controls",
        )
        return LivingPlan(
            user_goal=user_goal.strip(),
            overall_strategy=f"Clarification needed: {question}",
            steps=[clarification_step],
            current_step_id=1,
            replan_count=0,
            consulted_gemini=True,
            needs_clarification=True,
            clarification_question=question,
        )

    rationale = data.get("rationale") or data.get("overall_strategy") or "Strategic plan generated by Gemini"
    raw_steps = data.get("recommended_strategy") or data.get("steps") or []

    steps: List[PlanStep] = []
    for idx, s in enumerate(raw_steps, start=1):
        if not isinstance(s, dict):
            continue

        step_id_val = s.get("step_id", idx)
        try:
            step_id = int(step_id_val)
            if step_id < 1:
                step_id = idx
        except (ValueError, TypeError):
            step_id = idx

        raw_intent = str(s.get("intent", "NAVIGATE")).strip().upper()
        try:
            intent = StepIntent(raw_intent)
        except ValueError:
            intent = INTENT_FALLBACK_MAP.get(raw_intent, StepIntent.NAVIGATE)

        description = str(s.get("description", f"Step {step_id}")).strip() or f"Step {step_id}"
        target_description = s.get("target_description")
        if target_description is not None:
            target_description = str(target_description).strip() or None

        success_criteria = str(s.get("success_criteria", "Visual confirmation of step completion")).strip()
        if not success_criteria:
            success_criteria = "Visual confirmation of step completion"

        step_rationale = str(s.get("rationale", "")).strip()
        contingency = s.get("contingency")
        if contingency is not None:
            contingency = str(contingency).strip() or None

        steps.append(
            PlanStep(
                step_id=step_id,
                intent=intent,
                description=description,
                target_description=target_description,
                success_criteria=success_criteria,
                rationale=step_rationale,
                status=StepStatus.PENDING,
                contingency=contingency,
            )
        )

    if steps:
        steps[0].status = StepStatus.IN_PROGRESS
        active_step_id = steps[0].step_id
    else:
        active_step_id = 1

    return LivingPlan(
        user_goal=user_goal.strip(),
        overall_strategy=rationale.strip(),
        steps=steps,
        current_step_id=active_step_id,
        replan_count=0,
        consulted_gemini=True,
    )


# ---------------------------------------------------------------------------
# Dynamic Step Verification & Contingency Generation
# ---------------------------------------------------------------------------

def check_and_insert_contingencies(
    plan: LivingPlan,
    step: PlanStep,
    screen_diff: float,
    caret_active: bool = True,
    blocking_dialog: Optional[Union[UIElement, str]] = None,
) -> Optional[PlanStep]:
    """
    Checks for common execution anomalies and inserts contingency steps:
    1. Blocking modal dialogs -> DISMISS_DIALOG contingency.
    2. Missing caret focus for INPUT_DATA -> NAVIGATE click-to-focus contingency.
    3. 0% visual diff stagnation for interactive steps -> re-ground contingency.

    When a prerequisite contingency step is inserted, updates plan.current_step_id
    to that contingency step so remediation executes first.
    """
    contingency: Optional[PlanStep] = None
    if blocking_dialog:
        label = getattr(blocking_dialog, "label", None) or str(blocking_dialog)
        contingency = plan.insert_modal_dialog_contingency(label or "Modal Dialog")
    elif step.intent == StepIntent.INPUT_DATA and not caret_active:
        contingency = plan.insert_caret_contingency(step.target_description)
    else:
        interactive_intents = {
            StepIntent.NAVIGATE,
            StepIntent.INPUT_DATA,
            StepIntent.SELECT_OPTION,
            StepIntent.LAUNCH_OR_ACTIVATE,
        }
        if step.intent in interactive_intents and screen_diff < 0.001:
            contingency = plan.insert_stagnation_contingency(step)

    if contingency is not None:
        plan.current_step_id = contingency.step_id

    return contingency


def verify_step_completion(
    step: PlanStep,
    action: ActionPlan,
    result: ActionResult,
    screen_diff: float = 0.0,
    current_window: Optional[WindowInfo] = None,
) -> bool:
    """
    Verifies completion of a PlanStep following physical action execution and visual settling.
    Evaluates across all 8 StepIntent semantic categories:
      1. LAUNCH_OR_ACTIVATE: Window title / process match, or significant visual diff (>= 0.02).
      2. NAVIGATE: Action succeeded and visual diff >= 0.02 (or CLI returncode == 0).
      3. INPUT_DATA: Action succeeded and visual diff >= 0.005 (or CLI returncode == 0).
      4. SELECT_OPTION: Action succeeded and visual diff >= 0.005.
      5. VERIFY_STATE: Passive assertion / check succeeded (or target window matched).
      6. DISMISS_DIALOG: Action succeeded and visual diff >= 0.01 or dialog absent from window title.
      7. CONSULT_ADVISOR: Consultation successfully returned strategic blueprint.
      8. CONCLUDE: Goal marked DONE and action succeeded.
    """
    if result is None or not getattr(result, "success", True) or getattr(result, "interrupted", False):
        return False

    if getattr(action, "action", None) == ActionType.PANIC:
        return False

    intent = step.intent

    if intent == StepIntent.LAUNCH_OR_ACTIVATE:
        # Check window title / process name match
        target = (step.target_description or "").strip().lower()
        if not target:
            from parasite_ai.mind.resolver import UniversalAppResolver
            extracted = UniversalAppResolver.extract_target_app(step.description)
            if extracted:
                target = extracted.strip().lower()

        if target and current_window:
            win_title = (getattr(current_window, "title", None) or "").lower()
            proc_name = (getattr(current_window, "process_name", None) or "").lower()
            if target in win_title or target in proc_name:
                return True
            # Active window is known and does NOT match target application
            return False

        # CLI launch returncode check
        if getattr(action, "action", None) == ActionType.RUN_CLI_COMMAND:
            return getattr(result, "returncode", None) == 0

        # Visual difference check (new application window opened)
        return screen_diff >= 0.02

    elif intent == StepIntent.NAVIGATE:
        if getattr(action, "action", None) == ActionType.RUN_CLI_COMMAND:
            return getattr(result, "returncode", None) == 0
        return screen_diff >= 0.02

    elif intent == StepIntent.INPUT_DATA:
        if getattr(action, "action", None) == ActionType.RUN_CLI_COMMAND:
            return getattr(result, "returncode", None) == 0
        # Typing/paste actions should produce observable screen difference
        if getattr(action, "action", None) in (ActionType.TYPE, ActionType.CLICK_AND_TYPE, ActionType.HOTKEY):
            return screen_diff >= 0.005
        return screen_diff >= 0.005

    elif intent == StepIntent.SELECT_OPTION:
        return screen_diff >= 0.005

    elif intent == StepIntent.VERIFY_STATE:
        target = (step.target_description or "").strip().lower()
        if target and current_window:
            win_title = (getattr(current_window, "title", None) or "").lower()
            proc_name = (getattr(current_window, "process_name", None) or "").lower()
            if target in win_title or target in proc_name:
                return True
        # Passive state verification: successful assertion
        return bool(getattr(result, "success", True))

    elif intent == StepIntent.DISMISS_DIALOG:
        if screen_diff >= 0.01:
            return True
        if current_window:
            win_title = (getattr(current_window, "title", None) or "").lower()
            dialog_keywords = ("dialog", "alert", "confirm", "warning", "error", "prompt", "save changes", "notice")
            if not any(kw in win_title for kw in dialog_keywords):
                return True
        return bool(getattr(result, "success", True))

    elif intent == StepIntent.CONSULT_ADVISOR:
        return bool(getattr(result, "success", True))

    elif intent == StepIntent.CONCLUDE:
        action_type = getattr(action, "action", None)
        reasoning = (getattr(action, "reasoning", None) or "").lower()
        return bool(getattr(result, "success", True)) and (
            action_type == ActionType.DONE
            or step.status == StepStatus.COMPLETED
            or "done" in reasoning
            or "complete" in reasoning
        )

    return False

