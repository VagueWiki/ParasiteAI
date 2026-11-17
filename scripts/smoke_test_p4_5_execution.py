"""
scripts/smoke_test_p4_5_execution.py - Stage P4.5 Live Execution, Cache & Playbook Smoke Probes (P-H .. P-L).

MUST be run interactively by the operator on an unlocked Windows desktop session via
`run_smoke_probe_p4_5.bat` (Engineering Cadence Section 6).

Probes:
  P-H: Farmed ParasitePlan executed end-to-end (Notepad + text), persisting full plan JSON.
  P-I: Layer 1.5 AppMemory cache hit on same goal (parasite_skill invocations == 0).
  P-J: calculator-evaluate local playbook end-to-end ("calculate 12*7").
  P-K: paint-new-and-save local playbook end-to-end (verifies saved file on disk, then cleans up).
  P-L: AppMemory SQLite WAL mode, row counts, and zero-Gemini draft SKILL.md promotion.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parasite_ai.config import AppConfig, AppMemoryConfig, ParasiteSkillConfig, SkillsConfig, load_config
from parasite_ai.main import setup_logging
from parasite_ai.mind.app_memory import AppMemory
from parasite_ai.mind.skills import SkillProvenance
from parasite_ai.runtime import RuntimeOrchestrator

logger = logging.getLogger("parasite_ai.smoke_p4_5")


def _cleanup_processes(names: List[str]) -> None:
    for proc in names:
        try:
            subprocess.run(
                ["taskkill", "/IM", proc, "/F"],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass


def _build_orchestrator(
    base_cfg: AppConfig,
    *,
    skills_enabled: bool,
    parasite_enabled: bool,
    app_memory_enabled: bool,
    db_path: Path,
    skills_dir: Path = Path("data/skills"),
) -> RuntimeOrchestrator:
    cfg = base_cfg.model_copy(deep=True)
    cfg.headless = False
    cfg.skills = SkillsConfig(enabled=skills_enabled, skills_dir=skills_dir, learning_enabled=False)
    cfg.parasite_skill = ParasiteSkillConfig(
        enabled=parasite_enabled,
        proactive_planning=True,
        proactive_mode="always" if parasite_enabled else "open_ended",
        reactive_recovery=True,
    )
    cfg.app_memory = AppMemoryConfig(
        enabled=app_memory_enabled,
        db_path=db_path,
        max_consecutive_failures=2,
        promote_after_successes=2,
    )
    return RuntimeOrchestrator(config=cfg)


def probe_ph_farmed_execution(base_cfg: AppConfig, work_dir: Path) -> Dict[str, Any]:
    """P-H: Farm a plan via ParasiteSkill, execute it end-to-end, persist full plan JSON."""
    db_path = work_dir / "app_memory.db"
    goal = "open Notepad and type ParasiteAI P4.5 verified"
    orch = _build_orchestrator(
        base_cfg,
        skills_enabled=False,
        parasite_enabled=True,
        app_memory_enabled=True,
        db_path=db_path,
    )
    t0 = time.perf_counter()
    try:
        receipt = orch.run_goal_sync(goal, max_steps=12)
        farmed_plan_dump: Any = None
        if orch.app_memory is not None and orch.pipeline._episode_farmed_plan_id is not None:
            row = orch.app_memory._conn.execute(
                "SELECT plan_json FROM farmed_plans WHERE id = ?",
                (orch.pipeline._episode_farmed_plan_id,),
            ).fetchone()
            if row:
                farmed_plan_dump = json.loads(row["plan_json"])
        passed = bool(receipt.success and farmed_plan_dump is not None)
        return {
            "passed": passed,
            "goal": goal,
            "exit_reason": receipt.exit_reason,
            "steps_executed": receipt.steps_executed,
            "fast_path_steps": getattr(orch.pipeline, "_episode_fast_path_steps", 0),
            "duration_sec": round(time.perf_counter() - t0, 2),
            "farmed_plan": farmed_plan_dump,
        }
    finally:
        if orch.app_memory is not None:
            orch.app_memory.close()
        _cleanup_processes(["notepad.exe"])


def probe_pi_cache_hit(base_cfg: AppConfig, work_dir: Path) -> Dict[str, Any]:
    """P-I: Re-run P-H goal; verify Layer 1.5 cache hit with 0 ParasiteSkill invocations."""
    db_path = work_dir / "app_memory.db"
    goal = "open Notepad and type ParasiteAI P4.5 verified"
    orch = _build_orchestrator(
        base_cfg,
        skills_enabled=False,
        parasite_enabled=True,
        app_memory_enabled=True,
        db_path=db_path,
    )
    invocations = 0
    orig_invoke = orch.parasite_skill.invoke

    def _counting_invoke(*args: Any, **kwargs: Any) -> Any:
        nonlocal invocations
        invocations += 1
        return orig_invoke(*args, **kwargs)

    orch.parasite_skill.invoke = _counting_invoke  # type: ignore[method-assign]
    t0 = time.perf_counter()
    try:
        receipt = orch.run_goal_sync(goal, max_steps=12)
        passed = bool(receipt.success and invocations == 0)
        return {
            "passed": passed,
            "goal": goal,
            "exit_reason": receipt.exit_reason,
            "parasite_invocations": invocations,
            "fast_path_steps": getattr(orch.pipeline, "_episode_fast_path_steps", 0),
            "duration_sec": round(time.perf_counter() - t0, 2),
        }
    finally:
        if orch.app_memory is not None:
            orch.app_memory.close()
        _cleanup_processes(["notepad.exe"])


def probe_pj_calculator(base_cfg: AppConfig, work_dir: Path) -> Dict[str, Any]:
    """P-J: Execute calculator-evaluate playbook end-to-end."""
    db_path = work_dir / "playbooks_memory.db"
    goal = "calculate 12*7"
    orch = _build_orchestrator(
        base_cfg,
        skills_enabled=True,
        parasite_enabled=False,
        app_memory_enabled=True,
        db_path=db_path,
    )
    t0 = time.perf_counter()
    try:
        receipt = orch.run_goal_sync(goal, max_steps=10)
        return {
            "passed": bool(receipt.success),
            "goal": goal,
            "exit_reason": receipt.exit_reason,
            "steps_executed": receipt.steps_executed,
            "fast_path_steps": getattr(orch.pipeline, "_episode_fast_path_steps", 0),
            "duration_sec": round(time.perf_counter() - t0, 2),
        }
    finally:
        if orch.app_memory is not None:
            orch.app_memory.close()
        _cleanup_processes(["CalculatorApp.exe"])


def probe_pk_paint_save(base_cfg: AppConfig, work_dir: Path) -> Dict[str, Any]:
    """P-K: Execute paint-new-and-save playbook and verify output file on disk."""
    db_path = work_dir / "playbooks_memory.db"
    out_file = work_dir / "p4_5_smoke_canvas.png"
    if out_file.exists():
        out_file.unlink()
    goal = f"open paint and save as {out_file}"
    orch = _build_orchestrator(
        base_cfg,
        skills_enabled=True,
        parasite_enabled=False,
        app_memory_enabled=True,
        db_path=db_path,
    )
    t0 = time.perf_counter()
    try:
        receipt = orch.run_goal_sync(goal, max_steps=10)
        file_exists = out_file.exists() and out_file.stat().st_size > 0
        return {
            "passed": bool(receipt.success and file_exists),
            "goal": goal,
            "exit_reason": receipt.exit_reason,
            "file_exists": file_exists,
            "duration_sec": round(time.perf_counter() - t0, 2),
        }
    finally:
        if out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
        if orch.app_memory is not None:
            orch.app_memory.close()
        _cleanup_processes(["mspaint.exe"])


def probe_pl_app_memory_promotion(base_cfg: AppConfig, work_dir: Path) -> Dict[str, Any]:
    """P-L: Verify SQLite WAL mode, table counts, and zero-Gemini draft promotion."""
    db_path = work_dir / "app_memory.db"
    sandbox_skills = work_dir / "sandbox_skills"
    sandbox_skills.mkdir(parents=True, exist_ok=True)
    orch = _build_orchestrator(
        base_cfg,
        skills_enabled=True,
        parasite_enabled=False,
        app_memory_enabled=True,
        db_path=db_path,
        skills_dir=sandbox_skills,
    )
    try:
        assert orch.app_memory is not None
        wal_mode = orch.app_memory.journal_mode()
        promoted = orch._promote_farmed_plans()
        farmed_count = int(orch.app_memory._conn.execute("SELECT COUNT(*) FROM farmed_plans").fetchone()[0])
        ep_count = int(orch.app_memory._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])
        prof_count = int(orch.app_memory._conn.execute("SELECT COUNT(*) FROM app_profiles").fetchone()[0])
        draft_ok = any(
            s.draft and s.provenance == SkillProvenance.FARMED and (sandbox_skills / s.id / "SKILL.md").exists()
            for s in promoted
        )
        passed = wal_mode == "wal" and farmed_count >= 1 and ep_count >= 1 and draft_ok
        return {
            "passed": passed,
            "journal_mode": wal_mode,
            "farmed_plans": farmed_count,
            "episodes": ep_count,
            "app_profiles": prof_count,
            "promoted_count": len(promoted),
            "draft_skill_verified": draft_ok,
        }
    finally:
        if orch.app_memory is not None:
            orch.app_memory.close()


def _disable_console_quick_edit() -> None:
    """Disable Windows cmd.exe QuickEdit mode so GUI clicks never pause stdout."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            new_mode = (mode.value & ~0x0040) | 0x0080  # -ENABLE_QUICK_EDIT_MODE +ENABLE_EXTENDED_FLAGS
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


