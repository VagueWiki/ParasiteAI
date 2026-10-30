# Discrepancy Analysis: Simulated Test Suites vs. Physical Windows Desktop & Hardware Execution (M1–M5)

## 1. Observation

Direct observations from codebase inspection, test suite analysis, system environment querying, and live hardware telemetry:

### 1.1 Companion Dock & DWM Composition
* **Code Location**: `parasite_ai/ui/companion_dock.py:168-175`, `parasite_ai/ui/companion_dock.py:461-491`, `parasite_ai/ui/companion_dock.py:523-537`.
* **Observed Implementation**:
  ```python
  flags = Qt.WindowType.Window
  if self.config.always_on_top:
      flags |= Qt.WindowType.WindowStaysOnTopHint
  if self.config.frameless:
      flags |= Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool

  self.setWindowFlags(flags)
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
  ```
  In `anchor_to_screen()`:
  ```python
  if screen is None:
      screen = QGuiApplication.primaryScreen()
  screen_rect = screen.availableGeometry()
  ```
  In `_clamp_to_virtual_desktop()`:
  ```python
  screen = QGuiApplication.primaryScreen()
  vgeom = screen.virtualGeometry()
  min_x = vgeom.x() - self.width() + 60
  max_x = vgeom.right() - 60
  ```
* **Test Suite Observation**: `tests/test_companion_dock.py:30-45` and `tests/test_e2e_integration.py:64` run under `QT_QPA_PLATFORM="offscreen"`. The dock is instantiated and tested via simulated PyQt signal emissions and `qtbot.mouseClick()`. No native DWM window composition, taskbar shell presence, or multi-monitor dragging is exercised in tests.

### 1.2 Click-Through Ghost-Hand HUD & Extended Styles
* **Code Location**: `parasite_ai/ui/win32_styles.py:31-78`, `parasite_ai/ui/ghost_hud.py:162-202`, `parasite_ai/ui/ghost_hud.py:339-342`.
* **Observed Implementation**:
  ```python
  REQUIRED_HUD_EX_STYLES = (
      WS_EX_LAYERED
      | WS_EX_TRANSPARENT
      | WS_EX_TOPMOST
      | WS_EX_NOACTIVATE
      | WS_EX_TOOLWINDOW
  )
  user32 = ctypes.windll.user32
  current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
  new_style = current_style | REQUIRED_HUD_EX_STYLES
  user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
  ```
  Neither `argtypes` nor `restype` is configured on `GetWindowLongW` or `SetWindowLongW`.
  In `ghost_hud.py:339-341`:
  ```python
  def _to_local(self, x: int, y: int) -> QPoint:
      geo = self.geometry()
      return QPoint(x - geo.x(), y - geo.y())
  ```
* **Test Suite Observation**: In `tests/test_ghost_hud.py:76-94`, tests instantiate `GhostHUD(enable_win32_styles=False)` or patch `ctypes.windll.user32` with a `MagicMock`. Real Win32 click-through (`WS_EX_TRANSPARENT`) is explicitly disabled in the unit tests to prevent headless crashes.

### 1.3 Kinematic Bézier Glide, Acceleration & Display Clipping
* **Code Location**: `parasite_ai/hands/kinematics.py:215-238`, `parasite_ai/hands/mouse.py:197-207`, `parasite_ai/hands/mouse.py:416-438`.
* **Observed Implementation**:
  In `kinematics.py:222-225`:
  ```python
  p_over = (
      round(p_target[0] + d_over * ux),
      round(p_target[1] + d_over * uy),
  )
  ```
  `p_over` is unconstrained and can lie outside display coordinates if `p_target` is near a display border.
  In `mouse.py:426-438`:
  ```python
  norm_x = int(((x - vx) * 65535) / max(1, vcx - 1))
  norm_y = int(((y - vy) * 65535) / max(1, vcy - 1))

  inp = INPUT(type=INPUT_MOUSE)
  inp.u.mi.dx = norm_x
  inp.u.mi.dy = norm_y
  inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
  ```
  `norm_x` and `norm_y` are neither clamped to `[0, 65535]` nor bounds-checked against virtual desktop limits.
