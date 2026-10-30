# Implementation Plan: Feature 15 — Visible Browser Brain Offloader

**Author**: `teamwork_explorer_m4_3`  
**Target Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload  
**Scope**: `parasite_ai/mind/offloader.py` and `tests/test_browser_offloader.py`

---

## 1. Executive Summary & Core Philosophy

Feature 15 delivers the **Visible Browser Brain Offloader**, fulfilling Requirement **R1** and **R4** of ParasiteAI:
- **Zero-VRAM instant startup**: When no local GGUF model exists or when the user toggles browser-only mode, the system operates completely in 0 MB VRAM by offloading cognitive reasoning to frontier web AI.
- **100% Visible Desktop Automation**: **NO Puppeteer, NO Playwright, NO Selenium headless, NO hidden Chrome DevTools Protocol (CDP) sockets.** The user physically sees Google Chrome (or Opera GX) focused on their desktop, the address bar activated, the prompt typed with human-like cadence, and the response harvested.
- **Sentinel Clipboard Verification Protocol**: Protects user privacy and guarantees data integrity by backing up original user clipboard text, injecting a randomized test UUID token, triggering copy, verifying that clipboard content changed from the test UUID to genuine model output, and restoring original user clipboard contents in a guaranteed `finally:` block.
- **Seamless BrainManager Integration**: Functions as the primary provider in zero-VRAM mode and transparent fallback provider for `LocalBrainManager` and `BrowserOffloadBackend`.

---

## 2. Architecture & Class Design

### 2.1 File Location
Target file: `g:\__Docs\ParasiteAI\parasite_ai\mind\offloader.py`  
Export in `parasite_ai/mind/__init__.py`: `BrowserOffloader`, `OffloaderState`, `SentinelClipboardVerifier`, `IClipboardBackend`, `IBrowserWindowBackend`.

### 2.2 Protocols & Dependency Inversion

To ensure 100% deterministic, high-speed unit testing that does not disturb physical desktop windows or developer clipboard state during CI/test runs, the offloader employs protocol-based dependency injection.

```python
from typing import Protocol, Optional, Tuple, List, Dict, Any, Callable, Union
from pathlib import Path
import threading

class IClipboardBackend(Protocol):
    """Protocol for clipboard reading and writing."""
    def get_text(self) -> str:
        """Returns current text content from clipboard. Returns empty string if non-text or empty."""
        ...
    def set_text(self, text: str) -> None:
        """Writes text string to clipboard."""
        ...

class IBrowserWindowBackend(Protocol):
    """Protocol for desktop window discovery, activation, and geometry."""
    def find_browser_window(self, browser_type: str) -> Optional[int]:
        """Returns HWND of existing visible browser window, or None."""
        ...
    def focus_window(self, hwnd: int) -> bool:
        """Restores and brings window to foreground."""
        ...
    def launch_browser(self, executable_path: Union[str, Path], url: str) -> Optional[int]:
        """Launches browser executable with URL and returns new window HWND."""
        ...
    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) window bounding rectangle in screen pixels."""
        ...
    def is_window_foreground(self, hwnd: int) -> bool:
        """Returns True if hwnd is currently the active foreground window."""
        ...
```

### 2.3 Concrete Backends

#### A. Clipboard Backends
1. `Win32ClipboardBackend` (Production):
   - Uses `pyperclip` with automatic fallback to native Win32 `user32.OpenClipboard` / `GetClipboardData` / `SetClipboardData`.
   - Incorporates retry loop (5 attempts, 15ms sleep on `OpenClipboard` failure) to tolerate temporary clipboard locks by background Windows processes.
2. `MockClipboardBackend` (Testing):
   - In-memory string `_content: str = ""`.
   - Tracks `write_history: List[str]` and `read_history: List[str]`.
   - Supports failure simulation flags: `fail_on_read: bool`, `fail_on_write: bool`.

#### B. Browser Window Backends
1. `Win32BrowserWindowBackend` (Production):
   - Window enumeration: `user32.EnumWindows` callback verifying `user32.IsWindowVisible(hwnd)` and inspecting process name via `OpenProcess` + `QueryFullProcessImageNameW` (`chrome.exe` / `opera.exe`) or window titles containing `"Google Chrome"` / `"Opera"`.
   - Robust foreground activation:
     ```python
     def focus_window(self, hwnd: int) -> bool:
         if user32.IsIconic(hwnd):
             user32.ShowWindow(hwnd, 9)  # SW_RESTORE
         else:
             user32.ShowWindow(hwnd, 5)  # SW_SHOW
         
         # Bypass Windows foreground lock timeout restrictions
         cur_thread = kernel32.GetCurrentThreadId()
         target_thread = user32.GetWindowThreadProcessId(hwnd, None)
         user32.AttachThreadInput(cur_thread, target_thread, True)
         try:
             user32.BringWindowToTop(hwnd)
             user32.SetForegroundWindow(hwnd)
         finally:
             user32.AttachThreadInput(cur_thread, target_thread, False)
         return user32.GetForegroundWindow() == hwnd
     ```
   - Process launch: `subprocess.Popen([str(executable_path), url])` followed by polling for new HWND up to 5.0s.
   - Geometry: `user32.GetWindowRect(hwnd)`.
