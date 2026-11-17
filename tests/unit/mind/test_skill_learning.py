"""Unit tests for TraceRecorder, SkillLearner purity gates, sanitization, and draft approval flow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
import numpy as np
import pytest

from parasite_ai.config import SkillsConfig
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodeReceipt,
    StepRecord,
)
from parasite_ai.mind.parasite_protocol import ParasitePhase
from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    ContainerWindowSnapshot,
    SkillActionStep,
    SkillActions,
    SkillDefinition,
    SkillLearner,
    SkillPostconditions,
    SkillPreconditions,
    SkillProvenance,
    SkillRegistry,
    SkillState,
    SkillTrigger,
    SkillType,
    TraceRecorder,
    render_skill_md,
)

pytestmark = pytest.mark.unit


def _make_step_record(
    idx: int,
    action_type: ActionType = ActionType.CLICK,
    coords=(420, 310),
    text=None,
    keys=None,
    reasoning="Click control",
    success=True,
    tier=CadenceTier.TIER_1_LOCAL,
) -> StepRecord:
    return StepRecord(
        step_id=idx,
        action=ActionPlan(
            action=action_type,
            coordinates=coords,
            text=text,
            keys=keys,
            reasoning=reasoning,
        ),
        success=success,
        screen_diff=0.12 if success else 0.0,
        tier_level=tier,
    )


def _make_receipt(
    goal: str = "Open report template",
    *,
    success: bool = True,
    exit_reason: str = "DONE",
    hw_interrupts: int = 0,
) -> EpisodeReceipt:
    return EpisodeReceipt(
        goal=goal,
        success=success,
        exit_reason=exit_reason,
        total_steps=3,
        duration_sec=5.2,
        hardware_interrupt_count=hw_interrupts,
    )


def _coauthored_markdown(skill_id: str = "report-template", include_coords: bool = False) -> str:
    extra = "\n      relative_coordinates: [10, 20]" if include_coords else ""
    return (
        "---\n"
        "schema_version: 1\n"
        f"id: {skill_id}\n"
        "name: Open Report Template\n"
        "version: 1\n"
        "type: workflow\n"
        "draft: false\n"  # SkillLearner must force-override this back to True!
        "state: ACTIVE\n"  # SkillLearner must force-override this back to CANDIDATE!
        "provenance: authored\n"  # Must override to CO_AUTHORED
        "description: Opens report template cleanly.\n"
        "trigger:\n"
        '  goal_patterns: ["^Open report template$"]\n'
        '  keywords: ["open", "report", "template"]\n'
        "  min_score: 0.6\n"
        "preconditions:\n"
        "  container_process: notepad.exe\n"
        "actions:\n"
        "  steps:\n"
        "    - intent: LAUNCH_OR_ACTIVATE\n"
        "      verb: HOTKEY\n"
        '      target_description: "File open menu"\n'
        f'      keys: ["ctrl", "o"]{extra}\n'
        '      success_criteria: "Open dialog visible"\n'
        "postconditions:\n"
        '  success_criteria: "Template visible"\n'
        "---\n"
        "# Report Template\n"
    )


class _StubParasiteSkill:
    def __init__(self, md: Optional[str], ok: bool = True, available: bool = True) -> None:
        self.md = md
        self.ok = ok
        self.available = available
        self.requests = []

    def is_available(self) -> bool:
        return self.available

    def invoke(self, request, cancellation_token=None):
        self.requests.append(request)
        return SimpleNamespace(ok=self.ok, skill_markdown=self.md)


class _MockCapturer:
    def capture_rect(self, rect):
        x = np.linspace(0, 255, 100, dtype=np.uint8)[None, :]
        return np.repeat(x[:, :, None], 3, axis=2).repeat(100, axis=0)


class _MockProbe:
    def get_active_container(self, process_name: str, title_regex: Optional[str] = None):
        return ContainerWindowSnapshot(
            hwnd=55,
            process_name=process_name,
            title="Notepad",
            window_rect=(10, 10, 650, 490),
            client_origin=(18, 42),
            client_size=(624, 440),
        )

    def get_window_by_hwnd(self, hwnd: int):
        return self.get_active_container("notepad.exe")


def _populated_recorder(tmp_path: Path, count: int = 3) -> TraceRecorder:
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    rec = TraceRecorder(
        skills_dir=tmp_path,
        window_probe=_MockProbe(),
        capturer=_MockCapturer(),
        clock=lambda: now,
    )
    for i in range(1, count + 1):
        rec.observe(
            _make_step_record(i, coords=(100 + i, 200 + i), text="password=my_secret"),
            pre_window="Desktop",
            post_window="Notepad",
            post_process="notepad.exe",
            target_label="Editor body",
        )
    return rec


def test_trace_sanitized_view_strips_coordinates_and_redacts_secrets(tmp_path: Path) -> None:
    rec = _populated_recorder(tmp_path, count=2)
    sanitized = rec.sanitized_view()
    assert "(101, 201)" not in sanitized
    assert "coordinates=" not in sanitized
    assert "my_secret" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    saved_trace = rec.save_trace("Open report template")
    assert saved_trace.is_file()
    assert "_traces" in str(saved_trace)


def test_learning_eligibility_gates_reject_independently(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, learning_enabled=True, min_trace_steps=2, max_trace_steps=4)
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(cfg, clock=lambda: now)
    ps = _StubParasiteSkill(_coauthored_markdown())
    learner = SkillLearner(cfg, reg, ps, clock=lambda: now)

    rec = _populated_recorder(tmp_path, count=3)

    # 1. Outcome failure
    ok, _ = learner.is_eligible(_make_receipt(success=False), rec)
    assert not ok
    ok, _ = learner.is_eligible(_make_receipt(exit_reason="MAX_STEPS_EXHAUSTED"), rec)
    assert not ok

    # 2. Purity: hardware interrupt / USER_OVERRIDE / PANIC
    ok, _ = learner.is_eligible(_make_receipt(hw_interrupts=1), rec)
    assert not ok

    rec_override = _populated_recorder(tmp_path, count=2)
    rec_override.observe(_make_step_record(3, tier=CadenceTier.USER_OVERRIDE))
    assert not learner.is_eligible(_make_receipt(), rec_override)[0]

    rec_panic = _populated_recorder(tmp_path, count=2)
    rec_panic.observe(_make_step_record(3, action_type=ActionType.PANIC, success=False))
    assert not learner.is_eligible(_make_receipt(), rec_panic)[0]

    # 3. Substance bounds
    assert not learner.is_eligible(_make_receipt(), _populated_recorder(tmp_path, count=1))[0]
    assert not learner.is_eligible(_make_receipt(), _populated_recorder(tmp_path, count=5))[0]

    # 4. Safety: sensitive window / RED risk
    rec_sens = _populated_recorder(tmp_path, count=2)
    rec_sens.observe(_make_step_record(3), sensitive_window=True)
    assert not learner.is_eligible(_make_receipt(), rec_sens)[0]

    rec_red = _populated_recorder(tmp_path, count=2)
    rec_red.observe(_make_step_record(3), risk_level="RED")
    assert not learner.is_eligible(_make_receipt(), rec_red)[0]

    # 5. Availability
    ps.available = False
    assert not learner.is_eligible(_make_receipt(), rec)[0]
    ps.available = True

    learner_disabled = SkillLearner(
        SkillsConfig(enabled=True, skills_dir=tmp_path, learning_enabled=False),
        reg,
        ps,
    )
    assert not learner_disabled.is_eligible(_make_receipt(), rec)[0]

    # 6. Novelty: already matched active skill -> ineligible
    existing = SkillDefinition(
        id="existing-report",
        name="Existing",
        draft=False,
        state=SkillState.ACTIVE,
        description="Already exists.",
        trigger=SkillTrigger(goal_patterns=[r"^Open report template$"], min_score=0.6),
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[SkillActionStep(intent=StepIntent.NAVIGATE, verb="WAIT", success_criteria="ok")]
        ),
        postconditions=SkillPostconditions(success_criteria="ok"),
    )
    reg.save(existing)
    assert not learner.is_eligible(_make_receipt(), rec)[0]


def test_maybe_learn_forces_draft_overrides_anchors_and_collision_suffix(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, learning_enabled=True)
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(cfg, clock=lambda: now)
    ps = _StubParasiteSkill(_coauthored_markdown("report-template"))
    learner = SkillLearner(cfg, reg, ps, clock=lambda: now)
    rec = _populated_recorder(tmp_path, count=3)

    saved1 = learner.maybe_learn(_make_receipt(), rec)
    assert saved1 is not None
    assert ps.requests[-1].phase == ParasitePhase.SKILL_COAUTHOR
    assert ps.requests[-1].include_screenshot is False
    # Overridden invariant fields regardless of Gemini output
    assert saved1.draft is True
    assert saved1.state == SkillState.CANDIDATE
    assert saved1.type == SkillType.WORKFLOW
    assert saved1.provenance == SkillProvenance.CO_AUTHORED
    assert saved1.reflex_gate is None
    assert len(saved1.invalidation.visual_anchors) == 1

    # Draft skill cannot match until approved, then CANDIDATE -> ACTIVE on first replay
    assert reg.match("Open report template") is None
    reg.approve_draft(saved1.id)
    m = reg.match("Open report template")
    assert m is not None
    assert m.skill.state == SkillState.CANDIDATE
    promoted = reg.record_outcome(saved1.id, success=True)
    assert promoted.state == SkillState.ACTIVE

    # Collision suffix when a different goal yields the same slug
    saved2 = learner.maybe_learn(_make_receipt(goal="Open alternate report"), rec)
    assert saved2 is not None
    assert saved2.id == "report-template-2"


def test_maybe_learn_saves_nothing_on_failure_or_invalid_markdown(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, learning_enabled=True)
    reg = SkillRegistry(cfg)
    rec = _populated_recorder(tmp_path, count=3)

    learner_fail = SkillLearner(cfg, reg, _StubParasiteSkill(None, ok=False))
    assert learner_fail.maybe_learn(_make_receipt(), rec) is None
    assert reg.skills == {}

    learner_bad = SkillLearner(cfg, reg, _StubParasiteSkill("not valid skill markdown", ok=True))
    assert learner_bad.maybe_learn(_make_receipt(), rec) is None
    assert reg.skills == {}
