"""
tests/test_episode_receipt.py - Unit & Integration Tests for Episode Receipts & Exit Codes.

Verifies:
1. EpisodeReceipt and StepRecordSummary schema validation and JSON serialization.
2. StepRecord.to_summary() projection fidelity.
3. RuntimeOrchestrator generation and persistence of EpisodeReceipt on goal completion,
   panic abort, stagnation loop, and max steps.
4. CLI --episode-report argument parsing and exit code mapping.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from parasite_ai.main import parse_args
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodeReceipt,
    StepRecord,
    StepRecordSummary,
)
from parasite_ai.runtime import RuntimeOrchestrator


def test_step_record_to_summary_projection() -> None:
    """Verifies that a full StepRecord correctly projects to a compact StepRecordSummary."""
    action = ActionPlan(
        action=ActionType.CLICK,
        target_id=42,
        coordinates=(100, 200),
        reasoning="Click target button",
    )
    rec = StepRecord(
        step_id=3,
        user_goal="Open settings",
        persona_thought="Looking for settings button",
        persona_speech="Clicking settings",
        action=action,
        target_info={"id": 42, "label": "Settings", "role": "Button"},
        screen_diff=0.08,
        success=True,
        tier_level=CadenceTier.TIER_1_LOCAL,
    )

    summary = rec.to_summary(duration_sec=0.456)
    assert isinstance(summary, StepRecordSummary)
    assert summary.step_id == 3
    assert summary.action_type == "CLICK"
    assert summary.target_id == 42
    assert summary.target_label == "Settings"
    assert summary.coordinates == (100, 200)
    assert summary.screen_diff == 0.08
    assert summary.success is True
    assert summary.duration_sec == 0.456
    assert summary.error_message is None


def test_episode_receipt_serialization_and_save(tmp_path: Path) -> None:
    """Verifies EpisodeReceipt serialization, JSON generation, and file saving."""
    summary = StepRecordSummary(
        step_id=1,
        action_type="DONE",
        success=True,
        screen_diff=0.0,
        duration_sec=0.15,
    )
    receipt = EpisodeReceipt(
        goal="Calculate 2 + 2",
        success=True,
        total_steps=1,
        duration_sec=1.23,
        exit_reason="DONE",
        steps=[summary],
    )

    out_file = tmp_path / "subdir" / "receipt.json"
    receipt.save(out_file)

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["goal"] == "Calculate 2 + 2"
    assert data["success"] is True
    assert data["total_steps"] == 1
    assert data["exit_reason"] == "DONE"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["action_type"] == "DONE"


def test_runtime_orchestrator_receipt_on_done(tmp_path: Path) -> None:
    """Verifies that RuntimeOrchestrator generates and saves an EpisodeReceipt on DONE."""
    out_file = tmp_path / "reports" / "done_receipt.json"
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True, episode_report_path=str(out_file))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    orch.interrupt_guard.is_interrupted = MagicMock(return_value=False)

    # Mock pipeline step to immediately return DONE
    done_action = ActionPlan(action=ActionType.DONE, reasoning="Goal achieved")
    done_record = StepRecord(
        step_id=1,
        user_goal="Launch calculator",
        action=done_action,
        success=True,
    )
    orch.pipeline.step = MagicMock(return_value=done_record)

    orch._execute_goal_episode("Launch calculator", max_steps=5)

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.success is True
    assert orch.last_episode_receipt.exit_reason == "DONE"
    assert orch.last_episode_receipt.total_steps == 1
    assert out_file.exists()


def test_runtime_orchestrator_receipt_on_max_steps(tmp_path: Path) -> None:
    """Verifies that RuntimeOrchestrator records failure and MAX_STEPS exit_reason."""
    out_file = tmp_path / "max_steps_receipt.json"
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True, episode_report_path=str(out_file))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    orch.interrupt_guard.is_interrupted = MagicMock(return_value=False)

    wait_action = ActionPlan(action=ActionType.WAIT, reasoning="Waiting for window")
    wait_record = StepRecord(
        step_id=1,
        user_goal="Unachievable goal",
        action=wait_action,
        success=True,
    )
    orch.pipeline.step = MagicMock(return_value=wait_record)

    orch._execute_goal_episode("Unachievable goal", max_steps=2)

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.success is False
    assert orch.last_reason == "MAX_STEPS" if hasattr(orch, "last_reason") else orch.last_episode_receipt.exit_reason == "MAX_STEPS"
    assert orch.last_episode_receipt.total_steps == 2
    assert out_file.exists()


def test_cli_episode_report_argument_parsing() -> None:
    """Verifies parse_args correctly captures --episode-report flag."""
    args = parse_args(["--episode-report", "benchmarks/results/receipt_01.json"])
    assert args.episode_report == "benchmarks/results/receipt_01.json"


def test_runtime_orchestrator_receipt_on_panic(tmp_path: Path) -> None:
    """Verifies that RuntimeOrchestrator records PANIC exit reason and failure."""
    out_file = tmp_path / "panic_receipt.json"
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True, episode_report_path=str(out_file))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    orch.interrupt_guard.is_interrupted = MagicMock(return_value=False)

    panic_action = ActionPlan(action=ActionType.PANIC, reasoning="Operator safety abort")
    panic_record = StepRecord(
        step_id=1,
        user_goal="Test panic",
        action=panic_action,
        success=False,
    )
    orch.pipeline.step = MagicMock(return_value=panic_record)

    orch._execute_goal_episode("Test panic", max_steps=5)

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.success is False
    assert orch.last_episode_receipt.exit_reason == "PANIC"
    assert out_file.exists()


def test_runtime_orchestrator_receipt_on_stagnation(tmp_path: Path) -> None:
    """Verifies that RuntimeOrchestrator records LOOP_STAGNATION exit reason on 3-strike loop."""
    out_file = tmp_path / "stagnation_receipt.json"
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True, episode_report_path=str(out_file))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    orch.interrupt_guard.is_interrupted = MagicMock(return_value=False)
    orch.memory.is_in_loop = MagicMock(return_value=True)

    wait_action = ActionPlan(action=ActionType.WAIT, reasoning="Looping")
    wait_record = StepRecord(
        step_id=1,
        user_goal="Looping goal",
        action=wait_action,
        success=False,
    )
    orch.pipeline.step = MagicMock(return_value=wait_record)

    orch._execute_goal_episode("Looping goal", max_steps=5)

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.success is False
    assert orch.last_episode_receipt.exit_reason == "LOOP_STAGNATION"
    assert out_file.exists()


def test_interrupt_guard_counting_and_reset() -> None:
    """Verifies physical hardware interrupt tracking and reset in InterruptGuard."""
    from parasite_ai.safety.interrupt_guard import InterruptGuard

    guard = InterruptGuard(cooldown_seconds=0.1)
    assert guard.interrupt_count == 0

    # Simulate physical touch
    guard._signal_physical_touch("test_mouse_move")
    assert guard.interrupt_count == 1

    guard._signal_physical_touch("test_key_press")
    assert guard.interrupt_count == 2

    guard.reset_interrupt_counters()
    assert guard.interrupt_count == 0


def test_subprocess_real_exit_code_and_receipt(tmp_path: Path) -> None:
    """
    RESULT-ORIENTED OS INTEGRATION TEST:
    Spawns a real Windows Python subprocess to execute ParasiteAI CLI with --auto-exit-on-complete,
    validating that the OS process returncode is strictly 1 on timeout and that the receipt file
    on disk contains valid JSON and telemetry.
    """
    import subprocess
    import sys

    cfg_path = tmp_path / "test_cfg.yaml"
    skills_dir = (tmp_path / "skills").as_posix()
    cfg_path.write_text(f"skills:\n  enabled: false\n  skills_dir: \"{skills_dir}\"\n", encoding="utf-8")

    report_path = tmp_path / "subprocess_test_receipt.json"
    cmd = [
        sys.executable,
        "-m",
        "parasite_ai.main",
        "--config",
        str(cfg_path),
        "--headless",
        "--brain-mode",
        "mock",
        "--goal",
        "Subprocess telemetry test goal",
        "--max-steps",
        "1",
        "--auto-exit-on-complete",
        "--episode-report",
        str(report_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

    # In headless test mode with 1 step that does not emit DONE, exit code must be 1 (failure)
    assert proc.returncode == 1, f"Process failed with exit code {proc.returncode}. stderr: {proc.stderr}"
    assert report_path.exists(), f"Episode receipt was not written to {report_path}"

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["goal"] == "Subprocess telemetry test goal"
    assert data["exit_reason"] in ("MAX_STEPS", "DONE")
    assert data["total_steps"] == 1
    assert data["max_steps"] == 1
    assert isinstance(data["duration_sec"], (int, float))
    assert data["duration_sec"] > 0
    assert isinstance(data["step_latencies_sec"], list)
    assert len(data["step_latencies_sec"]) == 1
    assert data["hardware_interrupt_count"] >= 0


def test_runtime_orchestrator_incremental_checkpoint_and_provenance(tmp_path: Path) -> None:
    """Verifies P4.6.6 per-step IN_PROGRESS checkpointing and plan/skill provenance fields."""
    from parasite_ai.mind.dual_mind import ActionResult

    out_file = tmp_path / "reports" / "checkpoint_receipt.json"
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True, episode_report_path=str(out_file))
    orch.window_guard.is_safe_to_operate = MagicMock(return_value=True)
    orch.interrupt_guard.is_interrupted = MagicMock(return_value=False)

    observed_mid_run: list[dict] = []
    step_calls = {"n": 0}

    def _step_fn(user_goal: str = ""):
        step_calls["n"] += 1
        if step_calls["n"] == 1:
            # Set provenance inside Step 1 after _execute_goal_episode calls start_debug_episode()
            orch.pipeline._episode_plan_source = "skill"
            orch.pipeline._episode_skill_id = "minimize-notepad"
            orch.pipeline._episode_farmed_plan_id = None
            orch.pipeline._episode_fast_path_steps = 1
            orch.pipeline._episode_parasite_invocations = 0
            orch.pipeline._episode_parasite_status = None
            return StepRecord(
                step_id=1,
                user_goal=user_goal,
                action=ActionPlan(action=ActionType.HOTKEY, keys=["win", "down"], reasoning="Minimize"),
                result=ActionResult(success=True),
                success=True,
            )
        # Before Step 2 runs, Step 1 checkpoint must already be on disk as IN_PROGRESS
        # while last_episode_receipt remains None so --auto-exit-on-complete does not fire early.
        assert orch.last_episode_receipt is None
        assert out_file.exists()
        observed_mid_run.append(json.loads(out_file.read_text(encoding="utf-8")))
        return StepRecord(
            step_id=2,
            user_goal=user_goal,
            action=ActionPlan(action=ActionType.DONE, reasoning="Minimized"),
            result=ActionResult(success=True),
            success=True,
        )

    orch.pipeline.step = MagicMock(side_effect=_step_fn)

    orch._execute_goal_episode("Minimize Notepad", max_steps=5)

    assert len(observed_mid_run) == 1
    mid = observed_mid_run[0]
    assert mid["exit_reason"] == "IN_PROGRESS"
    assert mid["total_steps"] == 1
    assert mid["plan_source"] == "skill"
    assert mid["skill_id"] == "minimize-notepad"
    assert mid["fast_path_steps"] == 1

    assert orch.last_episode_receipt is not None
    assert orch.last_episode_receipt.exit_reason == "DONE"
    assert orch.last_episode_receipt.total_steps == 2
    assert orch.last_episode_receipt.plan_source == "skill"
    assert orch.last_episode_receipt.skill_id == "minimize-notepad"
    assert orch.last_episode_receipt.fast_path_steps == 1

    final_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert final_data["exit_reason"] == "DONE"
    assert final_data["total_steps"] == 2
    assert final_data["plan_source"] == "skill"


