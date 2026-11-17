"""
parasite_ai/mind/skills.py - Universal Skill Engine, Visual Drift Quarantine & Autonomous Learner.

Supports human-readable SKILL.md playbooks (YAML frontmatter + Markdown) across two
strictly separated types:
  - type: workflow (semantic-only, compiled to LivingPlan, zero coordinates)
  - type: reflex_micro_skill (§7.6 exemption: client-relative coordinates permitted
    IFF gated by exact window dimensions, sub-5 ms pHash anchor, and fail-closed
    abort to UIA/VLM on any mismatch).

Provides pHash visual drift detection, 30-day TTL decay, quarantined archival
(moves to _quarantine/, never deletes), deterministic trace recording, and
Gemini-coauthored draft skills gated by Discord/operator approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Tuple
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from parasite_ai.config import SkillsConfig
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodeReceipt,
    INTERACTIVE_ACTION_TYPES,
    StepRecord,
    compute_phash,
    hamming_distance,
)
from parasite_ai.mind.parasite_protocol import (
    ParasiteFailure,
    ParasitePhase,
    ParasiteRequest,
    assert_no_numeric_coordinates,
    strip_control_chars,
)
from parasite_ai.mind.offloader import sanitize_consultation_prompt
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepDirective, StepIntent, StepStatus
from parasite_ai.safety.content_scanner import sanitize_or_reject

logger = logging.getLogger(__name__)

_PARAM_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_PARAM_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,31}$")
_PHASH_HEX_RE = re.compile(r"^[0-9a-f]{16}$")
_FRONTMATTER_RE = re.compile(r"^\s*---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n(.*))?$", re.DOTALL)
_FREEFORM_PARAM_NAMES = frozenset({"text", "note", "content", "body", "message"})
_GENERATIVE_CUE_RE = re.compile(
    r"\b(?:short|sentence|greeting|poem|story|essay|summary|summarize|overview|presentation|slide|explain)\b"
    r"|\babout\s+yourself\b"
    r"|\bdraft\s+an?\b",
    re.IGNORECASE,
)


def utcnow() -> datetime:
    """Returns timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Enumerations & Schemas
# ---------------------------------------------------------------------------

class SkillType(str, Enum):
    WORKFLOW = "workflow"
    REFLEX_MICRO_SKILL = "reflex_micro_skill"


class SkillState(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"


class SkillProvenance(str, Enum):
    AUTHORED = "authored"
    LEARNED = "learned"
    CO_AUTHORED = "co_authored"
    FARMED = "farmed"


class SkillTrigger(BaseModel):
    """Matching rules evaluated deterministically without model calls."""

    goal_patterns: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    process_names: List[str] = Field(default_factory=list)
    min_score: float = Field(default=0.6, ge=0.0, le=1.0)

    @field_validator("goal_patterns")
    @classmethod
    def _validate_regexes(cls, patterns: List[str]) -> List[str]:
        for pat in patterns:
            if not isinstance(pat, str) or len(pat) > 256:
                raise ValueError(f"Goal pattern exceeds max length (256) or is invalid: {pat!r}")
            try:
                re.compile(pat)
            except re.error as exc:
                raise ValueError(f"Invalid goal_pattern regex {pat!r}: {exc}") from exc
        return patterns


class SkillParameter(BaseModel):
    """Named slot extracted from trigger regex groups."""

    name: str
    description: str = ""
    required: bool = True

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not _PARAM_NAME_RE.match(v or ""):
            raise ValueError(f"Invalid parameter name '{v}'.")
        return v


class SkillPreconditions(BaseModel):
    """OS window/process preconditions required before executing a skill."""

    container_process: Optional[str] = None
    container_title_regex: Optional[str] = None
    requires_launch: bool = False
    launch_query: Optional[str] = None
    launch_method: Literal["start_search", "win_r"] = "start_search"

    @field_validator("container_title_regex")
    @classmethod
    def _validate_title_regex(cls, pat: Optional[str]) -> Optional[str]:
        if pat is None:
            return None
        if len(pat) > 256:
            raise ValueError("container_title_regex exceeds max length (256).")
        try:
            re.compile(pat)
        except re.error as exc:
            raise ValueError(f"Invalid container_title_regex {pat!r}: {exc}") from exc
        return pat


class ReflexSafetyGate(BaseModel):
    """Mandatory §7.6 gate schema when type == reflex_micro_skill."""

    model_config = ConfigDict(extra="forbid")

    expected_window_size: Tuple[int, int]
    relative_origin: Literal["client_top_left", "window_top_left"] = "client_top_left"
    phash_anchor: str
    phash_max_hamming: int = Field(default=6, ge=0, le=16)
    fail_closed_fallback: Literal["uia_vlm"] = "uia_vlm"

    @field_validator("expected_window_size")
    @classmethod
    def _validate_window_size(cls, size: Tuple[int, int]) -> Tuple[int, int]:
        w, h = size
        if w <= 0 or h <= 0:
            raise ValueError(f"expected_window_size must be positive, got {size}.")
        return (int(w), int(h))

    @field_validator("phash_anchor")
    @classmethod
    def _validate_phash(cls, value: str) -> str:
        if not _PHASH_HEX_RE.match((value or "").lower()):
            raise ValueError(f"phash_anchor must be 16 lowercase hex chars, got {value!r}.")
        return value.lower()


class SkillActionStep(BaseModel):
    """Single action step inside a SKILL.md workflow or reflex micro-skill."""

    model_config = ConfigDict(extra="forbid")

    intent: StepIntent
    verb: Literal[
        "CLICK",
        "DOUBLE_CLICK",
        "RIGHT_CLICK",
        "TYPE",
        "HOTKEY",
        "SCROLL",
        "WAIT",
    ]
    target_description: Optional[str] = None
    relative_coordinates: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    submit: bool = False
    clear_first: bool = False
    wait_ms: int = Field(default=0, ge=0, le=10000)
    success_criteria: str

    @field_validator("target_description", "text", "success_criteria")
    @classmethod
    def _no_coords_in_strings(cls, v: Optional[str], info: Any) -> Optional[str]:
        return assert_no_numeric_coordinates(v, info.field_name)

    @field_validator("keys")
    @classmethod
    def _no_coords_in_keys(cls, keys: Optional[List[str]]) -> Optional[List[str]]:
        if keys is None:
            return None
        return [assert_no_numeric_coordinates(k, "keys") or "" for k in keys if k]

    @model_validator(mode="after")
    def _validate_verb_shape(self) -> "SkillActionStep":
        if self.verb == "HOTKEY" and not self.keys:
            raise ValueError("HOTKEY step requires non-empty 'keys'.")
        if self.verb == "TYPE" and self.text is None:
            raise ValueError("TYPE step requires non-null 'text'.")
        if self.verb in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            has_desc = bool(self.target_description and self.target_description.strip())
            has_rel = self.relative_coordinates is not None
            if not has_desc and not has_rel:
                raise ValueError(
                    f"{self.verb} step requires 'target_description' (or 'relative_coordinates' on reflex_micro_skill)."
                )
        return self


class SkillActions(BaseModel):
    steps: List[SkillActionStep] = Field(min_length=1, max_length=25)


class SkillPostconditions(BaseModel):
    success_criteria: str
    expected_process: Optional[str] = None

    @field_validator("success_criteria")
    @classmethod
    def _no_coords_in_post(cls, v: str) -> str:
        return assert_no_numeric_coordinates(v, "postconditions.success_criteria") or ""


class VisualAnchor(BaseModel):
    phash: str
    window_size: Tuple[int, int]
    captured_at: datetime

    @field_validator("phash")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        if not _PHASH_HEX_RE.match((value or "").lower()):
            raise ValueError(f"VisualAnchor phash must be 16 hex chars, got {value!r}.")
        return value.lower()

    @field_validator("window_size")
    @classmethod
    def _validate_dim(cls, size: Tuple[int, int]) -> Tuple[int, int]:
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError(f"VisualAnchor window_size must be positive, got {size}.")
        return (int(size[0]), int(size[1]))

    @field_validator("captured_at")
    @classmethod
    def _normalize_dt(cls, dt: datetime) -> datetime:
        return _ensure_utc(dt)


class InvalidationCriteria(BaseModel):
    ttl_days: int = Field(default=30, ge=1, le=365)
    phash_max_hamming: int = Field(default=10, ge=0, le=32)
    max_consecutive_failures: int = Field(default=2, ge=1, le=10)
    visual_anchors: List[VisualAnchor] = Field(default_factory=list, max_length=3)


class SkillStats(BaseModel):
    created_at: datetime = Field(default_factory=utcnow)
    last_verified_at: datetime = Field(default_factory=utcnow)
    last_used_at: Optional[datetime] = None
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)

    @field_validator("created_at", "last_verified_at", "last_used_at")
    @classmethod
    def _norm_dt(cls, dt: Optional[datetime]) -> Optional[datetime]:
        return _ensure_utc(dt) if dt is not None else None


