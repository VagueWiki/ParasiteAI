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

        # Level 2: Exact prefix match with token boundary
        if (
            l_norm.startswith(t_norm + " ")
            or l_norm.startswith(t_norm + " -")
            or l_norm.startswith(t_norm + ":")
        ):
            return 0.95

        # Level 3: Word boundary regex match (\b)
        lead_bound = r"\b" if re.match(r"^\w", t_norm) else r"(?<!\w)"
        if re.search(r"\w$", t_norm):
            trail_bound = r"\b"
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

    @staticmethod
    def extract_target_app(goal_or_intent: str) -> Optional[str]:
        """
        Extracts application name generically from natural language strings.
        Handles patterns like:
          - "open discord" -> "discord"
          - "launch visual studio code and create a file" -> "visual studio code"
          - "start spotify" -> "spotify"
          - "run powershell" -> "powershell"
          - "open up obsidian" -> "obsidian"
          - "switch to notepad" -> "notepad"
        """
        if not goal_or_intent:
            return None

        text = goal_or_intent.strip()
        
        # Regex capturing generic verbs followed by target app name
        # Handles attached punctuation delimiters (e.g. "open visual studio code, then write code")
        pattern = (
            r"(?i)\b(?:open|launch|start|run|switch\s+to|bring\s+up)\s+(?:up\s+)?"
            r"(?:the\s+|a\s+|an\s+)?(?:app(?:lication)?\s+)?"
            r"([a-zA-Z0-9_\-\.\s\+#]+?)"
            r"(?:\s*(?:[,\.;:!?]+\s*|\s+)(?:and|then|to|with|in|for|please|$)|[,\.;:!?]+(?:\s+|$)|$)"
        )
        match = re.search(pattern, text)
        if match:
            app_candidate = match.group(1).strip(" ,.;:!?\t\n")
            # Filter out generic non-app words
            if app_candidate.lower() not in {"it", "this", "that", "something", "window", "file", "folder", "menu"}:
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
        # Tier 1: Check Visible SOM Elements (Desktop icons, Taskbar, Open Windows)
        # ------------------------------------------------------------------
        best_match = PrecisionAppMatcher.find_best_element(target_clean, elements, threshold=0.80)
        if best_match:
            elem, score = best_match
            self.reset()
            return ActionPlan(
                action=ActionType.CLICK,
                target_id=elem.id,
                coordinates=(elem.center_x, elem.center_y),
                reasoning=f"Found visible '{elem.label}' ({elem.role}) matching '{target_app}'; clicking directly",
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
        search_edit = next(
            (
                e for e in elements
                if (e.role == "Edit" or "search" in (e.role or "").lower())
                and any(
                    kw in (e.label or "").lower()
                    for kw in ("search", "type here to search", "search box")
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
