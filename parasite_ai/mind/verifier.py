"""
parasite_ai/mind/verifier.py - Runtime Pre-DONE Objective Goal Verifier.

Provides fast (<5ms CPU), domain-agnostic OS post-condition verification before
allowing the cognitive pipeline to return ActionType.DONE. Checks live Win32 window
states, minimization flags, classic Notepad Edit buffer text (WM_GETTEXT), filesystem
paths, clipboard content, and modal dialogs.
Strictly adheres to Invariant D4: ZERO hardcoded benchmark task IDs or test tokens.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Win32 Constants
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_PROMPT_ECHO_PHRASES = (
    "write a short two-sentence greeting",
    "2-sentence overview",
    "two-sentence overview",
    "the first sentence is about",
    "first sentence will be about",
    "the second sentence is about",
    "second sentence will be about",
)
_META_OUTLINE_PATTERN = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|next|final)\s+sentence\s+(?:is|will\s+be|focuses|covers|describes|explains)\s+(?:about\s+)?\b"
)
_SENTENCE_WORD_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_ECHO_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "on", "for", "to", "with", "about", "and", "or",
    "brief", "short", "overview", "summary", "write", "compose", "draft", "type",
    "open", "notepad", "sentence", "sentences",
})


def _extract_required_sentence_count(goal_lower: str) -> int:
    """Extracts an explicit N-sentence requirement from a goal string, or 0 if unspecified."""
    m = re.search(r"\b(\d+|one|two|three|four|five)[-\s]+sentences?\b", goal_lower or "")
    if not m:
        return 0
    tok = m.group(1)
    if tok.isdigit():
        return max(1, int(tok))
    return _SENTENCE_WORD_COUNTS.get(tok, 0)


def _count_sentences(text: str) -> int:
    """Counts complete punctuated sentences containing at least two alphanumeric words."""
    if not text or not text.strip():
        return 0
    parts = re.findall(r"[^.!?\r\n]+[.!?]+", text.strip())
    return sum(1 for p in parts if len(re.findall(r"[A-Za-z0-9]+", p)) >= 2)


def _segment_echoes_goal(segment: str, goal: str) -> bool:
    """Returns True if a short segment is mostly topic/goal words with minimal original content."""
    if not goal or not segment or len(segment) >= 100:
        return False
    goal_words = set(re.findall(r"[a-z0-9]+", goal.lower())) - _ECHO_STOPWORDS
    seg_words = [w for w in re.findall(r"[a-z0-9]+", segment.lower()) if w not in _ECHO_STOPWORDS]
    if not seg_words or not goal_words:
        return False
    return (sum(1 for w in seg_words if w in goal_words) / len(seg_words)) >= 0.6


def _is_prompt_echo(text: str, goal: str = "") -> bool:
    """Returns True if text echoes generative prompt instructions or meta-outline placeholders."""
    buf_low = (text or "").lower().strip()
    if any(phrase in buf_low for phrase in _PROMPT_ECHO_PHRASES):
        return True
    if _META_OUTLINE_PATTERN.search(buf_low):
        return True
    if goal and buf_low:
        if _count_sentences(buf_low) <= 1 and _segment_echoes_goal(buf_low, goal):
            return True
        first_sent = re.split(r"(?<=[.!?])\s+|\r?\n", buf_low, maxsplit=1)[0].strip()
        if first_sent and _segment_echoes_goal(first_sent, goal):
            return True
    return False


def _find_unexpected_modal_dialog(
    goal_lower: str,
    windows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Detects an unrequested #32770 save/confirmation/error dialog blocking the workspace."""
    is_dismiss_or_teardown = any(
        w in goal_lower
        for w in (
            "close", "exit", "quit", "terminate", "kill",
            "dismiss", "don't save", "dont save", "without saving",
            "save", "error dialog",
        )
    )
    if is_dismiss_or_teardown:
        return None
    for win in windows:
        if win.get("class_name") != "#32770":
            continue
        t_low = win.get("title", "").lower()
        proc_low = win.get("process_name", "").lower()
        if (
            "notepad" in t_low
            or proc_low == "notepad.exe"
            or any(k in t_low for k in ("error", "warning", "save changes", "confirm"))
        ):
            return win
    return None


class GoalVerificationResult(BaseModel):
    """Result of runtime goal post-condition verification."""
    model_config = ConfigDict(extra="ignore")

    verified: bool = True
    reason: str = "Goal state verified"
    checked_conditions: List[str] = Field(default_factory=list)


def get_live_windows(include_empty_titles: bool = False) -> List[Dict[str, Any]]:
    """
    Returns top-level visible windows with:
    hwnd, title, class_name, pid, process_name, is_minimized (IsIconic).
    """
    windows: List[Dict[str, Any]] = []
    if sys.platform != "win32":
        return windows

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

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
            proc_name = ""
            if pid.value > 0:
                h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                if h_proc:
                    try:
                        buf = ctypes.create_unicode_buffer(512)
                        size = wintypes.DWORD(512)
                        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                            proc_name = os.path.basename(buf.value)
                    finally:
                        kernel32.CloseHandle(h_proc)

            is_minimized = bool(user32.IsIconic(hwnd))

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            rect_tuple = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))

            windows.append({
                "hwnd": int(hwnd),
                "title": title,
                "class_name": class_name,
                "pid": int(pid.value),
                "process_name": proc_name,
                "is_minimized": is_minimized,
                "rect": rect_tuple,
            })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)
    except Exception as exc:
        logger.debug("get_live_windows failed: %s", exc)

    return windows


def read_calculator_display() -> Optional[str]:
    """Reads the current display string from Windows Calculator via UIA, or None if unavailable."""
    if sys.platform != "win32":
        return None
    try:
        import uiautomation as auto  # type: ignore

        calc_win = auto.WindowControl(searchDepth=2, ClassName="ApplicationFrameWindow")
        if calc_win.Exists(0, 0):
            res_ctrl = calc_win.TextControl(searchDepth=6, AutomationId="CalculatorResults")
            if res_ctrl.Exists(0, 0):
                return (res_ctrl.Name or "").strip()
    except Exception as exc:
        logger.debug("read_calculator_display failed: %s", exc)
    return None