def main() -> int:
    _disable_console_quick_edit()
    parser = argparse.ArgumentParser(description="Stage P4.5 Live Execution Smoke Probes (P-H .. P-L)")
    parser.add_argument("--probe", default="all", help="Probe ID (P-H..P-L) or 'all'")
    parser.add_argument("--config", default=None, help="Optional config YAML path")
    args = parser.parse_args()

    base_cfg = load_config(args.config) if args.config else AppConfig()
    setup_logging(base_cfg)

    probes: Dict[str, Callable[[AppConfig, Path], Dict[str, Any]]] = {
        "P-H": probe_ph_farmed_execution,
        "P-I": probe_pi_cache_hit,
        "P-J": probe_pj_calculator,
        "P-K": probe_pk_paint_save,
        "P-L": probe_pl_app_memory_promotion,
    }
    selected = list(probes.keys()) if args.probe.lower() == "all" else [args.probe.upper()]

    out_dir = ROOT / "benchmarks" / "results" / "smoke_p4_5"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    results: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="parasite_p4_5_") as tmp:
        work_dir = Path(tmp)
        for pid in selected:
            fn = probes.get(pid)
            if fn is None:
                logger.error("Unknown probe ID: %s", pid)
                return 2
            logger.info("=== Running Probe %s ===", pid)
            try:
                results[pid] = fn(base_cfg, work_dir)
            except Exception as exc:
                logger.exception("Probe %s raised exception", pid)
                results[pid] = {"passed": False, "error": str(exc)}

    all_passed = all(bool(r.get("passed")) for r in results.values())
    payload = {
        "timestamp": ts,
        "all_passed": all_passed,
        "results": results,
    }
    receipt_path = out_dir / f"smoke_p4_5_{ts}.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Smoke receipt written to %s (all_passed=%s)", receipt_path, all_passed)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
