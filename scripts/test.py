"""
scripts/test.py - Unified ParasiteAI Test Suite Runner.

Usage:
    python scripts/test.py              # Default: Run active Unit + Integration suites (< 20s)
    python scripts/test.py unit         # Run Tier 1 Unit tests only (< 8s)
    python scripts/test.py integration  # Run Tier 2 Integration tests (< 15s)
    python scripts/test.py mind         # Run unit tests for parasite_ai.mind
    python scripts/test.py hands        # Run unit tests for kinematics & inputs
    python scripts/test.py vision       # Run unit tests for grounding & capture
    python scripts/test.py safety       # Run unit tests for guards & safety
    python scripts/test.py ui           # Run unit tests for HUD & overlay
    python scripts/test.py core         # Run unit tests for config & core
    python scripts/test.py challenger   # Run historical challenger archive (on-demand)
    python scripts/test.py live         # Run live Windows OS desktop benchmarks (with prompt)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def _get_python_executable() -> str:
    """Resolve pytest runner python executable, preferring .venv if present."""
    # Check if pytest is importable in current interpreter
    try:
        import pytest  # noqa: F401
        return sys.executable
    except ImportError:
        pass

    # Look for local project venv
    root = Path(__file__).resolve().parent.parent
    for candidate in [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
    ]:
        if candidate.is_file():
            return str(candidate)

    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description="ParasiteAI Tiered Test Runner")
    parser.add_argument(
        "suite",
        nargs="?",
        default="active",
        choices=[
            "active",
            "unit",
            "integration",
            "all",
            "mind",
            "hands",
            "vision",
            "safety",
            "ui",
            "core",
            "archive",
            "challenger",
            "live",
        ],
        help="Target test profile / tier to execute (default: active)",
    )
    parser.add_argument(
        "-k",
        "--expression",
        help="Pytest -k filter expression",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Run in quiet mode",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Run in verbose mode",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Bypass interactive prompts (e.g. for live OS runs in CI)",
    )

    args = parser.parse_args()

    python_bin = _get_python_executable()
    cmd = [python_bin, "-m", "pytest"]

    if args.quiet:
        cmd.append("-q")
    elif args.verbose:
        cmd.append("-vv")

    if args.expression:
        cmd.extend(["-k", args.expression])

    if args.suite in ("active", "all"):
        # Relies on testpaths = ["tests/unit", "tests/integration"] in pyproject.toml
        pass
    elif args.suite == "unit":
        cmd.append("tests/unit")
    elif args.suite == "integration":
        cmd.append("tests/integration")
    elif args.suite in ("mind", "hands", "vision", "safety", "ui", "core"):
        cmd.append(f"tests/unit/{args.suite}")
    elif args.suite in ("archive", "challenger"):
        cmd.append("tests/archive")
    elif args.suite == "live":
        if not args.yes:
            print("============================================================")
            print(" WARNING: Live OS tests manipulate the physical desktop!")
            print(" - Spawns real notepad.exe processes")
            print(" - May inspect or modify clipboard contents")
            print(" - Please do NOT touch the mouse/keyboard during execution.")
            print("============================================================")
            ans = input("Proceed with Live OS benchmark tests? [y/N]: ").strip().lower()
            if ans not in ("y", "yes"):
                print("Aborted.")
                return 1
        cmd.extend(["tests/live_os", "-m", "live_os"])

    print(f"[*] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