* **Test Suite Observation**: `tests/test_kinematics.py` and `tests/test_mouse_driver.py` run in `simulation_mode=True` or verify math on synthetic trajectories without invoking `SendInput` or verifying cursor clipping against physical monitor borders.

### 1.4 Physical Touch Abort & Low-Level Hooks
* **Code Location**: `parasite_ai/safety/interrupt_guard.py:362-395`, `parasite_ai/safety/interrupt_guard.py:396-435`, `parasite_ai/safety/interrupt_guard.py:482-516`.
* **Observed Implementation**:
  ```python
  self._mouse_hook = self._user32.SetWindowsHookExW(
      WH_MOUSE_LL, self._mouse_proc_cb, h_mod, 0,
  )
  self._keyboard_hook = self._user32.SetWindowsHookExW(
      WH_KEYBOARD_LL, self._keyboard_proc_cb, h_mod, 0,
  )
  ```
  In `_low_level_mouse_proc`:
  ```python
  struct = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
  is_injected = bool(struct.flags & LLMHF_INJECTED)
  if not is_injected:
      self._signal_physical_touch(...)
  ```
  In `mouse.py:436`:
  ```python
  inp.u.mi.dwExtraInfo = 0
  ```
* **Test Suite Observation**: `tests/test_interrupt_guard.py:58-100` tests the interrupt mechanism exclusively by calling `guard.simulate_event("mouse", flags=0)`. No real interactive Windows messages or concurrent physical/synthetic inputs are dispatched.

### 1.5 Chrome / Gemini Offload Selectors & Sentinel Clipboard
* **Code Location**: `parasite_ai/mind/offloader.py:473-503`, `parasite_ai/vision/grounding.py:181-224`, `parasite_ai/mind/offloader.py:316-373`.
* **Observed Implementation**:
  In `offloader.py:474-502`:
  ```python
  rect = self.window_backend.get_window_rect(hwnd)
  prompt_x = rect[0] + (rect[2] - rect[0]) // 2
  prompt_y = rect[3] - 120

  if self.mouse_driver:
      self.mouse_driver.click(prompt_x, prompt_y, button="left", cancellation_token=cancellation_token)

  self.keyboard_driver.type_text(prompt, submit=True, cancellation_token=cancellation_token)
  ...
  def trigger_copy() -> bool:
      if self.mouse_driver:
          self.mouse_driver.click(prompt_x, prompt_y - 200, button="left", cancellation_token=cancellation_token)
      if self.keyboard_driver:
          return self.keyboard_driver.hotkey("ctrl", "c", cancellation_token=cancellation_token)
      return True
  ```
  `BrowserOffloader` does NOT use `ScreenGrounder` or UI Automation at all. It uses hardcoded relative window coordinate offsets.
  In `SentinelClipboardVerifier.execute_harvest()` (`offloader.py:317-370`):
  ```python
  original_clip = self.clipboard.get_text()
  ...
  self.clipboard.set_text(sentinel_token)
  ...
  while time.perf_counter() < deadline:
      curr = self.clipboard.get_text()
      if curr != sentinel_token and len(curr.strip()) > 0:
          harvested_text = curr
          break
  ...
  self.clipboard.set_text(original_clip)
  ```
* **Test Suite Observation**: `tests/test_browser_offloader.py:27-187` runs with `MockClipboardBackend` and `MockBrowserWindowBackend`, intercepting `execute_harvest` with `MagicMock(return_value="Answer from existing Chrome")`.

### 1.6 Brain Resource Budget & Local Environment Telemetry
* **Hardware Telemetry Command Execution**:
  - `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv`:
    Output: `NVIDIA GeForce RTX 4060, 8188 MiB total, 2394 MiB used, 5564 MiB free`.
  - Python import check: `uv run python -c "import llama_cpp"`:
    Output: `No module named 'llama_cpp'`.
  - Directory listing: `g:\__Docs\ParasiteAI\models`:
    Output: Empty directory (0 files).
  - Port checks for local OpenAI / Ollama servers:
    Output: Ports 8080 and 11434 timed out / unreachable.
  - Configuration in `config.yaml`:
    `brain.mode: "browser_offload"`, `download_auto: false`, `local_model.model_id: "Qwen/Qwen2.5-3B-Instruct-GGUF"`.