class SkillDefinition(BaseModel):
    """Canonical SKILL.md schema with strict §7.6 and §8 invariants."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str
    name: str
    version: int = Field(default=1, ge=1)
    type: SkillType = SkillType.WORKFLOW
    draft: bool = False
    state: SkillState = SkillState.CANDIDATE
    provenance: SkillProvenance = SkillProvenance.AUTHORED
    description: str
    trigger: SkillTrigger
    parameters: List[SkillParameter] = Field(default_factory=list)
    preconditions: SkillPreconditions
    reflex_gate: Optional[ReflexSafetyGate] = None
    actions: SkillActions
    postconditions: SkillPostconditions
    invalidation: InvalidationCriteria = Field(default_factory=InvalidationCriteria)
    stats: SkillStats = Field(default_factory=SkillStats)
    body: str = ""
    source_path: Optional[Path] = Field(default=None, exclude=True)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _SKILL_ID_RE.match(value or ""):
            raise ValueError(
                f"Skill id '{value}' must match ^[a-z0-9][a-z0-9_-]{{2,63}}$."
            )
        return value

    @field_validator("name", "description", "body")
    @classmethod
    def _no_coords_in_prose(cls, v: str, info: Any) -> str:
        return assert_no_numeric_coordinates(v, info.field_name) or ""

    @model_validator(mode="after")
    def _enforce_skill_invariants(self) -> "SkillDefinition":
        # 1. §7.6 vs §8.1 coordinate gate policy
        if self.type == SkillType.WORKFLOW:
            if self.reflex_gate is not None:
                raise ValueError("type='workflow' forbids 'reflex_gate'.")
            for idx, step in enumerate(self.actions.steps, start=1):
                if step.relative_coordinates is not None:
                    raise ValueError(
                        f"type='workflow' forbids 'relative_coordinates' (step {idx})."
                    )
        else:
            # type == REFLEX_MICRO_SKILL (§7.6 Exemption)
            if self.reflex_gate is None:
                raise ValueError("type='reflex_micro_skill' requires 'reflex_gate'.")
            if not (
                self.preconditions.container_process
                and self.preconditions.container_process.strip()
            ):
                raise ValueError(
                    "type='reflex_micro_skill' requires 'preconditions.container_process'."
                )
            max_w, max_h = self.reflex_gate.expected_window_size
            rel_steps = 0
            for idx, step in enumerate(self.actions.steps, start=1):
                if step.relative_coordinates is not None:
                    rel_steps += 1
                    rx, ry = step.relative_coordinates
                    if not (0 <= rx < max_w and 0 <= ry < max_h):
                        raise ValueError(
                            f"Step {idx} relative_coordinates {(rx, ry)} out of bounds for expected_window_size {(max_w, max_h)}."
                        )
            if rel_steps == 0:
                raise ValueError(
                    "type='reflex_micro_skill' requires at least one step with relative_coordinates."
                )

        # 2. Parameter placeholders must all be declared
        declared = {p.name for p in self.parameters}
        for idx, step in enumerate(self.actions.steps, start=1):
            for field_val in (step.text, step.target_description, step.success_criteria):
                if not field_val:
                    continue
                for ph in _PARAM_PLACEHOLDER_RE.findall(field_val):
                    if ph not in declared:
                        raise ValueError(
                            f"Undeclared parameter '{{{{{ph}}}}}' referenced in step {idx}."
                        )

        return self


# ---------------------------------------------------------------------------
# Frontmatter Codec
# ---------------------------------------------------------------------------

def parse_skill_md(text: str, source_path: Optional[Path] = None) -> SkillDefinition:
    """Parses YAML frontmatter (yaml.safe_load only) + Markdown body into SkillDefinition."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("SKILL.md text cannot be empty.")

    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("SKILL.md missing valid YAML frontmatter delimited by '---'.")

    raw_yaml, raw_body = m.group(1), (m.group(2) or "")
    loaded = yaml.safe_load(raw_yaml)
    if not isinstance(loaded, dict):
        raise ValueError("SKILL.md frontmatter must deserialize to a mapping.")
    if "body" in loaded:
        raise ValueError("'body' cannot appear inside YAML frontmatter.")

    return SkillDefinition(**loaded, body=raw_body.strip(), source_path=source_path)


def render_skill_md(skill: SkillDefinition) -> str:
    """Renders SkillDefinition with deterministic field order for byte-stable round-trips."""
    frontmatter = skill.model_dump(mode="json", exclude={"body", "source_path"})
    if skill.type == SkillType.WORKFLOW:
        frontmatter.pop("reflex_gate", None)
        for step in frontmatter.get("actions", {}).get("steps", []):
            step.pop("relative_coordinates", None)

    yaml_text = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
    ).rstrip()
    body = (skill.body or "").strip()
    if body:
        return f"---\n{yaml_text}\n---\n{body}\n"
    return f"---\n{yaml_text}\n---\n"


# ---------------------------------------------------------------------------
# Container Window Probe, Visual Drift & §7.6 Reflex Gate Resolver
# ---------------------------------------------------------------------------

@dataclass
class ContainerWindowSnapshot:
    """OS-verified container window metadata (never synthetic offsets)."""

    hwnd: int
    process_name: str
    title: str
    window_rect: Tuple[int, int, int, int]   # (left, top, right, bottom)
    client_origin: Tuple[int, int]           # screen (x, y) of client (0, 0)
    client_size: Tuple[int, int]             # (width, height) of client area


class IContainerWindowProbe(Protocol):
    """OS interface locating verified container windows for drift and §7.6 gates."""

    def get_active_container(
        self, process_name: str, title_regex: Optional[str] = None
    ) -> Optional[ContainerWindowSnapshot]: ...

    def get_window_by_hwnd(self, hwnd: int) -> Optional[ContainerWindowSnapshot]: ...