2. `MockBrowserWindowBackend` (Testing):
   - Simulates browser window presence without OS calls.
   - Configurable initial state (e.g., `existing_hwnd: Optional[int] = 12345`).
   - Tracks `focused_hwnds`, `launched_calls`, and configurable rect `(100, 100, 1500, 900)`.

---

## 3. Sentinel Clipboard Verification Protocol

### 3.1 Security & Reliability Invariants
1. **User Data Preservation**: The user's clipboard must NEVER be clobbered or permanently lost. Even on unexpected exceptions, aborts, or timeouts, the original clipboard content is restored.
2. **Zero False Positives / Zero Private Leaks**: If the model response copy action fails (e.g. click missed or wrong element selected), the clipboard remains equal to the sentinel UUID. The offloader will NEVER mistake pre-existing user clipboard data for an AI response!
3. **Collision Resistance**: Uses 128-bit randomized hex UUIDs (`__PARASITE_SENTINEL_{uuid.uuid4().hex}__`) with custom configurable prefix from `config.brain.offload.sentinel_token_prefix`.

### 3.2 Protocol Implementation (`SentinelClipboardVerifier`)

```python
class SentinelClipboardVerifier:
    def __init__(
        self,
        clipboard: IClipboardBackend,
        token_prefix: str = "__PARASITE_SENTINEL__",
        poll_interval_s: float = 0.05,
        default_timeout_s: float = 4.0,
    ):
        self.clipboard = clipboard
        self.token_prefix = token_prefix
        self.poll_interval_s = poll_interval_s
        self.default_timeout_s = default_timeout_s

    def generate_sentinel(self) -> str:
        return f"{self.token_prefix}_{uuid.uuid4().hex}__"

    def execute_harvest(
        self,
        trigger_copy_action: Callable[[], bool],
        timeout_s: Optional[float] = None,
        cancellation_token: Optional[threading.Event] = None,
    ) -> Optional[str]:
        # Step 1: Backup current clipboard text
        try:
            original_clip = self.clipboard.get_text()
        except Exception as exc:
            logger.warning("Could not backup original clipboard: %s", exc)
            original_clip = ""

        # Step 2: Inject unique sentinel token
        sentinel_token = self.generate_sentinel()
        harvested_text: Optional[str] = None

        try:
            self.clipboard.set_text(sentinel_token)
            
            # Verify sentinel was successfully armed
            if self.clipboard.get_text() != sentinel_token:
                logger.error("Failed to arm sentinel token in clipboard.")
                return None

            if cancellation_token and cancellation_token.is_set():
                return None

            # Step 3: Trigger physical copy action (clicking Copy or Ctrl+C)
            if not trigger_copy_action():
                logger.warning("Trigger copy action failed.")
                return None

            # Step 4: Poll clipboard for change
            deadline = time.perf_counter() + (timeout_s or self.default_timeout_s)
            while time.perf_counter() < deadline:
                if cancellation_token and cancellation_token.is_set():
                    return None

                try:
                    current = self.clipboard.get_text()
                    # A genuine response must be non-empty and DIFFERENT from sentinel
                    if current != sentinel_token and len(current.strip()) > 0:
                        harvested_text = current
                        break
                except Exception:
                    pass

                time.sleep(self.poll_interval_s)

            return harvested_text

        finally:
            # Step 5: Restore original user clipboard text ALWAYS
            try:
                self.clipboard.set_text(original_clip)
            except Exception as exc:
                logger.error("Failed to restore original clipboard: %s", exc)
```

---

## 4. Visible Browser Offloader State Machine

### 4.1 State Definitions
```python
class OffloaderState(str, Enum):
    IDLE = "IDLE"
    LOCATING_BROWSER = "LOCATING_BROWSER"
    FOCUSING_WINDOW = "FOCUSING_WINDOW"
    NAVIGATING_URL = "NAVIGATING_URL"
    WAITING_PAGE_READY = "WAITING_PAGE_READY"
    FOCUSING_PROMPT = "FOCUSING_PROMPT"
    TYPING_PROMPT = "TYPING_PROMPT"
    WAITING_RESPONSE = "WAITING_RESPONSE"
    HARVESTING_RESPONSE = "HARVESTING_RESPONSE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

### 4.2 Sequence of Operations in `query_web_ai`

1. **Locate or Launch**:
   - Query `window_backend.find_browser_window(browser_type)`.
   - If not found, lookup path from `config.browser_paths[browser_type]`.
   - Launch browser with target URL (`config.default_web_ai_url`, e.g. `https://gemini.google.com`).
   - Call `window_backend.focus_window(hwnd)`.
2. **Navigate Address Bar**:
   - Focus address bar via `keyboard_driver.hotkey("ctrl", "l")`.
   - Type target URL via `keyboard_driver.type_text(url, submit=True)`.
   - Wait for page readiness (configurable navigation wait: default 1500ms or screen settling).
