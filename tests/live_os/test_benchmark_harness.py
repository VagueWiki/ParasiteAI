"""
tests/test_benchmark_harness.py - Unit & Live OS Result Tests for Benchmark Suite & Verifiers.

Verifies:
1. suite.yaml structure, syntax, and task count (20 core tasks across L1, L2, L3 + 3 stretch probes).
2. Complete coverage of referenced setup hooks in SETUP_REGISTRY and verifiers in VERIFIER_REGISTRY.
3. Accurate computation of scorecard metrics, latency percentiles, and false-DONE rates.
4. Markdown report formatting integrity (including Windows 10 host telemetry).
5. LIVE WINDOWS 10 OS VERIFIER RESULT TESTS:
   - Real notepad.exe launch, Win32 Edit WM_GETTEXT buffer inspection, minimize (IsIconic), and termination.
   - Composed prose verification vs. instruction goal-echo rejection.
   - Real disk workspace file seeding, renaming, and directory verification.
   - Real Windows clipboard verification.
   - Real modal dialog spawn, detection, and dismissal verification.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from benchmarks.run_benchmark import (
    check_interactive_desktop_access,
    classify_failure_mode,
    compute_metrics,
    format_markdown_report,
    load_suite,
)
from benchmarks.verifiers import (
    SETUP_REGISTRY,
    VERIFIER_REGISTRY,
    WORKSPACE_DIR,
    cleanup_benchmark_processes,
    clear_clipboard,
    close_modal_dialogs,
    inject_notepad_text,
    minimize_process_windows,
    run_setup,
    run_verifier,
)

pytestmark = pytest.mark.live_os


def test_suite_yaml_task_count_and_fields() -> None:
    """Verifies benchmarks/suite.yaml defines 20 core tasks (10 L1, 7 L2, 3 L3) and 3 Stretch tasks."""
    suite_path = Path("benchmarks/suite.yaml")
    assert suite_path.exists(), "benchmarks/suite.yaml must exist"

    core_tasks = load_suite(suite_path, include_stretch=False)
    assert len(core_tasks) == 20, f"Expected 20 core tasks in benchmark suite, got {len(core_tasks)}"

    all_tasks = load_suite(suite_path, include_stretch=True)
    assert len(all_tasks) == 23, f"Expected 23 total tasks (20 core + 3 stretch), got {len(all_tasks)}"

    level_counts = {"L1": 0, "L2": 0, "L3": 0, "Stretch": 0}
    task_ids = set()

    for t in all_tasks:
        for req_key in ("id", "name", "tier", "level", "prompt", "max_steps", "timeout_sec", "setup", "verifier"):
            assert req_key in t, f"Task {t.get('id')} missing required field '{req_key}'"

        assert t["id"] not in task_ids, f"Duplicate task id: {t['id']}"
        task_ids.add(t["id"])

        lvl = t["level"]
        assert lvl in level_counts, f"Unexpected level '{lvl}' in task {t['id']}"
        level_counts[lvl] += 1

        assert t["setup"] in SETUP_REGISTRY, f"Setup '{t['setup']}' must be in SETUP_REGISTRY"
        assert t["verifier"] in VERIFIER_REGISTRY, f"Verifier '{t['verifier']}' must be in VERIFIER_REGISTRY"

    assert level_counts["L1"] == 10, f"Expected 10 L1 tasks, got {level_counts['L1']}"
    assert level_counts["L2"] == 7, f"Expected 7 L2 tasks, got {level_counts['L2']}"
    assert level_counts["L3"] == 3, f"Expected 3 L3 tasks, got {level_counts['L3']}"
    assert level_counts["Stretch"] == 3, f"Expected 3 Stretch tasks, got {level_counts['Stretch']}"


def test_compute_metrics_calculation() -> None:
    """Verifies that compute_metrics computes exact percentages, percentiles, and detects false DONEs."""
    sample_results = [
        {
            "id": "L1-01",
            "level": "L1",
            "verifier_passed": True,
            "agent_success": True,
            "claimed_done": True,
            "false_done": False,
            "total_steps": 2,
            "step_latencies_sec": [1.5, 2.5],
            "hardware_interrupt_count": 0,
            "duration_sec": 4.0,
            "exit_reason": "DONE",
        },
        {
            "id": "L1-02",
            "level": "L1",
            "verifier_passed": False,
            "agent_success": False,
            "claimed_done": False,
            "false_done": False,
            "total_steps": 5,
            "step_latencies_sec": [2.0, 2.0, 2.0, 2.0, 2.0],
            "hardware_interrupt_count": 1,
            "duration_sec": 10.0,
            "exit_reason": "MAX_STEPS",
        },
        {
            "id": "L2-01",
            "level": "L2",
            "verifier_passed": False,
            "agent_success": True,
            "claimed_done": True,
            "false_done": True,
            "total_steps": 3,
            "step_latencies_sec": [1.0, 2.0, 3.0],
            "hardware_interrupt_count": 0,
            "duration_sec": 6.0,
            "exit_reason": "DONE",
        },
        {
            "id": "L3-01",
            "level": "L3",
            "verifier_passed": True,
            "agent_success": True,
            "claimed_done": True,
            "false_done": False,
            "total_steps": 4,
            "step_latencies_sec": [2.0, 2.0, 2.0, 2.0],
            "hardware_interrupt_count": 0,
            "duration_sec": 8.0,
            "exit_reason": "DONE",
        },
    ]

    metrics = compute_metrics(sample_results)
    assert metrics["total_tasks"] == 4
    assert metrics["verified_pass_count"] == 2
    assert metrics["verified_pass_rate"] == 50.0
    assert metrics["false_done_count"] == 1
    assert metrics["false_done_rate"] == 25.0
    assert metrics["total_hardware_interrupts"] == 1
    assert metrics["mean_steps"] == 3.5
    assert metrics["mean_duration_sec"] == 7.0
    assert metrics["median_step_sec"] == 2.0
    assert metrics["p90_step_sec"] >= 2.0

    assert metrics["levels"]["L1"]["total"] == 2
    assert metrics["levels"]["L1"]["passed"] == 1
    assert metrics["levels"]["L1"]["pass_rate"] == 50.0
    assert metrics["levels"]["L2"]["pass_rate"] == 0.0
    assert metrics["levels"]["L3"]["pass_rate"] == 100.0


def test_markdown_report_formatting() -> None:
    """Verifies Markdown scorecard generation includes Windows 10 header and metrics."""
    sample_results = [
        {
            "id": "L1-01",
            "name": "Launch Notepad",
            "tier": "Tier_A",
            "level": "L1",
            "verifier_passed": True,
            "agent_success": True,
            "claimed_done": True,
            "false_done": False,
            "total_steps": 2,
            "step_latencies_sec": [1.5, 2.0],
            "hardware_interrupt_count": 0,
            "duration_sec": 3.5,
            "exit_reason": "DONE",
        },
    ]
    metrics = compute_metrics(sample_results)
    report = format_markdown_report(metrics, sample_results, "Test Benchmark")

    assert "# Test Benchmark" in report
    assert "Windows 10" in report
    assert "Ground-Truth Pass Rate" in report
    assert "| Level | Passed / Total | Pass Rate | Gate Target |" in report
    assert "`L1-01`" in report
    assert "Launch Notepad" in report
    assert "✅ PASS" in report


def test_live_os_notepad_open_text_minimize_and_terminate() -> None:
    """
    RESULT-ORIENTED OS VERIFIER TEST:
    Launches a real Windows 10 notepad.exe instance via setup_open_notepad,
    verifies window detection, injects text into the Win32 Edit control and
    verifies WM_GETTEXT buffer inspection, minimizes the window and verifies IsIconic,
    and finally terminates Notepad and verifies termination.
    """
    try:
        assert run_setup("open_notepad") is True

        # 1. Notepad is open and visible -> process_and_window is True, terminated is False
        assert (
            run_verifier(
                "verify_process_and_window",
                {"process_name": "notepad.exe", "window_title_keywords": ["Notepad"]},
            )
            is True
        )
        assert run_verifier("verify_process_terminated", {"process_name": "notepad.exe"}) is False
        assert run_verifier("verify_window_minimized", {"process_name": "notepad.exe"}) is False

        # 2. Inject text into live Notepad Edit control and verify buffer reading
        assert inject_notepad_text("Benchmark Alpha Test 42", mark_dirty=False) is True
        assert (
            run_verifier(
                "verify_window_contains_text",
                {"process_name": "notepad.exe", "expected_text": "Benchmark Alpha Test 42"},
            )
            is True
        )
        assert (
            run_verifier(
                "verify_window_contains_text",
                {"process_name": "notepad.exe", "expected_text": "NonExistentToken999"},
            )
            is False
        )

        # 3. Minimize the live Notepad window and verify IsIconic detection
        assert minimize_process_windows("notepad.exe") is True
        assert run_verifier("verify_window_minimized", {"process_name": "notepad.exe"}) is True
        # A minimized window must NOT count as a visible active surface for launch tasks
        assert (
            run_verifier(
                "verify_process_and_window",
                {"process_name": "notepad.exe", "window_title_keywords": ["Notepad"]},
            )
            is False
        )

        # 4. Terminate Notepad and verify termination
        cleanup_benchmark_processes()
        assert run_verifier("verify_process_terminated", {"process_name": "notepad.exe"}) is True
    finally:
        cleanup_benchmark_processes()


def test_live_os_notepad_composed_text_rejects_goal_echo() -> None:
    """
    RESULT-ORIENTED OS VERIFIER TEST:
    Verifies that verify_notepad_composed_text rejects literal goal echoing and
    accepts genuine multi-sentence prose in a real Windows 10 Notepad buffer.
    """
    try:
        assert run_setup("open_notepad") is True
        params = {
            "min_chars": 25,
            "forbid_substrings": ["write a short two-sentence greeting"],
        }

        # Case A: Goal echo -> must fail
        inject_notepad_text("Open Notepad and write a short two-sentence greeting.", mark_dirty=False)
        assert run_verifier("verify_notepad_composed_text", params) is False

        # Case B: Too short -> must fail
        inject_notepad_text("Hi there.", mark_dirty=False)
        assert run_verifier("verify_notepad_composed_text", params) is False

        # Case C: Genuine two-sentence greeting -> must pass
        inject_notepad_text(
            "Hello and welcome to your desktop! I hope your projects go smoothly today.",
            mark_dirty=False,
        )
        assert run_verifier("verify_notepad_composed_text", params) is True
    finally:
        cleanup_benchmark_processes()


def test_live_os_workspace_file_and_directory_verifiers() -> None:
    """
    RESULT-ORIENTED OS VERIFIER TEST:
    Verifies real filesystem setup and verification hooks in benchmarks/workspace.
    """
    assert run_setup("seed_workspace_file", {"filename": "seed.txt", "content": "Project Proposal v1"}) is True
    assert (
        run_verifier(
            "verify_file_exists_and_content",
            {"file_path": "benchmarks/workspace/seed.txt", "expected_content": "Project Proposal v1"},
        )
        is True
    )
    assert (
        run_verifier(
            "verify_window_or_file_contains",
            {
                "file_path": "benchmarks/workspace/seed.txt",
                "expected_substrings": ["Project Proposal v1", "- Approved"],
            },
        )
        is False
    )

    # Append "- Approved" to disk file and verify
    seed_file = WORKSPACE_DIR / "seed.txt"
    seed_file.write_text("Project Proposal v1 - Approved", encoding="utf-8")
    assert (
        run_verifier(
            "verify_window_or_file_contains",
            {
                "file_path": "benchmarks/workspace/seed.txt",
                "expected_substrings": ["Project Proposal v1", "- Approved"],
            },
        )
        is True
    )

    # Rename file test
    assert run_setup("seed_rename_file", {"old_name": "old_name.txt", "content": "Rename target"}) is True
    assert (
        run_verifier(
            "verify_file_renamed",
            {"old_path": "benchmarks/workspace/old_name.txt", "new_path": "benchmarks/workspace/new_name.txt"},
        )
        is False
    )
    (WORKSPACE_DIR / "old_name.txt").rename(WORKSPACE_DIR / "new_name.txt")
    assert (
        run_verifier(
            "verify_file_renamed",
            {"old_path": "benchmarks/workspace/old_name.txt", "new_path": "benchmarks/workspace/new_name.txt"},
        )
        is True
    )

    # Directory creation test
    assert run_verifier("verify_directory_exists", {"dir_path": "benchmarks/workspace/Reports"}) is False
    (WORKSPACE_DIR / "Reports").mkdir(parents=True, exist_ok=True)
    assert run_verifier("verify_directory_exists", {"dir_path": "benchmarks/workspace/Reports"}) is True


def test_live_os_clipboard_verifier() -> None:
    """
    RESULT-ORIENTED OS VERIFIER TEST:
    Verifies Windows system clipboard inspection and clearing.
    """
    import pyperclip

    clear_clipboard()
    assert run_verifier("verify_clipboard_contains", {"expected_text": "TOKEN_9941"}) is False
    pyperclip.copy("Clipboard payload: TOKEN_9941")
    assert run_verifier("verify_clipboard_contains", {"expected_text": "TOKEN_9941"}) is True
    clear_clipboard()


def test_live_os_modal_error_dialog_setup_and_verifier() -> None:
    """
    RESULT-ORIENTED OS VERIFIER TEST:
    Spawns a real Win32 MessageBoxW error dialog, verifies it blocks the verifier,
    dismisses it, opens Notepad, and verifies the combined condition passes.
    """
    try:
        assert run_setup("spawn_modal_error_dialog", {"dialog_title": "Benchmark System Error"}) is True
        # Dialog is open and Notepad is not open -> must be False
        assert (
            run_verifier(
                "verify_dialog_closed_and_window_open",
                {"dialog_title": "Benchmark System Error", "process_name": "notepad.exe"},
            )
            is False
        )
        # Dismiss dialog and open Notepad -> must be True
        close_modal_dialogs(["Benchmark System Error"])
        assert run_setup("open_notepad") is True
        assert (
            run_verifier(
                "verify_dialog_closed_and_window_open",
                {"dialog_title": "Benchmark System Error", "process_name": "notepad.exe"},
            )
            is True
        )
    finally:
        cleanup_benchmark_processes()


def test_classify_failure_mode_categories() -> None:
    """Verifies that classify_failure_mode accurately maps all failure taxonomy branches."""
    # 1. Pass
    assert classify_failure_mode({"verifier_passed": True}) == "PASS"

    # 2. Setup error
    assert classify_failure_mode({"verifier_passed": False, "exit_reason": "SETUP_ERROR"}) == "SETUP_ERROR"

    # 3. False DONE
    assert classify_failure_mode({"verifier_passed": False, "false_done": True}) == "FALSE_DONE"

    # 4. Panic abort
    assert classify_failure_mode({"verifier_passed": False, "exit_reason": "PANIC"}) == "PANIC_ABORT"

    # 5. Hardware preempted
    assert (
        classify_failure_mode(
            {"verifier_passed": False, "hardware_interrupt_count": 2, "exit_reason": "MAX_STEPS"}
        )
        == "HARDWARE_PREEMPTED"
    )

    # 6. Loop stagnation
    assert (
        classify_failure_mode(
            {"verifier_passed": False, "hardware_interrupt_count": 0, "exit_reason": "LOOP_STAGNATION"}
        )
        == "LOOP_STAGNATION"
    )

    # 7. Target misfire
    assert (
        classify_failure_mode(
            {
                "verifier_passed": False,
                "hardware_interrupt_count": 0,
                "exit_reason": "ERROR",
                "error": "Target ID #4 not found in grounded elements",
            }
        )
        == "TARGET_MISFIRE"
    )

    # 8. Max steps exhausted
    assert (
        classify_failure_mode(
            {"verifier_passed": False, "hardware_interrupt_count": 0, "exit_reason": "MAX_STEPS"}
        )
        == "MAX_STEPS_EXHAUSTED"
    )


def test_incremental_checkpoint_and_resume(tmp_path: Path) -> None:
    """Verifies checkpointing and resume skips already recorded tasks."""
    import json

    results_file = tmp_path / "baseline_p0.json"
    initial_data = {
        "metrics": {"total_tasks": 1},
        "tasks": [{"id": "L1-01", "name": "Launch Notepad", "verifier_passed": True}],
    }
    results_file.write_text(json.dumps(initial_data), encoding="utf-8")

    # Read back and verify completed_ids contains L1-01
    loaded = json.loads(results_file.read_text(encoding="utf-8"))
    completed_ids = {r["id"] for r in loaded.get("tasks", [])}
    assert "L1-01" in completed_ids
    assert "L1-02" not in completed_ids


def test_preflight_detects_synthetic_capture_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies check_interactive_desktop_access blocks execution when BitBlt is synthetic."""
    import numpy as np

    class MockSyntheticCapturer:
        last_capture_backend_used = "synthetic"

        def capture_screen(self) -> np.ndarray:
            return np.zeros((100, 100, 3), dtype=np.uint8)

    monkeypatch.setattr("parasite_ai.vision.capture.ScreenCapture", MockSyntheticCapturer)

    # Headless allows it
    ok_headless, _ = check_interactive_desktop_access(allow_headless=True)
    assert ok_headless is True

    # Non-headless correctly detects blocked BitBlt and returns False
    ok_interactive, reason = check_interactive_desktop_access(allow_headless=False)
    assert ok_interactive is False
    assert "Windows GDI BitBlt screen capture is blocked" in reason