class Win32ContainerWindowProbe:
    """Queries live Win32 window/client bounds strictly through OS APIs."""

    def _snapshot_hwnd(self, hwnd: int) -> Optional[ContainerWindowSnapshot]:
        try:
            import ctypes
            from ctypes import wintypes
            from parasite_ai.mind.verifier import get_live_windows

            matches = [w for w in get_live_windows(include_empty_titles=True) if w["hwnd"] == hwnd]
            if not matches:
                return None
            info = matches[0]
            user32 = ctypes.windll.user32
            c_rect = wintypes.RECT()
            origin_pt = wintypes.POINT(0, 0)
            if user32.GetClientRect(hwnd, ctypes.byref(c_rect)) and user32.ClientToScreen(
                hwnd, ctypes.byref(origin_pt)
            ):
                client_origin = (int(origin_pt.x), int(origin_pt.y))
                client_size = (
                    max(0, int(c_rect.right - c_rect.left)),
                    max(0, int(c_rect.bottom - c_rect.top)),
                )
            else:
                l, t, r, b = info["rect"]
                client_origin = (int(l), int(t))
                client_size = (max(0, r - l), max(0, b - t))

            return ContainerWindowSnapshot(
                hwnd=int(hwnd),
                process_name=info["process_name"],
                title=info["title"],
                window_rect=info["rect"],
                client_origin=client_origin,
                client_size=client_size,
            )
        except Exception as exc:
            logger.debug("Win32ContainerWindowProbe snapshot failed: %s", exc)
            return None

    def get_active_container(
        self, process_name: str, title_regex: Optional[str] = None
    ) -> Optional[ContainerWindowSnapshot]:
        try:
            import ctypes
            from parasite_ai.mind.verifier import get_live_windows

            target_proc = (process_name or "").lower().strip()
            fg_hwnd = int(ctypes.windll.user32.GetForegroundWindow() or 0)
            title_re = re.compile(title_regex, re.IGNORECASE) if title_regex else None

            candidates = get_live_windows(include_empty_titles=True)
            # Prefer foreground window if matching preconditions
            ordered = sorted(
                candidates,
                key=lambda w: (0 if int(w["hwnd"]) == fg_hwnd else 1),
            )
            for w in ordered:
                if w["is_minimized"]:
                    continue
                if target_proc and w["process_name"].lower() != target_proc:
                    continue
                if title_re and not title_re.search(w["title"] or ""):
                    continue
                return self._snapshot_hwnd(int(w["hwnd"]))
        except Exception as exc:
            logger.debug("Win32ContainerWindowProbe search failed: %s", exc)
        return None

    def get_window_by_hwnd(self, hwnd: int) -> Optional[ContainerWindowSnapshot]:
        return self._snapshot_hwnd(hwnd)


@dataclass
class FreshnessVerdict:
    state: SkillState
    expired: bool
    age_days: float


@dataclass
class DriftVerdict:
    checked: bool
    drifted: bool
    min_hamming: Optional[int] = None
    live_anchor: Optional[VisualAnchor] = None
    reason: str = ""


@dataclass
class ReflexDispatchResolution:
    """Result of the 4-gate §7.6 check on a reflex_micro_skill."""

    ok: bool
    action_plan: Optional[ActionPlan] = None
    target_hwnd: Optional[int] = None
    drifted: bool = False
    reason: str = ""
    fallback: Literal["uia_vlm"] = "uia_vlm"


def verify_and_resolve_reflex_skill(
    skill: SkillDefinition,
    window_probe: Optional[IContainerWindowProbe],
    capturer: Any,
    parameters: Optional[Dict[str, str]] = None,
) -> ReflexDispatchResolution:
    """
    Executes the mandatory §7.6 4-gate safety verification immediately prior to dispatching
    a reflex_micro_skill burst. Fails closed to UIA/VLM on any mismatch.
    """
    if skill.type != SkillType.REFLEX_MICRO_SKILL or skill.reflex_gate is None:
        return ReflexDispatchResolution(ok=False, reason="Not a gated reflex_micro_skill.")

    if window_probe is None or capturer is None:
        return ReflexDispatchResolution(ok=False, reason="Window probe or capturer unavailable.")

    gate = skill.reflex_gate
    proc = skill.preconditions.container_process or ""
    snap = window_probe.get_active_container(proc, skill.preconditions.container_title_regex)
    if snap is None:
        return ReflexDispatchResolution(
            ok=False, reason=f"Container window '{proc}' not active/found."
        )

    # Gate 2: Exact window/client dimension check
    if gate.relative_origin == "client_top_left":
        actual_size = snap.client_size
        origin_x, origin_y = snap.client_origin
        capture_rect = (
            origin_x,
            origin_y,
            actual_size[0],
            actual_size[1],
        )
    else:
        l, t, r, b = snap.window_rect
        actual_size = (max(0, r - l), max(0, b - t))
        origin_x, origin_y = l, t
        capture_rect = (l, t, actual_size[0], actual_size[1])

    if actual_size != gate.expected_window_size:
        return ReflexDispatchResolution(
            ok=False,
            reason=(
                f"Dimension mismatch for '{proc}': actual={actual_size} != expected={gate.expected_window_size}."
            ),
        )

    # Gate 1: Verify every relative coordinate remains strictly inside resolved bounds
    w, h = actual_size
    for idx, step in enumerate(skill.actions.steps, start=1):
        if step.relative_coordinates is not None:
            rx, ry = step.relative_coordinates
            if not (0 <= rx < w and 0 <= ry < h):
                return ReflexDispatchResolution(
                    ok=False,
                    reason=f"Step {idx} relative_coordinates {(rx, ry)} outside {(w, h)}.",
                )

    # Gate 3: Sub-5ms pHash visual anchor check
    try:
        frame = capturer.capture_rect(capture_rect)
        live_phash = compute_phash(frame)
    except Exception as exc:
        return ReflexDispatchResolution(ok=False, reason=f"Pre-dispatch capture failed: {exc}")

    dist = hamming_distance(live_phash, gate.phash_anchor)
    if dist > gate.phash_max_hamming:
        return ReflexDispatchResolution(
            ok=False,
            drifted=True,
            reason=(
                f"Reflex pHash anchor mismatch: hamming={dist} > threshold={gate.phash_max_hamming}."
            ),
        )

    # Gate 4: All checks pass -> translate client-relative coordinates to native desktop pixels
    params = parameters or {}
    burst_actions: List[ActionPlan] = []
    for step in skill.actions.steps:
        if step.verb in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK") and step.relative_coordinates is not None:
            rx, ry = step.relative_coordinates
            act_type = ActionType(step.verb)
            burst_actions.append(
                ActionPlan(
                    action=act_type,
                    coordinates=(origin_x + rx, origin_y + ry),
                    reasoning=f"Gated reflex skill '{skill.id}': {step.target_description or step.verb}",
                )
            )
        elif step.verb == "TYPE" and step.text is not None:
            rendered_text = _substitute_params(step.text, params)
            burst_actions.append(
                ActionPlan(
                    action=ActionType.TYPE,
                    text=rendered_text,
                    submit=bool(step.submit),
                    clear_first=bool(step.clear_first),
                    reasoning=f"Gated reflex skill '{skill.id}' TYPE",
                )
            )
        elif step.verb == "HOTKEY" and step.keys:
            burst_actions.append(
                ActionPlan(
                    action=ActionType.HOTKEY,
                    keys=list(step.keys),
                    reasoning=f"Gated reflex skill '{skill.id}' HOTKEY",
                )
            )
        elif step.verb == "WAIT":
            burst_actions.append(
                ActionPlan(
                    action=ActionType.WAIT,
                    wait_ms=step.wait_ms or 100,
                    reasoning=f"Gated reflex skill '{skill.id}' WAIT",
                )
            )

    if not burst_actions:
        return ReflexDispatchResolution(
            ok=False, reason="Reflex skill yielded zero dispatchable burst actions."
        )

    return ReflexDispatchResolution(
        ok=True,
        target_hwnd=snap.hwnd,
        action_plan=ActionPlan(
            action=ActionType.BURST,
            burst_actions=burst_actions,
            reasoning=f"§7.6 Gated reflex burst for skill '{skill.id}' (hamming={dist}/{gate.phash_max_hamming}).",
        ),
    )


