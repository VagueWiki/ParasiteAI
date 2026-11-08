"""
benchmarks/verifiers.py - Programmatic OS Ground-Truth Verification & Setup Engine.

Provides objective, result-oriented ground-truth verifiers checking Windows 10 OS
side effects: top-level Win32 windows, minimized/iconic states, classic Notepad Edit
buffer contents (WM_GETTEXT + UIA ValuePattern), Calculator UIA results, File Explorer
CabinetWClass windows, filesystem mutations, and clipboard contents.

Also provides deterministic pre-task setup hooks and post-task teardown routines so
that every benchmark task starts from a verified initial precondition.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("parasite_ai.benchmarks.verifiers")

# Win32 Constants
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_SETTEXT = 0x000C
WM_CLOSE = 0x0010
EM_SETMODIFY = 0x00B9
SW_MINIMIZE = 6
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

WORKSPACE_DIR = Path("C:/ParasiteAI/benchmarks/workspace")


def _get_process_name_from_pid(pid: int) -> str:
    """Queries the executable basename for a given Win32 PID."""
    if os.name != "nt" or pid <= 0:
        return ""
    kernel32 = ctypes.windll.kernel32
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h_proc:
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h_proc)
    return ""


def get_open_windows(include_empty_titles: bool = False) -> List[Dict[str, Any]]:
    """
    Returns a list of visible top-level windows on Windows 10 with:
    hwnd, title, class_name, pid, process_name, and is_minimized (IsIconic).
    """
    windows: List[Dict[str, Any]] = []
    if os.name != "nt":
        return windows

    user32 = ctypes.windll.user32

    def _enum_proc(hwnd: int, lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0 and not include_empty_titles:
            return True
        title_buf = ctypes.create_unicode_buffer(length + 1)
        if length > 0:
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = _get_process_name_from_pid(pid.value)
        is_minimized = bool(user32.IsIconic(hwnd))

        windows.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "class_name": class_name,
                "pid": int(pid.value),
                "process_name": proc_name,
                "is_minimized": is_minimized,
            }
        )
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    try:
        user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)
    except Exception as exc:
        logger.debug("EnumWindows failed: %s", exc)

    return windows


def is_process_running(process_name: str) -> bool:
    """Checks whether a given process executable is currently running."""
    proc_clean = process_name.lower().replace(".exe", "")
    # First check visible windows (fast path)
    for win in get_open_windows(include_empty_titles=True):
        if win["process_name"].lower().replace(".exe", "") == proc_clean:
            return True
    # Fallback to tasklist for background / minimized / UWP processes
    try:
        cmd = ["tasklist", "/FI", f"IMAGENAME eq {proc_clean}.exe", "/NH"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return f"{proc_clean}.exe" in res.stdout.lower()
    except Exception:
        return False


def kill_process(process_name: str, force: bool = True) -> bool:
    """Terminates running instances of a process by name."""
    proc_clean = process_name.lower().replace(".exe", "") + ".exe"
    try:
        cmd = ["taskkill", "/IM", proc_clean]
        if force:
            cmd.insert(1, "/F")
            cmd.insert(2, "/T")
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        time.sleep(0.2)
        return True
    except Exception as exc:
        logger.debug("Failed to kill process %s: %s", process_name, exc)
        return False


def close_modal_dialogs(titles: Optional[List[str]] = None) -> None:
    """Closes any open benchmark modal dialogs matching title substrings."""
    if os.name != "nt":
        return
    target_titles = [t.lower() for t in (titles or ["Benchmark System Error"])]
    user32 = ctypes.windll.user32
    for win in get_open_windows():
        if any(t in win["title"].lower() for t in target_titles):
            user32.PostMessageW(win["hwnd"], WM_CLOSE, 0, 0)


def read_notepad_text() -> str:
    """
    Reads the document text from all open Notepad windows on Windows 10.
    Uses Win32 FindWindowExW(hwnd, 0, 'Edit', None) + WM_GETTEXT (classic Windows 10 Notepad)
    and falls back to UI Automation ValuePattern / TextPattern if needed.
    """
    if os.name != "nt":
        return ""

    user32 = ctypes.windll.user32
    collected: List[str] = []

    for win in get_open_windows(include_empty_titles=True):
        is_notepad = (
            win["process_name"].lower() == "notepad.exe"
            or win["class_name"] == "Notepad"
            or "notepad" in win["title"].lower()
        )
        if not is_notepad:
            continue

        hwnd = win["hwnd"]
        # 1. Classic Windows 10 Notepad: direct child 'Edit' control
        edit_hwnd = user32.FindWindowExW(hwnd, 0, "Edit", None)
        if not edit_hwnd:
            # Windows 11 / RichEdit fallback: RichEditD2DPT
            edit_hwnd = user32.FindWindowExW(hwnd, 0, "RichEditD2DPT", None)

        if edit_hwnd:
            length = user32.SendMessageW(edit_hwnd, WM_GETTEXTLENGTH, 0, 0)
            if length >= 0:
                buf = ctypes.create_unicode_buffer(length + 2)
                user32.SendMessageW(edit_hwnd, WM_GETTEXT, length + 1, buf)
                if buf.value:
                    collected.append(buf.value)
                    continue

        # 2. UI Automation ValuePattern / DocumentRange fallback
        try:
            import uiautomation as auto

            ctrl = auto.ControlFromHandle(hwnd)
            if ctrl:
                for c, _ in auto.WalkControl(ctrl, maxDepth=5):
                    if c.ControlTypeName in ("EditControl", "DocumentControl"):
                        try:
                            vp = c.GetValuePattern()
                            if vp and vp.Value:
                                collected.append(vp.Value)
                                break
                        except Exception:
                            pass
                        try:
                            tp = c.GetTextPattern()
                            if tp and tp.DocumentRange:
                                txt = tp.DocumentRange.GetText(-1)
                                if txt:
                                    collected.append(txt)
                                    break
                        except Exception:
                            pass
        except Exception as exc:
            logger.debug("UIA fallback in read_notepad_text failed: %s", exc)

    return "\n".join(collected)


def inject_notepad_text(text: str, mark_dirty: bool = True) -> bool:
    """
    Writes text directly into the first open Windows 10 Notepad 'Edit' control
    via WM_SETTEXT and optionally marks the buffer modified (EM_SETMODIFY) so
    closing Notepad prompts the 'Save / Don't Save' dialog.
    """
    if os.name != "nt":
        return False

    user32 = ctypes.windll.user32
    for win in get_open_windows(include_empty_titles=True):
        if win["process_name"].lower() == "notepad.exe" or win["class_name"] == "Notepad":
            edit_hwnd = user32.FindWindowExW(win["hwnd"], 0, "Edit", None)
            if edit_hwnd:
                buf = ctypes.create_unicode_buffer(text)
                user32.SendMessageW(edit_hwnd, WM_SETTEXT, 0, buf)
                if mark_dirty:
                    user32.SendMessageW(edit_hwnd, EM_SETMODIFY, 1, 0)
                return True
    return False


def minimize_process_windows(process_name: str) -> bool:
    """Minimizes all visible top-level windows belonging to process_name."""
    if os.name != "nt":
        return False
    proc_clean = process_name.lower().replace(".exe", "")
    user32 = ctypes.windll.user32
    minimized_any = False
    for win in get_open_windows():
        if win["process_name"].lower().replace(".exe", "") == proc_clean:
            user32.ShowWindow(win["hwnd"], SW_MINIMIZE)
            minimized_any = True
    time.sleep(0.2)
    return minimized_any


def reset_workspace_dir(workspace_dir: Path = WORKSPACE_DIR) -> Path:
    """Recreates a clean scratch directory at benchmarks/workspace."""
    if workspace_dir.exists():
        for item in workspace_dir.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception as exc:
                logger.debug("Failed removing workspace item %s: %s", item, exc)
    else:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def clear_clipboard() -> None:
    """Clears the system clipboard."""
    try:
        import pyperclip

        pyperclip.copy("")
    except Exception:
        pass


def cleanup_benchmark_processes() -> None:
    """Closes benchmark target applications and modal dialogs to leave the desktop clean."""
    close_modal_dialogs()
    targets = [
        "notepad.exe",
        "CalculatorApp.exe",
        "calculator.exe",
        "mspaint.exe",
    ]
    for target in targets:
        if is_process_running(target):
            kill_process(target)


# ---------------------------------------------------------------------------
# Pre-Task Setup Hooks (SETUP_REGISTRY)
# ---------------------------------------------------------------------------


def setup_clean_workspace(**kwargs: Any) -> bool:
    """Resets processes, scratch workspace directory, and clipboard."""
    cleanup_benchmark_processes()
    reset_workspace_dir()
    clear_clipboard()
    return True


def setup_open_notepad(**kwargs: Any) -> bool:
    """Cleans workspace, launches notepad.exe, and verifies it is open and visible."""
    setup_clean_workspace()
    subprocess.Popen(["notepad.exe"])
    deadline = time.time() + 5.0
    while time.time() < deadline:
        for win in get_open_windows():
            if win["process_name"].lower() == "notepad.exe" and not win["is_minimized"]:
                return True
        time.sleep(0.2)
    return False


def setup_open_dirty_notepad(initial_text: str = "Unsaved benchmark draft", **kwargs: Any) -> bool:
    """Launches Notepad and populates unsaved text so closing triggers the Save/Don't Save modal."""
    if not setup_open_notepad():
        return False
    time.sleep(0.2)
    return inject_notepad_text(initial_text, mark_dirty=True)


