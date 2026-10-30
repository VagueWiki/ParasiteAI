# ParasiteAI — Architectural & Foundation Survey Report (R1)

**Author:** `teamwork_explorer_survey_1`  
**Timestamp:** 2026-10-29T11:01:00Z  
**Status:** Completed  
**Milestone:** Phase 0 — Scope Survey & Foundation Architecture  
**Target Scope:** R1 (Foundation & Zero-Config Local Brain Setup) and Core System Architecture  

---

## 1. Executive Summary & Philosophy

ParasiteAI is engineered as a **100% visible, desktop-native local AI assistant** that operates directly on the user's physical Windows desktop with **zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces**.

### Core Tenets
1. **Total Visibility & Transparency:** Every action, thought, target reticle, and web search occurs visibly on screen. The user watches the companion think, aim, move the physical mouse along natural curved trajectories, and type characters with human cadence.
2. **Instant Physical Safety Yield (<2ms):** The user maintains absolute supremacy. Moving the physical mouse or pressing any key triggers an instant hardware interrupt via low-level Win32 hooks (`LLMHF_INJECTED = 0`), halting synthetic actions in under 2ms.
3. **Dual-Mind Cognitive Pipeline:** Separation of creative persona voice (Pass 1: Persona Engine) from strict desktop command execution (Pass 2: Action Dispatcher), preventing KV-cache thrashing and maintaining character authenticity.
4. **Zero-Config Self-Contained Local Brain:** Integrated within the desktop GUI, supporting both local GGUF execution (quantized Qwen2.5 models tailored for 8 GB VRAM) and an instant **Browser-Only Zero-VRAM Mode** that allows immediate full desktop functionality without multi-gigabyte downloads.
5. **No Headless Automation:** Web interactions occur via real installed browsers (Google Chrome, Opera GX) through physical clicks, typed queries, visible streaming observation, and sentinel clipboard verification.

---

## 2. Hardware & Environment Profile Verification