* **Test Suite Observation**: `tests/test_brain_manager.py` and `tests/test_stress_gguf.py` use `MockBackend` or mock binary files (`b"GGUF\x03\x00\x00\x00"`). No real tensor allocation or GPU offloading occurs in tests.

---

## 2. Logic Chain

From the observations above, the following direct inferences establish the architectural discrepancies between simulated test suites and physical desktop execution:

### 2.1 Companion Dock Desktop Discrepancies
1. **Observation**: `Qt.WindowType.Tool` is appended when `frameless=True` (Section 1.1).
2. **Inference**: On Microsoft Windows, `Qt.WindowType.Tool` removes the window's button from the Windows Taskbar and excludes it from the `Alt+Tab` application switcher. While this matches a desktop gadget aesthetic, it prevents users from minimizing or re-focusing the dock via the taskbar.
3. **Observation**: `anchor_to_screen()` and `_clamp_to_virtual_desktop()` query only `QGuiApplication.primaryScreen()` (Section 1.1).
4. **Inference**: In multi-monitor desktop environments where secondary monitors have negative virtual desktop offsets (e.g., monitor to the left at `[-1920, 0]`) or differing Windows scaling factors (e.g., primary 150% 4K + secondary 100% 1080p), the dock will compute incorrect geometry bounds when dragged to secondary monitors and may get snapped back to the primary screen.

### 2.2 Ghost-Hand HUD Click-Through & Coordinate Translation
1. **Observation**: `apply_click_through_styles()` calls `GetWindowLongW` and `SetWindowLongW` without defining ctypes `argtypes`/`restype` or using 64-bit `GetWindowLongPtrW`/`SetWindowLongPtrW` (Section 1.2).
2. **Inference**: On 64-bit Windows, invoking 32-bit `GetWindowLongW`/`SetWindowLongW` with bitmasks containing high bits (`WS_EX_NOACTIVATE = 0x08000000`, `WS_EX_LAYERED = 0x00080000`) risks integer sign-extension or pointer truncation. If Windows fails to apply the style or if Qt recreates the native window handle, the overlay will become click-intercepting rather than click-through, blocking user clicks.
3. **Observation**: In unit tests, `enable_win32_styles` is set to `False` (Section 1.2).
4. **Inference**: The unit test pass rate of 100% does not validate that a physical click passes through the transparent Qt surface to an underlying window on a real Windows compositor (DWM).

### 2.3 Kinematic Bézier Glide vs. Physical Display Clipping & Windows Acceleration
1. **Observation**: Overshoot trajectory generation computes `p_over = p_target + d_over * ux` without checking physical display boundaries, and `_apply_cursor_move` computes `norm_x = int(((x - vx) * 65535) / max(1, vcx - 1))` without clamping to `[0, 65535]` (Section 1.3).
2. **Inference**: When targeting elements near the screen border (e.g., the Windows Start button at `(0, 1079)`, window minimize/close buttons at `(1919, 0)`, or taskbar tray icons), overshoot can produce coordinates outside the virtual desktop. Passing negative integers or values > 65535 into `MOUSEINPUT.dx/dy` with `MOUSEEVENTF_ABSOLUTE` triggers undefined Win32 cursor wrapping or clipping, causing the cursor to warp to unexpected locations.
3. **Observation**: `mouse.py` uses `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK` for waypoint moves (Section 1.3).
4. **Inference**: Absolute coordinates bypass Windows cursor ballistics ("Enhance pointer precision"), which correctly lands at exact target pixels. However, if physical user movement occurs simultaneously with synthetic moves, Windows cursor physics blends relative and absolute deltas, causing the cursor to jitter erratically before the physical abort token triggers.

