"""
scripts/run_idle_gated_smoke.py - Idle- & Unlocked-Desktop-Gated Live Smoke Runner (Mode B).

Used by the scheduled Antigravity automation (`parasiteai-eval-iterate`) so live Win32
desktop smoke probes only execute when the interactive desktop is unlocked, BitBlt-capable,
llama-server is healthy, and the user has been physically idle for >= 120 seconds.

If any preflight gate fails (busy user, locked screen, UAC/sensitive window, or daemon down),
prints a JSON skip receipt and exits 0 cleanly without disturbing the user's desktop.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Dict, Optional, Tuple
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parasite_ai.config import AppConfig, load_config
from parasite_ai.safety.window_guard import WindowGuard, ensure_interactive_desktop


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def get_user_idle_seconds() -> float:
    """Returns seconds since last physical keyboard/mouse input via Win32 GetLastInputInfo."""
    if sys.platform != "win32":
        return 0.0
    try:
        ensure_interactive_desktop()
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        now_tick = int(kernel32.GetTickCount())
        elapsed_ms = (now_tick - int(lii.dwTime)) & 0xFFFFFFFF
        return elapsed_ms / 1000.0
    except Exception:
        return 0.0


def check_live_bitblt_capture(monitor_index: int = 1) -> Tuple[bool, str]:
    """Verifies physical BitBlt desktop capture works right now (fails on locked/secure desktop)."""
    try:
        import mss

        ensure_interactive_desktop()
        with mss.MSS() as sct:
            idx = monitor_index if 0 < monitor_index < len(sct.monitors) else 1
            shot = sct.grab(sct.monitors[idx])
            if shot is None or shot.width <= 0 or shot.height <= 0 or not shot.raw:
                return False, "BitBlt returned empty frame"
            return True, f"BitBlt OK ({shot.width}x{shot.height})"
    except Exception as exc:
        return False, f"BitBlt capture unavailable: {exc}"


def check_llama_healthy(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Checks llama-server /health endpoint."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def evaluate_desktop_readiness(
    *,
    idle_sec: float,
    min_idle_sec: float,
    window_safe: bool,
    bitblt_ok: bool,
    bitblt_detail: str,
    llama_ok: bool,
) -> Tuple[bool, str]:
    """Pure readiness evaluator deciding whether unattended live GUI testing is safe."""
    if not window_safe:
        return False, "Desktop locked, hwnd=0, or sensitive/protected foreground window active."
    if not bitblt_ok:
        return False, bitblt_detail or "BitBlt capture failed."
    if idle_sec < min_idle_sec:
        return False, f"User active recently (idle {idle_sec:.1f}s < required {min_idle_sec:.1f}s)."
    if not llama_ok:
        return False, "llama-server on port 8080 is not healthy."
    return True, f"Ready (idle={idle_sec:.1f}s, {bitblt_detail}, llama_ok=True)."


def run_if_ready(
    *,
    min_idle_sec: float = 120.0,
    auto_start_llama: bool = False,
    cfg: Optional[AppConfig] = None,
    desktop_attach_fn: Callable[[], bool] = ensure_interactive_desktop,
    idle_fn: Callable[[], float] = get_user_idle_seconds,
    window_safe_fn: Optional[Callable[[], bool]] = None,
    bitblt_fn: Callable[[int], Tuple[bool, str]] = check_live_bitblt_capture,
    llama_fn: Callable[[str, int], bool] = check_llama_healthy,
    smoke_runner: Optional[Callable[[], int]] = None,
) -> Dict[str, Any]:
    """Checks all 4 desktop readiness gates and runs the smoke probe only if all pass."""
    desktop_attach_fn()
    resolved_cfg = cfg or (load_config(ROOT / "config.yaml") if (ROOT / "config.yaml").is_file() else AppConfig())
    mon_idx = int(getattr(getattr(resolved_cfg, "vision", None), "monitor_index", 1) or 1)
    host = str(getattr(resolved_cfg.brain.local_model, "server_host", "127.0.0.1"))
    port = int(getattr(resolved_cfg.brain.local_model, "server_port", 8080))

    if window_safe_fn is None:
        wg = WindowGuard(config=resolved_cfg.safety)
        window_safe_fn = wg.is_safe_to_operate

    idle_sec = float(idle_fn())
    window_safe = bool(window_safe_fn())
    bitblt_ok, bitblt_detail = bitblt_fn(mon_idx)
    llama_ok = bool(llama_fn(host, port))

    if not llama_ok and auto_start_llama and window_safe and bitblt_ok and idle_sec >= min_idle_sec:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "serve_llama.py"), "start"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        llama_ok = bool(llama_fn(host, port))

    ready, reason = evaluate_desktop_readiness(
        idle_sec=idle_sec,
        min_idle_sec=min_idle_sec,
        window_safe=window_safe,
        bitblt_ok=bitblt_ok,
        bitblt_detail=bitblt_detail,
        llama_ok=llama_ok,
    )
    if not ready:
        return {
            "ran": False,
            "skipped": True,
            "reason": reason,
            "idle_sec": round(idle_sec, 1),
            "window_safe": window_safe,
            "bitblt_ok": bitblt_ok,
            "llama_ok": llama_ok,
            "exit_code": 0,
        }

    if smoke_runner is None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_test_p4_7_generalization.py")],
            cwd=str(ROOT),
            timeout=300,
        )
        rc = int(proc.returncode)
    else:
        rc = int(smoke_runner())

    return {
        "ran": True,
        "skipped": False,
        "reason": reason,
        "idle_sec": round(idle_sec, 1),
        "window_safe": window_safe,
        "bitblt_ok": bitblt_ok,
        "llama_ok": llama_ok,
        "exit_code": rc,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Idle- & Unlocked-Desktop-Gated Live Smoke Runner")
    parser.add_argument("--min-idle-sec", type=float, default=120.0, help="Required user idle seconds (default: 120)")
    parser.add_argument("--auto-start-llama", action="store_true", help="Auto-start llama-server if desktop is ready")
    args = parser.parse_args()

    result = run_if_ready(
        min_idle_sec=args.min_idle_sec,
        auto_start_llama=args.auto_start_llama,
    )
    print(json.dumps(result, indent=2))
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
