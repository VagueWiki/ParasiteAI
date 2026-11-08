@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  ParasiteAI - Persistent llama-server Supervisor
echo  Host: Windows 10 ^| RTX 4060 (6,500 MB VRAM Budget)
echo ============================================================

REM Check if virtual environment python exists
if not exist ".venv\Scripts\python.exe" (
    echo [-] Error: Python virtual environment not found in .venv\Scripts\python.exe
    pause
    exit /b 1
)

REM Check if llama-server.exe is provisioned
if not exist "bin\llama-server\llama-server.exe" (
    echo [*] llama-server.exe not found in bin\llama-server\. Running provisioner...
    .venv\Scripts\python.exe scripts\provision_llama_server.py
    if errorlevel 1 (
        echo [-] Provisioning failed.
        pause
        exit /b 1
    )
)

echo [*] Starting llama-server with GPU Governance check...
.venv\Scripts\python.exe scripts\serve_llama.py start --daemon=false
if errorlevel 1 (
    echo [-] Server exited with an error.
    pause
    exit /b 1
)

pause
