"""
tests/integration/test_parasite_skill_pipeline.py - Integration Tests for Stage P4.4.

Verifies end-to-end integration across:
- DualMindPipeline <-> SkillRegistry (workflow matching, visual drift quarantine, §7.6 reflex burst bypass & fallback)
- DualMindPipeline <-> ParasiteSkill (proactive open-ended routing, selected_program injection, Tier-2 reactive recovery & trigger attribution)
- Byte-identical legacy P3 suppression when SkillsConfig / ParasiteSkillConfig use default enabled=False
- RuntimeOrchestrator <-> TraceRecorder <-> SkillLearner (episode persistence, passive STALE promotion, draft gating, thread-safe approve/reject)
- DiscordBotC2 <-> SkillApprovalView <-> episode alerts (parasite_skill_alert, skill_learned, fail-closed auth whitelist)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import numpy as np
import pytest

from parasite_ai.config import (
    AppConfig,
    DiscordConfig,
    ParasiteSkillConfig,
    SkillsConfig,
)
from parasite_ai.mind.dual_mind import DualMindPipeline, should_trigger_proactive_plan
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodicMemory,
    EscalationStateMachine,
    compute_phash,
)
from parasite_ai.mind.parasite_protocol import (
    ParasiteAction,
    ParasiteFailure,
    ParasitePhase,
    ParasitePlan,
    ParasitePlanStep,
    ParasiteRequest,
    RecoveryTrigger,
)
from parasite_ai.mind.parasite_skill import ParasiteResult
from parasite_ai.mind.plan import StepDirective, StepIntent
from parasite_ai.mind.skills import (
    ContainerWindowSnapshot,
    IContainerWindowProbe,
    InvalidationCriteria,
    ReflexSafetyGate,
    SkillActions,
    SkillActionStep,
    SkillDefinition,
    SkillParameter,
    SkillPostconditions,
    SkillPreconditions,
    SkillProvenance,
    SkillRegistry,
    SkillState,
    SkillStats,
    SkillTrigger,
    SkillType,
    TraceRecorder,
    VisualAnchor,
)
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.ui.bridge import EpisodeEvent, UIBridge
from parasite_ai.ui.discord_bot import DiscordBotC2, SkillApprovalView


# ---------------------------------------------------------------------------
# Deterministic Integration Fakes
# ---------------------------------------------------------------------------

def _solid_frame(color: Tuple[int, int, int] = (40, 80, 120), w: int = 1280, h: int = 720) -> np.ndarray:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = color
    return arr


def _patterned_frame(seed: int = 1, w: int = 320, h: int = 440) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(h // 8, w // 8, 3), dtype=np.uint8)
    return np.repeat(np.repeat(base, 8, axis=0), 8, axis=1)


def _blank_white_frame(w: int = 320, h: int = 440) -> np.ndarray:
    arr = np.full((h, w, 3), 255, dtype=np.uint8)
    # Create stark half-split pattern so pHash differs strongly from patterned_frame
    arr[:, : w // 2] = (10, 10, 10)
    return arr


class FakeCapturer:
    def __init__(self, full_frame: Optional[np.ndarray] = None, rect_frame: Optional[np.ndarray] = None) -> None:
        self.full_frame = full_frame if full_frame is not None else _solid_frame()
        self.rect_frame = rect_frame if rect_frame is not None else _patterned_frame(7)

    def capture_screen(self, monitor_idx: Optional[int] = None) -> np.ndarray:
        return self.full_frame.copy()

    def capture_rect(self, rect: Tuple[int, int, int, int]) -> np.ndarray:
        return self.rect_frame.copy()


class FakeContainerProbe(IContainerWindowProbe):
    def __init__(self, snap: Optional[ContainerWindowSnapshot] = None) -> None:
        self.snap = snap

    def get_active_container(
        self, process_name: str, title_regex: Optional[str] = None
    ) -> Optional[ContainerWindowSnapshot]:
        if self.snap is None:
            return None
        if process_name and self.snap.process_name.lower() != process_name.lower():
            return None
        return self.snap

    def get_window_by_hwnd(self, hwnd: int) -> Optional[ContainerWindowSnapshot]:
        if self.snap and self.snap.hwnd == hwnd:
            return self.snap
        return None


class FakeCUABrain:
    """Plain-Python CUA stub (bypasses MagicMock guard in _is_cua_mode_active)."""

    def __init__(
        self, actions: Optional[List[Tuple[str, ActionPlan]]] = None
    ) -> None:
        self.seq = list(
            actions or [("Finishing", ActionPlan(action=ActionType.DONE, reasoning="done"))]
        )
        self.calls: List[Dict[str, Any]] = []
        self.generate_cua_step = MagicMock(side_effect=self._cua)

    def supports_vision(self) -> bool:
        return True

    def _cua(self, **kwargs: Any) -> Tuple[str, ActionPlan]:
        self.calls.append(kwargs)
        if len(self.seq) > 1:
            return self.seq.pop(0)
        return self.seq[0]


def _make_cua_brain(
    actions: Optional[List[Tuple[str, ActionPlan]]] = None
) -> FakeCUABrain:
    return FakeCUABrain(actions=actions)


def _make_window_guard(title: str = "Notepad", proc: str = "notepad.exe", safe: bool = True) -> MagicMock:
    wg = MagicMock()
    wg.is_safe_to_operate.return_value = safe
    info = SimpleNamespace(title=title, process_name=proc, rect=(0, 0, 1280, 720))
    wg.get_active_window.return_value = info
    wg.get_active_window_info.return_value = info
    return wg


def _make_workflow_skill(
    skill_id: str = "open-notepad-notes",
    state: SkillState = SkillState.ACTIVE,
    anchor: Optional[VisualAnchor] = None,
    last_verified_at: Optional[datetime] = None,
    proc: str = "notepad.exe",
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name="Notepad Note Flow",
        state=state,
        description="Write structured note in Notepad",
        trigger=SkillTrigger(
            goal_patterns=[r"^write note (?P<note>.+)$"],
            keywords=["write", "note"],
            process_names=[proc],
            min_score=0.6,
        ),
        parameters=[SkillParameter(name="note", description="Text body", required=True)],
        preconditions=SkillPreconditions(container_process=proc),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    text="{{note}}",
                    success_criteria="Text appears inside Notepad",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Note typed", expected_process=proc),
        invalidation=InvalidationCriteria(
            visual_anchors=[anchor] if anchor is not None else [],
            phash_max_hamming=8,
        ),
        stats=SkillStats(last_verified_at=last_verified_at or datetime.now(timezone.utc)),
    )


def _make_reflex_skill(
    phash_anchor: str,
    expected_size: Tuple[int, int] = (320, 440),
    skill_id: str = "calc-reflex-add",
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name="Calculator Quick Key",
        type=SkillType.REFLEX_MICRO_SKILL,
        state=SkillState.ACTIVE,
        description="Static client-relative calc sequence",
        trigger=SkillTrigger(
            goal_patterns=[r"^quick calc (?P<expr>.+)$"],
            keywords=["quick", "calc"],
            process_names=["CalculatorApp.exe"],
            min_score=0.6,
        ),
        parameters=[SkillParameter(name="expr", description="Key sequence", required=True)],
        preconditions=SkillPreconditions(container_process="CalculatorApp.exe"),
        reflex_gate=ReflexSafetyGate(
            expected_window_size=expected_size,
            relative_origin="client_top_left",
            phash_anchor=phash_anchor,
            phash_max_hamming=4,
            fail_closed_fallback="uia_vlm",
        ),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="CLICK",
                    target_description="Input area",
                    relative_coordinates=(40, 60),
                    success_criteria="Focused input",
                ),
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    text="{{expr}}",
                    success_criteria="Expression typed",
                ),
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Expression submitted"),
    )


# ---------------------------------------------------------------------------
# 1. DualMindPipeline <-> SkillRegistry (Workflow + Visual Drift)
# ---------------------------------------------------------------------------

def test_pipeline_matches_workflow_skill_and_skips_gemini_proactive(tmp_path: Path) -> None:
    cfg = AppConfig(
        skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)),
        parasite_skill=ParasiteSkillConfig(enabled=True, proactive_mode="always"),
    )
    reg = SkillRegistry(config=cfg.skills)
    reg.save(_make_workflow_skill())

    parasite = MagicMock()
    parasite.is_available.return_value = True
    brain = _make_cua_brain([("Typing note", ActionPlan(action=ActionType.TYPE, text="hello", reasoning="type"))])
    mouse = MagicMock()
    mouse.click.return_value = True
    kb = MagicMock()
    kb.type_text.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(),
        config=cfg,
        skill_registry=reg,
        parasite_skill=parasite,
    )

    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
        rec = pipe.step("write note hello world")
    assert rec.success is True
    assert pipe.active_plan is not None
    assert "Skill Playbook:" in pipe.active_plan.overall_strategy
    assert "hello world" in pipe.active_plan.steps[0].description
    parasite.invoke.assert_not_called()
    # CUA working_memory_context receives the compiled skill step
    assert "hello world" in brain.calls[0]["working_memory_context"]


def test_workflow_skill_visual_drift_quarantines_and_falls_back(tmp_path: Path) -> None:
    clean_frame = _patterned_frame(seed=11, w=320, h=440)
    drifted_frame = _blank_white_frame(w=320, h=440)
    anchor = VisualAnchor(
        phash=compute_phash(clean_frame),
        window_size=(320, 440),
        captured_at=datetime.now(timezone.utc),
    )

    snap = ContainerWindowSnapshot(
        hwnd=42,
        process_name="notepad.exe",
        title="Notepad",
        window_rect=(100, 100, 420, 540),
        client_origin=(108, 130),
        client_size=(304, 400),
    )
    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    reg = SkillRegistry(
        config=cfg.skills,
        window_probe=FakeContainerProbe(snap),
        capturer=FakeCapturer(rect_frame=drifted_frame),
    )
    wf_skill = _make_workflow_skill(skill_id="drifting-note", anchor=anchor)
    reg.save(wf_skill)

    brain = _make_cua_brain([("Fallback step", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="fallback"))])
    pipe = DualMindPipeline(
        brain_manager=brain,
        capturer=FakeCapturer(rect_frame=drifted_frame),
        window_guard=_make_window_guard(),
        config=cfg,
        skill_registry=reg,
    )

    # Coordinate-free WORKFLOW skills must NOT be falsely drift-quarantined at startup
    pipe.step("write note test")
    assert "drifting-note" in reg.skills
    assert not (tmp_path / "_quarantine" / "drifting-note" / "SKILL.md").exists()
    assert pipe.active_plan is not None
    assert "Skill Playbook:" in pipe.active_plan.overall_strategy

    # Whereas LEARNED REFLEX_MICRO_SKILL drift IS quarantined at startup and falls back
    reg2 = SkillRegistry(
        config=cfg.skills,
        window_probe=FakeContainerProbe(
            ContainerWindowSnapshot(
                hwnd=77,
                process_name="CalculatorApp.exe",
                title="Calculator",
                window_rect=(200, 150, 536, 620),
                client_origin=(208, 180),
                client_size=(320, 440),
            )
        ),
        capturer=FakeCapturer(rect_frame=drifted_frame),
    )
    reflex_skill = _make_reflex_skill(
        skill_id="drifting-reflex",
        phash_anchor=anchor.phash,
        expected_size=(320, 440),
    ).model_copy(
        update={
            "provenance": SkillProvenance.LEARNED,
            "invalidation": InvalidationCriteria(visual_anchors=[anchor], phash_max_hamming=4),
        }
    )
    reg2.save(reflex_skill)
    pipe2 = DualMindPipeline(
        brain_manager=_make_cua_brain([("Fallback step", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="fallback"))]),
        capturer=FakeCapturer(rect_frame=drifted_frame),
        window_guard=_make_window_guard(title="Calculator", proc="CalculatorApp.exe"),
        config=cfg,
        skill_registry=reg2,
    )
    pipe2.step("quick calc 2+2")
    assert "drifting-reflex" not in reg2.skills
    assert (tmp_path / "_quarantine" / "drifting-reflex" / "SKILL.md").exists()
    assert pipe2.active_plan is not None
    assert "Skill Playbook:" not in pipe2.active_plan.overall_strategy


# ---------------------------------------------------------------------------
# 2. DualMindPipeline <-> §7.6 Gated Reflex Micro-Skills
# ---------------------------------------------------------------------------

def test_reflex_micro_skill_executes_burst_when_all_gates_pass(tmp_path: Path) -> None:
    ref_frame = _patterned_frame(seed=99, w=320, h=440)
    snap = ContainerWindowSnapshot(
        hwnd=77,
        process_name="CalculatorApp.exe",
        title="Calculator",
        window_rect=(200, 150, 536, 620),
        client_origin=(208, 180),
        client_size=(320, 440),
    )
    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    reg = SkillRegistry(config=cfg.skills, window_probe=FakeContainerProbe(snap))
    reg.save(_make_reflex_skill(phash_anchor=compute_phash(ref_frame), expected_size=(320, 440)))

    mouse = MagicMock()
    mouse.click.return_value = True
    kb = MagicMock()
    kb.type_text.return_value = True
    brain = _make_cua_brain()

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=FakeCapturer(rect_frame=ref_frame),
        window_guard=_make_window_guard(title="Calculator", proc="CalculatorApp.exe"),
        config=cfg,
        skill_registry=reg,
    )

    rec = pipe.step("quick calc 7*8")
    assert rec.action.action == ActionType.BURST
    assert rec.success is True
    # Burst bypassed VLM on step 1 and translated client_origin=(208, 180) + rel=(40, 60) -> (248, 240)
    assert brain.generate_cua_step.call_count == 0
    mouse.click.assert_called_once()
    call_kw = mouse.click.call_args.kwargs
    assert (call_kw["x"], call_kw["y"]) == (248, 240)
    kb.type_text.assert_called_once_with(text="7*8", submit=False, cancellation_token=None)

    # Next step hands back to UI-TARS cleanly for verification/DONE instead of looping burst
    rec2 = pipe.step("quick calc 7*8")
    assert rec2.action.action == ActionType.DONE
    assert brain.generate_cua_step.call_count == 1


def test_reflex_dimension_mismatch_aborts_fail_closed_to_uitars(tmp_path: Path) -> None:
    ref_frame = _patterned_frame(seed=99, w=320, h=440)
    resized_snap = ContainerWindowSnapshot(
        hwnd=77,
        process_name="CalculatorApp.exe",
        title="Calculator",
        window_rect=(200, 150, 700, 700),
        client_origin=(208, 180),
        client_size=(480, 500),  # Mismatch vs expected (320, 440)
    )
    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    reg = SkillRegistry(config=cfg.skills, window_probe=FakeContainerProbe(resized_snap))
    reg.save(_make_reflex_skill(phash_anchor=compute_phash(ref_frame), expected_size=(320, 440)))

    mouse = MagicMock()
    kb = MagicMock()
    brain = _make_cua_brain([("Fallback UIA/VLM", ActionPlan(action=ActionType.CLICK, coordinates=(260, 260), reasoning="fallback"))])
    mouse.click.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=FakeCapturer(rect_frame=ref_frame),
        window_guard=_make_window_guard(title="Calculator", proc="CalculatorApp.exe"),
        config=cfg,
        skill_registry=reg,
    )

    rec = pipe.step("quick calc 7*8")
    assert rec.action.action != ActionType.BURST
    assert brain.generate_cua_step.call_count == 1
    # Dimension change alone falls back without quarantining the reflex skill
    assert "calc-reflex-add" in reg.skills


def test_reflex_phash_drift_aborts_quarantines_and_falls_back(tmp_path: Path) -> None:
    expected_frame = _patterned_frame(seed=10, w=320, h=440)
    drifted_frame = _blank_white_frame(w=320, h=440)
    snap = ContainerWindowSnapshot(
        hwnd=77,
        process_name="CalculatorApp.exe",
        title="Calculator",
        window_rect=(200, 150, 536, 620),
        client_origin=(208, 180),
        client_size=(320, 440),  # Exact size passes Gate 2, triggers Gate 3 pHash drift!
    )
    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    reg = SkillRegistry(config=cfg.skills, window_probe=FakeContainerProbe(snap))
    reg.save(
        _make_reflex_skill(
            skill_id="calc-drifted",
            phash_anchor=compute_phash(expected_frame),
            expected_size=(320, 440),
        ).model_copy(update={"provenance": SkillProvenance.LEARNED})
    )

    brain = _make_cua_brain([("Fallback VLM", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="vlm"))])
    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        capturer=FakeCapturer(rect_frame=drifted_frame),
        window_guard=_make_window_guard(title="Calculator", proc="CalculatorApp.exe"),
        config=cfg,
        skill_registry=reg,
    )

    rec = pipe.step("quick calc 9+1")
    assert rec.action.action != ActionType.BURST
    assert brain.generate_cua_step.call_count == 1
    assert "calc-drifted" not in reg.skills
    assert (tmp_path / "_quarantine" / "calc-drifted" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# 3. DualMindPipeline <-> ParasiteSkill (Proactive & Tier-2 Reactive)
# ---------------------------------------------------------------------------

def test_proactive_open_ended_selected_program_injected_into_cua() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=True,
            proactive_mode="open_ended",
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(
        ok=True,
        phase=ParasitePhase.PROACTIVE_PLAN,
        plan=ParasitePlan(
            selected_program="GIMP",
            rationale="Desktop screenshot edit best performed using installed GIMP menu filters.",
            steps=[
                ParasitePlanStep(
                    intent=StepIntent.LAUNCH_OR_ACTIVATE,
                    description="Open GIMP from desktop or Start Menu",
                    target_description="GIMP",
                    tool_route="GUI",
                    success_criteria="GIMP window visible",
                    contingency="Use Windows Paint if GIMP fails to launch",
                )
            ],
        ),
    )
    brain = _make_cua_brain([("Opening GIMP", ActionPlan(action=ActionType.HOTKEY, keys=["win"], reasoning="open start"))])
    kb = MagicMock()
    kb.hotkey.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        keyboard_driver=kb,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(title="Desktop", proc="explorer.exe"),
        config=cfg,
        parasite_skill=parasite,
    )

    pipe.step("make this image black and white")
    parasite.invoke.assert_called_once()
    req = parasite.invoke.call_args.args[0]
    assert req.phase == ParasitePhase.PROACTIVE_PLAN

    wm_ctx = brain.calls[0]["working_memory_context"]
    assert "[Selected: GIMP]" in wm_ctx
    assert "Contingency: Use Windows Paint" in wm_ctx
    assert pipe.active_plan is not None and pipe.active_plan.consulted_gemini is True


def test_focused_single_app_goal_skips_proactive_planning() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=True,
            proactive_mode="open_ended",
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    brain = _make_cua_brain([("Typing", ActionPlan(action=ActionType.TYPE, text="hello", reasoning="type"))])
    kb = MagicMock()
    kb.type_text.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        keyboard_driver=kb,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(title="Desktop", proc="explorer.exe"),
        config=cfg,
        parasite_skill=parasite,
    )

    pipe.step("Open Notepad and type hello")
    parasite.invoke.assert_not_called()
    assert brain.generate_cua_step.call_count == 1


def test_proactive_gemini_failure_falls_back_cleanly_to_local_cua() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=True,
            proactive_mode="open_ended",
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(
        ok=False,
        phase=ParasitePhase.PROACTIVE_PLAN,
        failure=ParasiteFailure.FOCUS_TIMEOUT,
        detail="Gemini Chrome window did not focus cleanly.",
    )
    brain = _make_cua_brain([("Local attempt", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="local"))])

    pipe = DualMindPipeline(
        brain_manager=brain,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(title="Desktop", proc="explorer.exe"),
        config=cfg,
        parasite_skill=parasite,
    )

    rec = pipe.step("compare two folders on desktop")
    assert rec.action.action == ActionType.WAIT
    assert pipe.active_plan is not None
    assert pipe.active_plan.consulted_gemini is False
    assert brain.generate_cua_step.call_count == 1


def test_reactive_tier2_routes_click_failures_to_parasite_skill() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=False,
            reactive_recovery=True,
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(
        ok=True,
        phase=ParasitePhase.REACTIVE_RECOVERY,
        plan=ParasitePlan(
            selected_program="WordPad",
            rationale="Dialog focus blocked Save button; click Save dropdown instead.",
            steps=[
                ParasitePlanStep(
                    intent=StepIntent.NAVIGATE,
                    description="Open File menu before clicking Save",
                    target_description="File",
                    success_criteria="File menu opens",
                )
            ],
        ),
        action=ParasiteAction(verb="CLICK", target_description="File menu"),
    )

    static_frame = _solid_frame()
    brain = _make_cua_brain(
        [
            ("Click 1", ActionPlan(action=ActionType.CLICK, coordinates=(500, 500), reasoning="try 1")),
            ("Click 2", ActionPlan(action=ActionType.CLICK, coordinates=(520, 500), reasoning="try 2")),
            ("Done", ActionPlan(action=ActionType.DONE, reasoning="done")),
        ]
    )
    mouse = MagicMock()
    mouse.click.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        capturer=FakeCapturer(full_frame=static_frame),
        window_guard=_make_window_guard(),
        config=cfg,
        parasite_skill=parasite,
    )

    # Strike 1 + Strike 2 (consecutive clicks with zero visual diff) -> TIER_2_CONSULT
    pipe.step("save file in wordpad")
    pipe.step("save file in wordpad")
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT

    rec3 = pipe.step("save file in wordpad")
    assert rec3.success is True
    parasite.invoke.assert_called_once()
    req = parasite.invoke.call_args.args[0]
    assert req.phase == ParasitePhase.REACTIVE_RECOVERY
    assert req.trigger == RecoveryTrigger.CONSECUTIVE_CLICK_FAILURES
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
    assert pipe.active_plan is not None and any("File menu" in s.description for s in pipe.active_plan.steps)


def test_reactive_tier2_attributes_oscillation_trigger() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=False,
            reactive_recovery=True,
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(
        ok=True,
        phase=ParasitePhase.REACTIVE_RECOVERY,
        action=ParasiteAction(verb="HOTKEY", keys=["escape"]),
    )

    # Return failing hotkey strikes or repeating clicks at exact same pixel to trigger is_oscillating
    static_frame = _solid_frame()
    brain = _make_cua_brain(
        [
            ("C1", ActionPlan(action=ActionType.CLICK, coordinates=(100, 100), reasoning="c1")),
            ("C2", ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(100, 100), reasoning="c2")),
            ("C3", ActionPlan(action=ActionType.HOTKEY, keys=["tab"], reasoning="k1")),
            ("C4", ActionPlan(action=ActionType.HOTKEY, keys=["tab"], reasoning="k2")),
            ("C5", ActionPlan(action=ActionType.HOTKEY, keys=["tab"], reasoning="k3")),
        ]
    )
    mouse = MagicMock()
    mouse.click.return_value = True
    kb = MagicMock()
    kb.hotkey.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=FakeCapturer(full_frame=static_frame),
        window_guard=_make_window_guard(),
        config=cfg,
        parasite_skill=parasite,
    )

    # Override memory directly so oscillation is guaranteed cleanly at step 3
    pipe.step("open dialog in notepad")
    pipe.step("open dialog in notepad")
    # Now simulate step 3 repeating hotkey tab -> same_hk_repeats >= 2 -> is_oscillating -> strike 2 -> TIER_2
    pipe.escalation_sm.reset()
    pipe.escalation_sm.local_strikes = 1
    pipe.step("open dialog in notepad")  # tab #1 -> strike? Wait: in CUA hotkey gets min diff credit
    # Verify non-CUA or zero-diff oscillation forces OSCILLATION strike cleanly:
    pipe.memory.record_step(ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"]), True, 0.05, "g")
    pipe.memory.record_step(ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"]), True, 0.05, "g")
    # Next step runs repeating ctrl+s via override_action (non-CUA) -> hits is_oscillating -> strike 2
    pipe.escalation_sm.reset()
    pipe.escalation_sm.local_strikes = 1
    pipe.step(
        "open dialog in notepad",
        override_action=ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"], reasoning="repeat"),
    )
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
    pipe.step("open dialog in notepad")
    parasite.invoke.assert_called_once()
    assert parasite.invoke.call_args.args[0].trigger == RecoveryTrigger.OSCILLATION


def test_reactive_tier2_triggers_on_abab_coordinate_and_type_hotkey_cycles() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(enabled=True, max_calls_per_episode=3),
    )
    parasite = MagicMock()
    parasite.invoke.return_value = ParasiteResult(
        ok=True,
        phase=ParasitePhase.REACTIVE_RECOVERY,
        action=ParasiteAction(verb="HOTKEY", keys=["win", "r"]),
    )
    brain = _make_cua_brain([])
    mouse = MagicMock()
    mouse.click.return_value = True
    kb = MagicMock()
    kb.hotkey.return_value = True
    kb.type_text.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=FakeCapturer(full_frame=_solid_frame()),
        window_guard=_make_window_guard(),
        config=cfg,
        parasite_skill=parasite,
    )

    # ABAB coordinate cycle (even with 0.95 screen_diff) triggers OSCILLATION on step 4
    pipe.memory.record_step(ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(529, 20)), True, 0.95, "Open Notepad")
    pipe.memory.record_step(ActionPlan(action=ActionType.CLICK, coordinates=(1906, 12)), True, 0.97, "Open Notepad")
    pipe.memory.record_step(ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(531, 20)), True, 0.95, "Open Notepad")
    pipe.escalation_sm.local_strikes = 1
    rec4 = pipe.step(
        "Open Notepad",
        override_action=ActionPlan(action=ActionType.CLICK, coordinates=(1906, 12), reasoning="abab_click"),
    )
    assert pipe._last_strike_cause == RecoveryTrigger.OSCILLATION
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT

    # Also verify ABAB TYPE <-> HOTKEY cycle triggers OSCILLATION on step 4
    pipe.escalation_sm.reset()
    pipe.escalation_sm.local_strikes = 1
    pipe.memory.clear()
    pipe.memory.record_step(ActionPlan(action=ActionType.TYPE, text="Notepad"), True, 0.02, "Open Notepad")
    pipe.memory.record_step(ActionPlan(action=ActionType.HOTKEY, keys=["enter"]), True, 0.02, "Open Notepad")
    pipe.memory.record_step(ActionPlan(action=ActionType.TYPE, text="Notepad"), True, 0.02, "Open Notepad")
    pipe._last_strike_cause = None
    pipe.step(
        "Open Notepad",
        override_action=ActionPlan(action=ActionType.HOTKEY, keys=["enter"], reasoning="abab_hk"),
    )
    assert pipe._last_strike_cause == RecoveryTrigger.OSCILLATION
    assert pipe.escalation_sm.local_strikes >= 1


def test_reactive_tier2_failure_falls_back_cleanly_to_tier1() -> None:
    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=False,
            reactive_recovery=True,
        )
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(
        ok=False,
        phase=ParasitePhase.REACTIVE_RECOVERY,
        failure=ParasiteFailure.GENERATION_TIMEOUT,
        detail="Gemini response stalled.",
    )
    brain = _make_cua_brain([("Next local try", ActionPlan(action=ActionType.DONE, reasoning="done"))])
    pipe = DualMindPipeline(
        brain_manager=brain,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(),
        config=cfg,
        parasite_skill=parasite,
    )
    pipe.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    rec = pipe.step("finish settings change")
    assert rec.success is False
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
    assert pipe.escalation_sm.local_strikes == 0

    # Local model continues uninterrupted on next step
    rec_next = pipe.step("finish settings change")
    assert rec_next.action.action == ActionType.DONE


def test_disabled_defaults_preserve_identical_p3_tier2_suppression(tmp_path: Path) -> None:
    cfg = AppConfig()  # Code defaults: skills.enabled=False, parasite_skill.enabled=False
    assert cfg.skills.enabled is False
    assert cfg.parasite_skill.enabled is False

    reg = SkillRegistry(config=cfg.skills)
    reg.save(_make_workflow_skill())

    parasite = MagicMock()
    parasite.is_available.return_value = False
    offloader = MagicMock()
    brain = _make_cua_brain([("Local step", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="local"))])

    pipe = DualMindPipeline(
        brain_manager=brain,
        capturer=FakeCapturer(),
        window_guard=_make_window_guard(),
        offloader=offloader,
        config=cfg,
        skill_registry=reg,
        parasite_skill=parasite,
    )
    pipe.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    pipe.escalation_sm.local_strikes = 2

    rec = pipe.step("write note legacy mode")
    # Default CUA mode suppresses Tier 2 consultation and resets to Tier 1 without invoking ParasiteSkill or Offloader
    parasite.invoke.assert_not_called()
    offloader.query_web_ai.assert_not_called()
    assert pipe.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
    assert pipe.escalation_sm.local_strikes == 0
    assert rec.action.action == ActionType.WAIT
    assert "Skill Playbook:" not in (pipe.active_plan.overall_strategy if pipe.active_plan else "")


# ---------------------------------------------------------------------------
# 4. RuntimeOrchestrator <-> TraceRecorder <-> SkillLearner
# ---------------------------------------------------------------------------

_COAUTHORED_SKILL_MD = """---
schema_version: 1
id: learned-quick-memo
name: Learned Quick Memo
version: 1
type: workflow
draft: true
state: CANDIDATE
provenance: co_authored
description: Repeatable sequence for typing a quick memo
trigger:
  goal_patterns:
    - "^create quick memo$"
  keywords:
    - quick
    - memo
  process_names:
    - notepad.exe
  min_score: 0.6
