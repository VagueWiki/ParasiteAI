"""
parasite_ai/mind/offloader.py - Visible Browser Brain Offloader & Sentinel Clipboard Protocol.

Operates with 100% visible physical desktop Chrome/Opera automation (zero headless browsers,
zero invisible scrapers, zero hidden CDP sockets). Implements Sentinel Clipboard Verification
to safely harvest responses without corrupting or exposing user clipboard contents.
"""

from __future__ import annotations

from enum import Enum
import logging
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union
import uuid

import pyperclip

from parasite_ai.config import BrowserOffloadConfig
from parasite_ai.ui.bridge import UIBridge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions & States
# ---------------------------------------------------------------------------

class OffloadHarvestError(Exception):
    """Raised when harvesting model response from web AI fails or times out."""


class BrowserNotFoundError(Exception):
    """Raised when the requested web browser is neither running nor installed."""


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


# ---------------------------------------------------------------------------
# Backends Protocols & Implementations
# ---------------------------------------------------------------------------

class IClipboardBackend(Protocol):
    """Protocol for reading and writing text to the clipboard."""

    def get_text(self) -> str:
        """Returns current text content from clipboard (empty string if non-text)."""
        ...

    def set_text(self, text: str) -> None:
        """Writes text string to clipboard."""
        ...


class Win32ClipboardBackend:
    """Production clipboard backend wrapping pyperclip with Win32 lock retries."""

    def __init__(self, max_retries: int = 5, retry_delay_s: float = 0.015) -> None:
        self.max_retries = max_retries
        self.retry_delay_s = retry_delay_s

    def get_text(self) -> str:
        for attempt in range(self.max_retries):
            try:
                content = pyperclip.paste()
                return content if content is not None else ""
            except Exception as exc:
                if attempt == self.max_retries - 1:
                    logger.debug("Clipboard paste failed after %d retries: %s", self.max_retries, exc)
                    return ""
                time.sleep(self.retry_delay_s)
        return ""

    def set_text(self, text: str) -> None:
        for attempt in range(self.max_retries):
            try:
                pyperclip.copy(text)
                return
            except Exception as exc:
                if attempt == self.max_retries - 1:
                    logger.warning("Clipboard copy failed after %d retries: %s", self.max_retries, exc)
                    return
                time.sleep(self.retry_delay_s)


class MockClipboardBackend:
    """Deterministic mock clipboard backend for high-speed testing."""

    def __init__(self, initial_text: str = "") -> None:
        self._content: str = initial_text
        self.read_history: List[str] = []
        self.write_history: List[str] = []
        self.fail_on_read: bool = False
        self.fail_on_write: bool = False

    def get_text(self) -> str:
        if self.fail_on_read:
            raise RuntimeError("Simulated clipboard read failure")
        self.read_history.append(self._content)
        return self._content

    def set_text(self, text: str) -> None:
        if self.fail_on_write:
            raise RuntimeError("Simulated clipboard write failure")
        self._content = text
        self.write_history.append(text)


class IBrowserWindowBackend(Protocol):
    """Protocol for finding, focusing, and launching browser windows."""

    def find_browser_window(self, browser_type: str) -> Optional[int]:
        ...

    def focus_window(self, hwnd: int) -> bool:
        ...

    def launch_browser(self, executable_path: Union[str, Path], url: str) -> Optional[int]:
        ...

    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        ...

    def is_window_foreground(self, hwnd: int) -> bool:
        ...


class Win32BrowserWindowBackend:
    """Production Win32 window manager for visible browser windows."""

    def find_browser_window(self, browser_type: str) -> Optional[int]:
        try:
            import ctypes
            user32 = ctypes.windll.user32

            matched_hwnd: Optional[int] = None
            type_lower = browser_type.lower()

            def enum_proc(hwnd: int, lparam: int) -> bool:
                nonlocal matched_hwnd
                if not user32.IsWindowVisible(hwnd):
                    return True

                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.lower()

                    if type_lower == "chrome" and "google chrome" in title:
                        matched_hwnd = hwnd
                        return False
                    elif "opera" in type_lower and "opera" in title:
                        matched_hwnd = hwnd
                        return False

                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
            return matched_hwnd
        except Exception as exc:
            logger.debug("Win32 find_browser_window error: %s", exc)
            return None

    def focus_window(self, hwnd: int) -> bool:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(hwnd, 5)  # SW_SHOW

            cur_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            user32.AttachThreadInput(cur_thread, target_thread, True)
            try:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            finally:
                user32.AttachThreadInput(cur_thread, target_thread, False)

            return bool(user32.GetForegroundWindow() == hwnd)
        except Exception as exc:
            logger.debug("Win32 focus_window error: %s", exc)
            return False

    def launch_browser(self, executable_path: Union[str, Path], url: str) -> Optional[int]:
        try:
            path_obj = Path(executable_path)
            if not path_obj.exists():
                return None
            subprocess.Popen([str(path_obj), url])
            # Poll for window up to 4.0s
            deadline = time.time() + 4.0
            while time.time() < deadline:
                hwnd = self.find_browser_window(path_obj.stem)
                if hwnd:
                    return hwnd
                time.sleep(0.2)
            return None
        except Exception as exc:
            logger.error("Failed to launch browser %s: %s", executable_path, exc)
            return None

    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            pass
        return (0, 0, 1920, 1080)

    def is_window_foreground(self, hwnd: int) -> bool:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return bool(user32.GetForegroundWindow() == hwnd)
        except Exception:
            return False


