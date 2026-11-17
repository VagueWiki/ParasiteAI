"""Unit tests for P4.5.3 SQLite WAL AppMemory, Layer 1.5 cache, concurrency, and draft promotion."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from parasite_ai.config import AppConfig, AppMemoryConfig, ParasiteSkillConfig, SkillsConfig
from parasite_ai.mind.app_memory import AppMemory, normalize_goal
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.parasite_protocol import (
    ParasitePhase,
    ParasitePlan,
    ParasitePlanStep,
)
from parasite_ai.mind.parasite_skill import ParasiteResult
from parasite_ai.mind.plan import StepDirective, StepIntent
from parasite_ai.mind.skills import SkillProvenance, SkillState
from parasite_ai.runtime import RuntimeOrchestrator

pytestmark = pytest.mark.unit


def _sample_plan(program: str = "Notepad") -> ParasitePlan:
    return ParasitePlan(
        selected_program=program,
        rationale="Type directly into Notepad.",
        steps=[
            ParasitePlanStep(
                intent=StepIntent.INPUT_DATA,
                description="Type hello",
                success_criteria="Hello visible",
                action=StepDirective(verb="TYPE", text="hello", submit=False),
            )
        ],
    )


def test_app_memory_wal_mode_eligibility_eviction_and_version_gate(tmp_path) -> None:
    db = tmp_path / "app_memory.db"
    mem = AppMemory(
        AppMemoryConfig(enabled=True, db_path=db, max_consecutive_failures=2, promote_after_successes=2),
        app_version="0.4.5.3",
    )
    assert mem.journal_mode() == "wal"
    assert normalize_goal("  Open   Notepad! ") == "open notepad"

    plan_id = mem.store_farmed_plan("Open Notepad!", _sample_plan())
    # 0 successes -> NOT eligible yet
    assert mem.lookup_farmed_plan("open notepad") is None

    # 1 success -> eligible
    mem.record_outcome(plan_id, success=True)
    hit = mem.lookup_farmed_plan("open notepad")
    assert hit is not None
    assert hit[0] == plan_id
    assert hit[1].selected_program == "Notepad"

    # Version prefix mismatch -> NOT returned
    mem_other = AppMemory(AppMemoryConfig(enabled=True, db_path=db), app_version="0.5.0.0")
    assert mem_other.lookup_farmed_plan("open notepad") is None
    mem_other.close()

    # 2 consecutive failures -> evicted
    mem.record_outcome(plan_id, success=False)
    mem.record_outcome(plan_id, success=False)
    assert mem.lookup_farmed_plan("open notepad") is None

    # App profile & episode recording
    mem.record_app_seen("notepad.exe", "Untitled - Notepad", launch_ok=True)
    ep_id = mem.record_episode(
        goal="open notepad",
        plan_source="farmed",
        plan_ref=str(plan_id),
        success=True,
        exit_reason="DONE",
        steps=2,
        duration_sec=1.5,
        fast_path_steps=2,
    )
    assert ep_id >= 1
    mem.close()


def test_app_memory_concurrent_writers(tmp_path) -> None:
    db = tmp_path / "concurrent.db"
    mem = AppMemory(AppMemoryConfig(enabled=True, db_path=db), app_version="0.4.5.3")
    plan_id = mem.store_farmed_plan("write test", _sample_plan())
    errors = []

    def worker(idx: int) -> None:
        try:
            for _ in range(10):
                mem.record_outcome(plan_id, success=True)
                mem.record_app_seen(f"app{idx}.exe", "Window")
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert errors == []
    mem.close()


def test_dual_mind_layer_1_5_cache_hit_skips_parasite_skill(tmp_path) -> None:
    db = tmp_path / "dm_cache.db"
    mem = AppMemory(AppMemoryConfig(enabled=True, db_path=db), app_version="0.4.5.3")
    pid = mem.store_farmed_plan("write hello in notepad", _sample_plan())
    mem.record_outcome(pid, success=True)

    cfg = AppConfig(
        parasite_skill=ParasiteSkillConfig(enabled=True),
        app_memory=AppMemoryConfig(enabled=True, db_path=db),
    )
    parasite = MagicMock()
    parasite.is_available.return_value = True
    parasite.invoke.return_value = ParasiteResult(ok=True, phase=ParasitePhase.PROACTIVE_PLAN, plan=_sample_plan())

    wg = MagicMock()
    wg.is_safe_to_operate.return_value = True
    wg.get_active_window.return_value = SimpleNamespace(title="Desktop", process_name="explorer.exe", rect=(0, 0, 100, 100))

    pipe = DualMindPipeline(
        brain_manager=MagicMock(),
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        capturer=MagicMock(),
        window_guard=wg,
        config=cfg,
        parasite_skill=parasite,
        app_memory=mem,
    )
    plan = pipe._initialize_or_update_plan("Write hello in Notepad!")
    assert parasite.invoke.call_count == 0
    assert pipe._episode_farmed_plan_id == pid
    assert plan.steps[0].directive is not None
    assert plan.steps[0].directive.text == "hello"
    mem.close()


def test_runtime_promotes_coord_free_farmed_plan_to_candidate_and_preserves_fallback(tmp_path) -> None:
    db = tmp_path / "promo.db"
    skills_dir = tmp_path / "skills"
    cfg = AppConfig(
        headless=True,
        skills=SkillsConfig(enabled=True, skills_dir=skills_dir),
        app_memory=AppMemoryConfig(enabled=True, db_path=db, promote_after_successes=2),
    )
    cfg.brain.mode = "mock"
    orch = RuntimeOrchestrator(config=cfg, simulation_mode=True)
    assert orch.app_memory is not None

    explicit_launch_plan = ParasitePlan(
        selected_program="Notepad",
        rationale="Launch Notepad via Win+R, type Draft, select all, and copy.",
        steps=[
            ParasitePlanStep(
                intent=StepIntent.LAUNCH_OR_ACTIVATE,
                description="Open Run",
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
                description="Type hello",
                success_criteria="Hello visible",
                action=StepDirective(verb="TYPE", text="hello", submit=False, clear_first=True),
            ),
        ],
    )
    pid = orch.app_memory.store_farmed_plan("Open Notepad, type 'hello'!", explicit_launch_plan)
    orch.app_memory.record_outcome(pid, success=True)
    orch.app_memory.record_outcome(pid, success=True)

    promoted = orch._promote_farmed_plans()
    assert len(promoted) == 1
    skill = promoted[0]
    assert skill.draft is False
    assert skill.state == SkillState.CANDIDATE
    assert skill.provenance == SkillProvenance.FARMED
    assert skill.trigger.keywords == ["open", "notepad", "type", "hello"]
    assert skill.preconditions.requires_launch is False
    assert skill.preconditions.container_process == "notepad.exe"
    assert skill.actions.steps[1].submit is True
    assert skill.actions.steps[2].clear_first is True
    assert (skills_dir / skill.id / "SKILL.md").exists()

    # SkillRegistry matches promoted keyword skill immediately (no black hole)
    assert orch.skill_registry.match("Open Notepad, type 'hello'!") is not None
    # Layer 1.5 lookup_farmed_plan also remains available as fallback
    assert orch.app_memory.lookup_farmed_plan("Open Notepad, type 'hello'!") is not None
    # Already promoted -> not promoted a second time
    assert orch._promote_farmed_plans() == []

    # Coordinate/pointer action plan still promotes as draft=True
    pointer_plan = ParasitePlan(
        selected_program="Paint",
        rationale="Click toolbar button.",
        steps=[
            ParasitePlanStep(
                intent=StepIntent.NAVIGATE,
                description="Click toolbar",
                target_description="Toolbar button",
                success_criteria="Tool selected",
                action=StepDirective(verb="CLICK"),
            )
        ],
    )
    pid2 = orch.app_memory.store_farmed_plan("click paint toolbar", pointer_plan)
    orch.app_memory.record_outcome(pid2, success=True)
    orch.app_memory.record_outcome(pid2, success=True)
    promoted_pointer = orch._promote_farmed_plans()
    assert len(promoted_pointer) == 1
    assert promoted_pointer[0].draft is True
    orch.app_memory.close()