preconditions:
  container_process: notepad.exe
actions:
  steps:
    - intent: INPUT_DATA
      verb: TYPE
      text: memo text
      success_criteria: Memo text typed in editor
postconditions:
  success_criteria: Memo appears on screen
  expected_process: notepad.exe
---
Co-authored draft memo skill.
"""


def test_runtime_episode_learns_draft_emits_event_and_approves(tmp_path: Path) -> None:
    cfg = AppConfig(
        headless=True,
        skills=SkillsConfig(
            enabled=True,
            learning_enabled=True,
            skills_dir=str(tmp_path),
            min_trace_steps=2,
            max_trace_steps=10,
        ),
        parasite_skill=ParasiteSkillConfig(
            enabled=True,
            proactive_planning=False,
            reactive_recovery=False,
        ),
    )
    bridge = UIBridge()
    events: List[EpisodeEvent] = []
    bridge.subscribe_episode_events(events.append)

    orch = RuntimeOrchestrator(config=cfg, bridge=bridge, simulation_mode=True, headless=True)
    # Use mock capture/window_guard so episode runs purely in memory without desktop side effects
    frame = _solid_frame()
    orch.screen_capture.capture_screen = MagicMock(return_value=frame)
    orch.screen_capture.capture_rect = MagicMock(return_value=_patterned_frame(5, w=300, h=300))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    win = SimpleNamespace(title="Untitled - Notepad", process_name="notepad.exe", rect=(0, 0, 1280, 720))
    orch.window_guard.get_active_window = MagicMock(return_value=win)
    orch.window_guard.get_active_window_info = MagicMock(return_value=win)

    orch.pipeline.brain_manager.supports_vision = MagicMock(return_value=True)
    orch.pipeline.brain_manager.generate_cua_step = MagicMock(
        side_effect=[
            ("Focus editor", ActionPlan(action=ActionType.CLICK, coordinates=(400, 300), reasoning="focus")),
            ("Type text", ActionPlan(action=ActionType.TYPE, text="hello", reasoning="type")),
            ("Done", ActionPlan(action=ActionType.DONE, reasoning="done")),
        ]
    )
    orch.pipeline.goal_verifier.verify_goal_state = MagicMock(
        return_value=SimpleNamespace(verified=True, reason="ok")
    )

    # Mock ParasiteSkill co-author result cleanly
    orch.parasite_skill.is_available = MagicMock(return_value=True)
    orch.parasite_skill.invoke = MagicMock(
        return_value=ParasiteResult(
            ok=True,
            phase=ParasitePhase.SKILL_COAUTHOR,
            skill_markdown=_COAUTHORED_SKILL_MD,
        )
    )

    with patch("time.sleep", return_value=None):
        orch._execute_goal_episode("create quick memo", max_steps=6)

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.success is True
    assert list((tmp_path / "_traces").glob("*.json"))

    # Draft saved as draft=True -> not matched yet!
    assert "learned-quick-memo" in orch.skill_registry.skills
    assert orch.skill_registry.skills["learned-quick-memo"].draft is True
    assert orch.skill_registry.match("create quick memo") is None

    learned_events = [e for e in events if e.kind == "skill_learned"]
    assert len(learned_events) == 1
    assert learned_events[0].data["skill_id"] == "learned-quick-memo"

    # Approve thread-safely -> now eligible for local execution!
    approved = orch.approve_learned_skill("learned-quick-memo")
    assert approved.draft is False
    assert orch.skill_registry.match("create quick memo") is not None


def test_runtime_reject_learned_skill_quarantines(tmp_path: Path) -> None:
    cfg = AppConfig(headless=True, skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    draft_skill = _make_workflow_skill(skill_id="draft-to-reject").model_copy(update={"draft": True})
    orch.skill_registry.save(draft_skill)

    q_path = orch.reject_learned_skill("draft-to-reject", reason="Unsafe draft")
    assert q_path.exists()
    assert "draft-to-reject" not in orch.skill_registry.skills
    assert (tmp_path / "_quarantine" / "draft-to-reject" / "SKILL.md").exists()


def test_runtime_passive_reverification_promotes_stale_skill(tmp_path: Path) -> None:
    old_dt = datetime.now(timezone.utc) - timedelta(days=45)
    stale_skill = _make_workflow_skill(skill_id="stale-memo", last_verified_at=old_dt)

    cfg = AppConfig(headless=True, skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    # Pre-seed SKILL.md on disk BEFORE RuntimeOrchestrator loads registry
    seed_reg = SkillRegistry(config=cfg.skills)
    seed_reg.save(stale_skill)

    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    assert orch.skill_registry.skills["stale-memo"].state == SkillState.STALE

    orch.screen_capture.capture_screen = MagicMock(return_value=_solid_frame())
    orch.screen_capture.capture_rect = MagicMock(return_value=_patterned_frame(3, w=200, h=200))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    win = SimpleNamespace(title="Notepad", process_name="notepad.exe", rect=(0, 0, 1280, 720))
    orch.window_guard.get_active_window = MagicMock(return_value=win)
    orch.window_guard.get_active_window_info = MagicMock(return_value=win)
    orch.pipeline.brain_manager.supports_vision = MagicMock(return_value=True)
    orch.pipeline.brain_manager.generate_cua_step = MagicMock(
        side_effect=[
            ("Type", ActionPlan(action=ActionType.TYPE, text="abc", reasoning="type")),
            ("Done", ActionPlan(action=ActionType.DONE, reasoning="done")),
        ]
    )
    orch.pipeline.goal_verifier.verify_goal_state = MagicMock(
        return_value=SimpleNamespace(verified=True, reason="ok")
    )

    with patch("time.sleep", return_value=None):
        orch._execute_goal_episode("write note abc", max_steps=4)

    assert orch.skill_registry.skills["stale-memo"].state == SkillState.ACTIVE


def test_runtime_contaminated_episode_blocks_learning(tmp_path: Path) -> None:
    cfg = AppConfig(
        headless=True,
        skills=SkillsConfig(enabled=True, learning_enabled=True, skills_dir=str(tmp_path), min_trace_steps=1),
        parasite_skill=ParasiteSkillConfig(enabled=True, proactive_planning=False),
    )
    bridge = UIBridge()
    events: List[EpisodeEvent] = []
    bridge.subscribe_episode_events(events.append)

    orch = RuntimeOrchestrator(config=cfg, bridge=bridge, simulation_mode=True, headless=True)
    orch.screen_capture.capture_screen = MagicMock(return_value=_solid_frame())
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    win = SimpleNamespace(title="Notepad", process_name="notepad.exe", rect=(0, 0, 1280, 720))
    orch.window_guard.get_active_window = MagicMock(return_value=win)
    orch.window_guard.get_active_window_info = MagicMock(return_value=win)
    orch.pipeline.brain_manager.supports_vision = MagicMock(return_value=True)
    orch.pipeline.brain_manager.generate_cua_step = MagicMock(
        side_effect=[
            ("Type", ActionPlan(action=ActionType.TYPE, text="permanently delete all", reasoning="red risk step")),
            ("Done", ActionPlan(action=ActionType.DONE, reasoning="done")),
        ]
    )
    orch.pipeline.goal_verifier.verify_goal_state = MagicMock(
        return_value=SimpleNamespace(verified=True, reason="ok")
    )
    orch.parasite_skill.is_available = MagicMock(return_value=True)
    orch.parasite_skill.invoke = MagicMock()

    with patch("time.sleep", return_value=None):
        orch._execute_goal_episode("create quick memo", max_steps=4)

    assert orch.trace_recorder.had_red_risk is True
    orch.parasite_skill.invoke.assert_not_called()
    assert not [e for e in events if e.kind == "skill_learned"]


# ---------------------------------------------------------------------------
# 5. DiscordBotC2 <-> SkillApprovalView & P4.4 Embed Alerts
# ---------------------------------------------------------------------------

async def test_discord_dispatch_parasite_alert_and_skill_learned_embeds(tmp_path: Path) -> None:
    cfg = AppConfig(
        headless=True,
        discord=DiscordConfig(enabled=False, authorized_user_ids=[12345]),
        skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)),
    )
    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    c2 = DiscordBotC2(orchestrator=orch, config=cfg)

    channel = MagicMock()
    channel.send = AsyncMock()

    await c2._dispatch_episode_event(
        EpisodeEvent(
            kind="parasite_skill_alert",
            goal="open-ended task",
            data={
                "failure": "GENERATION_TIMEOUT",
                "phase": "PROACTIVE_PLAN",
                "detail": "Gemini did not finish within 60s",
                "diagnostics_path": "logs/parasite_skill_diagnostics/err.json",
                "fallback": "LOCAL_UITARS",
            },
        ),
        channel,
    )
    assert channel.send.await_count == 1
    alert_embed = channel.send.call_args.kwargs["embed"]
    assert "ParasiteSkill Fail-Closed Fallback" in alert_embed.title

    await c2._dispatch_episode_event(
        EpisodeEvent(
            kind="skill_learned",
            goal="create quick memo",
            data={
                "skill_id": "learned-quick-memo",
                "name": "Learned Quick Memo",
                "summary": "Repeatable memo typing workflow",
                "steps": 3,
                "skill_path": "data/skills/learned-quick-memo/SKILL.md",
            },
        ),
        channel,
    )
    assert channel.send.await_count == 2
    learned_kwargs = channel.send.call_args.kwargs
    assert isinstance(learned_kwargs["view"], SkillApprovalView)
    assert "learned-quick-memo" in learned_kwargs["embed"].title


async def test_discord_skill_approval_view_auth_and_approve_reject(tmp_path: Path) -> None:
    cfg = AppConfig(headless=True, skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    orch.skill_registry.save(_make_workflow_skill(skill_id="draft-a").model_copy(update={"draft": True}))
    orch.skill_registry.save(_make_workflow_skill(skill_id="draft-b").model_copy(update={"draft": True}))

    # Empty whitelist MUST fail-closed
    empty_view = SkillApprovalView("draft-a", orch, authorized_user_ids=[])
    intr_unauth = MagicMock()
    intr_unauth.user = MagicMock(id=999)
    intr_unauth.response = MagicMock(send_message=AsyncMock(), edit_message=AsyncMock())
    assert await empty_view.interaction_check(intr_unauth) is False
    intr_unauth.response.send_message.assert_awaited_once()

    # Wrong user fails closed
    auth_view = SkillApprovalView("draft-a", orch, authorized_user_ids=[111])
    assert await auth_view.interaction_check(intr_unauth) is False

    # Authorized user approves draft-a
    intr_ok = MagicMock()
    intr_ok.user = MagicMock(id=111, mention="<@111>")
    intr_ok.response = MagicMock(send_message=AsyncMock(), edit_message=AsyncMock())
    assert await auth_view.interaction_check(intr_ok) is True
    await auth_view.approve.callback(intr_ok)
    assert auth_view.decision == "approved"
    assert orch.skill_registry.skills["draft-a"].draft is False
    intr_ok.response.edit_message.assert_awaited_once()

    # Authorized user rejects draft-b
    reject_view = SkillApprovalView("draft-b", orch, authorized_user_ids=[111])
    intr_ok2 = MagicMock()
    intr_ok2.user = MagicMock(id=111, mention="<@111>")
    intr_ok2.response = MagicMock(send_message=AsyncMock(), edit_message=AsyncMock())
    await reject_view.reject.callback(intr_ok2)
    assert reject_view.decision == "rejected"
    assert "draft-b" not in orch.skill_registry.skills
    assert (tmp_path / "_quarantine" / "draft-b" / "SKILL.md").exists()


def test_workflow_deferred_drift_triggers_when_container_launches(tmp_path: Path) -> None:
    clean_frame = _patterned_frame(seed=14, w=320, h=440)
    drifted_frame = _blank_white_frame(w=320, h=440)
    anchor = VisualAnchor(
        phash=compute_phash(clean_frame),
        window_size=(320, 440),
        captured_at=datetime.now(timezone.utc),
    )
    snap = ContainerWindowSnapshot(
        hwnd=55,
        process_name="notepad.exe",
        title="Notepad",
        window_rect=(50, 50, 370, 490),
        client_origin=(58, 80),
        client_size=(304, 400),
    )
    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=str(tmp_path)))
    reg = SkillRegistry(
        config=cfg.skills,
        window_probe=FakeContainerProbe(snap),
        capturer=FakeCapturer(rect_frame=drifted_frame),
    )
    reflex_skill = _make_workflow_skill(skill_id="deferred-drift", anchor=anchor)
    reflex_skill.type = SkillType.REFLEX_MICRO_SKILL
    reflex_skill.provenance = SkillProvenance.LEARNED
    reg.save(reflex_skill)

    # Step starts on explorer.exe (before notepad launches), then active window shifts to notepad.exe
    wg = MagicMock()
    wg.is_safe_to_operate.return_value = True
    desktop_win = SimpleNamespace(title="Desktop", process_name="explorer.exe", rect=(0, 0, 1280, 720))
    notepad_win = SimpleNamespace(title="Notepad", process_name="notepad.exe", rect=(50, 50, 370, 490))
    calls = {"n": 0}

    def _next_win() -> SimpleNamespace:
        calls["n"] += 1
        # Initial calls see explorer.exe during _initialize_or_update_plan, subsequent calls see notepad.exe
        return desktop_win if calls["n"] <= 2 else notepad_win

    wg.get_active_window_info.side_effect = _next_win
    wg.get_active_window.side_effect = _next_win

    brain = _make_cua_brain([("Step", ActionPlan(action=ActionType.WAIT, wait_ms=50, reasoning="ok"))])
    pipe = DualMindPipeline(
        brain_manager=brain,
        capturer=FakeCapturer(rect_frame=drifted_frame),
        window_guard=wg,
        config=cfg,
        skill_registry=reg,
    )

    # Plan init ran while explorer.exe active, then inside step() eff_win switches to notepad.exe -> drift checked!
    pipe.step("write note hello")
    assert "deferred-drift" not in reg.skills
    assert (tmp_path / "_quarantine" / "deferred-drift" / "SKILL.md").exists()


def test_should_trigger_proactive_plan_gates_matrix() -> None:
    from parasite_ai.mind.affordance import ActionAffordance

    ps = MagicMock()
    ps.is_available.return_value = True

    cfg_oe = AppConfig(parasite_skill=ParasiteSkillConfig(enabled=True, proactive_planning=True, proactive_mode="open_ended"))
    assert should_trigger_proactive_plan("make photo black and white", None, ActionAffordance.PHYSICAL_GUI, False, ps, cfg_oe) is True
    assert should_trigger_proactive_plan("Open Notepad and type hi", "notepad", ActionAffordance.PHYSICAL_GUI, False, ps, cfg_oe) is False
    assert should_trigger_proactive_plan("compare Paint vs GIMP and convert png", "paint", ActionAffordance.PHYSICAL_GUI, False, ps, cfg_oe) is True
    assert should_trigger_proactive_plan("run pytest now", None, ActionAffordance.LOCAL_DEVELOPER_TOOL, False, ps, cfg_oe) is False
    assert should_trigger_proactive_plan("make photo black and white", None, ActionAffordance.PHYSICAL_GUI, True, ps, cfg_oe) is False

    cfg_off = AppConfig(parasite_skill=ParasiteSkillConfig(enabled=True, proactive_planning=True, proactive_mode="off"))
    assert should_trigger_proactive_plan("make photo black and white", None, ActionAffordance.PHYSICAL_GUI, False, ps, cfg_off) is False


def test_runtime_wires_hybrid_local_assist_and_smoke_probe_contracts(
    tmp_path: Path, monkeypatch
) -> None:
    import parasite_ai
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend
    from scripts import smoke_test_p4_4_parasite_skill as smoke_mod

    assert parasite_ai.__version__ == "0.4.8.4"

    cfg = AppConfig(skills=SkillsConfig(enabled=False, skills_dir=str(tmp_path / "skills")))
    assert cfg.parasite_skill.local_assist_enabled is True
    assert cfg.parasite_skill.max_local_assist_calls_per_invoke == 4
    assert cfg.parasite_skill.scroll_before_copy_attempts == 3
    assert "Send message" in cfg.parasite_skill.send_button_names
    assert "Copy response" in cfg.parasite_skill.copy_button_names
    assert "Copy code" in cfg.parasite_skill.copy_button_names
    assert "ask away" in cfg.parasite_skill.overlay_uia_signatures

    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    assert isinstance(orch.parasite_skill.local_assist, HybridLocalAssistBackend)
    assert orch.parasite_skill.local_assist.screen_grounder is orch.screen_grounder
    assert orch.parasite_skill.local_assist.brain_manager is orch.brain_manager
    assert orch.parasite_skill.local_assist.capturer is orch.screen_capture

    # Smoke probe helpers (P-B, P-F & P-G contracts) must execute cleanly with zero enum/method typos
    fake_cap = FakeCapturer(full_frame=_patterned_frame(9, w=320, h=240))

    class _FakeMemClip:
        def __init__(self):
            self.text = ""
            self.dib = b""
        def set_text(self, t):
            self.text = t
        def get_text(self):
            return self.text
        def set_image_dib(self, frame):
            self.dib = f"DIB:{frame.shape}".encode()
        def snapshot(self):
            return (self.text, self.dib)
        def restore(self, snap):
            self.text, self.dib = snap

    monkeypatch.setattr(smoke_mod, "Win32ImageClipboard", _FakeMemClip)
    res_b = smoke_mod.probe_b_cf_dib_clipboard(fake_cap)  # type: ignore[arg-type]
    assert res_b["passed"] is True

    res_f = smoke_mod.probe_f_phash_drift_and_ttl(fake_cap)  # type: ignore[arg-type]
    assert res_f["passed"] is True
    assert res_f["ttl_decayed_to_stale"] is True

    monkeypatch.setattr(
        smoke_mod,
        "Win32EnvironmentDiscovery",
        lambda **kw: SimpleNamespace(collect=lambda **k: (["explorer.exe: Home"], ["Notepad", "Paint"])),
    )

    def _fake_nvidia(cmd, **kwargs):
        q = " ".join(cmd)
        if "memory.used" in q:
            return SimpleNamespace(returncode=0, stdout="6650\n")
        return SimpleNamespace(returncode=0, stdout="")  # 0 MB Parasite compute VRAM even on busy desktop

    monkeypatch.setattr(smoke_mod.subprocess, "run", _fake_nvidia)
    res_g = smoke_mod.probe_g_env_discovery_and_vram()
    assert res_g["passed"] is True
    assert res_g["parasite_vram_mb"] == 0
    assert res_g["desktop_total_vram_mb"] == 6650


def test_uia_chrome_anchor_clears_draft_ignores_caret_flicker_and_scrolls_to_copy(
    tmp_path: Path,
) -> None:
    import re
    from parasite_ai.mind.memory import compute_dhash
    from parasite_ai.mind.parasite_protocol import build_parasite_prompt
    from parasite_ai.mind.parasite_skill import ParasiteRequest, ParasiteSkill

    cfg = ParasiteSkillConfig(
        enabled=True,
        diagnostics_dir=tmp_path / "diag",
        hotkey=["alt", "g"],
        attach_settle_ms=100,
        min_generation_wait_ms=100,
        stream_stability_ms=300,
        generation_timeout_sec=10.0,
        harvest_timeout_sec=2.0,
        submit_verify_timeout_sec=0.3,
        scroll_before_copy_attempts=2,
        local_assist_enabled=True,
    )

    class _AnchorWin:
        def __init__(self) -> None:
            self.active_hwnd = 101
            self.copy_pos = None

        def get_foreground_hwnd(self) -> int:
            return self.active_hwnd

        def find_gemini_window(self, *args, **kwargs):
            return None

        def find_gemini_window_detailed(self, *args, **kwargs):
            return (202, "uia_chrome_anchor")

        def get_process_name(self, hwnd: int) -> str:
            return "chrome.exe" if hwnd == 202 else "notepad.exe"

        def get_window_title(self, hwnd: int) -> str:
            return "Google Chrome" if hwnd == 202 else "Notepad"

        def ensure_on_primary_monitor(self, hwnd: int) -> bool:
            return False

        def has_input_focus(self, hwnd: int) -> bool:
            return True

        def get_window_rect(self, hwnd: int):
            return (100, 100, 514, 755)

        def is_window_visible(self, hwnd: int) -> bool:
            return True

        def focus_window(self, hwnd: int) -> bool:
            self.active_hwnd = hwnd
            return True

        def minimize_window(self, hwnd: int) -> bool:
            return True

        def dismiss_window(self, hwnd: int, *, toggle_hotkey_fn=None) -> bool:
            if toggle_hotkey_fn:
                toggle_hotkey_fn()
            return True

        def find_uia_button(self, hwnd: int, names, *, pick_last: bool = True):
            if any("Copy" in n for n in names):
                return self.copy_pos
            return None

        def find_uia_input_box(self, hwnd: int, names):
            return (300, 718)

        def is_window_topmost(self, hwnd: int) -> bool:
            return True

        def has_window_style(self, hwnd: int, style: int) -> bool:
            return False

    class _FakeClip:
        def __init__(self) -> None:
            self.text = ""
            self.last_prompt = ""
            self.dib = b""

        def snapshot(self):
            return (self.text, self.dib)

        def restore(self, snap) -> None:
            self.text, self.dib = snap

        def set_image_dib(self, frame) -> None:
            self.dib = b"DIB"

        def set_unicode_text(self, t: str) -> None:
            self.text = t
            if 'nonce="' in t:
                self.last_prompt = t

        def get_unicode_text(self) -> str:
            return self.text

        def set_text(self, t: str) -> None:
            self.text = t

        def get_text(self) -> str:
            return self.text

    class _FakeKbd:
        def __init__(self) -> None:
            self.hotkeys: List[Tuple[str, ...]] = []

        def hotkey(self, *keys: str, cancellation_token=None) -> bool:
            self.hotkeys.append(tuple(keys))
            if tuple(keys) == ("alt", "g"):
                win.active_hwnd = 202
            elif tuple(keys) == ("enter",):
                state["phase"] = "post_enter"
            return True

    state = {"phase": "pre_submit", "scrolled": False, "tick": 0}

    class _FakeMouse:
        def __init__(self, clip: _FakeClip) -> None:
            self.clip = clip
            self.clicks: List[Tuple[int, int]] = []
            self.scrolls = 0

        def click(self, x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
            self.clicks.append((int(x), int(y)))
            if (int(x), int(y)) == (478, 718):
                state["phase"] = "submitted"
            elif (int(x), int(y)) == (197, 652):
                # Extract nonce from pasted prompt
                m = re.search(r'nonce="([a-f0-9]+)"', self.clip.last_prompt)
                nonce = m.group(1) if m else "0000"
                self.clip.text = (
                    f'<parasite_plan nonce="{nonce}">\n'
                    '{\n'
                    '  "selected_program": "Notepad",\n'
                    '  "rationale": "Simple editor works reliably.",\n'
                    '  "steps": [{"intent": "NAVIGATE", "description": "Focus editor", "success_criteria": "Focused"}]\n'
                    '}\n'
                    '</parasite_plan>'
                )
            return True

        def scroll(self, delta: int, x=None, y=None, cancellation_token=None) -> bool:
            self.scrolls += 1
            state["scrolled"] = True
            return True

    class _FakeCap:
        def capture_screen(self, monitor_idx: Optional[int] = None):
            return np.full((100, 100, 3), 80, dtype=np.uint8)

        def capture_rect(self, rect_wh):
            _, _, w, h = rect_wh
            state["tick"] += 1
            frame = np.full((h, w, 3), 120, dtype=np.uint8)
            if state["phase"] == "submitted":
                frame[80:300, 40:400] = 220
            if state["scrolled"]:
                frame[320:520, 40:400] = 240
            if state["tick"] % 2 == 1:
                frame[h - 32 : h - 24, 90:94] = 255
            return frame

    class _FakeAssist:
        def __init__(self) -> None:
            self.copy_calls = 0

        def verify_gemini_surface(self, hwnd, rect, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, rect, input_names):
            return (300, 718, "screen_grounder")

        def locate_send_button(self, hwnd, rect, send_names):
            return (478, 718, "local_vlm")

        def locate_copy_button(self, hwnd, rect, copy_names, exclude_points=None):
            self.copy_calls += 1
            return (197, 652, "local_vlm")

    win = _AnchorWin()
    clip = _FakeClip()
    kbd = _FakeKbd()
    mouse = _FakeMouse(clip)
    assist = _FakeAssist()
    clock_val = {"t": 0.0}

    def _clock() -> float:
        return clock_val["t"]

    def _sleep(sec: float) -> None:
        clock_val["t"] += sec

    skill = ParasiteSkill(
        config=cfg,
        keyboard_driver=kbd,
        mouse_driver=mouse,
        capturer=_FakeCap(),
        clipboard=clip,
        window_backend=win,
        env_discovery=SimpleNamespace(collect=lambda **kw: ([], [])),
        local_assist=assist,
        clock=_clock,
        sleep_fn=_sleep,
    )

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Integration E2E"))
    assert res.ok is True
    assert res.identity_mode != "win32_title"
    assert res.submit_method == "send_button:local_vlm"
    assert ("ctrl", "a") in kbd.hotkeys
    assert ("backspace",) in kbd.hotkeys
    assert mouse.scrolls >= 1
    assert assist.copy_calls == 1
    assert (197, 652) in mouse.clicks


def test_promoted_farmed_skill_matches_and_compiles_with_submit_without_black_hole(tmp_path: Path) -> None:
    from parasite_ai.config import AppMemoryConfig

    db_path = tmp_path / "app_memory.db"
    skills_dir = tmp_path / "skills"
    cfg = AppConfig(
        headless=True,
        skills=SkillsConfig(enabled=True, skills_dir=skills_dir),
        app_memory=AppMemoryConfig(enabled=True, db_path=db_path, promote_after_successes=2),
    )
    cfg.brain.mode = "mock"
    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True, headless=True)
    assert orch.app_memory is not None

    plan = ParasitePlan(
        selected_program="Notepad",
        rationale="Launch Notepad via Win+R, write Draft, copy.",
        steps=[
            ParasitePlanStep(
                intent=StepIntent.LAUNCH_OR_ACTIVATE,
                description="Open Run dialog",
                success_criteria="Run visible",
                action=StepDirective(verb="HOTKEY", keys=["win", "r"]),
            ),
            ParasitePlanStep(
                intent=StepIntent.INPUT_DATA,
                description="Run notepad",
                success_criteria="Notepad launched",
                action=StepDirective(verb="TYPE", text="notepad", submit=True),
            ),
            ParasitePlanStep(
                intent=StepIntent.INPUT_DATA,
                description="Type Draft",
                success_criteria="Draft typed",
                action=StepDirective(verb="TYPE", text="Draft", submit=False),
            ),
        ],
    )
    pid = orch.app_memory.store_farmed_plan("open notepad type draft", plan)
    orch.app_memory.record_outcome(pid, success=True)
    orch.app_memory.record_outcome(pid, success=True)

    promoted = orch._promote_farmed_plans()
    assert len(promoted) == 1
    assert promoted[0].draft is False

    matched = orch.skill_registry.match("Open Notepad type Draft", active_process="explorer.exe")
    assert matched is not None
    living = orch.skill_registry.compile_to_living_plan(matched, "Open Notepad type Draft", active_process="explorer.exe")
    assert len(living.steps) == 3
    assert living.steps[0].directive is not None and living.steps[0].directive.keys == ["win", "r"]
    assert living.steps[1].directive is not None and living.steps[1].directive.submit is True
    assert living.steps[2].directive is not None and living.steps[2].directive.text == "Draft"
    orch.app_memory.close()



