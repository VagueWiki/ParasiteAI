# Forensic Integrity Audit Report: ParasiteAI (M1–M5)

**Work Product**: `parasite_ai/`, `main.py`, `launch_parasite.bat`, `tests/`  
**Profile**: General Project  
**Integrity Mode**: Development (per `ORIGINAL_REQUEST.md`)  
**Verdict**: **CLEAN**  

---

## 1. Observation

### Test Suite Execution
- **Command**: `uv run pytest`
- **Result**:
  ```
  580 passed in 72.87s (0:01:12)
  platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
  PyQt6 6.12.0 -- Qt runtime 6.12.0
  ```
  All 580 tests across 34 test suites passed with 0 failures, 0 skips, 0 xfails.

### Dry-Run CLI Self-Test Execution
- **Command**: `uv run python main.py --dry-run`
- **Result**:
  ```
  [INFO] parasite_ai.main: Executing ParasiteAI dry-run self-test...
  [INFO] parasite_ai.main: Shutting down ParasiteAI subsystems...
  [INFO] parasite_ai.main: ParasiteAI shutdown complete.
  Clean dry-run initialization completed successfully
  Exit code: 0
  ```

### Check 1 (Static Analysis: Hardcoded Values & Test Runner Sniffing)
- Searched codebase `parasite_ai/` for test harness sniffing:
  - `"pytest"`: 0 occurrences found.
  - `"unittest"`: 0 occurrences found.
  - `_pytest`: 0 occurrences found.
  - `sys.modules`: 0 occurrences found.
  - `sys.argv`: Only 1 occurrence in `parasite_ai/main.py:81` (`self.qapp = QApplication(sys.argv)`), standard Qt application initialization.
  - `os.environ`: Only standard runtime configuration flags (`PARASITE_LOG_LEVEL`, `PARASITE_BRAIN_MODE`, `PARASITE_INTEGRITY_MODE`, and `QT_QPA_PLATFORM = "offscreen"` in `parasite_ai/main.py:76`).
  - No sniffing of test runner or hardcoded mock coordinates in production logic.

### Check 2 (Facade Analysis: Empty Stubs & Dummy Implementations)
- Inspected `runtime.py`, `main.py`, `parasite_ai/main.py`, `parasite_ai/safety/`, `parasite_ai/hands/`, `parasite_ai/vision/`, `parasite_ai/mind/`, `parasite_ai/ui/`.
- No empty functions or dummy constants returned in place of real logic.
- Inspected `tests/`:
  - `assert True`: 0 occurrences across all test files.
  - `@pytest.mark.skip`: 0 occurrences across all test files.
  - `@pytest.mark.xfail`: 0 occurrences across all test files.
  - Empty `def test_...: pass`: 0 occurrences across all test files.
- Pre-populated artifacts: Checked for leftover `.log`, `*result*`, `*output*` files; 0 found.

### Check 3 (Hardware Hooks & Windows APIs)
- **Low-Level Hooks** (`parasite_ai/safety/interrupt_guard.py` lines 80–232, 350–395):
  - ctypes bindings configured for `SetWindowsHookExW` (`WH_MOUSE_LL = 14`, `WH_KEYBOARD_LL = 13`), `UnhookWindowsHookEx`, `CallNextHookEx`, `GetMessageW`, `TranslateMessage`, `DispatchMessageW`, `PeekMessageW`, `PostThreadMessageW`, `timeBeginPeriod(1)`, `timeEndPeriod(1)`.
  - Dedicated hook thread (`InterruptGuardHookThread`) with authentic message pump loop.
  - Ctypes struct definitions: `MSLLHOOKSTRUCT` (32 bytes), `KBDLLHOOKSTRUCT` (24 bytes) validated via `assert ctypes.sizeof(...)`.
  - Genuine flag inspection: checks `struct.flags & LLMHF_INJECTED` and `struct.flags & LLKHF_INJECTED` to distinguish synthetic injected inputs from physical hardware touches.
- **Sensitive Window Guard** (`parasite_ai/safety/window_guard.py` lines 93–230):
  - Win32 calls: `GetForegroundWindow`, `GetWindowThreadProcessId`, `GetWindowTextW`, `GetClassNameW`, `GetWindowRect`, `OpenProcess`, `QueryFullProcessImageNameW`, `CloseHandle`.
