@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Stage P4.4 Titular ParasiteSkill ^& Skill Engine Smoke Probe

cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI Stage P4.4 Physical Symbiosis Smoke Probe
echo  Probes P-A .. P-G: Alt+G Focus, CF_DIB Clipboard, Gemini
echo  Proactive/Reactive Planning, Fail-Closed Guards, pHash/TTL
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

echo [PREFLIGHT] Ensuring "Gemini in Chrome" app window is installed and ready on Alt+G.
echo NOTE: Hands off mouse/keyboard during probe execution. Physical touch aborts cleanly.
echo.

%PY_EXE% scripts\smoke_test_p4_4_parasite_skill.py --probe all %*
set "PROBE_ERR=%ERRORLEVEL%"
echo.

echo ============================================================
if "%PROBE_ERR%"=="0" (
    echo  Stage P4.4 Smoke Probes (P-A .. P-G^): PASSED
) else (
    echo  Stage P4.4 Smoke Probes (P-A .. P-G^): FAILED (exit code %PROBE_ERR%^)
)
echo  Receipts written under benchmarks\results\smoke_p4_4\
echo ============================================================
pause