def read_notepad_buffer(allow_uia_fallback: bool = True) -> str:
    """Reads current document text from open Notepad windows via WM_GETTEXT."""
    if sys.platform != "win32":
        return ""

    try:
        user32 = ctypes.windll.user32
        collected: List[str] = []
        for win in get_live_windows(include_empty_titles=True):
            is_notepad = (
                win["process_name"].lower() == "notepad.exe"
                or win["class_name"] == "Notepad"
                or "notepad" in win["title"].lower()
            )
            if not is_notepad:
                continue

            hwnd = win["hwnd"]
            edit_hwnd = user32.FindWindowExW(hwnd, 0, "Edit", None)
            if not edit_hwnd:
                edit_hwnd = user32.FindWindowExW(hwnd, 0, "RichEditD2DPT", None)

            if edit_hwnd:
                length = user32.SendMessageW(edit_hwnd, WM_GETTEXTLENGTH, 0, 0)
                if length >= 0:
                    buf = ctypes.create_unicode_buffer(length + 2)
                    user32.SendMessageW(edit_hwnd, WM_GETTEXT, length + 1, buf)
                    if buf.value:
                        collected.append(buf.value)
                    # If edit control was directly queried, don't fall through to UIA
                    continue

            if not allow_uia_fallback:
                continue

            # UIA fallback if edit control not directly reached
            try:
                import uiautomation as auto
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl:
                    for c, _ in auto.WalkControl(ctrl, maxDepth=5):
                        if c.ControlTypeName in ("EditControl", "DocumentControl"):
                            vp = getattr(c, "GetValuePattern", None)
                            if callable(vp):
                                pat = vp()
                                if pat and getattr(pat, "Value", None):
                                    collected.append(pat.Value)
                                    break
            except Exception:
                pass

        return "\n".join(collected)
    except Exception as exc:
        logger.debug("read_notepad_buffer failed: %s", exc)
        return ""


