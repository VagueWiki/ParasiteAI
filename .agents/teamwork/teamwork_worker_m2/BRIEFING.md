# BRIEFING — 2026-10-29T12:49:00Z

## Mission
Implement ParasiteAI Milestone M2 (Safety & Physical Input Layer) including InterruptGuard, WindowGuard, Panic, Kinematics, MouseDriver, and KeyboardDriver with 100% test pass rate and high fidelity to Windows low-level input architecture.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M2 - Safety & Physical Input Layer

## 🔒 Key Constraints
- Exact Win32 ctypes struct sizes and offsets:
  - ctypes.sizeof(INPUT) == 40 bytes on x64 with 4-byte padding aligning union at offset 8.
  - ctypes.sizeof(MSLLHOOKSTRUCT) == 32 bytes.
  - ctypes.sizeof(KBDLLHOOKSTRUCT) == 24 bytes.
- Hook flags: LLMHF_INJECTED = 0x01, LLKHF_INJECTED = 0x10. Retain callback references to prevent garbage collection crashes (0xC0000005).
- Interrupt token: threading.Event cross-thread cancellation token aborting movement/typing in < 2ms on physical hardware touch.
- Deterministic simulation harnesses in InterruptGuard, MouseDriver, KeyboardDriver allowing pytest to run headlessly, reliably, and deterministically without touching physical hardware.
- Window Guard: hwnd == 0 and inaccessible processes fail safe to protected/sensitive (is_safe_to_operate() == False).
- Kinematics: Flash & Hogan Minimum Jerk polynomial tau(s) = 10s^3 - 15s^4 + 6s^5, Cubic Bézier with asymmetric control points, Fitts's Law duration, sin(pi * s) boundary-damped micro-jitter, overshoot with corrective micro-hop.
- Keyboard: KEYEVENTF_UNICODE = 0x0004, UTF-16 surrogate pairs for > 0xFFFF, Shift+Enter multiline safety, log-normal cadence jitter.
- Panic: Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, screen corner slam with emergency hardware release clearing stuck buttons/keys.
- Verification: uv run pytest (189 existing tests + all new tests pass, 0 failures).
- Integrity Mandate: No cheating, no hardcoded test outputs, genuine logic and state.

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T12:49:00Z

## Task Summary
- **What to build**: Full M2 safety and input subsystem:
  - `parasite_ai/safety/interrupt_guard.py`
  - `parasite_ai/safety/window_guard.py`
  - `parasite_ai/safety/panic.py`
  - `parasite_ai/safety/__init__.py`
  - `parasite_ai/hands/kinematics.py`
  - `parasite_ai/hands/mouse.py`
  - `parasite_ai/hands/keyboard.py`
  - `parasite_ai/hands/__init__.py`
  - Unit & integration tests for all components
- **Success criteria**: All 189 M1 tests pass + comprehensive M2 test suite passes cleanly with 0 regressions.
- **Interface contracts**: Master Project Spec & Explorer Reports.

## Key Decisions Made
- [TBD - will populate after analyzing explorer reports]

## Artifact Index
- `BRIEFING.md` — persistent situational awareness
- `progress.md` — heartbeat and progress tracker
- `handoff.md` — final 5-component handoff report

## Change Tracker
- **Files modified**: None yet
- **Build status**: Pending initial run
- **Pending issues**: None

## Quality Status
- **Build/test result**: Pending
- **Lint status**: Pending
- **Tests added/modified**: Pending

## Loaded Skills
- None specified for load
