@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stint P4.1 Precision Actuation Smoke Probe

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stint P4.1 Physical Precision Smoke Probe
echo  Verifying: HumanCurve Ballistics + Centroid Button Snapping
echo             + Pre-Click Optical Zoom on Calculator (7, 8, 9)
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

echo [1/3] Checking persistent llama-server daemon status...
%PY_EXE% scripts\serve_llama.py status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Persistent llama-server is not running. Starting daemon...
    %PY_EXE% scripts\serve_llama.py start
    %PY_EXE% -c "import time; time.sleep(3)"
)
echo.

echo [2/3] Running Stint P4.1 Hardware Calculator Precision Probe...
echo NOTE: Hands off mouse/keyboard for ~5 seconds. Touching hardware aborts in ^<2ms.
echo.
%PY_EXE% scripts\smoke_test_p4_1_precision.py
set "PROBE_ERR=%ERRORLEVEL%"
echo.

echo [3/3] Running Benchmark Task L1-08 (Compute Multiplication in Calculator)...
%PY_EXE% -m benchmarks.run_benchmark --task L1-08 --max-steps-cap 8 --output-name smoke_p4_1_L1_08
set "BENCH_ERR=%ERRORLEVEL%"
echo.

echo ============================================================
if "%PROBE_ERR%"=="0" (
    echo  [2/3] Precision Probe: PASSED
) else (
    echo  [2/3] Precision Probe: FAILED (exit code %PROBE_ERR%)
)
if "%BENCH_ERR%"=="0" (
    echo  [3/3] Benchmark L1-08: PASSED (benchmarks\results\smoke_p4_1_L1_08.*)
) else (
    echo  [3/3] Benchmark L1-08: FAILED (exit code %BENCH_ERR%)
)
echo ============================================================
pause
