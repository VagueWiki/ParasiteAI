# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed / Fixed - Stint P4.8.4 (`0.4.8.4`) Auto-Parasite on Consent Denial & 30s Gemini Cooldown
- **30s Gemini Circuit-Breaker Cooldown ([`config.py`](file:///C:/ParasiteAI/parasite_ai/config.py)):**
  - Lowered `ParasiteSkillConfig.breaker_cooldown_sec` default `600.0` → `30.0` seconds.
- **Auto-Parasite on Consent Denial ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - When `consent_handler` returns `False` (without cancellation token set) and `parasite_skill` is available, `DualMindPipeline.step()` now automatically calls `request_parasite_consult()` so the next step asks Gemini for an alternative safe path, and updated `RiskConsentView.cancel` confirmation text.
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):** `0.4.8.3` → `0.4.8.4`.

### Added / Fixed - Stint P4.8.3 (`0.4.8.3`) Post-Search Launch `DONE` Gate, Persistent Course Correction & Non-Destructive Window Switching
- **Post-Search Launch `DONE` Gate & Non-Destructive Planning ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Added pre-`DONE` gate in `DualMindPipeline.step()` vetoing premature `finished()` on `open/launch/start/play/run` goals when the last interactive step was `TYPE` (without `submit=True`) and no click/launch followed.
  - Strengthened `DO NOT CLOSE UNRELATED WINDOWS` (switch via taskbar / `win` / `win r` instead of closing active games/apps) and `COMPLETION & NO UNREQUESTED SAVES` in `UITARS_SYSTEM_PROMPT`.
- **Persistent Course Correction & `ParasiteSkill` Breaker Reset ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Persisted `_active_operator_steering` for up to 3 steps (`_active_operator_steering_ttl=3`).
  - Logged exact `ParasiteFailure` reasons in `ParasiteSkill._fail()`, added `reset_circuit_breaker()`, and wired `request_parasite_consult()` to reset the cooldown on manual `🧠 Parasite It`.
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):** `0.4.8.2` → `0.4.8.3`.