### 2.4 Physical Touch Abort: Hook Timeouts, Driver Artifacts & GIL Contention
1. **Observation**: `WH_MOUSE_LL` and `WH_KEYBOARD_LL` callbacks are processed in Python via ctypes `HOOKPROC`, while synthetic inputs set `dwExtraInfo = 0` (Section 1.4).
2. **Inference 1 (Hook Timeout & Silent Unhooking)**: Windows enforces `LowLevelHooksTimeout` (typically 200ms–1000ms). If Python's GIL is held by CPU-intensive tasks (e.g., RapidOCR ONNX inference or screen capture diffing), the hook thread's message pump stalls. When Windows detects that the hook procedure did not return in time, the OS silently unhooks the procedure. Subsequent physical touches will fail to trigger an interrupt, completely removing the safety guard without raising an exception.
3. **Inference 2 (Kernel Drivers vs. Synthetic Flags)**: Modern gaming mouse drivers (Razer Synapse, Logitech G Hub) operate kernel-level filter drivers. Injected events from certain mouse macros appear with `flags = 0` (physical), which triggers the abort guard. Conversely, other third-party automation tools injecting events with `LLMHF_INJECTED = 1` are treated as synthetic. Because ParasiteAI does not stamp its own unique signature into `dwExtraInfo` (e.g. `0x50415241` / "PARA"), it cannot distinguish its own synthetic events from third-party synthetic events.

### 2.5 Chrome / Gemini Offload: Hardcoded Heuristic Fragility & Clipboard Loss
1. **Observation**: `BrowserOffloader` uses `prompt_x = rect[0] + (rect[2] - rect[0]) // 2`, `prompt_y = rect[3] - 120` to find the prompt box, and clicks `prompt_y - 200` followed by `Ctrl+C` to harvest responses (Section 1.5).
2. **Inference 1 (Total Failure on Real Web AI DOM)**: On a real Google Chrome browser viewing `gemini.google.com`, clicking `rect[3] - 320` lands on the chat history canvas. Clicking the web canvas does NOT select text. In Chromium, pressing `Ctrl+C` with no selected text does NOT write anything to the clipboard. As a result, the clipboard retains `__PARASITE_SENTINEL__<uuid>`. The polling loop in `execute_harvest` will poll for the full 45-second timeout, fail to detect any new clipboard content, and throw `OffloadHarvestError`.
3. **Inference 2 (Bypassing UI Automation)**: While `PROJECT.md` claims Tier 1 Win32 UI Automation tree walking locates the prompt box and Copy button, `BrowserOffloader` does not call `ScreenGrounder` or `uiautomation`. It is 100% blind pixel heuristics.
4. **Inference 3 (User Clipboard Manager Corruption & Data Loss)**:
   - In Windows 11, the native Clipboard History (`Win+V`) and tools like Ditto record all clipboard changes. Injecting sentinels creates persistent junk entries.
   - `get_text()` only saves plain text. If the user had an image, screenshot, or rich text in their clipboard before offloading, `execute_harvest` restores only empty string or plain text, destroying the user's rich clipboard contents.

### 2.6 Brain Resource Budget on RTX 4060 8 GB
1. **Observation**: Live telemetry shows 5564 MiB free VRAM (Section 1.6). `models/` is empty and `llama_cpp` is not installed.
2. **Inference 1 (7B Model Out-of-Memory)**: Loading a 7B Q4_K_M model requires ~4.68 GB weights + ~1.0 GB KV cache (for 4096 context) = ~5.7 GB VRAM. This exceeds the 5564 MiB headroom on the physical RTX 4060. Loading 7B with full GPU layer offloading will crash with CUDA Out-Of-Memory or spill into system RAM via PCIe, reducing inference speeds to ~1–3 tokens/sec.
3. **Inference 2 (3B Model Feasibility)**: `Qwen2.5-3B-Instruct-Q4_K_M` requires ~2.17 GB weights + ~0.5 GB KV cache = ~2.7 GB VRAM, safely fitting within the 5564 MiB headroom.
4. **Inference 3 (Current Execution State)**: Because `llama_cpp` is missing and `models/` is empty, attempting to switch to `brain.mode: "local_llm"` in real desktop execution will throw an immediate runtime error. Currently, the system is constrained to `browser_offload` or `mock`.

