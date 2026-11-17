"""Targeted unit tests for Stint P4.6.10 (0.4.6.10) fixes."""

from unittest.mock import MagicMock

import numpy as np

from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier, EpisodicMemory
from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    SkillActions,
    SkillActionStep,
    SkillDefinition,
    SkillPostconditions,
    SkillPreconditions,
    SkillRegistry,
    SkillState,
    SkillTrigger,
)


def _make_seed_txt_skill() -> SkillDefinition:
    return SkillDefinition(
        id="open-c-parasiteai-benchmarks-workspace-seed-txt",
        name="Notepad",
        state=SkillState.ACTIVE,
        draft=False,
        description="Open C:\\ParasiteAI\\benchmarks\\workspace\\seed.txt in Notepad.",
        trigger=SkillTrigger(
            goal_patterns=[],
            keywords=["open", "c", "parasiteai", "benchmarks", "workspace", "seed", "txt"],
            process_names=["notepad.exe"],
            min_score=0.6,
        ),
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.LAUNCH_OR_ACTIVATE,
                    verb="WAIT",
                    target_description="Notepad",
                    success_criteria="Notepad visible",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Opened"),
    )


def test_skill_registry_rejects_filename_and_verb_mismatch_on_keyword_skill() -> None:
    """Keyword-only skill for seed.txt must NOT match a rename goal for old_name.txt -> new_name.txt."""
    reg = SkillRegistry.__new__(SkillRegistry)
    reg._skills = {"open-c-parasiteai-benchmarks-workspace-seed-txt": _make_seed_txt_skill()}

    mismatch = reg.match(
        "Open File Explorer to C:\\ParasiteAI\\benchmarks\\workspace and rename old_name.txt to new_name.txt"
    )
    assert mismatch is None

    valid = reg.match("Open C:\\ParasiteAI\\benchmarks\\workspace\\seed.txt")
    assert valid is not None
    assert valid.skill.id == "open-c-parasiteai-benchmarks-workspace-seed-txt"


def test_cua_burst_repetition_triggers_oscillation_without_false_diff_credit() -> None:
    """Repeated zero-diff BURST([TYPE, HOTKEY]) must not get 0.02 diff credit and must escalate strikes."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    capturer = MagicMock()
    capturer.capture.return_value = frame
    dispatcher = MagicMock()
    dispatcher.execute.return_value = MagicMock(success=True, error_message=None, returncode=None)
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Typing notepad again",
        ActionPlan(
            action=ActionType.BURST,
            burst_actions=[
                ActionPlan(action=ActionType.TYPE, text="notepad"),
                ActionPlan(action=ActionType.HOTKEY, keys=["enter"]),
            ],
            reasoning="Repeat notepad burst",
        ),
    )

    pipeline = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        capturer=capturer,
    )
    pipeline.dispatcher = dispatcher
    for _ in range(3):
        pipeline.step(user_goal="Open Notepad")

    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT


def test_parasite_skill_teardown_sleeps_after_fallback_minimize() -> None:
    """_teardown calls _sleep(0.15) after fallback minimize_window when Gemini stayed foreground."""
    from parasite_ai.mind.parasite_skill import ParasiteSkill

    wb = MagicMock()
    wb.get_foreground_hwnd.return_value = 999
    sleep_mock = MagicMock()
    skill = ParasiteSkill.__new__(ParasiteSkill)
    skill.window_backend = wb
    skill.keyboard = MagicMock()
    skill.clipboard = MagicMock()
    skill.config = MagicMock(hotkey=("ctrl", "alt", "g"))
    skill._sleep = sleep_mock

    skill._teardown(
        clip_snap=None,
        gemini_hwnd=999,
        minimize_gemini=False,
        prior_hwnd=111,
        restore_prior_focus=True,
        clear_draft=False,
    )

    wb.minimize_window.assert_called_once_with(999)
    sleep_mock.assert_called_once_with(0.15)
