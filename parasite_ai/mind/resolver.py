"""
parasite_ai/mind/resolver.py - Universal Application & Desktop Target Resolver.

Provides generic multi-tier application launching and target resolution across Windows
without brittle application-specific hardcoding:
  - Tier 1: Search visible desktop icons, taskbar pins, and active windows via Set-of-Mark label matching.
  - Tier 2: Windows Start Search chord (Win key -> Type name -> Enter).
  - Tier 3: Run Dialog fallback (Win+R -> Type executable / alias -> Enter).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, List, Optional, Tuple

from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.ui.types import UIElement

logger = logging.getLogger(__name__)


class PrecisionAppMatcher:
    """
    High-precision fuzzy element matcher.
    Enforces word boundary regex, exact matching priority, and destructive verb disqualification.
    """

    NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}
    PREFERRED_ROLES = {
        "button", "listitem", "menuitem", "hyperlink", "image",
        "pane", "icon", "treeitem", "tabitem", "window",
    }

    @classmethod
    def score_match(cls, label: str, target: str) -> float:
        l_norm = label.strip().lower()
        t_norm = target.strip().lower()
        if not l_norm or not t_norm:
            return 0.0

        # Strip Windows Taskbar running-window suffixes (e.g. "App.exe - 1 running window")
        l_norm = re.sub(r"(?:\.exe)?\s*-\s*\d+\s+running\s+windows?$", "", l_norm)
        t_norm = re.sub(r"(?:\.exe)?\s*-\s*\d+\s+running\s+windows?$", "", t_norm)

        # Strip common Windows file extensions from shortcuts/executables
        l_norm = re.sub(r"\.(url|lnk|exe)$", "", l_norm)
        t_norm = re.sub(r"\.(url|lnk|exe)$", "", t_norm)

        # Level 1: Exact match (highest confidence)
        if l_norm == t_norm:
            return 1.0

        tokens = re.findall(r"[a-zA-Z0-9_\-\+#]+", l_norm)
        if not tokens:
            return 0.0

        # Invariant: Disqualify destructive/exit elements immediately
        words = set(re.findall(r"[a-zA-Z0-9]+", l_norm))
        if any(v in words or v in tokens for v in cls.NEGATIVE_VERBS):
            return 0.0

        # Level 2: Exact prefix match with token boundary (e.g. label="app title 2", target="app title")
        if (
            l_norm.startswith(t_norm + " ")
            or l_norm.startswith(t_norm + " -")
            or l_norm.startswith(t_norm + ":")
        ):
            return 0.95

        # Level 2b: Target prefix match with token boundary (e.g. target="app title 2", label="app title")
        if (
            t_norm.startswith(l_norm + " ")
            or t_norm.startswith(l_norm + " -")
            or t_norm.startswith(l_norm + ":")
        ):
            return 0.90

        # Level 2c: Normalized base match stripping numeric/version suffixes (e.g. "app title 2" vs "app title")
        l_base = re.sub(r"\s+\d+(\.\d+)*$", "", l_norm)
        t_base = re.sub(r"\s+\d+(\.\d+)*$", "", t_norm)
        if l_base and t_base and l_base == t_base:
            return 0.92

        # Level 2d: Spaceless / compound-word match (e.g. "compoundapp" vs "compound app 2", "editor++" vs "editor ++")
        l_compact = re.sub(r"[^a-z0-9\+#]", "", l_norm)
        t_compact = re.sub(r"[^a-z0-9\+#]", "", t_norm)
        l_base_compact = re.sub(r"[^a-z0-9\+#]", "", l_base)
        t_base_compact = re.sub(r"[^a-z0-9\+#]", "", t_base)
        if len(t_compact) >= 4 and len(l_compact) >= 4:
            if l_compact == t_compact or (l_base_compact and t_base_compact and l_base_compact == t_base_compact):
                return 0.90
            # Compound prefix match where target is at least 70% of the base label (e.g. "compoundapp" in "compoundapp2")
            # Invariant: Disallow prefix match if trailing remainder contains identifier symbols (+, #)
            # or domain extension suffixes (.net, net, io) that the target does not have
            if l_compact.startswith(t_compact) and len(t_compact) >= int(len(l_base_compact or l_compact) * 0.75):
                trailing_rem = l_compact[len(t_compact):]
                has_symbol_or_domain = any(c in trailing_rem for c in ("+", "#")) or trailing_rem in ("net", "dotnet", "io")
                if not has_symbol_or_domain:
                    return 0.88
            if t_compact.startswith(l_compact) and len(l_compact) >= int(len(t_base_compact or t_compact) * 0.75):
                trailing_rem = t_compact[len(l_compact):]
                has_symbol_or_domain = any(c in trailing_rem for c in ("+", "#")) or trailing_rem in ("net", "dotnet", "io")
                if not has_symbol_or_domain:
                    return 0.85

        # Level 3: Word boundary regex match (\b) with identifier suffix awareness
        lead_bound = r"\b" if re.match(r"^\w", t_norm) else r"(?<!\w)"
        if re.search(r"\w$", t_norm):
            # Invariant: word boundary cannot be immediately followed by '+', '#', or a period followed by alpha (e.g. .net)
            trail_bound = r"(?!\s*[\+\#]|\.[a-zA-Z]|\w)"
        else:
            # Trailing non-word characters (e.g. '+', '#'): standard \b fails because adjacent space/punct is non-word.
            # Require boundary not immediately followed by identical symbol or word character.
            trail_char = t_norm[-1]
            trail_bound = r"(?!" + re.escape(trail_char) + r"|\w)"
        pattern = lead_bound + re.escape(t_norm) + trail_bound
        if re.search(pattern, l_norm, re.IGNORECASE):
            # Positional score: earlier occurrence yields higher score
            idx = l_norm.find(t_norm)
            pos_ratio = max(0.0, 1.0 - (idx / max(1, len(l_norm))))
            return 0.80 + (0.10 * pos_ratio)

        # Level 3b: Multi-word token subset match ignoring filler articles (e.g. target="visual studio" vs label="Microsoft Visual Studio Code")
        stopwords = {"the", "of", "and", "in", "to", "a", "an", "for", "on", "at"}
        t_words = [w for w in re.findall(r"[a-z0-9\+#]+", t_norm) if w not in stopwords]
        l_words = [w for w in re.findall(r"[a-z0-9\+#]+", l_norm) if w not in stopwords]
        if len(t_words) >= 2 and len(l_words) >= 2 and l_words[0] == t_words[0] and len(t_words[0]) >= 4:
            if all(tw in l_words for tw in t_words):
                return 0.88

        # Rejection: Arbitrary substrings without word boundaries (e.g. 'art' in 'SmartScreen') score 0.0
        return 0.0

    @classmethod
    def find_best_element(
        cls, target: str, elements: List[UIElement], threshold: float = 0.80
    ) -> Optional[Tuple[UIElement, float]]:
        candidates: List[Tuple[UIElement, float]] = []
        for elem in elements:
            role = (elem.role or "").lower()
            if not any(r in role for r in cls.PREFERRED_ROLES):
                continue
            score = cls.score_match(elem.label or "", target)
            if score >= threshold:
                candidates.append((elem, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]


class UniversalAppResolver:
    """
    Generic application launcher and UI element resolver.
    Operates without hardcoded application dictionaries.
    Follows a deadlock-free 3-tier state machine:
      - Tier 1: Inspect active visible SOM elements via PrecisionAppMatcher (threshold=0.80).
      - Tier 2: Windows Start Search chord (Win -> Type target_app -> Enter).
      - Tier 3: Windows Run dialog fallback (Win+R -> Type target_app -> Enter).
      - Exhaustion: Emit ActionType.WAIT with diagnostic reasoning (no infinite loop).
    """

    DEFAULT_CADENCE_BUFFER_MS: float = 250.0

    def __init__(self, cadence_buffer_ms: float = DEFAULT_CADENCE_BUFFER_MS) -> None:
        self.cadence_buffer_ms: float = float(cadence_buffer_ms)
        self._target_app: Optional[str] = None
        self._start_search_attempts: int = 0
        self._search_opened: bool = False
        self._run_dialog_attempts: int = 0
        self._run_opened: bool = False

    @property
    def _last_attempted_app(self) -> Optional[str]:
        return self._target_app

    @_last_attempted_app.setter
    def _last_attempted_app(self, val: Optional[str]) -> None:
        self._target_app = val

    @property
    def cadence_buffer_s(self) -> float:
        return max(0.0, self.cadence_buffer_ms / 1000.0)

    def _sleep_cadence_buffer(self, cancellation_token: Optional[threading.Event] = None) -> bool:
        """Enforces cadence buffer. Returns True if interrupted by cancellation token."""
        if self.cadence_buffer_s <= 0.0:
            return False
        if cancellation_token is not None:
            return cancellation_token.wait(timeout=self.cadence_buffer_s)
        time.sleep(self.cadence_buffer_s)
        return False

    GENERIC_NON_APP_WORDS = {
        "it", "this", "that", "something", "window", "windows", "file", "folder", "menu",
        "game", "games", "app", "apps", "application", "applications",
        "program", "programs", "tool", "tools", "active", "active window",
        "with", "from", "all", "everything", "first", "here", "there", "again",
    }

    @classmethod
    def extract_target_app(cls, goal_or_intent: str) -> Optional[str]:
        """
        Extracts application name generically from natural language strings.
        Handles patterns like:
          - "open browser" -> "browser"
          - "play some game title" -> "game title"
          - "play game title 2" -> "game title 2"
          - "launch visual studio code and create a file" -> "visual studio code"
          - "start editor" -> "editor"
          - "run powershell" -> "powershell"
          - "open up notes" -> "notes"
          - "switch to terminal" -> "terminal"
        """
        if not goal_or_intent:
            return None

        text = goal_or_intent.strip()

        # Do not extract a launch target if the user goal is explicitly about closing or minimizing windows
        if re.match(r"(?i)^\s*(?:please\s+)?(?:close|minimize|minimise|hide|dismiss|exit|quit)\b", text):
            return None

        # Regex capturing generic verbs followed by target app name
        # Handles attached punctuation delimiters (e.g. "open visual studio code, then write code")
        # Supports "play", "play some", "play the game", etc.
        # Disallows conversational prepositions right after the verb (e.g. "start with ...", "start by ...")
        pattern = (
            r"(?i)\b(?:open|launch|start|run|play|switch\s+to|bring\s+up)\s+(?:up\s+)?"
            r"(?!(?:with|by|from|in|on|at|to|over|again)\b)"
            r"(?:(?:yourself|myself|himself|herself|ourselves|me|us)\s+)?"
            r"(?:some\s+)?"
            r"(?:the\s+|a\s+|an\s+)?(?:app(?:lication)?\s+|game\s+)?"
            r"([a-zA-Z0-9_\-\.\s\+#]+?)"
            r"(?:\s*(?:[,\.;:!?]+\s*|\s+)\b(?:and|then|to|with|without|in|for|please|on\s+your\s+own|by\s+yourself|autonomously|alone)\b|[,\.;:!?]+(?:\s+|$)|$)"
        )
        match = re.search(pattern, text)
        if match:
            app_candidate = match.group(1).strip(" ,.;:!?\t\n")
            # Strip any residual leading reflexive pronouns/quantifiers or trailing conversational/wildcard modifiers
            app_candidate = re.sub(
                r"(?i)^(?:(?:yourself|myself|himself|herself|ourselves|me|us|some|the|a|an)\s+)+",
                "",
                app_candidate,
            ).strip(" ,.;:!?\t\n")
            app_candidate = re.sub(
                r"(?i)\s+\b(?:on\s+your\s+own|by\s+yourself|without\s+(?:my|user|human|any)(?:\s+input)?|autonomously|alone|for\s+me|right\s+now|(?:or|of)\s+whatever|whatever|or\s+something(?:\s+like\s+that)?|and\s+stuff)\b.*$",
                "",
                app_candidate,
            ).strip(" ,.;:!?\t\n")
            cand_lower = app_candidate.lower()
            # Filter out generic non-app words or conversational clauses
            if (
                cand_lower not in cls.GENERIC_NON_APP_WORDS
                and not any(cand_lower.startswith(p) for p in ("with ", "by ", "from ", "active ", "all "))
            ):
                return app_candidate

        return None

    def resolve_launch_action(
        self,
        target_app: Optional[str],
        elements: List[UIElement],
        cancellation_token: Optional[threading.Event] = None,
    ) -> ActionPlan:
        """
        Resolves the optimal launch action for an application using multi-tier strategy.
        Enforces non-blocking millisecond checks against cancellation_token.
        Safely returns ActionPlan(action=ActionType.WAIT) if target_app is None or empty.
        """
        if not target_app or not isinstance(target_app, str) or not target_app.strip():
            return ActionPlan(
                action=ActionType.WAIT,
                wait_ms=500,
                reasoning="No target application identified for launch",
            )

        target_clean = target_app.strip().lower()

        # Reset state counters when switching to a different target_app
        if self._target_app is not None and self._target_app != target_clean:
            self.reset()
        self._target_app = target_clean

        # ------------------------------------------------------------------
        # Tier 0: If an open window matching target_app already exists on screen,
        # focus that open window instead of re-double-clicking a desktop shortcut!
        # ------------------------------------------------------------------
        open_win_elem = next(
            (
                e for e in elements
                if (e.window_title or "").strip().lower() not in ("program manager", "workerw", "desktop", "taskbar", "running applications", "")
                and (e.process_name or "").strip().lower() != "explorer.exe"
                and PrecisionAppMatcher.score_match(e.window_title or "", target_clean) >= 0.80
                and (e.label or "").strip().lower() not in ("close", "minimize", "minimise", "maximize", "maximise", "restore", "system")
            ),
            None,
        )
        if open_win_elem is not None:
            self.reset()
            return ActionPlan(
                action=ActionType.CLICK,
                target_id=open_win_elem.id,
                coordinates=(open_win_elem.center_x, open_win_elem.center_y),
                reasoning=f"Target window '{open_win_elem.window_title}' is already open on screen; focusing window instead of re-launching desktop shortcut",
            )

        # ------------------------------------------------------------------
        # Tier 1: Check Visible SOM Elements (Desktop icons, Taskbar, Open Windows)
        # ------------------------------------------------------------------
        best_match = PrecisionAppMatcher.find_best_element(target_clean, elements, threshold=0.80)
        if best_match:
            elem, score = best_match
            self.reset()
            w_norm = (elem.window_title or "").strip().lower()
            is_taskbar = w_norm in ("taskbar", "running applications") or "running window" in (elem.label or "").lower()
            # If element is a desktop icon (process_name is explorer.exe or role is ListItem on desktop), use DOUBLE_CLICK
            is_desktop_item = (
                not is_taskbar
                and (
                    elem.role == "ListItem"
                    or (
                        (elem.process_name or "").lower() == "explorer.exe"
                        and w_norm in ("program manager", "workerw", "desktop", "")
                    )
                )
            )
            action = ActionType.DOUBLE_CLICK if is_desktop_item else ActionType.CLICK
            return ActionPlan(
                action=action,
                target_id=elem.id,
                coordinates=(elem.center_x, elem.center_y),
                reasoning=f"Found visible '{elem.label}' ({elem.role}) matching '{target_app}'; {'double-clicking desktop icon' if is_desktop_item else 'clicking directly'}",
            )

        # ------------------------------------------------------------------
        # Check if Windows Run dialog is currently open on screen
        # ------------------------------------------------------------------
        run_edit = next(
            (
                e for e in elements
                if e.role == "Edit" and any(
                    kw in (e.label or "").lower()
                    for kw in ("open", "type the name of a program", "run")
                )
            ),
            None,
        )
        if run_edit:
            if " " in target_clean or self._run_dialog_attempts >= 1:
                # Windows Run dialog cannot execute multi-word targets without registered alias, or already failed
                self._run_opened = False
                self._run_dialog_attempts = 1
                return ActionPlan(
                    action=ActionType.HOTKEY,
                    keys=["esc"],
                    reasoning=f"Run dialog does not support multi-word target '{target_app}'; dismissing and falling back to Start Search",
                )
            self._run_opened = False
            self._run_dialog_attempts = 1
            return ActionPlan(
                action=ActionType.CLICK_AND_TYPE,
                target_id=run_edit.id,
                text=target_app,
                submit=True,
                reasoning=f"Run dialog detected; typing '{target_app}' and pressing Enter to execute",
            )

        # ------------------------------------------------------------------
        # Check if Start Menu search box is currently open and focused
        # ------------------------------------------------------------------
        # Start search box belongs to Windows Search / Taskbar, NOT File Explorer browsing folders
        search_edit = next(
            (
                e for e in elements
                if (e.role == "Edit" or "search" in (e.role or "").lower())
                and any(
                    kw in (e.label or "").lower()
                    for kw in ("search", "type here to search", "search box")
                )
                and (
                    not e.process_name
                    or (e.process_name or "").lower() in ("searchapp.exe", "searchhost.exe", "startmenuexperiencehost.exe")
                    or (
                        (e.process_name or "").lower() == "explorer.exe"
                        and (e.window_title or "").lower() in ("search", "start", "", "taskbar", "cortana")
                    )
                )
            ),
            None,
        )
        if search_edit:
            if self._search_opened:
                self._sleep_cadence_buffer(cancellation_token)
            self._search_opened = False
            self._start_search_attempts = 1
            return ActionPlan(
                action=ActionType.CLICK_AND_TYPE,
                target_id=search_edit.id,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Start Search box detected; typing '{target_app}' and pressing Enter to launch",
            )

        # ------------------------------------------------------------------
        # Tier 2: Windows Start Search Chord (Win Key)
        # ------------------------------------------------------------------
        if self._start_search_attempts == 0 and not self._search_opened:
            self._search_opened = True
            return ActionPlan(
                action=ActionType.HOTKEY,
                keys=["win"],
                wait_ms=int(self.cadence_buffer_ms),
                reasoning=f"Tier 2 Universal Launch: Triggering Windows Start Search for '{target_app}' via Win key",
            )

        if self._search_opened:
            self._search_opened = False
            self._start_search_attempts = 1
            self._sleep_cadence_buffer(cancellation_token)
            return ActionPlan(
                action=ActionType.TYPE,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Tier 2 Universal Launch: Typing '{target_app}' into active Start Search and pressing Enter",
            )

        # ------------------------------------------------------------------
        # Tier 3: Windows Run Dialog Fallback Transition (Win+R)
        # ------------------------------------------------------------------
        if self._start_search_attempts >= 1:
            if self._run_dialog_attempts == 0 and not self._run_opened:
                self._run_opened = True
                return ActionPlan(
                    action=ActionType.HOTKEY,
                    keys=["win", "r"],
                    wait_ms=int(self.cadence_buffer_ms),
                    reasoning=f"Tier 3 Universal Launch: Triggering Run dialog (Win+R) to launch '{target_app}'",
                )

            if self._run_opened:
                self._run_opened = False
                self._run_dialog_attempts = 1
                self._sleep_cadence_buffer(cancellation_token)
                return ActionPlan(
                    action=ActionType.TYPE,
                    text=f"{target_app}\n",
                    submit=True,
                    reasoning=f"Tier 3 Universal Launch: Typing '{target_app}' into active Run dialog and pressing Enter",
                )

        # ------------------------------------------------------------------
        # Exhaustion: Both Tier 2 and Tier 3 have been attempted
        # ------------------------------------------------------------------
        return ActionPlan(
            action=ActionType.WAIT,
            wait_ms=500,
            reasoning=f"Resolution exhausted: Both Tier 2 (Start search) and Tier 3 (Win+R) failed to launch '{target_app}'. Escalating to cognitive replan.",
        )

    def reset(self) -> None:
        """Reset internal search/run state."""
        self._target_app = None
        self._start_search_attempts = 0
        self._search_opened = False
        self._run_dialog_attempts = 0
        self._run_opened = False
