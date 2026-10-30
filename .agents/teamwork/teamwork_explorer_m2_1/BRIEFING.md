# BRIEFING — 2026-10-29T12:50:00Z

## Mission
Analyze, architect, and specify the Safety Subsystem (InterruptGuard and WindowGuard) for ParasiteAI Milestone M2.

## 🔒 My Identity
- Archetype: explorer
- Roles: explorer, investigator, synthesizer
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M2 — Safety & Physical Input Layer

## 🔒 Key Constraints
- Read-only investigation — do NOT implement production code
- Write only to working directory g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\
- Provide exact class definitions, method signatures, ctypes struct layouts, ctypes calling conventions (WINFUNCTYPE), test specifications, and deterministic simulation harness
- Deliver plan.md and handoff.md, notify orchestrator via send_message

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T12:40:48Z

## Investigation State
- **Explored paths**:
  - `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md`
  - `g:\__Docs\ParasiteAI\parasite_ai\config.py` (SafetyConfig)
  - `g:\__Docs\ParasiteAI\pyproject.toml`
  - Win32 API ctypes verification: `MSLLHOOKSTRUCT`, `KBDLLHOOKSTRUCT`, `HOOKPROC`, `user32`, `kernel32`, `winmm`
  - Cross-thread latency benchmarking: `threading.Event` wake latency measured at ~0.055ms
  - Foreground window inspection verification: `GetForegroundWindow`, fail-safe `hwnd==0`
- **Key findings**:
  - `MSLLHOOKSTRUCT` size is exactly 32 bytes on x64, with `flags` at offset 12 and `dwExtraInfo` at 24.
  - `KBDLLHOOKSTRUCT` size is exactly 24 bytes on x64, with `flags` at offset 8 and `dwExtraInfo` at 16.
  - Injected flags: `LLMHF_INJECTED = 0x01`, `LLKHF_INJECTED = 0x10`. Physical hardware events have bit 0 (mouse) or bit 4 (keyboard) unset.
  - Dedicated hook thread must call `PeekMessageW` prior to signaling ready to guarantee message queue creation for `PostThreadMessageW(WM_QUIT)`.
  - Callback function pointers must be saved as attributes on `self` to prevent Python garbage collection causing ACCESS_VIOLATION.
  - `threading.Event` wakes in 0.055ms, 36x faster than the 2.0ms budget.
  - Sliding cooldown state machine extends timer to 10.0s on each physical touch and auto-re-arms after silence.
  - `WindowGuard` enforces `hwnd == 0 -> is_sensitive = True` and `OpenProcess failed -> is_sensitive = True` fail-safes.
- **Unexplored areas**: None for Safety Subsystem; hands kinematics and keyboard driver delegated to m2_2 and m2_3.

## Key Decisions Made
- Architecture of `InterruptGuard`: Dedicated message pump thread with `timeBeginPeriod(1)`, sub-microsecond callback, `threading.Event` token, sliding cooldown with background re-arm timer, and `simulate_event` deterministic harness.
- Architecture of `WindowGuard`: Multi-layered inspection combining window title, process image name, elevated console detection, and `hwnd == 0` / Access Denied fail-safe defaults.
- Delivered comprehensive implementation plan in `plan.md` and 5-component handoff report in `handoff.md`.

## Artifact Index
- plan.md — Complete technical implementation plan for Worker
- handoff.md — 5-component handoff report for Worker and Orchestrator
- progress.md — Liveness heartbeat and milestone progress
- DISPATCH.md — Agent dispatch instructions and history