3. **Focus Prompt & Input**:
   - Compute prompt coordinate from window rect:
     `rect = window_backend.get_window_rect(hwnd)`
     `input_x = rect[0] + (rect[2] - rect[0]) // 2`
     `input_y = rect[3] - 120`
   - Click prompt box via `mouse_driver.click(input_x, input_y)`.
   - Type prompt via `keyboard_driver.type_text(prompt, submit=True)`.
   - Multi-line safety: `KeyboardDriver` automatically emits `Shift+Enter` for interior newlines, preventing accidental premature chat submission, and emits plain `Enter` on final submit.
4. **Wait for Model Streaming**:
   - Wait up to `stream_timeout_sec` (45s).
   - Polls screen settling or dwell time `stream_stability_ms` (1500ms).
5. **Sentinel Harvest**:
   - Define copy trigger:
     - If copy button coordinates provided or found, click button.
     - Fallback: click response area and send `hotkey("ctrl", "c")`.
   - Execute `sentinel_verifier.execute_harvest(trigger_func)`.
   - Verify non-empty response harvested and original user clipboard restored.
   - Return clean response string.

---

## 5. Integration with `LocalBrainManager`

In `parasite_ai/mind/brain_manager.py`:
- `BrowserOffloadBackend` is already constructed to delegate to `offloader.query_web_ai(full_query, browser_type=...)`.
- `LocalBrainManager`:
  - When instantiated with `offloader=None`, can lazily create a `BrowserOffloader(config=config.brain.offload, keyboard_driver=..., mouse_driver=...)`.
  - When no GGUF model is found on disk during startup, automatically sets `mode = BrainMode.BROWSER_OFFLOAD` and routes all cognitive tasks (`generate_thought`, `generate_action`) to `BrowserOffloadBackend`.
  - When `toggle_browser_only_mode(True)` is called, unloads local GPU model and activates `BrowserOffloadBackend` in 0 MB VRAM.

---

## 6. Comprehensive Automated Test Strategy (`tests/test_browser_offloader.py`)

The test suite will contain 100% automated, fast, deterministic tests running under `uv run pytest`:

### Test Cases & Invariants

| Test Name | Test Objective | Verification Criteria |
|---|---|---|
| `test_sentinel_harvest_success` | Full sentinel lifecycle on successful copy | 1. Original clip restored<br>2. Harvested text matches simulated copy<br>3. Sentinel armed and cleared |
| `test_sentinel_harvest_miss_or_no_change` | Copy action fails or clicks nothing | 1. Returns `None`<br>2. Original clip restored<br>3. User data NOT leaked |
| `test_sentinel_harvest_empty_original_clip` | User clipboard was originally empty | 1. Restores `""`<br>2. Does not throw error |
| `test_sentinel_harvest_cancellation_token` | Interrupt triggered during poll loop | 1. Aborts in < 50ms<br>2. Original clip restored |
| `test_sentinel_token_uniqueness` | Generate 500 tokens in loop | 1. All unique UUIDs<br>2. Starts with configured prefix |
| `test_locate_existing_browser_window` | Chrome already open on desktop | 1. Discovers HWND<br>2. Brings to front<br>3. Does not call `launch_browser` |
| `test_launch_browser_when_missing` | Chrome not running | 1. Invokes `launch_browser`<br>2. Waits for HWND<br>3. Navigates to target URL |
| `test_browser_offloader_full_flow` | End-to-end simulated prompt query | 1. Focus -> Nav -> Click -> Type -> Harvest<br>2. Returns harvested model text |
| `test_multiline_prompt_shift_enter` | Prompt has internal `\n` | 1. Verifies Shift+Enter sent for newlines<br>2. Only final submit uses Enter |
| `test_offloader_cancellation_during_typing` | Physical touch interrupt during query | 1. Key release called<br>2. Aborts cleanly<br>3. Clipboard restored |
| `test_brain_manager_fallback_delegation` | `LocalBrainManager` using `BrowserOffloader` | 1. `brain_manager.generate()` calls offloader<br>2. Returns offloaded text |
| `test_zero_vram_startup_mode` | Startup with empty models directory | 1. Mode is `BROWSER_OFFLOAD`<br>2. State is `READY_BROWSER_OFFLOAD`<br>3. VRAM is 0 MB |

---

## 7. Next Actions for Implementation Worker

1. Create `parasite_ai/mind/offloader.py` with:
   - `IClipboardBackend`, `Win32ClipboardBackend`, `MockClipboardBackend`
   - `IBrowserWindowBackend`, `Win32BrowserWindowBackend`, `MockBrowserWindowBackend`
   - `SentinelClipboardVerifier`
   - `BrowserOffloader` (alias `ChromeOffloader`)
   - `OffloaderState`, `OffloadHarvestError`, `BrowserNotFoundError`
2. Update `parasite_ai/mind/__init__.py` with module exports.
3. Update `parasite_ai/mind/brain_manager.py` to auto-instantiate `BrowserOffloader` if `offloader` is None.
4. Implement `tests/test_browser_offloader.py` covering all test cases in Section 6.
5. Run `uv run pytest tests/test_browser_offloader.py` and ensure 100% pass.
