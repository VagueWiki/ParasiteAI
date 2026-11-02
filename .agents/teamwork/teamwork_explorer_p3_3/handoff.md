# Investigation Report: Requirement R3 (Phase 3C: Start Search Cadence Buffer) & R4 (Test Suite Status)

**Working Directory:** `C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_3\`  
**Date:** 2026-10-31  
**Archetype:** Explorer  
**Scope:** Phase 3C (Start Search Cadence Buffer in `UniversalAppResolver`) & Phase 3D/R4 (Test Suite Regression Status)

---

## 1. Observation

### 1.1 Existing Test Suite Status (Requirement R4)
The full test suite was executed against the project virtual environment via:
```powershell
& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest
```
**Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0 -- C:\ParasiteAI\.venv\Scripts\python.exe
cachedir: .pytest_cache
PyQt6 6.12.0 -- Qt runtime 6.12.0 -- Qt compiled 6.12.0
rootdir: C:\ParasiteAI
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.1, mock-3.17.0, qt-4.5.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 797 items

... (all intermediate test modules passing) ...

tests/test_window_guard.py::TestWindowGuardAPIAndDataModels::test_get_active_window_and_is_safe_to_operate PASSED [100%]

======================= 797 passed in 127.80s (0:02:07) =======================
```
- **Total tests collected:** 797
- **Total tests passed:** 797 (100% pass rate)
- **Failures / Errors / Regressions:** 0
- **Duration:** 127.80s

### 1.2 Inspection of `parasite_ai/mind/resolver.py` (`UniversalAppResolver`)
Lines 23–33 of `parasite_ai/mind/resolver.py`:
```python
class UniversalAppResolver:
    """
    Generic application launcher and UI element resolver.
    Operates without hardcoded application dictionaries.
    """

    def __init__(self) -> None:
        self._last_attempted_app: Optional[str] = None
        self._search_opened: bool = False
        self._run_opened: bool = False
```

Lines 144–164 of `parasite_ai/mind/resolver.py` (Tier 2 Windows Start Search Chord):
```python
        # ------------------------------------------------------------------
        # Tier 2: Windows Start Search Chord (Win Key)
        # ------------------------------------------------------------------
        if not self._search_opened:
            self._search_opened = True
            self._last_attempted_app = target_app
            return ActionPlan(
                action=ActionType.HOTKEY,
                keys=["win"],
                reasoning=f"Tier 2 Universal Launch: Triggering Windows Start Search for '{target_app}' via Win key",
            )

        if self._search_opened:
            self._search_opened = False
            return ActionPlan(
                action=ActionType.TYPE,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Tier 2 Universal Launch: Typing '{target_app}' into active Start Search and pressing Enter",
            )
```

Lines 123–142 of `parasite_ai/mind/resolver.py` (Start Search box detection):
```python
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
            self._search_opened = False
            return ActionPlan(
                action=ActionType.CLICK_AND_TYPE,
                target_id=search_edit.id,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Start Search box detected; typing '{target_app}' and pressing Enter to launch",
            )
```

Key observations on `resolver.py`:
1. `resolver.py` does not import `time` and does not import `KeyboardDriver`.
2. There is zero pause, delay, or cadence buffer between setting `self._search_opened = True` and emitting the `ActionType.TYPE` command on the subsequent invocation.
3. The method signature is:
   ```python
   def resolve_launch_action(self, target_app: str, elements: List[UIElement]) -> ActionPlan:
   ```
4. `UniversalAppResolver` has no constructor arguments (`__init__(self) -> None`).

### 1.3 Inspection of `parasite_ai/mind/dual_mind.py` Integration
Lines 597 and 801–810 of `parasite_ai/mind/dual_mind.py`:
- `self.resolver = UniversalAppResolver()` is instantiated with no parameters in `DualMindPipeline.__init__`.
- In `DualMindPipeline.step()`, when an app launch is needed:
  ```python
  action_plan = self.resolver.resolve_launch_action(
      target_app=target_app,
      elements=elements,
  )
  ```
- Then `action_res = self.action_dispatcher.dispatch(action=action_plan, som_elements=elements, cancellation_token=token)`.
- In `ActionDispatcher.dispatch()`:
  - `ActionType.HOTKEY` calls `self.keyboard_driver.hotkey(*keys, cancellation_token=cancellation_token)`. It does NOT consult or sleep for `action.wait_ms`.
  - `ActionType.TYPE` calls `self.keyboard_driver.type_text(...)`.
  - `ActionType.CLICK_AND_TYPE` calls `self.keyboard_driver.click_and_type(...)`.
  - `ActionType.WAIT` is the only action where `ActionDispatcher` performs `time.sleep(wait_sec)` or `cancellation_token.wait(wait_sec)`.