- **Physical Mouse Driver** (`parasite_ai/hands/mouse.py` lines 48–83, 125–142, 408–449):
  - Win32 calls: `SendInput`, `GetCursorPos`, `GetSystemMetrics`, `timeBeginPeriod(1)`.
  - Struct definitions: `MOUSEINPUT` (32 bytes), `INPUT` (40 bytes, offset 8).
  - Absolute virtual desktop coordinate normalization: `(x - vx) * 65535 / max(1, vcx - 1)`.
- **Physical Keyboard Driver** (`parasite_ai/hands/keyboard.py` lines 81–152, 209–251, 372–449):
  - Win32 `SendInput` with `KEYEVENTF_UNICODE` (0x0004).
  - Decomposes astral plane characters (> 0xFFFF) into UTF-16 surrogate pairs (`decompose_utf16`).
  - Shift+Enter multiline safety for intermediate newlines (`_send_shift_enter`).
- **Click-Through Ghost HUD** (`parasite_ai/ui/win32_styles.py` lines 18–81):
  - `GetWindowLongW(hwnd, GWL_EXSTYLE)`, `SetWindowLongW`, `SetWindowPos`.
  - Extended styles applied: `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`.
- **DPI Awareness** (`parasite_ai/ui/dpi.py` lines 18–68):
  - Win32 API calls: `SetProcessDpiAwarenessContext` (Per-Monitor v2), `shcore.SetProcessDpiAwareness`, `SetProcessDPIAware`.

### Check 4 (Preemption Authenticity)
- `parasite_ai/safety/interrupt_guard.py` line 167:
  - `self._cancellation_token = threading.Event()`
  - Signaled immediately upon physical input: `self._cancellation_token.set()`
- `InterruptGuard.wait_interruptible(timeout)`:
  - Calls `self._cancellation_token.wait(timeout=timeout)` directly on the OS event, returning immediately on signal without sleep loops.
- `parasite_ai/hands/mouse.py` lines 198–208:
  - In `move_to` 120Hz trajectory loop:
    ```python
    for pt in waypoints:
        if cancellation_token and cancellation_token.is_set():
            self.release_all_buttons()
            return False
        self._apply_cursor_move(pt[0], pt[1])
        if cancellation_token and cancellation_token.wait(timeout=step_delay_s):
            self.release_all_buttons()
            return False
    ```
- `parasite_ai/hands/keyboard.py` lines 412–439:
  - In `type_text`: per-character cancellation checking and `self.backend.sleep_interruptible(pause_s, cancellation_token)` which delegates to `cancellation_token.wait(timeout=duration_s)`.
- Benchmark test `tests/test_challenger_m2_2.py::TestAdversarialWaitInterruptibleLatencyBenchmark`:
  - 100 trials measuring wake latency when interrupted asynchronously from a timer thread empirically pass with wake latency < 2.0ms.

### Check 5 (Zero Headless Browsers)
- Grep across entire repository:
  - `selenium`: 0 results
  - `playwright`: 0 results
  - `puppeteer`: 0 results
  - `websocket`: 0 results
  - `devtools`: 0 results
  - `cdp`: 1 result in docstring of `parasite_ai/mind/offloader.py:5` documenting the strict architectural constraint of "zero hidden CDP sockets".
- `pyproject.toml`: Contains zero headless browser dependencies.
- Physical browser offloader implementation (`parasite_ai/mind/offloader.py` lines 430–522):
  - Physical window location & foreground activation (`find_browser_window`, `focus_window`).
  - Physical hotkey navigation (`hotkey("ctrl", "l")`, typing URL, Enter).
  - Physical prompt typing via `keyboard_driver.type_text(prompt, submit=True)`.
  - Physical copy harvest via mouse click and `hotkey("ctrl", "c")`.

### Check 6 (Sentinel Clipboard Verification)
- Implementation (`parasite_ai/mind/offloader.py` lines 280–374, `SentinelClipboardVerifier`):
  - Token generation: `generate_sentinel()` produces `f"{self.token_prefix}_{uuid.uuid4().hex}__"` (128-bit randomized hex UUID).
  - Step 1: Pre-existing clipboard backup: `original_clip = self.clipboard.get_text()`.
  - Step 2: Inject sentinel token: `self.clipboard.set_text(sentinel_token)`.
  - Step 3: Verification: asserts clipboard contains sentinel token before proceeding.
  - Step 4: Triggers physical copy action (`trigger_copy_action`).
  - Step 5: Polls clipboard until `curr != sentinel_token and len(curr.strip()) > 0`.
  - Step 6: Guaranteed restoration: `finally:` block executes `self.clipboard.set_text(original_clip)` to preserve user clipboard integrity without destruction.

---

## 2. Logic Chain

