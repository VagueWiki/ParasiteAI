"""
ParasiteAI - Sensitive Window Guard & Privacy Shield.
Monitors foreground window, detects sensitive applications (password managers,
elevated administrator consoles, security prompts), and enforces fail-safe blackouts.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from typing import List, Optional, Tuple

from parasite_ai.config import SafetyConfig


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowGuardedException(RuntimeError):
    """Raised when an action or perception is attempted while a sensitive window is active."""
    pass


DEFAULT_SENSITIVE_PROCESSES: List[str] = [
    "bitwarden.exe",
    "1password.exe",
    "keepass.exe",
    "keepassxc.exe",
    "taskmgr.exe",
    "regedit.exe",
    "credentialui.exe",
    "consent.exe",
    "logonui.exe",
]

DEFAULT_SENSITIVE_TITLES: List[str] = [
    "Bitwarden",
    "1Password",
    "KeePass",
    "Task Manager",
    "Registry Editor",
    "Windows Security",
    "User Account Control",
    "Credential Manager",
]


@dataclass(frozen=True)
class WindowInfo:
    """Snapshot of active window state and privacy classification."""
    hwnd: int
    title: str
    class_name: str
    process_name: str
    process_path: str
    pid: int
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_sensitive: bool
    reason: str


class WindowGuard:
    """
    Foreground window privacy shield.
    Inspects active foreground window for password managers, admin prompts,
    or inaccessible processes, enforcing a strict fail-safe default.
    """

    def __init__(
        self,
        sensitive_titles: Optional[List[str]] = None,
        sensitive_processes: Optional[List[str]] = None,
        config: Optional[SafetyConfig] = None,
        custom_process_blacklist: Optional[List[str]] = None,
        custom_title_blacklist: Optional[List[str]] = None,
    ):
        cfg = config or SafetyConfig()

        proc_set = set(p.lower() for p in (sensitive_processes or cfg.sensitive_process_names or DEFAULT_SENSITIVE_PROCESSES))
        if custom_process_blacklist:
            proc_set.update(p.lower() for p in custom_process_blacklist)
        self.sensitive_processes = list(proc_set)

        title_set = set(t.lower() for t in (sensitive_titles or cfg.sensitive_window_titles or DEFAULT_SENSITIVE_TITLES))
        if custom_title_blacklist:
            title_set.update(t.lower() for t in custom_title_blacklist)
        self.sensitive_titles = list(title_set)

        self._init_win32_bindings()

    def _init_win32_bindings(self) -> None:
        try:
            self._user32 = ctypes.windll.user32
            self._kernel32 = ctypes.windll.kernel32

            self._user32.GetForegroundWindow.argtypes = []
            self._user32.GetForegroundWindow.restype = wintypes.HWND

            self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD

            self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            self._user32.GetWindowTextW.restype = ctypes.c_int

            self._user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            self._user32.GetClassNameW.restype = ctypes.c_int

            self._user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            self._user32.GetWindowRect.restype = wintypes.BOOL

            self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._kernel32.OpenProcess.restype = wintypes.HANDLE

            self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._kernel32.CloseHandle.restype = wintypes.BOOL

            self._kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD),
            ]
            self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        except Exception:
            pass

    def evaluate_sensitivity(
        self,
        title: str,
        process_name: str,
        hwnd: int = 1,
        can_open_process: bool = True,
    ) -> Tuple[bool, str]:
        """
        Pure deterministic sensitivity evaluator.
        Enforces all fail-safe invariants.
        """
        # Fail-Safe 1: hwnd == 0 (Desktop switch, lock screen, screen saver)
        if hwnd == 0:
            return True, "No active foreground window (hwnd == 0 / locked / desktop switch)"

        # Fail-Safe 2: Inaccessible process (e.g. UAC elevated prompt or access denied)
        if not can_open_process:
            return True, "Elevated or protected process (OpenProcess access denied)"

        title_lower = title.lower()
        proc_lower = process_name.lower()

        # Check process blacklist
        for proc in self.sensitive_processes:
            if proc == proc_lower or proc_lower.endswith(proc):
                return True, f"Sensitive process matched: '{proc}'"

        # Check title blacklist
        for t in self.sensitive_titles:
            if t in title_lower:
                return True, f"Sensitive window title matched: '{t}'"

        # Check elevated console header
        if "administrator:" in title_lower:
            return True, "Elevated console window ('Administrator:')"

        return False, "Window is safe to operate"

    def get_active_window_info(self) -> WindowInfo:
        """
        Queries Win32 subsystem for foreground window metadata.
        Applies fail-safe rules for hwnd == 0 and elevated processes.
        """
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return WindowInfo(
                hwnd=0,
                title="",
                class_name="",
                process_name="",
                process_path="",
                pid=0,
                rect=(0, 0, 0, 0),
                is_sensitive=True,
                reason="No active foreground window (hwnd == 0 / locked / desktop switch)",
            )

        # Extract Window Title
        title_buf = ctypes.create_unicode_buffer(512)
        self._user32.GetWindowTextW(hwnd, title_buf, 512)
        title = title_buf.value

        # Extract Class Name
        class_buf = ctypes.create_unicode_buffer(256)
        self._user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        # Extract Window Rect
        rect = wintypes.RECT()
        self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
        rect_tuple = (rect.left, rect.top, rect.right, rect.bottom)

        # Extract PID
        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_name="",
                process_path="",
                pid=0,
                rect=rect_tuple,
                is_sensitive=True,
                reason="Invalid PID 0 (system idle or protected)",
            )

        # Open Process Handle
        h_process = self._kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid.value,
        )

        if not h_process:
            # Elevated process or protected security desktop
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_name="",
                process_path="",
                pid=pid.value,
                rect=rect_tuple,
                is_sensitive=True,
                reason="Elevated or protected process (OpenProcess access denied)",
            )

        try:
            path_buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if self._kernel32.QueryFullProcessImageNameW(h_process, 0, path_buf, ctypes.byref(size)):
                process_path = path_buf.value
                process_name = os.path.basename(process_path)
            else:
                process_path = ""
                process_name = ""
        finally:
            self._kernel32.CloseHandle(h_process)

        is_sensitive, reason = self.evaluate_sensitivity(
            title=title,
            process_name=process_name,
            hwnd=hwnd,
            can_open_process=True,
        )

        return WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            process_name=process_name,
            process_path=process_path,
            pid=pid.value,
            rect=rect_tuple,
            is_sensitive=is_sensitive,
            reason=reason,
        )

    def is_safe_to_operate(self) -> bool:
        """
        Returns True if and only if the active foreground window is safe.
        Returns False if sensitive, inaccessible, locked, or hwnd == 0.
        """
        try:
            info = self.get_active_window_info()
            return not info.is_sensitive
        except Exception:
            # Fail safe on any error
            return False

    def get_active_window(self) -> WindowInfo:
        """Alias for get_active_window_info()."""
        return self.get_active_window_info()