def setup_seed_workspace_file(
    filename: str = "seed.txt",
    content: str = "Project Proposal v1",
    **kwargs: Any,
) -> bool:
    """Cleans workspace and seeds a file in benchmarks/workspace."""
    setup_clean_workspace()
    target = WORKSPACE_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target.exists()


def setup_seed_rename_file(
    old_name: str = "old_name.txt",
    content: str = "Rename target content",
    **kwargs: Any,
) -> bool:
    """Cleans workspace and seeds old_name.txt for file rename verification."""
    return setup_seed_workspace_file(filename=old_name, content=content)


def setup_open_notepad_with_seed_file(
    filename: str = "source.txt",
    content: str = "TOKEN_9941",
    **kwargs: Any,
) -> bool:
    """Creates a seed file in benchmarks/workspace and opens it in Notepad."""
    if not setup_seed_workspace_file(filename=filename, content=content):
        return False
    target = WORKSPACE_DIR / filename
    subprocess.Popen(["notepad.exe", str(target)])
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if content in read_notepad_text():
            return True
        time.sleep(0.2)
    return False


def setup_spawn_modal_error_dialog(
    dialog_title: str = "Benchmark System Error",
    dialog_message: str = "An unexpected benchmark error occurred. Click OK to dismiss.",
    **kwargs: Any,
) -> bool:
    """Spawns a non-blocking Win32 MessageBoxW modal dialog in a child process."""
    setup_clean_workspace()
    code = (
        "import ctypes; "
        f"ctypes.windll.user32.MessageBoxW(0, {dialog_message!r}, {dialog_title!r}, 0x00000010 | 0x00040000)"
    )
    subprocess.Popen([sys.executable, "-c", code])
    deadline = time.time() + 5.0
    while time.time() < deadline:
        for win in get_open_windows():
            if dialog_title.lower() in win["title"].lower():
                return True
        time.sleep(0.2)
    return False


