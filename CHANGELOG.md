# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Unified High-Fidelity Debug Logging Subsystem (`parasite_ai.main`, `parasite_ai.config`): Rotating file logger at `logs/parasite_debug.log` (15 MB rotation, 5 backups, millisecond timestamps, thread names, module and line numbers). Added `--debug` and `--log-file` CLI arguments.
- Diagnostic Tracing across Cognition, Execution & Misfires (`parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.affordance`): Direct logging of Pass 1 persona prompts and monologues, Pass 2 action prompts, raw model responses, parsed JSON actions, localized ROI diff verification results, strike transitions, caret check suppression, and sandboxed CLI execution tokens, exit codes, and stdout/stderr streams.
- Localized ROI Diffing (`parasite_ai.mind.dual_mind`): `BoundingBox.pad(padding_px=20)` with multi-monitor virtual screen bounds clamping (`3840x1080 @ 100% DPI`), scoping post-action visual difference verification to padded action targets (`extract_action_target_roi()`).
- Win32 Caret Focus Verification (`parasite_ai.mind.dual_mind`): 64-bit Win32 `GUITHREADINFO` ctypes struct and `check_caret_focus` verifying `(flags & GUI_CARETBLINKING) or (hwndCaret != 0)` prior to emitting `ActionType.TYPE` with a 250ms polling loop.
- Start Search Cadence Buffer (`parasite_ai.mind.resolver`): 250ms cadence pause in `UniversalAppResolver` post-`Win` key chord with millisecond preemption checks.
- Dynamic Living Plan schemas (`StepIntent`, `StepStatus`, `PlanStep`, `LivingPlan`) in `parasite_ai.mind.plan`.
- Strategic Gemini consultation protocol (`format_gemini_consultation_prompt`, `extract_strategic_blueprint_json`, `parse_gemini_consultation_response`) for multi-step reasoning.
- Non-blocking hard termination mechanism on `Ctrl+Alt+K` via `taskkill /F /T /PID` and `os._exit(1)`.
- Export alias `WebOffloadBackend = BrowserOffloadBackend` in `parasite_ai.mind.brain_manager`.
- Foveated Multi-Scale Perception Engine (`parasite_ai.vision.foveated`): 1:1 unscaled native pixel crops around cursor/active window targets alongside a lightweight global macro overview, with 64-bit `dHash` visual change gating and adaptive rate limiting.
- Universal Application Resolver (`parasite_ai.mind.resolver`): Generic multi-tier target resolution across arbitrary Windows applications (Tier 1 Set-of-Mark matching, Tier 2 Start Search chord, Tier 3 Run dialog fallback) without hardcoded application lists.
- Multimodal Visual Grounder (`parasite_ai.vision.vlm_grounder`): Local Qwen2.5-VL tag/box parsing with hybrid coordinate snapping to nearby UIA/SOM controls.
- Dynamic Living Plan integration into `DualMindPipeline`: automated stage sequencing, progress tracking, and unexpected modal dialog contingency insertion.

### Changed
- Default brain configuration in `config.yaml` set to `local_llm`.
- Application launcher `launch_parasite.bat` now explicitly passes `--brain-mode local_llm %*`.
- Eliminated legacy hardcoded application dictionary `app_map` in `DualMindPipeline.step`.
- Virtual desktop metrics in `parasite_ai.vision.capture`: dynamic `get_virtual_screen_bounds()` replaces fixed `(1080, 1920)` synthetic fallback for dual-monitor configurations.
- Browser offload prompt delivery in `parasite_ai.mind.offloader`: replaced character-by-character `KEYEVENTF_UNICODE` typing with high-speed `<100ms` `Ctrl+V` clipboard paste and safe user clipboard restoration.
- Local brain manager execution decoupling: `LocalBrainManager._init_backend` retains `BrainMode.LOCAL_LLM` and sets `BrainState.NO_MODEL_PRESENT` when local models are missing, without silently mutating mode to browser offload.
- `LocalBrainManager.generate`: raises `RuntimeError` when local model is unavailable in local mode rather than silently dispatching web offload.
- `LocalBrainManager.generate_thought`: returns graceful character monologue fallback without web offload if local inference fails.
- Screen corner slam panic handling in `PanicManager`: added 1.0-second edge-triggered debouncing to eliminate Qt event loop flooding.
- Sentinel harvest protocol in `SentinelClipboardVerifier.execute_harvest`: added periodic retriggering of `trigger_copy_action` during polling loop to prevent timeout errors.

### Fixed
- Companion Dock Internal Monologue Autoscroll (`parasite_ai.ui.companion_dock`): Fixed cursor positioning bug where `appendPlainText` left cursor at position 0, causing `ensureCursorVisible()` to force the viewport to the top of the text box. Cursor now advances to end and explicitly scrolls vertical scrollbar to maximum, ensuring the newest thought line is always visible.
- Unintended Gemini web offload on cognitive Pass 1 during local LLM execution.
- `OffloadHarvestError` timeouts caused by one-shot copy button clicking and clipboard verification deadlocks during browser offload.
- Companion Dock UI freezes during rapid screen corner mouse movements.

## [0.1.0] - 2026-10-29

### Added
- Python 3.12 environment with `uv` dependency management and lockfile pinning.
- Pydantic V2 configuration architecture (`AppConfig`, `SystemConfig`, `BrainConfig`, `UIConfig`, `SafetyConfig`, `HandsConfig`, `VisionConfig`).
- Pluggable `LocalBrainManager` supporting GGUF validation, streaming non-blocking downloads, CUDA 12 GPU acceleration via `llama-cpp-python`, and Zero-VRAM browser offload.
- Low-level Win32 hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) with injected input filtering (`LLMHF_INJECTED`, `LLKHF_INJECTED`).
- Sub-2ms hardware touch interrupt guard preemption token.
- Global emergency panic management (`Esc`, `Ctrl+Alt+P`, `Ctrl+Alt+Backspace`, screen corner slam).
- Privacy protection with `WindowGuard` monitoring password managers, terminals, and elevated UAC windows.
- Natural human kinematic mouse trajectories (Cubic Bézier, Flash & Hogan Min-Jerk velocity profile, micro-jitter, terminal overshoot).
- Unicode physical keyboard driver with human cadence jitter and `Shift+Enter` multiline safety.
- Always-on-top visible PyQt6 `CompanionDock` with character avatar, mood/state pills, speech/thought bubbles, and pause/panic controls.
- Transparent fullscreen click-through `GhostHUD` (`WS_EX_LAYERED | WS_EX_TRANSPARENT`) rendering Set-of-Mark numbered boxes and 300ms pre-click reticle.
- Hybrid screen grounding combining Win32 UI Automation tree walking with scoped RapidOCR fallback.
- Episodic working memory ring buffer with visual dHash screen difference checking and 3-strike failure loop detection.
- Dual-mind cognitive pipeline: Pass 1 character monologue (Persona Engine) and Pass 2 deterministic JSON action generation (Action Dispatcher).
- Physical Chrome offloader using visible browser automation and Sentinel Clipboard Verification.
- Master `RuntimeOrchestrator` coordinating GUI, background cognitive worker, and Win32 hook threads.
- Desktop entry points `main.py`, `launch_parasite.bat`, and emergency process killer `kill_parasite.bat`.
