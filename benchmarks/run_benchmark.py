#!/usr/bin/env python3
"""
benchmarks/run_benchmark.py - Hands-Off Windows 10 Desktop Benchmark Runner.

Executes the 20-task benchmark suite defined in benchmarks/suite.yaml (plus 3 optional
Stretch probes), establishes deterministic pre-task preconditions via SETUP_REGISTRY,
validates objective OS side-effects using VERIFIER_REGISTRY, detects false-DONE
hallucinations, and compiles comprehensive metrics scorecards.

Features:
- Pre-flight interactive desktop & GPU check (guards against silent BitBlt sandbox blocks).
- Incremental checkpointing: saves report & JSON after every completed task.
- Resume capability (--resume): skips already completed tasks upon restart.
- Max steps cap (--max-steps-cap): bounds step execution for faster baseline iteration.
- Failure mode taxonomy classification for comprehensive diagnostic reports.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import yaml

from benchmarks.verifiers import (
    SETUP_REGISTRY,
    VERIFIER_REGISTRY,
    cleanup_benchmark_processes,
    run_setup,
    run_verifier,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("parasite_ai.benchmarks")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def check_interactive_desktop_access(allow_headless: bool = False) -> Tuple[bool, str]:
    """
    Verifies that the current execution environment has real Windows desktop
    graphics and accessibility access (not a restricted CI sandbox where BitBlt is blocked).
    """
    if allow_headless:
        return True, "Headless simulation mode allowed"

    from parasite_ai.vision.capture import ScreenCapture

    capturer = ScreenCapture()
    frame = capturer.capture_screen()
    if (
        capturer.last_capture_backend_used == "synthetic"
        or frame is None
        or frame.size == 0
        or np.all(frame == 0)
    ):
        return False, (
            "Windows GDI BitBlt screen capture is blocked or unavailable (synthetic blank frame returned). "
            "The benchmark runner must be executed from an interactive Windows desktop console session "
            "(e.g. by running 'run_baseline_p0.bat') rather than an unprivileged background/sandbox token."
        )

    from parasite_ai.vision.grounding import ScreenGrounder

    grounder = ScreenGrounder()
    elements = grounder.ground()
    if not elements:
        return False, (
            "UI Automation tree walk returned 0 interactive elements on the desktop. "
            "Ensure the desktop session is active and not locked or running under an unprivileged service token."
        )

    return (
        True,
        f"Interactive desktop access verified (backend: {capturer.last_capture_backend_used}, elements: {len(elements)})",
    )


def reset_cursor_to_neutral() -> None:
    """Parks physical cursor at screen center between tasks to prevent hover lock or stale tooltip activation."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.SetCursorPos(960, 540)
        except Exception:
            pass


class SuitePanicMonitor:
    """Listens for Ctrl+Alt+K / Ctrl+Alt+Q at the benchmark suite level and kills active tasks immediately."""

    def __init__(self) -> None:
        self.aborted = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_id: int = 0
        self._ready = threading.Event()

    def start(self) -> None:
        if sys.platform != "win32" or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_hotkey_loop,
            name="BenchmarkSuitePanicMonitor",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=1.5)

    def stop(self) -> None:
        if sys.platform == "win32" and self._thread_id:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = 0

    def _run_hotkey_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        # Ctrl+Alt+K (9001) and Ctrl+Alt+Q (9002)
        try:
            user32.RegisterHotKey(None, 9001, 0x0001 | 0x0002 | 0x4000, 0x4B)
            user32.RegisterHotKey(None, 9002, 0x0001 | 0x0002 | 0x4000, 0x51)
        except Exception:
            pass
        self._ready.set()

        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in (9001, 9002):  # WM_HOTKEY
                logger.critical("Suite-wide emergency panic hotkey detected (Ctrl+Alt+K/Q)! Halting benchmark suite...")
                self.aborted.set()
                try:
                    cleanup_benchmark_processes()
                except Exception:
                    pass
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.UnregisterHotKey(None, 9001)
            user32.UnregisterHotKey(None, 9002)
        except Exception:
            pass


