import re
from typing import List, Optional, Tuple
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.ui.types import UIElement

class PrecisionAppMatcher:
    NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}
    PREFERRED_ROLES = {"button", "listitem", "menuitem", "hyperlink", "image", "pane", "icon", "treeitem", "tabitem", "window"}

    @classmethod
    def score_match(cls, label: str, target: str) -> float:
        l_norm = label.strip().lower()
        t_norm = target.strip().lower()
        if not l_norm or not t_norm:
            return 0.0

        # Exact match
        if l_norm == t_norm:
            return 1.0

        # Word tokens
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", l_norm)
        if not tokens:
            return 0.0

        # Check negative verb penalty
        if any(v in tokens for v in cls.NEGATIVE_VERBS):
            return 0.0  # Immediately disqualify destructive action elements like "Exit Notepad"

        # Check if starts with target (e.g. "Notepad - Untitled")
        if l_norm.startswith(t_norm + " ") or l_norm.startswith(t_norm + " -") or l_norm.startswith(t_norm + ":"):
            return 0.95

        # Word boundary regex search
        pattern = r"\b" + re.escape(t_norm) + r"\b"
        if re.search(pattern, l_norm, re.IGNORECASE):
            # Positional score: prefer matches where target appears earlier
            idx = l_norm.find(t_norm)
            pos_ratio = max(0.0, 1.0 - (idx / max(1, len(l_norm))))
            return 0.80 + (0.10 * pos_ratio)

        return 0.0

    @classmethod
    def find_best_element(cls, target: str, elements: List[UIElement], threshold: float = 0.80) -> Optional[Tuple[UIElement, float]]:
        candidates = []
        for elem in elements:
            role = (elem.role or "").lower()
            if not any(r in role for r in cls.PREFERRED_ROLES):
                continue
            score = cls.score_match(elem.label or "", target)
            if score >= threshold:
                candidates.append((elem, score))
        if not candidates:
            return None
        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

class RemediatedUniversalAppResolver:
    def __init__(self, cadence_buffer_ms: float = 250.0) -> None:
        self.cadence_buffer_ms = cadence_buffer_ms
        self._target_app: Optional[str] = None
        self._start_search_attempts: int = 0
        self._search_opened: bool = False
        self._run_dialog_attempts: int = 0
        self._run_opened: bool = False

    def reset(self) -> None:
        self._target_app = None
        self._start_search_attempts = 0
        self._search_opened = False
        self._run_dialog_attempts = 0
        self._run_opened = False

    def resolve_launch_action(self, target_app: str, elements: List[UIElement]) -> ActionPlan:
        target_clean = target_app.strip().lower()
        if not target_clean:
            return ActionPlan(action=ActionType.WAIT, wait_ms=500, reasoning="No target application identified")

        # App change detection
        if self._target_app != target_clean:
            self.reset()
            self._target_app = target_clean

        # ------------------------------------------------------------------
        # Tier 1: Grounded Icon & Element Match via Precision Matcher
        # ------------------------------------------------------------------
        best = PrecisionAppMatcher.find_best_element(target_clean, elements)
        if best:
            elem, score = best
            return ActionPlan(
                action=ActionType.CLICK,
                target_id=elem.id,
                reasoning=f"Found visible '{elem.label}' ({elem.role}) matching '{target_app}' (score={score:.2f}); clicking directly",
            )

        # ------------------------------------------------------------------
        # Check active dialogs on screen
        # ------------------------------------------------------------------
        run_edit = next(
            (e for e in elements if e.role == "Edit" and any(kw in (e.label or "").lower() for kw in ("open", "type the name of a program", "run"))),
            None,
        )
        if run_edit:
            self._run_opened = False
            self._run_dialog_attempts += 1
            return ActionPlan(
                action=ActionType.CLICK_AND_TYPE,
                target_id=run_edit.id,
                text=target_app,
                submit=True,
                reasoning=f"Run dialog detected; typing '{target_app}' and pressing Enter",
            )

        search_edit = next(
            (e for e in elements if (e.role == "Edit" or "search" in (e.role or "").lower()) and any(kw in (e.label or "").lower() for kw in ("search", "type here to search", "search box"))),
            None,
        )
        if search_edit:
            self._search_opened = False
            self._start_search_attempts += 1
            return ActionPlan(
                action=ActionType.CLICK_AND_TYPE,
                target_id=search_edit.id,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Start Search box detected; typing '{target_app}' and pressing Enter",
            )

        # ------------------------------------------------------------------
        # Tier 2: Windows Start Search Chord (Max 1 full attempt: Win -> Type)
        # ------------------------------------------------------------------
        if self._start_search_attempts == 0:
            if not self._search_opened:
                self._search_opened = True
                return ActionPlan(
                    action=ActionType.HOTKEY,
                    keys=["win"],
                    wait_ms=int(self.cadence_buffer_ms),
                    reasoning=f"Tier 2 Universal Launch: Triggering Windows Start Search for '{target_app}' via Win key",
                )
            else:
                self._search_opened = False
                self._start_search_attempts += 1
                return ActionPlan(
                    action=ActionType.TYPE,
                    text=f"{target_app}\n",
                    submit=True,
                    reasoning=f"Tier 2 Universal Launch: Typing '{target_app}' into active Start Search and pressing Enter",
                )

        # ------------------------------------------------------------------
        # Tier 3: Run Dialog Fallback (Max 1 full attempt: Win+R -> Type)
        # ------------------------------------------------------------------
        if self._run_dialog_attempts == 0:
            if not self._run_opened:
                self._run_opened = True
                return ActionPlan(
                    action=ActionType.HOTKEY,
                    keys=["win", "r"],
                    wait_ms=int(self.cadence_buffer_ms),
                    reasoning=f"Tier 3 Universal Launch: Triggering Run dialog (Win+R) to launch '{target_app}'",
                )
            else:
                self._run_opened = False
                self._run_dialog_attempts += 1
                return ActionPlan(
                    action=ActionType.TYPE,
                    text=f"{target_app}\n",
                    submit=True,
                    reasoning=f"Tier 3 Universal Launch: Typing '{target_app}' into Run dialog and pressing Enter",
                )

        # ------------------------------------------------------------------
        # All Tiers Exhausted
        # ------------------------------------------------------------------
        return ActionPlan(
            action=ActionType.WAIT,
            wait_ms=500,
            reasoning=f"UniversalAppResolver exhausted all 3 tiers for '{target_app}'; escalating to cognitive replan",
        )

