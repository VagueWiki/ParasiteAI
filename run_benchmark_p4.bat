@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P4 Benchmark Runner (UI-TARS-1.5-7B + Precision, Reflex, Skill Engine & AppMemory)

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P4 Certification Benchmark Runner (Windows 10)
echo  Model: UI-TARS-1.5-7B + Stage P4 Stack
echo  Configuration:
echo   - Native 1080p Visual Encoding (1920x1080, quality 90)
echo   - HumanCurve Ballistics, CentroidSnapper & Reflex Engine
echo   - Universal Skill Engine (SKILL.md) & Directive Fast Path
echo   - Titular ParasiteSkill Symbiosis & SQLite WAL AppMemory
echo   - Monitor 2 Auto-Relocation Guard & Shell Flyout Guard
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

echo [1/3] Checking persistent llama-server daemon status...
%PY_EXE% scripts\serve_llama.py status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Persistent llama-server is not running or unhealthy!
    echo Attempting to start supervisor daemon...
    %PY_EXE% scripts\serve_llama.py start
    %PY_EXE% -c "import time; time.sleep(3)"
)
echo.

echo [2/3] Checking GPU Governance and VRAM Headroom...
%PY_EXE% scripts\check_gpu_governance.py
echo.

echo [3/3] Starting Stage P4 Benchmark Suite (20 Tasks, Checkpointed, Full Suite Budgets)...
echo NOTE: Please keep hands off mouse and keyboard on Monitor 1 during the run.
echo       Move your physical mouse or keyboard to preempt in <2ms, or press Ctrl+Alt+K for emergency kill.
echo.
%PY_EXE% -m benchmarks.run_benchmark --output-name baseline_p4 --resume %*
set "BENCH_EXIT=%ERRORLEVEL%"

echo.
echo ============================================================
echo  Stage P4 Benchmark Run Finished with Exit Code: %BENCH_EXIT%
echo  Reports: benchmarks\results\baseline_p4.md and .json
echo ============================================================

if exist "benchmarks\results\baseline_p4.json" (
    if exist "benchmarks\results\baseline_p3.json" (
        echo.
        echo [*] Generating P3 vs P4 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p3.json --candidate benchmarks\results\baseline_p4.json
    )
    if exist "benchmarks\results\baseline_p2_7.json" (
        echo.
        echo [*] Generating P2.7 vs P4 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p2_7.json --candidate benchmarks\results\baseline_p4.json
    )
    if exist "benchmarks\results\baseline_p0.json" (
        echo.
        echo [*] Generating P0 vs P4 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p0.json --candidate benchmarks\results\baseline_p4.json
    )
)

pause
exit /b %BENCH_EXIT%