### 1.4 Inspection of `tests/test_resolver.py`
Lines 73–87 of `tests/test_resolver.py`:
```python
def test_tier2_start_chord_sequence() -> None:
    resolver = UniversalAppResolver()
    elements: list[UIElement] = []

    # First step: Trigger Start Search via Win key
    action1 = resolver.resolve_launch_action("davinci resolve", elements)
    assert action1.action == ActionType.HOTKEY
    assert action1.keys == ["win"]

    # Second step: Start search is now active -> types application name and presses Enter
    action2 = resolver.resolve_launch_action("davinci resolve", elements)
    assert action2.action == ActionType.TYPE
    assert "davinci resolve\n" in (action2.text or "")
    assert action2.submit is True
```
- Existing tests in `tests/test_resolver.py` (5 tests) run synchronously and pass in 0.59s.
- `test_tier2_start_chord_sequence` invokes `resolve_launch_action` twice sequentially without mocking time.

---

## 2. Logic Chain

1. **Root Cause of Character Dropping:**
   - In Windows 10/11, pressing the `Win` key signals the Windows Shell (`explorer.exe` / `SearchHost.exe` / `StartMenuExperienceHost.exe`) to display the Start Menu search interface and activate input focus.
   - Initializing the XAML/DirectX search surface and focusing its caret takes approximately 100–200ms.
   - If keystrokes are sent immediately after the `Win` hotkey without waiting, the initial characters (e.g. the "n-o-t" in "notepad") are dropped by the OS before the search input control is ready.

2. **Placement of the 250ms Buffer:**
   - The requirement R3 explicitly states:
     > *"Implement a 250ms cadence buffer in `parasite_ai/mind/resolver.py` (`UniversalAppResolver`) after the `Win` key chord before typing application names to avoid dropping characters while the Windows Search UI initializes."*
     > *"A 250ms cadence pause is enforced in `parasite_ai/mind/resolver.py` between the `Win` key trigger and typing the target application name."*
   - In `UniversalAppResolver`, Tier 2 operates as a two-phase state machine:
     - Phase 1 (`not self._search_opened`): Emits `ActionType.HOTKEY` with `keys=["win"]` and sets `self._search_opened = True`.
     - Phase 2 (`self._search_opened` is `True`): Emits `ActionType.TYPE` with `text=f"{target_app}\n"` and resets `self._search_opened = False`.
   - Therefore, the cadence pause must be enforced at the transition point when `self._search_opened` is `True`, immediately before returning the `ActionPlan(action=ActionType.TYPE, ...)` plan (and also if `search_edit` is detected while `self._search_opened` is `True`).

3. **Mechanism for Timing:**
   - `UniversalAppResolver` should support a configurable parameter `cadence_buffer_ms: float = 250.0` (with class default `DEFAULT_CADENCE_BUFFER_MS = 250.0`).
   - Timing should be implemented via `time.sleep(self.cadence_buffer_s)` (where `cadence_buffer_s = self.cadence_buffer_ms / 1000.0`).
   - To preserve sub-2ms preemption invariants, `resolve_launch_action` can optionally accept `cancellation_token: Optional[threading.Event] = None`:
     ```python
     def _cadence_sleep(self, cancellation_token: Optional[threading.Event] = None) -> bool:
         if self.cadence_buffer_s <= 0:
             return False
         if cancellation_token is not None:
             return cancellation_token.wait(timeout=self.cadence_buffer_s)
         time.sleep(self.cadence_buffer_s)
         return False
     ```
   - In addition, setting `wait_ms=int(self.cadence_buffer_ms)` in the Phase 1 `HOTKEY` `ActionPlan` self-documents the intent in episodic memory and living plan records.

4. **Testing and Mock Strategy:**
   - `unittest.mock.patch("parasite_ai.mind.resolver.time.sleep")` allows unit tests to:
     a. Verify `mock_sleep.assert_called_once_with(0.25)` during the Tier 2 chord sequence.
     b. Verify that custom buffer parameters (e.g., 500ms -> `0.5s`, 0ms -> no sleep) work as expected.
     c. Keep unit tests executing in <1ms without introducing artificial 250ms delays in test suites.

---

## 3. Caveats

1. **DualMindPipeline Step Boundaries:**
   In real end-to-end execution, `DualMindPipeline.step()` processes one action per cycle. In live environments, the time between step 1 (`HOTKEY win`) and step 2 (`TYPE app`) includes screen capture and perception latency (~20–80ms). Enforcing `time.sleep(0.25)` inside `resolve_launch_action` guarantees that even on ultra-fast machines or under mock perception conditions, the search UI receives the full 250ms cadence buffer.
2. **Existing Test `test_tier2_start_chord_sequence`:**
   In `tests/test_resolver.py`, `test_tier2_start_chord_sequence` currently runs unmocked. If `time.sleep(0.25)` is introduced without mocking in that specific test, the test will take ~0.25s longer. To keep unit test execution blazing fast, the test should either patch `time.sleep` or initialize `resolver = UniversalAppResolver(cadence_buffer_ms=0)` while a dedicated new test explicitly verifies the 250ms sleep.
3. **No External Process Dependency:**
   The buffer is purely time-based (cadence buffer) as specified in R3. It does not poll Windows internal UI Automation or hook Windows Search UI private threads, which preserves strict anti-hardcoding and portability.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Implementation in `parasite_ai/mind/resolver.py`

#### A. Imports & Constants
```python
import logging
import re
import threading
import time
from typing import Any, List, Optional
```

