# Handoff Report: Milestone M4 Explorer 3 (Visible Browser Brain Offloader)

**Author**: `teamwork_explorer_m4_3`  
**Recipient**: Orchestrator (`9a16f679-6db4-4849-ba56-0f4856cbbf9b`)  
**Scope**: Feature 15 — Visible Browser Brain Offloader (`parasite_ai/mind/offloader.py`), Sentinel Clipboard Verification Protocol, `BrainManager` Fallback Integration, and Automated Test Strategy (`tests/test_browser_offloader.py`).

---

## 1. Observation

1. **Task Assignment**:
   - `DISPATCH.md` lines 10-32: Assigned Feature 15 (Visible Browser Brain Offloader). Requires 100% visible physical Chrome automation (NO headless browsers, NO hidden CDPs), Sentinel Clipboard Verification protocol (backup user clipboard, inject random test UUID, trigger copy, verify response, restore original clipboard), seamless fallback provider integration with `BrainManager`, and complete test strategy in `tests/test_browser_offloader.py`.
2. **Existing Brain Manager Architecture**:
   - `parasite_ai/mind/brain_manager.py` lines 41-44: `BrainMode` defines `BROWSER_OFFLOAD = "browser_offload"`.
   - `parasite_ai/mind/brain_manager.py` lines 374-414: `BrowserOffloadBackend` is already structured to delegate inference to `self.offloader.query_web_ai(full_query, browser_type=self.preferred_browser)`:
     ```python
     if self.offloader and hasattr(self.offloader, "query_web_ai"):
         return self.offloader.query_web_ai(full_query, browser_type=self.preferred_browser)
     ```
   - `parasite_ai/mind/brain_manager.py` lines 506-514: Zero-VRAM Fallback boots in `BrainMode.BROWSER_OFFLOAD` when no valid local GGUF model is found on disk.
   - `parasite_ai/mind/brain_manager.py` lines 903-929: `toggle_browser_only_mode(True)` unloads GPU models and transitions to `BrowserOffloadBackend` instantly.
3. **Configuration Schema**:
   - `config.yaml` lines 32-41 & `parasite_ai/config.py` lines 129-171: `BrowserOffloadConfig` already defines `preferred_browser`, `browser_paths` (Chrome, Opera GX), `default_web_ai_url` (`https://gemini.google.com`), `stream_stability_ms` (1500), `stream_timeout_sec` (45), and `sentinel_token_prefix` (`__PARASITE_SENTINEL__`).
4. **Physical Drivers**:
   - `parasite_ai/hands/keyboard.py` lines 354-450: `KeyboardDriver.type_text` provides human cadence jitter, surrogate pairs, per-keystroke interrupt cancellation, and multiline `Shift+Enter` safety for intermediate newlines.
   - `parasite_ai/hands/keyboard.py` lines 489-551: `KeyboardDriver.hotkey` executes key chords like `Ctrl+L` and `Ctrl+C`.
   - `parasite_ai/hands/mouse.py` lines 216-271: `MouseDriver.click` executes curved cursor gliding and click with 300ms pre-click reticle.
5. **Test Suite Baseline**:
   - Ran `uv run pytest`: 424 passed in 31.81s across the entire project.

---

## 2. Logic Chain

1. **Zero Headless / Visible Automation Invariant**:
   - The original request R1 & R4 strictly prohibits Puppeteer, Playwright, Selenium headless, and hidden Chrome DevTools Protocol (CDP) sockets.
   - Therefore, browser interaction MUST occur via standard desktop OS operations:
     a. Querying existing Chrome windows using Win32 `EnumWindows` and process inspection (`chrome.exe`).
     b. Bringing the window visibly to the foreground with `ShowWindow` and `SetForegroundWindow` (with `AttachThreadInput` to overcome Windows foreground locking).
     c. Navigating via physical keystrokes (`Ctrl+L` -> URL -> `Enter`).
     d. Focusing the input field via physical mouse click or Tab.
     e. Typing prompts with `KeyboardDriver.type_text` using human cadence jitter and `Shift+Enter` multiline protection.