def classify_failure_mode(task_res: Dict[str, Any]) -> str:
    """Categorizes the primary failure mode of a benchmark task episode."""
    if task_res.get("verifier_passed"):
        return "PASS"
    if task_res.get("exit_reason") == "SETUP_ERROR":
        return "SETUP_ERROR"
    if task_res.get("false_done"):
        return "FALSE_DONE"
    if task_res.get("exit_reason") == "PANIC":
        return "PANIC_ABORT"
    if int(task_res.get("hardware_interrupt_count", 0)) > 0:
        return "HARDWARE_PREEMPTED"
    if task_res.get("exit_reason") == "LOOP_STAGNATION":
        return "LOOP_STAGNATION"
    err = str(task_res.get("error") or "")
    if "Target ID" in err or "not found in grounded elements" in err:
        return "TARGET_MISFIRE"
    if task_res.get("exit_reason") in ("MAX_STEPS", "TIMEOUT"):
        return "MAX_STEPS_EXHAUSTED"
    return "UNKNOWN_FAILURE"


def load_suite(suite_path: Path, include_stretch: bool = False) -> List[Dict[str, Any]]:
    """Loads and validates benchmark task definitions from YAML."""
    if not suite_path.exists():
        raise FileNotFoundError(f"Benchmark suite file not found: {suite_path}")
    data = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    tasks = list(data.get("tasks", []))
    if include_stretch:
        tasks.extend(data.get("stretch_tasks", []))
    return tasks