# ---------------------------------------------------------------------------
# Skill Matching, Registry, Drift/TTL Lifecycle & LivingPlan Compilation
# ---------------------------------------------------------------------------

def _substitute_params(text: str, params: Dict[str, str]) -> str:
    return _PARAM_PLACEHOLDER_RE.sub(
        lambda m: str(params.get(m.group(1), m.group(0))),
        text,
    )


@dataclass
class SkillMatch:
    skill: SkillDefinition
    score: float
    parameters: Dict[str, str] = field(default_factory=dict)


@dataclass
class SkillLoadReport:
    loaded: int = 0
    skipped_drafts: int = 0
    decayed_to_stale: int = 0
    errors: List[str] = field(default_factory=list)


class SkillRegistry:
    """Loads, matches, drift-checks, decays, atomically persists, and quarantines SKILL.md."""

    def __init__(
        self,
        config: SkillsConfig,
        clock: Callable[[], datetime] = utcnow,
        window_probe: Optional[IContainerWindowProbe] = None,
        capturer: Any = None,
    ) -> None:
        self.config = config
        self._clock = clock
        self.window_probe = window_probe if window_probe is not None else Win32ContainerWindowProbe()
        self.capturer = capturer
        self._skills: Dict[str, SkillDefinition] = {}

    @property
    def skills(self) -> Dict[str, SkillDefinition]:
        return dict(self._skills)

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def load_all(self) -> SkillLoadReport:
        """Scans skills_dir, skipping '_' directories and malformed files cleanly."""
        report = SkillLoadReport()
        self._skills.clear()
        root = Path(self.config.skills_dir)
        if not root.exists():
            return report

        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            skill_file = child / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                skill = parse_skill_md(skill_file.read_text(encoding="utf-8"), source_path=skill_file)
                verdict = self.evaluate_freshness(skill, persist=True)
                if verdict.expired:
                    report.decayed_to_stale += 1
                if skill.draft:
                    report.skipped_drafts += 1
                self._skills[skill.id] = skill
                report.loaded += 1
            except Exception as exc:
                msg = f"Failed loading {skill_file}: {exc}"
                logger.warning(msg)
                report.errors.append(msg)

        return report

    def _score_skill(
        self,
        skill: SkillDefinition,
        goal: str,
        active_process: Optional[str],
    ) -> Optional[SkillMatch]:
        goal_str = goal or ""
        goal_tokens = set(re.findall(r"[a-z0-9_]+", goal_str.lower()))

        pattern_hit = 0.0
        extracted: Dict[str, str] = {}
        for pat in skill.trigger.goal_patterns:
            m = re.search(pat, goal_str, re.IGNORECASE)
            if m:
                pattern_hit = 1.0
                for k, v in m.groupdict().items():
                    if v is not None:
                        val = v.strip()
                        is_quoted = False
                        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                            is_quoted = True
                            val = val[1:-1]
                        else:
                            try:
                                start_idx, end_idx = m.span(k)
                            except IndexError:
                                start_idx, end_idx = -1, -1
                            if start_idx >= 0 and end_idx >= 0:
                                left_q = goal_str[:start_idx].rstrip()[-1:]
                                right_q = goal_str[end_idx:].lstrip()[:1]
                                if left_q in ("'", '"') and right_q == left_q:
                                    is_quoted = True
                        if k in _FREEFORM_PARAM_NAMES and not is_quoted and _GENERATIVE_CUE_RE.search(val):
                            return None
                        extracted[k] = val
                break

        kw_list = [k.lower().strip() for k in skill.trigger.keywords if k.strip()]
        if kw_list:
            matched_kw = sum(
                1
                for k in kw_list
                if (k in goal_str.lower() if " " in k else k in goal_tokens)
            )
            kw_overlap = matched_kw / len(kw_list)
        else:
            kw_overlap = 0.0

        proc_hit = 0.0
        if active_process and skill.trigger.process_names:
            proc_lower = active_process.lower().strip()
            if any(p.lower().strip() == proc_lower for p in skill.trigger.process_names):
                proc_hit = 1.0

        if skill.trigger.goal_patterns:
            score = 0.6 * pattern_hit + 0.3 * kw_overlap + 0.1 * proc_hit
        elif skill.trigger.process_names:
            score = 0.85 * kw_overlap + 0.15 * proc_hit
        else:
            score = kw_overlap

        if score < skill.trigger.min_score:
            return None

        if not skill.trigger.goal_patterns:
            skill_corpus_text = (
                f"{skill.id} {skill.name} {skill.description} {' '.join(kw_list)}"
            ).lower()
            skill_corpus_tokens = set(re.findall(r"[a-z0-9_]+", skill_corpus_text))
            goal_filenames = [
                fn
                for fn in re.findall(r"\b[a-z0-9_-]+\.[a-z0-9]{1,5}\b", goal_str.lower())
                if not fn.endswith(".exe")
            ]
            for fn in goal_filenames:
                stem = fn.split(".", 1)[0]
                if fn not in skill_corpus_text and stem not in skill_corpus_tokens:
                    return None
            primary_verbs = {
                "rename",
                "delete",
                "remove",
                "create",
                "copy",
                "move",
                "minimize",
                "close",
                "save",
            }
            if (goal_tokens & primary_verbs) - skill_corpus_tokens:
                return None

        # Validate required parameters were captured and are non-empty
        for param in skill.parameters:
            if param.required and not extracted.get(param.name, "").strip():
                return None

        return SkillMatch(skill=skill, score=score, parameters=extracted)

    def _find_best_match(
        self,
        goal: str,
        active_process: Optional[str],
        allowed_states: Tuple[SkillState, ...],
        allow_drafts: bool = False,
    ) -> Optional[SkillMatch]:
        candidates: List[SkillMatch] = []
        for skill in self._skills.values():
            if not allow_drafts and skill.draft:
                continue
            if skill.state not in allowed_states:
                continue
            m = self._score_skill(skill, goal, active_process)
            if m is not None:
                candidates.append(m)

        if not candidates:
            return None

        candidates.sort(
            key=lambda m: (-round(m.score, 9), -m.skill.stats.success_count, m.skill.id)
        )
        return candidates[0]

    def match(self, goal: str, active_process: Optional[str] = None) -> Optional[SkillMatch]:
        """Deterministically selects highest-scoring non-draft ACTIVE/CANDIDATE skill."""
        return self._find_best_match(
            goal=goal,
            active_process=active_process,
            allowed_states=(SkillState.ACTIVE, SkillState.CANDIDATE),
            allow_drafts=False,
        )

    def find_stale_match(
        self, goal: str, active_process: Optional[str] = None
    ) -> Optional[SkillMatch]:
        """Finds STALE non-draft skill matching goal for passive re-verification tracking."""
        return self._find_best_match(
            goal=goal,
            active_process=active_process,
            allowed_states=(SkillState.STALE,),
            allow_drafts=False,
        )

    def evaluate_freshness(
        self, skill: SkillDefinition, persist: bool = False
    ) -> FreshnessVerdict:
        """Applies TTL decay against injected clock; persists ACTIVE -> STALE transition."""
        now = _ensure_utc(self._clock())
        verified = _ensure_utc(skill.stats.last_verified_at)
        age_days = max(0.0, (now - verified).total_seconds() / 86400.0)
        ttl = skill.invalidation.ttl_days or self.config.ttl_days
        expired = age_days > float(ttl)

        if expired and skill.state == SkillState.ACTIVE:
            skill.state = SkillState.STALE
            if persist and skill.source_path is not None:
                self.save(skill)
        return FreshnessVerdict(state=skill.state, expired=expired, age_days=age_days)

    def check_visual_drift(
        self, skill: SkillDefinition, hwnd: int = 0
    ) -> DriftVerdict:
        """Computes pHash of verified OS container rect and checks min distance over anchors."""
        anchors = skill.invalidation.visual_anchors
        if not anchors:
            return DriftVerdict(checked=False, drifted=False, reason="No visual anchors recorded.")
        if self.capturer is None or self.window_probe is None:
            return DriftVerdict(checked=False, drifted=False, reason="Probe/capturer unavailable.")

        snap = (
            self.window_probe.get_window_by_hwnd(hwnd)
            if hwnd > 0
            else self.window_probe.get_active_container(
                skill.preconditions.container_process or "",
                skill.preconditions.container_title_regex,
            )
        )
        if snap is None:
            return DriftVerdict(checked=False, drifted=False, reason="Container HWND unavailable.")

        l, t, r, b = snap.window_rect
        w, h = max(1, r - l), max(1, b - t)
        frame = self.capturer.capture_rect((l, t, w, h))
        live_phash = compute_phash(frame)
        min_dist = min(hamming_distance(a.phash, live_phash) for a in anchors)

        live_anchor = VisualAnchor(
            phash=live_phash,
            window_size=(w, h),
            captured_at=_ensure_utc(self._clock()),
        )
        threshold = skill.invalidation.phash_max_hamming
        drifted = min_dist > threshold
        reason = (
            f"Visual drift detected (min_hamming={min_dist} > {threshold})."
            if drifted
            else f"Visual anchor verified (min_hamming={min_dist} <= {threshold})."
        )
        return DriftVerdict(
            checked=True,
            drifted=drifted,
            min_hamming=min_dist,
            live_anchor=live_anchor,
            reason=reason,
        )

    @staticmethod
    def process_matches_window(
        fg_proc: Optional[str],
        expected_proc: Optional[str],
        active_title: Optional[str] = None,
    ) -> bool:
        """Matches foreground process against expected_proc, including UWP ApplicationFrameHost.exe."""
        exp = (expected_proc or "").strip().lower()
        fg = (fg_proc or "").strip().lower()
        if not exp or not fg:
            return True
        if fg == exp:
            return True
        if fg == "applicationframehost.exe":
            exp_stem = re.sub(r"\.exe$", "", exp)
            title_l = (active_title or "").strip().lower()
            if not title_l:
                return True
            title_tokens = [t for t in re.findall(r"[a-z0-9]+", title_l) if len(t) >= 3]
            return any(tok in exp_stem or exp_stem in tok for tok in title_tokens)
        return False

    def compile_to_living_plan(
        self,
        match: SkillMatch,
        user_goal: str,
        active_process: Optional[str] = None,
        active_title: Optional[str] = None,
    ) -> LivingPlan:
        """Compiles a matched SkillDefinition + extracted params into LivingPlan steps."""
        skill = match.skill
        params = match.parameters
        steps: List[PlanStep] = []

        target_proc = (skill.preconditions.container_process or "").strip()
        cur_proc = (active_process or "").strip()
        if (
            skill.preconditions.requires_launch
            and target_proc
            and not self.process_matches_window(cur_proc, target_proc, active_title)
        ):
            app_stem = re.sub(r"\.exe$", "", target_proc, flags=re.IGNORECASE)
            launch_query = (skill.preconditions.launch_query or "").strip() or app_stem
            launch_method = getattr(skill.preconditions, "launch_method", "start_search")
            launch_keys = ["win", "r"] if launch_method == "win_r" else ["win"]
            launch_desc = "Open Windows Run Dialog" if launch_method == "win_r" else "Open Windows Start Menu"
            launch_crit = "Run dialog input is open" if launch_method == "win_r" else "Start Menu search input is open"
            steps.append(
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description=launch_desc,
                    target_description=launch_desc,
                    success_criteria=launch_crit,
                    rationale="launch:open_start",
                    status=StepStatus.IN_PROGRESS,
                    tool_route="GUI",
                    directive=StepDirective(verb="HOTKEY", keys=launch_keys),
                )
            )
            steps.append(
                PlanStep(
                    step_id=2,
                    intent=StepIntent.LAUNCH_OR_ACTIVATE,
                    description=f"Launch {launch_query}",
                    target_description=launch_query,
                    success_criteria=f"Application '{launch_query}' is visible and active",
                    rationale="launch:submit_search",
                    status=StepStatus.PENDING,
                    tool_route="GUI",
                    directive=StepDirective(verb="TYPE", text=launch_query, submit=True),
                )
            )

        offset = len(steps)
        for idx, s in enumerate(skill.actions.steps, start=1 + offset):
            substituted_text: Optional[str] = (
                _substitute_params(s.text, params) if s.text is not None else None
            )
            if s.verb == "TYPE":
                payload = substituted_text or ""
                desc = f"TYPE: {payload}"
            elif s.verb == "HOTKEY":
                desc = f"HOTKEY: {'+'.join(s.keys or [])}"
            elif s.verb == "WAIT":
                desc = f"WAIT: {s.wait_ms}ms"
            else:
                desc = f"{s.verb}: {_substitute_params(s.target_description or s.verb, params)}"

            directive = StepDirective(
                verb=s.verb,
                text=substituted_text,
                keys=list(s.keys) if s.keys else None,
                submit=bool(s.submit),
                clear_first=bool(s.clear_first),
                wait_ms=s.wait_ms,
            )

            steps.append(
                PlanStep(
                    step_id=idx,
                    intent=s.intent,
                    description=strip_control_chars(desc),
                    target_description=(
                        _substitute_params(s.target_description, params)
                        if s.target_description
                        else None
                    ),
                    success_criteria=_substitute_params(s.success_criteria, params),
                    rationale=f"skill:{skill.id}@v{skill.version}",
                    status=StepStatus.IN_PROGRESS if idx == 1 else StepStatus.PENDING,
                    tool_route="GUI",
                    directive=directive,
                )
            )

        return LivingPlan(
            user_goal=user_goal,
            overall_strategy=f"Skill Playbook: {skill.name} (skill:{skill.id}@v{skill.version})",
            steps=steps,
            current_step_id=1,
            consulted_gemini=False,
        )

    def approve_draft(self, skill_id: str) -> SkillDefinition:
        """Approves a draft learned skill so it becomes eligible for matching."""
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Unknown skill '{skill_id}'.")
        skill.draft = False
        skill.stats.last_verified_at = _ensure_utc(self._clock())
        self.save(skill)
        return skill

    def reject_draft(self, skill_id: str, reason: str = "Operator rejected draft") -> Path:
        """Moves a draft skill directly into _quarantine/ without deletion."""
        return self.quarantine(skill_id, reason=reason, force=True)

    def record_outcome(
        self,
        skill_id: str,
        success: bool,
        anchor: Optional[VisualAnchor] = None,
    ) -> SkillDefinition:
        """Updates execution stats, promotes CANDIDATE/STALE -> ACTIVE, or quarantines on consecutive failures."""
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Unknown skill '{skill_id}'.")

        now = _ensure_utc(self._clock())
        skill.stats.last_used_at = now

        if success:
            skill.stats.success_count += 1
            skill.stats.consecutive_failures = 0
            skill.stats.last_verified_at = now
            if skill.state in (SkillState.CANDIDATE, SkillState.STALE):
                skill.state = SkillState.ACTIVE
            if anchor is not None:
                anchors = list(skill.invalidation.visual_anchors)
                if not any(hamming_distance(a.phash, anchor.phash) == 0 for a in anchors):
                    anchors.append(anchor)
                    skill.invalidation.visual_anchors = anchors[-3:]
            self.save(skill)
        else:
            skill.stats.failure_count += 1
            skill.stats.consecutive_failures += 1
            if skill.stats.consecutive_failures >= skill.invalidation.max_consecutive_failures:
                if skill.provenance == SkillProvenance.AUTHORED:
                    skill.state = SkillState.STALE
                    logger.warning(
                        "Protected AUTHORED skill '%s' reached %d consecutive failures; "
                        "degrading to STALE instead of _quarantine/.",
                        skill_id,
                        skill.stats.consecutive_failures,
                    )
                    self.save(skill)
                else:
                    self.quarantine(
                        skill_id,
                        reason=(
                            f"Exceeded max_consecutive_failures "
                            f"({skill.stats.consecutive_failures}/{skill.invalidation.max_consecutive_failures})."
                        ),
                    )
            else:
                self.save(skill)

        return skill

    def save(self, skill: SkillDefinition) -> Path:
        """Atomically writes ContentScanner-verified SKILL.md to data/skills/<id>/SKILL.md."""
        total_redacted = 0

        def _scan_value(val: Any) -> Any:
            nonlocal total_redacted
            if isinstance(val, str):
                res = sanitize_or_reject(val)
                if not res.allowed:
                    raise ValueError(f"Skill '{skill.id}' rejected by ContentScanner: {res.reason}")
                total_redacted += res.redacted_count
                return res.text
            if isinstance(val, list):
                return [_scan_value(item) for item in val]
            if isinstance(val, dict):
                return {k: _scan_value(v) for k, v in val.items()}
            return val

        raw_data = skill.model_dump(exclude={"body", "source_path"})
        clean_data = _scan_value(raw_data)
        clean_body = _scan_value(skill.body)
        if total_redacted > 0:
            logger.warning(
                "ContentScanner redacted %d secret(s) before saving skill '%s'.",
                total_redacted,
                skill.id,
            )
            skill = SkillDefinition(**clean_data, body=clean_body, source_path=skill.source_path)

        rendered = render_skill_md(skill)
        final_scan = sanitize_or_reject(rendered)
        if not final_scan.allowed:
            raise ValueError(f"Skill '{skill.id}' rejected by ContentScanner: {final_scan.reason}")

        skill_dir = Path(self.config.skills_dir) / skill.id
        skill_dir.mkdir(parents=True, exist_ok=True)
        target_path = skill_dir / "SKILL.md"

        fd, tmp_name = tempfile.mkstemp(dir=str(skill_dir), prefix=".SKILL_", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        skill.source_path = target_path
        self._skills[skill.id] = skill
        return target_path

    def quarantine(self, skill_id: str, reason: str, force: bool = False) -> Path:
        """Moves invalidated/drifted non-AUTHORED skill directory into _quarantine/ (never deletes)."""
        existing = self._skills.get(skill_id)
        if (
            not force
            and existing is not None
            and not existing.draft
            and existing.provenance == SkillProvenance.AUTHORED
        ):
            existing.state = SkillState.STALE
            logger.warning(
                "Protected AUTHORED skill '%s' degraded to STALE instead of _quarantine/ (%s)",
                skill_id,
                reason,
            )
            return self.save(existing)

        skill = self._skills.pop(skill_id, None)
        root = Path(self.config.skills_dir)
        quarantine_root = root / "_quarantine"
        quarantine_root.mkdir(parents=True, exist_ok=True)

        src_dir = root / skill_id
        if skill is not None:
            skill.state = SkillState.INVALIDATED
            if not src_dir.exists():
                src_dir.mkdir(parents=True, exist_ok=True)
            note = f"\n\n<!-- Quarantined: {strip_control_chars(reason)} -->\n"
            skill_file = src_dir / "SKILL.md"
            skill_file.write_text(render_skill_md(skill) + note, encoding="utf-8")

        dest_dir = quarantine_root / skill_id
        if dest_dir.exists():
            suffix = self._clock().strftime("%Y%m%dT%H%M%SZ")
            dest_dir = quarantine_root / f"{skill_id}_{suffix}"

        if src_dir.exists():
            shutil.move(str(src_dir), str(dest_dir))
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)

        logger.warning("Quarantined skill '%s' -> %s (%s)", skill_id, dest_dir, reason)
        return dest_dir


