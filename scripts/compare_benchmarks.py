#!/usr/bin/env python3
"""
scripts/compare_benchmarks.py - Comparative Scorecard Generator for ParasiteAI Benchmarks.

Compares two benchmark JSON results (e.g. baseline_p0 vs baseline_p1), computes
empirical deltas, generates side-by-side Markdown scorecards, and assesses Stage Gates.

Usage:
    python scripts/compare_benchmarks.py --baseline benchmarks/results/baseline_p0.json --candidate benchmarks/results/baseline_p1.json
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_benchmark(path: Path) -> Dict[str, Any]:
    """Loads benchmark JSON file."""
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_delta_pct(val_b: float, val_c: float, higher_is_better: bool = True) -> str:
    """Formats a percentage difference with sign and color indicator."""
    delta = val_c - val_b
    sign = "+" if delta > 0 else ""
    formatted = f"{sign}{delta:.1f}%"
    if abs(delta) < 0.01:
        return "0.0%"
    if (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
        return f"**{formatted}** (Improved)"
    return f"{formatted} (Regressed)"


def format_delta_num(val_b: float, val_c: float, higher_is_better: bool = False, unit: str = "") -> str:
    """Formats numeric delta."""
    delta = val_c - val_b
    sign = "+" if delta > 0 else ""
    formatted = f"{sign}{delta:.2f}{unit}"
    if abs(delta) < 0.001:
        return f"0.00{unit}"
    if (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
        return f"**{formatted}** (Improved)"
    return f"{formatted} (Regressed)"


def generate_comparison_markdown(
    base_data: Dict[str, Any],
    cand_data: Dict[str, Any],
    base_name: str = "baseline_p0",
    cand_name: str = "baseline_p1",
) -> str:
    """Generates Markdown comparison report."""
    base_m = base_data.get("metrics", {})
    cand_m = cand_data.get("metrics", {})

    b_pass = float(base_m.get("verified_pass_rate", 0.0))
    c_pass = float(cand_m.get("verified_pass_rate", 0.0))

    b_false_done = float(base_m.get("false_done_rate", 0.0))
    c_false_done = float(cand_m.get("false_done_rate", 0.0))

    b_med_lat = float(base_m.get("median_step_sec", 0.0))
    c_med_lat = float(cand_m.get("median_step_sec", 0.0))

    b_p90_lat = float(base_m.get("p90_step_sec", 0.0))
    c_p90_lat = float(cand_m.get("p90_step_sec", 0.0))

    lines = [
        f"# ParasiteAI Comparative Benchmark Scorecard: {base_name} vs {cand_name}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Baseline (`{base_name}`):** {base_data.get('total_tasks', len(base_data.get('tasks', [])))} Tasks  ",
        f"**Candidate (`{cand_name}`):** {cand_data.get('total_tasks', len(cand_data.get('tasks', [])))} Tasks  ",
        "",
        "## 1. Executive Summary & Key Metric Deltas",
        "| Metric | Baseline (`" + base_name + "`) | Candidate (`" + cand_name + "`) | Empirical Delta | Target Gate |",
        "| :--- | :---: | :---: | :---: | :--- |",
        f"| **Overall Pass Rate** | {b_pass:.1f}% ({base_m.get('verified_pass_count', 0)}) | **{c_pass:.1f}%** ({cand_m.get('verified_pass_count', 0)}) | {format_delta_pct(b_pass, c_pass, True)} | Lift over P0 |",
        f"| **False-`DONE` Rate** | {b_false_done:.1f}% ({base_m.get('false_done_count', 0)}) | **{c_false_done:.1f}%** ({cand_m.get('false_done_count', 0)}) | {format_delta_pct(b_false_done, c_false_done, False)} | <= 10.0% |",
        f"| **Median Step Latency** | {b_med_lat:.3f}s | **{c_med_lat:.3f}s** | {format_delta_num(b_med_lat, c_med_lat, False, 's')} | <= 3.0s |",
        f"| **P90 Step Latency** | {b_p90_lat:.3f}s | **{c_p90_lat:.3f}s** | {format_delta_num(b_p90_lat, c_p90_lat, False, 's')} | <= 6.0s |",
        f"| **Mean Duration / Task** | {base_m.get('mean_duration_sec', 0.0):.1f}s | **{cand_m.get('mean_duration_sec', 0.0):.1f}s** | {format_delta_num(base_m.get('mean_duration_sec', 0.0), cand_m.get('mean_duration_sec', 0.0), False, 's')} | Lower is better |",
        f"| **Hardware Interrupts** | {base_m.get('total_hardware_interrupts', 0)} | **{cand_m.get('total_hardware_interrupts', 0)}** | 0 | 0 (No self-interruption) |",
        "",
        "## 2. Difficulty Level Breakdown",
        "| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |",
        "| :--- | :---: | :---: | :---: | :--- |",
    ]

    base_levels = base_m.get("levels", {})
    cand_levels = cand_m.get("levels", {})
    for lvl in ("L1", "L2", "L3"):
        bl = base_levels.get(lvl, {})
        cl = cand_levels.get(lvl, {})
        b_rate = float(bl.get("pass_rate", 0.0))
        c_rate = float(cl.get("pass_rate", 0.0))
        target_str = ">= 50%" if lvl == "L1" else (">= 25%" if lvl == "L2" else "Informational")
        lines.append(
            f"| **{lvl}** | {b_rate:.1f}% ({bl.get('passed', 0)}/{bl.get('total', 0)}) | **{c_rate:.1f}%** ({cl.get('passed', 0)}/{cl.get('total', 0)}) | {format_delta_pct(b_rate, c_rate, True)} | {target_str} |"
        )

    # Task by Task Transition Matrix
    lines.extend(
        [
            "",
            "## 3. Task-by-Task Transition Matrix",
            "| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |",
            "| :--- | :--- | :---: | :--- | :--- | :--- | :--- |",
        ]
    )

    base_tasks = {t["id"]: t for t in base_data.get("tasks", [])}
    cand_tasks = {t["id"]: t for t in cand_data.get("tasks", [])}

    all_ids = list(base_tasks.keys())
    for tid in cand_tasks.keys():
        if tid not in all_ids:
            all_ids.append(tid)

    for tid in all_ids:
        bt = base_tasks.get(tid, {})
        ct = cand_tasks.get(tid, {})
        name = ct.get("name") or bt.get("name") or tid
        lvl = ct.get("level") or bt.get("level") or "N/A"

        b_pass_task = bt.get("verifier_passed", False)
        c_pass_task = ct.get("verifier_passed", False)

        b_outcome = "✅ PASS" if b_pass_task else f"❌ {bt.get('failure_mode', bt.get('exit_reason', 'FAIL'))}"
        c_outcome = "✅ PASS" if c_pass_task else f"❌ {ct.get('failure_mode', ct.get('exit_reason', 'FAIL'))}"

        if not b_pass_task and c_pass_task:
            verdict = "🟢 **NEW PASS**"
        elif b_pass_task and not c_pass_task:
            verdict = "🔴 **REGRESSION**"
        elif b_pass_task and c_pass_task:
            verdict = "✅ MAINTAINED PASS"
        else:
            verdict = "⚪ UNRESOLVED"

        b_dur = float(bt.get("duration_sec", 0.0))
        c_dur = float(ct.get("duration_sec", 0.0))
        dur_delta = c_dur - b_dur
        dur_str = f"{'+' if dur_delta > 0 else ''}{dur_delta:.1f}s"

        lines.append(
            f"| `{tid}` | {name} | {lvl} | {b_outcome} | {c_outcome} | {verdict} | {dur_str} |"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="ParasiteAI Benchmark Comparator")
    parser.add_argument("--baseline", required=True, help="Path to baseline JSON (e.g. baseline_p0.json)")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON (e.g. baseline_p1.json)")
    parser.add_argument("--output", help="Optional output Markdown file path")
    args = parser.parse_args()

    base_path = Path(args.baseline)
    cand_path = Path(args.candidate)

    base_data = load_benchmark(base_path)
    cand_data = load_benchmark(cand_path)

    md = generate_comparison_markdown(
        base_data,
        cand_data,
        base_name=base_path.stem,
        cand_name=cand_path.stem,
    )

    out_file = Path(args.output) if args.output else cand_path.parent / f"{base_path.stem}_vs_{cand_path.stem}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"[+] Comparative scorecard written to: {out_file}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