def run_single_task(
    task: Dict[str, Any],
    results_dir: Path,
    python_exe: str,
    brain_mode: Optional[str] = None,
    headless: bool = False,
    max_steps_cap: Optional[int] = None,
    suite_aborted: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Runs a single benchmark task episode and executes its ground-truth OS verifier."""
    task_id = task["id"]
    name = task["name"]
    tier = task.get("tier", "Unknown")
    level = task.get("level", "L1")
    prompt = task["prompt"]
    max_steps = int(task.get("max_steps", 10))
    if max_steps_cap is not None and max_steps_cap > 0:
        max_steps = min(max_steps, int(max_steps_cap))

    timeout_sec = int(task.get("timeout_sec", 45))
    setup_name = task.get("setup", "clean_workspace")
    setup_params = task.get("setup_params", {})
    verifier_name = task.get("verifier", "")
    verifier_params = task.get("params", {})

    logger.info("------------------------------------------------------------")
    logger.info("Starting Task [%s]: '%s' (%s, %s)", task_id, name, tier, level)
    logger.info(
        "Prompt: %r | Setup: %s | Verifier: %s | Max Steps: %d | Timeout: %ds",
        prompt,
        setup_name,
        verifier_name,
        max_steps,
        timeout_sec,
    )

    # 1. Establish deterministic pre-task precondition
    setup_ok = run_setup(setup_name, setup_params)
    if not setup_ok:
        logger.error("Pre-task setup '%s' failed for [%s]. Aborting task.", setup_name, task_id)
        cleanup_benchmark_processes()
        res = {
            "id": task_id,
            "name": name,
            "tier": tier,
            "level": level,
            "prompt": prompt,
            "setup": setup_name,
            "setup_ok": False,
            "verifier": verifier_name,
            "verifier_passed": False,
            "agent_success": False,
            "claimed_done": False,
            "false_done": False,
            "exit_code": -2,
            "exit_reason": "SETUP_ERROR",
            "total_steps": 0,
            "step_latencies_sec": [],
            "hardware_interrupt_count": 0,
            "total_strikes": 0,
            "highest_tier_reached": "NONE",
            "duration_sec": 0.0,
            "timed_out": False,
            "error": f"Pre-task setup '{setup_name}' failed",
        }
        res["failure_mode"] = classify_failure_mode(res)
        return res

    reset_cursor_to_neutral()
    time.sleep(0.5)

    receipt_file = results_dir / f"{task_id}_receipt.json"
    if receipt_file.exists():
        receipt_file.unlink()

    # 2. Build execution command
    cmd = [
        python_exe,
        "-m",
        "parasite_ai.main",
        "--goal",
        prompt,
        "--max-steps",
        str(max_steps),
        "--auto-exit-on-complete",
        "--episode-report",
        str(receipt_file),
    ]
    if brain_mode:
        cmd.extend(["--brain-mode", brain_mode])
    if headless:
        cmd.append("--headless")

    t_start = time.time()
    exit_code = -1
    timed_out = False
    suite_panic = False

    logs_dir = results_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{task_id}.log"

    try:
        try:
            with open(log_file, "w", encoding="utf-8", errors="replace") as log_fh:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                deadline = t_start + timeout_sec
                while proc.poll() is None:
                    if suite_aborted is not None and suite_aborted.is_set():
                        suite_panic = True
                        proc.kill()
                        proc.wait(timeout=5)
                        break
                    if time.time() >= deadline:
                        timed_out = True
                        logger.warning("Task [%s] timed out after %ds", task_id, timeout_sec)
                        proc.kill()
                        proc.wait(timeout=5)
                        break
                    time.sleep(0.2)
                else:
                    exit_code = proc.returncode
        except Exception as exc:
            logger.error("Task [%s] subprocess invocation failed: %s", task_id, exc)

        wall_duration = round(time.time() - t_start, 3)

        # 3. Read generated EpisodeReceipt (Stint P0.3 + P4.6.6 schema)
        receipt: Dict[str, Any] = {}
        if receipt_file.exists():
            try:
                receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("Failed to parse receipt JSON: %s", exc)

        agent_success = bool(receipt.get("success", False))
        claimed_done = bool(receipt.get("claimed_done", agent_success))
        raw_exit_reason = str(receipt.get("exit_reason") or "").strip()
        if suite_panic:
            exit_reason = "PANIC"
        elif raw_exit_reason and raw_exit_reason != "IN_PROGRESS":
            exit_reason = raw_exit_reason
        else:
            exit_reason = "TIMEOUT" if timed_out else f"EXIT_{exit_code}"
        total_steps = int(receipt.get("total_steps", 0))
        step_latencies = list(receipt.get("step_latencies_sec", []))
        hw_interrupts = int(receipt.get("hardware_interrupt_count", 0))
        total_strikes = int(receipt.get("total_strikes", 0))
        highest_tier = str(receipt.get("highest_tier_reached", "TIER_1_LOCAL"))

        # 4. Execute programmatic ground-truth verifier BEFORE post-task cleanup
        logger.info("Running verifier '%s' for [%s]...", verifier_name, task_id)
        verifier_passed = run_verifier(verifier_name, verifier_params)

        # 5. Check false-DONE anomaly (agent claimed DONE without objective OS side-effect)
        false_done = (claimed_done or agent_success) and not verifier_passed
    finally:
        # 6. Cold-to-cold teardown: kill lingering parasite_ai.main hooks, release modifiers, & close target apps
        cleanup_benchmark_processes()
        reset_cursor_to_neutral()

    res = {
        "id": task_id,
        "name": name,
        "tier": tier,
        "level": level,
        "prompt": prompt,
        "setup": setup_name,
        "setup_ok": True,
        "verifier": verifier_name,
        "verifier_passed": verifier_passed,
        "agent_success": agent_success,
        "claimed_done": claimed_done,
        "false_done": false_done,
        "exit_code": exit_code,
        "exit_reason": exit_reason,
        "total_steps": total_steps,
        "min_steps_with_skill": int(task.get("min_steps_with_skill", 0)),
        "min_steps_no_skill": int(task.get("min_steps_no_skill", 0)),
        "max_steps": max_steps,
        "step_latencies_sec": step_latencies,
        "hardware_interrupt_count": hw_interrupts,
        "total_strikes": total_strikes,
        "highest_tier_reached": highest_tier,
        "plan_source": str(receipt.get("plan_source") or "local"),
        "skill_id": receipt.get("skill_id"),
        "farmed_plan_id": receipt.get("farmed_plan_id"),
        "fast_path_steps": int(receipt.get("fast_path_steps", 0)),
        "parasite_invocations": int(receipt.get("parasite_invocations", 0)),
        "parasite_status": receipt.get("parasite_status"),
        "veto_count": int(receipt.get("veto_count", 0)),
        "fast_path_abort_reason": receipt.get("fast_path_abort_reason"),
        "log_file": str(log_file),
        "duration_sec": wall_duration,
        "timed_out": timed_out,
        "error": receipt.get("error"),
    }
    res["failure_mode"] = classify_failure_mode(res)

    logger.info(
        "Result [%s]: Verifier=%s | ClaimedDone=%s | FalseDone=%s | Mode=%s | Steps=%d | Interrupts=%d | Duration=%.2fs",
        task_id,
        "PASS" if verifier_passed else "FAIL",
        claimed_done,
        false_done,
        res["failure_mode"],
        total_steps,
        hw_interrupts,
        wall_duration,
    )

    return res


def _percentile(sorted_vals: List[float], pct: float) -> float:
    """Computes a linear-interpolated percentile from a sorted list of floats."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 3)
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac, 3)


