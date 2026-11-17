"""
parasite_ai/mind/parasite_protocol.py - Strict Nonce-Bound Protocol & Domain Models for ParasiteSkill.

Defines request/response models, semantic-only action/plan schemas (zero screen
coordinates, §8.1), shared coordinate-pattern guards (§8.3), symbolic prompt
templates across PROACTIVE_PLAN / REACTIVE_RECOVERY / SKILL_COAUTHOR phases, and a
strict nonce-bound XML-tag parser defending against screen-sourced prompt injection.
"""

from __future__ import annotations

from enum import Enum
import hmac
import json
import re
import secrets
from typing import Any, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from parasite_ai.mind.offloader import sanitize_consultation_prompt
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepDirective,
    StepIntent,
    StepStatus,
    _CONTROL_CHAR_RE,
    _COORDINATE_PATTERNS,
    assert_no_numeric_coordinates,
    find_coordinate_patterns,
    strip_control_chars,
)


def generate_nonce(nbytes: int = 8) -> str:
    """Generates a fresh cryptographic hex nonce per request."""
    return secrets.token_hex(nbytes)


# ---------------------------------------------------------------------------
# Enums & Failure Taxonomy
# ---------------------------------------------------------------------------

class ParasitePhase(str, Enum):
    """Lifecycle roles played by ParasiteSkill."""

    PROACTIVE_PLAN = "PROACTIVE_PLAN"
    REACTIVE_RECOVERY = "REACTIVE_RECOVERY"
    SKILL_COAUTHOR = "SKILL_COAUTHOR"


class RecoveryTrigger(str, Enum):
    """Deterministic cause attributed when Tier-2 reactive recovery fires."""

    OSCILLATION = "OSCILLATION"
    CONSECUTIVE_CLICK_FAILURES = "CONSECUTIVE_CLICK_FAILURES"
    CONSECUTIVE_STRIKES = "CONSECUTIVE_STRIKES"


class ParasiteFailure(str, Enum):
    """Exhaustive fail-closed failure codes for ParasiteSkill invocations."""

    PREFLIGHT_SENSITIVE_WINDOW = "PREFLIGHT_SENSITIVE_WINDOW"
    BREAKER_OPEN = "BREAKER_OPEN"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    HOTKEY_INTERRUPTED = "HOTKEY_INTERRUPTED"
    FOCUS_TIMEOUT = "FOCUS_TIMEOUT"
    WINDOW_IDENTITY_MISMATCH = "WINDOW_IDENTITY_MISMATCH"
    CARET_NOT_ACQUIRED = "CARET_NOT_ACQUIRED"
    CLIPBOARD_LOCKED = "CLIPBOARD_LOCKED"
    DIB_PACK_FAILED = "DIB_PACK_FAILED"
    PASTE_INTERRUPTED = "PASTE_INTERRUPTED"
    SUBMIT_INTERRUPTED = "SUBMIT_INTERRUPTED"
    GENERATION_TIMEOUT = "GENERATION_TIMEOUT"
    COPY_BUTTON_NOT_FOUND = "COPY_BUTTON_NOT_FOUND"
    HARVEST_TIMEOUT = "HARVEST_TIMEOUT"
    TAGS_MISSING = "TAGS_MISSING"
    TAGS_DUPLICATED = "TAGS_DUPLICATED"
    NONCE_MISMATCH = "NONCE_MISMATCH"
    PAYLOAD_INVALID = "PAYLOAD_INVALID"
    PAYLOAD_OVERSIZE = "PAYLOAD_OVERSIZE"
    INTERRUPTED = "INTERRUPTED"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


# ---------------------------------------------------------------------------
# Request & Semantic Domain Schemas (§8.1 Compliant)
# ---------------------------------------------------------------------------

class ParasiteRequest(BaseModel):
    """Structured invocation payload delivered to ParasiteSkill."""

    phase: ParasitePhase
    user_goal: str
    trigger: Optional[RecoveryTrigger] = None
    recent_history: str = ""
    active_plan_context: str = ""
    active_window_label: Optional[str] = None
    open_windows: List[str] = Field(default_factory=list)
    available_programs: List[str] = Field(default_factory=list)
    include_screenshot: bool = True
    trace_payload: Optional[str] = None