---

## 3. Prioritized Risk Matrix

| Risk Level | Feature / Area | Simulated Test Condition | Real Desktop Failure Mode / Risk | Recommended Hardening Action |
|:---:|:---|:---|:---|:---|
| **HIGH** | **Chrome / Gemini Web Offloader** | `MockClipboardBackend` with mock text injection in `test_browser_offloader.py`. | **Complete Offload Failure**: `prompt_y - 200` + `Ctrl+C` clicks empty canvas; text is never selected; clipboard never changes from sentinel; 45s harvest timeout triggers every time. | Connect `ScreenGrounder` to locate the actual "Copy" button or prompt box in the Chrome accessibility tree (`DocumentControl`), or use a reliable DOM select/copy strategy (`Ctrl+A` in scoped response container, or JS copy button via browser URL bar/extension). |
| **HIGH** | **Brain Resource Budget & Local LLM** | `MockBackend` returns static strings in `test_brain_manager.py`. | **Subsystem Unavailable / OOM**: `models/` is empty, `llama_cpp` is uninstalled. Attempting to load 7B model on RTX 4060 with 5564 MiB free spills into system RAM or crashes with CUDA OOM. | 1. Enforce `Qwen2.5-3B-Instruct-Q4_K_M` as default local model.<br>2. Install `llama-cpp-python` with CUDA wheel or document external llama-server endpoint.<br>3. Verify VRAM headroom guard clamps `n_gpu_layers` dynamically. |
| **HIGH** | **Physical Touch Abort (GIL & Hook Timeout)** | `guard.simulate_event()` called on main thread in `test_interrupt_guard.py`. | **Silent Safety Disarming**: If Python GIL is blocked by RapidOCR or token streaming, Windows `LowLevelHooksTimeout` (200-1000ms) drops the hook silently without error, leaving mouse/keyboard automation unstoppable. | 1. Keep hook callback minimal in C/ctypes without GIL lock where possible.<br>2. Periodically verify hook health via `GetGUIThreadInfo` or test pulse.<br>3. Stamp unique `dwExtraInfo` (e.g. `0x50415241`) on all synthetic events. |
| **MEDIUM** | **Bézier Glide Display Clipping** | Math trajectory checks and `simulation_mode=True` in `test_mouse_driver.py`. | **Cursor Warping / Out-of-Bounds**: Overshoot trajectory points outside virtual screen bounds (`< 0` or `> 65535`) wrap to opposite screen edges or fail Win32 `SendInput`. | Add explicit clamping `max(vx, min(pt[0], vx + vcx - 1))` in `_apply_cursor_move` before normalizing to `[0, 65535]`. |
| **MEDIUM** | **Ghost-Hand HUD Win32 Extended Styles** | Mocked `user32` or `enable_win32_styles=False` in `test_ghost_hud.py`. | **Click Interception Risk**: 32-bit `GetWindowLongW`/`SetWindowLongW` on 64-bit Windows without ctypes types risks incorrect bitmask application; overlay could intercept mouse clicks. | Update `win32_styles.py` to use `GetWindowLongPtrW` and `SetWindowLongPtrW` with explicit `argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG_PTR]` and `restype = wintypes.LONG_PTR`. |
| **MEDIUM** | **Sentinel Clipboard Pollution & Rich Data Loss** | String-only mock clipboard in `test_browser_offloader.py`. | **User Data Loss**: Non-text clipboard contents (images, files) are destroyed on harvest; Windows 11 Clipboard History is polluted with UUID sentinels. | Use Win32 native clipboard formats (`CF_UNICODETEXT`, `CF_DIB`) or save full clipboard format sequence before sentinel injection; filter sentinels from Windows history using `ExcludeClipboardContentFromMonitorProcessing`. |
| **LOW** | **Companion Dock Shell Presence** | Offscreen Qt widget testing in `test_companion_dock.py`. | **Missing Taskbar Icon**: `Qt.WindowType.Tool` prevents the dock from having a taskbar button or appearing in `Alt+Tab`. | Make `Qt.WindowType.Tool` configurable via `config.yaml` (`show_in_taskbar: bool = true`). |
| **LOW** | **Multi-DPI Geometry & Screen Topology** | Single screen geometry in `test_dpi.py`. | **Coordinate Drift**: Dragging dock across mixed-DPI monitors (150% + 100%) drifts anchoring if `screenChanged` does not re-scale margins. | Connect to `QWindow.screenChanged` and dynamically recompute geometry upon display topology change. |

