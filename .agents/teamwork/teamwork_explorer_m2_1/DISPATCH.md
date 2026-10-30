# Dispatch for Explorer M2 (1/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 2 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md

Milestone: M2 — Safety & Physical Input Layer
Focus: Safety Subsystem (`parasite_ai/safety/interrupt_guard.py` and `parasite_ai/safety/window_guard.py`)
Requirements:
1. Low-level Win32 hooks (`WH_MOUSE_LL = 14`, `WH_KEYBOARD_LL = 13`) filtering `LLMHF_INJECTED = 0x01` and `LLKHF_INJECTED = 0x10`.
2. Hardware interrupt latency < 2ms (benchmarked at 0.162ms via `threading.Event`).
3. Software simulation harness `simulate_event(event_type, flags, vk_code)` for deterministic automated testing.
4. Window Guard with sensitive window detection (Bitwarden, 1Password, KeePass, Task Manager, elevated Admin consoles) and fail-safe default (`hwnd == 0 -> protected`).

Deliverable: Concrete implementation plan and test specifications for Worker in `plan.md` and `handoff.md`.

## 2026-10-29T12:40:48Z
You are teamwork_explorer_m2_1, an exploration agent for ParasiteAI Milestone M2: Safety & Physical Input Layer.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\
You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\DISPATCH.md
4. Survey 2 Technical Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md
5. Existing codebase in g:\__Docs\ParasiteAI\parasite_ai\

Your Focus:
Safety Subsystem: `parasite_ai/safety/interrupt_guard.py` and `parasite_ai/safety/window_guard.py`, plus tests `tests/test_interrupt_guard.py` and `tests/test_window_guard.py`.

Technical Requirements to analyze & specify:
1. Low-level Win32 hooks (`WH_MOUSE_LL = 14`, `WH_KEYBOARD_LL = 13`) inspecting `LLMHF_INJECTED = 0x01` and `LLKHF_INJECTED = 0x10`.
2. Dedicated Win32 hook thread with proper message pump (`GetMessageW` / `DispatchMessageW`), sub-microsecond callback execution, clean unhooking (`UnhookWindowsHookEx`), and `WM_QUIT` teardown.
3. Hardware interrupt latency < 2ms using `threading.Event` cross-thread cancellation token.
4. Cooldown state machine with sliding window (10.0s cooldown on physical touch) and re-arming logic.
5. Deterministic simulation harness: `simulate_event(event_type, flags, vk_code)` allowing pytest to simulate physical hardware events (`flags=0`) vs synthetic events (`flags=INJECTED`) reliably in automated test suites without requiring manual user input.
6. Window Guard: Active foreground window inspection (`GetForegroundWindow`, window title, process image name). Blacklist for password managers (Bitwarden, 1Password, KeePass, KeePassXC), Task Manager, Regedit, CredentialUI, and elevated console windows. Fail-safe protection on inaccessible windows (`hwnd == 0 -> protected`).

Deliverable:
Write your complete technical implementation plan in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\plan.md` and your final report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\handoff.md`. Include exact class definitions, method signatures, ctypes struct layouts, ctypes calling conventions (WINFUNCTYPE), and test case specifications for the Worker.
When finished, notify the orchestrator via send_message.