class ParasitePlanStep(BaseModel):
    """Semantic-only strategic plan step returned by Gemini inside <parasite_plan>."""

    model_config = ConfigDict(extra="forbid")

    intent: StepIntent
    description: str = Field(min_length=1, max_length=300)
    target_description: Optional[str] = Field(default=None, max_length=160)
    tool_route: Literal["GUI", "CLI", "ADVISOR"] = "GUI"
    success_criteria: str = Field(min_length=1, max_length=200)
    contingency: Optional[str] = Field(default=None, max_length=200)
    action: Optional[StepDirective] = None

    @field_validator("intent", mode="before")
    @classmethod
    def _normalize_intent_alias(cls, v: Any) -> Any:
        if not isinstance(v, str):
            return v
        norm = v.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "LAUNCH": "LAUNCH_OR_ACTIVATE",
            "OPEN": "LAUNCH_OR_ACTIVATE",
            "OPEN_APP": "LAUNCH_OR_ACTIVATE",
            "ACTIVATE": "LAUNCH_OR_ACTIVATE",
            "START": "LAUNCH_OR_ACTIVATE",
            "CLICK": "NAVIGATE",
            "DOUBLE_CLICK": "NAVIGATE",
            "RIGHT_CLICK": "NAVIGATE",
            "HOTKEY": "NAVIGATE",
            "KEY_PRESS": "NAVIGATE",
            "PRESS": "NAVIGATE",
            "SCROLL": "NAVIGATE",
            "SELECT": "NAVIGATE",
            "FOCUS": "NAVIGATE",
            "TYPE": "INPUT_DATA",
            "TYPE_TEXT": "INPUT_DATA",
            "INPUT": "INPUT_DATA",
            "WRITE": "INPUT_DATA",
            "ENTER_TEXT": "INPUT_DATA",
            "PASTE": "INPUT_DATA",
            "SAVE": "INPUT_DATA",
            "VERIFY": "VERIFY_STATE",
            "CHECK": "VERIFY_STATE",
            "WAIT": "VERIFY_STATE",
            "INSPECT": "VERIFY_STATE",
            "CLOSE": "DISMISS_DIALOG",
            "DISMISS": "DISMISS_DIALOG",
            "CANCEL": "DISMISS_DIALOG",
            "DONE": "COMPLETE_GOAL",
            "FINISH": "COMPLETE_GOAL",
            "COMPLETE": "COMPLETE_GOAL",
        }
        return aliases.get(norm, norm)

    @field_validator("description", "target_description", "success_criteria", "contingency")
    @classmethod
    def _reject_coordinates(cls, v: Optional[str], info: Any) -> Optional[str]:
        return assert_no_numeric_coordinates(v, info.field_name)


class ParasitePlan(BaseModel):
    """Multi-step strategic plan emitted by Gemini inside <parasite_plan>."""

    model_config = ConfigDict(extra="forbid")

    selected_program: Optional[str] = Field(default=None, max_length=120)
    rationale: str = Field(min_length=1, max_length=800)
    steps: List[ParasitePlanStep] = Field(min_length=1, max_length=15)

    @field_validator("selected_program", "rationale")
    @classmethod
    def _reject_coordinates(cls, v: Optional[str], info: Any) -> Optional[str]:
        return assert_no_numeric_coordinates(v, info.field_name)

    def to_living_plan(self, user_goal: str) -> LivingPlan:
        """Compiles validated Gemini plan into an executable LivingPlan."""
        strategy = (
            f"[Selected: {self.selected_program}] {self.rationale}"
            if self.selected_program
            else self.rationale
        )
        plan_steps: List[PlanStep] = []
        for idx, step in enumerate(self.steps, start=1):
            plan_steps.append(
                PlanStep(
                    step_id=idx,
                    intent=step.intent,
                    description=strip_control_chars(step.description),
                    target_description=(
                        strip_control_chars(step.target_description)
                        if step.target_description is not None
                        else None
                    ),
                    success_criteria=strip_control_chars(step.success_criteria),
                    rationale=strategy[:240],
                    status=StepStatus.IN_PROGRESS if idx == 1 else StepStatus.PENDING,
                    contingency=(
                        strip_control_chars(step.contingency)
                        if step.contingency is not None
                        else None
                    ),
                    tool_route=step.tool_route,
                    directive=step.action,
                )
            )
        return LivingPlan(
            user_goal=strip_control_chars(user_goal),
            overall_strategy=strip_control_chars(strategy),
            steps=plan_steps,
            current_step_id=1,
            consulted_gemini=True,
        )


