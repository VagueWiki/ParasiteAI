# BRIEFING — 2026-10-29T21:06:00Z

## Mission
Conduct a deep architectural and implementation discrepancy analysis across M1–M5 comparing simulated test conditions against physical Windows desktop and hardware execution requirements.

## 🔒 My Identity
- Archetype: explorer
- Roles: discrepancy_analyst
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_discrepancy
- Original parent: b73c0b17-614f-47e4-8b69-eef76039cfb6
- Milestone: M1-M5 Discrepancy Analysis

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Strictly observe 5-component handoff report protocol
- Compare unit/simulated test conditions with physical Windows desktop execution requirements

## Current Parent
- Conversation ID: b73c0b17-614f-47e4-8b69-eef76039cfb6
- Updated: 2026-10-29T20:57:51Z

## Investigation State
- **Explored paths**:
  - `parasite_ai/ui/companion_dock.py`, `ghost_hud.py`, `win32_styles.py`, `dpi.py`
  - `parasite_ai/hands/kinematics.py`, `mouse.py`, `keyboard.py`
  - `parasite_ai/safety/interrupt_guard.py`, `window_guard.py`, `panic.py`
  - `parasite_ai/mind/offloader.py`, `brain_manager.py`, `dual_mind.py`, `memory.py`
  - `parasite_ai/vision/grounding.py`, `capture.py`, `runtime.py`, `main.py`
  - `tests/test_*.py` (E2E, offloader, ghost HUD, interrupt guard, kinematics)
  - Live hardware inspection: `nvidia-smi` (RTX 4060, 5564 MiB free), `models/` directory (empty), `llama_cpp` (not installed), local endpoints 8080/11434 (offline).
- **Key findings**:
  - **High Risk**: BrowserOffloader relies on hardcoded window coordinates (`rect[3] - 120` and `rect[3] - 320` + `Ctrl+C`) completely bypassing UIA/grounding. In real Chrome/Gemini, clicking unselected canvas does not select text and `Ctrl+C` copies nothing, causing sentinel harvest timeouts (45s).
  - **High Risk**: Brain resource budget discrepancy — `models/` is empty, `llama-cpp-python` is not installed, local servers are offline. Attempting 7B model on 8GB RTX 4060 (only 5564 MiB free) will OOM or thrash shared RAM; 3B model is mandatory for local inference.
  - **High Risk**: Low-level hook timeout risk (`WH_MOUSE_LL` / `WH_KEYBOARD_LL`) in Python — if heavy OCR/LLM/Qt processing blocks the GIL, Windows drops the hook silently, disabling physical interrupt protection.
  - **Medium Risk**: Kinematic overshoot does not clamp coordinates before normalizing to `[0, 65535]` with `MOUSEEVENTF_ABSOLUTE`, causing wrap/overflow on screen edges or multi-monitor setups.
  - **Medium Risk**: GhostHUD 64-bit ctypes usage lacks `argtypes`/`restype` and uses 32-bit `GetWindowLongW`/`SetWindowLongW` instead of `Ptr` variants.
  - **Low/Medium Risk**: CompanionDock uses `Qt.WindowType.Tool`, hiding it from the Windows taskbar and Alt+Tab; multi-DPI dragging across mixed monitors can drift without per-monitor geometry updates.
- **Unexplored areas**: None across M1–M5 core contracts.

## Key Decisions Made
- Categorized all discrepancies into a 3-tier Risk Matrix (High/Medium/Low) with actionable remediation steps.
- Structuring `handoff.md` following the mandatory 5-component protocol.

## Artifact Index
- DISPATCH.md — Task assignment and incoming messages
- BRIEFING.md — Persistent working memory
- progress.md — Liveness heartbeat and progress tracker
- handoff.md — Comprehensive 5-component handoff report