SETUP_REGISTRY: Dict[str, Callable[..., bool]] = {
    "clean_workspace": setup_clean_workspace,
    "open_notepad": setup_open_notepad,
    "open_dirty_notepad": setup_open_dirty_notepad,
    "seed_workspace_file": setup_seed_workspace_file,
    "seed_rename_file": setup_seed_rename_file,
    "open_notepad_with_seed_file": setup_open_notepad_with_seed_file,
    "spawn_modal_error_dialog": setup_spawn_modal_error_dialog,
}


def run_setup(setup_name: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """Executes a named pre-task setup hook and returns True if precondition is established."""
    if not setup_name:
        return setup_clean_workspace()
    fn = SETUP_REGISTRY.get(setup_name)
    if not fn:
        logger.error("Unknown setup hook '%s'", setup_name)
        return False
    try:
        return fn(**(params or {}))
    except Exception as exc:
        logger.error("Setup hook '%s' failed: %s", setup_name, exc, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Post-Task Ground-Truth Verifiers (VERIFIER_REGISTRY)
# ---------------------------------------------------------------------------


def verify_process_and_window(
    process_name: str,
    window_title_keywords: Optional[List[str]] = None,
    **kwargs: Any,
) -> bool:
    """Verifies that target process is running AND has a visible, non-minimized window."""
    if not is_process_running(process_name):
        logger.info("[VERIFY] Process '%s' is not running.", process_name)
        return False

    proc_clean = process_name.lower().replace(".exe", "")
    windows = get_open_windows()
    for win in windows:
        if win["is_minimized"]:
            continue
        title_lower = win["title"].lower()
        win_proc_clean = win["process_name"].lower().replace(".exe", "")
        if window_title_keywords:
            if any(kw.lower() in title_lower for kw in window_title_keywords):
                logger.info("[VERIFY] Found matching window '%s' for '%s'", win["title"], process_name)
                return True
        elif win_proc_clean == proc_clean:
            return True

    logger.info(
        "[VERIFY] Process '%s' running, but no visible non-minimized window matched %s",
        process_name,
        window_title_keywords,
    )
    return False


def verify_process_terminated(process_name: str, **kwargs: Any) -> bool:
    """Verifies that the process has completely terminated and has no open windows."""
    time.sleep(0.5)
    running = is_process_running(process_name)
    logger.info("[VERIFY] Process '%s' running status: %s (expected False)", process_name, running)
    return not running


def verify_window_minimized(process_name: str, **kwargs: Any) -> bool:
    """Verifies that process_name is running AND its window is minimized (IsIconic == True)."""
    proc_clean = process_name.lower().replace(".exe", "")
    windows = get_open_windows(include_empty_titles=True)
    matched_windows = [
        w
        for w in windows
        if w["process_name"].lower().replace(".exe", "") == proc_clean
        or (proc_clean == "notepad" and "notepad" in w["title"].lower())
    ]
    if not matched_windows:
        logger.info("[VERIFY] No window found for '%s' to verify minimized state.", process_name)
        return False
    return all(w["is_minimized"] for w in matched_windows)


def verify_window_contains_text(
    process_name: str,
    expected_text: str,
    **kwargs: Any,
) -> bool:
    """
    Verifies that an open window of process_name contains the expected text string
    via direct Win32 Edit WM_GETTEXT inspection or UI Automation ValuePattern/TextPattern.
    """
    if not is_process_running(process_name):
        return False

    proc_clean = process_name.lower().replace(".exe", "")
    if proc_clean == "notepad":
        text_content = read_notepad_text()
        if expected_text.lower() in text_content.lower():
            logger.info("[VERIFY] Found expected text '%s' in Notepad buffer.", expected_text)
            return True

    # General UIA ValuePattern / TextPattern inspection for non-Notepad windows
    try:
        import uiautomation as auto

        root = auto.GetRootControl()
        for child in root.GetChildren():
            if proc_clean in (child.Name or "").lower():
                for c, _ in auto.WalkControl(child, maxDepth=5):
                    for getter in ("GetValuePattern", "GetLegacyIAccessiblePattern"):
                        try:
                            pat = getattr(c, getter)()
                            val = getattr(pat, "Value", "") or ""
                            if expected_text.lower() in str(val).lower():
                                return True
                        except Exception:
                            pass
    except Exception as exc:
        logger.debug("UIA text inspection failed: %s", exc)

    return False


def verify_notepad_composed_text(
    min_chars: int = 25,
    forbid_substrings: Optional[List[str]] = None,
    **kwargs: Any,
) -> bool:
    """
    Verifies that Notepad contains composed prose of at least min_chars with sentence
    punctuation and does NOT merely echo the user's goal instruction.
    """
    if not is_process_running("notepad.exe"):
        return False

    text = read_notepad_text().strip()
    if len(text) < min_chars:
        logger.info("[VERIFY] Notepad text too short (%d < %d chars): %r", len(text), min_chars, text)
        return False

    if not any(p in text for p in (".", "!", "?")):
        logger.info("[VERIFY] Notepad text lacks sentence punctuation: %r", text)
        return False

    lower_text = text.lower()
    for forbidden in forbid_substrings or []:
        if forbidden.lower() in lower_text:
            logger.info("[VERIFY] Notepad text echoed forbidden prompt substring %r", forbidden)
            return False

    return True


def verify_calculator_result(expected_value: str, **kwargs: Any) -> bool:
    """Verifies Windows 10 Calculator display reflects the expected mathematical result."""
    if not is_process_running("CalculatorApp.exe") and not is_process_running("calculator.exe"):
        return False

    try:
        import uiautomation as auto

        calc_win = auto.WindowControl(searchDepth=2, ClassName="ApplicationFrameWindow")
        if calc_win.Exists(0, 0):
            res_ctrl = calc_win.TextControl(searchDepth=6, AutomationId="CalculatorResults")
            if res_ctrl.Exists(0, 0):
                txt = (res_ctrl.Name or "").replace(",", "").strip()
                # Calculator Name is typically "Display is 56"
                tokens = txt.split()
                if expected_value in tokens or txt.endswith(expected_value):
                    logger.info("[VERIFY] Calculator display confirmed '%s' in '%s'", expected_value, txt)
                    return True
    except Exception as exc:
        logger.debug("Calculator verification exception: %s", exc)

    return False


def verify_explorer_window_open(
    required_title_substrings: Optional[List[str]] = None,
    **kwargs: Any,
) -> bool:
    """Verifies that a visible File Explorer window (CabinetWClass) is open."""
    for win in get_open_windows():
        if win["is_minimized"]:
            continue
        if win["class_name"] in ("CabinetWClass", "ExploreWClass"):
            if not required_title_substrings:
                return True
            if any(sub.lower() in win["title"].lower() for sub in required_title_substrings):
                return True
    return False


def verify_clipboard_contains(expected_text: str, **kwargs: Any) -> bool:
    """Verifies that the Windows system clipboard contains expected_text."""
    try:
        import pyperclip

        clip = pyperclip.paste() or ""
        if expected_text.lower() in clip.lower():
            logger.info("[VERIFY] Clipboard contains expected text %r", expected_text)
            return True
        logger.info("[VERIFY] Clipboard content %r did not match %r", clip, expected_text)
    except Exception as exc:
        logger.debug("Clipboard read error: %s", exc)
    return False


def _resolve_benchmark_path(file_path: str) -> Path:
    """Resolves a path relative to C:/ParasiteAI, user home, or absolute path."""
    p = Path(file_path)
    if p.is_absolute():
        return p
    candidate_repo = Path("C:/ParasiteAI") / file_path
    if candidate_repo.exists():
        return candidate_repo
    candidate_home = Path(os.path.expanduser(f"~/{file_path}"))
    if candidate_home.exists():
        return candidate_home
    return candidate_repo


def verify_file_exists_and_content(file_path: str, expected_content: str, **kwargs: Any) -> bool:
    """Verifies that a file exists on disk and contains expected_content."""
    p = _resolve_benchmark_path(file_path)
    if not p.exists() or not p.is_file():
        logger.info("[VERIFY] File '%s' does not exist.", p)
        return False

    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        if expected_content.lower() in content.lower():
            logger.info("[VERIFY] File '%s' verified with expected content.", p)
            return True
        logger.info("[VERIFY] Content '%s' not found in file '%s' (got %r).", expected_content, p, content)
        return False
    except Exception as exc:
        logger.debug("File read error: %s", exc)
        return False


def verify_window_or_file_contains(
    file_path: str,
    expected_substrings: List[str],
    process_name: str = "notepad.exe",
    **kwargs: Any,
) -> bool:
    """Verifies that all expected_substrings appear either in the open Notepad buffer or saved file."""
    # Check live Notepad buffer first
    if is_process_running(process_name):
        buf = read_notepad_text().lower()
        if all(sub.lower() in buf for sub in expected_substrings):
            return True

    # Check saved file on disk
    p = _resolve_benchmark_path(file_path)
    if p.exists() and p.is_file():
        content = p.read_text(encoding="utf-8", errors="ignore").lower()
        if all(sub.lower() in content for sub in expected_substrings):
            return True

    return False


def verify_file_renamed(old_path: str, new_path: str, **kwargs: Any) -> bool:
    """Verifies that old_path no longer exists and new_path exists on disk."""
    old_p = _resolve_benchmark_path(old_path)
    new_p = _resolve_benchmark_path(new_path)
    return (not old_p.exists()) and new_p.exists()


def verify_directory_exists(dir_path: str, **kwargs: Any) -> bool:
    """Verifies that a directory exists on disk."""
    p = _resolve_benchmark_path(dir_path)
    return p.exists() and p.is_dir()


def verify_dialog_closed_and_window_open(
    dialog_title: str = "Benchmark System Error",
    process_name: str = "notepad.exe",
    window_title_keywords: Optional[List[str]] = None,
    **kwargs: Any,
) -> bool:
    """Verifies that the blocking modal dialog was dismissed AND the target app window is open."""
    for win in get_open_windows():
        if dialog_title.lower() in win["title"].lower():
            logger.info("[VERIFY] Blocking dialog '%s' is still open.", dialog_title)
            return False
    return verify_process_and_window(
        process_name=process_name,
        window_title_keywords=window_title_keywords or ["Notepad"],
    )


VERIFIER_REGISTRY: Dict[str, Callable[..., bool]] = {
    "verify_process_and_window": verify_process_and_window,
    "verify_process_terminated": verify_process_terminated,
    "verify_window_minimized": verify_window_minimized,
    "verify_window_contains_text": verify_window_contains_text,
    "verify_notepad_composed_text": verify_notepad_composed_text,
    "verify_calculator_result": verify_calculator_result,
    "verify_explorer_window_open": verify_explorer_window_open,
    "verify_clipboard_contains": verify_clipboard_contains,
    "verify_file_exists_and_content": verify_file_exists_and_content,
    "verify_window_or_file_contains": verify_window_or_file_contains,
    "verify_file_renamed": verify_file_renamed,
    "verify_directory_exists": verify_directory_exists,
    "verify_dialog_closed_and_window_open": verify_dialog_closed_and_window_open,
}


def run_verifier(verifier_name: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """Executes a named ground-truth verifier from VERIFIER_REGISTRY."""
    fn = VERIFIER_REGISTRY.get(verifier_name)
    if not fn:
        logger.warning("Unknown verifier '%s'; failing verification by default.", verifier_name)
        return False
    try:
        return fn(**(params or {}))
    except Exception as exc:
        logger.error("Verifier '%s' raised exception: %s", verifier_name, exc, exc_info=True)
        return False
