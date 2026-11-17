@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P3 Benchmark Runner (UI-TARS-1.5-7B Native 1080p + Action Chaining & Phased Memory)

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P3 Benchmark Runner (Windows 10)
echo  Model: UI-TARS-1.5-7B
echo  Configuration:
echo   - Native 1080p Visual Encoding (1920x1080, quality 90)
echo   - Universal Action Chaining (type text\n with auto-submit)
echo   - Semantic Loop Breaker (Repetitive typing & double-click recovery)
echo   - Monitor 2 Auto-Relocation Guard (Snaps out-of-bounds windows)
echo   - 7-Phase Compound Working Memory Checklists & Taskbar Affordances
echo   - Visible Browser Consultation Protocol (Prompt Sanitization & Monitor 1)
echo   - 8,192-Token Context with q8_0 KV Cache
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

echo [3/3] Starting Stage P3 Benchmark Suite (20 Tasks, Checkpointed, Max Steps Cap: 8)...
echo NOTE: Please keep hands off mouse and keyboard on Monitor 1 during the run.
echo       Move your physical mouse or keyboard to preempt in <2ms, or press Ctrl+Alt+K for emergency kill.
echo.
%PY_EXE% -m benchmarks.run_benchmark --output-name baseline_p3 --resume --max-steps-cap 8 %*
set "BENCH_EXIT=%ERRORLEVEL%"

echo.
echo ============================================================
echo  Stage P3 Benchmark Run Finished with Exit Code: %BENCH_EXIT%
echo  Reports: benchmarks\results\baseline_p3.md and .json
echo ============================================================

if exist "benchmarks\results\baseline_p3.json" (
    if exist "benchmarks\results\baseline_p2_7.json" (
        echo.
        echo [*] Generating P2.7 vs P3 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p2_7.json --candidate benchmarks\results\baseline_p3.json
    )
    if exist "benchmarks\results\baseline_p2.json" (
        echo.
        echo [*] Generating P2 vs P3 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p2.json --candidate benchmarks\results\baseline_p3.json
    )
    if exist "benchmarks\results\baseline_p0.json" (
        echo.
        echo [*] Generating P0 vs P3 Comparative Scorecard...
        %PY_EXE% scripts\compare_benchmarks.py --baseline benchmarks\results\baseline_p0.json --candidate benchmarks\results\baseline_p3.json
    )
)

pause
exit /b %BENCH_EXIT%