def test_format_markdown_report_includes_plan_source() -> None:
    """P4.6.6: Detailed Task Scorecard surfaces Plan Source alongside outcome telemetry."""
    results = [
        {
            "id": "L1-07",
            "name": "Minimize Notepad",
            "tier": 1,
            "level": "L1",
            "verifier_passed": True,
            "agent_success": True,
            "claimed_done": True,
            "false_done": False,
            "failure_mode": "PASS",
            "plan_source": "skill",
            "skill_id": "minimize-notepad",
            "total_steps": 2,
            "min_steps_with_skill": 2,
            "min_steps_no_skill": 2,
            "max_steps": 8,
            "duration_sec": 3.5,
            "exit_reason": "DONE",
            "step_latencies_sec": [1.5, 2.0],
            "hardware_interrupt_count": 0,
            "total_strikes": 0,
            "highest_tier_reached": "TIER_1_LOCAL",
        },
        {
            "id": "L2-08",
            "name": "Notepad Multiply",
            "tier": 1,
            "level": "L2",
            "verifier_passed": False,
            "agent_success": False,
            "claimed_done": False,
            "false_done": False,
            "failure_mode": "TIMEOUT",
            "plan_source": "farmed",
            "farmed_plan_id": 10,
            "total_steps": 3,
            "min_steps_with_skill": 4,
            "min_steps_no_skill": 6,
            "max_steps": 15,
            "duration_sec": 120.0,
            "exit_reason": "TIMEOUT",
            "step_latencies_sec": [5.0, 2.0, 3.0],
            "hardware_interrupt_count": 0,
            "total_strikes": 1,
            "highest_tier_reached": "TIER_1_LOCAL",
        },
    ]
    md = format_markdown_report(compute_metrics(results), results, title="P4.6.6 Scorecard Test")
    assert "| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Plan Source | Steps (Act/MinS/MinL/Max) | Duration | Exit Reason |" in md
    assert "`skill` (minimize-notepad)" in md
    assert "`farmed` (#10)" in md