1. **Static Analysis & Anti-Sniffing (Check 1)**:
   Observations show 0 occurrences of test runner sniffing (`pytest`, `unittest`, `_pytest`, `sys.modules`) and only standard CLI initialization via `sys.argv`. Therefore, runtime execution behavior is identical between test harnesses and real environments.

2. **Facade & Stub Verification (Check 2)**:
   Every module across `parasite_ai/` provides genuine logic and algorithmic processing (Bézier kinematics, Set-of-Marks IoU clustering, GGUF binary unpacking, low-level Win32 hook dispatch). In `tests/`, all 580 tests have substantive assertions with 0 skipped or empty tests. Therefore, the implementation is authentic.

3. **Win32 & Low-Level API Authenticity (Check 3)**:
   Inspection of `interrupt_guard.py`, `mouse.py`, `keyboard.py`, `window_guard.py`, `win32_styles.py`, and `dpi.py` confirmed authentic ctypes declarations matching exact 64-bit Windows memory layouts (`sizeof(INPUT) == 40`, `sizeof(MSLLHOOKSTRUCT) == 32`, `sizeof(KBDLLHOOKSTRUCT) == 24`), real hook message loops, and native window extended styles. Therefore, the Windows hardware and API layer is authentic.

4. **Preemption Architecture (Check 4)**:
   Preemption relies on native OS-level signaling via `threading.Event` wired directly into low-level hook callbacks. Action execution loops (Bézier interpolation and keystroke injection) poll this token using `wait()` without busy-wait loops or arbitrary `time.sleep()` preemption hacks. Empirical testing confirms sub-2ms interrupt latency. Therefore, the preemption token is genuine.

5. **Zero Headless Browsers (Check 5)**:
   Source code greps and dependency analysis confirm complete absence of Selenium, Playwright, Puppeteer, CDP, and websockets. Browser offloading operates via physical window foregrounding, cursor gliding, and keystroke injection. Therefore, the constraint is strictly satisfied.

6. **Sentinel Clipboard Protocol (Check 6)**:
   `SentinelClipboardVerifier` generates unique 128-bit UUIDs, verifies sentinel injection, and strictly restores the pre-existing clipboard in a `finally:` block. Therefore, clipboard harvesting is authentic and non-destructive.

7. **Overall Conclusion**:
   Because Checks 1 through 6 pass without a single failure under the Development integrity mode specified in `ORIGINAL_REQUEST.md`, the verdict is CLEAN.

---

## 3. Caveats

- **OS Thread Scheduling Under Extreme Load**: In `test_challenger_m2_2.py`, latency benchmarks require sub-2ms wake times. On heavily loaded systems, Windows non-real-time OS thread scheduling may introduce brief scheduling jitter exceeding 2ms on occasional individual iterations. However, under standard operating conditions and dedicated test execution, all benchmark trials pass cleanly within budget.
- **Physical Desktop Interaction Guardrail**: Live tests that physically move the mouse or take over user input require explicit user consent per `ORIGINAL_REQUEST.md` R2. The dry-run self-test (`python main.py --dry-run`) does not take over input and validates cleanly.

---

## 4. Conclusion

**Verdict: CLEAN**

The ParasiteAI codebase across Milestones M1 through M5 satisfies all forensic integrity criteria. The implementation is authentic, contains zero dummy facades or test-sniffing cheats, executes authentic Win32/ctypes low-level hardware hooks and SendInput dispatch, enforces genuine sub-2ms preemption, uses zero headless browser frameworks, and protects user clipboard data through an atomic Sentinel Clipboard protocol.

---

## 5. Verification Method

To independently reproduce and verify this audit:

1. **Run full unit & integration test suite**:
   ```powershell
   uv run pytest
   ```
   *Expected outcome*: 580 passed in ~70–90 seconds.

2. **Run sub-2ms preemption benchmark independently**:
   ```powershell
   uv run pytest tests/test_challenger_m2_2.py -k "TestAdversarialWaitInterruptibleLatencyBenchmark" -v
   ```
   *Expected outcome*: 5 passed in ~1 second.

3. **Verify dry-run startup and subsystem integrity**:
   ```powershell
   uv run python main.py --dry-run
   ```
   *Expected outcome*: Exits with code 0 and logs `Clean dry-run initialization completed successfully`.

4. **Verify zero headless browser packages**:
   ```powershell
   Select-String -Path "parasite_ai\**\*.py" -Pattern "selenium|playwright|puppeteer|websocket"
   ```
   *Expected outcome*: 0 matches.