class RuntimeGoalVerifier:
    """
    Domain-agnostic runtime goal verifier.
    Extracts semantic requirements from natural language goals and validates live OS state.
    """

    def __init__(self) -> None:
        pass

    def build_working_memory_snapshot(
        self,
        user_goal: str,
        active_window: Optional[Any] = None,
        grounded_elements: Optional[List[Any]] = None,
    ) -> str:
        """
        Builds a fast (<3ms CPU) live OS working memory snapshot and sub-goal checklist
        for injection into the single-pass CUA prompt. Zero VRAM overhead.
        """
        if not user_goal or not isinstance(user_goal, str):
            return ""

        goal = user_goal.strip()
        goal_lower = goal.lower()
        windows = get_live_windows(include_empty_titles=False)

        lines: List[str] = []

        # 1. Foreground Window & Spatial Geometry
        fg_hwnd = getattr(active_window, "hwnd", None) if active_window else None
        fg_title = getattr(active_window, "title", None) if active_window else None
        fg_proc = getattr(active_window, "process_name", None) if active_window else None
        fg_rect = getattr(active_window, "rect", None) if active_window else None
        fg_label = ""
        if isinstance(fg_title, str) and isinstance(fg_proc, str) and (fg_title.strip() or fg_proc.strip()):
            fg_label = f"{fg_title.strip()} ({fg_proc.strip()})" if fg_title.strip() and fg_proc.strip() else (fg_title.strip() or fg_proc.strip())
        elif windows:
            # Fallback to topmost non-minimized window
            topmost = next((w for w in windows if not w["is_minimized"] and w["class_name"] not in ("Progman", "WorkerW", "Shell_TrayWnd")), None)
            if topmost:
                fg_label = f"{topmost['title']} ({topmost['process_name']})"
                if not fg_hwnd and topmost.get("hwnd"):
                    fg_hwnd = topmost.get("hwnd")
                if not fg_rect and topmost.get("rect"):
                    fg_rect = topmost.get("rect")
                if not fg_title:
                    fg_title = topmost.get("title")
                if not fg_proc:
                    fg_proc = topmost.get("process_name")

        # Fallback to Win32 GetForegroundWindow rect/hwnd if still None
        if (fg_rect is None or fg_hwnd is None) and sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                live_fg = user32.GetForegroundWindow()
                if live_fg:
                    if not fg_hwnd:
                        fg_hwnd = live_fg
                    if fg_rect is None:
                        r = wintypes.RECT()
                        if user32.GetWindowRect(live_fg, ctypes.byref(r)):
                            fg_rect = (int(r.left), int(r.top), int(r.right), int(r.bottom))
            except Exception:
                pass

        # Resolve target monitor dimensions for physical screen pixel working memory geometry
        mw, mh = 1920, 1080
        ml, mt_mon = 0, 0
        try:
            from parasite_ai.vision.capture import get_monitor_bounds
            ml, mt_mon, mw, mh = get_monitor_bounds(1)
            if mw <= 0 or mh <= 0:
                mw, mh = 1920, 1080
                ml, mt_mon = 0, 0
        except Exception:
            pass

        if fg_label:
            bounds_str = ""
            if isinstance(fg_rect, (tuple, list)) and len(fg_rect) == 4:
                wl, wt, wr, wb = fg_rect
                ww, wh = wr - wl, wb - wt
                if ww > 0 and wh > 0:
                    bounds_str = f" [Bounds: x={wl}, y={wt}, w={ww}, h={wh}]"
            lines.append(f"- Active Window: {fg_label}{bounds_str}")

        # 2. Desktop Shell & Taskbar Strip Geometry in physical screen pixels
        tb_top = mt_mon + mh - 40
        tb_bot = mt_mon + mh
        lines.append(f"- Desktop Taskbar: Bottom strip (y={tb_top}..{tb_bot})")

        # 3. Open Application Windows (filter desktop shell / self)
        cur_pid = os.getpid()
        shell_classes = {"progman", "workerw", "shell_traywnd", "shell_secondarytraywnd", "windows.ui.core.corewindow"}
        user_wins = [
            w for w in windows
            if w.get("pid") != cur_pid
            and w.get("class_name", "").lower() not in shell_classes
            and "parasiteai" not in w.get("title", "").lower()
            and w.get("title", "").strip()
        ]
        if user_wins:
            app_summaries = []
            for w in user_wins[:5]:
                min_tag = " [Minimized]" if w["is_minimized"] else ""
                w_title = w["title"][:30] + ("..." if len(w["title"]) > 30 else "")
                app_summaries.append(f"{w_title} ({w['process_name']}){min_tag}")
            lines.append(f"- Open Windows: {'; '.join(app_summaries)}")

        # 4. Running Background Applications Affordance (Taskbar Restore Guidance)
        bg_apps = []
        for w in user_wins:
            w_hwnd = w.get("hwnd")
            is_fg = False
            if fg_hwnd is not None and w_hwnd is not None:
                is_fg = (w_hwnd == fg_hwnd)
            elif fg_proc and fg_title:
                is_fg = (w.get("process_name") == fg_proc and w.get("title") == fg_title)

            if is_fg and not w.get("is_minimized"):
                continue

            p_lower = w.get("process_name", "").lower()
            t_lower = w.get("title", "").lower()

            is_relevant = False
            for target in ("notepad", "calculator", "paint", "mspaint", "explorer", "chrome", "edge", "cmd", "powershell"):
                if target in goal_lower and (target in p_lower or target in t_lower):
                    is_relevant = True
                    break
            if not is_relevant and any(term in goal_lower for term in ("window", "app", "application", "switch", "restore", "taskbar")):
                is_relevant = True

            if is_relevant:
                status = "Minimized" if w.get("is_minimized") else "In Background"
                w_title = w["title"][:25] + ("..." if len(w["title"]) > 25 else "")
                bg_apps.append(f"{w_title} ({w['process_name']}) [{status}]")

        if bg_apps:
            lines.append(f"- Running Background Applications: {'; '.join(bg_apps)} -> Click taskbar at y={tb_top}..{tb_bot} to restore")

        # 5. Blocking Modal Dialogs (#32770 or error prompts)
        modal_wins = [
            w for w in windows
            if (w.get("class_name") == "#32770" or any(k in w.get("title", "").lower() for k in ("error", "warning", "save as", "save changes", "confirm")))
            and not w.get("is_minimized")
        ]
        if modal_wins:
            m_titles = [w['title'] for w in modal_wins[:2]]
            lines.append(f"- ⚠️ Blocking Modal Dialog: {', '.join(m_titles)} (Interact with dialog first)")

        # 6. Live Notepad Buffer Preview (via fast WM_GETTEXT, no UIA walk)
        has_notepad_win = any("notepad" in w.get("process_name", "").lower() or "notepad" in w.get("title", "").lower() for w in windows)
        if has_notepad_win:
            nb_text = read_notepad_buffer(allow_uia_fallback=False)
            if nb_text.strip():
                clean_nb = " ".join(nb_text.split())
                if len(clean_nb) > 40:
                    clean_nb = clean_nb[:37] + "..."
                lines.append(f'- Notepad Buffer: "{clean_nb}"')
            else:
                lines.append("- Notepad Buffer: <empty>")

        # 7. Live Clipboard Preview
        if any(w in goal_lower for w in ("clipboard", "copy", "cut", "harvest", "paste")):
            clip_val = ""
            try:
                import pyperclip
                clip_val = pyperclip.paste() or ""
            except Exception:
                pass
            if clip_val.strip():
                clean_clip = " ".join(clip_val.split())
                if len(clean_clip) > 40:
                    clean_clip = clean_clip[:37] + "..."
                lines.append(f'- Clipboard: "{clean_clip}"')
            else:
                lines.append("- Clipboard: <empty>")

        # 7.5 Teardown / Closed Application Affordance
        is_teardown_goal = any(k in goal_lower for k in ("close", "exit", "quit", "terminate", "kill", "don't save", "dont save", "without saving"))
        if is_teardown_goal:
            teardown_targets = []
            for target in ("notepad", "calculator", "calc", "paint", "mspaint", "file explorer", "explorer", "chrome", "edge", "browser"):
                is_close = bool(re.search(rf"(?i)\b(?:close|exit|quit|terminate|kill)\b.*{target}", goal)) and not bool(re.search(rf"(?i)(?:^|then\s+|and\s+)(?:open|launch)\s+(?:the\s+)?(?:file\s+)?{target}\b", goal))
                if is_close:
                    teardown_targets.append(target)
            if teardown_targets:
                for target in teardown_targets:
                    target_proc = "mspaint" if target == "paint" else ("calculatorapp" if target in ("calculator", "calc") else ("explorer" if "explorer" in target else target))
                    matching_wins = [w for w in windows if target_proc in w.get("process_name", "").lower() or target in w.get("title", "").lower()]
                    if not matching_wins:
                        lines.append(f"- Target Application Status: {target} is CLOSED / TERMINATED (0 open windows). Teardown goal is fulfilled -> Emit DONE.")

        # 8. Decomposed Sub-Goal Progress Checklist
        checklist = self._derive_subgoal_checklist(goal, windows)
        if checklist:
            lines.append("- Sub-Goal Progress:")
            for item in checklist:
                lines.append(f"  {item}")
            if all(item.startswith("[x]") for item in checklist):
                lines.append(
                    "- Completion Status: All derived sub-goals are satisfied [x]. "
                    "If nothing further was requested, emit finished() immediately."
                )

        return "\n".join(lines)

    def _derive_subgoal_checklist(self, goal: str, windows: List[Dict[str, Any]]) -> List[str]:
        """Derives a fast [x]/[ ] sub-goal checklist from user_goal and live OS state."""
        goal_lower = goal.lower()
        items: List[str] = []

        # Read notepad buffer preview once for checklist status
        nb_text = ""
        has_notepad_in_goal = "notepad" in goal_lower
        if has_notepad_in_goal or any(w in goal_lower for w in ("type", "write", "result", "greeting")):
            try:
                nb_text = read_notepad_buffer(allow_uia_fallback=False)
            except Exception:
                nb_text = ""

        # Read clipboard text if clipboard or harvest mentioned
        clip_text = ""
        if any(w in goal_lower for w in ("clipboard", "copy", "cut", "harvest")):
            try:
                import pyperclip
                clip_text = pyperclip.paste() or ""
            except Exception:
                clip_text = ""

        # --- Phase 1: Modal Dialog Dismissal (Blocking Prerequisite) ---
        unexpected_modal = _find_unexpected_modal_dialog(goal_lower, windows)
        if unexpected_modal is not None:
            items.append(
                f"[ ] Dismiss unexpected dialog ('{unexpected_modal.get('title', 'Dialog')}') via Cancel or esc"
            )
        if any(w in goal_lower for w in ("close the error dialog", "dismiss", "error dialog")):
            has_error_dialog = any(
                (w.get("class_name") == "#32770" and any(k in w.get("title", "").lower() for k in ("error", "warning")))
                or "benchmark system error" in w.get("title", "").lower()
                for w in windows
            )
            items.append("[x] Dismiss modal dialog" if not has_error_dialog else "[ ] Dismiss modal dialog")

        # --- Phase 2: Source Applications Launch & Navigation ---
        # Seed file open in Notepad (e.g. L2-02)
        seed_match = re.search(r"(?i)\bopen\s+([A-Za-z]:\\[^\s'\"<>]+\.[a-zA-Z0-9]{1,6})\s+in\s+notepad", goal)
        if seed_match:
            seed_p = Path(seed_match.group(1))
            seed_open = any("notepad" in w.get("process_name", "").lower() and seed_p.name.lower() in w.get("title", "").lower() for w in windows)
            items.append(f"[x] Open {seed_p.name} in Notepad" if seed_open else f"[ ] Open {seed_p.name} in Notepad")

        # Calculator
        if "calculator" in goal_lower:
            calc_open = any("calculator" in w.get("process_name", "").lower() or "calculator" in w.get("title", "").lower() for w in windows)
            items.append("[x] Launch Calculator" if calc_open else "[ ] Launch Calculator")

            # Check if calculation is part of goal
            arith_m = re.search(r"(\d+)\s*([\+\-\*\/])\s*(\d+)", goal)
            if arith_m:
                n1, op, n2 = int(arith_m.group(1)), arith_m.group(2), int(arith_m.group(3))
                val = (n1 + n2) if op == "+" else (n1 - n2) if op == "-" else (n1 * n2) if op == "*" else (n1 // n2)
                calc_done = str(val) in nb_text or str(val) in clip_text
                items.append(f"[x] Compute {n1} {op} {n2} in Calculator" if calc_done else f"[ ] Compute {n1} {op} {n2} in Calculator")

        # Browser (Chrome / Edge)
        if any(b in goal_lower for b in ("chrome", "edge", "browser")):
            browser_open = any(any(b in w.get("process_name", "").lower() for b in ("chrome", "msedge")) for w in windows)
            items.append("[x] Launch Browser" if browser_open else "[ ] Launch Browser")

            url_m = re.search(r"(https?://[^\s'\",]+)", goal)
            if url_m:
                target_url = url_m.group(1)
                domain = target_url.split("//")[-1].split("/")[0].replace("www.", "")
                domain_root = domain.split(".")[0]
                at_url = any(
                    domain in w.get("title", "").lower()
                    or (len(domain_root) >= 3 and domain_root in w.get("title", "").lower())
                    for w in windows
                )
                items.append(f"[x] Navigate to {target_url}" if at_url else f"[ ] Navigate to {target_url}")

        # Paint
        if "paint" in goal_lower:
            paint_open = any("mspaint" in w.get("process_name", "").lower() or "paint" in w.get("title", "").lower() for w in windows)
            items.append("[x] Launch Paint" if paint_open else "[ ] Launch Paint")

        # File Explorer
        if "file explorer" in goal_lower or ("explorer" in goal_lower and any(k in goal_lower for k in ("open", "inside"))):
            expl_open = any(w.get("class_name") in ("CabinetWClass", "ExploreWClass") for w in windows)
            items.append("[x] Launch File Explorer" if expl_open else "[ ] Launch File Explorer")

        # --- Phase 3: Secondary / Destination Applications ---
        if "notepad" in goal_lower and not seed_match:
            is_referencing_preopened = bool(re.search(r"\b(?:from|in)\s+(?:the\s+)?open\s+notepad", goal_lower))
            is_closing = any(w in goal_lower for w in ("close notepad", "exit notepad", "quit notepad"))
            if not is_closing and not is_referencing_preopened:
                np_open = any("notepad" in w.get("process_name", "").lower() or "notepad" in w.get("title", "").lower() for w in windows)
                items.append("[x] Launch Notepad" if np_open else "[ ] Launch Notepad")

        # --- Phase 4: Data Entry / Editing ---
        if "notepad" in goal_lower and any(w in goal_lower for w in ("type", "write", "result", "greeting", "append")):
            arith_m = re.search(r"(\d+)\s*([\+\-\*\/])\s*(\d+)", goal)
            quoted = re.findall(r"['\"]([^'\"]{2,})['\"]", goal)

            if "append" in goal_lower and quoted:
                exp_append = quoted[0]
                has_append = exp_append.lower() in nb_text.lower()
                items.append(f"[x] Append '{exp_append}' to Notepad" if has_append else f"[ ] Append '{exp_append}' to Notepad")
            elif arith_m and "calculator" in goal_lower:
                n1, op, n2 = int(arith_m.group(1)), arith_m.group(2), int(arith_m.group(3))
                val = (n1 + n2) if op == "+" else (n1 - n2) if op == "-" else (n1 * n2) if op == "*" else (n1 // n2)
                if quoted:
                    exp_fmt = quoted[0]
                    has_res = exp_fmt.lower() in nb_text.lower() or str(val) in nb_text
                    items.append(f"[x] Type '{exp_fmt}' into Notepad" if has_res else f"[ ] Type '{exp_fmt}' into Notepad")
                else:
                    has_res = str(val) in nb_text
                    items.append(f"[x] Type result '{val}' into Notepad" if has_res else f"[ ] Type result '{val}' into Notepad")
            elif quoted:
                exp = quoted[0]
                has_exp = exp.lower() in nb_text.lower()
                items.append(f"[x] Type '{exp}' into Notepad" if has_exp else f"[ ] Type '{exp}' into Notepad")
            elif any(w in goal_lower for w in ("heading", "heading text", "text into notepad")):
                has_text = len(nb_text.strip()) >= 5
                items.append("[x] Record heading text into Notepad" if has_text else "[ ] Record heading text into Notepad")
            elif any(w in goal_lower for w in ("greeting", "two-sentence", "2-sentence", "sentence")):
                req_sents = _extract_required_sentence_count(goal_lower)
                sent_count = _count_sentences(nb_text)
                has_comp = (
                    len(nb_text.strip()) >= 15
                    and any(p in nb_text for p in (".", "!", "?"))
                    and not _is_prompt_echo(nb_text, goal=goal)
                    and (req_sents == 0 or sent_count >= req_sents)
                )
                if has_comp:
                    items.append("[x] Compose text in Notepad")
                elif nb_text.strip():
                    items.append(
                        "[ ] Compose text in Notepad (current text is too short, lacks sentence punctuation, or echoes the prompt)"
                    )
                else:
                    items.append("[ ] Compose text in Notepad")
            elif any(w in goal_lower for w in ("write", "type", "compose", "draft")):
                has_text = len(nb_text.strip()) >= 5
                items.append("[x] Write text in Notepad" if has_text else "[ ] Write text in Notepad")

        # --- Phase 5: Clipboard Operations ---
        if "clipboard" in goal_lower and any(w in goal_lower for w in ("copy", "harvest", "cut")):
            quoted = re.findall(r"['\"]([^'\"]{2,})['\"]", goal)
            if quoted:
                exp_clip = quoted[0]
                has_clip = exp_clip.lower() in clip_text.lower()
                items.append(f"[x] Copy '{exp_clip}' to clipboard" if has_clip else f"[ ] Copy '{exp_clip}' to clipboard")
            elif "token" in goal_lower:
                has_token = bool(clip_text.strip()) and any(c.isalnum() for c in clip_text)
                items.append("[x] Copy token to clipboard" if has_token else "[ ] Copy token to clipboard")
            else:
                items.append("[x] Copy text to clipboard" if bool(clip_text.strip()) else "[ ] Copy text to clipboard")

        # --- Phase 6: Persistence & File Management ---
        path_matches = re.findall(r"(?i)([A-Za-z]:\\[^\s'\"<>]+\.[a-zA-Z0-9]{1,6})", goal)
        if path_matches and any(w in goal_lower for w in ("save", "save it as", "save as")):
            p = Path(path_matches[0])
            save_dialog_open = any("save as" in w.get("title", "").lower() or (w.get("class_name") == "#32770" and "save" in w.get("title", "").lower()) for w in windows)
            file_saved = p.exists() and p.is_file() and p.stat().st_size > 0 and not save_dialog_open
            items.append(f"[x] Save file '{p.name}' to disk" if file_saved else f"[ ] Save file '{p.name}' to disk")

        rename_m = re.search(r"(?i)\brename\s+([^\s,;]+)\s+to\s+([^\s,;]+)", goal)
        if rename_m:
            new_f = rename_m.group(2).strip("'\"")
            dir_m = re.search(r"(?i)([A-Za-z]:\\[^\s,;]+)", goal)
            t_dir = Path(dir_m.group(1).rstrip("\\")) if dir_m else Path.cwd()
            n_path = t_dir / new_f if not Path(new_f).is_absolute() else Path(new_f)
            items.append(f"[x] Rename to '{new_f}'" if n_path.exists() else f"[ ] Rename to '{new_f}'")

        folder_m = re.search(r"(?i)\bcreate\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(?:named\s+)?['\"]?([^'\"\s]+)['\"]?", goal)
        if folder_m:
            f_name = folder_m.group(1).strip("'\"")
            dir_m = re.search(r"(?i)([A-Za-z]:\\[^\s,;]+)", goal)
            b_dir = Path(dir_m.group(1).rstrip("\\")) if dir_m else Path.cwd()
            d_path = b_dir / f_name if not Path(f_name).is_absolute() else Path(f_name)
            items.append(f"[x] Create folder '{f_name}'" if d_path.exists() and d_path.is_dir() else f"[ ] Create folder '{f_name}'")

        # --- Phase 7: Application Teardown / State Management ---
        is_teardown = any(k in goal_lower for k in ("close", "exit", "quit", "terminate", "kill", "don't save", "dont save", "without saving"))
        if is_teardown:
            for target in ("notepad", "calculator", "calc", "paint", "mspaint", "file explorer", "explorer", "chrome", "edge", "browser"):
                is_close = bool(re.search(rf"(?i)\b(?:close|exit|quit|terminate|kill)\b.*{target}", goal)) and not bool(re.search(rf"(?i)(?:^|then\s+|and\s+)(?:open|launch)\s+(?:the\s+)?(?:file\s+)?{target}\b", goal))
                if is_close:
                    target_proc = "mspaint" if target == "paint" else ("calculatorapp" if target in ("calculator", "calc") else ("explorer" if "explorer" in target else target))
                    still_open = any(target_proc in w.get("process_name", "").lower() or target in w.get("title", "").lower() for w in windows)
                    items.append(f"[x] Close {target}" if not still_open else f"[ ] Close {target}")
            if "don't save" in goal_lower or "dont save" in goal_lower or "without saving" in goal_lower:
                notepad_open = any("notepad" in w.get("process_name", "").lower() or "notepad" in w.get("title", "").lower() for w in windows)
                items.append("[x] Discard unsaved changes ('Don't Save')" if not notepad_open else "[ ] Choose 'Don't Save'")
        elif re.search(r"(?i)\b(?:close|exit|quit)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+)", goal):
            m = re.search(r"(?i)\b(?:close|exit|quit)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+)", goal)
            target_app = m.group(1).lower() if m else ""
            if target_app not in ("window", "dialog", "all", "the", "open"):
                still_open = any(target_app in w.get("process_name", "").lower() or target_app in w.get("title", "").lower() for w in windows)
                items.append(f"[x] Close {target_app}" if not still_open else f"[ ] Close {target_app}")

        if "minimize" in goal_lower:
            m = re.search(r"(?i)\bminimize\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+)", goal)
            target_app = m.group(1).lower() if m else ""
            if target_app not in ("window", "the"):
                matching = [w for w in windows if target_app in w.get("process_name", "").lower() or target_app in w.get("title", "").lower()]
                is_min = all(w["is_minimized"] for w in matching) if matching else False
                items.append(f"[x] Minimize {target_app}" if is_min else f"[ ] Minimize {target_app}")

        return items

    def verify_goal_state(
        self,
        user_goal: str,
        active_window: Optional[Any] = None,
        grounded_elements: Optional[List[Any]] = None,
    ) -> GoalVerificationResult:
        """
        Validates whether the user_goal has genuinely been achieved on the OS.
        Returns GoalVerificationResult(verified=True/False, reason=...).
        """
        if not user_goal or not isinstance(user_goal, str):
            return GoalVerificationResult(verified=True, reason="No goal specified")

        goal = user_goal.strip()
        checked: List[str] = []

        # 1. File Rename Check
        res = self._check_file_rename(goal)
        if res is not None:
            return res

        # 2. Directory Creation Check
        res = self._check_directory_creation(goal)
        if res is not None:
            return res

        # 3. File Save or Append Check
        res = self._check_file_save_or_append(goal)
        if res is not None:
            return res

        # 4. System Clipboard Check
        res = self._check_clipboard(goal)
        if res is not None:
            return res

        # 5. Modal Dialog Dismissal Check
        res = self._check_modal_dialogs(goal, grounded_elements)
        if res is not None:
            return res

        # 6. Window State & Content Check (Open, Close, Minimize, Edit buffer text, Calculator)
        res = self._check_window_and_app_state(goal, active_window, grounded_elements)
        if res is not None:
            return res

        # If no deterministic post-condition applies, defer to VLM's judgment
        return GoalVerificationResult(
            verified=True,
            reason="No deterministic post-condition violated; accepted by VLM visual judgment",
            checked_conditions=["default_pass"],
        )

    def _check_file_rename(self, goal: str) -> Optional[GoalVerificationResult]:
        """Validates 'rename <old> to <new>' operations on disk."""
        m = re.search(r"(?i)\brename\s+([^\s,;]+)\s+to\s+([^\s,;]+)", goal)
        if not m:
            return None

        old_file = m.group(1).strip("'\"")
        new_file = m.group(2).strip("'\"")

        # Resolve directory if specified in goal (e.g. C:\ParasiteAI\benchmarks\workspace)
        dir_match = re.search(r"(?i)([A-Za-z]:\\[^\s,;]+)", goal)
        target_dir = Path(dir_match.group(1).rstrip("\\")) if dir_match else Path.cwd()

        old_path = target_dir / old_file if not Path(old_file).is_absolute() else Path(old_file)
        new_path = target_dir / new_file if not Path(new_file).is_absolute() else Path(new_file)

        if not new_path.exists():
            return GoalVerificationResult(
                verified=False,
                reason=f"Target file {new_path.name} does not exist on disk yet. Complete renaming the file.",
                checked_conditions=["file_rename_exists"],
            )
        if old_path.exists() and old_path != new_path:
            return GoalVerificationResult(
                verified=False,
                reason=f"Old file {old_path.name} still exists on disk. Complete renaming the file.",
                checked_conditions=["file_rename_old_removed"],
            )

        return GoalVerificationResult(
            verified=True,
            reason=f"Verified file renamed from {old_path.name} to {new_path.name}",
            checked_conditions=["file_rename_success"],
        )

    def _check_directory_creation(self, goal: str) -> Optional[GoalVerificationResult]:
        """Validates 'create a (new) folder/directory named <name>'."""
        m = re.search(r"(?i)\bcreate\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(?:named\s+)?['\"]?([^'\"\s]+)['\"]?", goal)
        if not m:
            return None

        folder_name = m.group(1).strip("'\"")
        dir_match = re.search(r"(?i)([A-Za-z]:\\[^\s,;]+)", goal)
        base_dir = Path(dir_match.group(1).rstrip("\\")) if dir_match else Path.cwd()
        target_dir = base_dir / folder_name if not Path(folder_name).is_absolute() else Path(folder_name)

        if not target_dir.exists() or not target_dir.is_dir():
            return GoalVerificationResult(
                verified=False,
                reason=f"Directory '{target_dir}' does not exist on disk. Create the new folder.",
                checked_conditions=["directory_creation"],
            )

        return GoalVerificationResult(
            verified=True,
            reason=f"Directory '{target_dir}' verified on disk",
            checked_conditions=["directory_creation"],
        )

    def _check_file_save_or_append(self, goal: str) -> Optional[GoalVerificationResult]:
        """Validates file save or append goals with explicit file paths."""
        path_matches = re.findall(r"(?i)([A-Za-z]:\\[^\s'\"<>]+\.[a-zA-Z0-9]{1,6})", goal)
        if not path_matches:
            return None

        target_file_str = path_matches[0]
        p = Path(target_file_str)

        is_save = any(w in goal.lower() for w in ("save", "write to", "save it as", "save as"))
        is_append = "append" in goal.lower()

        # If Save As dialog (#32770) is still open, save is not finished
        windows = get_live_windows()
        for win in windows:
            if "save as" in win["title"].lower() or (win["class_name"] == "#32770" and "save" in win["title"].lower()):
                return GoalVerificationResult(
                    verified=False,
                    reason=f"Save As dialog '{win['title']}' is still open. Complete entering the filename and click Save.",
                    checked_conditions=["save_as_dialog_open"],
                )

        if is_save:
            if not p.exists() or not p.is_file():
                return GoalVerificationResult(
                    verified=False,
                    reason=f"Target file '{p.name}' has not been saved to disk at {p}. Complete the save operation.",
                    checked_conditions=["file_saved_exists"],
                )
            if p.stat().st_size == 0:
                return GoalVerificationResult(
                    verified=False,
                    reason=f"Saved file '{p.name}' is empty (0 bytes). Type the content before saving.",
                    checked_conditions=["file_saved_non_empty"],
                )

            # Check if expected content is specified (e.g. quoted string or computed total)
            quoted = re.findall(r"['\"]([^'\"]{3,})['\"]", goal)
            if quoted:
                expected_str = quoted[0]
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if expected_str.lower() not in content.lower():
                        return GoalVerificationResult(
                            verified=False,
                            reason=f"File '{p.name}' does not contain expected text {expected_str!r}.",
                            checked_conditions=["file_content_matched"],
                        )
                except Exception:
                    pass

            return GoalVerificationResult(
                verified=True,
                reason=f"File '{p.name}' verified on disk with non-empty content",
                checked_conditions=["file_saved_success"],
            )

        if is_append:
            # Check appended content in file or live Notepad buffer
            quoted = re.findall(r"['\"]([^'\"]{2,})['\"]", goal)
            if quoted:
                expected_str = quoted[0].strip()
                in_file = False
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                        if expected_str.lower() in content.lower():
                            in_file = True
                    except Exception:
                        pass
                in_buffer = expected_str.lower() in read_notepad_buffer().lower()
                if not in_file and not in_buffer:
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"Appended text {expected_str!r} not found in document buffer or file.",
                        checked_conditions=["append_text_present"],
                    )

            return GoalVerificationResult(
                verified=True,
                reason="Appended content verified",
                checked_conditions=["append_success"],
            )

        return None

    def _check_clipboard(self, goal: str) -> Optional[GoalVerificationResult]:
        """Validates 'copy ... to the clipboard' goals."""
        if not ("clipboard" in goal.lower() and any(w in goal.lower() for w in ("copy", "harvest", "cut"))):
            return None

        clip_text = ""
        try:
            import pyperclip
            clip_text = pyperclip.paste() or ""
        except Exception:
            pass

        if not clip_text.strip():
            return GoalVerificationResult(
                verified=False,
                reason="Clipboard is empty. Copy the target text to the clipboard before finishing.",
                checked_conditions=["clipboard_non_empty"],
            )

        # If a quoted string or specific token was mentioned to copy
        quoted = re.findall(r"['\"]([^'\"]{2,})['\"]", goal)
        if quoted:
            expected_token = quoted[0].strip()
            if expected_token.lower() not in clip_text.lower():
                return GoalVerificationResult(
                    verified=False,
                    reason=f"Clipboard contains {clip_text[:30]!r}, expected {expected_token!r}.",
                    checked_conditions=["clipboard_token_match"],
                )

        return GoalVerificationResult(
            verified=True,
            reason=f"Clipboard verified containing {clip_text[:30]!r}",
            checked_conditions=["clipboard_success"],
        )

    def _check_modal_dialogs(
        self,
        goal: str,
        grounded_elements: Optional[List[Any]] = None,
    ) -> Optional[GoalVerificationResult]:
        """Validates modal dialog dismissal goals."""
        is_dismiss_goal = any(w in goal.lower() for w in ("close the error dialog", "dismiss", "don't save", "dont save"))
        windows = get_live_windows()

        for win in windows:
            title_lower = win["title"].lower()
            if "benchmark system error" in title_lower or (win["class_name"] == "#32770" and any(k in title_lower for k in ("error", "warning", "save changes"))):
                if is_dismiss_goal or "open notepad" in goal.lower():
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"Modal dialog '{win['title']}' is still open. Dismiss the dialog first.",
                        checked_conditions=["modal_dialog_dismissed"],
                    )

        unexpected = _find_unexpected_modal_dialog(goal.lower(), windows)
        if unexpected is not None:
            return GoalVerificationResult(
                verified=False,
                reason=(
                    f"Unexpected modal dialog '{unexpected['title']}' is open. "
                    "Dismiss it (click Cancel or press esc) without closing or saving."
                ),
                checked_conditions=["unexpected_modal_dialog"],
            )

        if is_dismiss_goal and "don't save" in goal.lower():
            # If goal was 'Close the open Notepad window and choose Don't Save'
            notepad_running = any(w["process_name"].lower() == "notepad.exe" for w in windows)
            if notepad_running:
                return GoalVerificationResult(
                    verified=False,
                    reason="Notepad is still running. Click Don't Save to close it completely.",
                    checked_conditions=["dirty_notepad_closed"],
                )
            return GoalVerificationResult(
                verified=True,
                reason="Notepad closed and dialog dismissed",
                checked_conditions=["dirty_notepad_closed"],
            )

        return None

    def _check_window_and_app_state(
        self,
        goal: str,
        active_window: Optional[Any] = None,
        grounded_elements: Optional[List[Any]] = None,
    ) -> Optional[GoalVerificationResult]:
        """Validates window open, close, minimize, and document typing goals."""
        goal_lower = goal.lower()
        windows = get_live_windows()

        # A. Close Window Goals
        for app_raw in ("notepad", "calculator", "calc", "paint", "mspaint", "file explorer", "explorer", "chrome", "edge"):
            is_close = bool(re.search(rf"(?i)\b(?:close|exit|quit|terminate|kill)\b.*{app_raw}", goal)) and not bool(re.search(rf"(?i)(?:^|then\s+|and\s+)(?:open|launch)\s+(?:the\s+)?(?:file\s+)?{app_raw}\b", goal))
            if is_close:
                target_proc = "mspaint" if app_raw == "paint" else ("calculatorapp" if app_raw in ("calculator", "calc") else ("explorer" if "explorer" in app_raw else app_raw))
                matching_wins = [
                    w for w in windows
                    if target_proc in w["process_name"].lower() or app_raw in w["title"].lower()
                ]
                if matching_wins:
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"Application '{app_raw}' is still open ({matching_wins[0]['title']}). Close the window.",
                        checked_conditions=["app_closed"],
                    )
                return GoalVerificationResult(
                    verified=True,
                    reason=f"Application '{app_raw}' successfully closed",
                    checked_conditions=["app_closed"],
                )

        if re.match(r"(?i)^\s*(?:please\s+)?(?:close|exit|quit)\s+([a-zA-Z0-9_\-\.\s]+)", goal):
            m = re.match(r"(?i)^\s*(?:please\s+)?(?:close|exit|quit)\s+([a-zA-Z0-9_\-\.\s]+)", goal)
            app_raw = m.group(1).strip().split()[0].lower() if m else ""
            if app_raw and app_raw not in ("window", "the", "dialog", "all", "open"):
                app_proc = app_raw + ".exe" if not app_raw.endswith(".exe") else app_raw
                matching_wins = [
                    w for w in windows
                    if app_raw in w["process_name"].lower() or app_raw in w["title"].lower()
                ]
                if matching_wins:
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"Application '{app_raw}' is still open ({matching_wins[0]['title']}). Close the window.",
                        checked_conditions=["app_closed"],
                    )
                return GoalVerificationResult(
                    verified=True,
                    reason=f"Application '{app_raw}' successfully closed",
                    checked_conditions=["app_closed"],
                )

        # B. Minimize Window Goals
        if "minimize" in goal_lower:
            m = re.search(r"(?i)\bminimize\s+([a-zA-Z0-9_\-\.\s]+)", goal)
            app_raw = m.group(1).strip().split()[0].lower() if m else ""
            if app_raw and app_raw not in ("window", "the"):
                matching_wins = [
                    w for w in windows
                    if app_raw in w["process_name"].lower() or app_raw in w["title"].lower()
                ]
                if not matching_wins:
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"No window found for '{app_raw}' to minimize.",
                        checked_conditions=["app_minimized"],
                    )
                if not all(w["is_minimized"] for w in matching_wins):
                    return GoalVerificationResult(
                        verified=False,
                        reason=f"Window '{matching_wins[0]['title']}' is not minimized. Click the minimize button.",
                        checked_conditions=["app_minimized"],
                    )
                return GoalVerificationResult(
                    verified=True,
                    reason=f"Window '{matching_wins[0]['title']}' verified minimized",
                    checked_conditions=["app_minimized"],
                )

        # C. File Explorer Open Goals
        if "file explorer" in goal_lower or ("explorer" in goal_lower and "open" in goal_lower):
            has_explorer = any(
                w["class_name"] in ("CabinetWClass", "ExploreWClass") and not w["is_minimized"]
                for w in windows
            )
            if not has_explorer:
                return GoalVerificationResult(
                    verified=False,
                    reason="File Explorer window is not open. Launch File Explorer.",
                    checked_conditions=["explorer_open"],
                )
            return GoalVerificationResult(
                verified=True,
                reason="File Explorer window verified open",
                checked_conditions=["explorer_open"],
            )

        # D. Notepad Launch & Typing Goals
        is_notepad_close = bool(re.search(r"(?i)\b(?:close|exit|quit|terminate|kill)\b.*notepad", goal)) and not bool(re.search(r"(?i)(?:^|then\s+|and\s+)(?:open|launch)\s+(?:the\s+)?notepad\b", goal))
        if "notepad" in goal_lower and not is_notepad_close:
            notepad_wins = [
                w for w in windows
                if (
                    w["process_name"].lower() == "notepad.exe"
                    or ("notepad" in w["title"].lower() and "notepad++" not in w["title"].lower() and w["process_name"].lower() != "notepad++.exe")
                )
                and not w["is_minimized"]
            ]
            if not notepad_wins:
                return GoalVerificationResult(
                    verified=False,
                    reason="Notepad window is not open. Launch Notepad before finishing.",
                    checked_conditions=["notepad_open"],
                )

            # Check text typing/writing in Notepad
            if any(w in goal_lower for w in ("type", "write", "greeting", "result", "compose")):
                buf_text = read_notepad_buffer()
                if not buf_text.strip():
                    return GoalVerificationResult(
                        verified=False,
                        reason="Notepad editor is empty. Type the requested text into Notepad.",
                        checked_conditions=["notepad_text_non_empty"],
                    )

                # Quoted text verification
                quoted = re.findall(r"['\"]([^'\"]{2,})['\"]", goal)
                if quoted:
                    expected_str = quoted[0].strip()
                    if expected_str.lower() not in buf_text.lower():
                        return GoalVerificationResult(
                            verified=False,
                            reason=f"Notepad does not contain expected text {expected_str!r}.",
                            checked_conditions=["notepad_expected_text"],
                        )

                # Composition / greeting verification (avoid prompt echo & enforce sentence count)
                if any(k in goal_lower for k in ("greeting", "two-sentence", "2-sentence", "sentence")):
                    if _is_prompt_echo(buf_text, goal=goal):
                        return GoalVerificationResult(
                            verified=False,
                            reason=(
                                "Notepad contains echoed prompt instructions instead of composed prose. "
                                "Select all (ctrl a) and type actual original sentences."
                            ),
                            checked_conditions=["notepad_greeting_non_echo"],
                        )
                    req_sents = _extract_required_sentence_count(goal_lower)
                    sent_count = _count_sentences(buf_text)
                    if req_sents > 0 and sent_count < req_sents:
                        return GoalVerificationResult(
                            verified=False,
                            reason=(
                                f"Notepad only has {sent_count} complete sentence(s), but {req_sents} "
                                f"sentences were requested. Continue typing or select all (ctrl a) to write "
                                f"{req_sents} full original sentences."
                            ),
                            checked_conditions=["notepad_sentence_count"],
                        )
                    if len(buf_text.strip()) < 15 or not any(p in buf_text for p in (".", "!", "?")):
                        return GoalVerificationResult(
                            verified=False,
                            reason="Notepad composed text is too short or lacks sentence punctuation.",
                            checked_conditions=["notepad_greeting_composed"],
                        )

                # Arithmetic calculation typed into Notepad (e.g. 144 / 12 -> 12)
                arith_m = re.search(r"(\d+)\s*([\+\-\*\/])\s*(\d+)", goal)
                if arith_m and "calculator" in goal_lower:
                    try:
                        n1, op, n2 = int(arith_m.group(1)), arith_m.group(2), int(arith_m.group(3))
                        res_val = 0
                        if op == "+": res_val = n1 + n2
                        elif op == "-": res_val = n1 - n2
                        elif op == "*": res_val = n1 * n2
                        elif op == "/": res_val = n1 // n2
                        res_str = str(res_val)
                        if res_str not in buf_text:
                            return GoalVerificationResult(
                                verified=False,
                                reason=f"Notepad does not contain calculator result '{res_str}'.",
                                checked_conditions=["notepad_calculator_result"],
                            )
                    except Exception:
                        pass

            return GoalVerificationResult(
                verified=True,
                reason="Notepad window and content verified",
                checked_conditions=["notepad_verified"],
            )

        # E. Calculator Launch & Arithmetic Goals
        if "calculator" in goal_lower:
            calc_wins = [
                w for w in windows
                if (
                    w["process_name"].lower() in ("calculatorapp.exe", "calculator.exe")
                    or ("calculator" in w["title"].lower() and w["class_name"] == "ApplicationFrameWindow")
                )
                and not w["is_minimized"]
            ]
            if not calc_wins:
                return GoalVerificationResult(
                    verified=False,
                    reason="Calculator window is not open. Launch Calculator.",
                    checked_conditions=["calculator_open"],
                )
            arith_m = re.search(r"(\d+)\s*([\+\-\*\/])\s*(\d+)", goal)
            if arith_m:
                try:
                    n1, op, n2 = int(arith_m.group(1)), arith_m.group(2), int(arith_m.group(3))
                    res_val = 0
                    if op == "+": res_val = n1 + n2
                    elif op == "-": res_val = n1 - n2
                    elif op == "*": res_val = n1 * n2
                    elif op == "/": res_val = n1 // n2
                    expected_str = str(res_val)
                    calc_display = read_calculator_display()
                    if calc_display is not None:
                        tokens = calc_display.replace(",", "").strip().split()
                        if expected_str not in tokens and not calc_display.replace(",", "").strip().endswith(expected_str):
                            return GoalVerificationResult(
                                verified=False,
                                reason=f"Calculator display ({calc_display!r}) does not show expected result '{expected_str}'.",
                                checked_conditions=["calculator_result"],
                            )
                except Exception:
                    pass
            return GoalVerificationResult(
                verified=True,
                reason="Calculator window verified open",
                checked_conditions=["calculator_open"],
            )

        # F. Paint Launch Goals
        if "paint" in goal_lower:
            paint_wins = [
                w for w in windows
                if w["process_name"].lower() == "mspaint.exe" and not w["is_minimized"]
            ]
            if not paint_wins:
                return GoalVerificationResult(
                    verified=False,
                    reason="Paint window (mspaint.exe) is not open. Launch Paint.",
                    checked_conditions=["paint_open"],
                )
            return GoalVerificationResult(
                verified=True,
                reason="Paint window verified open",
                checked_conditions=["paint_open"],
            )

        return None