class ParasiteAction(BaseModel):
    """Semantic-only immediate contingency action; UI-TARS grounds pixels locally."""

    model_config = ConfigDict(extra="forbid")

    verb: Literal[
        "CLICK",
        "DOUBLE_CLICK",
        "RIGHT_CLICK",
        "TYPE",
        "HOTKEY",
        "SCROLL",
        "WAIT",
    ]
    target_description: Optional[str] = Field(default=None, max_length=160)
    text: Optional[str] = Field(default=None, max_length=500)
    keys: Optional[List[str]] = Field(default=None, max_length=4)
    scroll_direction: Optional[Literal["up", "down"]] = None

    @field_validator("target_description", "text")
    @classmethod
    def _reject_string_coords(cls, v: Optional[str], info: Any) -> Optional[str]:
        return assert_no_numeric_coordinates(v, info.field_name)

    @field_validator("keys")
    @classmethod
    def _clean_keys(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return [assert_no_numeric_coordinates(k, "keys") or "" for k in v if k]

    @model_validator(mode="after")
    def _validate_verb_shape(self) -> "ParasiteAction":
        if self.verb in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK") and not (
            self.target_description and self.target_description.strip()
        ):
            raise ValueError(f"{self.verb} requires a non-empty target_description.")
        if self.verb == "TYPE" and self.text is None:
            raise ValueError("TYPE requires non-null text.")
        if self.verb == "HOTKEY" and not self.keys:
            raise ValueError("HOTKEY requires non-empty keys list.")
        return self

    def to_contingency_step(self, step_id: int) -> PlanStep:
        """Converts semantic ParasiteAction into a LivingPlan contingency PlanStep."""
        if self.verb == "TYPE":
            desc = f"TYPE into target: {self.target_description or 'focused input'} -> '{self.text}'"
            intent = StepIntent.INPUT_DATA
        elif self.verb == "HOTKEY":
            chord = "+".join(self.keys or [])
            desc = f"HOTKEY press: {chord}"
            intent = StepIntent.NAVIGATE
        elif self.verb == "SCROLL":
            desc = f"SCROLL {self.scroll_direction or 'down'} on {self.target_description or 'active view'}"
            intent = StepIntent.NAVIGATE
        elif self.verb == "WAIT":
            desc = f"WAIT for UI state settle ({self.target_description or 'active screen'})"
            intent = StepIntent.VERIFY_STATE
        else:
            desc = f"{self.verb} on control: {self.target_description}"
            intent = StepIntent.NAVIGATE

        directive = StepDirective(
            verb=self.verb,
            text=strip_control_chars(self.text) if self.text is not None else None,
            keys=[strip_control_chars(k) for k in self.keys] if self.keys else None,
            scroll_direction=self.scroll_direction,
        )

        return PlanStep(
            step_id=step_id,
            intent=intent,
            description=strip_control_chars(desc)[:300],
            target_description=(
                strip_control_chars(self.target_description)[:160]
                if self.target_description
                else None
            ),
            success_criteria="Contributed recovery action shifts desktop UI cleanly.",
            rationale="ParasiteSkill semantic recovery step (grounded locally by UI-TARS).",
            status=StepStatus.IN_PROGRESS,
            tool_route="GUI",
            directive=directive,
        )


class ParsedParasiteResponse(BaseModel):
    """Validated outputs isolated from nonce-bound response blocks."""

    plan: Optional[ParasitePlan] = None
    action: Optional[ParasiteAction] = None
    skill_markdown: Optional[str] = None
    parsed_skill: Optional[Any] = None


# ---------------------------------------------------------------------------
# Strict Tag Parser
# ---------------------------------------------------------------------------

_TAG_BLOCK_RE = re.compile(
    r"<(?P<tag>parasite_plan|parasite_action|parasite_skill)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.DOTALL,
)
_OPEN_OR_UNCLOSED_TAG_RE = re.compile(
    r"<parasite_(?:plan|action|skill)\b",
    re.IGNORECASE,
)
_NONCE_ATTR_RE = re.compile(r"""nonce\s*=\s*["'](?P<nonce>[A-Za-z0-9_-]+)["']""")
_CODE_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_optional_code_fence(text: str) -> str:
    stripped = text.strip()
    m = _CODE_FENCE_RE.match(stripped)
    if m:
        return m.group(1).strip()
    return stripped


