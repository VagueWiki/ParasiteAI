@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P4.5 Farmed Execution, AppMemory ^& Playbook Smoke Probe

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P4.5 Live Execution Smoke Probe
echo  Probes P-H .. P-L: Farmed Plan Execution, Layer 1.5 Cache,
echo  Calculator/Paint Playbooks, SQLite WAL ^& Draft Promotion
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

echo [PREFLIGHT] Ensure llama-server (8080) and Gemini in Chrome (Alt+G) are ready.
echo NOTE: Hands off mouse/keyboard during probe execution. Physical touch aborts cleanly.
echo.

%PY_EXE% scripts\smoke_test_p4_5_execution.py --probe all %*
set "PROBE_ERR=%ERRORLEVEL%"
echo.

echo ============================================================
if "%PROBE_ERR%"=="0" (
    echo  Stage P4.5 Smoke Probes (P-H .. P-L^): PASSED
) else (
    echo  Stage P4.5 Smoke Probes (P-H .. P-L^): FAILED (exit code %PROBE_ERR%^)
)
echo  Receipts written under benchmarks\results\smoke_p4_5\
echo ============================================================
pause