#### B. Class Definition & Initialization
```python
class UniversalAppResolver:
    """
    Generic application launcher and UI element resolver.
    Operates without hardcoded application dictionaries.
    """
    DEFAULT_CADENCE_BUFFER_MS: float = 250.0

    def __init__(self, cadence_buffer_ms: float = DEFAULT_CADENCE_BUFFER_MS) -> None:
        self.cadence_buffer_ms: float = float(cadence_buffer_ms)
        self._last_attempted_app: Optional[str] = None
        self._search_opened: bool = False
        self._run_opened: bool = False

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
```

#### C. `resolve_launch_action` Cadence Enforcement
```python
    def resolve_launch_action(
        self,
        target_app: str,
        elements: List[UIElement],
        cancellation_token: Optional[threading.Event] = None,
    ) -> ActionPlan:
        # ... (Tier 1 icon / window search unchanged) ...

        # ... (Run dialog check unchanged) ...

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
        if not self._search_opened:
            self._search_opened = True
            self._last_attempted_app = target_app
            return ActionPlan(
                action=ActionType.HOTKEY,
                keys=["win"],
                wait_ms=int(self.cadence_buffer_ms),
                reasoning=f"Tier 2 Universal Launch: Triggering Windows Start Search for '{target_app}' via Win key",
            )

        if self._search_opened:
            self._search_opened = False
            self._sleep_cadence_buffer(cancellation_token)
            return ActionPlan(
                action=ActionType.TYPE,
                text=f"{target_app}\n",
                submit=True,
                reasoning=f"Tier 2 Universal Launch: Typing '{target_app}' into active Start Search and pressing Enter",
            )
```

### 4.2 Test Suite Additions in `tests/test_resolver.py`

Add the following targeted tests to `tests/test_resolver.py`:

```python
from unittest.mock import patch

def test_tier2_start_chord_cadence_buffer_enforced(mocker) -> None:
    """Verifies that 250ms cadence buffer is enforced prior to typing into Start Search."""
    mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
    resolver = UniversalAppResolver()
    elements: list[UIElement] = []

    # Step 1: Win hotkey triggered, no sleep yet
    action1 = resolver.resolve_launch_action("notepad", elements)
    assert action1.action == ActionType.HOTKEY
    assert action1.keys == ["win"]
    assert action1.wait_ms == 250
    mock_sleep.assert_not_called()

    # Step 2: Search active -> sleep(0.25) must be called before returning TYPE
    action2 = resolver.resolve_launch_action("notepad", elements)
    assert action2.action == ActionType.TYPE
    assert "notepad\n" in (action2.text or "")
    mock_sleep.assert_called_once_with(0.25)


def test_tier2_custom_cadence_buffer(mocker) -> None:
    """Verifies configurable cadence buffer duration."""
    mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
    resolver = UniversalAppResolver(cadence_buffer_ms=500.0)
    elements: list[UIElement] = []

    resolver.resolve_launch_action("calc", elements)
    mock_sleep.assert_not_called()

    resolver.resolve_launch_action("calc", elements)
    mock_sleep.assert_called_once_with(0.5)


def test_tier2_zero_cadence_buffer_skips_sleep(mocker) -> None:
    """Verifies cadence buffer of 0 skips sleep calls."""
    mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
    resolver = UniversalAppResolver(cadence_buffer_ms=0.0)
    elements: list[UIElement] = []

    resolver.resolve_launch_action("spotify", elements)
    resolver.resolve_launch_action("spotify", elements)
    mock_sleep.assert_not_called()


def test_start_search_box_detected_after_win_respects_cadence(mocker) -> None:
    """Verifies cadence buffer when Start Search edit control appears in elements after Win key."""
    mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
    resolver = UniversalAppResolver()

    # Step 1: Win key
    resolver.resolve_launch_action("paint", [])
    mock_sleep.assert_not_called()

    # Step 2: Search box appears in SOM elements
    elements = [
        UIElement.from_bbox(1, (100, 950, 400, 40), label="Search box", role="Edit"),
    ]
    action = resolver.resolve_launch_action("paint", elements)
    assert action.action == ActionType.CLICK_AND_TYPE
    mock_sleep.assert_called_once_with(0.25)
```

---

## 5. Verification Method

To independently verify this investigation and the upcoming implementation:

1. **Verify Baseline Test Suite:**
   Run in PowerShell:
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest
   ```
   *Expected:* 797 passed in ~128s.

2. **Verify Existing Resolver Tests:**
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_resolver.py
   ```
   *Expected:* 5 passed in ~0.6s.

3. **Verify Implementation of Phase 3C (Post-Implementation):**
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_resolver.py -k "cadence"
   ```
   *Expected:* All new cadence tests pass with `time.sleep` verified at exactly 250ms (`0.25s`).

4. **Verify Architectural Invariants:**
   - Strict anti-hardcoding rule: Verify `UniversalAppResolver` has zero application dictionaries or hardcoded lists (`grep_search` for dictionary maps in `resolver.py`).
   - Hardware preemption: Verify `cancellation_token` support in `_sleep_cadence_buffer`.
   - Dual-monitor safety & local LLM mode: Untouched and fully preserved.
