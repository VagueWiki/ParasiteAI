"""Unit tests for scripts/run_idle_gated_smoke.py Mode B desktop readiness gates."""

from __future__ import annotations

import pytest

from parasite_ai.config import AppConfig
from scripts.farm_eval_receipts import farm_new_results
from scripts.run_idle_gated_smoke import evaluate_desktop_readiness, run_if_ready

pytestmark = pytest.mark.unit


def test_evaluate_desktop_readiness_blocks_unsafe_locked_active_or_unhealthy() -> None:
    ok, msg = evaluate_desktop_readiness(
        idle_sec=200.0, min_idle_sec=120.0, window_safe=False, bitblt_ok=True, bitblt_detail="ok", llama_ok=True
    )
    assert ok is False and "locked" in msg.lower()

    ok, msg = evaluate_desktop_readiness(
        idle_sec=200.0, min_idle_sec=120.0, window_safe=True, bitblt_ok=False, bitblt_detail="BitBlt failed", llama_ok=True
    )
    assert ok is False and "BitBlt" in msg

    ok, msg = evaluate_desktop_readiness(
        idle_sec=15.0, min_idle_sec=120.0, window_safe=True, bitblt_ok=True, bitblt_detail="ok", llama_ok=True
    )
    assert ok is False and "idle" in msg.lower()

    ok, msg = evaluate_desktop_readiness(
        idle_sec=200.0, min_idle_sec=120.0, window_safe=True, bitblt_ok=True, bitblt_detail="ok", llama_ok=False
    )
    assert ok is False and "llama-server" in msg


def test_run_if_ready_skips_cleanly_when_user_active_and_runs_only_when_all_gates_pass() -> None:
    calls = []

    res_skip = run_if_ready(
        min_idle_sec=120.0,
        cfg=AppConfig(),
        idle_fn=lambda: 10.0,
        window_safe_fn=lambda: True,
        bitblt_fn=lambda _idx: (True, "BitBlt OK (1920x1080)"),
        llama_fn=lambda _h, _p: True,
        smoke_runner=lambda: calls.append(1) or 0,
    )
    assert res_skip["skipped"] is True
    assert res_skip["ran"] is False
    assert res_skip["exit_code"] == 0
    assert calls == []

    res_run = run_if_ready(
        min_idle_sec=120.0,
        cfg=AppConfig(),
        idle_fn=lambda: 185.0,
        window_safe_fn=lambda: True,
        bitblt_fn=lambda _idx: (True, "BitBlt OK (1920x1080)"),
        llama_fn=lambda _h, _p: True,
        smoke_runner=lambda: calls.append(1) or 0,
    )
    assert res_run["skipped"] is False
    assert res_run["ran"] is True
    assert res_run["exit_code"] == 0
    assert calls == [1]


def test_farm_new_results_filters_processed_receipts(tmp_path) -> None:
    import json
    smoke_dir = tmp_path / "benchmarks" / "results" / "smoke_p4_7"
    smoke_dir.mkdir(parents=True)
    (smoke_dir / "smoke_20261116T010000Z.json").write_text(json.dumps({"app_version": "0.4.7.1", "all_passed": False}), encoding="utf-8")
    (smoke_dir / "smoke_20261116T020000Z.json").write_text(json.dumps({"app_version": "0.4.7.2", "all_passed": True}), encoding="utf-8")
    (tmp_path / "benchmarks" / "results" / ".automation_eval_cursor.json").write_text(
        json.dumps(
            {
                "active_stage": "P4.7",
                "hold_stage_until_graduated": True,
                "last_app_version": "0.4.7.1",
                "processed_receipts": ["smoke_20261116T010000Z.json"],
            }
        ),
        encoding="utf-8",
    )

    farmed = farm_new_results(tmp_path)
    assert farmed["active_stage"] == "P4.7"
    assert farmed["hold_stage_until_graduated"] is True
    assert farmed["latest_smoke_receipt"] == {"name": "smoke_20261116T020000Z.json", "app_version": "0.4.7.2", "all_passed": True}
    assert farmed["awaiting_live_smoke_for_cursor_version"] is False
    assert farmed["new_receipts_count"] == 1
    assert farmed["new_receipts"][0]["name"] == "smoke_20261116T020000Z.json"
    assert farmed["new_receipts"][0]["all_passed"] is True

    # Once processed, awaiting_live_smoke_for_cursor_version becomes True if cursor_version is ahead of latest smoke receipt
    (tmp_path / "benchmarks" / "results" / ".automation_eval_cursor.json").write_text(
        json.dumps(
            {
                "active_stage": "P4.7",
                "hold_stage_until_graduated": True,
                "last_app_version": "0.4.7.4",
                "processed_receipts": ["smoke_20261116T010000Z.json", "smoke_20261116T020000Z.json"],
            }
        ),
        encoding="utf-8",
    )
    farmed2 = farm_new_results(tmp_path)
    assert farmed2["new_receipts_count"] == 0
    assert farmed2["latest_smoke_receipt"] == {"name": "smoke_20261116T020000Z.json", "app_version": "0.4.7.2", "all_passed": True}
    assert farmed2["awaiting_live_smoke_for_cursor_version"] is True


def test_run_if_ready_attaches_interactive_desktop_before_gates(monkeypatch) -> None:
    events = []

    res = run_if_ready(
        min_idle_sec=120.0,
        cfg=AppConfig(),
        desktop_attach_fn=lambda: events.append("attach") or True,
        idle_fn=lambda: events.append("idle") or 180.0,
        window_safe_fn=lambda: events.append("window") or True,
        bitblt_fn=lambda _idx: events.append("bitblt") or (True, "BitBlt OK (1920x1080)"),
        llama_fn=lambda _h, _p: events.append("llama") or True,
        smoke_runner=lambda: events.append("smoke") or 0,
    )
    assert res["ran"] is True
    assert events[0] == "attach"
    assert events[-1] == "smoke"

    # Also verify check_live_bitblt_capture calls ensure_interactive_desktop before mss.MSS()
    import scripts.run_idle_gated_smoke as mod

    attach_calls = []
    monkeypatch.setattr(mod, "ensure_interactive_desktop", lambda: attach_calls.append(1) or True)

    class _FakeShot:
        width = 1920
        height = 1080
        raw = b"\x00" * 16

    class _FakeMSS:
        monitors = [{}, {"left": 0, "top": 0, "width": 1920, "height": 1080}]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def grab(self, _mon):
            assert attach_calls == [1], "ensure_interactive_desktop must be called before mss.grab()"
            return _FakeShot()

    import sys
    import types

    monkeypatch.setitem(sys.modules, "mss", types.SimpleNamespace(MSS=_FakeMSS))
    ok, detail = mod.check_live_bitblt_capture(1)
    assert ok is True
    assert "1920x1080" in detail