if __name__ == "__main__":
    # Test Tier 1 Precision Matching
    elems = [
        UIElement(id=1, role="Button", label="SmartScreen", x=0, y=0, width=50, height=20, center_x=25, center_y=10),
        UIElement(id=2, role="Button", label="Certificate Manager", x=0, y=0, width=50, height=20, center_x=25, center_y=10),
        UIElement(id=3, role="MenuItem", label="Exit Notepad", x=0, y=0, width=50, height=20, center_x=25, center_y=10),
        UIElement(id=4, role="Button", label="Notepad", x=0, y=0, width=50, height=20, center_x=25, center_y=10),
    ]

    # Query "art" -> must NOT match SmartScreen
    assert PrecisionAppMatcher.find_best_element("art", elems) is None
    print("Precision Test 1 Passed: 'art' does NOT match 'SmartScreen'")

    # Query "cat" -> must NOT match Certificate Manager
    assert PrecisionAppMatcher.find_best_element("cat", elems) is None
    print("Precision Test 2 Passed: 'cat' does NOT match 'Certificate Manager'")

    # Query "notepad" -> must match id=4 ("Notepad"), NOT id=3 ("Exit Notepad")
    res_np = PrecisionAppMatcher.find_best_element("notepad", elems)
    assert res_np is not None and res_np[0].id == 4
    print("Precision Test 3 Passed: 'notepad' matches 'Notepad' (id=4), rejecting 'Exit Notepad'")

    # Test Tier 2 -> Tier 3 transition trajectory
    resolver = RemediatedUniversalAppResolver()
    trajectory = []
    for step in range(5):
        plan = resolver.resolve_launch_action("custom_app", [])
        trajectory.append((plan.action.value, plan.keys, plan.text))
    print("Resolver Trajectory across 5 steps:")
    for i, t in enumerate(trajectory):
        print(f"  Step {i+1}: action={t[0]}, keys={t[1]}, text={t[2]!r}")

    assert trajectory[0][0].upper() == "HOTKEY" and trajectory[0][1] == ["win"]
    assert trajectory[1][0].upper() == "TYPE" and trajectory[1][2] == "custom_app\n"
    assert trajectory[2][0].upper() == "HOTKEY" and trajectory[2][1] == ["win", "r"]
    assert trajectory[3][0].upper() == "TYPE" and trajectory[3][2] == "custom_app\n"
    assert trajectory[4][0].upper() == "WAIT"
    print("Tier 3 Fallback Transition Test Passed: Clean progression Tier 2 -> Tier 3 -> Exhausted!")