class MockBrowserWindowBackend:
    """Mock window manager for unit tests."""

    def __init__(self, existing_hwnd: Optional[int] = 12345) -> None:
        self.existing_hwnd = existing_hwnd
        self.focused_hwnds: List[int] = []
        self.launched_calls: List[Tuple[str, str]] = []
        self.rect: Tuple[int, int, int, int] = (100, 100, 1500, 900)
        self.current_foreground: Optional[int] = existing_hwnd

    def find_browser_window(self, browser_type: str) -> Optional[int]:
        return self.existing_hwnd

    def focus_window(self, hwnd: int) -> bool:
        self.focused_hwnds.append(hwnd)
        self.current_foreground = hwnd
        return True

    def launch_browser(self, executable_path: Union[str, Path], url: str) -> Optional[int]:
        self.launched_calls.append((str(executable_path), url))
        self.existing_hwnd = 998877
        self.current_foreground = 998877
        return 998877

    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        return self.rect

    def is_window_foreground(self, hwnd: int) -> bool:
        return self.current_foreground == hwnd


# ---------------------------------------------------------------------------
# Sentinel Clipboard Verification Protocol
# ---------------------------------------------------------------------------

class SentinelClipboardVerifier:
    """
    Protocol verifying clipboard harvests:
    1. Backs up user's pre-existing clipboard text.
    2. Injects unique 128-bit UUID sentinel token.
    3. Triggers physical copy action.
    4. Polls clipboard: accepts content ONLY when non-empty and DIFFERENT from sentinel.
    5. Guaranteed restoration of user's original clipboard text in finally: block.
    """

    def __init__(
        self,
        clipboard: IClipboardBackend,
        token_prefix: str = "__PARASITE_SENTINEL__",
        poll_interval_s: float = 0.05,
        default_timeout_s: float = 4.0,
    ) -> None:
        self.clipboard = clipboard
        self.token_prefix = token_prefix
        self.poll_interval_s = poll_interval_s
        self.default_timeout_s = default_timeout_s

    def generate_sentinel(self) -> str:
        """Generates a randomized 128-bit hex UUID token."""
        return f"{self.token_prefix}_{uuid.uuid4().hex}__"

    def execute_harvest(
        self,
        trigger_copy_action: Callable[[], bool],
        timeout_s: Optional[float] = None,
        cancellation_token: Optional[threading.Event] = None,
    ) -> Optional[str]:
        """
        Executes atomic backup -> sentinel inject -> copy trigger -> poll -> restore.
        """
        # Step 1: Backup current clipboard text
        try:
            original_clip = self.clipboard.get_text()
        except Exception as exc:
            logger.debug("Failed backing up original clipboard: %s", exc)
            original_clip = ""

        # Step 2: Inject sentinel token
        sentinel_token = self.generate_sentinel()
        harvested_text: Optional[str] = None

        try:
            self.clipboard.set_text(sentinel_token)

            # Verify sentinel was written
            try:
                check = self.clipboard.get_text()
                if check != sentinel_token:
                    logger.warning("Sentinel verification mismatch during arming.")
                    return None
            except Exception:
                return None

            if cancellation_token and cancellation_token.is_set():
                return None

            # Step 3: Trigger copy action (physical keystroke or mouse click)
            copy_ok = trigger_copy_action()
            if not copy_ok:
                logger.debug("Trigger copy action returned False.")
                return None

            # Step 4: Poll clipboard until it changes from sentinel
            duration = timeout_s if timeout_s is not None else self.default_timeout_s
            deadline = time.perf_counter() + duration

            while time.perf_counter() < deadline:
                if cancellation_token and cancellation_token.is_set():
                    return None

                try:
                    curr = self.clipboard.get_text()
                    if curr != sentinel_token and len(curr.strip()) > 0:
                        harvested_text = curr
                        break
                except Exception:
                    pass

                time.sleep(self.poll_interval_s)

            return harvested_text

        finally:
            # Step 5: Always restore original user clipboard content
            try:
                self.clipboard.set_text(original_clip)
            except Exception as exc:
                logger.error("Failed to restore original user clipboard: %s", exc)


