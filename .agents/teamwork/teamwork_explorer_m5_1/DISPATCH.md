# Task Assignment: Milestone M5 Explorer 1 (Entry Points & Startup Lifecycle)

**Recipient**: `teamwork_explorer_m5_1`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_1\`
**Assigned Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance

---

## Focus Area: Features 16 & 17 — Application Entry Points (`main.py`, `launch_parasite.bat`)
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Requirements R1, R2, R3, R4 & Entry Points).
   - `PROJECT.md` Features 16 & 17.
2. **Architecture & Scope**:
   - `main.py`:
     - Process DPI awareness bootstrapping (`parasite_ai/ui/dpi.py:init_dpi_awareness`).
     - Configuration loading (`parasite_ai/config.py:load_config`).
     - Qt application lifecycle management (`QApplication(sys.argv)`).
     - Component instantiation: `UIBridge`, `InterruptGuard`, `WindowGuard`, `MouseDriver`, `KeyboardDriver`, `ScreenCapture`, `ScreenGrounder`, `LocalBrainManager`, `EpisodicMemory`, `DualMindPipeline`, `CompanionDock`, `GhostHUD`.
     - Cross-thread synchronization: background daemon worker thread running the cognitive goal loop while Qt runs the GUI event loop.
     - Clean exit and signal handling: `SIGINT` / `Ctrl+C`, `QApplication.aboutToQuit`, unhooking Win32 hooks, stopping drivers, clearing overlay.
     - Headless / offscreen support: gracefully handling `QT_QPA_PLATFORM=offscreen` or `--headless` / `--dry-run` flag for automated CI testability.
   - `launch_parasite.bat`:
     - Clean batch script checking Windows environment, verifying `uv` availability, syncing virtual environment (`uv sync` or `uv run`), and launching `main.py`.
3. **Investigation Tasks**:
   - Inspect existing `parasite_ai/ui/dpi.py`, `win32_styles.py`, `bridge.py`, `companion_dock.py`, `ghost_hud.py`.
   - Inspect existing `parasite_ai/mind/dual_mind.py`, `brain_manager.py`, `safety/interrupt_guard.py`.
   - Formulate exact `main.py` architecture, CLI arguments (`--config`, `--headless`, `--dry-run`, `--no-hud`), and threading model.
   - Design automated tests for `main.py` entry point (`tests/test_entrypoints.py`).
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.