def parse_response(
    raw: str,
    nonce: str,
    phase: ParasitePhase,
    max_response_chars: int = 32000,
) -> Union[ParsedParasiteResponse, ParasiteFailure]:
    """
    Isolates strictly nonce-matched <parasite_*> blocks, discards all outer filler,
    rejects missing/duplicate/nested/poisoned blocks, and validates Pydantic schemas.
    """
    if not isinstance(raw, str) or not nonce:
        return ParasiteFailure.PAYLOAD_INVALID
    if len(raw) > max_response_chars:
        return ParasiteFailure.PAYLOAD_OVERSIZE

    matches = list(_TAG_BLOCK_RE.finditer(raw))
    if not matches:
        # Distinguish unclosed/partial tag vs totally absent tag
        if _OPEN_OR_UNCLOSED_TAG_RE.search(raw):
            return ParasiteFailure.PAYLOAD_INVALID
        return ParasiteFailure.TAGS_MISSING

    grouped: dict[str, List[Tuple[str, str]]] = {
        "parasite_plan": [],
        "parasite_action": [],
        "parasite_skill": [],
    }
    for m in matches:
        tag = m.group("tag")
        attrs = m.group("attrs") or ""
        body = m.group("body") or ""

        # Reject nested parasite tags anywhere inside block body
        if _OPEN_OR_UNCLOSED_TAG_RE.search(body):
            return ParasiteFailure.PAYLOAD_INVALID

        nonce_match = _NONCE_ATTR_RE.search(attrs)
        if not nonce_match:
            return ParasiteFailure.NONCE_MISMATCH
        found_nonce = nonce_match.group("nonce")
        if not hmac.compare_digest(found_nonce, nonce):
            return ParasiteFailure.NONCE_MISMATCH

        grouped[tag].append((found_nonce, body))

    if phase == ParasitePhase.SKILL_COAUTHOR:
        skill_blocks = grouped["parasite_skill"]
        if len(skill_blocks) == 0:
            return ParasiteFailure.TAGS_MISSING
        if len(skill_blocks) > 1:
            return ParasiteFailure.TAGS_DUPLICATED

        skill_md = _strip_optional_code_fence(skill_blocks[0][1])
        try:
            from parasite_ai.mind.skills import parse_skill_md

            skill_def = parse_skill_md(skill_md)
        except Exception:
            return ParasiteFailure.PAYLOAD_INVALID

        return ParsedParasiteResponse(skill_markdown=skill_md, parsed_skill=skill_def)

    # Planning & Recovery phases
    plan_blocks = grouped["parasite_plan"]
    action_blocks = grouped["parasite_action"]

    if len(plan_blocks) == 0:
        return ParasiteFailure.TAGS_MISSING
    if len(plan_blocks) > 1 or len(action_blocks) > 1:
        return ParasiteFailure.TAGS_DUPLICATED

    def _loads_json_with_winpath_fallback(raw_json: str) -> Any:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            def _escape_drive_path(match: re.Match[str]) -> str:
                return re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', match.group(0))

            repaired = re.sub(r'[A-Za-z]:\\[^"\r\n]*', _escape_drive_path, raw_json)
            repaired = re.sub(r'(?<!\\)\\(?![\\"/bfnrtu])', r'\\\\', repaired)
            return json.loads(repaired)

    def _sanitize_markdown_urls(obj: Any) -> Any:
        if isinstance(obj, str):
            return re.sub(r"\[[^\]]+\]\((https?://[^)\s]+)\)", r"\1", obj)
        if isinstance(obj, list):
            return [_sanitize_markdown_urls(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _sanitize_markdown_urls(v) for k, v in obj.items()}
        return obj

    plan_text = _strip_optional_code_fence(plan_blocks[0][1])
    try:
        plan_obj = _loads_json_with_winpath_fallback(plan_text)
        if not isinstance(plan_obj, dict):
            return ParasiteFailure.PAYLOAD_INVALID
        plan_obj = _sanitize_markdown_urls(plan_obj)
        plan = ParasitePlan(**plan_obj)
    except Exception:
        return ParasiteFailure.PAYLOAD_INVALID

    action: Optional[ParasiteAction] = None
    if phase == ParasitePhase.REACTIVE_RECOVERY and len(action_blocks) == 1:
        action_text = _strip_optional_code_fence(action_blocks[0][1])
        try:
            action_obj = _loads_json_with_winpath_fallback(action_text)
            if not isinstance(action_obj, dict):
                return ParasiteFailure.PAYLOAD_INVALID
            action_obj = _sanitize_markdown_urls(action_obj)
            action = ParasiteAction(**action_obj)
        except Exception:
            return ParasiteFailure.PAYLOAD_INVALID

    return ParsedParasiteResponse(plan=plan, action=action)


# ---------------------------------------------------------------------------
# Symbolic Prompt Builders (§8.3 Zero Numerical Anchoring)
# ---------------------------------------------------------------------------

def _sanitize_list(items: List[str], limit: int) -> str:
    if not items:
        return "<none>"
    cleaned = [
        strip_control_chars(sanitize_consultation_prompt(str(x))).strip()
        for x in items[:limit]
        if str(x).strip()
    ]
    return ", ".join(cleaned) if cleaned else "<none>"


def build_parasite_prompt(request: ParasiteRequest, nonce: str) -> str:
    """
    Constructs the sanitized prompt delivered to Gemini Web.
    Strictly enforces symbolic placeholders (§8.3) with zero screen coordinates.
    """
    goal = strip_control_chars(sanitize_consultation_prompt(request.user_goal))
    window_label = strip_control_chars(
        sanitize_consultation_prompt(request.active_window_label or "<unknown>")
    )
    history = strip_control_chars(
        sanitize_consultation_prompt(request.recent_history or "<none>")
    )
    plan_ctx = strip_control_chars(
        sanitize_consultation_prompt(request.active_plan_context or "<none>")
    )
    open_wins = _sanitize_list(request.open_windows, 15)
    avail_progs = _sanitize_list(request.available_programs, 40)

    if request.phase == ParasitePhase.SKILL_COAUTHOR:
        trace = strip_control_chars(
            sanitize_consultation_prompt(request.trace_payload or "<empty>")
        )
        return (
            "You are ParasiteAI's skill co-author. Generalize the sanitized execution trace below "
            "into a reusable semantic SKILL.md playbook.\n"
            "STRICT RULES:\n"
            "- Output ONLY inside one <parasite_skill nonce=\"{nonce}\">...</parasite_skill> block.\n"
            "- Write valid YAML frontmatter followed by Markdown sections (Intent, Procedure, Recovery Notes).\n"
            "- NEVER include screen coordinates, x/y pixels, or bounding boxes.\n"
            "- Set type: workflow and use semantic target descriptions or standard shortcuts.\n\n"
            "User Goal: {goal}\n"
            "Sanitized Execution Trace:\n{trace}\n\n"
            "Wrap your response strictly as:\n"
            "<parasite_skill nonce=\"{nonce}\">\n"
            "---\n"
            "schema_version: 1\n"
            "id: <skill_id>\n"
            "name: <skill_name>\n"
            "version: 1\n"
            "type: workflow\n"
            "draft: true\n"
            "state: CANDIDATE\n"
            "provenance: co_authored\n"
            "description: <summary>\n"
            "trigger:\n"
            "  goal_patterns: [\"<regex>\"]\n"
            "  keywords: [\"<keyword>\"]\n"
            "  process_names: [\"<process>\"]\n"
            "  min_score: 0.6\n"
            "preconditions:\n"
            "  container_process: <process>\n"
            "  requires_launch: true\n"
            "actions:\n"
            "  steps:\n"
            "    - intent: LAUNCH_OR_ACTIVATE\n"
            "      verb: HOTKEY\n"
            "      target_description: \"<control>\"\n"
            "      keys: [\"<key>\", \"<key>\"]\n"
            "      success_criteria: \"<condition>\"\n"
            "postconditions:\n"
            "  success_criteria: \"<condition>\"\n"
            "---\n"
            "# <skill_name>\n\n"
            "## Intent\n<purpose>\n\n"
            "## Procedure\n<steps>\n\n"
            "## Recovery Notes\n<notes>\n"
            "</parasite_skill>"
        ).format(nonce=nonce, goal=goal, trace=trace)

    schema_hint = (
        "<parasite_plan nonce=\"{nonce}\">\n"
        "{{\n"
        "  \"selected_program\": \"<program>\",\n"
        "  \"rationale\": \"<comparison_and_strategy>\",\n"
        "  \"steps\": [\n"
        "    {{\n"
        "      \"intent\": \"LAUNCH_OR_ACTIVATE\",\n"
        "      \"description\": \"<step_instruction>\",\n"
        "      \"target_description\": \"<control>\",\n"
        "      \"tool_route\": \"GUI\",\n"
        "      \"success_criteria\": \"<verifiable_state>\",\n"
        "      \"contingency\": \"<fallback_instruction>\",\n"
        "      \"action\": {{\n"
        "        \"verb\": \"<CLICK|DOUBLE_CLICK|RIGHT_CLICK|TYPE|HOTKEY|SCROLL|WAIT>\",\n"
        "        \"text\": \"<text>\",\n"
        "        \"keys\": [\"<key>\"],\n"
        "        \"submit\": false\n"
        "      }}\n"
        "    }}\n"
        "  ]\n"
        "}}\n"
        "</parasite_plan>"
    ).format(nonce=nonce)

    if request.phase == ParasitePhase.PROACTIVE_PLAN:
        return (
            "You are ParasiteAI's strategic planner assisting a local desktop GUI agent.\n"
            "Analyze the attached desktop screenshot together with the verified open windows "
            "and installed programs on this Windows PC.\n"
            "When multiple installed programs could achieve the goal, compare options in rationale, "
            "choose the most reliable option in selected_program (preferring already-open or native tools), "
            "and decompose the workflow into atomic, visually verifiable steps (max 15).\n"
            "STRICT RULES:\n"
            "- Output JSON inside ONE <parasite_plan nonce=\"{nonce}\">...</parasite_plan> tag.\n"
            "- NEVER emit screen coordinates, pixel offsets, or bounding boxes; local vision grounds targets.\n"
            "- Put every literal string to type and every key chord in action, never only in prose.\n"
            "- Valid intent values: LAUNCH_OR_ACTIVATE, NAVIGATE, INPUT_DATA, SELECT_OPTION, VERIFY_STATE, DISMISS_DIALOG, CONCLUDE.\n"
            "- Valid tool_route values: GUI.\n\n"
            "User Goal: {goal}\n"
            "Active Window: {win}\n"
            "Visible Open Windows: {open_wins}\n"
            "Discovered Installed Programs: {avail_progs}\n\n"
            "Required output format:\n{schema}"
        ).format(
            nonce=nonce,
            goal=goal,
            win=window_label,
            open_wins=open_wins,
            avail_progs=avail_progs,
            schema=schema_hint,
        )

    # REACTIVE_RECOVERY
    trigger_name = request.trigger.value if request.trigger else RecoveryTrigger.CONSECUTIVE_STRIKES.value
    action_hint = (
        "<parasite_action nonce=\"{nonce}\">\n"
        "{{\n"
        "  \"verb\": \"<CLICK|DOUBLE_CLICK|RIGHT_CLICK|TYPE|HOTKEY|SCROLL|WAIT>\",\n"
        "  \"target_description\": \"<control>\",\n"
        "  \"text\": \"<text>\",\n"
        "  \"keys\": [\"<key>\", \"<key>\"],\n"
        "  \"scroll_direction\": \"down\"\n"
        "}}\n"
        "</parasite_action>"
    ).format(nonce=nonce)

    return (
        "You are ParasiteAI's in-flight tactical recovery advisor.\n"
        "The local vision agent is stalled ({trigger}) while pursuing the user goal.\n"
        "Inspect the attached desktop screenshot, recent execution history, and current plan, "
        "diagnose the blocker (wrong focus, modal dialog, menu depth, shortcut needed), and emit "
        "a repaired strategic plan PLUS an optional immediate semantic recovery action.\n"
        "STRICT RULES:\n"
        "- Output ONE <parasite_plan nonce=\"{nonce}\">...</parasite_plan> JSON block.\n"
        "- Optionally output ONE <parasite_action nonce=\"{nonce}\">...</parasite_action> JSON block.\n"
        "- NEVER emit pixel coordinates or bounding boxes anywhere; describe UI targets semantically.\n"
        "- Valid verbs: CLICK, DOUBLE_CLICK, RIGHT_CLICK, TYPE, HOTKEY, SCROLL, WAIT.\n\n"
        "User Goal: {goal}\n"
        "Recovery Trigger: {trigger}\n"
        "Active Window: {win}\n"
        "Visible Open Windows: {open_wins}\n"
        "Discovered Installed Programs: {avail_progs}\n"
        "Recent Action History:\n{history}\n"
        "Current Plan Context:\n{plan_ctx}\n\n"
        "Required output format:\n{schema}\n\nOptional immediate semantic action:\n{action_hint}"
    ).format(
        nonce=nonce,
        trigger=trigger_name,
        goal=goal,
        win=window_label,
        open_wins=open_wins,
        avail_progs=avail_progs,
        history=history,
        plan_ctx=plan_ctx,
        schema=schema_hint,
        action_hint=action_hint,
    )