### Added / Fixed - Stint P4.8.2 (`0.4.8.2`) Live-Run Prompt Controls, Search-Bar Overwrite & Spatial Denial Scoping
- **Discord Idle vs. Active Controls & Rich Step Telemetry ([`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - Separated `ControlDeckView` (idle: `📝 New Task`, `📸 Screenshot`, `⚙️ Status`, `🛑 Panic` with explicit `custom_id`s) from `ActiveTaskControlsView` (live run: `🧭 Course Correct`, `🧠 Parasite It`, `📸 Screenshot`, `🛑 Panic`), attached to task dispatch and `step_completed` screenshot embeds.
  - Added `🧠 Parasite It` and `🧭 Course Correct` buttons to `RiskConsentView`, added `on_error` logging across all Views/Modals, trimmed `foreground_title`/`foreground_process` in consent embeds, and enriched `step_completed` embeds with Action, Coordinates, Thought, Window, Screen Diff %, and Tier/Strikes.
- **Search-Bar Overwrite & Spatial Denial Scoping ([`uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py), [`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `SEARCH & TEXT INPUT OVERWRITE` rule to `UITARS_SYSTEM_PROMPT` and auto-enabled `clear_first=True` when `TYPE` follows clicking a search/filter/address bar.
  - Scoped `CLICK_FAMILY` denial signatures to `(pattern, x // 96, y // 96)` so denying a `[X]` close click does not block unrelated clicks elsewhere, and injected `_active_operator_steering` directly before `generate_cua_step()`.
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):** `0.4.8.1` → `0.4.8.2`.

### Added / Fixed - Stint P4.8.1 (`0.4.8.1`) Discord Control Deck, Single-Denial Consent & "Parasite It" Gemini Tutorial
- **Always-Accessible Discord Control Button Deck ([`config.py`](file:///C:/ParasiteAI/parasite_ai/config.py), [`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - Added `ControlDeckView` (`📝 New Task`, `📸 Screenshot`, `🧭 Course Correct`, `🧠 Parasite It`, `⚙️ Status`, `🛑 Panic`), `/deck` slash command, `DiscordConfig.auto_post_deck: bool = True` (auto-posting on `on_ready` to `authorized_channel_ids[0]`), and attached `ControlDeckView` to `/status`, task dispatch, and `finished` embeds.
- **Single-Denial Consent Guard & `🛑 Abort Task` Button ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - Tracked denied risk signatures (`CLICK_FAMILY` / `action`, `pattern`) per episode in `DualMindPipeline._denied_risk_signatures` so denied `YELLOW`/`RED` actions (like `"No Thanks"` popup clicks flagged by `"close"` in reasoning) never re-prompt 3 times, suppressed `[CUA CLICK UPGRADE]` after consent denial, and added `🛑 Abort Task` to `RiskConsentView`.
- **Course Correction & On-Demand "Parasite It" Gemini Escalation ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py), [`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - Added `request_course_correction()` and `request_parasite_consult()` across `RuntimeOrchestrator` and `DualMindPipeline`, wired to `CourseCorrectModal` (`🧭 Course Correct`) and `🧠 Parasite It` in Discord.
- **Tutorial-Style Expected Results in `LivingPlan` ([`plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py)):**
  - Updated `LivingPlan.to_prompt_context()` to render `Target`, `Expected Result` (`success_criteria`), and `If Blocked` (`contingency`) for the active plan step.
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):** `0.4.8.0` → `0.4.8.1`.

### Fixed - Stint P4.8 (`0.4.8.0`) Post-Mortem Hotfixes: Episodic Memory, Desktop Fences Guard & Discord UX
- **Episodic Memory `AttributeError` & Episode Isolation ([`memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py), [`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Added thread-safe `EpisodicMemory.history` property and `__len__()` so `ActionConsentRequest` (`step_id=len(self.memory.history) + 1`) no longer raises `AttributeError: 'EpisodicMemory' object has no attribute 'history'` on `YELLOW`/`RED` risk actions.
  - Added `self.memory.clear()` in `RuntimeOrchestrator._run_loop()` and `_execute_goal_episode()` teardown so stale steps from crashed episodes cannot bleed into Step 1 of subsequent episodes.
- **Desktop Icon UIA Snapping & Stardock Fences Empty-Background `DOUBLE_CLICK` Guard ([`dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `ActionDispatcher._check_desktop_double_click_safety()`, `_is_desktop_surface_at_point()`, and `_probe_desktop_icon_uia()` to verify desktop `DOUBLE_CLICK` targets via UIA `ListItemControl` bounding boxes, snap near-misses to matching desktop `ListItem` icons, and fail-closed on empty desktop/Fence background double-clicks (preventing Fences from hiding all desktop icons) unless explicitly requested by the user goal.
- **Discord Screenshots & Streamlined Task Dispatch ([`config.py`](file:///C:/ParasiteAI/parasite_ai/config.py), [`discord_bot.py`](file:///C:/ParasiteAI/parasite_ai/ui/discord_bot.py)):**
  - Changed `DiscordConfig.milestone_screenshot_interval` default `3` → `1`, added `send_final_screenshot: bool = True`, and attached `final_screen.jpg` + `TaskQuickActionsView` (`📝 New Task` modal + `📸 Screenshot` button) to `finished` post-mortem embeds.
  - Added `on_message` / `_handle_text_message()` for authorized DMs, `@mention`s, `!task`/`!t`, `!panic`, and optional plain-text channel dispatch (`enable_message_tasks: bool = True`, `enable_message_content_intent: bool = False`, `use_task_threads: bool = False`).
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`test_memory.py`](file:///C:/ParasiteAI/tests/unit/mind/test_memory.py), [`test_discord_bot.py`](file:///C:/ParasiteAI/tests/unit/ui/test_discord_bot.py), [`test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`test_config.py`](file:///C:/ParasiteAI/tests/unit/core/test_config.py), [`test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.12` → `0.4.8.0`.

### Changed - Stage P4 (`0.4.0.0` – `0.4.7.12`) Graduation & `Stage P5` (`P5.1`) Handoff
- **Stage P4 Closure & Live Smoke Graduation ([`smoke_p4_7_20261117T044841Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T044841Z.json)):**
  - Verified `0.4.7.12` live smoke pass (`all_passed: true`: `P4.7-B` `5/5`, `P4.7-A` `9 steps`, `60.7s`, `214` chars of non-literal 2-sentence prose, `DONE`) and **114 passed** targeted unit + integration tests.
  - Graduated `P4.7` in [`benchmarks/results/.automation_eval_cursor.json`](file:///C:/ParasiteAI/benchmarks/results/.automation_eval_cursor.json), advancing `active_stage` to `P5.1`, and updated [`GATE_STATUS.md`](file:///C:/ParasiteAI/GATE_STATUS.md) and [`HANDOFF.md`](file:///C:/ParasiteAI/HANDOFF.md).

### Fixed - Stage P4 Closure: Stint P4.7.12 (`0.4.7.12`) Post-Completion `[EDITOR FOCUS GUARD]` `DONE` Promotion
- **Root Cause Forensics ([`smoke_p4_7_20261117T044420Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T044420Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - In `0.4.7.11`, `[EDITOR FOCUS GUARD]` broke the pre-typing click loop and `UI-TARS` composed 199 chars of valid 2-sentence non-literal prose at Step 9 (`non_literal_prose: true`), but on Steps 10–12 `UI-TARS` echoed `"currently obscured by other windows"` and clicked `*Untitled - Notepad` again; `[EDITOR FOCUS GUARD]` at Step 11 prompted `type(content=...)` instead of checking `goal_verifier.verify_goal_state()` and promoting to `DONE`, causing `MAX_STEPS`.
- **Goal-Verified `DONE` Promotion ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Updated `[EDITOR FOCUS GUARD]` in `DualMindPipeline.step()` to evaluate `self.goal_verifier.verify_goal_state(user_goal, cur_eff_win, [])` first and promote redundant editor clicks directly to `ActionType.DONE` when `ver.verified` is `True`.
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.11` → `0.4.7.12` (`parasite 0.4.7.12`), added `test_already_focused_editor_click_loop_promotes_to_done_when_goal_verified`, and verified **114 passed, 1 warning in 12.04s** across 4 targeted unit + integration test files.

### Fixed - Stage P4 Closure: Stint P4.7.11 (`0.4.7.11`) Already-Focused Editor Click-Loop Guard & Prompt Rule
- **Root Cause Forensics ([`smoke_p4_7_20261117T043425Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T043425Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - In the `0.4.7.10` live run, the test console stayed minimized and never closed (`P4.7-B` passed `5/5`), while `P4.7-A` launched `Untitled - Notepad (notepad.exe)` in Step 2 and then spent Steps 3–12 repeatedly clicking Notepad's `Text Editor` (`(197, 288)`, `(301, 264)`, `(322, 255)`) with `Diff: 0.0000` because `UI-TARS` perceived Notepad as obscured by background windows and `[CUA CLICK UPGRADE]` escalated repeated clicks to `DOUBLE_CLICK` instead of prompting `type(content=...)`.
- **Already-Focused Editor Click-Loop Guard ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Updated `DualMindPipeline.step()` so consecutive `CLICK`/`DOUBLE_CLICK` actions with `screen_diff < 0.02` inside an already-active text editor (`notepad.exe`, `wordpad.exe`, `notepad++.exe`) on pure writing/composing goals convert to `ActionType.WAIT` (`wait_ms=100`) and set `_cua_loop_warning` instructing `UI-TARS` to immediately emit `type(content=...)` instead of upgrading to `DOUBLE_CLICK`.
- **Already-Focused Prompt Rule ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Added `ALREADY FOCUSED TARGETS` rule to `UITARS_SYSTEM_PROMPT` instructing `UI-TARS` to check `Active Window` in Working Memory and emit `type(content=...)` directly when the target app is already active.
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.10` → `0.4.7.11` (`parasite 0.4.7.11`), added `test_already_focused_editor_click_loop_converts_to_wait_with_type_warning`, and verified **113 passed, 1 warning in 11.72s** across 4 targeted unit + integration test files.

### Fixed - Stage P4 Closure: Stint P4.7.10 (`0.4.7.10`) Host/Test-Console Click Guard, Live Probe Console Minimization & Background-Window Prompt Rule
- **Root Cause Forensics ([`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log#L1-L23)):**
  - During the `20:24:20` interactive `0.4.7.9` run of [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), `P4.7-B` passed and `P4.7-A` launched Notepad in Steps 1–2, then `UI-TARS` saw the `run_smoke_probe_p4_7.bat` console window (`HWND 2165288`, `consolewindowclass`) in the background and clicked `(1045, 92)` (`[X]` close button) to *"clear the workspace"*, terminating the running test console mid-step before any receipt was written.
- **Host & Test-Runner Click Guard ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `ActionDispatcher._check_host_window_click_safety()` and wired it into `ActionDispatcher.dispatch()` prior to `_evade_companion_dock_if_needed()` / `_activate_target_window_if_needed()`, blocking clicks targeting `GetConsoleWindow()`, `{os.getpid(), os.getppid()}`, or `ConsoleWindowClass`/`CASCADIA_HOSTING_WINDOW_CLASS` windows titled `"ParasiteAI Stage"`, `"ParasiteAI Benchmark"`, `"Benchmark Runner"`, or `"Smoke Probe"`.
- **Console Minimization & Prompt Rule ([`scripts/smoke_test_p4_7_generalization.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_7_generalization.py), [`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Added `_set_console_minimized()` in `smoke_test_p4_7_generalization.py` to minimize the runner console window during `probe_live_generative_notepad()` and restore it in `finally`.
  - Added `DO NOT CLOSE UNRELATED WINDOWS` rule to `UITARS_SYSTEM_PROMPT` instructing `UI-TARS` never to close background terminals/consoles to clear the workspace.
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.9` → `0.4.7.10` (`parasite 0.4.7.10`), added `test_host_window_click_guard_blocks_test_console_allows_notepad`, and verified **112 passed, 1 warning in 11.52s** across 4 targeted unit + integration test files.

### Fixed - Stage P4 Closure: Stint P4.7.9 (`0.4.7.9`) CompanionDock Window-Title Misidentification & Pytest Win32 Relocation Isolation
- **Root Cause Forensics ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log#L48)):**
  - `get_companion_dock_rect()` and `ActionDispatcher._evade_companion_dock_if_needed()` matched any visible window containing `"parasite"` in its title (including File Explorer open to `C:\ParasiteAI`, CMD/PowerShell debug consoles, and Antigravity IDE), calling `SetWindowPos(..., w, 56, ...)` during both live clicks and unmocked `pytest` runs (`headless=False` default).
  - `relocate_window_to_monitor()` and `Win32BrowserWindowBackend.ensure_on_primary_monitor()` lacked `PYTEST_CURRENT_TEST` isolation when `user32` was unmocked, lacked exemptions for File Explorer/terminals/IDEs/host PIDs, and moved/resized windows merely straddling Monitor 1 & Monitor 2 boundaries.
- **Strict Class Matching & Test Isolation ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`parasite_ai/mind/offloader.py`](file:///C:/ParasiteAI/parasite_ai/mind/offloader.py)):**
  - Added `_is_real_win32_window_mutation_blocked()` blocking Win32 window-mutation calls under `PYTEST_CURRENT_TEST` unless `user32` is explicitly mocked, and wired it across `get_companion_dock_rect()`, `_evade_companion_dock_if_needed()`, `relocate_window_to_monitor()`, and `Win32BrowserWindowBackend`.
  - Restricted `get_companion_dock_rect()` and `_evade_companion_dock_if_needed()` strictly to `CompanionDock` window class names (removing `"parasite" in title` and coordinate-only fallback matching).
  - Hardened `relocate_window_to_monitor()` to exempt self/parent PIDs, `explorer.exe`, terminals (`cmd.exe`, `powershell.exe`, `pwsh.exe`, `windowsterminal.exe`, `conhost.exe`), and IDEs (`code.exe`, `antigravity.exe`), and to skip windows already overlapping Monitor 1 (`rect.left < ml + mw and rect.right > ml`).
- **Tests, Version & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.8` → `0.4.7.9` (`parasite 0.4.7.9`), fixed `test_monitor1_progman_exemption_overlap_and_focus_recovery` to patch `parasite_ai.mind.dual_mind.relocate_window_to_monitor`, and added `test_companion_dock_evasion_never_touches_explorer_cmd_or_pytest` + `test_relocate_window_to_monitor_blocks_unmocked_pytest_protects_user_apps_and_overlap`.
  - **Verification:** **121 passed, 1 warning in 33.57s** across 9 targeted unit + integration test files.

### Fixed - Stage P4 Closure: Stint P4.7.8 (`0.4.7.8`) Meta-Outline Echo Gate, Duplicate Prose Suppression & Unrequested `Ctrl+S` Interceptor
- **Root Cause Forensics ([`smoke_p4_7_20261117T011501Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T011501Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - `P4.7-B` passed (`5/5`), while `P4.7-A` (`0.4.7.7`) exited on `MAX_STEPS` (`12` steps, `84.84s`): at Step 3, `UI-TARS` typed `"A brief overview of desktop automation. The first sentence is about the basic operations, and the second sentence is about the advanced features."` (`148` chars, `2` sentences — primed by the negative `'A brief overview of <topic>.'` phrase in `UITARS_SYSTEM_PROMPT` and slipping past `_is_prompt_echo()`'s single-sentence `< 100`-char guard).
  - On Step 4, duplicate `TYPE` triggered `[LOOP BREAKER]` -> `HOTKEY ['enter']`, causing Step 5 to double-type the text (`292` chars), and on Steps 6–12 `UI-TARS` ignored `Loop Intervention Warning` and oscillated `ctrl s` ↔ `Save As` `Cancel` until `MAX_STEPS`.
- **Meta-Outline & Opening-Sentence Topic-Echo Gate ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Extended `_is_prompt_echo(text, goal=...)` with `_META_OUTLINE_PATTERN` (catching structural placeholders such as `"the first sentence is about"` / `"the second sentence is about"`) and `_segment_echoes_goal()` across opening sentences (`< 100` chars) even in multi-sentence buffers.
- **De-Primed System Prompt ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Removed the verbatim `'A brief overview of <topic>.'` phrase from `GENERATIVE WRITING TASKS` in `UITARS_SYSTEM_PROMPT`, instructing the model positively to write factual body sentences directly without headings or sentence-outline commentary.
- **Goal-Aware Duplicate Prose & Unrequested `Ctrl+S` Guard ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Updated `[LOOP BREAKER]` so consecutive duplicate multi-word/punctuated prose (`len >= 40` or sentence-terminated) checks `goal_verifier.verify_goal_state()` rather than injecting `HOTKEY ['enter']`: promotes directly to `ActionType.DONE` if verified complete, or converts to diagnostic `WAIT` with `_cua_loop_warning` if incomplete.
  - Added `_goal_requests_save_or_close()` and a pre-dispatch `Ctrl+S` guard for non-save/non-close goals: promotes to `ActionType.DONE` when the goal is already verified complete, and blocks repeat `ctrl+s` cycles with `"Do NOT press Ctrl+S"` feedback when incomplete.
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_4_veto_feedback.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_4_veto_feedback.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.7` → `0.4.7.8` (`parasite 0.4.7.8`) and added 4 regression tests (`test_goal_verifier_rejects_multi_sentence_meta_outline_boilerplate`, `test_duplicate_prose_type_promotes_to_done_when_goal_verified_complete`, `test_unrequested_ctrl_s_promotes_to_done_when_goal_already_verified`, `test_repeat_unrequested_ctrl_s_blocked_when_goal_incomplete`).
  - **Verification:** **173 passed, 1 warning in 17.62s** across 9 targeted unit + integration test files.

### Fixed - Stage P4 Closure: Stint P4.7.7 (`0.4.7.7`) Generative Sentence-Count Gate, Topic-Echo Rejection & Unrequested `#32770` Modal Guard
- **Root Cause Forensics ([`smoke_p4_7_20261117T010318Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T010318Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - `P4.7-B` passed (`5/5`), while `P4.7-A` (`0.4.7.6`) suffered a **False-DONE**: `UI-TARS` typed a 1-sentence topic-echo title (`"A brief overview of desktop automation."`, `39` chars) at Step 3, clicked Notepad's Close `[X]` button at Step 4 (opening Notepad's `#32770` `"Notepad"` *Do you want to save changes?* modal dialog), and emitted `finished()` at Step 5, which `RuntimeGoalVerifier` accepted (`exit_reason: DONE`).
- **Sentence-Count & Goal-Word Overlap Echo Gate ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Added `_extract_required_sentence_count()`, `_count_sentences()`, and extended `_is_prompt_echo(text, goal=...)` with general content-word overlap (`>= 60%` non-stopword goal overlap on single-sentence buffers `< 100` chars).
  - Enforced both checks across `_derive_subgoal_checklist()` and `_check_window_and_app_state()` (`notepad_greeting_non_echo` and `notepad_sentence_count`).
- **Unrequested `#32770` Save/Confirmation Modal Guard ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Added `_find_unexpected_modal_dialog()` detecting open `#32770` `"Notepad"` / `"save changes"` / `"error"` / `"warning"` / `"confirm"` dialogs on non-teardown/non-save goals, blocking `DONE` (`unexpected_modal_dialog`) and surfacing `[ ] Dismiss unexpected dialog (...)` in `_derive_subgoal_checklist()`.
- **Prompt & Version Alignment ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Strengthened `GENERATIVE WRITING TASKS` and `COMPLETION & NO UNREQUESTED SAVES` in `UITARS_SYSTEM_PROMPT` to explicitly forbid 1-sentence title restatements and clicking Close (`X`) / `alt f4`.
  - Wired `parasite_ai.__version__` dynamically into `parasite_ai/main.py --version` and bumped unified version `0.4.7.6` → `0.4.7.7` (`parasite 0.4.7.7`).
- **Targeted Tests ([`tests/unit/test_p4_7_1_loop_and_checklist.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_1_loop_and_checklist.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Added 2 regression tests covering 1-sentence topic echo rejection, sentence-count enforcement, and `#32770` `"Notepad"` modal dialog veto.
  - **Verification:** **119 passed in 3.12s** across 5 targeted unit test files + **24 passed in 8.95s** in `test_parasite_skill_pipeline.py`.

### Fixed - Stage P4 Closure: Stint P4.7.6 (`0.4.7.6`) `capture.py` Circular Import Fix, Veto Stub Safety & Full 679-Test Suite Pass
- **Circular Import Elimination ([`parasite_ai/vision/capture.py`](file:///C:/ParasiteAI/parasite_ai/vision/capture.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py)):**
  - Removed the top-level `from parasite_ai.safety.window_guard import ensure_interactive_desktop` introduced in `P4.7.3` (which caused `ImportError: cannot import name 'ScreenCapture' from partially initialized module 'parasite_ai.vision.capture'` when importing `tests/unit/vision/test_grounding.py` in isolation) and replaced it with a lazy `_safe_ensure_interactive_desktop()` helper.
  - Added `test_vision_capture_imports_without_circular_import` and made `test_ensure_interactive_desktop` hermetic via mocked `ctypes.windll.user32`.
- **Veto Stub Compatibility & Test Determinism ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Guarded `verification.checked_conditions` with `getattr(verification, "checked_conditions", None) or ()` in `DualMindPipeline.step()` so lightweight `SimpleNamespace` verifier stubs (such as `test_dual_mind_drag_dispatch_and_veto_loop_telemetry`) do not raise `AttributeError`.
  - Patched `parasite_ai.mind.dual_mind.check_caret_focus` in `test_pipeline_matches_workflow_skill_and_skips_gemini_proactive` to eliminate live-OS foreground caret flakiness, and updated the version assertion to `0.4.7.6`.
- **Version Bump & Full Suite Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified version `0.4.7.5` → `0.4.7.6`.
  - **Full Unit + Integration Suite:** **679 passed, 1 warning in 75.31s** (`.\.venv\Scripts\python.exe -m pytest -q --tb=short`), including isolated `tests/unit/vision/test_grounding.py` (**14 passed in 3.21s**).

### Fixed - Stage P4 Closure: Stint P4.7.5 (`0.4.7.5`) Idle-Gated Smoke Interactive Desktop Attachment & Live Pass
- **Root Cause Forensics:** Running `scripts/run_idle_gated_smoke.py --auto-start-llama` from an isolated background desktop (`WinSta0\exebox-...`) skipped live verification because `check_live_bitblt_capture()` and `get_user_idle_seconds()` did not call `ensure_interactive_desktop()`, causing `mss.MSS().grab(...)` to fail with `"BitBlt capture unavailable: Windows graphics function failed (no error provided): BitBlt"`.
- **Interactive Desktop Attachment ([`scripts/run_idle_gated_smoke.py`](file:///C:/ParasiteAI/scripts/run_idle_gated_smoke.py), [`tests/unit/test_idle_gated_smoke.py`](file:///C:/ParasiteAI/tests/unit/test_idle_gated_smoke.py)):**
  - Wired `ensure_interactive_desktop()` into `get_user_idle_seconds()`, `check_live_bitblt_capture()`, and `run_if_ready()` (with an injectable `desktop_attach_fn` for hermetic unit testing).
  - Added `test_run_if_ready_attaches_interactive_desktop_before_gates` verifying desktop attachment precedes `BitBlt` and readiness gates.
- **Version Bump & Verification ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`smoke_p4_7_20261117T003922Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T003922Z.json)):**
  - Bumped unified version `0.4.7.4` → `0.4.7.5`.
  - **Targeted Tests:** **24 passed in 1.69s** across `test_idle_gated_smoke.py`, `test_p4_7_generalization.py`, `test_p4_7_1_loop_and_checklist.py`, and `test_p4_7_4_veto_feedback.py`.
  - **Live Idle-Gated Smoke (`0.4.7.5`):** [`smoke_p4_7_20261117T003922Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T003922Z.json) passed (`all_passed=true`, `P4.7-B` 5/5, `P4.7-A` 4 steps / `27.96s` / `215` chars of original prose / `mss` backend).

### Changed - Scheduled Automation Zero-Input Governance (`parasiteai-eval-iterate`)
- **Scheduled Autonomous Exemption ([`AGENTS.md`](file:///C:/ParasiteAI/AGENTS.md), [`GEMINI.md`](file:///C:/ParasiteAI/GEMINI.md), [`.agents/rules/engineering_cadence.md`](file:///C:/ParasiteAI/.agents/rules/engineering_cadence.md)):**
  - Added an explicit `Scheduled Autonomous Automation Exemption` under Section 2 waiving the interactive planning/approval halt (`RequestFeedback: true` / `ask_question`) strictly for unattended `parasiteai-eval-iterate` runs running in `UNATTENDED AUTONOMOUS MODE`, while preserving strict interactive Section 2 gating for normal user sessions.
- **Idempotency Telemetry & Prompt Alignment ([`scripts/farm_eval_receipts.py`](file:///C:/ParasiteAI/scripts/farm_eval_receipts.py), [`tests/unit/test_idle_gated_smoke.py`](file:///C:/ParasiteAI/tests/unit/test_idle_gated_smoke.py)):**
  - Added `latest_smoke_receipt` and `awaiting_live_smoke_for_cursor_version` to `farm_new_results()` so overlapping runs skip cleanly when `cursor_version` already leads the latest smoke receipt and `new_receipts_count == 0`.
  - Updated `sidecar.json` (`parasiteai-eval-iterate`) to invoke the Section 2 exemption, forbid `RequestFeedback: true` / `ask_question`, and align CLI invocations strictly to `access_grants`.

### Fixed - Stage P4 Closure: Stint P4.7.4 (`0.4.7.4`) Prompt-Echo Veto Ordering & Generative Composition Hinting
- **Root Cause Forensics ([`smoke_p4_7_20261116T224436Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261116T224436Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - `P4.7-B` passed (`5/5`), while `P4.7-A` exited on `MAX_STEPS` (`64.08s`) after `UI-TARS` typed `"A 2-sentence overview of desktop automation\r\n\r\n"` without trailing sentence punctuation.
  - `RuntimeGoalVerifier.verify_goal_state()` checked `len < 15 or not any(p in buf_text for p in (".", "!", "?"))` **before** the non-echo check, returning `"Notepad composed text is too short or lacks sentence punctuation."` instead of diagnosing the echoed prompt.
  - On `consecutive >= 2` pre-DONE vetoes, `DualMindPipeline.step()` appended `"If an inline rename, Save As box, or dialog edit is still open..."`, nudging `UI-TARS` into pressing `ctrl s` (`Save As`).
- **Prompt-Echo Check Ordering ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Moved the prompt-echo check ahead of the length/punctuation check inside `RuntimeGoalVerifier.verify_goal_state()` and added an actionable veto reason (`"Notepad contains echoed prompt instructions instead of composed prose. Select all (ctrl a) and type actual original sentences."`).
- **Composition-Specific Veto Hint ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Suppressed the `Save As box` `commit_hint` when `checked_conditions` contains `notepad_greeting_non_echo` or `notepad_greeting_composed`, replacing it on `consecutive >= 2` with `" (Do NOT press Ctrl+S; click the Notepad text area, select all with ctrl+a, and type original sentences.)"`.
- **Upstream Prompt Refinement ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Strengthened `GENERATIVE WRITING TASKS` in `UITARS_SYSTEM_PROMPT` using abstract symbolic placeholders (`<topic>`, `<sentence 1>. <sentence 2>.`) to discourage echoing the task's topic phrase.
- **Version Bump & Tests ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_1_loop_and_checklist.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_1_loop_and_checklist.py), [`tests/unit/test_p4_7_4_veto_feedback.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_4_veto_feedback.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Wired `[PRE-DONE VETO]` into `DualMindPipeline._cua_loop_warning` (cleared on productive `ActionType.TYPE`), extracted shared `_is_prompt_echo()` across `verify_goal_state()` and `_derive_subgoal_checklist()` with an incomplete/prompt-echo hint, and sharpened `GENERATIVE WRITING TASKS` (`<N>-sentence overview of <topic>`).
  - Bumped unified version `0.4.7.3` → `0.4.7.4` (`parasite 0.4.7.4`) and added 5 targeted regression tests (`test_goal_verifier_prioritizes_non_echo_over_missing_punctuation`, `test_dual_mind_notepad_composition_veto_suppresses_save_as_commit_hint`, and 3 tests in `test_p4_7_4_veto_feedback.py`).
  - **Verification:** **140 passed, 1 warning in 10.68s** across 6 targeted test files.

### Fixed - Stage P4 Closure: Stint P4.7.3 (`0.4.7.3`) Interactive Desktop Attachment (`SetThreadDesktop`), Automated BitBlt Capture & Non-Interactive Smoke Pass
- **Root Cause Forensics ([`smoke_p4_7_20261116T223220Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261116T223220Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - In background/scheduled automation environments, runner processes execute on an isolated thread desktop (`WinSta0\exebox-...`) rather than the active user input desktop (`WinSta0\default`).
  - GDI `BitBlt` with `CAPTUREBLT` returned `ERROR_ACCESS_DENIED (5)`, causing `ScreenCapture` to fall back to a blank synthetic black frame (brightness 0.0), while `SendInput` hotkey dispatch was cancelled or interrupted.
  - Blinded by black frames, `UI-TARS` attempted exploratory hotkeys (`ctrl+alt+s`), failing `P4.7-A` on `MAX_STEPS`.
- **Interactive Desktop Attachment (`SetThreadDesktop`) ([`parasite_ai/safety/window_guard.py`](file:///C:/ParasiteAI/parasite_ai/safety/window_guard.py)):**
  - Added `ensure_interactive_desktop() -> bool` which securely queries `user32.OpenInputDesktop(0, False, 0x01FF)` (or falls back to `OpenDesktopW('default')`) and attaches the calling thread via `user32.SetThreadDesktop(hdesk)` in `<0.1ms` before cleanly closing the desktop handle.
- **Subsystem Integration ([`parasite_ai/vision/capture.py`](file:///C:/ParasiteAI/parasite_ai/vision/capture.py), [`parasite_ai/hands/keyboard.py`](file:///C:/ParasiteAI/parasite_ai/hands/keyboard.py), [`parasite_ai/hands/mouse.py`](file:///C:/ParasiteAI/parasite_ai/hands/mouse.py), [`scripts/smoke_test_p4_7_generalization.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_7_generalization.py)):**
  - Called `ensure_interactive_desktop()` across `ScreenCapture._init_backend()`, `_get_thread_sct()`, and `capture_screen()`, enabling GDI `mss` BitBlt to capture live 1080p RGB screen frames (`mean brightness: ~143.7`) in automated/background contexts.
  - Wired `ensure_interactive_desktop()` into `Win32InputBackend.send_inputs()`, `Win32MouseDriver._send_absolute_move()`, and `_send_mouse_flag()`.
  - Added `ensure_interactive_desktop()` to `smoke_test_p4_7_generalization.py:main()` and `probe_live_generative_notepad()`, and recorded `capture_backend` in the JSON receipt.
- **Receipt & Telemetry Verification ([`smoke_p4_7_20261116T224205Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261116T224205Z.json)):**
  - `P4.7-B` (Sandboxed Generalization & Safety): **PASSED (`5/5` checks green)**.
  - `P4.7-A` (Live Unseen Generative Notepad Task): **PASSED** in **4 steps** and **28.63s** (`exit_reason: DONE`, `notepad_text_len: 235`, `non_literal_prose: True`, `capture_backend: mss`).
  - Total Stage P4.7 Smoke Probe: **PASSED (`all_passed: True`)**.
- **Version Bump & Tests ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Unified version bumped from `0.4.7.2` to `0.4.7.3` (`parasite 0.4.7.3`).
  - Added unit test `test_ensure_interactive_desktop()` and verified **27 passed** preflight unit tests and **24 passed** integration pipeline tests.

### Fixed - Stage P4 Closure: Stint P4.7.2 (`0.4.7.2`) Parser `rstrip('\\n')` Truncation Fix, Single-Char Ping-Pong Guard & Generative Prose Enforcement
- **Root Cause Forensics ([`smoke_p4_7_20261116T221916Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261116T221916Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - `P4.7-B` passed (`5/5`), while `P4.7-A` hit `MAX_STEPS` because `uitars_parser.py` called `raw_text.rstrip("\\n")` (a character-set strip of `'\\'` and `'n'`) on `type(content='A 2-sentence overview of desktop automation\n')`, truncating `'automation'` → `'automatio'`, which caused `UI-TARS` to spend Steps 4–12 typing `'n'` while `[LOOP BREAKER]` converted alternating `'n'` steps into `Enter`.
- **Exact Newline Suffix Stripping & Generative Writing Rule ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Replaced `.rstrip("\r\n").rstrip("\n").rstrip("\\n")` with exact suffix regex `re.sub(r"(?:\\n|\r?\n)+$", "", raw_text)` so words ending in `'n'` (`automation`, `python`, `open`) are never truncated when `submit=True`.
  - Added `GENERATIVE WRITING TASKS` rule to `UITARS_SYSTEM_PROMPT` instructing `UI-TARS` to type actual original prose rather than echoing prompt phrases as headers.
- **Single-Char `TYPE` → `Enter` Ping-Pong Guard ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Restricted the repetitive-typing `Enter` loop breaker to multi-char strings (`len(cur_text) >= 2`) without an `Enter` hotkey in the immediately preceding cycle.
- **`"2-sentence"` & Non-Echo Verifier Coverage ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Updated `RuntimeGoalVerifier.verify_goal_state()` to check `"2-sentence"` alongside `"two-sentence"`/`"greeting"` and reject echoed overview prompt phrases lacking composed prose.
- **Version Bump & Tests ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`tests/unit/test_p4_7_1_loop_and_checklist.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_1_loop_and_checklist.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version `0.4.7.1` → `0.4.7.2` and added 3 regression tests (`rstrip` suffix preservation, single-char `'n'` non-conversion, and `2-sentence` non-echo verification).
  - **Verification:** `parasite 0.4.7.2` and **156 passed, 1 warning in 11.59s** across 7 targeted test files.

### Fixed - Stage P4 Closure: Stint P4.7.1 (`0.4.7.1`) Live Smoke `P4.7-A` Unrequested-Save Suppression, Notepad Composition Checklist & Oscillation Loop Feedback
- **Root Cause Forensics ([`smoke_p4_7_20261116T220817Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261116T220817Z.json), [`logs/parasite_debug.log`](file:///C:/ParasiteAI/logs/parasite_debug.log)):**
  - `P4.7-B` passed (`5/5` sandbox checks), and `P4.7-A` bypassed `notepad-write-text` and typed 177 chars of generated 2-sentence prose by Step 3, then entered a Steps 4–12 `Ctrl+S` ↔ `Cancel` `ABAB` loop (`MAX_STEPS`) because `UITARS_SYSTEM_PROMPT` lacked a no-unrequested-saves completion rule, `_derive_subgoal_checklist()` omitted general unquoted Notepad writes, and `[TIER 2 SUPPRESSED]` silently reset strikes while `EpisodicMemory.format_for_prompt()` still suggested `Ctrl+S` on strikes.
- **No-Unrequested-Saves Completion Rule ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Added `COMPLETION & NO UNREQUESTED SAVES` rule to `UITARS_SYSTEM_PROMPT` instructing `UI-TARS` not to press `ctrl s`, save, or close windows unless explicitly requested, and to emit `finished()` immediately once all requested text/items are visible on screen.
- **Unquoted Notepad Composition Checklist & All-Satisfied Hint ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Extended `RuntimeGoalVerifier._derive_subgoal_checklist()` to emit `[x] Compose text in Notepad` / `[x] Write text in Notepad` for unquoted sentence/write/compose/draft prompts (while preserving `Record heading text into Notepad` ordering), and added an all-`[x]` completion status hint in `build_working_memory_snapshot()`.
- **Oscillation Strike Distinction & `[TIER 2 SUPPRESSED]` Loop Warning ([`parasite_ai/mind/memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py), [`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Updated `EpisodicMemory.format_for_prompt()` to distinguish `LOOP STRIKE` (`screen_diff >= threshold`) from `NO SCREEN CHANGE` and removed hardcoded `Ctrl+S` from strike suggestions.
  - Added `DualMindPipeline._cua_loop_warning` (populated on `is_oscillating` and `[TIER 2 SUPPRESSED]`, injected into `working_memory_context`, cleared on productive progress) and aligned `EpisodicMemory.record_step()` with `is_oscillating` strikes.
- **Smoke Prompt, Version Bump & Tests ([`scripts/smoke_test_p4_7_generalization.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_7_generalization.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`tests/unit/test_p4_7_1_loop_and_checklist.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_1_loop_and_checklist.py), [`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Updated `P4.7-A` goal to domain-neutral `"Open Notepad and write a 2-sentence overview of desktop automation"`, bumped unified version `0.4.7.0` → `0.4.7.1`, and added 4 targeted unit tests in `test_p4_7_1_loop_and_checklist.py`.
  - **Verification:** `parasite 0.4.7.1` and **149 passed, 1 warning in 12.43s** across 7 targeted test files (`test_p4_7_1_loop_and_checklist.py`, `test_p4_7_generalization.py`, `test_goal_verifier.py`, `test_memory.py`, `test_uitars_parser.py`, `test_p4_6_8_stabilization.py`, `test_parasite_skill_pipeline.py`).

### Added - Stage P4 Closure: Stint P4.7 (`0.4.7.0`) Real-World Skill Generalization, Synchronous `ContentScanner`, `{{slot}}` Parameterization & Deferred Co-Author Queue
- **Synchronous Zero-VRAM `ContentScanner` ([`parasite_ai/safety/content_scanner.py`](file:///C:/ParasiteAI/parasite_ai/safety/content_scanner.py), [`parasite_ai/safety/__init__.py`](file:///C:/ParasiteAI/parasite_ai/safety/__init__.py)):**
  - Added `ScanResult(allowed, text, reason, redacted_count)`, `ContentScanner`, and `sanitize_or_reject()` hard-rejecting prompt-injection markers (`<|im_start|>`, `<|endoftext|>`, `[system]`, `ignore previous/all prior instructions`) and redacting secrets (`sk-...`, `AIza...`, `ghp_...`, `Bearer ...`, `PRIVATE KEY` blocks, `password=/passwd=/secret=/api_key=/access_token=`) with `[REDACTED_SECRET]`.
  - Enforced across `SkillRegistry.save()` (pre-YAML field-level sanitization preserving safe scalar quoting) and `AppMemory.store_farmed_plan()` (with `ParasitePlan` JSON re-validation post-redaction).
- **Automatic `{{slot}}` Parameterization & `app_profiles` Process Lookup ([`parasite_ai/mind/app_memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/app_memory.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Added `AppMemory.get_last_process(program_hint)` querying `app_profiles` for discovered executable names beyond static `known_procs`.
  - Added `_extract_slot_template()` in `RuntimeOrchestrator._promote_farmed_plans()` extracting shared Windows paths (`{{path}}`), arithmetic expressions (`{{expr}}`, whitespace-normalized), and quoted literals (`{{text}}`) across `goal_norm` and non-launch `TYPE` steps into `SkillParameter(required=True)` and anchored `goal_patterns` (`<= 256` chars, preserving `keywords`).
- **Deferred `_pending_coauthor/` Queue & Live Smoke Runner ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py), [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat), [`scripts/smoke_test_p4_7_generalization.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_7_generalization.py)):**
  - Updated `SkillLearner.maybe_learn()` to atomically queue `ContentScanner`-cleaned traces under `data/skills/_pending_coauthor/` when trace purity/novelty passes and `ParasiteSkill` is unavailable or times out (`HARVEST_TIMEOUT`/`GENERATION_TIMEOUT`), plus `process_pending_coauthor(max_items=1)` invoked opportunistically post-episode in `RuntimeOrchestrator` when `learned is None`.
  - Added [`run_smoke_probe_p4_7.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_7.bat) and [`scripts/smoke_test_p4_7_generalization.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_7_generalization.py) with `[1/4]` `llama-server` status/auto-start, `[2/4]` `check_gpu_governance.py` VRAM headroom check, `[3/4]` CLI `--version` + 19 preflight P4.7/SkillRegistry unit tests (`19 passed in 1.13s`), and `[4/4]` QuickEdit-disabled sandbox (`P4.7-B`, `passed=True`) + live unseen generative Notepad task (`P4.7-A` with `read_notepad_buffer()` non-literal prose verification).
- **Tests ([`tests/unit/test_p4_7_generalization.py`](file:///C:/ParasiteAI/tests/unit/test_p4_7_generalization.py), [`tests/unit/mind/test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py)):**
  - Added 7 targeted unit tests in `test_p4_7_generalization.py` and updated `test_skill_registry.py` (`SkillProvenance.LEARNED` quarantine test + `AUTHORED` `STALE` degradation test).

### Changed - Stage P4 Closure: Stint P4.7 (`0.4.7.0`) Trace Ceiling, Baseline Skills & Version Bump
- **Long-Horizon Trace Ceiling ([`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py)):**
  - Raised `SkillsConfig.max_trace_steps` default from `25` to `40` and upper bound from `50` to `60`.
- **Baseline Skill Restoration ([`data/skills/minimize-notepad/SKILL.md`](file:///C:/ParasiteAI/data/skills/minimize-notepad/SKILL.md), [`data/skills/notepad-write-text/SKILL.md`](file:///C:/ParasiteAI/data/skills/notepad-write-text/SKILL.md)):**
  - Restored `minimize-notepad` from `_quarantine/` to `data/skills/minimize-notepad/SKILL.md` (`state: ACTIVE`, drift comments stripped) and cleaned `notepad-write-text/SKILL.md` (`consecutive_failures: 0`, stale quarantine comment stripped).
- **Unified Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified version from `0.4.6.11` to `0.4.7.0` (`parasite 0.4.7.0`).

### Fixed - Stage P4 Closure: Stint P4.7 (`0.4.7.0`) Literal-vs-Generative Gate, `AUTHORED` Slug Protection, Startup Drift Scope & Monitor-1 Focus Recovery
- **Literal vs. Generative Intent Gate ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Updated `SkillRegistry._score_skill()` to inspect `goal_str` flanking `(m.start(k), m.end(k))` as well as `v` for quote delimiters on `text`/`note`/`content`/`body`/`message` captures; unquoted captures containing generative cues (`short`, `sentence`, `greeting`, `poem`, `story`, `essay`, `summary`, `summarize`, `overview`, `presentation`, `slide`, `explain`, `about yourself`, `draft a/an`) return `None` (`L1-05` fix).
- **`AUTHORED` Baseline Protection & Startup Drift Fix ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py), [`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Protected non-draft `SkillProvenance.AUTHORED` skills from `_quarantine/` eviction in `SkillRegistry.record_outcome()` and `quarantine(..., force: bool = False)`, transitioning them to `SkillState.STALE` instead (`reject_draft()` passes `force=True`).
  - Restricted startup `check_visual_drift()` quarantine in `DualMindPipeline._initialize_or_update_plan()` to `SkillType.REFLEX_MICRO_SKILL` (matching `step()`), eliminating false drift quarantines on coordinate-free keyboard workflows.
- **Monitor-1 Shell Exemption & Focus Recovery ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Wired `window_guard` into `ActionDispatcher` and `target_process` into `dispatch()`, exempted `Progman`/`WorkerW` from off-monitor geometry blocks (keeping `alt+f4`/`win+down` blocked on shells), switched Monitor-1 bounds checks to horizontal overlap (`rect.left < ml + mw and rect.right > ml`), and added `_recover_monitor_window_focus()` prioritizing visible Monitor-1 `#32770` modals, then `target_process`, then topmost non-destructive Monitor-1 app windows (`L2-06`/`L2-07` fix).
  - **Verification:** `68 passed` targeted (`test_p4_7_generalization.py` + 8 skill/memory/safety suites), **full `4.X` closure suite `661 passed, 1 warning in 163.33s (0:02:43)`**, `parasite 0.4.7.0`.

### Fixed - Stage P4: Stint P4.6.11 (`0.4.6.11`) Atomic Keyboard Dispatch, Protected-Window Hotkey Guard, `InterruptGuard` Edge Triggering & `pytest` Win32 Hardware Isolation
- **Root Cause Forensics (Live Bot & `pytest` Stuck Modifiers):**
  - Forensic trace of `L1-06` (`"Close Notepad"`, `logs/parasite_debug.log`, `benchmarks/results/L1-06_receipt.json`) showed Step 1 closed Notepad via `alt+f4`, after which a stale `AppMemory` plan (`#18`) caused Step 2 to dispatch `alt+f4` into foreground `cmd.exe` (`ParasiteAI Stage P4 Benchmark Runner`) during `KeyboardDriver.hotkey()`'s `sleep_interruptible(0.030)` mid-chord while `VK_MENU` (`Alt`) was held down, terminating the runner with `Alt` stuck down system-wide.
  - Identified missing `KEYEVENTF_EXTENDEDKEY` flags and scan codes for `VK_LWIN`/`VK_RWIN`/`VK_RMENU`/`VK_RCONTROL` and missing `VK_TAB` / `VK_LWIN` / `VK_RWIN` cleanup across emergency release paths, as well as spurious `VK_MENU` key-up synthesis when `GetKeyState` reported `0xff80` in headless console Python processes without a message loop.
  - Identified unmocked Win32 hook/focus/keystroke side effects running during `pytest` (`InterruptGuard.start()`, `PanicManager` `backend=None`, `ActionDispatcher`, `tests/integration/test_e2e_integration.py`, `tests/unit/mind/test_app_memory.py`).
- **Atomic Keyboard Batches & State-Checked Releases ([`parasite_ai/hands/keyboard.py`](file:///C:/ParasiteAI/parasite_ai/hands/keyboard.py), [`parasite_ai/safety/panic.py`](file:///C:/ParasiteAI/parasite_ai/safety/panic.py), [`benchmarks/verifiers.py`](file:///C:/ParasiteAI/benchmarks/verifiers.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Defined `EXTENDED_VKS` and `ALL_MODIFIER_AND_LOCK_VKS` (12 keys including `VK_LWIN`, `VK_RWIN`, and `VK_TAB`).
  - Added `Win32InputBackend.is_key_down()` (strictly checking `GetAsyncKeyState(vk) & 0x8000` so unpumped `GetKeyState` `0xff80` cannot trigger false positives) and `map_vk_to_scan()` (`MapVirtualKeyW`), `MockInputBackend` equivalents, plus a weakref `_atexit_release_driver` handler on `Win32InputBackend`.
  - Refactored `KeyboardDriver.hotkey()` and `_send_shift_enter()` to single atomic `send_inputs()` batches built via `_build_vk_input()` (`KEYEVENTF_EXTENDEDKEY` + scan codes) wrapped in `try...finally`, wrapped `_send_unicode_char()` and `_send_plain_enter()` in `try...finally`, and state-checked `emergency_release_keys()`, `PanicManager.emergency_hardware_release()`, and `release_stuck_input_state()` before emitting key/button UP events.
  - Bound `self.interrupt_guard.panic_manager.backend = self.keyboard_driver.backend` in `RuntimeOrchestrator.__init__` and guarded `PanicManager.emergency_hardware_release()` raw `user32` fallback under `PYTEST_CURRENT_TEST`.
- **`InterruptGuard` Rising-Edge Semantics & Test Isolation ([`parasite_ai/safety/interrupt_guard.py`](file:///C:/ParasiteAI/parasite_ai/safety/interrupt_guard.py)):**
  - Skipped live `SetWindowsHookExW`/`RegisterHotKey` installation in `_hook_thread_entry()` when `PYTEST_CURRENT_TEST` is set, guarded `CallNextHookEx` behind non-null hook handles, ignored key-up events (`LLKHF_UP`/`WM_KEYUP`/`WM_SYSKEYUP`) in `_signal_physical_touch()` while still routing all key events to `PanicManager.check_key_event()`, and made `_on_interrupt_callback` strictly rising-edge (`if not was_interrupted:`).
- **Protected-Foreground Hotkey Guard, `AppMemory` Safety & Circular Import Fix ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), `data/app_memory.db`):**
  - Broke pre-existing circular import between `parasite_ai/safety/__init__.py` and `dual_mind.py` by moving `classify_action_risk` from top-level to lazy import inside `DualMindPipeline.step()`.
  - Added `ActionDispatcher._is_simulated_mode()` and `_check_foreground_hotkey_safety()` (wired into `HOTKEY`, `MINIMIZE_WINDOW`, `CLOSE_WINDOW`, `BURST`), and wrapped `AttachThreadInput` in `try...finally`.
  - Extracted `is_single_window_mgmt_goal()` in `should_trigger_proactive_plan()` and `_initialize_or_update_plan()` to skip Layer 1.5 `AppMemory` lookup on single-window management goals and `alt+tab`-starting plans, suppressed `Strategic Advisor Guidance` once teardown goals verify closed (`pre_ver.verified is True` / `"Teardown goal is fulfilled -> Emit DONE"`), and deleted stale farmed plans `id IN (1, 3, 18)` from `data/app_memory.db`.
- **Tests & Version Bump ([`tests/unit/test_p4_6_11_keyboard_safety.py`](file:///C:/ParasiteAI/tests/unit/test_p4_6_11_keyboard_safety.py), [`tests/integration/test_e2e_integration.py`](file:///C:/ParasiteAI/tests/integration/test_e2e_integration.py), [`tests/unit/mind/test_app_memory.py`](file:///C:/ParasiteAI/tests/unit/mind/test_app_memory.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py), [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py)):**
  - Added `tests/unit/test_p4_6_11_keyboard_safety.py` (5 unit tests), added `"--simulation"` in `test_e2e_integration.py` and `simulation_mode=True` in `test_app_memory.py`, and bumped unified version from `0.4.6.10` to `0.4.6.11`.
  - **Verification:** `124 passed, 1 warning in 34.42s` across all 9 targeted test files, `parasite 0.4.6.11`, and post-pytest modifier check returned `stuck_vks_after_pytest: []`.

### Fixed - Stage P4: Stint P4.6.10 (`0.4.6.10`) `SkillRegistry` Precision Guard, `BURST` Oscillation Detection, Repeat-Aware Diff Credit & `_teardown()` Settle
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.9` to `0.4.6.10`.
- **`SkillRegistry._score_skill()` Filename & Verb Mismatch Guard ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Rejected keyword-only skill matches (`goal_patterns == []`) when the goal specifies explicit non-`.exe` filenames or primary action verbs (`rename`, `delete`, `remove`, `create`, `copy`, `move`, `minimize`, `close`, `save`) absent from the skill's `id`/`name`/`description`/`keywords` (preventing `open-...-seed-txt` from hijacking `L2-04`).
- **`ActionType.BURST` Oscillation Detection & Repeat-Aware CUA Diff Credit ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `ActionType.BURST` sub-action matching and `BURST`/`TYPE` cross-matching to `_actions_match_for_oscillation()` and included `ActionType.BURST` in the oscillation check.
  - Suppressed the CUA `screen_diff_threshold` (`0.0200`) floor when an action repeats the previous step with `< 0.002` pixel change, preventing repeated no-op `TYPE`/`BURST` loops (`L2-06`, `L3-02`) from masking strikes.
- **`ParasiteSkill._teardown()` Post-Minimize Settle ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Added a `0.15s` settle after fallback `minimize_window(gemini_hwnd)` when Chrome remained foreground (`L3-02`).
- **Tests ([`tests/unit/test_p4_6_10_fixes.py`](file:///C:/ParasiteAI/tests/unit/test_p4_6_10_fixes.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Added 3 targeted unit tests covering keyword-skill filename/verb mismatch rejection, `BURST` oscillation + no-diff strike escalation, and `_teardown()` post-minimize settle (`87 passed`).

### Fixed - Stage P4: Stint P4.6.9 (`0.4.6.9`) `CONCLUDE` Minimize Fast-Path, Chrome `_teardown` Focus Guard, Tier-2 Exhaustion Fallback & CUA Copy/Folder Prompt Rules
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.8` to `0.4.6.9`.
- **`CONCLUDE` + `WAIT` Fast-Path & Tier-2 Exhaustion Fallback ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Exempted `StepIntent.CONCLUDE` + `WAIT` directives from `proc_mismatch` in `_try_directive_fast_path()` and emitted `ActionType.DONE` (gated downstream by `GoalVerifier.verify_goal_state()`), fixing false `proc_mismatch` aborts after minimize/close steps (`L1-07`).
  - Added `_episode_consult_exhausted`; when `TIER_2_CONSULT` exhausts Gemini consultations without a hardware interrupt, disabled further consultations for the episode and resumed `TIER_1_LOCAL` instead of spinning `WAIT (success=False)` in `USER_OVERRIDE` (`L2-07`).
- **`ParasiteSkill._teardown()` Post-Restore Focus Guard ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Verified `get_foreground_hwnd() != gemini_hwnd` after `focus_window(prior_hwnd)` and explicitly minimized `gemini_hwnd` if Chrome remained in the foreground (`L2-05`).
- **Zero-Numerical-Anchoring CUA Prompt Guidance ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Added `TEXT SELECTION & CLIPBOARD` (`ctrl c` after highlighting rather than repeating `drag`) and `NESTED FOLDERS` (enter `<parent>\<target>` before acting on files inside it) rules to `UITARS_SYSTEM_PROMPT`.
- **Tests ([`tests/unit/test_p4_6_9_fixes.py`](file:///C:/ParasiteAI/tests/unit/test_p4_6_9_fixes.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Added 4 targeted unit tests covering `CONCLUDE` + `WAIT`, Tier-2 exhaustion fallback, `_teardown()` Gemini foreground minimize, and `UITARS_SYSTEM_PROMPT` rules (`149 passed`).

### Fixed - Stage P4: Stint P4.6.8 (`0.4.6.8`) CUA `BURST` Diff Credit, Passive `WAIT` Stagnation Breaker, Multi-Line Deduplication & Window-Close Proactive Skip
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.7` to `0.4.6.8`.
- **Keyboard `BURST` Diff Floor & Passive `WAIT` Stagnation Breaker ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Included pure-keyboard `ActionType.BURST` commands (`TYPE`, `CLICK_AND_TYPE`, `HOTKEY`) in the CUA `screen_diff` threshold credit so small UI updates (such as Windows Calculator expressions in `L2-03` and `L3-02`) do not incur false strikes below `0.0200`.
  - Tracked `_consecutive_idle_waits`; after 3 consecutive zero-diff `ActionType.WAIT` actions (`screen_diff < 0.002`, excluding post-launch settles and Pre-DONE vetos), enforced `[IDLE WAIT LOOP DETECTED]` failure strikes so passive wait stalls (e.g., `L3-03`) escalate and break cleanly.
  - Updated `should_trigger_proactive_plan()` to skip unnecessary Gemini consultations for simple single-window management goals (`close`/`minimize`/`hide`/`dismiss`/`exit`/`quit` without multi-step cues, e.g. `L1-06`).
- **Degenerate Multi-Line Action Deduplication ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py)):**
  - Collapsed adjacent identical calls in unprompted multi-line `Action:` blocks and reduced clipped `> 4` non-`burst` repetition floods to a single call (`L1-05`).
- **Tests ([`tests/unit/mind/test_p4_6_8_stabilization.py`](file:///C:/ParasiteAI/tests/unit/mind/test_p4_6_8_stabilization.py)):**
  - Added 4 targeted unit tests covering multi-line duplicate collapse, keyboard `BURST` diff floor, 3x zero-diff `WAIT` stagnation strike, and `should_trigger_proactive_plan("Close Notepad")` (`89 passed`).

### Fixed - Stage P4: Stint P4.6.7 (`0.4.6.7`) Live Benchmark Evaluation, AppMemory Post-Episode Fix, CUA Drag/Multi-Action, Veto Loop-Breaker & URL/Scroll Hardening
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.6` to `0.4.6.7`.
- **Fixed Silent `AppMemory` `total_dur` `NameError` & Enriched Telemetry ([`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py), [`parasite_ai/mind/memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py), [`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py)):**
  - Defined `total_dur = max(0.0, time.time() - start_time)` before receipt construction so `AppMemory.record_episode()`, `record_outcome()`, `record_app_seen()`, and `_promote_farmed_plans()` execute reliably after every episode instead of skipping with `NameError: name 'total_dur' is not defined`.
  - Added `veto_count` and `fast_path_abort_reason` fields to `EpisodeReceipt`, `RuntimeOrchestrator._build_episode_receipt()`, and [`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py).
- **Pre-DONE Veto Loop-Breaker & Shell-Safe Launch `TYPE` Guard ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Tracked `_episode_veto_count` and `_consecutive_vetoed_dones`; after 2 consecutive vetoed `DONE` actions, enforced an oscillation failure strike and appended an inline-edit/dialog commit hint (`Enter`/Confirm) to break infinite `finished()` loops (e.g., `L2-04`).
  - Required shell launcher foreground (`explorer.exe`, `searchapp.exe`, `searchhost.exe`, `startmenuexperiencehost.exe`) before fast-pathing any `LAUNCH_OR_ACTIVATE` `TYPE` directive, preventing stray typing into non-shell apps like Calculator (`L3-02`), and recorded `_episode_fast_path_abort_reason` on fallback.
  - Added `ActionType.DRAG` execution dispatch via `MouseDriver.drag_and_drop()`.
- **CUA `drag` Verb, Multi-Line Action Splitting & General Prompt Rules ([`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py), [`parasite_ai/mind/memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py)):**
  - Added `ActionType.DRAG` (`end_coordinates`) and `drag(start_box, end_box)` parsing (`L2-07` wasted `WAIT` fix).
  - Updated `_split_top_level_calls()` to split top-level newline-separated action calls outside quotes/parens into `ActionType.BURST` (`L1-05` / `L3-02`).
  - Added zero-coordinate-anchor `UITARS_SYSTEM_PROMPT` rules for `Save As` full-path entry (`Alt+N` + `<full_path>\n`), Explorer inline renames (`\n`), and browser profile pickers.
- **Markdown-URL Sanitization & Step 10 Scroll Focus ([`parasite_ai/mind/parasite_protocol.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_protocol.py), [`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Sanitized `[label](https://...)` Markdown links inside harvested `ParasitePlan`/`ParasiteAction` JSON payloads (`L3-03`).
  - Updated `ParasiteSkill._press_pagedown()` to dispatch `MouseDriver.scroll(-5, x, y)` inside the safe upper-center of `win_rect` before/with `pagedown` during Step 10 hover-guard recovery.
- **Tests ([`tests/unit/mind/test_p4_6_7_stabilization.py`](file:///C:/ParasiteAI/tests/unit/mind/test_p4_6_7_stabilization.py)):**
  - Added 6 targeted unit tests covering `drag`/multi-line parsing, Markdown URL sanitization, pane wheel scroll, non-shell launch `TYPE` blocking, `DRAG` dispatch + Pre-DONE veto strikes, and `RuntimeOrchestrator` `total_dur`/receipt telemetry (`152 passed`).

### Fixed - Stage P4: Stint P4.6.6 (`0.4.6.6`) Subprocess Pipe Deadlock, Incremental Receipt Telemetry, Redundant Alt+Tab Skip & Copy Harvest Hardening
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified project version from `0.4.6.5` to `0.4.6.6`.
- **Eliminated Subprocess 4 KB Pipe Deadlock & Added Log Streaming ([`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py)):**
  - Replaced `subprocess.PIPE` in `run_single_task()` with direct streaming to `benchmarks/results/logs/<task_id>.log` (`stdout=log_fh, stderr=subprocess.STDOUT`), eliminating Windows 4 KB buffer deadlocks under `INFO` logging.
  - Added `Plan Source` (`skill`, `farmed`, `proactive_gemini`, `local` with `skill_id` or `farmed_plan_id`) to `format_markdown_report()` and preserved partial checkpoint counts/latencies/provenance when mapping `"IN_PROGRESS"` receipts to `"TIMEOUT"` or `"PANIC"`.
  - Updated [`ParasiteApp.shutdown`](file:///C:/ParasiteAI/parasite_ai/main.py) to flush all root logger handlers on exit.
- **Incremental `IN_PROGRESS` Receipt Checkpointing & Provenance Telemetry ([`parasite_ai/mind/memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Extended `EpisodeReceipt` with `plan_source`, `skill_id`, `farmed_plan_id`, `fast_path_steps`, `parasite_invocations`, and `parasite_status`, and made `EpisodeReceipt.save()` atomic via `.tmp` write + `.replace()`.
  - Added `RuntimeOrchestrator._build_episode_receipt()` and `_save_checkpoint_receipt()` to persist `"IN_PROGRESS"` receipts at episode start and after every completed step without setting `last_episode_receipt` prematurely before completion.
- **Directive Fast-Path Focus, Multi-App & Caret Exemption Hardening ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`data/skills/minimize-notepad/SKILL.md`](file:///C:/ParasiteAI/data/skills/minimize-notepad/SKILL.md)):**
  - Removed the extraneous `LAUNCH_OR_ACTIVATE` `alt+tab` step from `minimize-notepad/SKILL.md`, and guarded `_try_directive_fast_path()` to skip redundant `alt+tab` steps when the normalized target process is already focused.
  - Added `DualMindPipeline._normalize_expected_process()`, episode plan/Gemini provenance tracking across Layer 1/1.5/4/local & Tier-2 consultation, dynamic launched-app tracking across multi-app steps in `step()`, and Calculator / post-wait active-window caret exemptions in `_try_directive_fast_path()`.
- **`ParasiteSkill` Centroid Snap Guard & Step 10 `Page_Down` Copy Recovery ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Updated `HybridLocalAssistBackend._ask_vlm_locate()` to run `CentroidSnapper` on the masked `vlm_crop` and reject snaps drifting `> 32px` (preserving `28px` `edge_margin_px` Send snaps) or landing within `exclude_points`.
  - Added `ParasiteSkill._press_pagedown()` targeting `KeyboardDriver.hotkey("pagedown")` (replacing dead `.press_hotkey(["pagedown"])` calls on real drivers) and wired `pagedown` + `locate_copy_button` retries into Step 10 (`HARVESTING`) when Copy vanishes prior to click or hover-guard sees `</parasite_plan>`.

### Fixed - Stage P4: Stint P4.6.5 (`0.4.6.5`) Skill System & Deterministic Launch Redesign
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Bumped unified project version from `0.4.6.4` to `0.4.6.5`.
- **Promotion Black Hole & Keyword-Only Skill Scoring Fix ([`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py), [`parasite_ai/mind/app_memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/app_memory.py), [`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Updated `RuntimeOrchestrator._promote_farmed_plans()` to extract clean punctuation-free keywords (`re.findall(r"[a-z0-9]+", ...)`), resolve `container_process` / `requires_launch` accurately, and promote coordinate-free (`HOTKEY`/`TYPE`/`WAIT`) multi-success plans with `draft=False, state=SkillState.CANDIDATE` so they immediately enter candidate probation (pointer/click plans retain `draft=True`).
  - Removed `AND promoted_skill_id IS NULL` from `AppMemory.lookup_farmed_plan()` so Layer 1.5 remains an active fallback even after promotion while keeping deduplication in `promotion_candidates()`.
  - Updated `SkillRegistry._score_skill()` so keyword-only skills (`goal_patterns=[]`) score via `0.85 * kw_overlap + 0.15 * proc_hit` (or `kw_overlap` without `process_names`) instead of being capped at `0.40 < 0.60`, and stripped balanced outer quotes on extracted regex parameters.
- **`submit` / `clear_first` Forwarding Across Skill Schema & Directives ([`parasite_ai/mind/plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py), [`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Added `clear_first: bool = False` on `StepDirective` and `submit: bool = False` / `clear_first: bool = False` on `SkillActionStep`; forwarded both fields across `_promote_farmed_plans()`, `compile_to_living_plan()`, `verify_and_resolve_reflex_skill()`, and `_try_directive_fast_path()`.
- **Skill Playbook Repairs & Un-Quarantine ([`data/skills/`](file:///C:/ParasiteAI/data/skills)):**
  - Restored `notepad-write-text` from `_quarantine/` using `launch_method: win_r`, `launch_query: notepad`, `max_consecutive_failures: 3`, and quote-tolerant compound/in-app `goal_patterns`.
  - Enabled prefix-tolerant matching on `calculator-evaluate` (`Open Calculator and compute 7 * 8`), switched `paint-new-and-save` to `win_r` (`mspaint`), and repaired promoted `minimize-notepad` & `open-notepad-type-draft-select-all-text-and-copy` (`draft: false`, clean keywords, `submit: true` on `Win+R` `notepad`).
- **Deterministic `Win+R` Launch Directives & Readiness Wait Gate ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Attached deterministic `Win+R` launch `StepDirective`s on fallback `LivingPlan` skeletons when skills are enabled and a known system app (`notepad`, `calc`, `mspaint`, `cmd`, `powershell`, `explorer`) is not already active (omitting spurious execute steps on pure launch goals).
  - Added bounded post-launch `ActionType.WAIT` (`1000ms`, up to 2 retries per step when prior fast-path launch steps ran) in `_try_directive_fast_path()` before failing closed to VLM.

### Fixed - Stage P4: Stint P4.6.4 (`0.4.6.4`) `ParasiteSkill` `HARVEST_TIMEOUT` / `PAYLOAD_INVALID` Fixes & Ideal Min/Max Step Calibration
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.3.1` to `0.4.6.4`.
- **`ParasiteSkill` Bottom-Reveal & Fail-Closed Copy Verification ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Made `HybridLocalAssistBackend.verify_hover_tooltip()` fail closed (`require_positive=True`) unless RapidOCR positively detects `"copy"` in the hovered tooltip, preventing VLM hallucinations from exiting `AWAITING_GENERATION` or clicking non-Copy spots.
  - Added a `pagedown` keyboard fallback when wheel scrolling stalls (`no_change_streak >= 2`) so long `<parasite_plan>` responses reliably reveal the bottom action bar.
- **Windows Path & `StepIntent` Alias Tolerance ([`parasite_ai/mind/parasite_protocol.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_protocol.py)):**
  - Added `_loads_json_with_winpath_fallback()` in `parse_response()` to escape raw Windows path backslashes (fixing `Invalid \escape` `PAYLOAD_INVALID` failures).
  - Added `_normalize_intent_alias()` on `ParasitePlanStep` mapping verb aliases (`"TYPE"`, `"CLICK"`, `"OPEN"`, etc.) to canonical `StepIntent` values.
- **Simulated Ideal Min & Inefficient Max Step Calibration ([`benchmarks/suite.yaml`](file:///C:/ParasiteAI/benchmarks/suite.yaml), [`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py)):**
  - Added simulated `min_steps_with_skill`, `min_steps_no_skill`, and calibrated `max_steps` / `timeout_sec` across all 20 suite tasks, plus `mean_step_efficiency_ratio` and `Steps (Act/MinS/MinL/Max)` reporting.

### Fixed - Stage P4: Stint P4.6.3.1 Sub-Subversion Bump (`0.4.6.3.1`), Corner-Slam Removal, Suite-Wide `Ctrl+Alt+K` Kill & Reliable Hardware Pause
- **Sub-Subversion Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.3` to `0.4.6.3.1`.
- **Corner-Slam Panic Removal ([`parasite_ai/safety/panic.py`](file:///C:/ParasiteAI/parasite_ai/safety/panic.py), [`parasite_ai/safety/interrupt_guard.py`](file:///C:/ParasiteAI/parasite_ai/safety/interrupt_guard.py), [`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py), [`config.yaml`](file:///C:/ParasiteAI/config.yaml)):**
  - Removed `PanicTriggerSource.CORNER_SLAM`, `PanicManager.check_mouse_position()`, corner-slam debounce state, `corner_panic_enabled`, and `corner_distance_px` so physical mouse movement into screen corners only triggers standard co-pilot preemption (`USER_OVERRIDE`), never emergency panic.
- **Suite-Wide `Ctrl+Alt+K` Kill & `HARDWARE_PREEMPTED` Pause ([`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py)):**
  - Added `SuitePanicMonitor` (`Ctrl+Alt+K`/`Ctrl+Alt+Q` global hotkey listener) + `subprocess.Popen` abort polling in `run_single_task()`, and suite-level halt on `exit_reason == "PANIC"` / `exit_code == 2` so `Ctrl+Alt+K` terminates the entire benchmark suite instead of advancing to the next task.
  - Added interactive operator pause prompt in `run_benchmark.py` when a task ends with `HARDWARE_PREEMPTED`.
- **Mid-Step Hardware Interrupt Latching ([`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Added `_step_interrupted_latched` in `RuntimeOrchestrator` so physical mouse/keyboard touch occurring during a long VLM/action step still enforces the `USER_OVERRIDE` pause/cooldown at the next step boundary even if the 2.5s guard timer elapsed before `pipeline.step()` returned.

### Fixed - Stage P4: Stint P4.6.3 Subversion Bump (`0.4.6.3`), Cold-to-Cold Process/Input Cleanup & `ParasiteSkill` `FOCUS_TIMEOUT` Recovery
- **Subversion Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.6.2` to `0.4.6.3`.
- **Cold-to-Cold Process, Hook & Modifier Cleanup ([`benchmarks/verifiers.py`](file:///C:/ParasiteAI/benchmarks/verifiers.py), [`benchmarks/run_benchmark.py`](file:///C:/ParasiteAI/benchmarks/run_benchmark.py)):**
  - Added `kill_lingering_parasite_processes()` (terminates orphaned `parasite_ai.main` processes holding `WH_KEYBOARD_LL`/`WH_MOUSE_LL` hooks without touching Chrome) and `release_stuck_input_state()` (`SendInput`/Win32 key-up/button-up for all modifier keys and mouse buttons) to `cleanup_benchmark_processes()`.
  - Wrapped `run_single_task()` and `run_benchmark()` in `try ... finally` cold-to-cold cleanup so timeouts or `Ctrl+C` cannot leave lingering hooks or stuck keyboard modifiers.
- **`ParasiteSkill` `FOCUS_TIMEOUT` Recovery ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py), [`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py)):**
  - Raised default `focus_timeout_sec` from `4.0` to `5.5` and added a bounded 1-time recovery in `_focus_gemini_window()` that focuses an existing `chrome.exe` window (`_find_chrome_host_hwnd()`) and retries `Alt+G` when the initial `Alt+G` produces no foreground transition.

### Fixed - Stage P4: Stint P4.6.2 Version Bump (`0.4.6.2`), `ABAB` Oscillation Escalation & Pre-`DONE` Verification Hardening
- **Version Bump ([`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py)):**
  - Bumped unified project version from `0.4.5.4` to `0.4.6.2`.
- **2-Step `ABAB` Oscillation Loop Detection ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Expanded `DualMindPipeline.step()` oscillation lookback (`n=4`) and added `_actions_match_for_oscillation()` to detect `A -> B -> A -> B` coordinate ping-pong (`DOUBLE_CLICK` ↔ `CLICK`) and `TYPE` ↔ `HOTKEY` loops even when `screen_diff` is large (`~0.96`), triggering `RecoveryTrigger.OSCILLATION` → `ParasiteSkill` by step 4.
- **`PreDoneVerifier` `FALSE_DONE` Hardening ([`parasite_ai/mind/verifier.py`](file:///C:/ParasiteAI/parasite_ai/mind/verifier.py)):**
  - Excluded `notepad++.exe` / `"notepad++"` titles from Notepad launch verification, required `mspaint.exe` (`not is_minimized`) for Paint launch verification, and added `read_calculator_display()` UIA `CalculatorResults` verification when an arithmetic expression is present in the goal.

### Changed - Stage P4: Stint P4.6.1 Step Budget Expansion, Gemini-Safe Timeouts & Monitor 1 Workspace Isolation
- **Benchmark Step Budgets & Timeouts ([`run_benchmark_p4.bat`](file:///C:/ParasiteAI/run_benchmark_p4.bat), [`benchmarks/suite.yaml`](file:///C:/ParasiteAI/benchmarks/suite.yaml)):**
  - Removed `--max-steps-cap 8` from `run_benchmark_p4.bat` so benchmark tasks use full suite budgets.
  - Expanded `benchmarks/suite.yaml` budgets to accommodate `ParasiteSkill` Gemini round-trips plus local execution/recovery: `L1` (`16–20` steps, `150–180s`), `L2` (`24` steps, `220s`), and `L3` (`30` steps, `260s`).
- **Default Interactive `max_steps` ([`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py)):**
  - Raised default `--max-steps` and `RuntimeOrchestrator.default_max_steps` / `_execute_goal_episode` / `run_goal_sync` from `15` to `30`.
- **Reliable Monitor 1 Stray-Window Minimization ([`benchmarks/verifiers.py`](file:///C:/ParasiteAI/benchmarks/verifiers.py)):**
  - Updated `minimize_non_target_monitor1_windows()` to use `ShowWindowAsync(hwnd, SW_MINIMIZE)` with an `SW_FORCEMINIMIZE` (`11`) fallback when `IsIconic(hwnd)` remains false so stray editors (e.g., `Notepad++`) on Monitor 1 cannot intercept `UI-TARS` typing.

### Added - Stage P4: Stint P4.6 Preparation & P4.5 Milestone Gate
- **Stage P4 Certification Runner ([`run_benchmark_p4.bat`](file:///C:/ParasiteAI/run_benchmark_p4.bat), [`config.yaml`](file:///C:/ParasiteAI/config.yaml)):**
  - Enabled persistent `app_memory` (`data/app_memory.db`) in `config.yaml` and created `run_benchmark_p4.bat` (`baseline_p4` vs `baseline_p3`, `baseline_p2_7`, `baseline_p0`).
- **Integration Null-Safety & Workflow Drift Test Alignment ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Guarded `pre_win_label` against `None` in `DualMindPipeline.step()` post-launch check and updated `test_workflow_deferred_drift_triggers_when_container_launches` to `SkillType.REFLEX_MICRO_SKILL` per `P4.5.7`.
- **Milestone Verification (`pytest` + `--dry-verify`):**
  - Full suite verified: **624 passed, 1 warning in 65.24s**; benchmark `--dry-verify` **20/20 `[OK]`**.

### Fixed - Stage P4: Stint P4.5.11 Paint `F12` Save-As Shortcut & Playbook Restoration
- **Paint Save-As Shortcut ([`data/skills/paint-new-and-save/SKILL.md`](file:///C:/ParasiteAI/data/skills/paint-new-and-save/SKILL.md)):**
  - Restored `paint-new-and-save` from `data/skills/_quarantine/` (`state: ACTIVE`, reset failure counters) and updated Step 1 from `ctrl+shift+s` to `f12` (native Windows Paint Save As shortcut).
- **Verification ([`test_local_playbooks.py`](file:///C:/ParasiteAI/tests/unit/mind/test_local_playbooks.py)):**
  - Verified **2 passed in 0.59s**.

### Fixed - Stage P4: Stint P4.5.10 `locate_copy_button` Bottom Composer-Strip Margin
- **Gemini Copy Rescue Margin ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Relaxed `HybridLocalAssistBackend.locate_copy_button()` `max_local_y` threshold from `rect_h - 72` (`583` in a `655px` overlay) to `rect_h - 48` (`607`) so valid Copy response icons sitting immediately above the bottom composer (`ly = 585`) are not rejected while the composer input/Send strip (`ly >= 607`) remains excluded.
- **Verification ([`test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py)):**
  - Verified **30 passed in 11.98s**.

### Fixed - Stage P4: Stint P4.5.9 Plan Completion Lock, Directive-Verb Verification & Playbook Restoration
- **Completed `LivingPlan` Re-Entry Prevention ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Updated `DualMindPipeline._initialize_or_update_plan()` to retain a completed `LivingPlan` for the same `user_goal` instead of clearing `_fast_pathed_step_ids` and restarting the matched skill or farmed plan from Step 1, preventing infinite `escape` / `ctrl+s` loops (`P-J`, `P-K`).
- **Directive-Verb & Shell-Launch Verification ([`parasite_ai/mind/plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py)):**
  - Updated `verify_step_completion()` to require `action.action` to match `directive.verb` (`WAIT`, `HOTKEY`, `TYPE`) for non-launch directive steps so fallback `UI-TARS` recovery clicks do not skip unexecuted `TYPE` steps (`P-K` Step 4).
  - Allowed `StepIntent.LAUNCH_OR_ACTIVATE` `HOTKEY` directives (`win+r` / `win`) to complete when `screen_diff >= 0.02`, unblocking Run/Start shell launch advancement (`P-I` Step 1).
- **Playbook Restoration & Save-As Shortcut ([`data/skills/calculator-evaluate/SKILL.md`](file:///C:/ParasiteAI/data/skills/calculator-evaluate/SKILL.md), [`data/skills/paint-new-and-save/SKILL.md`](file:///C:/ParasiteAI/data/skills/paint-new-and-save/SKILL.md)):**
  - Restored `calculator-evaluate` and `paint-new-and-save` from `data/skills/_quarantine/` (`state: ACTIVE`, reset failure counters) and updated `paint-new-and-save` Step 1 from `ctrl+s` to `ctrl+shift+s` (`Save As`).
- **Verification ([`test_dual_mind_directive.py`](file:///C:/ParasiteAI/tests/unit/mind/test_dual_mind_directive.py), [`test_local_playbooks.py`](file:///C:/ParasiteAI/tests/unit/mind/test_local_playbooks.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py)):**
  - Verified **19 passed in 1.44s**.

### Fixed - Stage P4: Stint P4.5.8 UWP Host Matching, Post-Launch Settle & Launch-Input Fast Path
- **UWP `ApplicationFrameHost.exe` Equivalence ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py), [`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `SkillRegistry.process_matches_window()` and wired it into `compile_to_living_plan()` and `_try_directive_fast_path()` so UWP apps hosted by `ApplicationFrameHost.exe` (e.g., `CalculatorApp.exe`) match without triggering redundant relaunch cycles.
- **Post-Launch Foreground Settle & Run-Dialog Fast Path ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added a `1.5s` cancellation-aware post-launch foreground poll after `launch:submit_search` / Run-dialog `TYPE` submissions so newly launched apps become foreground before subsequent directives execute.
  - Allowed early `step_id <= 2` `TYPE` (`submit=True`) directives inside `Run`/`Start menu` (`explorer.exe`/`SearchApp.exe`) to execute on the directive fast path regardless of `intent`.
- **Verification ([`test_skill_schema.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_schema.py), [`test_local_playbooks.py`](file:///C:/ParasiteAI/tests/unit/mind/test_local_playbooks.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py)):**
  - Verified **33 passed in 0.92s**.

### Fixed - Stage P4: Stint P4.5.7 Workflow Drift Policy & Smoke Promotion Isolation
- **Workflow `pHash` Drift Exemption ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Restricted automatic `check_visual_drift()` quarantine in `DualMindPipeline.step()` to `SkillType.REFLEX_MICRO_SKILL` so coordinate-free `SkillType.WORKFLOW` skills are not falsely quarantined when window dimensions or canvas pixels vary.
  - Restored [`data/skills/paint-new-and-save/SKILL.md`](file:///C:/ParasiteAI/data/skills/paint-new-and-save/SKILL.md) from quarantine (`state: ACTIVE`, cleared stale `visual_anchors`).
- **Smoke Suite DB Isolation ([`scripts/smoke_test_p4_5_execution.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_5_execution.py)):**
  - Isolated `P-J` / `P-K` playbook runs to `playbooks_memory.db` so they do not auto-promote `P-H`/`P-I`'s farmed Notepad plan into live `data/skills/` prior to `P-L`'s `sandbox_skills` promotion check.
- **Verification ([`test_phash_drift.py`](file:///C:/ParasiteAI/tests/unit/mind/test_phash_drift.py), [`test_local_playbooks.py`](file:///C:/ParasiteAI/tests/unit/mind/test_local_playbooks.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py)):**
  - Verified **17 passed in 1.06s**.

### Fixed - Stage P4: Stint P4.5.6 Universal Shell Flyout Guard & Skill Launch Schema
- **Universal Shell/Search Focus Preservation ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added Win32 `ActionDispatcher._get_process_name_for_hwnd()` (`OpenProcess` + `QueryFullProcessImageNameW`) and extended `[SHELL FLYOUT GUARD]` in `_activate_target_window_if_needed()` to skip background window activation when Windows shell/search hosts (`startmenuexperiencehost.exe`, `searchapp.exe`, `searchhost.exe`, `shellexperiencehost.exe`) are in the foreground, preventing Start Menu clicks from focusing underlying background windows.
- **Schema-Level `launch_query` & `launch_method` ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py), [`data/skills/calculator-evaluate/SKILL.md`](file:///C:/ParasiteAI/data/skills/calculator-evaluate/SKILL.md)):**
  - Added optional `launch_query: Optional[str]` and `launch_method: Literal["start_search", "win_r"]` fields to `SkillPreconditions`.
  - Updated `SkillRegistry.compile_to_living_plan()` to honor `launch_query` and `launch_method` when emitting Step 1/2 launch directives, and configured `calculator-evaluate` with `launch_query: calc` + `launch_method: win_r`.
- **Verification ([`test_window_focus_and_navigation.py`](file:///C:/ParasiteAI/tests/unit/mind/test_window_focus_and_navigation.py), [`test_skill_schema.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_schema.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py)):**
  - Verified **46 passed in 1.17s**.

### Added - Stage P4: Stint P4.5.4 Local Playbooks, Live Execution Smoke & Milestone Verification (v0.4.5.4)
- **Version Bump (`0.4.5.4`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Local Keyboard-First Playbooks (`data/skills/`):**
  - Added [`data/skills/notepad-write-text/SKILL.md`](file:///C:/ParasiteAI/data/skills/notepad-write-text/SKILL.md), [`data/skills/calculator-evaluate/SKILL.md`](file:///C:/ParasiteAI/data/skills/calculator-evaluate/SKILL.md), and [`data/skills/paint-new-and-save/SKILL.md`](file:///C:/ParasiteAI/data/skills/paint-new-and-save/SKILL.md) (all `type: workflow`, `requires_launch: true`, zero coordinates).
- **Live Execution Smoke Suite ([`scripts/smoke_test_p4_5_execution.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_5_execution.py), [`run_smoke_probe_p4_5.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_5.bat)):**
  - Added probes `P-H` .. `P-L` verifying end-to-end farmed `ParasitePlan` execution (persisting full plan JSON), Layer 1.5 cache hit (`0` Gemini calls), `calculator-evaluate`, `paint-new-and-save`, and SQLite WAL / zero-Gemini draft promotion.
- **Milestone Verification ([`test_local_playbooks.py`](file:///C:/ParasiteAI/tests/unit/mind/test_local_playbooks.py)):**
  - Full pytest suite verified: **616 passed, 1 warning in 66.56s**.

### Added - Stage P4: Stint P4.5.3 App Memory Integration (SQLite WAL, Farmed-Plan Cache & Draft Promotion) (v0.4.5.3)
- **Version Bump (`0.4.5.3`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Persistent SQLite WAL `AppMemory` ([`parasite_ai/mind/app_memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/app_memory.py), [`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py)):**
  - Added `AppMemoryConfig` (`enabled: bool = False`, `db_path`, `max_consecutive_failures`, `promote_after_successes`) and thread-safe SQLite WAL `AppMemory` (`farmed_plans`, `app_profiles`, `episodes` tables).
  - Implemented exact normalized-goal Layer 1.5 lookup (`success_count >= 1`, version-prefix gated, failure-streak evicted) and zero-Gemini `promotion_candidates()` selection.
- **Layer 1.5 Cache & Zero-Gemini Draft Promotion ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py), [`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Wired Layer 1.5 lookup and Layer 4 plan storage into `DualMindPipeline._initialize_or_update_plan()`.
  - Wired episode outcome/profile persistence and `_promote_farmed_plans()` (`SkillProvenance.FARMED`, `draft=True`) into `RuntimeOrchestrator`.
- **Trace Hygiene ([`tests/integration/test_episode_receipt.py`](file:///C:/ParasiteAI/tests/integration/test_episode_receipt.py)):**
  - Isolated subprocess telemetry test to `tmp_path / "skills"` via `--config` and archived 8 polluted traces to `data/skills/_traces/_archive_test_pollution/`.
- **Verification ([`test_app_memory.py`](file:///C:/ParasiteAI/tests/unit/mind/test_app_memory.py), [`test_skill_learning.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_learning.py), [`test_episode_receipt.py`](file:///C:/ParasiteAI/tests/integration/test_episode_receipt.py), [`test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Verified **30 passed** (`test_app_memory.py`, `test_skill_learning.py`, `test_parasite_skill_pipeline.py`) and **9 passed** (`test_episode_receipt.py`); `0` polluted traces in `data/skills/_traces/`.

### Added - Stage P4: Stint P4.5.2 Directive Fast Path & Launch Primitive (v0.4.5.2)
- **Version Bump (`0.4.5.2`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Gated Directive Fast Path ([`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py)):**
  - Added `DualMindPipeline._try_directive_fast_path()` for keyboard/wait `StepDirective`s (`HOTKEY`, `WAIT`, `TYPE`), enforcing safety-window, process-match, caret-focus (`TYPE`), interrupt, and one-shot-per-step gates while bypassing `generate_cua_step()` and preserving P4.3 risk consent (`classify_action_risk`).
  - Added `Required action: <verb>` hint into CUA working-memory guidance when pointer directives (`CLICK*`, `SCROLL`) fall through to UI-TARS.
- **Directive-Aware Completion & General Launch Primitive ([`parasite_ai/mind/plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py), [`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Updated `verify_step_completion()` to evaluate `WAIT`, `HOTKEY`, and `TYPE` directives directly.
  - Updated `SkillRegistry.compile_to_living_plan(..., active_process=...)` to prepend a general Windows Start-Menu launch pair (`HOTKEY ["win"]` + `TYPE <app_stem> submit=True`) when `requires_launch=True` and `container_process` is not in the foreground.
- **Verification ([`test_dual_mind_directive.py`](file:///C:/ParasiteAI/tests/unit/mind/test_dual_mind_directive.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py), [`test_parasite_protocol.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_protocol.py)):**
  - Verified targeted sub-stint suite: **34 passed in 1.36s**.

### Added - Stage P4: Stint P4.5.1 Typed Step Directives (Schema, Protocol & Skill Compilation) (v0.4.5.1)
- **Version Bump (`0.4.5.1`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Typed `StepDirective` & Shared Coordinate Guards ([`parasite_ai/mind/plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py)):**
  - Moved `strip_control_chars`, `find_coordinate_patterns`, and `assert_no_numeric_coordinates` into `plan.py` (re-exported by `parasite_protocol.py` for zero breaking imports and zero circularity).
  - Added coordinate-free `StepDirective` (`verb`, `text`, `keys`, `submit`, `scroll_direction`, `wait_ms`) with `extra="forbid"` and verb-shape validation, plus optional `PlanStep.directive: Optional[StepDirective] = None`.
- **Protocol & Proactive Prompt Update ([`parasite_ai/mind/parasite_protocol.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_protocol.py)):**
  - Added `action: Optional[StepDirective] = None` to `ParasitePlanStep`, preserved `directive` in `ParasitePlan.to_living_plan()`, and attached `StepDirective` in `ParasiteAction.to_contingency_step()`.
  - Added symbolic `"action"` schema hint in `PROACTIVE_PLAN` / `REACTIVE_RECOVERY` prompts and removed `CLI` from the proactive `tool_route` instruction (`Valid tool_route values: GUI.`).
- **Skill Compilation ([`parasite_ai/mind/skills.py`](file:///C:/ParasiteAI/parasite_ai/mind/skills.py)):**
  - Updated `SkillRegistry.compile_to_living_plan()` to attach `StepDirective` with substituted `{{param}}` payloads (never copying `relative_coordinates`).
- **Verification ([`test_parasite_protocol.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_protocol.py), [`test_skill_registry.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_registry.py), [`test_skill_schema.py`](file:///C:/ParasiteAI/tests/unit/mind/test_skill_schema.py)):**
  - Verified targeted sub-stint suite: **48 passed in 0.80s**.

### Fixed - Stage P4: Stint P4.4.8 Drop `3x` Zoom Overwrite, Re-Enable Step 9 Scroll on `wait()`, & RapidOCR Hover-Tooltip Guard (v0.4.4.8)
- **Version Bump (`0.4.4.8`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Removed `3x` Zoom Overwrite ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Removed `_zoom_refine_copy_point()` and its call in `HybridLocalAssistBackend.locate_copy_button()` so coarse full-window VLM predictions (`CentroidSnapper`-refined) are returned directly without zoomed misidentification.
- **Step 9 Re-Scroll on `wait()` & RapidOCR Hover-Tooltip Guard ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Reset `scrolled_since_activity = False` when `locate_copy_button()` returns `None` (`Action: wait()`), allowing Step 9 to scroll down again if trailing streamed output pushed the action row below the fold.
  - Replaced full-window VLM tooltip reading in `HybridLocalAssistBackend.verify_hover_tooltip()` with deterministic local **RapidOCR** (`ScreenGrounder._get_ocr_engine()`) on a `2x` upscaled crop around `cursor_pt` (`±140 px` horizontal, `±60 px` vertical), and increased Step 10's pre-click hover wait to `0.60s`.
- **Verification ([`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py)):**
  - Added `test_step9_resumes_scroll_after_wait_and_rapidocr_hover_tooltip_guard` and cleaned up `test_send_centroid_snap_and_step10_closed_loop_copy_requery_with_exclude_masking`.
  - Verified targeted sub-stint suite: **52 passed, 1 warning in 20.42s** (`test_parasite_skill.py` `30 passed`, `test_parasite_skill_pipeline.py` `22 passed`) and CLI `--version` (`parasite 0.4.4.8`).

### Fixed - Stage P4: Stint P4.4.7 Scroll-Until-Bottom Settle, 3x Coarse-to-Fine Optical Zoom & Pre-Click Hover-Tooltip Guard (v0.4.4.7)
- **Version Bump (`0.4.4.7`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Scroll-Until-Bottom & Post-Scroll Animation/Network Settle ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Upgraded Step 9 (`AWAITING_GENERATION`) scroll passes to scroll continuously (`max(12, scroll_before_copy_attempts * 4)` ticks per pass) until UIA finds Copy or **two consecutive scroll ticks** produce negligible visual change (`sc_hd < 3 and sc_diff < 0.8`), followed by a `0.50s` post-scroll animation/streaming settle check before calling `locate_copy_button()`.
- **3x Optical Zoom & Pre-Click Hover-Tooltip Safety Guard ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Added `HybridLocalAssistBackend._zoom_refine_copy_point()` to upscale (`3x`) a local strip around coarse Copy candidates so tiny action-row icons (`↻` Regenerate vs `❐` Copy) are disambiguated with `CentroidSnapper` and zero-digit prompts (`Cadence §8.3`).
  - Added `HybridLocalAssistBackend.verify_hover_tooltip()` and a Step 10 pre-click `move_to` + `0.35s` hover-tooltip guard that aborts clicks on `"Close"`, `"More options"`, `"Redo"`, `"Regenerate"`, `"Good response"`, or `"Bad response"` tooltips, adds the coordinate to `failed_copy_points`, and re-queries cleanly.
- **Verification ([`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py)):**
  - Added `test_step9_scroll_to_bottom_3x_zoom_and_hover_tooltip_guard` and updated `test_send_centroid_snap_and_step10_closed_loop_copy_requery_with_exclude_masking`.
  - Verified targeted sub-stint suite: **52 passed, 1 warning in 20.16s** (`test_parasite_skill.py` `30 passed`, `test_parasite_skill_pipeline.py` `22 passed`) and CLI `--version` (`parasite 0.4.4.7`).

### Added - Stage P4: Stint P4.4.6 Forensic Screenshot Governance, Historical Capture Archival & Targeted Sub-Stint Test Gate (v0.4.4.6)
- **Version Bump (`0.4.4.6`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py), and [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py).
- **Governance Rules ([`.agents/rules/engineering_cadence.md`](file:///C:/ParasiteAI/.agents/rules/engineering_cadence.md), [`AGENTS.md`](file:///C:/ParasiteAI/AGENTS.md)):**
  - Added **Targeted vs. Milestone Test Gate (`§3`)**: sub-stints verify only targeted test files covering touched modules (`-q --tb=short`), reserving the full `500+` test suite for stage boundaries or cross-cutting core edits.
  - Added **Forensic-Only Screenshot Policy (`§7.7`)**: saved `.png` captures are strictly post-mortem debugging evidence and regression test fixtures, never UI specifications; agents must check sidecar `app_version` / `timestamp` and never derive pixel bands, fixed offsets, or icon-order assumptions from screenshots.
- **Forensic Metadata Tagging & Non-Destructive Capture Archival ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py), [`scripts/smoke_test_p4_4_parasite_skill.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_4_parasite_skill.py)):**
  - Embedded `app_version`, `artifact_role: "historical_forensic_debug_only"`, and `coding_spec_prohibited: true` in every diagnostic `.json` sidecar written by `ParasiteSkill._write_diagnostics()`.
  - Archived superseded captures into `data/logs/parasite_skill/_archive_old_runs/pre_p4_4_6/`, added explicit forensic-only `README.md` notices in [`data/logs/parasite_skill/README.md`](file:///C:/ParasiteAI/data/logs/parasite_skill/README.md) and [`data/logs/parasite_skill/_archive_old_runs/README.md`](file:///C:/ParasiteAI/data/logs/parasite_skill/_archive_old_runs/README.md), and updated `smoke_test_p4_4_parasite_skill.py` to auto-archive prior captures at the start of each new live probe run.
- **Verification ([`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py)):**
  - Added `test_write_diagnostics_embeds_forensic_only_metadata`.
  - Verified targeted sub-stint suite: **51 passed, 1 warning in 19.89s** (`test_parasite_skill.py` `29 passed`, `test_parasite_skill_pipeline.py` `22 passed`) and CLI `--version` (`parasite 0.4.4.6`).

### Fixed - Stage P4: Stint P4.4.5 Self-Echo-Free Prompting, Closed-Loop Visual Inhibition of Return (`exclude_points`), `CentroidSnapper` Integration & 64-Bit UIA Awakening (v0.4.4.5)
- **Version Bump (`0.4.4.5`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), and [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py).
- **64-Bit UIA Awakening & Self-Echo-Free VLM Grounding ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Updated `GeminiWindowBackend.awaken_accessibility()` to pass explicit `ctypes.wintypes.WPARAM(0)` / `LPARAM(-4)` (`OBJID_CLIENT`) to `SendMessageTimeoutW` and invoke `oleacc.AccessibleObjectFromWindow` cleanly.
  - Added general closed-loop visual inhibition of return (`exclude_points` painting `12 px` blackout circles onto `vlm_crop` before `_pad_crop_for_vlm()`) and optional Stage P4.1 `CentroidSnapper(max_button_size=64, edge_margin_px=28)` snapping (`snap_button_contour=True`) in `HybridLocalAssistBackend._ask_vlm_locate()`, enabled for both `locate_send_button()` and `locate_copy_button()`.
  - Removed the self-contradicting `"+ Type @ to add tabs"` echo from `locate_copy_button()`'s zero-digit `target_description` (`Cadence §8.3`), added `"more options"` to `reject_thought_substrings`, and tightened `_is_excluded()` default `min_dist_px` from `40.0` to `16.0` for tightly spaced action-row icons.
- **Closed-Loop Step 8 Submit Verification & Step 10 Harvest Re-Query ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Upgraded Step 8 (`SUBMITTING`) to support up to 2 Send-button attempts with `tried_send_points` (`exclude_points`) and a pre-click baseline post-click transition poll (`min(1.0, submit_verify_timeout_sec)`).
  - Upgraded Step 10 (`HARVESTING`) to perform a closed-loop `locate_copy_button(..., exclude_points=failed_copy_points)` re-query when clicking an initial icon yields no valid clipboard harvest.
- **Verification ([`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Added `test_send_centroid_snap_and_step10_closed_loop_copy_requery_with_exclude_masking` and updated `test_step8_send_button_click_fallback_and_send_copy_spatial_exclusion` and version assertion (`0.4.4.5`).
  - Verified full regression suite after final edit: **597 passed, 1 warning in 70.62s (0:01:10)** (`test_parasite_skill.py` `28 passed`, `test_parasite_skill_pipeline.py` `22 passed`) and CLI `--version` (`parasite 0.4.4.5`).

### Fixed - Stage P4: Stint P4.4.4 Noise-Tolerant `dHash` Stability Gates, Post-Scroll Fallthrough, Draft Sanitization & Action-Row Copy Grounding (v0.4.4.4)
- **Version Bump (`0.4.4.4`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), and [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py).
- **Noise-Tolerant `hamming_distance` Gates & Immediate Post-Scroll Copy Assist ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Replaced brittle exact `cur_dhash != prev_dhash` equality checks in Step 8 (`SUBMITTING`) and Step 9 (`AWAITING_GENERATION`) with `hamming_distance` + `_frame_diff_score` thresholds (`(sub_hd >= 4 and sub_step_diff >= 2.5) or sub_total_diff >= 15.0` in Step 8; `(step_hd >= 3 and frame_step_diff >= 0.4) or frame_step_diff >= 1.2` in Step 9) so `1–2` bit blinking text-caret or scrollbar flicker no longer triggers false Enter-submit detection or starves Step 9 stability accumulation.
  - Gated Step 9 scrolling on genuine generation activity (`pre_hd >= 3 or frame_total_diff >= 2.5`) or `>= 4000ms` elapsed, switched `scroll_before_copy_attempts` (`3`) to a per-stability-window budget (total invocation cap `9`), and removed the post-scroll `continue` so Step 9 falls straight through to `HybridLocalAssistBackend.locate_copy_button()` in the same iteration.
- **Composer Draft Sanitization & Action-Row Copy Grounding ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Added leftover composer draft clearing (`ctrl+a`, `backspace`, `backspace`) in Step 6 (`PASTING_IMAGE`) and `_teardown(clear_draft=...)` when `identity_mode != "win32_title"`.
  - Added `max_local_y` (`rect_h - 72` when `rect_h >= 300`) composer-strip rejection in `HybridLocalAssistBackend._ask_vlm_locate()` / `locate_copy_button()`, expanded `reject_thought_substrings` (`"add attachments"`, `"attachment"`, `"plus"`, `"microphone"`, `"thumbs up"`, `"thumbs down"`, `"good response"`, `"bad response"`), and clarified the zero-digit Copy action-row target description (`Cadence §8.3`).
- **Verification ([`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Added unit tests `test_locate_copy_button_rejects_bottom_composer_strip_and_attachment_thoughts` and `test_step9_ignores_single_bit_dhash_caret_flicker_and_falls_through_after_scroll`, plus end-to-end integration test `test_uia_chrome_anchor_clears_draft_ignores_caret_flicker_and_scrolls_to_copy`.
  - Verified full regression suite after final edit: **596 passed, 1 warning in 73.21s (0:01:13)** (`test_parasite_skill.py` `27 passed`, `test_parasite_skill_pipeline.py` `22 passed`) and CLI `--version` (`parasite 0.4.4.4`).

### Fixed - Stage P4: Stint P4.4.3 1:1 VLM Crop Padding, Multi-Tick Submit Verification & Scroll-to-Bottom Copy Harvest (v0.4.4.3)
- **Version Bump (`0.4.4.3`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), and [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py).
- **1:1 Native-Pixel Padded VLM Canvas & Thought Guard ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Added `HybridLocalAssistBackend._pad_crop_for_vlm()` anchoring small overlay crops (e.g., `414 x 655`) at `(0, 0)` inside an `896 x 896` black-padded canvas ($\ge 1024$ Qwen2.5-VL `28x28` vision tokens), eliminating `llama-server` (`--image-min-tokens 1024`) $1.72\times$ internal upscaling distortion while preserving 1:1 native screen pixel coordinates.
  - Updated `_ask_vlm_locate()` to send the `(0, 0)`-anchored padded canvas, reject border-clamped (`cw - 1` / `ch - 1`) out-of-crop coordinates, and filter `Thought:` contradictions (`reject_thought_substrings` in `locate_copy_button()` rejecting `"send button"`, `"upward arrow"`, `"add tabs"`, etc.) with strengthened zero-digit prompts (`Cadence §8.3`).
- **Multi-Tick Enter Submission Verification & Chat Viewport Scroll-to-Bottom ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py), [`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py), [`config.yaml`](file:///C:/ParasiteAI/config.yaml)):**
  - Updated Step 8 (`SUBMITTING`) to capture a post-Enter settle baseline (`post_enter_frame`) so a single-tick newline shift inside the multi-line composer no longer suppresses the Send-button click fallback unless full composer collapse (`>= 15.0%` diff) or continued post-Enter frame transition occurs.
  - Added `scroll_before_copy_attempts: 3`, `scroll_wheel_delta: -8`, and `max_local_assist_calls_per_invoke: 4` in `ParasiteSkillConfig` / `config.yaml`, plus `ParasiteResult.scroll_steps` telemetry.
  - Updated Step 9 (`AWAITING_GENERATION`) to dispatch vertical mouse-wheel scroll-down steps over the chat viewport when generation settles without a visible Copy button, bringing long responses and the bottom Copy action bar into view before invoking `HybridLocalAssistBackend.locate_copy_button()`.
- **Smoke Probe Telemetry & Verification ([`scripts/smoke_test_p4_4_parasite_skill.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_4_parasite_skill.py), [`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Recorded `scroll_steps` in `P-C` / `P-D` smoke receipts and added 2 unit tests covering `_pad_crop_for_vlm` / thought-contradiction rejection / clamped OOB rejection and Step 8 newline fallback + Step 9 scroll-to-bottom.
  - Verified full regression suite after final edit: **593 passed, 1 warning in 68.38s (0:01:08)** (`test_parasite_skill.py` `25 passed`, `test_parasite_skill_pipeline.py` `21 passed`, `test_config.py` `13 passed`, `test_entrypoints.py` `15 passed`), CLI `--version` (`parasite 0.4.4.3`), and zero PyQt runtime imports (`PYQT_MODS []`).

### Fixed - Stage P4: Stint P4.4.2 Gemini Overlay Submission, Generation Gate & Copy Harvest Stabilization (v0.4.4.2)
- **Version Bump (`0.4.4.2`):** Updated package and CLI version strings across [`pyproject.toml`](file:///C:/ParasiteAI/pyproject.toml), [`parasite_ai/__init__.py`](file:///C:/ParasiteAI/parasite_ai/__init__.py), and [`parasite_ai/main.py`](file:///C:/ParasiteAI/parasite_ai/main.py).
- **Chromium UIA Awakening & Composer Caret Precision ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py)):**
  - Added `GeminiWindowBackend.awaken_accessibility()` (`EnumChildWindows` + `SendMessageTimeoutW` `WM_GETOBJECT` / `OBJID_CLIENT` + read-only `ControlFromPoint` client probes) before `_iter_uia_controls()` to materialize lazy Chromium `AXPlatformNodeWin` DOM trees.
  - Updated `has_input_focus()` to reject full-window outer `DocumentControl` wrappers ($\ge 50\%$ window height) so Step 5 clicks the actual composer input box when caret focus is absent, and broadened `find_uia_button()` across `ButtonControl`/`CustomControl`/`MenuItemControl`/`HyperlinkControl` while filtering false-positive `"copy link"` / `"copy prompt"` labels.
- **Verified Send-Button Submission & Generation Activity Gate ([`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py), [`parasite_ai/config.py`](file:///C:/ParasiteAI/parasite_ai/config.py), [`config.yaml`](file:///C:/ParasiteAI/config.yaml)):**
  - Upgraded Step 6 (`PASTING_IMAGE`) to require initial `dHash` change followed by 2 stable ticks (`attach_settle_ms: 2500`) so image uploads complete before prompt paste/submit, and added a `200ms` post-paste settle after Step 7 (`PASTING_QUERY`).
  - Added Step 8 verified submission check (`submit_verify_timeout_sec: 1.5`) in `ParasiteSkill.invoke()`: if `Enter` leaves the overlay visually unchanged, locates and clicks the Send button (`send_button_names: ["Send message", "Send", "Submit", "Submit prompt"]`) via UIA or `HybridLocalAssistBackend.locate_send_button()`, recording `ParasiteResult.submit_method` and `last_send_pos`.
  - Gated Step 9 (`AWAITING_GENERATION`) on `generation_activity_observed` or `min_generation_wait_ms: 2000` with pixel-diff tracking (`_frame_diff_score`), preventing premature Copy harvesting on unsubmitted composers.
  - Updated `HybridLocalAssistBackend._ask_vlm_locate()` to permit `Action: wait()` when a target control is absent (`ActionType.WAIT -> None`) with zero digits (`Cadence §8.3`), and added `40 px` spatial exclusion (`_is_excluded` / `exclude_points`) so `locate_copy_button()` never re-clicks `last_send_pos`.
  - Updated `abort()` and `_write_diagnostics()` to capture live `gemini_hwnd` failure screenshots automatically on post-focus errors alongside `identity_mode`, `rescued_by`, and `submit_method` JSON telemetry.
- **Smoke Probe Telemetry & Verification ([`scripts/smoke_test_p4_4_parasite_skill.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_4_parasite_skill.py), [`tests/unit/mind/test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py), [`tests/integration/test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)):**
  - Called `awaken_accessibility()` in `P-A` and recorded `identity_mode`, `submit_method`, and `rescued_by` in `P-C` / `P-D`.
  - Verified full regression suite after final edit: **591 passed, 1 warning in 69.77s** (`test_parasite_skill.py` `23 passed`, `test_parasite_skill_pipeline.py` `21 passed`, `test_config.py` `13 passed`, `test_entrypoints.py` `15 passed`), CLI `--version` (`parasite 0.4.4.2`), and zero PyQt runtime imports (`PYQT_MODS []`).

### Fixed & Enhanced - Stage P4: Stint P4.4.1 Chrome Overlay Symbiosis, Hybrid Local Assist & Smoke Probe Repairs
- **Root-Cause Remediation (Borderless Chrome Gemini Overlay & Toggle Semantics):**
  - Updated [`parasite_ai/mind/parasite_skill.py`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py) (`GeminiWindowBackend` & `ParasiteSkill`) to detect Chrome's titleless/borderless `"Gemini in Chrome"` floating overlay (`chrome.exe` with `has_minimize_box=False`, UIA signature matching via `overlay_uia_signatures`, and `HWND`-delta fallback in `resolve_gemini_window()`), while keeping standard titled `"Gemini"` tab/PWA verification intact (`identity_mode` telemetry on `ParasiteResult`).
  - Added toggle-safe pre-hotkey open-overlay reuse (`is_window_visible_active()`) and ESC/`WM_CLOSE`-based cleanup (`dismiss_window()`) in `_teardown()` so subsequent `Alt+G` invocations do not toggle an already-open overlay closed, plus post-hotkey desktop frame capture on Step 4 failure for deterministic diagnostics.
  - Replaced unescaped `&` in [`run_smoke_probe_p4_4.bat`](file:///C:/ParasiteAI/run_smoke_probe_p4_4.bat) (`^&` in `title`) so the launcher opens cleanly without `cmd.exe` syntax errors.
- **Tiered Option-B Hybrid Local Reasoning Fallback (`ILocalAssistBackend` / `HybridLocalAssistBackend`):**
  - Added [`HybridLocalAssistBackend`](file:///C:/ParasiteAI/parasite_ai/mind/parasite_skill.py) (`parasite_ai/mind/__init__.py` exports + [`parasite_ai/runtime.py`](file:///C:/ParasiteAI/parasite_ai/runtime.py) wiring) operating strictly inside verified `chrome.exe` window bounds: Tier 1 deterministic read-only UIA (`find_uia_input_center`, `find_uia_text_match`), Tier 2 scoped `ScreenGrounder` (`window_filter=hwnd`, `force_ocr=True`), and Tier 3 conditional crop-clamped `LocalBrainManager` VLM fallback reading `ActionPlan.coordinates` with zero numerical anchoring (`Cadence §8.3`) and bounded call budget (`max_local_assist_calls_per_invoke`, tracked via `ParasiteResult.rescued_by`).
  - Extended [`ParasiteSkillConfig`](file:///C:/ParasiteAI/parasite_ai/config.py) and [`config.yaml`](file:///C:/ParasiteAI/config.yaml) with `overlay_uia_signatures`, `input_box_names`, broadened `copy_button_names` / `stop_button_names`, `local_assist_enabled: true`, and `max_local_assist_calls_per_invoke: 3` (`enabled: false` preserved).
- **Smoke Probe Repairs & Deferred Roadmap Capture:**
  - Repaired [`scripts/smoke_test_p4_4_parasite_skill.py`](file:///C:/ParasiteAI/scripts/smoke_test_p4_4_parasite_skill.py): updated `P-A` (`resolve_gemini_window`, UIA label/input probe, `dismiss_window` cleanup), `P-B` (`set_image_dib`), `P-F` (`StepIntent.VERIFY_STATE`), `P-G` (process/compute VRAM via `nvidia-smi --query-compute-apps` plus `desktop_total_vram_mb` telemetry), and `_try_attach_running_brain()` probing `:8080/health`.
  - Documented deferred **Live Adaptive Benchmarking & In-Flight Approach Mutator** in [`FUTURE_IDEAS.md`](file:///C:/ParasiteAI/FUTURE_IDEAS.md#L410-L423) (§7.3) targeting **Stint P4.5** & **P4.6**.
  - Verified full unit + integration regression suite: **589 passed, 1 warning in 62.20s** (up from 584 via +4 unit tests in [`test_parasite_skill.py`](file:///C:/ParasiteAI/tests/unit/mind/test_parasite_skill.py) and +1 integration test in [`test_parasite_skill_pipeline.py`](file:///C:/ParasiteAI/tests/integration/test_parasite_skill_pipeline.py)), zero PyQt runtime imports (`PYQT_MODS []`), CLI `--version` (`parasite 0.4.4`), and smoke script `--help`.

### Added - Stage P4: Stint P4.4 Autonomous Skill Engine & The Titular ParasiteSkill
- **Universal Skill Engine & Visual Drift Protection (`parasite_ai.mind.skills`, `parasite_ai.mind.memory`, `data/skills/`)**:
  - Added pure-NumPy 64-bit 2D-DCT perceptual hashing (`compute_phash()`) to `parasite_ai/mind/memory.py` alongside `hamming_distance()` for sub-5ms container visual drift detection.
  - Defined `SKILL.md` format (YAML frontmatter via `yaml.safe_load` + Markdown template) in `parasite_ai/mind/skills.py` with two strict types: semantic `type: workflow` (zero coordinates anywhere, compiled to `LivingPlan`) and `type: reflex_micro_skill` (§7.6 exemption permitting bounded client-relative coordinates only when paired with `ReflexSafetyGate`).
  - Added runtime §7.6 4-gate dispatcher `verify_and_resolve_reflex_skill()` (bounds check, exact OS client/window dimension check, sub-5ms pHash anchor check, and fail-closed abort to UIA/VLM on mismatch).
  - Implemented `SkillRegistry` with deterministic pattern/keyword/process scoring, 30-day TTL decay (`ACTIVE -> STALE`), passive re-verification back to `ACTIVE` on clean success, non-destructive `_quarantine/` archival on drift or rejection, atomic temp-file writes, and `draft: true` operator sign-off gating (`approve_draft`, `reject_draft`).
  - Implemented deterministic `TraceRecorder` (redacting secrets and omitting raw coordinates in `sanitized_view()`, saving raw traces locally under `data/skills/_traces/`) and 6-gate `SkillLearner` co-authoring `draft=true` playbooks via `ParasiteSkill`.
  - Created `data/skills/README.md` and `data/skills/_template/SKILL.md`.
- **Win32 Raw Bitmap (`CF_DIB`) & Unicode Clipboard Driver (`parasite_ai.hands.clipboard`, `parasite_ai.hands`)**:
  - Implemented 64-bit-safe `ctypes` clipboard driver (`pack_dib`, `Win32ClipboardAPI`, `Win32ImageClipboard`, `ClipboardSnapshot`) supporting bottom-up 24-bit `CF_DIB` packing (`mod 4` row stride padding, RGB→BGR conversion), lock-retry acquisition (`ERROR_CLIPBOARD_NOT_OPEN` backoff), `GlobalFree` cleanup on ownership failure, and atomic snapshot/restore teardown.
- **Strict Nonce-Bound Parasite Protocol (`parasite_ai.mind.parasite_protocol`)**:
  - Implemented `ParasitePhase` (`PROACTIVE_PLAN`, `REACTIVE_RECOVERY`, `SKILL_COAUTHOR`), `RecoveryTrigger`, 22-code `ParasiteFailure` taxonomy, coordinate-free semantic models (`ParasitePlan`, `ParasiteAction`, `ParasiteRequest`), shared numeric coordinate guards (`assert_no_numeric_coordinates`), symbolic §8.3 prompt builders (`build_parasite_prompt`), and constant-time nonce-bound `<parasite_plan>` / `<parasite_action>` / `<parasite_skill>` tag parser (`parse_response`) defending against screen-sourced prompt injection.
- **The Titular `ParasiteSkill` Orchestrator (`parasite_ai.mind.parasite_skill`)**:
  - Built physical desktop symbiosis state machine targeting `"Gemini in Chrome"` via `Alt+G` hotkey, `GeminiWindowBackend` (GUITHREADINFO/UIA caret verification and read-only UIA tree walks for Stop/Copy buttons, zero `rect[3] - 68` coordinate math), `Win32EnvironmentDiscovery` (Start Menu `.lnk` stems + `App Paths` registry + sensitivity-filtered open windows, zero hardcoded app maps), Monitor-1 `CF_DIB` image + Unicode prompt paste (`Ctrl+V` + `Enter`), sentinel Copy harvest, `minimize_window` + prior focus & clipboard teardown, circuit breaker, JSON/PNG diagnostics rotation (`logs/parasite_skill_diagnostics/`), and `parasite_skill_alert` UIBridge emission.
- **Closed-Loop Pipeline, Runtime & Discord C2 Integration (`parasite_ai.mind.dual_mind`, `parasite_ai.runtime`, `parasite_ai.ui.discord_bot`, `parasite_ai.config`, `config.yaml`, `pyproject.toml`, `parasite_ai/__init__.py`, `parasite_ai/main.py`)**:
  - Added `SkillsConfig` (`enabled=False` default) and `ParasiteSkillConfig` (`enabled=False` default) to `AppConfig`, enabled in `config.yaml` (`skills.enabled: true`, `skills.learning_enabled: false`, `parasite_skill.enabled: true`, `proactive_mode: "open_ended"`).
  - Integrated local skill matching, `should_trigger_proactive_plan()`, §7.6 reflex burst dispatch, deferred workflow drift quarantine, Tier-2 reactive routing (`CONSECUTIVE_CLICK_FAILURES` / `OSCILLATION` attribution), rich `[Selected: <program>]` CUA working memory injection, and per-step trace observation into `DualMindPipeline` while preserving byte-identical P3 suppression when disabled.
  - Wired thread-safe `approve_learned_skill` / `reject_learned_skill`, episode receipt skill outcome updates, and Discord `SkillApprovalView` (`[Approve Skill]`, `[Reject / Quarantine]`, fail-closed whitelist) + `parasite_skill_alert` / `skill_learned` embeds.
  - Added live hardware smoke suite `scripts/smoke_test_p4_4_parasite_skill.py` (`P-A`..`P-G`) and `run_smoke_probe_p4_4.bat`. Unified version string to `0.4.4`.
- **Test Coverage & Verification**:
  - Added **110 new tests** across 8 suites: `tests/unit/hands/test_clipboard_dib.py` (21), `tests/unit/mind/test_skill_schema.py` (19), `tests/unit/mind/test_skill_registry.py` (7), `tests/unit/mind/test_phash_drift.py` (6), `tests/unit/mind/test_parasite_protocol.py` (16), `tests/unit/mind/test_skill_learning.py` (4), `tests/unit/mind/test_parasite_skill.py` (17), and `tests/integration/test_parasite_skill_pipeline.py` (20).
  - Verified zero PyQt6 runtime/source imports, CLI `--version` (`parasite 0.4.4`), `_template/SKILL.md` schema lint, and full non-archived test suite: **584 / 584 passed in 69.34s (100% green, zero regression across 474 existing tests)**.

### Added - Stage P4: Stint P4.3 Interface Decoupling & Remote C2 (Headless Core + Discord Bot)
- **Pure-Python Headless Engine & UI Decoupling (`parasite_ai.ui.bridge`, `parasite_ai.runtime`, `parasite_ai.main`, `parasite_ai.config`, `config.yaml`)**:
  - Completely decommissioned legacy PyQt6 desktop overlay widgets (`CompanionDock`, `GhostHUD`, `win32_styles`), moving them and their 86 Qt widget tests to `archive/legacy_pyqt6_ui/` and `tests/archive/legacy_pyqt6_ui/` with comprehensive rollback reference notes and pre-P4.3 commit baseline (`b033e76`).
  - Removed `PyQt6>=6.7.0` and `pytest-qt>=4.4.0` from `pyproject.toml` and installed `discord.py>=2.4.0` via `uv sync`.
  - Re-architected `UIBridge` as a thread-safe, pure-Python event bus and command queue (`Signal`, `GoalRequest`, `EpisodeEvent`) supporting signal emission and episode lifecycle fanout with zero Qt event loop dependencies.
  - Re-architected `RuntimeOrchestrator` as a pure-Python class with structured episode events (`started`, `step_completed`, `finished`) and consent plumbing.
  - Refactored `parasite_ai/main.py` into a pure-Python background daemon, cleanly separating `--headless` (real OS desktop control without local overlay windows) from `--simulation` / `--dry-run` (mock CI hardware backends). Added `launch_parasite_discord.bat` launcher.
  - Short-circuited `_evade_companion_dock_if_needed` in `ActionDispatcher` to 0ms when running headless or with overlays absent.
- **Remote Discord Command & Control Daemon (`parasite_ai.ui.discord_bot`, `parasite_ai.config`, `config.yaml`)**:
  - Implemented async, zero-VRAM `DiscordBotC2` (`discord.py` `commands.Bot` + `app_commands.CommandTree`) running in a dedicated background daemon thread.
  - Enforced fail-closed whitelist authorization (`DiscordConfig.authorized_user_ids` populated via `config.yaml` or `PARASITE_DISCORD_USER_IDS` env var; rejects all users when empty).
  - Implemented slash commands:
    - `/task goal:<str> [max_steps:<int>]`: Dispatches user goal, spawns dedicated Discord thread (`🧵 Task: <goal>...`), streams thoughts and telemetry, and sends final `EpisodeReceipt` summary embed.
    - `/panic`: Immediate $<2\text{ms}$ software interrupt token preemption, triggers panic manager, flushes goal queue, and aborts any active consent waiters.
    - `/status`: Returns live hardware telemetry (GPU VRAM via `check_vram_headroom()`, Windows physical RAM via `GlobalMemoryStatusEx`, and foreground window title/process).
    - `/screen`: Captures desktop, downscales proportionally to `screen_max_width`, encodes in-memory JPEG, and attaches to embed with zero unrequested disk artifacts.
  - Integrated `trim_embed_value` 1000-char safety chunking and cyber embed color palette (`0x00F0FF` active, `0xFFB300` warning, `0xFF0055` panic/error, `0x00FF87` completion).
- **Deterministic Risk Classifier & Interactive Consent Gate (`parasite_ai.safety.risk_gate`, `parasite_ai.safety`, `parasite_ai.mind.dual_mind`)**:
  - Implemented deterministic `classify_action_risk` in `parasite_ai/safety/risk_gate.py` categorizing `ActionPlan` into `GREEN` (safe/observational), `YELLOW` (state-mutating/comm/general CLI), and `RED` (destructive CLI, credential manipulation, irreversible deletion).
  - Wired interactive `RiskConsentView` (`[Approve]`, `[Cancel]`, 60s fail-closed timeout) into `DualMindPipeline.step()` for Discord-dispatched tasks, while leaving unattended local CLI/benchmark runs fully non-blocking.
- **Test Coverage & Verification**:
  - Added 22 new unit tests across `tests/unit/safety/test_risk_gate.py` (9 tests), `tests/unit/ui/test_discord_bot.py` (11 tests), and `tests/unit/core/test_config.py` (2 tests).
  - Updated `tests/unit/ui/test_ui_bridge.py`, `tests/unit/core/test_entrypoints.py`, `tests/unit/core/test_logging_diagnostics.py`, `tests/unit/vision/test_grounding.py`, and `tests/integration/test_e2e_integration.py` to pure-Python interfaces.
  - Verified runtime zero-PyQt6 invariant: **ZERO-PYQT INVARIANT VERIFIED CLEAN**.
  - Full non-archived regression test suite: **474 / 474 passed in 45.71s (100% green)**.

### Added - Stage P4: Stint P4.2 Layer 0.5 Chained Reflex & Muscle Memory Burst Engine
- **Chained Reflex & Muscle Memory Burst Engine (`parasite_ai.hands.reflex`, `parasite_ai.hands`, `parasite_ai.config`, `config.yaml`)**:
  - Implemented `ReflexBurstDispatcher` and `ReflexBurstResult` in `parasite_ai/hands/reflex.py`, enabling sub-200ms CPU-native compound burst execution without intermediate VLM inference passes.
  - Added randomized 15–30ms inter-action biological hesitation, continuous $<2\text{ms}$ touch preemption checks (`InterruptGuard.is_active` / cancellation tokens) on every sub-action, centroid snapping per click target, and early abort on target window anomaly/hijack.
  - Added `ReflexConfig` to `parasite_ai/config.py` and `hands.reflex` to `config.yaml`.
  - Added optional `move_duration`, `hesitation_s`, and `dwell_s` overrides to `MouseDriver.click()`.
- **Compound Action Syntax & Grammar Parsing (`parasite_ai.mind.uitars_parser`, `parasite_ai.mind.memory`)**:
  - Added `ActionType.BURST` to `memory.py` with `"BURST"`, `"SEQUENCE"`, `"CHAIN"` verb synonyms, `INTERACTIVE_ACTION_TYPES` membership, `burst_actions: Optional[List[ActionPlan]]`, and `burst_count` tracking in `StepRecordSummary`.
  - Implemented `_split_top_level_calls()` and `_parse_single_action_call()` in `uitars_parser.py` parsing nested compound calls (`burst([...])`, `sequence([...])`, `chain([...])`) and comma-separated top-level chains (e.g. `hotkey("ctrl", "a"), click(start_box="(100, 200)"), type(content="hello")`) into `ActionPlan(action=ActionType.BURST, burst_actions=[...])`.
  - Updated `UITARS_SYSTEM_PROMPT` documenting compound `burst(...)` actions and advising coordinate-grounded anchoring before typing on desktop backgrounds.
- **DualMind Pipeline Integration & Multi-Target Telemetry Overlays (`parasite_ai.mind.dual_mind`, `parasite_ai.vision.debug_capture`)**:
  - Wired `ReflexBurstDispatcher` into `ActionDispatcher` and integrated `ActionType.BURST` execution in `DualMindPipeline.step()`, computing post-burst active window ROI diffs and dynamic post-render settling delays.
  - Added multi-target numbered green crosshairs (`burst_coords`) in `DebugScreenshotRecorder._annotate_pre_frame()` and `save_step_frames()`.
- **Test Coverage & Verification**:
  - Added 12 new unit/integration tests across `tests/unit/hands/test_reflex.py` (6 tests), `tests/unit/mind/test_uitars_parser.py` (5 tests), and `tests/integration/test_dual_mind.py` (1 test).
  - Full unit and integration regression test suite: **537 / 537 passed in 49.53s (100% green)**.

### Fixed - Stage P4: Stint P4.1.3 CompanionDock Monitor-2 Placement & Debug Screenshot Hygiene
- **Monitor-2 Placement (`parasite_ai.config`, `parasite_ai.ui.companion_dock`)**:
  - Added `CompanionDockConfig.monitor_index: int = 2` (1-based) and `CompanionDock._resolve_target_screen()`, updating `anchor_to_screen()` and `evade_coordinates()` so `CompanionDock` spawns on Monitor 2 by default and falls back cleanly to `primaryScreen()` on single-monitor setups.
- **Debug Screenshot Hygiene & Settling Burst Saving (`parasite_ai.vision.debug_capture`, `parasite_ai.mind.dual_mind`)**:
  - Added `DebugScreenshotRecorder._to_bgr()` (`RGB -> BGR` conversion) so saved JPEGs preserve accurate colors.
  - Skipped disk writes to the default `"data"` directory when `PYTEST_CURRENT_TEST` is set so `pytest` runs never pollute `data/screenshots/` while `tmp_path` unit tests still run.
  - Added `burst_frames` collection during `DualMindPipeline.step()` post-action render settling and `DebugScreenshotRecorder.save_step_frames(..., burst_frames=...)` saving `step_XX_post_01.jpg`, `step_XX_post_02.jpg`, etc.
  - Added 3 unit tests in `tests/unit/ui/test_companion_dock.py` (1) and `tests/unit/vision/test_debug_capture.py` (2).
  - Full regression suite after final edit: **525 / 525 passed in 48.72s (100% green)**.

### Added - Stage P4: Stint P4.1.2 Diagnostic Screenshot Capture & Rich Step Telemetry
- **Per-Step Annotated Diagnostic Screenshots (`parasite_ai.vision.debug_capture`, `parasite_ai.config`, `config.yaml`)**:
  - Added `DebugScreenshotRecorder` (`start_episode()`, `save_step_frames()`) saving human-only annotated `step_XX_pre.jpg` (red raw VLM crosshair, green final snapped/nudged crosshair + arrow, and top telemetry banner) and `step_XX_post.jpg` under `data/screenshots/<timestamp>_<goal_slug>/` without mutating the live perception buffer.
  - Added `SystemConfig.save_debug_screenshots` (default `False` in Pydantic for test isolation, enabled `true` in `config.yaml`), `max_screenshot_episodes` (`20`), and `max_archived_logs` (`25`), with automatic oldest-episode pruning and sensitive-window skip protection.
- **Richer Precision, Optical, & Probe Telemetry (`parasite_ai.mind.dual_mind`, `parasite_ai.runtime`, `parasite_ai.main`, `scripts/smoke_test_p4_1_precision.py`)**:
  - Wired `ActionDispatcher.last_refinement`, `[CENTROID NO-SNAP]` / `[OPTICAL ZOOM]` pass-through traces, and unified per-step `[STEP TELEMETRY]` logging in `DualMindPipeline.step()`, plus episode initialization in `Runtime._execute_goal_episode()`.
  - Added archive log pruning in `setup_logging()` (`parasite_ai/main.py`) and mirrored `[P4.1 SMOKE]` stdout messages through `logger.info` / `logger.error` in `scripts/smoke_test_p4_1_precision.py`.
  - Added 4 tests across `tests/unit/vision/test_debug_capture.py` (3 tests) and `tests/integration/test_dual_mind.py` (1 test).
  - Full regression suite after final edit: **522 / 522 passed in 52.54s (100% green)**.

### Fixed - Stage P4: Stint P4.1.1 Precision & Probe Stabilization Hotfix
- **Lazy UIA Grounding & O(1) `ControlFromPoint` Snapper (`parasite_ai.vision.grounding`)**:
  - Initialized `children: Optional[Any] = None` at the top of `ScreenGrounder._walk_uia_tree_inner()` to eliminate `UnboundLocalError` when `ground(lazy=True)` walks an external foreground window directly, and increased `lazy=True` single-window traversal limits (`walk_depth=6`, `raw_elements=80`, `max_win_elements=80`, `total_nodes_scanned=250`) to reach nested UWP controls.
  - Added O(1) Win32 accessibility point probing (`CentroidSnapper._inspect_uia_control_at()` & `_snap_via_uia_point()`, `strategy="uia_point"`) walking up to 2 ancestors from UWP `Text`/`Image` hit nodes to enclosing eligible buttons (`<=120x120 px`), recovering narrow border misses via at most 4 cardinal offsets (`edge_margin_px`), and halting contour fallback on `Edit`/`Document` surfaces (`enable_uia_point_probe=False` default).
- **Safe Unquoted Optical Hint Extraction & Config-Gated Tier-2 Micro-Glance (`parasite_ai.config`, `parasite_ai.vision.foveated`)**:
  - Added `VisionConfig.enable_vlm_micro_glance: bool = False` in `parasite_ai/config.py` to avoid unintended 1024-token VLM crop latencies while preserving standalone `ActionDispatcher(..., vlm_glance_fn=...)` behavior.
  - Added conservative unquoted action-target extraction in `extract_target_glyph_hint()` filtering prose stopwords, raw coordinates, and generic UI/positional nouns (e.g. `icon`, `window`, `top-left`) so CPU RapidOCR verification operates safely in CUA mode.
- **CUA Point-Probe Wiring & Target-Gated Monitor Relocation (`parasite_ai.mind.dual_mind`)**:
  - Updated `ActionDispatcher.__init__` and `_refine_click_target()` to auto-enable UIA point probing on live non-mock `win32` desktops and pass `use_uia_point=(cua_mode and not som_elements)` into `CentroidSnapper.snap_with_details()`.
  - Updated `DualMindPipeline._get_effective_active_window(user_goal: Optional[str] = None)` (and runtime `step()` / `_step_legacy_two_pass()` callers) to gate Monitor-2 relocation via `evaluate_window_disposition(...) == "TARGET"` when `user_goal` is supplied, keeping non-target Monitor-2 windows (e.g. `chrome_widgetwin_1`) undisturbed while preserving unscoped direct helper calls.
- **Interactive Hardware Probe & Verification (`scripts/smoke_test_p4_1_precision.py`, `run_smoke_probe_p4_1.bat`, tests)**:
  - Hardened `scripts/smoke_test_p4_1_precision.py` with `setup_logging()`, 5.0s Calculator polling + target-monitor relocation, `uia_bbox` + CUA `uia_point` click coverage across `'7'`, `'8'`, `'9'`, and `AutomationId="CalculatorResults"` (`searchDepth=6`) display readout verification.
  - Isolated `run_smoke_probe_p4_1.bat` benchmark output via `--output-name smoke_p4_1_L1_08` (protecting `baseline_p0.*`) with dual `[2/3]` / `[3/3]` status reporting.
  - Added 6 tests across `tests/unit/vision/test_grounding.py`, `tests/unit/vision/test_centroid_snapper.py`, and `tests/integration/test_dual_mind.py`.
  - Full regression suite after final edit: **518 / 518 passed in 48.55s (100% green)**.

### Added - Stage P4: Precision Actuation, Chained Reflexes, Discord C2 & App Memory
- **Stint P4.1: Physical Precision Layer (`parasite_ai.hands.kinematics`, `parasite_ai.hands.mouse`, `parasite_ai.vision.grounding`, `parasite_ai.vision.foveated`, `parasite_ai.mind.dual_mind`, `parasite_ai.config`)**:
  - **HumanCurve Two-Phase Ballistics & Biological Actuation (`parasite_ai.hands.kinematics`, `parasite_ai.hands.mouse`, `parasite_ai.config`)**:
    - Added asymmetric `two_phase_progress()` and `two_phase_velocity()` profiles to `KinematicsEngine` (Phase 1 ballistic sprint covering ~80–85% of distance with early peak acceleration around 37% duration, followed by Phase 2 smooth deceleration/homing into target bounds) with zero chaotic wind.
    - Added pre-click biological motor commitment hesitation (`25-60ms` configurable pause before `WM_LBUTTONDOWN`) and normally distributed stochastic button dwell hold (`45ms +/- 10ms`) in `MouseDriver.click()`, preserving sub-2ms cancellation token preemption via `_wait_interruptible()`.
    - Propagated `use_two_phase_ballistics`, `enable_motor_hesitation`, `motor_hesitation_min_ms`, `motor_hesitation_max_ms`, `dwell_mean_ms`, and `dwell_std_ms` in `MouseConfig`.
  - **Sub-Millimeter Centroid Button Snapping (`parasite_ai.vision.grounding`)**:
    - Implemented `CentroidSnapper` (`snap()`, `snap_with_details()`) to automatically center clicks on small interactive controls (`<=120x120 px`) when coordinates land within `8 px` of an edge or narrowly miss a border.
    - Uses Win32 UIA/SoM bounding boxes first (explicitly excluding `Edit` and `Document` surfaces to preserve caret positioning) and falls back to fast CPU OpenCV Canny/contour bounding-box detection on a local patch.
  - **Pre-Click Optical Zoom Verification (`parasite_ai.vision.foveated`, `parasite_ai.mind.dual_mind`)**:
    - Implemented `PreClickOpticalVerifier` (Hybrid Option C) and `extract_target_glyph_hint()` extracting a `128x128 px` 1:1 native crop around the target coordinate.
    - Tier 1 runs fast CPU RapidOCR glyph alignment and nudges the click to the detected glyph center (within `+/-24 px`); Tier 2 supports optional constrained VLM micro-glance fallback (`max_tokens=8`, symbolic `OFFSET(dx, dy)` / `MISMATCH` abort) on ambiguous targets.
    - Wired `CentroidSnapper` and `PreClickOpticalVerifier` into `ActionDispatcher._refine_click_target()` and `DualMindPipeline.step()`, passing live `frame` and `frame_origin`.
  - **Interactive Smoke Probe & Unit Test Coverage**:
    - Added `scripts/smoke_test_p4_1_precision.py` and `run_smoke_probe_p4_1.bat` targeting live Windows Calculator border-clipped clicks (`7, 8, 9`) and `L1-08`.
    - Added 17 unit tests across `tests/unit/hands/test_human_mouse_kinematics.py` (6 tests) and `tests/unit/vision/test_centroid_snapper.py` (11 tests).
    - Full regression suite: **512 / 512 passing (100% green)** across 438 unit tests and 74 integration tests.

### Added - Stage P3: Benchmark Certification & Alpha Gate Certification
- **Stint P3.4: Stage P3 Clean 20-Task Benchmark Certification Run (`benchmarks/results/baseline_p3.md`, `baseline_p3.json`)**:
  - **Empirical 20-Task Certification Scorecard**:
    - **Ground-Truth Pass Rate:** **35.0% (7/20)** — All-time project record (+15.0% net lift over P2.7, 7x over P0 baseline).
    - **Level 1 Pass Rate:** **50.0% (5/10)**: `L1-02` (Calculator DONE, 29.4s), `L1-03` (Paint, 31.5s), `L1-06` (Close Notepad, 32.4s), `L1-07` (Minimize Notepad, 34.1s), `L1-09` (File Explorer, 32.8s).
    - **Level 2 Pass Rate:** **14.3% (1/7)**: `L2-07` (Harvest Token to Clipboard, 48.2s).
    - **Level 3 Pass Rate:** **33.3% (1/3)**: `L3-01` (Close Dirty Notepad & Don't Save, 53.7s).
    - **Median Step Latency:** **6.034s** (down from 8.686s, -2.65s faster, a 30.5% speedup).
    - **P90 Step Latency:** **6.763s** (down from 9.360s, -2.60s faster).
    - **Mean Task Duration:** **45.65s** (down from 60.3s, -14.6s faster).
    - **False-DONE Rate:** Strictly **5.0% (1/20)** (`L2-06` launched Notepad++ instead of classic Notepad).
    - **Subprocess Timeouts:** **0 / 20** (100% clean exit across all 20 tasks, eliminating all artificial 60s aborts).
    - **Unhandled Crashes:** **0 / 20** (`UNKNOWN_FAILURE` dropped to 0).
    - **Hardware Interrupts:** **0** (perfect physical compliance).
    - **Alpha Gate Status:** **OFFICIALLY PASSED** 🟢.

### Planned - Stage P4: Precision Actuation, Chained Reflexes, Discord C2 & App Memory
- **Stage P4 Master Architecture & Implementation Plan (`p4_implementation_plan.md`)**:
  - Ratified clean 4-layer cognitive stack (L1 Physical Actuation -> L2 Chained Reflexes -> L3 Tactical 7B CUA -> L4 Strategic Gemini Offload).
  - Defined 6-stint roadmap: P4.1 (Physical Precision: `human-mouse` + Centroid Snapper + Optical Zoom) $\rightarrow$ P4.2 (Layer 2 Chained Reflex Engine) $\rightarrow$ P4.3 (Headless Discord C2) $\rightarrow$ P4.4 (Multimodal Screenshot Offload to Gemini) $\rightarrow$ P4.5 (`SKILL.md` Playbooks & Rot-Resistant Anti-Pattern Governance) $\rightarrow$ P4.6 (Benchmark Certification).
  - Target: $\ge 50.0\%$ benchmark pass rate, 100% Calculator button accuracy, 4x speedup on compound sequences.

### Added - Stage P3: Planner Tiers, Loop Breaking & Strategic Escalation
- **Stint P3.3.2: Suite Timeout Realignment, Closed-Process Teardown Affordance & Stale Cache Reset (`parasite_ai.mind.verifier`, `benchmarks.suite.yaml`, `benchmarks.run_benchmark`, `tests/unit/mind/test_goal_verifier.py`)**:
  - **Empirical Suite Timeout Calibration (`benchmarks/suite.yaml`)**:
    - Realigned task timeout allocations to match the physical latency profile of local 7B multimodal inference and physical kinematics ($\approx 8.7\text{s}/\text{step}$): scaled 8-step tasks from 60s to 85s, 12-step tasks from 75s to 110s, and 15-step tasks from 90s to 135s.
    - Eliminates artificial `subprocess.TimeoutExpired` aborts that prematurely terminated valid reasoning chains on tasks `L1-04`, `L1-05`, `L1-08`, and `L2-07`.
  - **Closed-Process Teardown Affordance (`parasite_ai.mind.verifier`)**:
    - Enhanced `RuntimeGoalVerifier.build_working_memory_snapshot()` to detect teardown intents (`close`, `exit`, `quit`, `terminate`, `kill`, `don't save`). Once target processes are confirmed terminated in live Win32 window state, dynamically injects `- Target Application Status: <app> is CLOSED / TERMINATED (0 open windows). Teardown goal is fulfilled -> Emit DONE.`
    - Upgraded Phase 7 in `_derive_subgoal_checklist()` to mark `[x] Close <target>` and `[x] Discard unsaved changes ('Don't Save')` upon process termination.
    - Fixed regex matching and false prerequisite collisions in `_check_window_and_app_state()` so teardown goals (`L3-01`) immediately pass and never collide with Notepad launch checks. Resolves the 5-step ghost-window hallucination loop.
  - **Clean Run Flag & Stale Receipt Wipe (`benchmarks/run_benchmark.py`)**:
    - Added `--fresh` CLI flag to wipe outdated JSON/MD reports and receipt files on demand.
    - Archived partial run to `benchmarks/results/baseline_p3_partial.json` and wiped stale receipts so the benchmark runner starts fresh without skipping fixed tasks.
  - **Unit Test Health**:
    - Added 4 new unit tests in `tests/unit/mind/test_goal_verifier.py` validating teardown affordance injection, non-collision with launch goals, composite modal dialog dismissal, and suite timeout proportionality.
    - Certified 100% green pass rate across 421 unit tests (`python scripts/test.py unit -q`) and 74 integration tests (`python scripts/test.py integration -q`). Total active suite: 495 / 495 passing.

- **Stint P3.3.1: Benchmark Hardening & Frozen WindowInfo Dataclass Fix (`parasite_ai.mind.dual_mind`, `benchmarks.verifiers`, `tests/unit/mind/test_window_focus_and_navigation.py`)**:
  - **Frozen `WindowInfo` Dataclass Mutation Fix (`parasite_ai.mind.dual_mind`)**:
    - Replaced direct mutation `cur_win.rect = (...)` with `dataclasses.replace(cur_win, rect=new_rect)` and `SimpleNamespace` fallback in `_get_effective_active_window()`, resolving the `FrozenInstanceError: cannot assign to field 'rect'` crash that aborted benchmark tasks during Monitor 2 relocation checks.
  - **Strict Window Title Immunity for Benchmark Runner Console (`parasite_ai.mind.dual_mind`, `benchmarks.verifiers`)**:
    - In `relocate_window_to_monitor()`, added narrow title matching for `"benchmark runner"`, `"parasiteai stage"`, and `"parasiteai benchmark"` so the runner console window on Monitor 2 is never dragged to Monitor 1.
    - In `minimize_non_target_monitor1_windows()`, added exemption for windows titled with `"benchmark runner"` to prevent minimizing or dismissing the test runner console during benchmark task preparation.
    - Strictly avoids broad process name exemptions (`cmd.exe`, `powershell.exe`) to preserve future automation capabilities.
  - **Unit Test Health**:
    - Added 2 new unit tests in `tests/unit/mind/test_window_focus_and_navigation.py` validating frozen dataclass immutability handling and benchmark runner title immunity.
    - Certified 100% green pass rate across 417 unit tests (`python scripts/test.py unit -q`) and 74 integration tests (`python scripts/test.py integration -q`). Total active suite: 491 / 491 passing.

- **Stint P3.3: Visible Browser Consultation Hardening (`parasite_ai.mind.offloader`, `parasite_ai.mind.dual_mind`, `tests/integration/test_browser_offloader.py`)**:
  - **Browser Window Monitor 1 Relocation Guard (`parasite_ai.mind.offloader`)**:
    - Implemented `ensure_on_primary_monitor()` on `Win32BrowserWindowBackend` and `MockBrowserWindowBackend`, which checks whether the browser's horizontal center falls outside Primary Monitor 1 ($X < 0$ or $X \ge 1920$).
    - If on Monitor 2 or beyond, automatically un-maximizes zoomed windows (`SW_RESTORE`) and snaps the browser onto Monitor 1 at $(50, 40)$ via Win32 `SetWindowPos(SWP_NOZORDER | SWP_SHOWWINDOW)`, ensuring grounded selectors and fallback prompts are 100% visible and actionable.
    - Added Microsoft Edge window matching in `find_browser_window` alongside Chrome and Opera.
  - **Outbound Prompt Sanitizer (`parasite_ai.mind.offloader`)**:
    - Implemented `sanitize_consultation_prompt(prompt)` to scrub sensitive tokens before transmission to external web AI interfaces. Redacts `sk-` OpenAI tokens, `AIza` Google keys, `ghp_` GitHub tokens, bearer tokens, and password/secret assignments to `[REDACTED_API_KEY]`, `[REDACTED_TOKEN]`, and `[REDACTED_SECRET]`.
  - **Strategic Advisor Blueprint Working Memory Injection (`parasite_ai.mind.dual_mind`)**:
    - In single-pass CUA mode (`use_cua_single_pass=True`), if an active strategic advisor plan is loaded on `self.active_plan`, dynamically formats and injects `- Strategic Advisor Guidance: Step {step_id} ({intent}) — {description}` into `working_memory_context` so UI-TARS 1.5 7B directly perceives the advised recovery strategy.
  - **Integration Test Health**:
    - Added 3 integration tests in `tests/integration/test_browser_offloader.py` validating Monitor 2 to Monitor 1 browser relocation, credential scrubbing, and CUA working memory advisor plan injection.
    - Certified 100% green pass rate across 415 unit tests (`python scripts/test.py unit -q`) and 74 integration tests (`python scripts/test.py integration -q`). Total active suite: 489 / 489 passing.

- **Stint P3.2: Compound Working Memory Checklists & Taskbar Affordances (`parasite_ai.mind.verifier`, `tests/unit/mind/test_goal_verifier.py`)**:
  - **Taskbar Background Applications Affordance (`parasite_ai.mind.verifier`)**:
    - Enriched `RuntimeGoalVerifier.build_working_memory_snapshot()` to inspect open windows against the foreground active window.
    - For target applications relevant to the goal (or standard desktop processes) that are open in the background or minimized, injected explicit dynamic affordance lines: `- Running Background Applications: <Title> (<Proc>) [Minimized / In Background] -> Click taskbar at y={tb_top}..{tb_bot} to restore`.
    - Eliminates redundant desktop double-clicks, search menu re-launches, or taskbar icon searching by directly surfacing the physical vertical coordinate bounds of the taskbar strip in native screen pixels without hardcoding horizontal button positions.
  - **Chronological Phased Sub-Goal Checklist Decomposition (`parasite_ai.mind.verifier`)**:
    - Re-architected `RuntimeGoalVerifier._derive_subgoal_checklist()` into a multi-phase procedural pipeline:
      - **Phase 1: Modal Dialog Prerequisite**: Prioritizes `[x]/[ ] Dismiss modal dialog` before application operations.
      - **Phase 2: Source Application Launch & Navigation**: Handles seed files (`[x]/[ ] Open <file> in Notepad`), Calculator launch & arithmetic computation (`[x]/[ ] Compute {n1} {op} {n2} in Calculator`), Browser navigation (`[x]/[ ] Launch Browser`, `[x]/[ ] Navigate to {url}` with domain root matching), Paint, and File Explorer.
      - **Phase 3: Secondary / Destination Applications**: Sequentially tracks `[x]/[ ] Launch Notepad` when needed, distinguishing active imperative commands from passive references to pre-opened windows.
      - **Phase 4: Data Entry / Editing**: Dynamically checks Notepad buffer for quoted text appends, arithmetic results (formatted or raw integers), prose greetings, or browser heading captures.
      - **Phase 5: Clipboard Operations**: Tracks token harvesting and quoted string captures in system clipboard.
      - **Phase 6: Persistence & File Management**: Verifies file creation on disk, target directory creation, and file renaming.
      - **Phase 7: Teardown / State Management**: Verifies application closing and window minimization.
  - **Unit Test Health**:
    - Added 5 new comprehensive unit tests in `tests/unit/mind/test_goal_verifier.py` testing minimized and background taskbar affordances, Calculator to Notepad multi-app sequencing, Browser to Notepad navigation and heading recording, and seed file appending / token harvesting.
    - Certified 100% green pass rate across all 415 unit tests (`python scripts/test.py unit -q`) and all 71 integration tests (`python scripts/test.py integration -q`). Total active suite: 486 / 486 passing.

- **Stint P3.1: Semantic Loop Breaker, Action Chaining & Monitor 2 Relocation Guard (`parasite_ai.mind.uitars_parser`, `parasite_ai.mind.dual_mind`, `tests/unit/mind/test_uitars_parser.py`, `tests/unit/mind/test_window_focus_and_navigation.py`, `tests/unit/mind/test_modal_and_menu_recovery.py`, `tests/unit/vision/test_vlm_grounder.py`)**:
  - **Universal Action Chaining (`parasite_ai.mind.uitars_parser`)**:
    - Enhanced `parse_uitars_action()` to recognize trailing newlines (`\n`, `\r\n`, `\\n`) and explicit kwargs (`submit=True`, `enter=True`, `press_enter=True`) in `type(...)` actions, setting `submit=True` while stripping trailing newline characters from `action_plan.text`. Allows typing and submission to execute atomically in a single dispatch turn, eliminating unnecessary 8.5-second inference passes.
  - **Pre-Dispatch Semantic Oscillation & Loop Breaker (`parasite_ai.mind.dual_mind`)**:
    - **Repetitive Typing Recovery**: In `DualMindPipeline.step()`, detects consecutive identical text typing across turns (addressing failure mode `L3-02`). Automatically converts redundant typing into `ActionType.HOTKEY(keys=['enter'])` to submit the typed input and launch the application.
    - **Repeated Double-Click Recovery**: Detects consecutive `DOUBLE_CLICK` actions within a 24px spatial cluster on the desktop surface (addressing failure mode `L3-03`). Converts the action to `ActionType.HOTKEY(keys=['enter'])` to launch the selected desktop icon via the Windows shell launch verb.
    - **Click-to-Double-Click Radius Generalization**: Expanded coordinate tolerance from 20px to 24px for upgrading single clicks to double clicks on desktop targets.
  - **Monitor 2 Auto-Relocation Guard (`parasite_ai.mind.dual_mind`)**:
    - Implemented `relocate_window_to_monitor(hwnd, target_mon_idx=1)` querying live Win32 window geometry and snapping non-shell windows centered on Monitor 2 ($cx \ge 1920$) onto Monitor 1 at $(100, 100)$ via `user32.SetWindowPos(hwnd, 0, 100, 100, w, h, SWP_NOZORDER)`.
    - Integrated relocation check into `ActionDispatcher._activate_target_window_if_needed()` and `DualMindPipeline._get_effective_active_window()`, ensuring newly spawned windows on Monitor 2 are automatically brought onto Monitor 1 for visual grounding.
  - **Post-Dispatch Coordinate Cluster & Typing Loop Tracking (`parasite_ai.mind.dual_mind`)**:
    - Enhanced toggle oscillation detection to evaluate 24px coordinate clusters for mouse clicks and consecutive identical text submissions for typing, enforcing failure strikes to alert the escalation state machine when progress stalls.
  - **Rule 8 Grounding Alignment in Vision Tests (`tests/unit/vision/test_vlm_grounder.py`)**:
    - Aligned legacy mock coordinate `(260, 463)` in `test_vlm_grounder.py` with Rule 8 native screen pixels `(500, 500)`.
  - **Unit Test Health**:
    - Added 7 new unit tests across `test_uitars_parser.py`, `test_window_focus_and_navigation.py`, and `test_modal_and_menu_recovery.py`.
    - Certified 100% green pass rate across all 410 unit tests (`python scripts/test.py unit -q`) and all 71 integration tests (`python scripts/test.py integration -q`). Total active suite: 481 / 481 passing.

### Added - Stage P2.7: Visual Grounding Calibration, Window Chrome Snapping & Coordinate Alignment
- **Stint P2.7.3: Token Context Limit & Multimodal Server Flag Cleanup (`scripts/serve_llama.py`, `config.yaml`, `parasite_ai/config.py`, `parasite_ai/mind/brain_manager.py`, `run_benchmark_p2_6.bat`, `run_benchmark_p2_5.bat`, `run_benchmark_p2.bat`, `tests/unit/mind/test_llama_server.py`)**:
  - **Pruned Incompatible Multimodal `--cache-reuse` Flag**: Updated `scripts/serve_llama.py` and `parasite_ai/mind/brain_manager.py` to suppress passing `--cache-reuse` to `llama-server.exe` when vision projectors (`--mmproj`) are active or when `cache_reuse_tokens <= 0`, eliminating multimodal prompt cache warnings from server logs.
  - **Configuration Default Alignment**: Set `cache_reuse_tokens: 0` in `config.yaml`, `parasite_ai/config.py`, and `LocalBrainManager`, cleanly documenting that multimodal models handle KV state per frame without chunked prompt reuse.
  - **Context Window Verification**: Validated 8,192-token context window with `q8_0` KV cache (occupying only 238 MiB VRAM), accommodating native 1080p visual payloads (~3,011 tokens) with zero risk of context eviction during long episodes.
  - **Safety Message Normalization**: Replaced legacy "slamming cursor into a corner" guidance in benchmark runner scripts (`run_benchmark_p2_6.bat`, `run_benchmark_p2_5.bat`, `run_benchmark_p2.bat`) with accurate `<2ms` physical touch preemption (`InterruptGuard`) and `<5ms` emergency kill (`Ctrl+Alt+K`).
  - **Unit Test Health**: Added regression test asserting `--cache-reuse` omission for multimodal daemon configurations in `tests/unit/mind/test_llama_server.py`; validated 100% green test pass across all 145 active `tests/unit/mind/` unit tests.
- **Stint P2.7.2.2: Prompt De-Anchoring, Working Memory Generalization & Master Cadence Governance Integration (`parasite_ai.mind.uitars_parser`, `parasite_ai.mind.verifier`, `.agents/rules/engineering_cadence.md`, `AGENTS.md`, `GEMINI.md`, `tests/unit/mind/test_goal_verifier.py`, `run_smoke_probe_p2_7.bat`)**:
  - **Prompt De-Anchoring (Section 8 §3 Invariant)**: Replaced literal runtime coordinate and action examples (`Action: left_double(start_box='(520,340)')`, `hotkey(key='win r')`, `type(content='notepad\n')`) in `UITARS_SYSTEM_PROMPT` with abstract symbolic placeholders (`(x, y)`, `<keys>`, `<text>\n`). Eliminates numerical anchoring where the VLM repeated canned prompt coordinates into empty screen space.
  - **Working Memory Layout Generalization (Section 8 §4 Invariant)**: Purged hardcoded taskbar button offset calculations (`start_x = ml + 24`, `start_y = mt_mon + mh - 20`, and `| Start button at ({start_x}, {start_y})`) from `RuntimeGoalVerifier.build_working_memory_snapshot()`. Working memory now strictly reflects verified OS work area dimensions (`- Desktop Taskbar: Bottom strip (y={tb_top}..{tb_bot})`) without injecting synthetic button guesses.
  - **Engineering Cadence Generalization & Self-Audit Gate**: Systematically rewrote `.agents/rules/engineering_cadence.md` across Sections 1–8 to be completely general and free of specific task or coordinate anti-examples. Codified Section 8 §3 (*Zero Numerical Anchoring in Prompt Engineering*) and Section 8 §4 (*Zero Synthetic Layout Guessing in Working Memory*). Integrated a mandatory Cadence Self-Audit Gate into Section 2.
  - **Master Agent Instructions Integration**: Established permanent root governance files `AGENTS.md` and `GEMINI.md` binding all future agent sessions, tools, and subagents directly to the 8 invariant sections of `engineering_cadence.md`.
  - **Probe Tuning & Unit Test Certification**: Increased `L1-01` step cap in `run_smoke_probe_p2_7.bat` from 4 to 6 to permit full search flyout typing sequence. Certified 100% green pass rate across all 145 active `tests/unit/mind/` unit tests.
- **Stint P2.7.2.1: Native Screen Pixel Contract & Core Heuristic De-Proliferation (`parasite_ai.mind.uitars_parser`, `parasite_ai.mind.verifier`, `parasite_ai.mind.memory`, `.agents/rules/engineering_cadence.md`, `tests/unit/mind/test_uitars_parser.py`, `tests/unit/mind/test_goal_verifier.py`, `tests/unit/mind/test_memory.py`, `tests/unit/mind/test_single_pass_cua.py`)**:
  - **Ratified Qwen2.5-VL Native Screen Pixel Contract (Rule 8 Amended)**: Formally amended Section 8 in `engineering_cadence.md` to align with UI-TARS 1.5's Qwen2.5-VL backbone architecture. Removed the legacy Qwen2-VL $[0..1000]$ normalization divisor from `parse_coordinates()`, parsing and clamping coordinates directly in physical screen pixels $[0..W-1, 0..H-1]$ without arithmetic distortion.
  - **Purged Core Heuristics (Rule 7 §3 Invariant)**: Completely eliminated hardcoded Win32 title bar geometry and close button calculation offsets (`close_x = min(wr - 20, ...)`) and `to_norm()` from `RuntimeGoalVerifier.build_working_memory_snapshot()`, restoring visual autonomy to the VLM.
  - **Prompt & History Alignment**: Updated `UITARS_SYSTEM_PROMPT` to instruct native screen pixels `(0, 0)` to `(screen_width, screen_height)`. Stripped `[norm=...]` annotations from `EpisodicMemory.format_context_for_prompt()`.
  - **Unit Test Certification**: Updated unit tests across parser, verifier, memory, and single-pass CUA modules; certified 100% green pass rate across 145 active tests.
- **Stint P2.7.1: Native 1080p Visual Encoding & Window Geometry Injection (`parasite_ai.mind.brain_manager`, `parasite_ai.mind.verifier`, `tests/unit/mind/test_goal_verifier.py`, `tests/unit/mind/test_single_pass_cua.py`)**:
  - Upgraded CUA screenshot encoding in `LocalBrainManager.generate_cua_step()` from `max_dim=1280, quality=85` to native `max_dim=1920, quality=90`. Eliminates downscaling blur on Monitor 1 ($1920 \times 1080$), providing crisp $1:1$ visual pixel representation to UI-TARS.
  - Enriched `RuntimeGoalVerifier.get_live_windows()` to query `user32.GetWindowRect(hwnd)` and return physical screen bounding boxes `(left, top, right, bottom)` for all active top-level windows.
  - Upgraded `RuntimeGoalVerifier.build_working_memory_snapshot()` to inject physical active window bounding rectangles: `Active Window: <title> (<proc>) [Bounds: x=left, y=top, w=width, h=height]`.
  - Added deterministic window chrome title bar guidance and close button ('X') coordinate anchors into working memory (`Window Title Bar: y=top..top+32 | Close Button ('X') at (close_x, close_y)`).
  - Added physical taskbar geometry anchors into working memory: `- Desktop Taskbar: Bottom strip (y=1040..1080 | Start button at (24, 1060))`.
  - Added unit test coverage for native 1080p frame encoding (`test_generate_cua_step_native_1080p_encoding`) and window geometry / taskbar injection (`test_build_working_memory_snapshot_window_geometry_and_taskbar`), maintaining 100% test suite health.

### Added - Stage P2.6: Local Context & Working Memory Optimization
- **Stint P2.6.4: Shell Flyout Focus Guard & `baseline_p2_6` Benchmark Certification (`parasite_ai.mind.dual_mind`, `benchmarks/verifiers`, `benchmarks/run_benchmark`, `run_benchmark_p2_6.bat`, `tests/unit/mind/test_window_focus_and_navigation.py`)**:
  - Implemented shell flyout and popup menu preservation in `ActionDispatcher._activate_target_window_if_needed()`, preventing background `SetForegroundWindow` calls when an open Start Menu (`OpenShell.CMenuContainer`, `DV2ControlHost`, `Windows.UI.Core.CoreWindow`), Search flyout, or context menu (`#32768`) holds focus.
  - Added bottom taskbar strip coordinate guard (`y >= 1032`) preventing clicks targeting taskbar controls from activating background application windows behind the taskbar.
  - Implemented Monitor 1 workspace cleanup and isolation in `benchmarks.verifiers.cleanup_benchmark_processes()`, dismissing leftover Explorer windows/dialogs, minimizing non-target third-party windows on Monitor 1 only (`0 <= center_x < 1920`), and foregrounding pre-opened Notepad windows.
  - Added engineering cadence rule Section 6 mandating root batch scripts for live benchmarks; created `run_benchmark_p2_6.bat`.
  - Executed certified 20-task benchmark: **5.0% Pass Rate** (`L1-09` Launch File Explorer newly verified passed), **0.0% False-DONE Rate** (0 occurrences across 20 tasks), **3.545s median step latency** (-2.44s vs P0), **0 MB added hardware cost**, and 100% green active test suite (471/471 passed). Documented full findings in `benchmarks/results/stage_p2_6_postmortem.md` and `baseline_p2_5_vs_baseline_p2_6.md`.
- **Stint P2.6.3: Zero-VRAM CPU Working Memory & Sub-Goal Checklist (`parasite_ai.mind.verifier`, `parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `tests/unit/mind/test_goal_verifier.py`, `tests/unit/mind/test_single_pass_cua.py`)**:
  - Implemented fast `<3ms` CPU working memory generator `RuntimeGoalVerifier.build_working_memory_snapshot()` querying active foreground window, open applications, blocking `#32770` modal dialogs, live Notepad buffer text via `WM_GETTEXT`, and clipboard text with 0 MB added VRAM.
  - Added automated `[x]`/`[ ]` sub-goal checklist generation in working memory snapshots for compound goals (window launches/closes/minimizes, text/arithmetic typing, clipboard operations, file save/rename/folder creation, dialog dismissals).
  - Optimized `read_notepad_buffer()` with `allow_uia_fallback=True` to immediately return empty or valid text from Win32 `Edit` handles without falling through to slow UIA walks.
  - Injected `Current OS Working Memory` snapshot into `LocalBrainManager.generate_cua_step()` in prefix-stable ordering (`Task` -> `Recent History` -> `Working Memory` -> `Instruction`), preserving contiguous KV prefix cache reuse.
  - Added unit tests for multi-app working memory checklists, file save / modal dialog states, and prefix-stable prompt ordering; certified 100% green pass across 469 active tests.
- **Stint P2.6.2: Semantic Episodic Ledger & State Delta Tracking (`parasite_ai.mind.memory`, `parasite_ai.mind.dual_mind`, `tests/unit/mind/test_memory.py`)**:
  - Enriched `StepRecord` and `EpisodicMemory.record_step()` with backward-compatible `pre_window`, `post_window`, and `screen_size` fields.
  - Implemented rolling milestone compression in `EpisodicMemory.format_for_prompt()` for steps older than the recent detailed window (`n`), summarizing early task steps into a single-line `- Completed Milestones (Steps #1-#X): ...` header to ensure early setup steps (e.g. app launching or clipboard copying) are never forgotten.
  - Added dual normalized `[0..1000]` coordinate formatting alongside pixel coordinates (`at (cx, cy) [norm=(norm_x, norm_y)]`) to enable direct visual-spatial correlation with UI-TARS output space.
  - Added OS active window transition delta tracking (`| Window: {pre_window} -> {post_window}`) and concise agent rationale (`| Thought: "..."`) to recent history formatting in prompt context.
  - Updated `DualMindPipeline.step()` to safely capture pre-dispatch and post-settle window titles/processes via `_format_window_label()` and snap coordinates to UI element metadata.
  - Added dedicated unit tests validating coordinate normalization, thought inclusion, window transition deltas, and milestone compression; verified 100% green pass across 466 active tests.
- **Stint P2.6.1: Quantized KV Cache (`q8_0`), Context Expansion (8,192 Tokens) & Prefix-Stable Prompt Ordering (`parasite_ai.config`, `config.yaml`, `parasite_ai.mind.brain_manager`, `scripts/serve_llama.py`)**:
  - Expanded `LocalModelConfig.context_size` default from `4,096` to `8,192` tokens and added `kv_cache_type_k: "q8_0"`, `kv_cache_type_v: "q8_0"`, and `cache_reuse_tokens: 256` configuration settings.
  - Configured `LlamaServerBackend` to launch `llama-server.exe` with `-c 8192 -ctk q8_0 -ctv q8_0 --cache-reuse 256`, cutting per-token KV memory in half (`~29.75 KB/token`) and doubling the usable context window at only `~238 MiB` KV cache memory (`+14 MiB` net delta vs. FP16 4k), strictly adhering to Invariant D1 (`6,500 MB` VRAM budget).
  - Implemented prefix-stable multimodal payload ordering in `LlamaServerBackend.generate()` and `OpenAIEndpointBackend.generate()` by placing `{"type": "text"}` before `{"type": "image_url"}` in the `user` message array, ensuring the invariant prefix tokens (`System Prompt` + `Task` + `History`) form a contiguous prefix before the dynamic per-frame screenshot tail.
  - Implemented prefix-stable prompt assembly in `LocalBrainManager.generate_cua_step()`, positioning static `Task: {user_goal}` first, followed by append-only `Recent History`, then action instructions.
  - Added CLI flags (`-ctk`, `-ctv`, `--cache-reuse`, `--ctx-size 8192`) to `scripts/serve_llama.py` with verified warm-up inference (`0.700s` text, `1.712s` vision smoke).
  - Validated 100% green test pass across 464 active unit and integration tests (`tests/unit/mind/test_llama_server.py`, `tests/unit/mind/test_single_pass_cua.py`).

## [0.3.5] - 2026-11-10: Stage P2.5 (Intermediary Housecleaning, Focus Stabilization & `baseline_p2_5` Certification)

### Certified Benchmark Baseline (`baseline_p2_5`)
- Executed all 20 canonical Windows 10 benchmark tasks on host desktop with persistent `llama-server.exe` daemon.
- **False-`DONE` Rate:** **0.0%** (0 occurrences across 20 tasks, maintaining strict objective integrity).
- **Median Step Latency:** **3.592s** (-2.39s faster than P0, -0.29s faster than P2).
- **P90 Step Latency:** **4.361s** (-5.44s faster than P0, -0.88s faster than P2).
- **Mean Task Duration:** **29.3s** (-10.0s faster than P0, -3.0s faster than P2).
- **Hardware Interrupts:** **0** (eliminated all mouse/cursor fighting and self-preemptions).
- **Cold-Start Latency:** **0ms** (persistent VLM server).
- Documented complete findings in `benchmarks/results/stage_p2_5_postmortem.md` and delta scorecards against P2 and P0.

### Added - Stage P2.5: Housecleaning, Focus Stabilization & Custom Shell Navigation (2026-11-09 - 2026-11-10)
- **Win32 Window Focus Activation Guard (`parasite_ai.mind.dual_mind`, `tests/unit/mind/test_window_focus_and_navigation.py`)**:
  - Implemented `ActionDispatcher._activate_target_window_if_needed(coords, target_hwnd)` checking `GetForegroundWindow()` against the root window under cursor coordinates using Win32 `WindowFromPoint` and `GetAncestor(hwnd, GA_ROOT)`.
  - Automatically restores minimized windows via `ShowWindow(SW_RESTORE)` and brings target windows to foreground via `SetForegroundWindow`, `BringWindowToTop`, and Win32 `AttachThreadInput` fallback prior to dispatching mouse clicks (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`) or typing (`TYPE`, `CLICK_AND_TYPE`).
  - Safeguarded shell surfaces (`Progman`, `WorkerW`, `Shell_TrayWnd`) from auto-focus hijacking to preserve desktop shortcut and taskbar clickability.
- **Dynamic Menu Grounding & Canned Coordinate Purge (`parasite_ai.mind.uitars_parser`)**:
  - Completely purged legacy canned taskbar coordinates (e.g. `(24, 980)`) from `UITARS_SYSTEM_PROMPT` in accordance with Invariant D4.
  - Added dynamic menu visual navigation instructions: when a Start Menu, system tray, or application menu is already open, the agent must visually ground within the menu boundaries or type directly to filter, never re-clicking the toggle button.
- **Benchmark Neutral Cursor Park & Dry-Run Subprocess Acceleration (`benchmarks/run_benchmark.py`, `parasite_ai.main`)**:
  - Added `reset_cursor_to_neutral(target_x=960, target_y=540)` using Win32 `SetCursorPos` before task initialization and post-teardown to prevent cursor lingering over critical screen hotzones (e.g., Start button, close buttons).
  - Optimized `--dry-run` to default to `mock` brain mode when `--brain-mode` is omitted, eliminating 4GB GGUF VRAM allocations during rapid unit/CLI smoke tests (reducing dry-run startup from 5.4s to 1.28s).
- **Pruned Dead 3B Vision & Monologue Subsystems (Stint P2.5.1)**:
  - Pruned dead Set-of-Marks and foveated composite generator overhead in `parasite_ai/vision/foveated.py`.
  - Isolated the ~860-line legacy 3B thought monologue and brittle heuristic block in `parasite_ai/mind/dual_mind.py`.
  - Converted `ScreenGrounder` full desktop UIA scans to lazy evaluation, prioritizing active foreground window elements.

---

## [0.3.0] - 2026-11-08: Stage P2 (Thin Perception-to-Action Loop, Resilient CUA & Pre-DONE Verification)

### Added
- **Objective Pre-`DONE` Runtime Goal Verifier (`parasite_ai.mind.verifier`, `tests/unit/mind/test_goal_verifier.py`)**:
  - Implemented `RuntimeGoalVerifier` executing sub-5ms CPU-only Win32, filesystem, clipboard, and window state checks before accepting completion:
    - Verifies target file creation, rename integrity, and content containment.
    - Verifies application running state, minimized/active status (`IsIconic`), and modal error dialog (`#32770`) dismissal.
    - Directly inspects live Notepad `Edit` buffer via Win32 `WM_GETTEXT` for target greeting strings, arithmetic results, and non-prompt echoes.
  - Intercepts premature `ActionType.DONE` calls in `DualMindPipeline.step()`, converting invalid completion claims into `ActionType.WAIT(wait_ms=250, success=False)` with actionable diagnostic `[PRE-DONE VETO]` feedback.
- **Empirical 20-Task Benchmark Suite P2 (`run_benchmark_p2.bat`, `benchmarks/results/baseline_p2.json`, `benchmarks/results/baseline_p2.md`)**:
  - Executed full 20-task Windows 10 benchmark suite with zero operator interventions:
    - **First Ground-Truth Task Pass:** Task `L1-01` (Launch Notepad) achieved 100% objective pass in 4 steps (`18.956s`) via `Win+R` + `notepad` + `Enter`.
    - **False-`DONE` Hallucinations Eliminated:** Dropped from 20.0% (P0) and 5.0% (P1) down to **0.0% (0 / 20 tasks)**.
    - **Median Step Latency:** Dropped to **3.881s** (improved from 4.741s in P1 and 5.986s in P0, beating the Alpha Gate `<= 5.0s` target).
    - **P90 Step Latency:** Improved to **5.242s** (down from 9.798s in P0).

### Changed & Fixed
- **CUA Token Budget & Stop Sequence Fortification (`parasite_ai.mind.brain_manager`, `parasite_ai.mind.uitars_parser`)**:
  - Doubled CUA output generation budget from 128 to 256 tokens in `LlamaServerBackend.generate_cua_step()`, eliminating action truncation after long thought monologues.
  - Configured explicit stop sequences (`<|im_end|>`, `\nassistant`, `<|endoftext|>`), preventing trailing role token bleed.
  - Fortified `parse_uitars_action()` regex to handle unclosed parentheses, trailing role tokens, and unquoted parameter strings.
- **Decommissioned Legacy Heuristic Web & Caret Relaxation (`parasite_ai.mind.dual_mind`, `parasite_ai.ui.ghost_hud`)**:
  - Gated legacy 700-line 3B heuristic block behind `if not use_cua_single_pass:`, giving `UI-TARS-1.5-7B` direct perception-to-action authority.
  - Suppressed 47.9s external Chrome `BrowserOffloader` consultations during local CUA execution.
  - Relaxed pre-`TYPE` Win32 caret guard for Windows shell and UWP controls (`StartMenuExperienceHost.exe`, `SearchApp.exe`, `CalculatorApp.exe`).
  - Removed Set-of-Marks visual clutter while preserving the click-through `GhostHUD` reticle.
  - Enhanced episodic prompt history with `(Enter pressed)`, `(Enter NOT pressed)`, and `[NO SCREEN CHANGE]` guidance to prevent click oscillation loops.

---

## [0.2.0] - 2026-11-08: Stage P1 (Local CUA Engine Upgrade — UI-TARS-1.5-7B & Persistent llama-server)

### Added
- **Out-of-Process Persistent CUDA `llama-server.exe` Infrastructure (`parasite_ai.mind.brain_manager`, `scripts/serve_llama.py`)**:
  - Integrated persistent CUDA `llama-server.exe` (`b12188`) supervisor with zero-overhead `0ms` warm attach across tasks and subprocesses.
  - Locked execution parameters to single-slot KV cache (`-np 1`), `-c 4096`, and `--image-min-tokens 1024` for deterministic latency.
  - Verified host GPU governance: `UI-TARS-1.5-7B.IQ4_XS.gguf` (`4.25 GB`) + `mmproj-Q8_0.gguf` (`856 MB`) running strictly within the 6,500 MB RTX 4060 VRAM budget.
  - Added unit test stub guards (`< 10 MB` file size check and `PYTEST_CURRENT_TEST` detection) to prevent test runners from spawning GPU server processes on dummy GGUFs.
- **Native `UI-TARS` Action Parser & Grounding (`parasite_ai.mind.uitars_parser`)**:
  - Implemented `parse_uitars_action()` parsing `Thought:` and native `Action:` formats (`click`, `left_double`, `right_single`, `type`, `hotkey`, `scroll`, `wait`, `finished`).
  - Added `[0..1000]` normalized coordinate scaling to native monitor pixels with hybrid UIA element snapping.
  - Added `ActionPlan._coerce_null_fields` verb recovery mapping legacy/synonym verbs (`SELECT*` -> `CLICK`, `PRESS` -> `HOTKEY`, `FINISH` -> `DONE`).
- **Single-Pass CUA Cognitive Loop (`parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`)**:
  - Consolidated dual-pass prompt generation (Pass 1 persona monologue + Pass 2 action JSON) into a single multimodal inference pass (`generate_cua_step()`), cutting cognitive latency in half.
  - Excluded `CompanionDock` overlay geometry and current process ID (`os.getpid()`) from UI grounding to prevent self-clicking loops.
  - Hardened `PrecisionAppMatcher.score_match()` against symbol/domain collisions (`Notepad++` vs `Notepad` = `0.0`, `paint.net` vs `Paint` = `0.0`).
- **4-Tier Modular Test Suite Architecture (`scripts/test.py`, `pyproject.toml`)**:
  - Restructured entire test suite into 4 clean tiers:
    - **Tier 1 (Unit):** Fast mocked unit tests (`tests/unit/`).
    - **Tier 2 (Integration):** Multi-component integration tests (`tests/integration/`).
    - **Tier 3 (Archive):** Historical stress/milestone suites (`tests/archive/`).
    - **Tier 4 (Live OS):** Live desktop actuation tests (`tests/live_os/`).
  - Built unified test CLI runner `scripts/test.py` with tier and domain filtering (`765 / 765` tests passing in `74.8s`).
- **Stage P1 Benchmark Suite & Comparative Scorecard (`run_benchmark_p1.bat`, `scripts/compare_benchmarks.py`)**:
  - Recorded `baseline_p1.json` and generated 3-way comparative scorecard (`baseline_p0_vs_baseline_p1.md`).
  - Dropped cold-start timeouts from 5 to 0, eliminated unhandled enum crashes (2 to 0), and reduced median step latency from `5.986s` to `4.741s`.

---

## [0.1.5] - 2026-11-07: Stage P0 (Measure, De-Hardcode & Baseline Benchmark)

### Added
- **Standardized 20-Task Windows 10 Benchmark Harness (`benchmarks/`)**:
  - Built declarative benchmark specification (`benchmarks/suite.yaml`) spanning Level 1 (Basic OS tasks), Level 2 (Multi-step dialogs), and Level 3 (Complex workflows).
  - Implemented independent ground-truth verifiers (`benchmarks/verifiers.py`) validating actual OS state via Win32 API, filesystem, and clipboard without trusting agent self-reports.
  - Built automated runner `benchmarks/run_benchmark.py` with timeout handling and telemetry capture.
- **Episode Telemetry Receipts & Deterministic Process Exits (`parasite_ai.mind.memory`, `parasite_ai.main`, `parasite_ai.runtime`)**:
  - Created `EpisodeReceipt` Pydantic model tracking per-step latencies (`grounding_ms`, `llm_pass1_ms`, `llm_pass2_ms`, `actuation_ms`), strike counts, terminal reasons, and full action traces.
  - Added CLI flag `--episode-report <path.json>` and deterministic exit codes (`0` for verified `DONE`, `1` for timeouts/aborts/errors).
- **GPU Governance Verification Harness (`scripts/check_gpu_governance.py`)**:
  - Added WDDM GPU memory check verifying dedicated VRAM usage vs. shared sysmem fallback to guarantee sub-50ms token generation.
- **Baseline P0 Benchmark Benchmark Run (`benchmarks/results/baseline_p0.json`, `benchmarks/results/baseline_p0.md`)**:
  - Recorded empirical baseline on legacy `Qwen2.5-VL-3B`: 5.0% overall pass rate, 20.0% false-`DONE` rate, 5 cold-start timeouts, and 5.986s median step latency.

### Changed & Fixed
- **De-Hardcoded Core Engine & Stripped Canned Overrides (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.brain_manager`)**:
  - Removed canned introduction override (`"Hello! I am Parasite..."`) from `DualMindPipeline.step()`, requiring the model to generate real content.
  - Stripped app-specific literals and game allowlists (`"warsim"`, `"rift wizard"`, `"steam"`, `"epic games"`) from core cognitive modules, shifting to structural UIA window classification.
  - Aligned VRAM ceiling to `6500 MB` and operator pause duration to `2.5s` across `config.yaml`, `config.py`, and project documentation.

---

## [0.1.1] - 2026-11-02: Local Multimodal VLM & RapidOCR Grounding Wire-Up

### Added
- **End-to-End Local VLM (`Qwen2.5-VL-3B-Instruct-GGUF` + `mmproj`) Wiring (`parasite_ai.vision.foveated`, `parasite_ai.vision.vlm_grounder`, `parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.config`, `config.yaml`)**:
  - **Multimodal `LlamaCppBackend` (`MTMDChatHandler` / `Qwen25VLChatHandler`)**: Updated `LlamaCppBackend` (`brain_manager.py`) to accept `mmproj_path`, auto-discover companion `mmproj-*.gguf` vision projectors on disk, initialize `MTMDChatHandler` (with fallback to `Qwen25VLChatHandler`), expose `supports_vision()`, and format `image_base64` payloads into multimodal `image_url` + `text` chat messages.
  - **Curated VLM + `mmproj` Dual-File Downloader**: Added `ggml-org/Qwen2.5-VL-3B-Instruct-GGUF` (`Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf`) to `CURATED_MODELS` and `config.yaml`, and updated `LocalBrainManager.start_download()` to automatically download and GGUF-verify both the main VLM weights and the companion `mmproj` vision projector.
  - **Set-of-Mark Foveated VLM Composite (`FoveatedVisionEngine.build_vlm_composite`)**: Added `encode_image_to_data_uri()` and `build_vlm_composite()` in `foveated.py` to overlay `[#ID]` badges onto the active-window foveal crop (or macro desktop overview) and encode it to a `640px` base64 JPEG data URI.
  - **Closed-Loop Pipeline Integration (`DualMindPipeline.step`)**: Wired `FoveatedVisionEngine` and `VLMGrounder` into `DualMindPipeline` (`dual_mind.py`) so both Pass 1 (`generate_thought`) and Pass 2 (`generate_action`) receive the live annotated visual frame (`image_base64`), and integrated `VLMGrounder` coordinate parsing (`<|box_start|>`, `<|coord_start|>`, `[ymin, xmin, ymax, xmax]`) and hybrid UIA element snapping in Step 4a.

### Fixed
- **Console/Custom-Rendered Window OCR Grounding, Already-Open Target Focus, & Gameplay Completion Guards (`parasite_ai.vision.grounding`, `parasite_ai.mind.resolver`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.main`, `config.yaml`)**:
  - **Fix 1 — Console/Custom-Window Scoped RapidOCR & Container Deduplication (`grounding.py`, `config.yaml`)**:
    - Enabled `ocr_scoped_only: true` in `config.yaml` so RapidOCR crops directly to the active window rectangle rather than scanning all 100 desktop shortcuts.
    - Excluded OS window chrome and scrollbar pseudo-buttons (`Page down`, `Line down`, `Minimize`, `Maximize`, `Close`, `System`, `Text Area`) from `active_uia_count` so console (`conhost.exe`) and custom-rendered game windows always trigger Scoped RapidOCR (`active_uia_count == 0 < 6`), and filtered scrollbar buttons out of the Set-of-Mark list.
    - Fixed `_deduplicate_and_merge()` so full-window container UIA elements (`Document "Text Area"`, `Pane`, `Window`, or `uia_area > 6 * ocr_area`) no longer swallow contained OCR text lines during `compute_containment` deduplication.
    - Promoted open target windows matching `goal_keywords` to the active window root when OS foreground is `Program Manager` or `ParasiteAI Launcher`.
  - **Fix 2 — Already-Open Window Focus, Console Keyboard Interaction, & Conversational Suffix Stripping (`resolver.py`, `dual_mind.py`)**:
    - Stripped trailing conversational clauses (`"on your own"`, `"without my input"`, `"by yourself"`, etc.) in `UniversalAppResolver.extract_target_app()` and stripped Windows Taskbar running-window suffixes (`"- 1 running window"`) in `PrecisionAppMatcher.score_match()`.
    - Added Tier 0 already-open window detection in `UniversalAppResolver.resolve_launch_action()` and Section 3c/3d in `DualMindPipeline.step()` so when the target application window is already open on screen, the agent focuses it instead of re-double-clicking the desktop shortcut or toggling its taskbar button.
    - Added console (`conhost.exe`) interaction handling that focuses the console window via `SetForegroundWindow`, converts mouse clicks on OCR text/menus into keyboard input (`TYPE` option number + `Enter`, or `HOTKEY ["enter"]`) to avoid Windows QuickEdit selection pauses, and exempts console hosts from Win32 `GUITHREADINFO` caret verification.
  - **Fix 3 — Open-Ended Gameplay Step Completion Guard & Automatic Timestamped Log Archiving (`plan.py`, `dual_mind.py`, `main.py`)**:
    - Updated `verify_step_completion()` (`plan.py`) and Section 2 (`dual_mind.py`) so open-ended gameplay/autonomous interaction goals (`"play ..."`, `"on your own"`, `"without my input"`) require at least 3 in-app interaction steps before marking `StepIntent.NAVIGATE` as `COMPLETED` or accepting `ActionType.DONE`.
    - Updated `setup_logging()` (`main.py`) to automatically archive any existing non-empty `logs/parasite_debug.log` to a timestamped file (`logs/parasite_debug<HHMMam/pm>.log`) on startup.
- **Pydantic Null-Field Coercion, CompanionDock Full Collapse Evasion, & Taskbar/Window Hijack Guards (`parasite_ai.mind.memory`, `parasite_ai.mind.brain_manager`, `parasite_ai.ui.companion_dock`, `parasite_ai.ui.bridge`, `parasite_ai.mind.dual_mind`)**:
  - Coerced null fields emitted by small local models to valid defaults.
  - Implemented collapsible `body_container` in `CompanionDock` and Win32 coordinate auto-evasion to prevent target icon occlusion.
  - Normalized taskbar double clicks to single click window activations.

### Added
- **Left-Monitor Vision & Actuation Lock & Continuous Iteration CLI Harness (`parasite_ai.config`, `parasite_ai.vision.capture`, `parasite_ai.vision.grounding`, `parasite_ai.mind.dual_mind`, `parasite_ai.runtime`, `parasite_ai.main`)**:
  - **Left-Monitor Scoping (`monitor_index: 1`)**: Added `VisionConfig.monitor_index` (default `1` — Left/Primary Monitor `0 <= x < 1920, 0 <= y < 1080`) and `get_monitor_bounds(monitor_idx)` in `capture.py`.
  - **UIA & OCR Monitor Bounding Filter**: Updated `ScreenGrounder` (`grounding.py`) to filter out top-level windows, UIA child controls, and OCR boxes whose centers fall outside the target monitor (`x >= 1920`), and tracked `_last_active_win_rect` so `DualMindPipeline._get_effective_active_window()` resolves the topmost window on the Left Monitor even when OS keyboard focus rests on the Right Monitor (e.g., Antigravity IDE or Discord).
  - **Actuation Coordinate Guard**: Updated `ActionDispatcher.validate_coordinates()` (`dual_mind.py`) to reject any mouse click/move coordinates outside the configured monitor bounds (`0 <= x < 1920, 0 <= y < 1080`).
  - **Continuous Automatic Iteration CLI Flags**: Added `--monitor-index`, `--auto-exit-on-complete`, and `--max-steps` CLI flags (`main.py`, `runtime.py`) so Antigravity can launch bounded single-episode test runs, inspect `logs/parasite_debug.log` on exit, patch bugs, and re-run autonomously.
- **Intermediate Platform Launcher & Steam Launch Options Handling (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.vision.grounding`, `parasite_ai.mind.brain_manager`, `parasite_ai.config`)**:
  - **Foreground-Scoped OCR Trigger**: Updated `ScreenGrounder.extract_elements()` to evaluate `active_uia_count` (UIA controls in the active foreground window) rather than total desktop UIA count so custom-rendered windows (such as Steam's `steamwebhelper.exe` Launch Options dialog or OpenGL/DirectX game menus) automatically trigger scoped RapidOCR even when 100+ background desktop icons exist.
  - **Intermediate Launcher Detection (`is_intermediate_launcher_window`)**: Added detection for game platform launchers and launch-options modals (`steam.exe`, `steamwebhelper.exe`, `epicgameslauncher.exe`, `riotclientservices.exe`, `"Launch Options"`) so `DualMindPipeline.step()` and `verify_step_completion()` do not prematurely declare victory (`DONE`) when a game's Launch Options dialog appears, instead clicking `"Play"` / `"Launch"` or pressing `Enter` until the actual game window launches.
  - **Hotkey `#ID` & Single-Letter Desktop Hotkey Sanitization**: Removed `"or hotkey"` from the Pass 1 `DECISION` prompt, added automatic conversion of `HOTKEY ["#<id>"]` to `CLICK` on `target_id=<id>`, redirected bare single-character desktop hotkeys (like `HOTKEY ["r"]`) to `resolve_launch_action()`, and extended the oscillation detector to catch repeated `HOTKEY` and `MINIMIZE_WINDOW` loops.
  - **Desktop Shortcut Minimize Guard & Context Menu Dismissal**: Prevented `MINIMIZE_WINDOW` from calling `ShowWindow(SW_MINIMIZE)` on the Windows Desktop (`Progman`/`WorkerW`) or targeting the target app's desktop shortcut, and added automatic `Esc` dismissal of stray desktop right-click `"Context"` menus before double-clicking desktop icons.
  - **Contingency Step Return to Paused Step (`LivingPlan.advance_step`)**: Fixed `check_and_insert_contingencies()` and `LivingPlan.advance_step()` so completing a stagnation contingency step returns execution to the paused `Step 1 (LAUNCH_OR_ACTIVATE)` rather than skipping ahead to `CONCLUDE`.
  - **Log Cycling**: Cycled `logs/parasite_debug.log` to `logs/parasite_debug1224pm.log`.
- **Dynamic Perception & Reasoning Upgrades (Stage 1) (`parasite_ai.vision.grounding`, `parasite_ai.mind.resolver`, `parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.main`)**:
  - **Spaceless & Compound Fuzzy Grounding**: Added normalized spaceless/compound token matching (`re.sub(r"[^a-z0-9\+#]", "", ...)`) in `ScreenGrounder` and `PrecisionAppMatcher.score_match()` so compound queries like `"riftwizard"` match desktop icons like `"Rift Wizard 2"` (`score=0.88`, `is_goal_match=True`).
  - **Pass 1 Background/Desktop Target Visibility & Structured Self-Critique**: Enriched `ScreenGrounder.format_concise_scene_summary()` to surface top background/desktop `[#ID]` targets to Pass 1, and updated Pass 1 (`generate_thought` and `PersonaConfig.system_prompt`) to emit structured `<thought>` blocks (`OBSERVATION`, `CRITIQUE`, `DECISION` with `[#ID]`) before 1-sentence character speech.
  - **Semantic `MINIMIZE_WINDOW` / `CLOSE_WINDOW` Target Validation**: Updated `ActionDispatcher.dispatch()` so if the LLM passes a non-button or wrong element `target_id` (such as `Document "Text Area"`) for `MINIMIZE_WINDOW` or `CLOSE_WINDOW`, it automatically resolves the actual `"Minimize"` or `"Close"` `Button` belonging to that window instead of clicking inside the window body.
  - **Child-Element Error Dialog Detection (`is_error_dialog_window`)**: Added inspection of grounded child `Text`/`Dialog` elements (e.g. `"Windows cannot find 'riftwizard'..."`) in addition to window titles, preventing `DualMindPipeline.step()` and `verify_step_completion()` from mistaking an `explorer.exe` launch error modal for the target application.
  - **Removed Brittle Thought Regex Overrides**: Removed `extract_target_app(persona_out.thought)` fallback and hardened `UniversalAppResolver.extract_target_app()` to ignore window-closing/minimizing goals (`"close ..."`, `"minimize ..."`) and conversational prepositions (`"start with ..."`).
  - **Log Noise Suppression & Cycling**: Suppressed `comtypes` DEBUG log flooding in `setup_logging()` and cycled `logs/parasite_debug.log` to `logs/parasite_debug1207pm.log`.
- **Companion Dock Window Controls (`parasite_ai.ui.companion_dock`, `parasite_ai.ui.bridge`, `parasite_ai.main`)**:
  - Added **Minimize (`—` / `□`)** and **Close (`✕`)** buttons to `CompanionDock`'s top-right header bar (`BtnMinimize` and `BtnClose`).
  - Added `minimize_dock()`, `restore_dock()`, `toggle_minimize_dock()`, `close_dock()`, and `evade_coordinates()` slots on `CompanionDock`, plus `minimize_dock()` and `restore_dock()` signals on `UIBridge`.
  - Connected `sig_close_requested` to `ParasiteApp._on_dock_close_requested` for clean application shutdown when the Close button is clicked.
- **Self-Occlusion Auto-Evasion (`parasite_ai.mind.dual_mind`, `parasite_ai.ui.companion_dock`)**:
  - Added `ActionDispatcher._evade_companion_dock_if_needed()` and `get_companion_dock_rect()` to detect when a click/double-click target (such as a desktop icon like `"Rift Wizard 2"` at `(1732, 528)`) overlaps `CompanionDock`'s own geometry, automatically collapsing and shifting the dock out of the way before clicking.
- **Window Lifecycle Evaluation — Minimize ("Need Soon") vs. Close ("Don't Need Anytime Soon") (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.memory`, `parasite_ai.mind.brain_manager`)**:
  - Added `ActionType.MINIMIZE_WINDOW` and `ActionType.CLOSE_WINDOW` to `ActionType` and `ActionDispatcher.dispatch()`.
  - Added deterministic `evaluate_window_disposition(window_title, process_name, user_goal, target_app)` classifying open windows into `"TARGET"`, `"NEED_SOON_MINIMIZE"` (persistent workspaces, IDEs, browsers, Steam, Discord, ParasiteAI Launcher), and `"DONT_NEED_CLOSE"` (modal error dialogs, stray File Explorer folder views, finished temporary utilities like Notepad/Calculator).
  - Updated `DualMindPipeline.step()` to automatically close `"DONT_NEED_CLOSE"` windows and minimize `"NEED_SOON_MINIMIZE"` windows when they obstruct desktop targets or intercept focus.

### Fixed
- **Browser Offloader Demo Chip Click & Screen-Center Clicking Loop (`parasite_ai.mind.offloader`)**:
  - Hardened `BrowserOffloader._find_prompt_target()` to strictly disqualify `Button`, `Hyperlink`, `ListItem`, `MenuItem`, and long sentence elements so Gemini starter/demo question chips are never clicked as the prompt input box.
  - Updated fallback prompt coordinate to `rect[3] - 68` (bottom input bar, below center-screen suggestion chips) and added `force_ocr=True` retry when Chrome exposes fewer than 3 UIA elements.
  - Added window title check (`get_window_title`) to skip redundant `Ctrl+L` URL re-navigation when Chrome is already on the target web AI tab.
  - Removed the blind `mouse_driver.click(prompt_x, prompt_y - 200)` fallback inside `trigger_copy()` that repeatedly clicked the center of the screen every 0.5s while polling for a response.

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

### Fixed
- Fixed crowded desktop UIA truncation and occlusion dropping target application shortcuts (`parasite_ai.vision.grounding`):
  - Raised desktop sibling capacity to 250 elements for explorer windows (`Program Manager`, `WorkerW`, `Desktop`).
  - Added in-flight keyword preservation during accessibility tree walks so items matching user goal keywords are never dropped by per-window limits or `is_occluded` bounding box checks.
  - Deduplicated child `TextControl` and `ImageControl` sub-nodes under desktop `ListItemControl` nodes to eliminate element slot bloat.
- Fixed Run dialog (`Win+R`) multi-word failure and modal error dialog loop (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.resolver`):
  - Added auto-dismissal for Windows modal error dialogs (`Windows cannot find '...'`) via Enter/Esc to prevent UI deadlock.
  - Automatically dismisses Run dialog and falls back to Windows Start Search when target application names contain spaces (e.g. `"rift wizard"`).
  - Upgraded desktop shortcut launching to `DOUBLE_CLICK`, and added active window obscuration detection with `Win+D` desktop reveal.
  - Fixed File Explorer folder search box hijack: restricted Start Search detection to system search hosts (`SearchApp.exe`, `SearchHost.exe`, `StartMenuExperienceHost.exe`, and taskbar explorer windows).
  - Added support for `"play"`, `"play some"`, and `"play the game"` in `UniversalAppResolver.extract_target_app` with a generic word blacklist (`"games"`, `"app"`, etc.).
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
- Document Content Typing and Stream-of-Consciousness Isolation (`parasite_ai.mind.dual_mind`): Isolated avatar persona monologue speech/thought from physical document typing. Persona thoughts are strictly forbidden from being injected into `action_plan.text`. Added support for goal intent keywords (`intro`, `introduction`, `introduce`) to type canonical companion introduction (`"Hello! I am Parasite, an autonomous desktop companion."`) and suppress premature enter keys (`submit=False`).
- Menu Bar & Interactive Control Typing Protection (`parasite_ai.mind.dual_mind`): Prevented `CLICK_AND_TYPE` from typing document content into non-text controls (`MenuItem`, `Button`, `TabItem`, `ScrollBar`). If an editor canvas (`Document`/`Edit`) is not in the grounded elements list, redirected target to the active window's client center to safely focus the document canvas instead of triggering menu accelerators or File/Save dialogs.
- Pass 2 Active Step Awareness (`parasite_ai.mind.dual_mind`): Prefixed `persona_intent` with active plan step description (`Active Step: ...`) so local LLM does not repeat application launch actions when target application is already active.
- Human Interrupt Recovery Latency (`parasite_ai.config`, `parasite_ai.safety.interrupt_guard`): Reduced `override_pause_duration_sec` from 10.0s down to 2.5s for fast control yield and recovery.
- Browser Offloader Full-Viewport Container Filtering (`parasite_ai.mind.offloader`): Filtered out full-page document wrappers from prompt target localization, preventing dead-center clicks into blank web page space.
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
