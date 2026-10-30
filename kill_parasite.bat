@echo off
echo [ParasiteAI] Instantly terminating all ParasiteAI processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'parasite_ai|main\.py' -and $_.Name -match 'python|uv' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo [ParasiteAI] All ParasiteAI processes terminated.