2. **Sentinel Clipboard Protocol Security Invariant**:
   - When extracting text from desktop applications via clipboard, simple `Ctrl+C` risks copying stale clipboard data or private user clipboard contents if the click misses or fails.
   - The Sentinel protocol resolves this deterministically:
     a. Save user's original clipboard text (`IClipboardBackend.get_text()`).
     b. Arm a unique sentinel token containing a 128-bit random UUID (`f"{prefix}_{uuid.uuid4().hex}__"`).
     c. Verify that the clipboard actually holds the sentinel token before triggering copy.
     d. Trigger the physical copy action (clicking the web UI copy button or sending `Ctrl+C`).
     e. Poll clipboard: accept harvested text ONLY when clipboard changes to non-empty text that is strictly different from the sentinel token.
     f. Regardless of outcome (success, failure, timeout, or interrupt), ALWAYS restore the original user clipboard in a `finally:` block.
   - This guarantees that user clipboard history is never lost, and failed copies will never leak user private data.
3. **Testability & CI Decoupling via Protocols**:
   - Directly automating Chrome and the Windows clipboard during `pytest` in headless CI or development workstations would disrupt user activities.
   - By creating `IClipboardBackend` (concrete `Win32ClipboardBackend` / `MockClipboardBackend`) and `IBrowserWindowBackend` (concrete `Win32BrowserWindowBackend` / `MockBrowserWindowBackend`), all offloader logic, state transitions, prompt typing, multiline formatting, and sentinel verification can be tested deterministically in memory within milliseconds.

---

## 3. Caveats

1. **Web AI Interface DOM Changes**:
   - Frontier web AI UIs (e.g. Gemini, ChatGPT) can update their DOM layout or input locations over time.
   - *Mitigation*: The offloader uses standard browser conventions (`Ctrl+L` for address bar navigation, bottom-third center click for prompt input, and `Shift+Enter` multiline safety). In M4, integration with `ScreenGrounder` (Feature 12) allows dynamically finding the "Copy" button or "Prompt" box by label if needed.
2. **Foreground Lockout in Windows 11**:
   - Windows 11 prevents background processes from abruptly stealing foreground focus unless thread input is attached.
   - *Mitigation*: `Win32BrowserWindowBackend.focus_window` uses `AttachThreadInput(cur_thread, target_thread, True)` before calling `SetForegroundWindow` and `BringWindowToTop`.
3. **Clipboard Locking by External Tools**:
   - Tools like Office Clipboard or password managers can briefly lock the Win32 clipboard.
   - *Mitigation*: `Win32ClipboardBackend` implements retry logic (5 attempts with 15ms sleep) around `OpenClipboard`.

---

## 4. Conclusion

1. Feature 15 (`parasite_ai/mind/offloader.py`) is fully designed and ready for direct implementation by worker agents.
2. The Sentinel Clipboard Verification protocol satisfies all security, privacy, and correctness requirements.
3. The seamless integration with `LocalBrainManager` and `BrowserOffloadBackend` is verified against existing codebase interfaces.
4. The test strategy in `tests/test_browser_offloader.py` provides 12 targeted unit and integration tests covering the complete state machine, error handling, multiline safety, cancellation interrupts, and BrainManager fallback.
5. All design artifacts and specifications are detailed in `plan.md`.

---

## 5. Verification Method

1. **Implementation Inspection**:
   - Inspect `parasite_ai/mind/offloader.py` for `BrowserOffloader`, `SentinelClipboardVerifier`, `IClipboardBackend`, `IBrowserWindowBackend`, `Win32ClipboardBackend`, `MockClipboardBackend`, `Win32BrowserWindowBackend`, and `MockBrowserWindowBackend`.
   - Verify zero usage of `selenium`, `playwright`, `puppeteer`, or CDP web sockets.
2. **Automated Test Command**:
   ```powershell
   uv run pytest tests/test_browser_offloader.py -v
   ```
   All test cases (Section 6 of `plan.md`) must pass with 100% pass rate.
3. **Regression Test Command**:
   ```powershell
   uv run pytest
   ```
   All 424 existing tests plus new browser offloader tests must pass cleanly.
4. **Invalidation Conditions**:
   - Any test leaks user clipboard content or fails to restore the original clipboard.
   - Sentinel verification accepts an empty string or the sentinel token itself as valid output.
   - Physical Chrome automation uses hidden CDP sockets or headless flags.