Direct verification performed on the host system:
- **Operating System:** Windows 11 (build 26100 / AMD64)
- **Package Manager:** `uv 0.11.7` (`uv 0.11.7 (9d177269e 2026-04-15 x86_64-pc-windows-msvc)`)
- **Python Version:** Pinned to **Python 3.12** (`cpython-3.12.13-windows-x86_64-none` verified and fetched on demand via `uv`).
- **GUI Engine:** Python 3.12 native Tkinter 8.6 + Win32 `ctypes` (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST`) verified operational.
- **GPU:** NVIDIA GeForce RTX 4060 with **8188 MiB (8 GB) VRAM**, Driver 610.74, CUDA 13.3. Idle VRAM usage is ~800 MiB, leaving ~7.3 GB usable headroom.
- **Installed Browsers:**
  - **Google Chrome:** `C:\Program Files\Google\Chrome\Application\chrome.exe` (Verified present in system App Paths)
  - **Opera GX:** `C:\Users\Suici\AppData\Local\Programs\Opera GX\opera.exe` (Verified present in HKCU App Paths)

---

## 3. System Architecture & Threading Model

```
+----------------------------------------------------------------------------------------------------+
|                                     VISIBLE DESKTOP ENVIRONMENT                                    |
|                                                                                                    |
|  +-------------------------------------+             +------------------------------------------+  |
|  |     Companion Dock (UI Thread)      |             |        Ghost-Hand HUD (UI Overlay)       |  |
|  | - Live Speech Bubble & Thoughts     |             | - Fullscreen transparent Win32 layered   |  |
|  | - Mood / State Badge                |             | - Numbered Set-of-Mark boxes [#1, #2...] |  |
|  | - Goal Input & Pause/Panic Buttons  |             | - 300ms Pre-Click Target Reticle         |  |
|  | - Local Brain Manager Panel         |             | - Natural Bezier Glide Trajectory line   |  |
|  +------------------^------------------+             +--------------------^---------------------+  |
+---------------------|-----------------------------------------------------|------------------------+
                      |                                                     |                         
                      | Events / Telemetry Queue                            | Overlay Box Queue       
                      v                                                     v                         
+----------------------------------------------------------------------------------------------------+
|                                   CORE COGNITIVE & EVENT LOOP                                      |
|                                                                                                    |
|   +-----------------------+     +------------------------+     +-------------------------------+   |
|   | Hybrid Screen Ground  |     |  Episodic Working Mem  |     | Dual-Mind Pipeline            |   |
|   | - Fast Win32 UIA      |---->| - Action History (10)  |---->| - Pass 1: Persona Engine      |   |
|   | - Scoped RapidOCR     |     | - Screen Diff Verifier |     |   (Natural thought & voice)   |   |
|   | - Spatial Deduplicat. |     | - Loop / Stagnation Det|     | - Pass 2: Action Dispatcher   |   |
|   +-----------------------+     +------------------------+     |   (Strict JSON Action Dict)   |   |
|                                                                +---------------+---------------+   |
|                                                                                |                   |
+--------------------------------------------------------------------------------|-------------------+
                                                                                 | Dispatched Action 
                      +----------------------------------------------------------+                   
                      v                                                                               
+-----------------------------------------------------+  +------------------------------------------+
|            SAFETY & HARDWARE HOOK LAYER             |  |         PHYSICAL EXECUTION LAYER         |
|                                                     |  |                                          |
| - Low-Level Win32 Hook: WH_MOUSE_LL / WH_KEYBOARD_LL|  | - HumanHandsController                   |
| - Filters LLMHF_INJECTED (0x1) vs Physical (0x0)    |  |   - Cubic Bezier curves with Fitts' Law  |
| - Instant < 2ms Abort on physical touch             |  |   - Micro-jitter & overshoot             |
| - Window Guard: Pauses on sensitive/blacklisted apps|  |   - Unicode character typing with jitter |
| - Global Panic Hotkey & Corner Slamming             |  | - Browser Brain Offload State Machine    |
|                                                     |  |   - Visible Chrome / Opera GX interaction|
|                                                     |  |   - Sentinel Clipboard Verification      |
+-----------------------------------------------------+  +------------------------------------------+
```

### Threading & Concurrency Architecture
1. **Main GUI Thread:**
   - Runs the Tkinter mainloop for `CompanionDock`.
   - Manages the `GhostHUD` transparent overlay window.
   - Consumes telemetry and render commands from a thread-safe `queue.Queue`.
   - Ensures 60 FPS smooth rendering without locking cognitive loops.
2. **Cognitive Worker Thread:**
   - Runs the perception -> cognition -> dispatch loop.
   - Drives `HybridGroundingEngine`, `PersonaEngine`, `ActionDispatcher`, and `EpisodicWorkingMemory`.
   - Dispatches physical actions to `HumanHandsController`.
3. **Safety & Hook Thread:**
   - Dedicated Win32 message pump for `SetWindowsHookExW` (`WH_MOUSE_LL` and `WH_KEYBOARD_LL`).
   - Atomic flag `interrupt_flag = threading.Event()`.
   - Polled every 8ms during Bezier glide steps; aborts in <2ms on hardware touch.
4. **Model Inference / Download Worker Thread:**
   - Non-blocking GGUF model download via HuggingFace Hub with streaming progress reporting.
   - Offloads blocking LLM prompt generation to prevent GUI freezing.

---

## 4. Directory Structure & Code Layout

In strict accordance with `PROJECT.md` conventions, all agent metadata remains in `.agents/teamwork/`, while project code is organized into a modular, clean hierarchy:

```
g:\__Docs\ParasiteAI\
├── .agents\
│   └── teamwork\                          # Agent communication, briefings, handoffs (NO source code)
├── config.yaml                            # User & runtime configuration
├── pyproject.toml                         # Project metadata, pinned dependencies, uv setup
├── main.py                                # Master entry point for desktop launch
├── launch_parasite.bat                    # Windows one-click desktop launcher
├── models\                                # Local GGUF models storage (ignored by git / agent rules)
├── parasite_ai\                           # Core application package
│   ├── __init__.py                        # Version & package exports
│   ├── config.py                          # Pydantic schema validation & YAML config loader
│   ├── core.py                            # Master orchestrator & main event loop
│   ├── mind\                              # Cognitive, memory, and model subsystems
│   │   ├── __init__.py
│   │   ├── brain_manager.py               # Local Brain Manager (R1: GGUF downloader, runtime, zero-VRAM toggle)
│   │   ├── dual_mind.py                   # Pass 1 PersonaEngine + Pass 2 ActionDispatcher
│   │   ├── memory.py                      # EpisodicWorkingMemory, screen diffing, loop detector
│   │   └── offloader.py                   # Visible Browser Brain Offloader (Chrome/Opera GX + Sentinel)
│   ├── vision\                            # Perception & screen grounding
│   │   ├── __init__.py
│   │   ├── capture.py                     # Fast mss screen capture & perceptual diffing
│   │   └── grounding.py                   # HybridGroundingEngine (Win32 UIA + scoped RapidOCR + SoM)
│   ├── hands\                             # Physical input execution
│   │   ├── __init__.py
│   │   ├── controller.py                  # HumanHandsController (Bezier mouse, Unicode typing)
│   │   └── kinematics.py                  # Human-like trajectory generator (overshoot, micro-jitter)
│   ├── safety\                            # Hardware hooks & security
│   │   ├── __init__.py
│   │   ├── interrupt_guard.py             # Win32 LLMHF_INJECTED hook & <2ms abort handler
│   │   └── window_guard.py                # Foreground window title & class inspector, no-fly rules
│   └── ui\                                # Desktop graphical user interfaces
│       ├── __init__.py
│       ├── companion_dock.py              # Always-on-top desktop dock (speech, mood, telemetry, controls)
│       └── ghost_hud.py                   # Transparent click-through layered Win32 overlay (SoM boxes)
└── tests\                                 # Automated test suite (executed via `uv run pytest`)
    ├── __init__.py
    ├── test_config.py                     # Config loading & Pydantic schema validation
    ├── test_brain_manager.py              # Brain Manager status, downloader mock, zero-VRAM toggle
    ├── test_interrupt_guard.py            # Synthetic vs physical input hook abort verification
    ├── test_grounding.py                  # Hybrid grounding & SoM coordinate extraction
    └── test_memory_and_offload.py         # Episodic memory loops & Sentinel clipboard verification
```

---

## 5. Dependency Architecture & `pyproject.toml`

### Build System & Python Pinning
- **Build backend:** `hatchling`
- **Python version constraint:** `requires-python = ">=3.12,<3.13"`
  - *Rationale:* Python 3.12 guarantees prebuilt binary wheels for all native Windows libraries (`uiautomation`, `rapidocr-onnxruntime`, `numpy`, `pillow`, `pynput`), avoiding C++ MSVC compilation bottlenecks on developer machines.

### Dependency Manifest
| Package | Version Spec | Subsystem | Technical Purpose & Rationale |
|---------|--------------|-----------|-------------------------------|
| `pydantic` | `>=2.6.0` | Core / Config | Robust schema validation for `config.yaml`, typed action dictionaries, telemetry payloads. |
| `pyyaml` | `>=6.0.1` | Core / Config | Parsing and serializing human-readable configuration files. |
| `mss` | `>=9.0.1` | Vision / Perception | Ultra-fast screen capture via direct Windows GDI/DirectX screen buffers (~10-15ms per frame). |
| `pillow` | `>=10.2.0` | Vision / UI | Image manipulation, cropping bounding boxes, HUD icon rendering. |
| `numpy` | `>=1.26.0` | Vision / Mind | High-speed array operations for perceptual frame diffing and Bezier trajectory calculation. |
| `pyautogui` | `>=0.9.54` | Hands / Utility | Screen resolution detection, secondary coordinate helpers. |
| `pytweening` | `>=1.2.0` | Hands / Kinematics | Cubic, sinusoidal, and exponential easing curves for natural mouse acceleration/deceleration. |
| `pynput` | `>=1.7.6` | Safety / Hands | Mouse and keyboard event listening and low-level hook interfacing. |
| `uiautomation` | `>=2.0.19` | Vision / Grounding | Direct Win32 / COM accessibility tree traversal (0 MB VRAM, ~15ms, exact UI element coordinates). |
| `rapidocr-onnxruntime` | `>=1.3.8` | Vision / Grounding | Lightweight ONNX-based CPU OCR for text detection inside custom canvas/web elements without GPU VRAM impact. |
| `pyperclip` | `>=1.8.2` | Mind / Offloader | System clipboard management for the Sentinel Clipboard save/verify/restore protocol. |
| `httpx` | `>=0.27.0` | Mind / Brain | Async/sync HTTP client for local inference servers (Ollama/llama.cpp server) and web AI coordination. |
| `huggingface-hub` | `>=0.23.0` | Mind / Brain | Programmatic model discovery and streaming GGUF downloads with progress callbacks. |

### Optional / Pluggable Local Inference
- `llama-cpp-python` (optional): Prebuilt GGUF runner with CUDA/CPU offload. If not pre-compiled, Brain Manager cleanly falls back to an external local server (e.g. `llama-server.exe` / Ollama) or **Browser-Only Mode**, ensuring the application never crashes on startup.

### Development & Testing Dependencies
```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]
```

---

## 6. Configuration Schema (`config.yaml`)

The configuration file must be declarative, fully documented, and strictly validated via Pydantic.

```yaml
# ParasiteAI System Configuration

system:
  log_level: "INFO"
  integrity_mode: "development"
  data_dir: "data"
  models_dir: "models"

persona:
  name: "Parasite"
  avatar: "cyber_cat"
  voice_style: "witty_desktop_companion"
  verbosity: "normal"  # concise, normal, verbose
  system_prompt: |
    You are Parasite, a desktop-native AI companion living on the user's screen.
    You have direct physical control of the mouse and keyboard when authorized.
    Speak naturally, expressively, and vividly in character.
    Always provide commentary on what you observe on screen before taking action.

mind:
  mode: "browser_offload"  # "local_llm", "browser_offload", or "hybrid"
  local_model:
    model_id: "Qwen/Qwen2.5-3B-Instruct-GGUF"
    filename: "qwen2.5-3b-instruct-q4_k_m.gguf"
    context_size: 4096
    gpu_layers: -1  # -1 = auto-offload to RTX 4060 VRAM, 0 = CPU only
    vram_budget_mb: 5500  # Enforces safe ceiling within 8 GB VRAM
    local_endpoint: "http://127.0.0.1:8080/v1"
  offload:
    preferred_browser: "chrome"  # "chrome" or "opera_gx"
    browser_paths:
      chrome: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
      opera_gx: "C:\\Users\\Suici\\AppData\\Local\\Programs\\Opera GX\\opera.exe"
    default_web_ai_url: "https://gemini.google.com"
    stream_stability_ms: 1500
    stream_timeout_sec: 45
    sentinel_token_prefix: "__PARASITE_SENTINEL__"

hands:
  mouse:
    speed_factor: 1.0
    trajectory_type: "cubic_bezier"
    overshoot_radius_px: 12
    micro_jitter_amplitude_px: 2
    step_delay_ms: 8
    preview_reticle_ms: 300
  keyboard:
    typing_wpm: 85
    cadence_jitter_ms: [25, 75]
    micro_pause_probability: 0.04
    micro_pause_duration_ms: [200, 600]

safety:
  interrupt_enabled: true
  interrupt_latency_budget_ms: 2.0
  override_pause_duration_sec: 10.0
  panic_hotkey: "ctrl+alt+backspace"
  corner_panic_enabled: true
  sensitive_window_titles:
    - "Bitwarden"
    - "1Password"
    - "KeePass"
    - "Task Manager"
    - "Administrator:"
    - "Windows Security"
    - "Registry Editor"

vision:
  grounding_mode: "hybrid"  # "hybrid" = uiautomation + scoped rapidocr
  max_som_elements: 60
  screen_diff_threshold: 0.02
  ocr_scoped_only: true
  som_glow_color: "#00FFCC"

ui:
  dock:
    width: 380
    height: 520
    anchor: "bottom_right"
    opacity: 0.95
    always_on_top: true
  hud:
    enabled: true
    fps_target: 60
    reticle_color: "#FF3366"
    som_box_color: "#00E5FF"
```

---

## 7. Local Brain Manager (R1) Technical Architecture

The **Local Brain Manager** (`parasite_ai/mind/brain_manager.py`) is the core component satisfying requirement R1. It eliminates the need for users to manually configure CLI servers or complex local environments.

### Key Responsibilities & Capabilities
1. **Model Discovery & Integrity Check:**
   - Scans the configured `models/` directory for `.gguf` files.
   - Validates file existence and file size against expected model specifications.
2. **Streaming Model Downloader with UI Callbacks:**
   - Uses `huggingface_hub.hf_hub_download` or streaming chunked HTTP to fetch quantized models:
     - Primary: `Qwen/Qwen2.5-3B-Instruct-GGUF` (file: `qwen2.5-3b-instruct-q4_k_m.gguf`, ~2.0 GB).
     - Heavy alternative: `Qwen/Qwen2.5-7B-Instruct-GGUF` (file: `qwen2.5-7b-instruct-q4_k_m.gguf`, ~4.7 GB).
   - Emits granular download progress events: `(bytes_downloaded, total_bytes, percentage, speed_mbps)`.
   - UI reflects live progress bar directly within the Companion Dock.
3. **Zero-VRAM / Browser-Only Mode (Immediate Out-of-the-Box Operation):**
   - A 1-click toggle in the Companion Dock allowing immediate live desktop execution without downloading any local GGUF weights.
   - Routes cognitive tasks directly through the **Visible Browser Brain Offloader** (Chrome / Opera GX -> Gemini Web / ChatGPT).
4. **VRAM Safety & GPU Budget Enforcement:**
   - Dedicated RTX 4060 safety checks: queries active VRAM before loading model weights.
   - Pins model layers to fit within ~5.5 GB VRAM, reserving 2.5 GB for Windows DWM and browser rendering.
5. **Unified Inference Interface Contract:**
   - Both local GGUF models and external fallbacks implement a common interface:
     ```python
     class BrainManager:
         def get_status(self) -> BrainStatus: ...
         def start_download(self, model_id: str, callback: Callable) -> None: ...
         def load_model(self) -> bool: ...
         def unload_model(self) -> None: ...
         def generate_thought(self, scene_summary: str, memory_context: str, goal: str) -> str: ...
         def generate_action(self, persona_intent: str, som_table: list[dict]) -> dict: ...
         def toggle_browser_only_mode(self, enabled: bool) -> None: ...
     ```

---

## 8. Interfaces & Inter-Module Communication

To maintain decoupling and rock-solid testability, modules communicate via typed Pydantic data schemas:

### State Machine Definition
```python
from enum import Enum

class SystemState(str, Enum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    THINKING = "THINKING"
    DRIVING = "DRIVING"
    OFFLOADING = "OFFLOADING"
    USER_OVERRIDE = "USER_OVERRIDE"
    PROTECTED_PAUSE = "PROTECTED_PAUSE"
    PANIC = "PANIC"
```

### Action Command Schema
```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Tuple

class ActionType(str, Enum):
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    CLICK_AND_TYPE = "CLICK_AND_TYPE"
    HOTKEY = "HOTKEY"
    SCROLL = "SCROLL"
    WAIT = "WAIT"
    OFFLOAD_WEB_AI = "OFFLOAD_WEB_AI"
    DONE = "DONE"

class ActionCommand(BaseModel):
    action: ActionType
    target_id: Optional[int] = None
    target_label: Optional[str] = None
    coordinates: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    submit: bool = False
    hotkey: Optional[str] = None
    scroll_amount: Optional[int] = None
    wait_ms: Optional[int] = None
    reasoning: Optional[str] = None
```

### Grounding Element Schema
```python
class GroundedElement(BaseModel):
    id: int
    role: str               # "Button", "Edit", "Tab", "Text", etc.
    label: str              # Accessible name or OCR text
    bbox: Tuple[int, int, int, int]  # (left, top, right, bottom)
    center: Tuple[int, int]          # (x, y)
    confidence: float = 1.0
```

---

## 9. Entry Points & Desktop Launcher Architecture

1. **`main.py`:**
   - Initializes structured logging.
   - Loads and validates `config.yaml` using Pydantic `Config`.
   - Checks system dependencies and GPU profile.
   - Instantiates `SafetyGuard` (`InterruptGuard` + `WindowGuard`).
   - Launches `CompanionDock` (UI mainloop) and `GhostHUD` (transparent Win32 overlay).
   - Starts `BrainManager` in the configured mode (defaulting to Browser-Only Zero-VRAM mode if no model is loaded yet).
   - Spawns background worker loop connecting perception, memory, cognition, and physical execution.
2. **`launch_parasite.bat`:**
   - Double-clickable Windows batch launcher:
     - Verifies `uv` is installed; prints clear instructions if missing.
     - Runs `uv sync` to ensure dependencies match `pyproject.toml`.
     - Executes `uv run python main.py`.
     - Keeps the console open on unexpected errors so the user can see diagnostics.

---

## 10. Automated Verification Plan (R1 & Foundation)

The test suite under `tests/` verifies the foundation without requiring live hardware interaction or GPU execution:
1. **`test_config.py`:**
   - Validates that `config.yaml` loads correctly and parses into Pydantic models.
   - Verifies default fallback values for missing keys.
   - Asserts invalid types (e.g. negative VRAM budget, non-numeric speeds) raise validation errors.
2. **`test_brain_manager.py`:**
   - Tests `BrainManager` initialization in both `local_llm` and `browser_offload` modes.
   - Verifies model presence/absence detection in `models/`.
   - Tests download progress callback handling via mock streaming chunks.
   - Verifies zero-VRAM browser-only toggle immediately sets ready status.
   - Tests structured thought and action parsing when given mock LLM responses.

---

## 11. Summary of Constraints & Findings

1. **Python 3.12 is optimal:** System has `uv 0.11.7` which downloads `cpython-3.12.13-windows-x86_64-none` directly. Tkinter 8.6 is bundled in this build, eliminating any C++ GUI dependencies.
2. **Hardware Verified:** RTX 4060 has 8188 MiB VRAM with 7.3 GB free. `Qwen2.5-3B-Instruct-Q4_K_M` (~2.0 GB) and `Qwen2.5-7B-Instruct-Q4_K_M` (~4.7 GB) fit comfortably within the safe GPU budget.
3. **Browsers Verified:** Both Google Chrome and Opera GX are installed in their standard locations.
4. **Clean Handoff:** All technical specifications, schemas, interfaces, and directory layouts are finalized and ready for the implementation track.
