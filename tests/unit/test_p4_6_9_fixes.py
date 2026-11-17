"""Targeted unit tests for Stint P4.6.9 (0.4.6.9) fixes."""

from unittest.mock import MagicMock

from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionType, CadenceTier, EpisodicMemory
from parasite_ai.mind.parasite_protocol import ParasiteFailure, ParasitePhase
from parasite_ai.mind.parasite_skill import ParasiteResult
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepDirective,
    StepIntent,
)
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT


def test_conclude_wait_fast_path_emits_done_even_when_target_proc_not_foreground() -> None:
    """CONCLUDE + WAIT must not abort with proc_mismatch after minimize/close left target window."""
    pipeline = DualMindPipeline(brain_manager=MagicMock(), memory=EpisodicMemory())
    step = PlanStep(
        step_id=3,
        intent=StepIntent.CONCLUDE,
        description="Verify Notepad is minimized.",
        success_criteria="Notepad is minimized.",
        directive=StepDirective(verb="WAIT", wait_ms=0),
    )
    desktop_win = MagicMock(process_name="explorer.exe", title="Program Manager")

    res = pipeline._try_directive_fast_path(
        step=step,
        active_window=desktop_win,
        expected_process="notepad.exe",
        token=None,
    )

    assert res is not None
    thought, action_plan = res
    assert action_plan.action == ActionType.DONE
    assert "CONCLUDE" in thought
    assert pipeline._episode_fast_path_abort_reason is None


def test_consultation_exhaustion_falls_back_to_tier1_without_user_override_spin() -> None:
    """Exhausting Tier 2 Gemini consultations must fall back to TIER_1_LOCAL, not spin USER_OVERRIDE."""
    ps = MagicMock()
    ps.is_available.return_value = True
    ps.invoke.return_value = ParasiteResult(
        ok=False,
        phase=ParasitePhase.REACTIVE_RECOVERY,
        failure=ParasiteFailure.HARVEST_TIMEOUT,
        detail="Timed out harvesting response.",
    )
    pipeline = DualMindPipeline(
        brain_manager=MagicMock(),
        memory=EpisodicMemory(),
        parasite_skill=ps,
    )
    pipeline.active_plan = LivingPlan(
        user_goal="Copy token from Notepad",
        overall_strategy="Highlight and copy token",
        steps=[PlanStep(step_id=1, intent=StepIntent.SELECT_OPTION, description="Copy token", success_criteria="Token copied.")],
    )
    # Trigger consultation #1 and #2 -> max_consultation_failures (2) reached
    pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    pipeline.step(user_goal="Copy token from Notepad")
    pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    pipeline.step(user_goal="Copy token from Notepad")

    assert pipeline._episode_consult_exhausted is True
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
    assert ps.invoke.call_count == 2


def test_parasite_skill_teardown_minimizes_gemini_if_still_foreground() -> None:
    """_teardown must minimize gemini_hwnd if focus_window(prior_hwnd) left Gemini in foreground."""
    from parasite_ai.mind.parasite_skill import ParasiteSkill

    wb = MagicMock()
    wb.get_foreground_hwnd.return_value = 999  # gemini_hwnd stayed foreground
    kb = MagicMock()
    cb = MagicMock()
    skill = ParasiteSkill.__new__(ParasiteSkill)
    skill.window_backend = wb
    skill.keyboard = kb
    skill.clipboard = cb
    skill.config = MagicMock(hotkey=("ctrl", "alt", "g"))

    skill._teardown(
        clip_snap=None,
        gemini_hwnd=999,
        minimize_gemini=False,
        prior_hwnd=111,
        restore_prior_focus=True,
        clear_draft=False,
    )

    wb.focus_window.assert_called_once_with(111)
    wb.minimize_window.assert_called_once_with(999)


def test_uitars_prompt_has_clipboard_and_nested_folder_guidance_without_numeric_anchors() -> None:
    """UITARS_SYSTEM_PROMPT includes copy-after-select and folder-entry rules without literal coords."""
    assert "TEXT SELECTION & CLIPBOARD" in UITARS_SYSTEM_PROMPT
    assert "ctrl c" in UITARS_SYSTEM_PROMPT
    assert "NESTED FOLDERS" in UITARS_SYSTEM_PROMPT
    assert "<parent>\\<target>" in UITARS_SYSTEM_PROMPT