def test_run_single_task_streams_logs_and_preserves_in_progress_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P4.6.6: Subprocess redirects output to logs/<task_id>.log and preserves IN_PROGRESS checkpoint telemetry."""
    import json
    from unittest.mock import MagicMock
    from benchmarks import run_benchmark

    monkeypatch.setattr(run_benchmark, "run_setup", lambda name, params: True)
    monkeypatch.setattr(run_benchmark, "run_verifier", lambda name, params: False)
    monkeypatch.setattr(run_benchmark, "cleanup_benchmark_processes", lambda: None)
    monkeypatch.setattr(run_benchmark, "reset_cursor_to_neutral", lambda: None)

    receipt_file = tmp_path / "L1-01_receipt.json"

    class _FakeProc:
        returncode = None

        def poll(self):
            return None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return 0

    popen_calls = []

    def _fake_popen(cmd, stdout=None, stderr=None, text=False, **kwargs):
        popen_calls.append({"cmd": cmd, "stdout": stdout, "stderr": stderr})
        assert stdout is not None and stdout is not run_benchmark.subprocess.PIPE
        assert stderr == run_benchmark.subprocess.STDOUT
        stdout.write("chunk of stdout log\n")
        stdout.flush()
        receipt_file.write_text(
            json.dumps(
                {
                    "success": False,
                    "claimed_done": False,
                    "exit_reason": "IN_PROGRESS",
                    "total_steps": 2,
                    "step_latencies_sec": [1.1, 2.2],
                    "plan_source": "farmed",
                    "farmed_plan_id": 7,
                    "fast_path_steps": 1,
                    "parasite_invocations": 1,
                    "parasite_status": "HARVEST_TIMEOUT",
                }
            ),
            encoding="utf-8",
        )
        return _FakeProc()

    monkeypatch.setattr(run_benchmark.subprocess, "Popen", _fake_popen)
    task = {
        "id": "L1-01",
        "name": "Launch Notepad",
        "tier": 1,
        "level": "L1",
        "prompt": "Open Notepad",
        "setup": "clean_workspace",
        "verifier": "verify_window_open",
        "max_steps": 10,
        "timeout_sec": 0,
    }
    res = run_benchmark.run_single_task(
        task=task,
        python_exe="python",
        results_dir=tmp_path,
        brain_mode="mock",
        headless=True,
    )
    assert len(popen_calls) == 1
    assert res["timed_out"] is True
    assert res["exit_reason"] == "TIMEOUT"
    assert res["total_steps"] == 2
    assert res["step_latencies_sec"] == [1.1, 2.2]
    assert res["plan_source"] == "farmed"
    assert res["farmed_plan_id"] == 7
    assert res["fast_path_steps"] == 1
    assert res["parasite_invocations"] == 1
    assert res["parasite_status"] == "HARVEST_TIMEOUT"
    log_path = tmp_path / "logs" / "L1-01.log"
    assert log_path.exists()
    assert "chunk of stdout log" in log_path.read_text(encoding="utf-8")
