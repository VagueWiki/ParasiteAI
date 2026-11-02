# Phase 4 Pre-Implementation Survey Report: Focus Areas 1–4

**Author:** Survey Explorer 3 (`teamwork_explorer_p4_survey_3`)  
**Target Milestone:** Phase 4 Implementation Readiness Audit  
**Date:** 2026-11-01  
**Scope:**
1. UniversalAppResolver Hardening & PrecisionAppMatcher (Master Plan Section 8, Sub-Phase 4E, VERIF-11)
2. Win32 Ctypes Structs 64-bit ABI sizing (Master Plan Section 9.2, Sub-Phase 4F, VERIF-9)
3. Anti-Hardcoding Invariant audit (`git grep -i "app_map"` check, Master Plan Section 8, VERIF-6)
4. Existing baseline tests (877 tests) status and Phase 4 test suites status (`tests/test_escalation_cadence.py`, `tests/test_dual_channel_output.py`, `tests/test_tool_aware_reasoning.py`, `tests/test_scene_serialization.py`, `tests/test_cli_sandbox.py`, `tests/test_resolver_precision.py`, etc.)

---

## 1. Observation

### 1.1 UniversalAppResolver & PrecisionAppMatcher
* **File:** `C:\ParasiteAI\parasite_ai\mind\resolver.py`
  * **Lines 33–38:**
    ```python
    def __init__(self, cadence_buffer_ms: float = DEFAULT_CADENCE_BUFFER_MS) -> None:
        self.cadence_buffer_ms: float = float(cadence_buffer_ms)
        self._last_attempted_app: Optional[str] = None
        self._search_opened: bool = False
        self._run_opened: bool = False
    ```
    *Observation:* Only `_search_opened` and `_run_opened` exist. Attempt counters `_start_search_attempts` and `_run_dialog_attempts` required by Master Plan Section 8.2 are completely absent.
  * **Lines 100–115:**
    ```python
    for elem in elements:
        label = (elem.label or "").strip().lower()
        if not label:
            continue

        # Exact match or strong substring match
        is_match = (label == target_clean) or (target_clean in label and len(target_clean) >= 3)
        if is_match:
            role = (elem.role or "").lower()
            if any(r in role for r in ("button", "listitem", "menuitem", "hyperlink", "image", "pane", "icon", "treeitem", "tabitem", "window")):
                return ActionPlan(
                    action=ActionType.CLICK,
                    target_id=elem.id,
                    reasoning=f"Found visible '{elem.label}' ({elem.role}) matching '{target_app}'; clicking directly",
                )
    ```
    *Observation:* Naive substring matching `target_clean in label and len(target_clean) >= 3` is used. For example, querying "art" matches "SmartScreen", "cat" matches "Certificate Manager", and "notepad" matches "Exit Notepad".
  * **Lines 168–195:**
    ```python
    # Tier 2: Windows Start Search Chord (Win Key)
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

    # ------------------------------------------------------------------
    # Tier 3: Run Dialog fallback (Win+R)
    # ------------------------------------------------------------------
    return ActionPlan(
        action=ActionType.HOTKEY,
        keys=["win", "r"],
        reasoning=f"Tier 3 Universal Launch: Triggering Run dialog (Win+R) to launch '{target_app}'",
    )
    ```
    *Observation:* Once `self._search_opened` transitions True $\to$ False in step 2, subsequent calls to `resolve_launch_action()` find `not self._search_opened` (since it was reset to False), causing an infinite alternating loop between `HOTKEY ["win"]` and `TYPE "{target_app}\n"`. Lines 191–195 (Tier 3: `HOTKEY ["win", "r"]`) are completely unreachable.
  * **Absence of `PrecisionAppMatcher`:**
    * `git grep "PrecisionAppMatcher"` in `parasite_ai/` returned 0 matches.
    * `PrecisionAppMatcher` exists only in `tests/test_challenger_p4_iter2_empirical.py` as a test mock (`MasterPlanPrecisionAppMatcher`), not in production source.

### 1.2 Win32 Ctypes Structs 64-bit ABI Sizing
* All 10 Win32 ctypes structures specified in Master Plan Section 9.2 exist across the codebase:
  1. `POINT`: `parasite_ai/safety/interrupt_guard.py:82`
  2. `RECT`: `wintypes.RECT` imported in `parasite_ai/safety/window_guard.py:10` and `parasite_ai/mind/dual_mind.py:228`
  3. `MSLLHOOKSTRUCT`: `parasite_ai/safety/interrupt_guard.py:89`
  4. `KBDLLHOOKSTRUCT`: `parasite_ai/safety/interrupt_guard.py:108`
  5. `MOUSEINPUT`: `parasite_ai/hands/keyboard.py:96`
  6. `KEYBDINPUT`: `parasite_ai/hands/keyboard.py:107`
  7. `HARDWAREINPUT`: `parasite_ai/hands/keyboard.py:117`
  8. `INPUT_UNION`: `parasite_ai/hands/keyboard.py:125`
  9. `INPUT`: `parasite_ai/hands/keyboard.py:133`
  10. `GUITHREADINFO`: `parasite_ai/mind/dual_mind.py:217`