# ---------------------------------------------------------------------------
# Visible Browser Offloader Engine
# ---------------------------------------------------------------------------

class BrowserOffloader:
    """
    Visible Browser Brain Offloader.
    Offloads cognitive reasoning to frontier web AI using 100% visible physical
    desktop interactions (focusing window, navigating URL, typing prompts with human
    cadence, and harvesting responses via Sentinel Clipboard Verification).
    """

    def __init__(
        self,
        config: Optional[BrowserOffloadConfig] = None,
        clipboard_backend: Optional[IClipboardBackend] = None,
        window_backend: Optional[IBrowserWindowBackend] = None,
        keyboard_driver: Optional[Any] = None,
        mouse_driver: Optional[Any] = None,
        bridge: Optional[UIBridge] = None,
        grounder: Optional[Any] = None,
    ) -> None:
        self.config = config or BrowserOffloadConfig()
        self.clipboard_backend = clipboard_backend or Win32ClipboardBackend()
        self.window_backend = window_backend or Win32BrowserWindowBackend()
        self.keyboard_driver = keyboard_driver
        self.mouse_driver = mouse_driver
        self.bridge = bridge
        self.grounder = grounder

        self.verifier = SentinelClipboardVerifier(
            clipboard=self.clipboard_backend,
            token_prefix=self.config.sentinel_token_prefix,
            poll_interval_s=0.05,
            default_timeout_s=float(self.config.stream_timeout_sec),
        )
        self.state: OffloaderState = OffloaderState.IDLE

    def _find_prompt_target(self, hwnd: int) -> Tuple[int, int]:
        """
        Attempts to locate Chrome's web AI prompt input box via ScreenGrounder.
        Falls back to relative window center-bottom coordinate heuristic.
        """
        if self.grounder:
            try:
                elements = self.grounder.ground(window_filter=hwnd)
                candidates: List[Any] = []
                for elem in elements:
                    role = getattr(elem, "role", "").lower()
                    label = getattr(elem, "label", "").lower()
                    if role in ("edit", "document"):
                        candidates.append(elem)
                    elif any(kw in label for kw in ("prompt", "ask", "message", "chat", "type", "search")):
                        candidates.append(elem)

                if candidates:
                    # Select the bottom-most prompt input (highest center_y)
                    best_elem = max(candidates, key=lambda e: getattr(e, "center_y", 0))
                    logger.debug("Grounded prompt box: '%s' at (%d, %d)", getattr(best_elem, "label", ""), best_elem.center_x, best_elem.center_y)
                    return (best_elem.center_x, best_elem.center_y)
            except Exception as exc:
                logger.debug("ScreenGrounder prompt localization error: %s", exc)

        # Fallback heuristic: center-bottom of window
        rect = self.window_backend.get_window_rect(hwnd)
        prompt_x = rect[0] + (rect[2] - rect[0]) // 2
        prompt_y = rect[3] - 120
        return (prompt_x, prompt_y)

    def _find_copy_button(self, hwnd: int) -> Optional[Tuple[int, int]]:
        """
        Attempts to locate Chrome's web AI response 'Copy' button via ScreenGrounder.
        Returns (center_x, center_y) if found, else None.
        """
        if not self.grounder:
            return None

        try:
            elements = self.grounder.ground(window_filter=hwnd)
            candidates: List[Any] = []
            for elem in elements:
                role = getattr(elem, "role", "").lower()
                label = getattr(elem, "label", "").lower()
                if "copy" in label or label in ("salin", "copier", "kopieren"):
                    candidates.append(elem)
                elif role == "button" and ("copy" in label or "clipboard" in label):
                    candidates.append(elem)

            if candidates:
                # Select the latest (bottom-most) copy button
                best_elem = max(candidates, key=lambda e: getattr(e, "center_y", 0))
                logger.debug("Grounded Copy button: '%s' at (%d, %d)", getattr(best_elem, "label", ""), best_elem.center_x, best_elem.center_y)
                return (best_elem.center_x, best_elem.center_y)
        except Exception as exc:
            logger.debug("ScreenGrounder copy button localization error: %s", exc)

        return None

    def _update_state(self, new_state: OffloaderState) -> None:
        self.state = new_state
        if self.bridge:
            self.bridge.notify_telemetry(f"Offloader: {new_state.value}")

    def query_web_ai(
        self,
        prompt: str,
        browser_type: Optional[str] = None,
        cancellation_token: Optional[threading.Event] = None,
    ) -> str:
        """
        Executes end-to-end visible physical browser offload workflow:
        1. Finds or launches browser window.
        2. Brings window to foreground.
        3. Navigates to target web AI interface.
        4. Focuses prompt area and types prompt with multiline Shift+Enter.
        5. Waits for response and harvests text using Sentinel Clipboard Verification.
        """
        b_type = (browser_type or self.config.preferred_browser).lower()
        target_url = self.config.default_web_ai_url

        try:
            # 1. Locate or Launch Browser Window
            self._update_state(OffloaderState.LOCATING_BROWSER)
            hwnd = self.window_backend.find_browser_window(b_type)

            if hwnd is None:
                # Browser not running -> launch executable
                exec_path = self.config.browser_paths.get(b_type)
                if not exec_path:
                    raise BrowserNotFoundError(f"No configured executable path for browser: '{b_type}'")
                hwnd = self.window_backend.launch_browser(exec_path, target_url)
                if hwnd is None:
                    raise BrowserNotFoundError(f"Failed to launch or acquire window for browser: '{b_type}'")

            # 2. Focus Window
            self._update_state(OffloaderState.FOCUSING_WINDOW)
            focused = self.window_backend.focus_window(hwnd)
            if not focused:
                logger.debug("Could not confirm foreground focus on HWND %s", hwnd)

            if cancellation_token and cancellation_token.is_set():
                raise OffloadHarvestError("Offload cancelled before navigation")

            # 3. Navigate URL (Ctrl+L -> URL -> Enter)
            self._update_state(OffloaderState.NAVIGATING_URL)
            if self.keyboard_driver:
                self.keyboard_driver.hotkey("ctrl", "l", cancellation_token=cancellation_token)
                time.sleep(0.05)
                self.keyboard_driver.type_text(target_url, submit=True, cancellation_token=cancellation_token)

            # Wait for page readiness
            self._update_state(OffloaderState.WAITING_PAGE_READY)
            settle_s = max(0.1, self.config.stream_stability_ms / 1000.0)
            if cancellation_token:
                if cancellation_token.wait(timeout=settle_s):
                    raise OffloadHarvestError("Offload cancelled during page wait")
            else:
                time.sleep(settle_s)

            # 4. Focus Prompt & Type Text
            self._update_state(OffloaderState.FOCUSING_PROMPT)
            prompt_x, prompt_y = self._find_prompt_target(hwnd)

            if self.mouse_driver:
                self.mouse_driver.click(prompt_x, prompt_y, button="left", cancellation_token=cancellation_token)

            self._update_state(OffloaderState.TYPING_PROMPT)
            if self.keyboard_driver:
                ok = self.keyboard_driver.type_text(prompt, submit=True, cancellation_token=cancellation_token)
                if not ok:
                    raise OffloadHarvestError("Typing was aborted or interrupted by user")

            # 5. Wait for Response & Harvest
            self._update_state(OffloaderState.WAITING_RESPONSE)
            time.sleep(0.1)

            self._update_state(OffloaderState.HARVESTING_RESPONSE)

            def trigger_copy() -> bool:
                if cancellation_token and cancellation_token.is_set():
                    return False

                # Tier 1: Grounded Copy button click
                copy_coords = self._find_copy_button(hwnd)
                if copy_coords and self.mouse_driver:
                    return self.mouse_driver.click(
                        copy_coords[0], copy_coords[1], button="left", cancellation_token=cancellation_token
                    )

                # Tier 2: Fallback heuristic (click response canvas + Ctrl+C)
                if self.mouse_driver:
                    self.mouse_driver.click(prompt_x, prompt_y - 200, button="left", cancellation_token=cancellation_token)
                if self.keyboard_driver:
                    return self.keyboard_driver.hotkey("ctrl", "c", cancellation_token=cancellation_token)
                return True

            harvested = self.verifier.execute_harvest(
                trigger_copy_action=trigger_copy,
                timeout_s=float(self.config.stream_timeout_sec),
                cancellation_token=cancellation_token,
            )

            if not harvested:
                self._update_state(OffloaderState.FAILED)
                raise OffloadHarvestError("Failed to harvest response from web AI (timeout or sentinel mismatch)")

            self._update_state(OffloaderState.COMPLETED)
            return harvested

        except Exception as exc:
            self._update_state(OffloaderState.FAILED)
            if not isinstance(exc, (OffloadHarvestError, BrowserNotFoundError)):
                raise OffloadHarvestError(f"Unexpected browser offload failure: {exc}") from exc
            raise


# Alias for Chrome specific naming
ChromeOffloader = BrowserOffloader
