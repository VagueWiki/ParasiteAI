@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P4.7 Generalization ^& 4.X Closure Smoke Probe

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P4.7.12 (0.4.7.12^) Live Smoke Probe
echo  [1/4] llama-server Daemon Check / Auto-Start
echo  [2/4] GPU Governance ^& RTX 4060 VRAM Check
echo  [3/4] P4.7 Preflight Unit Tests ^& Version Gate
echo  [4/4] Sandboxed + Live Unseen Generative Notepad Probe
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
if !ERRORLEVEL! NEQ 0 (
    echo [!] Persistent llama-server is not running or unhealthy. Starting daemon...
    %PY_EXE% scripts\serve_llama.py start
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to start llama-server daemon. Aborting.
        pause
        exit /b 1
    )
    %PY_EXE% -c "import time; time.sleep(2)"
    %PY_EXE% scripts\serve_llama.py status
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] llama-server health check still failing after start. Aborting.
        pause
        exit /b 1
    )
) else (
    echo [+] llama-server daemon is healthy.
)
echo.

echo [2/4] Checking GPU Governance and VRAM Headroom...
%PY_EXE% scripts\check_gpu_governance.py
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] GPU governance check failed. Aborting.
    pause
    exit /b 1
)
echo.

echo [3/4] Running P4.7 preflight unit tests ^& CLI version check...
%PY_EXE% -m parasite_ai.main --version
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] CLI version check failed. Aborting.
    pause
    exit /b 1
)
%PY_EXE% -m pytest tests\unit\test_p4_7_generalization.py tests\unit\test_p4_7_1_loop_and_checklist.py tests\unit\mind\test_skill_registry.py -q --tb=short
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] P4.7 preflight unit tests failed. Aborting live probe.
    pause
    exit /b 1
)
echo.

echo [4/4] Running Stage P4.7 Live Generalization Smoke Probe...
echo NOTE: Hands off mouse/keyboard during probe execution. Physical touch aborts cleanly.
echo.
%PY_EXE% scripts\smoke_test_p4_7_generalization.py %*
set "PROBE_ERR=!ERRORLEVEL!"
echo.

echo ============================================================
if "!PROBE_ERR!"=="0" (
    echo  Stage P4.7 Smoke Probe: PASSED
) else (
    echo  Stage P4.7 Smoke Probe: FAILED (exit code !PROBE_ERR!^)
)
echo  Receipts written under benchmarks\results\smoke_p4_7\
echo ============================================================
pause
exit /b !PROBE_ERR!
