@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stint P2.7 Targeted Smoke Probe (L1-01 & L1-06)

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stint P2.7 Targeted Smoke Probe (Windows 10)
echo  Verifying Native 1080p Resolution on Live Physical Desktop
echo  Testing: Task L1-01 (Start Button) & Task L1-06 (Window Close)
echo ============================================================
echo.

set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    where uv >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PY_EXE=uv run python"
    ) else (
        set "PY_EXE=python"
    )
)

echo [1/4] Checking persistent llama-server daemon status...
%PY_EXE% scripts\serve_llama.py status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Persistent llama-server is not running. Starting daemon...
    %PY_EXE% scripts\serve_llama.py start
    %PY_EXE% -c "import time; time.sleep(3)"
)
echo.

echo [2/4] Checking GPU Governance and VRAM Headroom...
%PY_EXE% scripts\check_gpu_governance.py
echo.

echo [3/4] Running Targeted Smoke Probes (Hands-off for ~20-30 seconds)...
echo NOTE: Touching your physical mouse or keyboard will instantly take back control in ^<2ms.
echo.

echo --- Running Probe 1: Task L1-01 (Open Notepad / Start Menu) ---
%PY_EXE% -m benchmarks.run_benchmark --task L1-01 --max-steps-cap 6
echo.

echo --- Running Probe 2: Task L1-06 (Close Pre-Opened Notepad) ---
%PY_EXE% -m benchmarks.run_benchmark --task L1-06 --max-steps-cap 4
echo.

echo [4/4] Inspecting Empirical Receipts and Coordinates...
%PY_EXE% scripts\inspect_probe_receipts.py L1-01 L1-06

echo ============================================================
echo  Targeted Smoke Probe Complete!
echo ============================================================
pause