* **Direct Runtime Inspection Output via Python 3.12 64-bit on Windows:**
  ```
  === POINT (size=8, align=4) ===
    x: offset=0, size=4, type=c_long
    y: offset=4, size=4, type=c_long
  === RECT (size=16, align=4) ===
    left: offset=0, size=4, type=c_long
    top: offset=4, size=4, type=c_long
    right: offset=8, size=4, type=c_long
    bottom: offset=12, size=4, type=c_long
  === MSLLHOOKSTRUCT (size=32, align=8) ===
    pt: offset=0, size=8, type=POINT
    mouseData: offset=8, size=4, type=c_ulong
    flags: offset=12, size=4, type=c_ulong
    time: offset=16, size=4, type=c_ulong
    dwExtraInfo: offset=24, size=8, type=c_ulonglong
  === KBDLLHOOKSTRUCT (size=24, align=8) ===
    vkCode: offset=0, size=4, type=c_ulong
    scanCode: offset=4, size=4, type=c_ulong
    flags: offset=8, size=4, type=c_ulong
    time: offset=12, size=4, type=c_ulong
    dwExtraInfo: offset=16, size=8, type=c_ulonglong
  === MOUSEINPUT (size=32, align=8) ===
    dx: offset=0, size=4, type=c_long
    dy: offset=4, size=4, type=c_long
    mouseData: offset=8, size=4, type=c_ulong
    dwFlags: offset=12, size=4, type=c_ulong
    time: offset=16, size=4, type=c_ulong
    dwExtraInfo: offset=24, size=8, type=c_ulonglong
  === KEYBDINPUT (size=24, align=8) ===
    wVk: offset=0, size=2, type=c_ushort
    wScan: offset=2, size=2, type=c_ushort
    dwFlags: offset=4, size=4, type=c_ulong
    time: offset=8, size=4, type=c_ulong
    dwExtraInfo: offset=16, size=8, type=c_ulonglong
  === HARDWAREINPUT (size=8, align=4) ===
    uMsg: offset=0, size=4, type=c_ulong
    wParamL: offset=4, size=2, type=c_ushort
    wParamH: offset=6, size=2, type=c_ushort
  === INPUT_UNION (size=32, align=8) ===
    mi: offset=0, size=32, type=MOUSEINPUT
    ki: offset=0, size=24, type=KEYBDINPUT
    hi: offset=0, size=8, type=HARDWAREINPUT
  === INPUT (size=40, align=8) ===
    type: offset=0, size=4, type=c_ulong
    u: offset=8, size=32, type=INPUT_UNION
  === GUITHREADINFO (size=72, align=8) ===
    cbSize: offset=0, size=4, type=c_ulong
    flags: offset=4, size=4, type=c_ulong
    hwndActive: offset=8, size=8, type=c_void_p
    hwndFocus: offset=16, size=8, type=c_void_p
    hwndCapture: offset=24, size=8, type=c_void_p
    hwndMenuOwner: offset=32, size=8, type=c_void_p
    hwndMoveSize: offset=40, size=8, type=c_void_p
    hwndCaret: offset=48, size=8, type=c_void_p
    rcCaret: offset=56, size=16, type=RECT
  ```
  *Observation:* All 10 structure sizes and offsets conform 100% to the x64 Windows ABI requirements documented in Master Plan Section 9.2.
* **Test Suite Status:** Dedicated test file `tests/test_schema_mapping.py` mandated by Section 12 (VERIF-9) does not exist yet.

### 1.3 Anti-Hardcoding Invariant Audit
* **Command:** `git grep -i "app_map" parasite_ai/`
  * **Result:** Exit code 1, zero matches returned.
* **Command:** `grep_search` for `notepad.exe` and `calc.exe` in `parasite_ai/`
  * **Result:** 0 matches.
* **Source inspection:** `parasite_ai/mind/dual_mind.py` contains dynamic launcher hooks; no hardcoded application dictionaries exist.
* Existing regression tests in `tests/test_phase3_execution_loop.py:513` and `tests/test_challenger_p3_stress.py:513` explicitly assert that neither `"app_map"` nor `"APP_MAP"` exists as attributes or module dictionaries.

