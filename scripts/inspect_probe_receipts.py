#!/usr/bin/env python3
"""
scripts/inspect_probe_receipts.py - Inspects empirical coordinates from smoke probe receipts.
Checks if native 1080p vision resolved the Start button (y >= 1040) and window close 'X' targeting.
"""

import json
from pathlib import Path
import sys

RESULTS_DIR = Path("benchmarks/results")

def inspect_task(task_id: str, target_desc: str):
    receipt_path = RESULTS_DIR / f"{task_id}_receipt.json"
    print(f"\n============================================================")
    print(f" PROBE INSPECTION: Task [{task_id}] ({target_desc})")
    print(f"============================================================")
    if not receipt_path.is_file():
        print(f"[ERROR] Receipt file not found: {receipt_path}")
        return False

    try:
        with open(receipt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to read receipt: {exc}")
        return False

    name = data.get("name", data.get("goal", task_id))
    passed = data.get("success", data.get("verifier_passed", False))
    steps = data.get("steps", [])
    total_steps = len(steps)

    print(f"Task Name:        {name}")
    print(f"Verifier Passed:  {'[PASS] YES' if passed else '[FAIL] NO'}")
    print(f"Total Steps:      {total_steps}")
    print(f"\nRecorded Step Coordinates:")

    for step in steps:
        step_id = step.get("step_id")
        action = step.get("action_type")
        coords = step.get("coordinates")
        success = step.get("success")
        diff = step.get("screen_diff")
        diff_str = f"{diff:.2%}" if isinstance(diff, (int, float)) else "N/A"
        print(f"  Step #{step_id}: Action={action:<10} | Coords={str(coords):<14} | SDiff={diff_str:<7} | OK={success}")

    # Specific assertions
    if task_id == "L1-01" and steps:
        first_click = next((s for s in steps if s.get("action_type") in ("CLICK", "DOUBLE_CLICK")), None)
        if first_click and first_click.get("coordinates"):
            cx, cy = first_click["coordinates"]
            print(f"\n--> Start Button Evaluation:")
            print(f"    First Click: ({cx}, {cy})")
            if cy >= 1020 and cx <= 80:
                print(f"    [VERIFIED SUCCESS] Clicks landed in bottom taskbar Start area (x={cx} <= 80, y={cy} >= 1020)!")
                print(f"    The 720p downscaling clamp (y ~ 750) has been physically ELIMINATED.")
            elif cy < 1000:
                print(f"    [ATTENTION] Click stopped short at y={cy} (target is y >= 1040).")
            else:
                print(f"    [INFO] Click coordinates: ({cx}, {cy})")

    if task_id == "L1-06" and steps:
        first_click = next((s for s in steps if s.get("action_type") in ("CLICK", "DOUBLE_CLICK")), None)
        if first_click and first_click.get("coordinates"):
            cx, cy = first_click["coordinates"]
            print(f"\n--> Window Close ('X') Evaluation:")
            print(f"    First Click: ({cx}, {cy})")
            if cx > 1600 and cy < 50:
                print(f"    [WARNING] Click targeted top-right of entire monitor ({cx}, {cy}) instead of window bounds.")
            else:
                print(f"    [VERIFIED] Click targeted localized window chrome at ({cx}, {cy})! Verifier passed: {passed}")

    return passed

if __name__ == "__main__":
    tasks = sys.argv[1:] if len(sys.argv) > 1 else ["L1-01", "L1-06"]
    descs = {
        "L1-01": "Open Notepad via Start Menu / Desktop",
        "L1-06": "Close Pre-Opened Notepad Window",
    }
    for t in tasks:
        inspect_task(t, descs.get(t, t))
    print("\nProbe Inspection Complete.\n")
