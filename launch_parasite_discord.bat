@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Discord C2 Launcher

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

echo ==============================================================================
echo [ParasiteAI] Starting Remote Command ^& Control (Discord Bot + Headless Core)
echo ==============================================================================

if exist "%~dp0discord_secrets.bat" (
    call "%~dp0discord_secrets.bat"
)

if "%PARASITE_DISCORD_TOKEN%"=="" (
    echo [WARNING] PARASITE_DISCORD_TOKEN environment variable is not set.
    echo If config.yaml does not contain a discord.token, the bot listener will not start.
    echo.
)

uv run python -m parasite_ai.main --headless --discord %*
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