### 1.4 Baseline & Phase 4 Test Suites Status
* **Full Baseline Test Execution:**
  * Command: `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest -q`
  * Result: `922 passed in 144.58s (0:02:24)`. 100% green pass rate across all collected tests.
  * Breakdown:
    * 877 baseline tests inherited from Phases 1–3
    * 45 preplanning empirical challenger tests (`test_challenger_p4_empirical.py` [18], `test_challenger_p4_iter2_c1.py` [8], `test_challenger_p4_iter2_empirical.py` [19])
    * Total: 877 + 45 = 922 tests.
* **Phase 4 New Test Suites Status:**
  | Required Test Suite | Master Plan Reference | Exists? | Description |
  | :--- | :--- | :--- | :--- |
  | `tests/test_escalation_cadence.py` | Sub-Phase 4B, VERIF-1 | **No** | 4-tier escalation state machine unit and transition tests |
  | `tests/test_dual_channel_output.py` | Sub-Phase 4C, VERIF-3 | **No** | Dual-channel router, JSON extraction & speech sanitization tests |
  | `tests/test_tool_aware_reasoning.py` | Sub-Phase 4D, VERIF-4 | **No** | Tool-aware affordance evaluator tests |
  | `tests/test_scene_serialization.py` | Sub-Phase 4A, VERIF-5 | **No** | Set-of-Mark table serialization and <3 KB payload tests |
  | `tests/test_cli_sandbox.py` | Sub-Phase 4D, VERIF-10 | **No** | CLI execution sandbox security and preemption abort tests |
  | `tests/test_resolver_precision.py` | Sub-Phase 4E, VERIF-11 | **No** | UniversalAppResolver attempt progression & PrecisionAppMatcher tests |
  | `tests/test_schema_mapping.py` | Sub-Phase 4F, VERIF-9 | **No** | 10 Win32 ctypes structures & Pydantic models ABI sizing tests |
  | `tests/test_gemini_consultation_protocol.py` | Sub-Phase 4A, VERIF-2 | **Yes** | 18 passing tests verifying prompt formatting and blueprint extraction |

---

## 2. Logic Chain

1. **Resolver Vulnerability & Deadlock:**
   * In `parasite_ai/mind/resolver.py:168`, `resolve_launch_action()` checks `if not self._search_opened:` to emit `HOTKEY ["win"]`, setting `_search_opened = True`.
   * On the following tick (`resolver.py:178`), `if self._search_opened:` matches, emitting `TYPE f"{target_app}\n"`, and resets `_search_opened = False`.
   * On the third tick (when the app has not focused because Start Search failed), `_search_opened` is `False`. The resolver re-enters `if not self._search_opened:` and sends `HOTKEY ["win"]` again.
   * Because there is no attempt counter (`_start_search_attempts`), the resolver oscillates between Win and Type indefinitely. Lines 191–195 (`HOTKEY ["win", "r"]`) can never execute.
   * Furthermore, lines 106–107 use naive substring matching (`target_clean in label and len(target_clean) >= 3`), causing false positive clicks on words containing the search term (e.g. "art" in "SmartScreen").
   * *Inference:* Implementing `_start_search_attempts`, `_run_dialog_attempts`, a clean exhaustion branch emitting `ActionType.WAIT`, and adding `PrecisionAppMatcher` to `resolver.py` is necessary to eliminate the deadlock and substring collisions.

2. **Win32 Structs ABI Compliance:**
   * Direct ctypes reflection using Python 3.12 64-bit on Windows verified that `POINT` (8B), `RECT` (16B), `MSLLHOOKSTRUCT` (32B), `KBDLLHOOKSTRUCT` (24B), `MOUSEINPUT` (32B), `KEYBDINPUT` (24B), `HARDWAREINPUT` (8B), `INPUT_UNION` (32B), `INPUT` (40B), and `GUITHREADINFO` (72B) match expected 64-bit Windows ABI memory layouts down to individual byte offsets and field alignments.
   * In-source assertions (`assert ctypes.sizeof(MSLLHOOKSTRUCT) == 32`, `assert ctypes.sizeof(KBDLLHOOKSTRUCT) == 24`, `assert ctypes.sizeof(INPUT) == 40`) already guard runtime integrity.
   * *Inference:* The structs are ready and compliant; only the dedicated verification test file `tests/test_schema_mapping.py` needs to be created to fulfill VERIF-9.

3. **Anti-Hardcoding Invariant:**
   * Both `git grep -i "app_map" parasite_ai/` and recursive content searches for static executables ("notepad.exe", "calc.exe") yielded zero matches.
   * *Inference:* The codebase strictly adheres to the dynamic grounding invariant (VERIF-6). No legacy hardcoding remnants exist in source code.