def compute_metrics(task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes summary metrics, latency percentiles, and pass rates across levels."""
    total = len(task_results)
    if total == 0:
        return {}

    verified_passes = sum(1 for r in task_results if r.get("verifier_passed"))
    agent_successes = sum(1 for r in task_results if r.get("claimed_done", r.get("agent_success")))
    false_dones = sum(1 for r in task_results if r.get("false_done"))
    loop_aborts = sum(1 for r in task_results if r.get("exit_reason") == "LOOP_STAGNATION")
    total_interrupts = sum(int(r.get("hardware_interrupt_count", 0)) for r in task_results)

    # Metrics by difficulty level (L1, L2, L3, Stretch)
    levels: Dict[str, Dict[str, Any]] = {}
    for lvl in ("L1", "L2", "L3", "Stretch"):
        lvl_tasks = [r for r in task_results if r.get("level") == lvl]
        if lvl_tasks:
            passes = sum(1 for r in lvl_tasks if r.get("verifier_passed"))
            levels[lvl] = {
                "total": len(lvl_tasks),
                "passed": passes,
                "pass_rate": round((passes / len(lvl_tasks)) * 100, 1),
            }

    # Failure modes breakdown
    failure_modes: Dict[str, int] = {}
    for r in task_results:
        fm = r.get("failure_mode") or classify_failure_mode(r)
        failure_modes[fm] = failure_modes.get(fm, 0) + 1

    durations = [float(r.get("duration_sec", 0.0)) for r in task_results]
    steps = [int(r.get("total_steps", 0)) for r in task_results]
    eff_ratios = [
        float(r.get("total_steps", 0)) / float(r["min_steps_with_skill"])
        for r in task_results
        if r.get("verifier_passed") and int(r.get("min_steps_with_skill", 0)) > 0
    ]
    mean_eff_ratio = round(sum(eff_ratios) / len(eff_ratios), 2) if eff_ratios else 0.0

    all_step_latencies: List[float] = []
    for r in task_results:
        for lat in r.get("step_latencies_sec", []) or []:
            all_step_latencies.append(float(lat))
    all_step_latencies.sort()

    median_step_sec = round(statistics.median(all_step_latencies), 3) if all_step_latencies else 0.0
    p90_step_sec = _percentile(all_step_latencies, 90.0) if all_step_latencies else 0.0

    return {
        "total_tasks": total,
        "verified_pass_count": verified_passes,
        "verified_pass_rate": round((verified_passes / total) * 100, 1),
        "agent_claimed_success_rate": round((agent_successes / total) * 100, 1),
        "false_done_count": false_dones,
        "false_done_rate": round((false_dones / total) * 100, 1),
        "loop_abort_count": loop_aborts,
        "total_hardware_interrupts": total_interrupts,
        "mean_steps": round(sum(steps) / total, 2) if total else 0.0,
        "mean_step_efficiency_ratio": mean_eff_ratio,
        "mean_duration_sec": round(sum(durations) / total, 2) if total else 0.0,
        "median_step_sec": median_step_sec,
        "p90_step_sec": p90_step_sec,
        "levels": levels,
        "failure_modes": failure_modes,
    }


def format_markdown_report(
    metrics: Dict[str, Any],
    task_results: List[Dict[str, Any]],
    title: str,
    gpu_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates a GitHub-flavored Markdown scorecard report."""
    gpu_desc = "RTX 4060 (8,188 MiB Dedicated, 6,500 MB Budget)"
    if gpu_info:
        gpu_desc = f"{gpu_info.get('gpu_name', 'NVIDIA GPU')} ({gpu_info.get('memory_total_mb', 8188)} MB VRAM, Driver {gpu_info.get('driver_version', 'N/A')})"

    lines = [
        f"# {title}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Host Environment:** Windows 10 / {gpu_desc}  ",
        f"**Total Tasks:** {metrics.get('total_tasks', 0)}  ",
        f"**Ground-Truth Pass Rate:** **{metrics.get('verified_pass_rate', 0.0)}%** ({metrics.get('verified_pass_count', 0)}/{metrics.get('total_tasks', 0)})  ",
        f"**Claimed DONE Rate:** {metrics.get('agent_claimed_success_rate', 0.0)}%  ",
        f"**False DONE Rate:** {metrics.get('false_done_rate', 0.0)}% ({metrics.get('false_done_count', 0)} occurrences)  ",
        f"**Mean Steps:** {metrics.get('mean_steps', 0.0)} | **Step Efficiency (vs Ideal Skill Min):** {metrics.get('mean_step_efficiency_ratio', 0.0)}x | **Mean Duration:** {metrics.get('mean_duration_sec', 0.0)}s  ",
        f"**Median Step Latency:** {metrics.get('median_step_sec', 0.0)}s | **P90 Step Latency:** {metrics.get('p90_step_sec', 0.0)}s  ",
        f"**Hardware Interrupts:** {metrics.get('total_hardware_interrupts', 0)}  ",
        "",
        "## Performance by Difficulty Level",
        "| Level | Passed / Total | Pass Rate | Gate Target |",
        "| :--- | :--- | :--- | :--- |",
    ]

    gate_targets = {"L1": ">= 70%", "L2": ">= 40%", "L3": "Informational", "Stretch": "Informational"}
    for lvl, data in metrics.get("levels", {}).items():
        lines.append(
            f"| **{lvl}** | {data['passed']} / {data['total']} | **{data['pass_rate']}%** | {gate_targets.get(lvl, 'N/A')} |"
        )

    # Failure Mode Taxonomy Breakdown
    if metrics.get("failure_modes"):
        lines.extend(
            [
                "",
                "## Failure Mode Taxonomy",
                "| Failure Category | Occurrences | Description |",
                "| :--- | :---: | :--- |",
            ]
        )
        desc_map = {
            "PASS": "Task verified successfully by objective OS verifier.",
            "FALSE_DONE": "Model claimed DONE, but OS ground-truth state failed.",
            "TARGET_MISFIRE": "Model emitted target ID not found in grounded elements.",
            "LOOP_STAGNATION": "Model repeated actions without screen change (3 consecutive strikes).",
            "MAX_STEPS_EXHAUSTED": "Cognitive step budget exhausted before goal completion.",
            "HARDWARE_PREEMPTED": "Operator physical mouse/keyboard touch paused or preempted episode.",
            "PANIC_ABORT": "Operator emergency panic hotkey triggered abort.",
            "SETUP_ERROR": "Pre-task environment setup precondition failed.",
            "UNKNOWN_FAILURE": "Unhandled exception or unmapped failure.",
        }
        for mode, count in sorted(metrics["failure_modes"].items(), key=lambda x: -x[1]):
            lines.append(f"| `{mode}` | {count} | {desc_map.get(mode, 'N/A')} |")

    lines.extend(
        [
            "",
            "## Detailed Task Scorecard",
            "| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Plan Source | Steps (Act/MinS/MinL/Max) | Duration | Exit Reason |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :--- |",
        ]
    )

    for r in task_results:
        v_icon = "✅ PASS" if r.get("verifier_passed") else "❌ FAIL"
        a_icon = "DONE" if r.get("claimed_done", r.get("agent_success")) else "FAIL"
        mode_str = r.get("failure_mode") or classify_failure_mode(r)
        psrc = str(r.get("plan_source") or "local")
        sid = r.get("skill_id")
        fpid = r.get("farmed_plan_id")
        if sid:
            plan_col = f"`{psrc}` ({sid})"
        elif fpid is not None:
            plan_col = f"`{psrc}` (#{fpid})"
        else:
            plan_col = f"`{psrc}`"
        min_s = r.get("min_steps_with_skill", "-")
        min_l = r.get("min_steps_no_skill", "-")
        max_s = r.get("max_steps", "-")
        steps_col = f"{r['total_steps']} / {min_s} / {min_l} / {max_s}"
        lines.append(
            f"| `{r['id']}` | {r['name']} | {r['tier']} | {r['level']} | {v_icon} | {a_icon} | `{mode_str}` | {plan_col} | {steps_col} | {r['duration_sec']}s | `{r['exit_reason']}` |"
        )

    return "\n".join(lines)


def run_dry_verify(tasks: List[Dict[str, Any]]) -> int:
    """
    Executes the pre-task setup hook and teardown lifecycle for all selected tasks
    without invoking the LLM, certifying that setup hooks and verifier bindings work on Windows 10.
    """
    logger.info("============================================================")
    logger.info(" ParasiteAI Benchmark Dry-Verify Self-Check (%d Tasks)", len(tasks))
    logger.info("============================================================")
    all_ok = True
    for t in tasks:
        tid = t["id"]
        setup_name = t.get("setup", "clean_workspace")
        setup_params = t.get("setup_params", {})
        verifier_name = t.get("verifier", "")

        if setup_name not in SETUP_REGISTRY:
            logger.error("[%s] Unknown setup hook: %s", tid, setup_name)
            all_ok = False
            continue
        if verifier_name not in VERIFIER_REGISTRY:
            logger.error("[%s] Unknown verifier: %s", tid, verifier_name)
            all_ok = False
            continue

        setup_ok = run_setup(setup_name, setup_params)
        cleanup_benchmark_processes()
        status_str = "OK" if setup_ok else "FAIL"
        logger.info(
            "[%s] %-45s | Setup=%-28s [%s] | Verifier=%s",
            tid,
            t["name"],
            setup_name,
            status_str,
            verifier_name,
        )
        if not setup_ok:
            all_ok = False

    cleanup_benchmark_processes()
    logger.info("============================================================")
    logger.info(" Dry-Verify Status: %s", "PASSED" if all_ok else "FAILED")
    logger.info("============================================================")
    return 0 if all_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ParasiteAI Windows 10 Desktop Benchmark Harness")
    parser.add_argument("--suite", type=str, default="benchmarks/suite.yaml", help="Path to suite YAML file")
    parser.add_argument("--tier", type=str, default=None, help="Filter tasks by tier (e.g. Tier_A, Tier_B)")
    parser.add_argument("--level", type=str, default=None, help="Filter tasks by level (L1, L2, L3, Stretch)")
    parser.add_argument("--task", type=str, default=None, help="Run a specific task ID (e.g. L1-01)")
    parser.add_argument("--include-stretch", action="store_true", help="Include the 3 game/launcher Stretch probes")
    parser.add_argument("--brain-mode", type=str, default=None, help="Override brain mode (e.g. local_llm)")
    parser.add_argument("--headless", action="store_true", help="Run with simulation/offscreen flags")
    parser.add_argument("--dry-verify", action="store_true", help="Verify setup/teardown hooks without running LLM")
    parser.add_argument("--output-name", type=str, default="baseline_p0", help="Base filename for generated reports")
    parser.add_argument("--output-dir", type=str, default="benchmarks/results", help="Directory for reports")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip tasks that have already been recorded in the target JSON report",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe existing JSON/MD report and receipt files to ensure a clean benchmark run",
    )
    parser.add_argument(
        "--max-steps-cap",
        type=int,
        default=None,
        help="Upper bound on cognitive steps per task episode (useful for fast baseline runs)",
    )
    args = parser.parse_args()

    suite_path = Path(args.suite)
    include_stretch = args.include_stretch or (args.level and args.level.lower() == "stretch")
    tasks = load_suite(suite_path, include_stretch=bool(include_stretch))

    if args.tier:
        tiers = {x.strip().lower() for x in args.tier.split(",")}
        tasks = [t for t in tasks if t.get("tier", "").lower() in tiers]
    if args.level:
        levels = {x.strip().lower() for x in args.level.split(",")}
        tasks = [t for t in tasks if t.get("level", "").lower() in levels]
    if args.task:
        task_ids = {x.strip().lower() for x in args.task.split(",")}
        tasks = [t for t in tasks if t["id"].lower() in task_ids]

    if not tasks:
        logger.error("No tasks matched criteria.")
        return 1

    if args.dry_verify:
        return run_dry_verify(tasks)

    # Pre-Flight Desktop Access Check
    ok, reason = check_interactive_desktop_access(allow_headless=args.headless)
    if not ok:
        logger.error("============================================================")
        logger.error(" [SANDBOX_BLOCKED] Desktop Access Pre-Flight Check Failed:")
        logger.error(" %s", reason)
        logger.error("============================================================")
        logger.error(" To execute the hands-off baseline with real visible desktop kinematics,")
        logger.error(" please open an interactive Command Prompt / PowerShell window and run:")
        logger.error("     run_baseline_p0.bat")
        logger.error("============================================================")
        return 2

    results_dir = Path(args.output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    output_basename = args.output_name or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_benchmark"
    md_file = results_dir / f"{output_basename}.md"
    json_file = results_dir / f"{output_basename}.json"

    python_exe = sys.executable

    # Ingest GPU governance info if available
    gpu_info: Optional[Dict[str, Any]] = None
    try:
        from scripts.check_gpu_governance import query_nvidia_smi

        gpu_info = query_nvidia_smi()
    except Exception:
        pass

    # Clean run override
    if args.fresh:
        args.resume = False
        if json_file.exists():
            json_file.unlink()
        if md_file.exists():
            md_file.unlink()
        for f in results_dir.glob("*_receipt.json"):
            if not f.name.startswith("test_"):
                try:
                    f.unlink()
                except Exception:
                    pass
        logger.info("Clean run requested (--fresh): wiped previous benchmark files for %s", output_basename)

    # Check for resume
    task_results: List[Dict[str, Any]] = []
    completed_ids: set[str] = set()
    if args.resume and json_file.exists():
        try:
            existing_data = json.loads(json_file.read_text(encoding="utf-8"))
            task_results = existing_data.get("tasks", [])
            completed_ids = {r["id"] for r in task_results}
            logger.info(
                "Resuming from %s: %d tasks already recorded (%s)",
                json_file.name,
                len(completed_ids),
                sorted(completed_ids),
            )
        except Exception as exc:
            logger.warning("Could not parse existing resume file %s: %s", json_file.name, exc)

    logger.info("============================================================")
    logger.info(" ParasiteAI Benchmark Runner - %d Tasks Queued", len(tasks))
    logger.info(" Output Directory: %s | Report Base: %s", results_dir, output_basename)
    if args.max_steps_cap:
        logger.info(" Max Steps Cap: %d", args.max_steps_cap)
    logger.info("============================================================")

    cleanup_benchmark_processes()
    suite_monitor = SuitePanicMonitor()
    suite_monitor.start()
    suite_abort_requested = False
    try:
        for task in tasks:
            if suite_monitor.aborted.is_set():
                suite_abort_requested = True
                logger.critical("Suite-wide emergency panic active; stopping benchmark run.")
                break
            if task["id"] in completed_ids:
                logger.info("Skipping task [%s] (already completed in %s)", task["id"], json_file.name)
                continue

            res = run_single_task(
                task=task,
                results_dir=results_dir,
                python_exe=python_exe,
                brain_mode=args.brain_mode,
                headless=args.headless,
                max_steps_cap=args.max_steps_cap,
                suite_aborted=suite_monitor.aborted,
            )
            task_results.append(res)
            completed_ids.add(task["id"])

            # Incremental checkpointing: save immediately after each task
            metrics = compute_metrics(task_results)
            report_title = f"ParasiteAI Benchmark Report ({output_basename})"
            md_content = format_markdown_report(metrics, task_results, report_title, gpu_info=gpu_info)

            md_file.write_text(md_content, encoding="utf-8")
            json_file.write_text(
                json.dumps({"metrics": metrics, "tasks": task_results}, indent=2),
                encoding="utf-8",
            )
            logger.info("Checkpoint saved: %s and %s (%d/%d tasks)", md_file.name, json_file.name, len(task_results), len(tasks))

            if suite_monitor.aborted.is_set() or res.get("exit_reason") == "PANIC" or res.get("exit_code") == 2:
                suite_abort_requested = True
                logger.critical(
                    "Emergency panic detected on task [%s] (exit_reason=%s, exit_code=%s). Halting benchmark suite.",
                    task["id"],
                    res.get("exit_reason"),
                    res.get("exit_code"),
                )
                break

            if res.get("outcome_mode") == "HARDWARE_PREEMPTED" and sys.stdin and sys.stdin.isatty():
                logger.warning("Task [%s] was preempted by physical mouse/keyboard input. Pausing suite.", task["id"])
                try:
                    choice = input(
                        f"\n[PAUSED] Task {task['id']} preempted by physical touch. "
                        "Press Enter to resume benchmark suite, or type 'q' + Enter to stop: "
                    ).strip().lower()
                except EOFError:
                    choice = "q"
                if choice in ("q", "quit", "exit", "abort"):
                    suite_abort_requested = True
                    logger.info("Operator requested benchmark stop after hardware preemption.")
                    break
    finally:
        suite_monitor.stop()
        cleanup_benchmark_processes()
        reset_cursor_to_neutral()

    metrics = compute_metrics(task_results)
    report_title = f"ParasiteAI Benchmark Report ({output_basename})"
    md_content = format_markdown_report(metrics, task_results, report_title, gpu_info=gpu_info)

    md_file.write_text(md_content, encoding="utf-8")
    json_file.write_text(
        json.dumps({"metrics": metrics, "tasks": task_results}, indent=2),
        encoding="utf-8",
    )

    print("\n" + md_content + "\n")
    logger.info("Saved final benchmark reports to %s and %s", md_file, json_file)

    return 2 if suite_abort_requested else 0


if __name__ == "__main__":
    sys.exit(main())