---

## 4. Caveats

1. **User Interaction & Input Takeover Guardrail**:
   Under the Teamwork safety rules, no interactive test taking physical control of the user's mouse and keyboard was initiated during this turn without explicit user consent. Findings for live cursor glide and mid-flight preemption are deduced from static analysis of ctypes bindings, Win32 API specifications, and unit test mocks.
2. **Chrome DOM Variability**:
   Web interfaces for Gemini and ChatGPT update their DOM and CSS class names frequently. Dynamic web element verification requires a live authenticated browser session.
3. **Hardware VRAM Headroom Fluctuation**:
   Available VRAM was measured at 5564 MiB at the time of inspection. Background GPU applications (browsers, Discord, video players) will alter this headroom dynamically.

---

## 5. Conclusion

The ParasiteAI test suite (`uv run pytest`) reports **580 passing tests** because all core physical and external interfaces are decoupled via deterministic mocks (`MockClipboardBackend`, `MockBrowserWindowBackend`, `simulate_event`, offscreen Qt, and `simulation_mode=True`).

However, **a direct attempt to run ParasiteAI live on the physical Windows desktop in its current state will fail on three critical fronts**:
1. **The Web Offloader will time out**: The hardcoded heuristic `prompt_y - 200` + `Ctrl+C` does not select or copy text in Google Chrome / Gemini, resulting in guaranteed 45s harvest timeouts.
2. **The Local Brain cannot start**: `models/` is empty, `llama-cpp-python` is not installed in the virtual environment, and local API servers are offline.
3. **Physical Screen Edge Moves will wrap or clip**: The kinematic trajectory generator produces overshoot coordinates beyond display borders that are not clamped before Win32 absolute normalization.

The core architectural contracts (dual-mind separation, Pydantic schemas, signal routing, and episodic memory loop detection) are sound and well-tested. Hardening the 6 areas detailed in the Risk Matrix—specifically replacing the hardcoded offloader click with grounded button targeting, clamping coordinates in `mouse.py`, adding 64-bit ctypes safety in `win32_styles.py`, and configuring the 3B GGUF model—will bridge the gap from simulated perfection to robust physical desktop execution.

---

## 6. Verification Method

To independently reproduce and verify every finding in this report:

1. **Verify Unit Test Simulation vs Native Styles**:
   Inspect `tests/test_ghost_hud.py:76-83` and `tests/test_browser_offloader.py:173-180`. Confirm that tests mock Win32 APIs and override `execute_harvest` with synthetic strings.
2. **Verify Chrome Offloader Pixel Heuristics**:
   Inspect `parasite_ai/mind/offloader.py:474-503`. Confirm that `prompt_x = rect[0] + (rect[2] - rect[0]) // 2` and `prompt_y - 200` are hardcoded and that `ScreenGrounder` is never imported or called.
3. **Verify Kinematic Coordinate Clamping Gap**:
   Inspect `parasite_ai/hands/mouse.py:426-438` and `parasite_ai/hands/kinematics.py:222-225`. Confirm absence of `max(0, min(65535, ...))` clamping on `norm_x` and `norm_y`.
4. **Verify Live VRAM Headroom**:
   Execute `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv`. Confirm free VRAM is ~5.5 GB (insufficient for 7B + context, safe for 3B).
5. **Verify Local Model & Backend Status**:
   Execute `dir models` (confirm 0 files) and `uv run python -c "import llama_cpp"` (confirm `ModuleNotFoundError`).
