# Dispatch for Explorer M2 (3/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 2 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md

Milestone: M2 — Safety & Physical Input Layer
Focus: Unicode Keyboard Driver & Global Panic Abort Subsystem (`parasite_ai/hands/keyboard.py` and global panic triggers)
Requirements:
1. `KEYEVENTF_UNICODE` typing with 64-bit aligned `INPUT` structure (size 40 bytes, offset 8).
2. Astral plane emoji surrogate pairs ($> 0xFFFF$, $W_1$ high surrogate + $W_2$ low surrogate).
3. Multiline safety: `Shift+Enter` for intermediate newlines vs `Enter` for submission.
4. Human cadence jitter (log-normal inter-key delays, punctuation and paragraph pauses).
5. Per-keystroke interrupt check (< 2ms abort).
6. Global panic abort hotkeys (`Esc`, `Ctrl+Alt+P`, `Ctrl+Alt+Backspace`, screen corner slam) releasing any stuck keys and resetting hardware state.
7. Atomic `click_and_type` with focus initialization and caret verification.
8. Test simulation harness for mock keyboard events and unit testing.

Deliverable: Concrete implementation plan and test specifications for Worker in `plan.md` and `handoff.md`.

## 2026-10-29T12:41:07Z
You are teamwork_explorer_m2_3, an exploration agent for ParasiteAI Milestone M2: Safety & Physical Input Layer.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\
You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\DISPATCH.md
4. Survey 2 Technical Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md
5. Existing codebase in g:\__Docs\ParasiteAI\parasite_ai\

Your Focus:
Unicode Keyboard Driver & Global Panic Abort Subsystem: `parasite_ai/hands/keyboard.py` and global panic triggers, plus tests `tests/test_keyboard_driver.py` and `tests/test_panic.py`.

Technical Requirements to analyze & specify:
1. Direct Unicode injection using Win32 `SendInput` with `KEYEVENTF_UNICODE (0x0004)`:
   - Exact 64-bit aligned `INPUT` structure (verbatim 40 bytes on x64, with 8-byte union offset).
   - Layout-independent typing (`wVk = 0`, `wScan = ord(char)`).
2. Astral plane emoji support (code points $> 0xFFFF$ split into UTF-16 surrogate pairs $W_1$ and $W_2$).
3. Multiline safety: `Shift+Enter` for intermediate newlines vs plain `Enter` for prompt submission.
4. Natural human cadence jitter: log-normal inter-key delays ($\approx 30-70$ms), punctuation pauses ($80-150$ms), sentence and newline pauses ($150-300$ms).
5. Per-keystroke interrupt verification: checking `cancellation_token` or `interrupt_event.is_set()` before and after every character to abort immediately in < 2ms.
6. Atomic `click_and_type`: moves mouse, executes click, waits for focus caret initialization (60-90ms), then types with per-key interrupt checks.
7. Multi-layered Global Panic Abort mechanisms:
   - `Esc` key during driving/offloading.
   - `Ctrl + Alt + P` and `Ctrl + Alt + Backspace` system-wide.
   - Screen corner slam (cursor $\le 4$px from screen corner).
   - Emergency hardware state release: clears all held mouse buttons and modifier keys (`Shift`, `Ctrl`, `Alt`) to avoid stuck-key states.
8. Deterministic simulation harness for mock typing and testing in CI without physical keyboard interaction.

Deliverable:
Write your complete technical implementation plan in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\plan.md` and your final report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\handoff.md`. Include exact class definitions, method signatures, ctypes struct definitions, and pytest test suite specs for the Worker.
When finished, notify the orchestrator via send_message.
