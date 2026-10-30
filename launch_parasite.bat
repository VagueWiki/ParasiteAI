@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Launcher

cd /d "%~dp0"

where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
        set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    ) else if exist "%LOCALAPPDATA%\bin\uv.exe" (
        set "PATH=%LOCALAPPDATA%\bin;%PATH%"
    ) else (
        echo [ERROR] uv package manager was not found on PATH or standard install directories.
        echo Please install uv from: https://astral.sh/uv
        exit /b 1
    )
)

echo [ParasiteAI] Synchronizing virtual environment...
uv sync
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] uv sync failed with exit code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
)

echo [ParasiteAI] Launching desktop assistant (Local GGUF RTX 4060 Mode)...
uv run python main.py %*
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
