# Task Assignment: Milestone M4 Explorer 3 (Visible Browser Brain Offloader)

**Recipient**: `teamwork_explorer_m4_3`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_3\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Focus Area: Feature 15 — Visible Browser Brain Offloader (`parasite_ai/mind/offloader.py`)
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Requirement R1: Zero-VRAM Visible Browser Brain Offload & Core Philosophy: Zero Headless Browsers).
   - `PROJECT.md` Feature 15 & survey reports.
2. **Architecture & Scope**:
   - 100% visible, desktop-native browser interaction: NO Puppeteer, NO Playwright, NO Selenium headless, NO hidden Chrome DevTools Protocol (CDP) sockets.
   - Physical automation: focuses or launches the user's visible Google Chrome window on the desktop.
   - Physical desktop interactions: activates address bar (`Ctrl+L`), navigates to target AI web interface, clicks prompt input field, types prompt via `KeyboardDriver` with human cadence, clicks generate button.
   - Sentinel Clipboard Verification protocol:
     1. Backs up user's current clipboard text safely.
     2. Sets a randomized test UUID into the clipboard to prove clipboard control.
     3. Automates copy of the AI response (e.g. clicking the web UI copy button or selecting text and sending `Ctrl+C`).
     4. Reads clipboard and verifies that content changed from the test UUID to genuine model output.
     5. Restores original user clipboard text to preserve user data.
   - Integration with `BrainManager` as a transparent fallback provider when local GGUF model is not present or VRAM is 0.
3. **Investigation Tasks**:
   - Inspect existing `parasite_ai/mind/brain_manager.py` and `parasite_ai/hands/keyboard.py`, `mouse.py`.
   - Design `ChromeOffloader` class interface, configuration, navigation flows, Sentinel Clipboard protocol, and fail-safe timeouts.
   - Specify automated test strategy in `tests/test_browser_offloader.py` with mockable desktop window focus and clipboard harnesses.
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T16:47:45Z
You are assigned as Milestone M4 Explorer 3 (`teamwork_explorer_m4_3`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_3\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_3\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

EXPLORER FOCUS:
- Feature 15: Visible Browser Brain Offloader (`parasite_ai/mind/offloader.py`).
- Design 100% visible physical Chrome automation (NO headless browsers, NO hidden CDPs).
- Design Sentinel Clipboard Verification protocol (backup user clipboard, inject random test UUID, trigger response copy, verify response, restore original clipboard).
- Design integration into `BrainManager` as seamless fallback provider.
- Formulate complete implementation plan and automated test strategy in `tests/test_browser_offloader.py`.
- Write your plan in `plan.md` and handoff in `handoff.md`. Do NOT modify code directly.
- Notify the orchestrator via `send_message`.
