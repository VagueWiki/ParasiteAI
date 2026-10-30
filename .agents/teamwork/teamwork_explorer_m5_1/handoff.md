# Handoff Report: Milestone M5 Explorer 1 (Entry Points & Startup Lifecycle)

## 1. Observation
- `pyproject.toml` lines 74-75 declares the console script entry point:
  ```toml
  [project.scripts]
  parasite = "parasite_ai.main:main"
  ```
  Neither `main.py` at the project root nor `parasite_ai/main.py` existed on disk prior to this investigation.
- `PROJECT.md` lines 26-28 and 48 defines Feature 16:
  `Application Entry Points | main.py (DPI-aware bootstrapper) and launch_parasite.bat`.
- `parasite_ai/ui/dpi.py` lines 18-25 implements `init_high_dpi_awareness() -> bool`, but lacks the direct alias `init_dpi_awareness` referenced in the dispatch instructions.
- `parasite_ai/ui/bridge.py` lines 20-55 implements `UIBridge` with signal routing (`sig_state_changed`, `sig_thought_updated`, `sig_speech_updated`, `sig_telemetry_updated`, `sig_perception_updated`, `sig_targets_updated`, `sig_reticle_requested`) and a thread-safe goal queue (`sig_goal_submitted`, `get_next_goal()`).
- `parasite_ai/ui/companion_dock.py` lines 110-144 accepts `bridge: Optional[UIBridge]` and auto-wires signals in `_connect_bridge()`.
- `parasite_ai/ui/ghost_hud.py` lines 121-161 accepts `bridge: Optional[UIBridge]` and `enable_win32_styles: bool = True`, allowing clean disabling of native Win32 window calls during headless testing.
- `parasite_ai/mind/dual_mind.py` lines 500-535 defines `DualMindPipeline.__init__` accepting `brain_manager`, `memory`, `mouse_driver`, `keyboard_driver`, `screen_grounder`, `capturer`, `interrupt_guard`, `window_guard`, `bridge`, `offloader`, `config`.
- Full project test suite execution:
  `uv run pytest` executed 552 tests across 32 test files, with all 552 passing in 43.01s (Command output: `552 passed in 43.01s`).

---

## 2. Logic Chain
1. *From Observation 1*: The project specifies `parasite = "parasite_ai.main:main"` in `pyproject.toml`, while `ORIGINAL_REQUEST.md` and `PROJECT.md` require launching via `python main.py` or `launch_parasite.bat`.
   *Inference*: The implementation should place the primary application logic and `main(argv=None)` in `parasite_ai/main.py`, while providing a clean root `main.py` that delegates to `parasite_ai.main:main()`.
2. *From Observation 3*: On Windows, DPI awareness must be initialized prior to `QApplication` instantiation to guarantee 1:1 coordinate matching between Win32 UI Automation bounds, screen capture pixels, and transparent overlay coordinates.
   *Inference*: `init_high_dpi_awareness()` must be called in `parasite_ai/main.py` before `QApplication` starts. Adding `init_dpi_awareness = init_high_dpi_awareness` in `parasite_ai/ui/dpi.py` ensures interface contract compliance.
3. *From Observations 4, 5, 6, 7*: The GUI event loop requires the main OS thread (`app.exec()`), whereas the autonomous cognitive perception-reasoning loop must not block the UI.
   *Inference*: The cognitive engine must run in a dedicated daemon worker thread (`CognitiveDaemon`), synchronizing strictly via `UIBridge`.
4. *From Observations 5 & 6*: In headless/CI environments or offscreen platforms (`QT_QPA_PLATFORM=offscreen`), physical input drivers must run in simulation mode (`simulation_mode=True`) and Win32 extended window styles must not be applied to offscreen surfaces (`enable_win32_styles=False`).
   *Inference*: Passing `--headless` or `--dry-run` must configure these settings automatically to enable fast, headless CI automated verification.
5. *From Observation 7*: Graceful shutdown must be atomic and idempotent.
   *Inference*: `ParasiteApp.shutdown()` must set `stop_event`, join the cognitive daemon, stop `InterruptGuard` (unhooking `WH_MOUSE_LL`/`WH_KEYBOARD_LL`), release held keys/buttons, close `ScreenCapture`, and close UI windows.

---

## 3. Caveats
- Windows Low-Level Hardware Hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) require an active Windows message loop on their creating thread; `InterruptGuard` runs its own dedicated thread with `GetMessageW`, so terminating the app must call `interrupt_guard.stop()` to post `WM_QUIT` and avoid orphan hooks.
- On Windows, Python's default signal handler for `SIGINT` (`Ctrl+C`) does not interrupt a blocking native C++ call like Qt's `GetMessage` in `QApplication.exec()`. A periodic 200ms `QTimer` is required to ensure Python signal dispatch.
- In pure headless Linux or container environments where Windows DLLs (`user32`, `kernel32`, `winmm`) do not exist, `InterruptGuard`, `MouseDriver`, `WindowGuard`, and `dpi.py` already feature fallback guards (`sys.platform != "win32"` and simulation mode).

---

## 4. Conclusion
Features 16 & 17 can be implemented cleanly and deterministically with zero architectural conflicts.
The recommended implementation encompasses:
1. `parasite_ai/ui/dpi.py` & `parasite_ai/ui/__init__.py`: Export `init_dpi_awareness` alias.
2. `parasite_ai/main.py`: `ParasiteApp` class, CLI parser (`--config`, `--headless`, `--dry-run`, `--no-hud`, `--brain-mode`, `--goal`, `--log-level`), cognitive worker daemon thread, clean shutdown coordinator, and `main(argv=None) -> int`.
3. Root `main.py`: Root wrapper delegating to `parasite_ai.main:main`.
4. `launch_parasite.bat`: Windows launcher checking `uv`, running `uv sync`, and executing `uv run python main.py %*`.
5. `tests/test_entrypoints.py`: Automated test suite covering CLI parsing, dry-run, headless instantiation, signal handling, idempotent shutdown, and batch script validation.

Detailed technical design and code templates are fully documented in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_1\plan.md`.

---

## 5. Verification Method
1. **DPI Alias Verification**:
   `uv run python -c "from parasite_ai.ui.dpi import init_dpi_awareness; assert callable(init_dpi_awareness)"`
2. **CLI & Dry-Run Verification**:
   `uv run python main.py --dry-run --headless` (Must exit code 0 without hanging).
3. **Automated Test Suite**:
   `uv run pytest tests/test_entrypoints.py -v` (All tests must pass).
4. **Full Regression Test Suite**:
   `uv run pytest` (All existing 552 tests + new entrypoint tests must pass).
5. **Batch Script Syntax & Existence**:
   Verify `launch_parasite.bat` exists in root, contains `uv sync` and `uv run python main.py %*`.