# ---------------------------------------------------------------------------
# TraceRecorder & Autonomous SkillLearner (§5)
# ---------------------------------------------------------------------------

@dataclass
class TraceEntry:
    step_index: int
    verb: str
    keys: Optional[List[str]]
    text: Optional[str]
    reasoning: str
    target_label: Optional[str]
    coordinates: Optional[Tuple[int, int]]
    pre_window: str
    post_window: str
    success: bool
    screen_diff: float
    tier: str
    risk_level: str = "GREEN"
    had_user_override: bool = False
    had_sensitive_window: bool = False


class TraceRecorder:
    """Deterministic local trace recorder capturing step history + OS visual anchors."""

    def __init__(
        self,
        skills_dir: Path = Path("data/skills"),
        window_probe: Optional[IContainerWindowProbe] = None,
        capturer: Any = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.window_probe = window_probe
        self.capturer = capturer
        self._clock = clock
        self.entries: List[TraceEntry] = []
        self.captured_anchors: List[VisualAnchor] = []
        self.had_sensitive_window: bool = False
        self.had_red_risk: bool = False
        self.had_user_override: bool = False
        self._last_process: str = ""

    def reset(self) -> None:
        self.entries.clear()
        self.captured_anchors.clear()
        self.had_sensitive_window = False
        self.had_red_risk = False
        self.had_user_override = False
        self._last_process = ""

    def observe(
        self,
        step_record: StepRecord,
        pre_window: str = "",
        post_window: str = "",
        post_process: str = "",
        target_label: Optional[str] = None,
        risk_level: str = "GREEN",
        sensitive_window: bool = False,
    ) -> None:
        """Records a completed DualMind step deterministically with zero model calls."""
        if sensitive_window:
            self.had_sensitive_window = True
        if str(risk_level).upper() == "RED":
            self.had_red_risk = True
        if step_record.tier_level == CadenceTier.USER_OVERRIDE:
            self.had_user_override = True

        act = step_record.action
        self.entries.append(
            TraceEntry(
                step_index=step_record.step_id,
                verb=act.action.value,
                keys=list(act.keys) if act.keys else None,
                text=act.text,
                reasoning=act.reasoning or "",
                target_label=target_label,
                coordinates=act.coordinates,
                pre_window=pre_window or (step_record.pre_window or ""),
                post_window=post_window or (step_record.post_window or ""),
                success=step_record.success,
                screen_diff=step_record.screen_diff,
                tier=step_record.tier_level.value,
                risk_level=risk_level,
                had_user_override=(step_record.tier_level == CadenceTier.USER_OVERRIDE),
                had_sensitive_window=sensitive_window,
            )
        )

        # Capture visual anchor via OS APIs on container process transition (< 5ms)
        proc = (post_process or "").strip()
        if (
            proc
            and proc.lower() != self._last_process.lower()
            and len(self.captured_anchors) < 3
            and self.window_probe is not None
            and self.capturer is not None
        ):
            self._last_process = proc
            snap = self.window_probe.get_active_container(proc)
            if snap is not None:
                l, t, r, b = snap.window_rect
                w, h = max(1, r - l), max(1, b - t)
                try:
                    frame = self.capturer.capture_rect((l, t, w, h))
                    phash = compute_phash(frame)
                    self.captured_anchors.append(
                        VisualAnchor(
                            phash=phash,
                            window_size=(w, h),
                            captured_at=_ensure_utc(self._clock()),
                        )
                    )
                except Exception as exc:
                    logger.debug("Anchor capture skipped during trace observe: %s", exc)
        elif proc:
            self._last_process = proc

    def interactive_success_count(self) -> int:
        return sum(
            1
            for e in self.entries
            if e.success and e.verb in {a.value for a in INTERACTIVE_ACTION_TYPES}
        )

    def sanitized_view(self) -> str:
        """Serializes a coordinate-free, secret-redacted trace summary safe for Gemini co-authoring."""
        lines: List[str] = []
        for e in self.entries:
            if not e.success:
                continue
            target = sanitize_consultation_prompt(e.target_label or "")
            text = sanitize_consultation_prompt(e.text or "")
            reasoning = sanitize_consultation_prompt(e.reasoning or "")
            win = sanitize_consultation_prompt(e.post_window or e.pre_window or "")
            keys = "+".join(e.keys) if e.keys else ""
            # Note: coordinates are intentionally excluded and asserted absent
            parts = [f"step={e.step_index}", f"verb={e.verb}"]
            if keys:
                parts.append(f"keys={keys}")
            if target:
                parts.append(f"target={target}")
            if text:
                parts.append(f"text={text}")
            if win:
                parts.append(f"window={win}")
            if reasoning:
                parts.append(f"reason={reasoning[:140]}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def save_trace(self, goal: str) -> Path:
        """Persists raw local execution trace inside _traces/ (never leaves the box)."""
        traces_dir = self.skills_dir / "_traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        ts = self._clock().strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "_", (goal or "goal").lower()).strip("_")[:40] or "goal"
        path = traces_dir / f"{ts}_{slug}.json"
        payload = {
            "goal": goal,
            "captured_at": self._clock().isoformat(),
            "entries": [
                {
                    "step_index": e.step_index,
                    "verb": e.verb,
                    "keys": e.keys,
                    "text": e.text,
                    "reasoning": e.reasoning,
                    "target_label": e.target_label,
                    "coordinates": list(e.coordinates) if e.coordinates else None,
                    "pre_window": e.pre_window,
                    "post_window": e.post_window,
                    "success": e.success,
                    "screen_diff": e.screen_diff,
                    "tier": e.tier,
                    "risk_level": e.risk_level,
                }
                for e in self.entries
            ],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path


class SkillLearner:
    """Evaluates episode purity gates and co-authors draft SKILL.md playbooks via ParasiteSkill."""

    def __init__(
        self,
        config: SkillsConfig,
        registry: SkillRegistry,
        parasite_skill: Any = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.config = config
        self.registry = registry
        self.parasite_skill = parasite_skill
        self._clock = clock
        self._last_deferred_path: Optional[Path] = None

    def _check_purity_and_novelty(
        self, receipt: EpisodeReceipt, recorder: TraceRecorder
    ) -> Tuple[bool, str]:
        """Checks trace purity, substance bounds, safety, and novelty gates."""
        if not self.config.enabled or not self.config.learning_enabled:
            return False, "Skill learning disabled by configuration."
        if not receipt.success or receipt.exit_reason != "DONE":
            return False, f"Episode did not finish cleanly (success={receipt.success}, exit={receipt.exit_reason})."
        if receipt.hardware_interrupt_count > 0 or recorder.had_user_override:
            return False, "Episode contaminated by human interrupt or USER_OVERRIDE."
        if any(e.verb == ActionType.PANIC.value for e in recorder.entries):
            return False, "Episode contained PANIC step."
        count = recorder.interactive_success_count()
        if count < self.config.min_trace_steps or count > self.config.max_trace_steps:
            return False, f"Interactive step count {count} outside [{self.config.min_trace_steps}, {self.config.max_trace_steps}]."
        if recorder.had_sensitive_window or recorder.had_red_risk:
            return False, "Episode touched sensitive window or RED-risk consent action."
        if self.registry.match(receipt.goal) is not None:
            return False, "Active non-draft skill already covers this goal."
        return True, "Eligible"

    def is_eligible(self, receipt: EpisodeReceipt, recorder: TraceRecorder) -> Tuple[bool, str]:
        """Checks all 6 §5.2 learning eligibility gates independently."""
        purity_ok, reason = self._check_purity_and_novelty(receipt, recorder)
        if not purity_ok:
            return False, reason
        if self.parasite_skill is None or not self.parasite_skill.is_available():
            return False, "ParasiteSkill unavailable or circuit breaker open."
        return True, "Eligible"

    def _allocate_unique_id(self, candidate_id: str) -> str:
        base = re.sub(r"[^a-z0-9_-]+", "-", (candidate_id or "learned-skill").lower()).strip("-_")
        if len(base) < 3 or not base[0].isalnum():
            base = f"skill-{base}" if base else "learned-skill"
        base = base[:56]

        existing = set(self.registry.skills.keys())
        q_dir = Path(self.config.skills_dir) / "_quarantine"
        if q_dir.exists():
            existing.update(p.name for p in q_dir.iterdir() if p.is_dir())

        if base not in existing and not (Path(self.config.skills_dir) / base).exists():
            return base

        idx = 2
        while True:
            cand = f"{base[:58]}-{idx}"
            if cand not in existing and not (Path(self.config.skills_dir) / cand).exists():
                return cand
            idx += 1

    def _queue_pending_coauthor(
        self,
        goal: str,
        trace_payload: str,
        anchors: List[VisualAnchor],
        reason: str,
    ) -> Optional[Path]:
        """Atomically persists a ContentScanner-cleaned trace under _pending_coauthor/ for retry."""
        goal_scan = sanitize_or_reject(goal)
        trace_scan = sanitize_or_reject(trace_payload)
        if not goal_scan.allowed or not trace_scan.allowed:
            logger.warning(
                "SkillLearner refused to queue deferred coauthor trace (ContentScanner rejected)."
            )
            return None

        pending_dir = Path(self.config.skills_dir) / "_pending_coauthor"
        pending_dir.mkdir(parents=True, exist_ok=True)
        now = _ensure_utc(self._clock())
        ts = now.strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "_", goal_scan.text.lower()).strip("_")[:40] or "goal"
        target_path = pending_dir / f"{ts}_{slug}.json"
        idx = 2
        while target_path.exists():
            target_path = pending_dir / f"{ts}_{slug}_{idx}.json"
            idx += 1

        payload = {
            "schema_version": 1,
            "goal": goal_scan.text,
            "trace_payload": trace_scan.text,
            "queued_at": now.isoformat(),
            "reason": reason,
            "visual_anchors": [a.model_dump(mode="json") for a in anchors[:3]],
        }
        serialized = json.dumps(payload, indent=2)

        fd, tmp_name = tempfile.mkstemp(dir=str(pending_dir), prefix=".pending_", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        logger.info("Queued deferred SKILL_COAUTHOR trace -> %s (reason=%s)", target_path.name, reason)
        return target_path

    def _finalize_and_save_coauthored(
        self,
        skill_markdown: str,
        anchors: List[VisualAnchor],
    ) -> Optional[SkillDefinition]:
        """Parses co-authored markdown, enforces local invariants, and persists via ContentScanner."""
        try:
            draft_skill = parse_skill_md(skill_markdown)
        except Exception as exc:
            logger.warning("SkillLearner rejected invalid co-authored markdown: %s", exc)
            return None

        now = _ensure_utc(self._clock())
        unique_id = self._allocate_unique_id(draft_skill.id)

        # Force-override critical local invariants regardless of Gemini output
        cleaned_steps: List[SkillActionStep] = [
            s.model_copy(update={"relative_coordinates": None})
            for s in draft_skill.actions.steps
        ]

        final_skill = SkillDefinition(
            schema_version=1,
            id=unique_id,
            name=draft_skill.name,
            version=1,
            type=SkillType.WORKFLOW,
            draft=True,
            state=SkillState.CANDIDATE,
            provenance=SkillProvenance.CO_AUTHORED,
            description=draft_skill.description,
            trigger=draft_skill.trigger,
            parameters=draft_skill.parameters,
            preconditions=draft_skill.preconditions,
            reflex_gate=None,
            actions=SkillActions(steps=cleaned_steps),
            postconditions=draft_skill.postconditions,
            invalidation=InvalidationCriteria(
                ttl_days=self.config.ttl_days,
                phash_max_hamming=self.config.phash_max_hamming,
                max_consecutive_failures=self.config.max_consecutive_failures,
                visual_anchors=list(anchors[:3]),
            ),
            stats=SkillStats(
                created_at=now,
                last_verified_at=now,
                last_used_at=None,
                success_count=0,
                failure_count=0,
                consecutive_failures=0,
            ),
            body=draft_skill.body,
        )

        try:
            self.registry.save(final_skill)
        except ValueError as exc:
            logger.warning("SkillLearner rejected co-authored skill at save: %s", exc)
            return None

        logger.info("Saved co-authored draft skill '%s' (draft=True, state=CANDIDATE).", unique_id)
        return final_skill

    def maybe_learn(
        self,
        receipt: EpisodeReceipt,
        recorder: TraceRecorder,
    ) -> Optional[SkillDefinition]:
        """Invokes Gemini co-authoring when eligible, or queues deferred trace on unavailability/timeout."""
        self._last_deferred_path = None
        purity_ok, reason = self._check_purity_and_novelty(receipt, recorder)
        if not purity_ok:
            logger.debug("SkillLearner skipped '%s': %s", receipt.goal, reason)
            return None

        sanitized_trace = recorder.sanitized_view()
        if not sanitized_trace.strip():
            return None

        anchors = list(recorder.captured_anchors[:3])
        if self.parasite_skill is None or not self.parasite_skill.is_available():
            self._last_deferred_path = self._queue_pending_coauthor(
                receipt.goal,
                sanitized_trace,
                anchors,
                reason="parasite_unavailable",
            )
            return None

        req = ParasiteRequest(
            phase=ParasitePhase.SKILL_COAUTHOR,
            user_goal=receipt.goal,
            include_screenshot=False,
            trace_payload=sanitized_trace,
        )
        result = self.parasite_skill.invoke(req)
        if not getattr(result, "ok", False) or not getattr(result, "skill_markdown", None):
            failure = getattr(result, "failure", None)
            fail_val = failure.value if hasattr(failure, "value") else str(failure or "")
            if fail_val in (
                ParasiteFailure.HARVEST_TIMEOUT.value,
                ParasiteFailure.GENERATION_TIMEOUT.value,
            ):
                self._last_deferred_path = self._queue_pending_coauthor(
                    receipt.goal,
                    sanitized_trace,
                    anchors,
                    reason=fail_val,
                )
            else:
                logger.info("SkillLearner co-author invocation failed cleanly; no skill saved.")
            return None

        return self._finalize_and_save_coauthored(result.skill_markdown, anchors)

    def process_pending_coauthor(
        self,
        max_items: int = 1,
        skip_paths: Optional[set[Path]] = None,
    ) -> List[SkillDefinition]:
        """Opportunistically drains queued _pending_coauthor/ traces when ParasiteSkill is healthy."""
        if max_items <= 0 or not self.config.enabled or not self.config.learning_enabled:
            return []
        if self.parasite_skill is None or not self.parasite_skill.is_available():
            return []

        pending_dir = Path(self.config.skills_dir) / "_pending_coauthor"
        if not pending_dir.is_dir():
            return []

        created: List[SkillDefinition] = []
        for path in sorted(pending_dir.glob("*.json")):
            if skip_paths and path in skip_paths:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                goal = str(data.get("goal") or "")
                trace_payload = str(data.get("trace_payload") or "")
                raw_anchors = data.get("visual_anchors") or []
            except Exception as exc:
                logger.warning("Removing corrupt pending coauthor trace %s: %s", path.name, exc)
                path.unlink(missing_ok=True)
                continue

            goal_scan = sanitize_or_reject(goal)
            trace_scan = sanitize_or_reject(trace_payload)
            if not goal_scan.allowed or not trace_scan.allowed or not trace_scan.text.strip():
                logger.warning("Removing unsafe/empty pending coauthor trace %s.", path.name)
                path.unlink(missing_ok=True)
                continue

            if self.registry.match(goal_scan.text) is not None:
                path.unlink(missing_ok=True)
                continue

            anchors: List[VisualAnchor] = []
            for item in raw_anchors[:3]:
                if isinstance(item, dict):
                    try:
                        anchors.append(VisualAnchor(**item))
                    except Exception:
                        pass

            req = ParasiteRequest(
                phase=ParasitePhase.SKILL_COAUTHOR,
                user_goal=goal_scan.text,
                include_screenshot=False,
                trace_payload=trace_scan.text,
            )
            result = self.parasite_skill.invoke(req)
            if getattr(result, "ok", False) and getattr(result, "skill_markdown", None):
                saved = self._finalize_and_save_coauthored(result.skill_markdown, anchors)
                path.unlink(missing_ok=True)
                if saved is not None:
                    created.append(saved)
                    if len(created) >= max_items:
                        break
            else:
                failure = getattr(result, "failure", None)
                fail_val = failure.value if hasattr(failure, "value") else str(failure or "")
                if fail_val in (
                    ParasiteFailure.HARVEST_TIMEOUT.value,
                    ParasiteFailure.GENERATION_TIMEOUT.value,
                    ParasiteFailure.BREAKER_OPEN.value,
                ):
                    break
                path.unlink(missing_ok=True)

        return created
