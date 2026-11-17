"""
scripts/farm_eval_receipts.py - Read-only Receipt & Log Farmer for Scheduled Automation.

Scans benchmarks/results/ and logs/ for un-processed active-stage receipts (and post-cutoff
benchmark receipts) against benchmarks/results/.automation_eval_cursor.json, and outputs
a compact JSON summary including the sequential stage lock (`active_stage`).
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent


def _parse_iso_epoch(ts: Any) -> float:
    if not ts or not isinstance(ts, str):
        return 0.0
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def farm_new_results(root: Path = ROOT) -> Dict[str, Any]:
    results_dir = root / "benchmarks" / "results"
    cursor_path = results_dir / ".automation_eval_cursor.json"

    processed: set[str] = set()
    cursor_data: Dict[str, Any] = {}
    if cursor_path.is_file():
        try:
            cursor_data = json.loads(cursor_path.read_text(encoding="utf-8"))
            processed = {str(x) for x in cursor_data.get("processed_receipts", [])}
        except Exception:
            cursor_data = {}

    legacy_cutoff = _parse_iso_epoch(cursor_data.get("ignore_legacy_results_before"))

    new_receipts: List[Dict[str, Any]] = []
    latest_smoke_receipt: Dict[str, Any] | None = None
    smoke_dir = results_dir / "smoke_p4_7"
    if smoke_dir.is_dir():
        smoke_files = sorted(smoke_dir.glob("*.json"))
        for p in smoke_files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                summary_entry = {
                    "file": str(p.relative_to(root)),
                    "name": p.name,
                    "app_version": data.get("app_version"),
                    "all_passed": data.get("all_passed"),
                    "results": data.get("results"),
                    "summary": data.get("summary"),
                }
                latest_smoke_receipt = {
                    "name": p.name,
                    "app_version": data.get("app_version"),
                    "all_passed": data.get("all_passed"),
                }
                if p.name not in processed:
                    new_receipts.append(summary_entry)
            except Exception as exc:
                latest_smoke_receipt = {"name": p.name, "parse_error": str(exc)}
                if p.name not in processed:
                    new_receipts.append({"file": str(p.relative_to(root)), "name": p.name, "parse_error": str(exc)})

    if results_dir.is_dir():
        bench_candidates = sorted(results_dir.glob("baseline_*.json")) + sorted(results_dir.glob("*_receipt.json"))
        for p in bench_candidates:
            if p.name in processed:
                continue
            if legacy_cutoff > 0.0 and p.stat().st_mtime <= legacy_cutoff:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                new_receipts.append(
                    {
                        "file": str(p.relative_to(root)),
                        "name": p.name,
                        "app_version": data.get("app_version"),
                        "all_passed": data.get("all_passed"),
                        "results": data.get("results"),
                        "summary": data.get("summary"),
                    }
                )
            except Exception as exc:
                new_receipts.append({"file": str(p.relative_to(root)), "name": p.name, "parse_error": str(exc)})

    logs_dir = root / "logs"
    recent_logs: List[Dict[str, Any]] = []
    if logs_dir.is_dir():
        log_files = sorted(logs_dir.glob("parasite_debug*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]
        for lf in log_files:
            recent_logs.append(
                {
                    "file": str(lf.relative_to(root)),
                    "size_bytes": lf.stat().st_size,
                    "mtime": lf.stat().st_mtime,
                }
            )

    cursor_version = cursor_data.get("last_app_version")
    latest_smoke_version = (latest_smoke_receipt or {}).get("app_version")
    awaiting_live_smoke = (
        len(new_receipts) == 0
        and bool(cursor_version)
        and latest_smoke_version != cursor_version
    )

    return {
        "active_stage": cursor_data.get("active_stage", "P4.7"),
        "hold_stage_until_graduated": bool(cursor_data.get("hold_stage_until_graduated", True)),
        "stage_sequence": cursor_data.get("stage_sequence", ["P4.7", "P5.1"]),
        "cursor_version": cursor_version,
        "cursor_last_evaluated_at": cursor_data.get("last_evaluated_at"),
        "latest_smoke_receipt": latest_smoke_receipt,
        "awaiting_live_smoke_for_cursor_version": awaiting_live_smoke,
        "new_receipts_count": len(new_receipts),
        "new_receipts": new_receipts,
        "recent_logs": recent_logs,
    }


def main() -> int:
    print(json.dumps(farm_new_results(ROOT), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