4. **Testing Baseline & Phase 4 Gap:**
   * All 922 collected tests currently in `tests/` pass 100% green without regressions.
   * However, 7 of the 8 Phase 4 test suites specified in Master Plan Section 10/12 do not exist on disk.
   * *Inference:* Phase 4 test suites must be implemented in their designated files (`test_escalation_cadence.py`, `test_dual_channel_output.py`, `test_tool_aware_reasoning.py`, `test_scene_serialization.py`, `test_cli_sandbox.py`, `test_resolver_precision.py`, `test_schema_mapping.py`) during Phase 4 implementation.

---

## 3. Caveats

1. **Challenger P4 Suites vs Production Tests:** The current repository contains 45 tests across `test_challenger_p4_empirical.py`, `test_challenger_p4_iter2_c1.py`, and `test_challenger_p4_iter2_empirical.py`. These files were authored during preplanning to stress-test mock models and plan specifications. They do not replace the official Phase 4 test suites that will test production runtime modules (`parasite_ai/mind/dual_mind.py`, `parasite_ai/mind/resolver.py`, `parasite_ai/mind/cli_sandbox.py`, etc.).
2. **PyQt6 / GUI Threading:** Running the full test suite (922 tests) requires the project virtualenv (`C:\ParasiteAI\.venv`) containing `PyQt6` and `pytest-qt`. Tests take ~2.5 minutes to execute due to physical timing tests and Qt event loop spin cycles.

---

## 4. Conclusion

The codebase is in an excellent, robust state with a 100% green baseline (922/922 passing tests) and zero anti-hardcoding violations. The Win32 ctypes structures strictly adhere to 64-bit ABI sizing.

The implementation tasks for the surveyed areas in Phase 4 are clearly scoped:
1. **UniversalAppResolver Hardening:**
   - Integrate `PrecisionAppMatcher` into `parasite_ai/mind/resolver.py` with word-boundary regex (`\b`), negative verb filtering, and role filtering.
   - Update `UniversalAppResolver` with `_start_search_attempts` and `_run_dialog_attempts` counters to ensure clean 3-tier fallback progression (`Win` $\to$ `Type` $\to$ `Win+R` $\to$ `Type` $\to$ `WAIT` on exhaustion).
2. **Schema Mapping & Struct Testing:**
   - Create `tests/test_schema_mapping.py` covering all 10 Win32 ctypes structures and Pydantic models.
3. **Phase 4 Test Suites:**
   - Author the 7 missing Phase 4 test suites (`test_escalation_cadence.py`, `test_dual_channel_output.py`, `test_tool_aware_reasoning.py`, `test_scene_serialization.py`, `test_cli_sandbox.py`, `test_resolver_precision.py`, `test_schema_mapping.py`).

---

## 5. Verification Method

To independently verify these findings, execute the following commands in powershell:

1. **Verify 10 Win32 Ctypes Struct Sizing & Offsets:**
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -c "
   import ctypes
   from ctypes import wintypes
   from parasite_ai.safety.interrupt_guard import POINT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT
   from parasite_ai.hands.keyboard import MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT
   from parasite_ai.mind.dual_mind import GUITHREADINFO

   structs = [
       ('POINT', POINT, 8),
       ('RECT', wintypes.RECT, 16),
       ('MSLLHOOKSTRUCT', MSLLHOOKSTRUCT, 32),
       ('KBDLLHOOKSTRUCT', KBDLLHOOKSTRUCT, 24),
       ('MOUSEINPUT', MOUSEINPUT, 32),
       ('KEYBDINPUT', KEYBDINPUT, 24),
       ('HARDWAREINPUT', HARDWAREINPUT, 8),
       ('INPUT_UNION', INPUT_UNION, 32),
       ('INPUT', INPUT, 40),
       ('GUITHREADINFO', GUITHREADINFO, 72),
   ]
   for name, s, exp in structs:
       assert ctypes.sizeof(s) == exp, f'{name} size mismatch: got {ctypes.sizeof(s)}, expected {exp}'
   print('ALL 10 STRUCT SIZES VERIFIED!')
   "
   ```

2. **Verify Anti-Hardcoding Invariant (0 matches):**
   ```powershell
   git grep -i "app_map" parasite_ai/
   # Expect exit code 1 (no output)
   ```

3. **Verify Baseline Test Pass Rate:**
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest -q
   # Expect: 922 passed in ~145s
   ```

4. **Verify Resolver Attempt Counter & PrecisionAppMatcher Absence:**
   ```powershell
   & "C:\ParasiteAI\.venv\Scripts\python.exe" -c "
   from parasite_ai.mind import resolver
   assert not hasattr(resolver, 'PrecisionAppMatcher')
   r = resolver.UniversalAppResolver()
   assert not hasattr(r, '_start_search_attempts')
   print('Confirmed: PrecisionAppMatcher and _start_search_attempts are not yet implemented in resolver.py')
   "
   ```
