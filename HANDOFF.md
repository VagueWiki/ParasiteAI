# ParasiteAI — Model Handoff Summary (`HANDOFF.md`)

See the full artifact at `C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\handoff_to_claude.md` as well as `PROJECT.md` and `GATE_STATUS.md`.

## Quick Reference
- **Launch on Desktop:** `.\launch_parasite.bat` (or `uv run python main.py --brain-mode local_llm`)
- **Instant Hard Kill Hotkey:** **`Ctrl + Alt + K`** or **`Ctrl + Alt + Q`** (registered at both the `WH_KEYBOARD_LL` hook level and OS kernel `RegisterHotKey` level in `parasite_ai/safety/interrupt_guard.py` and `parasite_ai/safety/panic.py`; immediately releases all mouse/keyboard state and kills the process tree via `taskkill /F /T /PID` + `os._exit(0)`).
- **External Kill Script:** `.\kill_parasite.bat`
- **Run Tests:** `uv run pytest -q`
