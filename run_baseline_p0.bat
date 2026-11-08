@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P0 Hands-Off Baseline Runner

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P0 Hands-Off Baseline Runner (Windows 10)
echo ============================================================

set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    where uv >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY_EXE=uv run python"
    ) else (
        set "PY_EXE=python"
    )
)

echo [1/2] Checking GPU Governance & VRAM Headroom...
%PY_EXE% scripts\check_gpu_governance.py
echo.

echo [2/2] Starting Hands-Off Baseline Suite (20 Tasks, Checkpointed, Max Steps Cap: 5)...
echo NOTE: Please keep hands off mouse and keyboard on Monitor 1 during the run.
echo       Press Esc, Ctrl+Alt+P, or slam the cursor into a corner at any time to pause/abort.
echo.
%PY_EXE% -m benchmarks.run_benchmark --output-name baseline_p0 --resume --max-steps-cap 5 %*
set "BENCH_EXIT=%ERRORLEVEL%"

echo.
echo ============================================================
echo  Baseline Run Finished with Exit Code: %BENCH_EXIT%
echo  Reports: benchmarks\results\baseline_p0.md and .json
echo ============================================================
exit /b %BENCH_EXIT%
