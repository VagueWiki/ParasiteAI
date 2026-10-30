# Local Brain Manager Architecture & Technical Specification

**Author:** `teamwork_explorer_m1_3`  
**Target Module:** `parasite_ai/mind/brain_manager.py`  
**Test Suite:** `tests/test_brain_manager.py`  
**Milestone:** M1 (Foundation & Zero-Config Setup)  
**Status:** Architecture Recommendation & Blueprint  

---

## 1. Executive Summary & Purpose

ParasiteAI operates as a 100% visible, desktop-native assistant on Windows 11. Cognitive execution powers two core passes:
1. **Pass 1 (Persona Engine):** Natural language character thoughts and spoken monologue displayed in the Companion Dock.
2. **Pass 2 (Action Dispatcher):** Deterministic translation of the Persona's intent and on-screen Set-of-Mark elements into structured JSON action commands (`CLICK`, `CLICK_AND_TYPE`, `HOTKEY`, `SCROLL`, `WAIT`, `OFFLOAD_WEB_AI`, `DONE`).

In conventional local AI setups, users encounter friction: multi-gigabyte mandatory downloads, complex CLI server configurations (Ollama / llama.cpp compilation), and GPU VRAM crashes when gaming or running browser tabs.

The **Local Brain Manager** (`parasite_ai/mind/brain_manager.py`) is engineered to solve these challenges through four foundational pillars:
- **Zero-Config Out-of-the-Box Execution:** If no local model is downloaded, ParasiteAI boots instantly in **Zero-VRAM Browser Offload Mode**, immediately capable of physical desktop operations via Google Chrome or Opera GX without waiting for multi-gigabyte downloads.
- **Self-Contained Local Model Management:** Discovers, validates, and manages GGUF weights inside a dedicated `models/` folder, checking GGUF magic headers and file integrity.
- **Non-Blocking Streaming Downloader:** Enables 1-click model downloads directly from HuggingFace Hub with a real-time progress callback hook (bytes, speed, ETA, percentage) feeding the Companion Dock UI.
- **Unified Inference Dispatch Contract:** Provides a single, polymorphic interface abstracting in-process `llama-cpp-python`, local OpenAI-compatible HTTP servers (`llama-server`, Ollama), the physical browser offloader, and deterministic mocks for unit tests.

---

## 2. System Architecture & Component Interactions

```
+----------------------------------------------------------------------------------------------------+
|                                      COMPANION DOCK (UI)                                           |
|  - Brain Status Pill: [READY (Local LLM)] or [READY (Zero-VRAM Offload)] or [DOWNLOADING (45%)]    |
|  - 1-Click Toggle: [Enable Browser-Only Mode (0 VRAM)]                                            |
|  - 1-Click Action: [Download Recommended Qwen2.5-3B (2.1 GB)] -> Progress Bar                       |
+--------------------------------------------------^-------------------------------------------------+
                                                   | Status / Progress Events
                                                   v
+----------------------------------------------------------------------------------------------------+
|                               LOCAL BRAIN MANAGER (`brain_manager.py`)                              |
|                                                                                                    |
|  +--------------------+  +--------------------+  +---------------------+  +---------------------+  |
|  |   Status Monitor   |  |   Directory Mgr    |  | Downloader & Hooks  |  |  VRAM Budget Guard  |  |
|  | - State machine    |  | - models/ scan     |  | - Background thread |  | - RTX 4060 ceiling  |  |
|  | - Backend selector |  | - GGUF header check|  | - Chunk streaming   |  |   (5.5 GB safe max)  |  |
|  | - Dynamic fallback |  | - Atomic rename    |  | - Cancel token      |  | - Layer auto-split  |  |
|  +--------------------+  +--------------------+  +---------------------+  +---------------------+  |
|                                                                                                    |
|  +-----------------------------------------------------------------------------------------------+  |
|  |                              Unified Inference Dispatch Router                                 |  |
|  |                                                                                               |  |
|  |  [Case 1: Local GGUF]        [Case 2: Local Server]      [Case 3: Browser Offload] [Case 4: Mock]|  |
|  |  LlamaCppBackend             OpenAIEndpointBackend       BrowserOffloadBackend     MockBackend  |  |
|  |  (In-process C++/CUDA)       (HTTP :8080/v1 or :11434)   (Chrome/Opera GX Web AI)  (Unit Tests) |  |
|  +-----------------------------------------------------------------------------------------------+  |
+--------------------------------------------------^-------------------------------------------------+
                                                   | generate_thought() / generate_action()
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                      COGNITIVE ENGINE                                              |
|  - Pass 1: Persona Engine (Character monologue, speech bubble stream)                              |
|  - Pass 2: Action Dispatcher (Structured JSON command, SoM #ID selection)                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. State Machine & Status Management

### 3.1 Mode and State Enumerations

```python
from enum import Enum

class BrainMode(str, Enum):
    """Configured operating mode for the Brain subsystem."""
    LOCAL_LLM = "local_llm"            # In-process GGUF or local HTTP server
    BROWSER_OFFLOAD = "browser_offload"# Zero-VRAM mode using desktop browser web AI
    HYBRID = "hybrid"                  # Local LLM for quick actions, Browser for deep reasoning
    MOCK = "mock"                      # Deterministic mock backend for automated testing

class BrainState(str, Enum):
    """Runtime lifecycle state of the Brain."""
    UNINITIALIZED = "UNINITIALIZED"
    NO_MODEL_PRESENT = "NO_MODEL_PRESENT"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOAD_PAUSED = "DOWNLOAD_PAUSED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    MODEL_READY_ON_DISK = "MODEL_READY_ON_DISK"
    LOADING = "LOADING"
    READY_LOCAL = "READY_LOCAL"
    READY_BROWSER_OFFLOAD = "READY_BROWSER_OFFLOAD"
    INFERRING = "INFERRING"
    ERROR = "ERROR"
```

### 3.2 Telemetry & Status Data Models

```python
from pydantic import BaseModel
from typing import Optional, List

class ModelMetadata(BaseModel):
    """Information regarding a detected or downloadable model."""
    model_id: str                      # HuggingFace repo (e.g., 'Qwen/Qwen2.5-3B-Instruct-GGUF')
    filename: str                      # GGUF filename (e.g., 'qwen2.5-3b-instruct-q4_k_m.gguf')
    filesize_bytes: int                # Exact or expected size
    filesize_display: str              # E.g., '2.17 GB'
    is_downloaded: bool = False
    is_valid_gguf: bool = False
    file_path: Optional[str] = None
    recommended_gpu_layers: int = -1   # -1 = auto full GPU offload on RTX 4060
    vram_required_mb: int = 3500       # Estimated VRAM footprint with 4K context

class DownloadProgress(BaseModel):
    """Live streaming download metrics dispatched to UI callbacks."""
    model_id: str
    filename: str
    bytes_downloaded: int
    total_bytes: int
    percentage: float                  # 0.0 to 100.0
    speed_mbps: float                  # Current download speed
    eta_seconds: float                 # Estimated time remaining
    elapsed_seconds: float
    status: str                        # 'downloading', 'verifying', 'completed', 'failed', 'cancelled'

class BrainStatus(BaseModel):
    """Comprehensive snapshot of the Brain subsystem state."""
    mode: BrainMode
    state: BrainState
    active_backend: str                # 'llama_cpp', 'openai_endpoint', 'browser_offload', 'mock'
    current_model: Optional[str] = None
    available_models: List[ModelMetadata] = []
    download_progress: Optional[DownloadProgress] = None
    vram_budget_mb: int = 5500
    vram_used_mb: Optional[int] = None
    vram_free_mb: Optional[int] = None
    status_message: str = "Ready"
```

---

## 4. Directory Management (`models/`)

### 4.1 Storage Policy
- **Configurable Location:** `models_dir` specified in `config.yaml` (default: `models` relative to project root).
- **Auto-Creation:** If the directory does not exist, `LocalBrainManager` creates it automatically with safe permissions.
- **Git Hygiene:** Only code and configs are committed. Model binaries (`*.gguf`) and incomplete chunks (`*.tmp`) reside in `models/` and are ignored by git.
- **Atomic File Management:** Downloads are written to `.tmp` files (e.g. `qwen2.5-3b-instruct-q4_k_m.gguf.tmp`) and atomically renamed upon SHA/GGUF header validation. This prevents the manager from loading corrupted, partial downloads.

### 4.2 GGUF Magic Header Integrity Validation
A file may exist on disk with the `.gguf` extension due to an aborted download or corrupt write. `LocalBrainManager` performs binary validation before reporting the model as valid:
1. Open the file in binary mode (`"rb"`).
2. Read the first 4 bytes. GGUF specification dictates magic bytes `0x47 0x47 0x55 0x46` (ASCII string `"GGUF"`).
3. Read the next 4 bytes as unsigned 32-bit little-endian integer (`<I`). This represents the GGUF specification version (versions 2 and 3 supported).
4. Verify file length > 1 MB.

```python
def validate_gguf_header(filepath: Path) -> bool:
    """Verifies that the target file exists and possesses a valid GGUF magic header."""
    if not filepath.exists() or filepath.stat().st_size < 1024 * 1024:
        return False
    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                return False
            version_bytes = f.read(4)
            if len(version_bytes) < 4:
                return False
            version = struct.unpack("<I", version_bytes)[0]
            return version in (2, 3)
    except Exception:
        return False
```

### 4.3 Model Catalog
`LocalBrainManager` maintains a built-in catalog of curated models tuned for 8 GB VRAM:
1. **Recommended Default (`Qwen2.5-3B-Instruct-Q4_K_M`):**
   - Repo: `Qwen/Qwen2.5-3B-Instruct-GGUF`
   - File: `qwen2.5-3b-instruct-q4_k_m.gguf`
   - Size: ~2.17 GB
   - VRAM Footprint: ~3.2 GB with 4096 context.
   - Fits on host RTX 4060 with > 4.5 GB headroom for Windows DWM and browser tabs.
2. **Heavy Reasoning Alternative (`Qwen2.5-7B-Instruct-Q4_K_M`):**
   - Repo: `Qwen/Qwen2.5-7B-Instruct-GGUF`
   - File: `qwen2.5-7b-instruct-q4_k_m.gguf`
   - Size: ~4.68 GB
   - VRAM Footprint: ~5.4 GB with 4096 context.
   - Maxes out the 5.5 GB safe VRAM budget on RTX 4060.
3. **Ultra-Light Alternative (`Qwen2.5-1.5B-Instruct-Q4_K_M`):**
   - Repo: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`
   - File: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
   - Size: ~1.12 GB
   - VRAM Footprint: ~1.8 GB. Runs fast on CPU-only or low-end systems.

---

## 5. Non-Blocking Streaming Downloader & Progress Hooks

### 5.1 Architecture & Threading
Downloading multi-gigabyte models over HTTPS must never block the GUI thread.
- **Worker Thread:** `DownloadThread(threading.Thread)` runs as a daemon thread.
- **Cancellation:** Driven by an atomic `threading.Event()` (`cancel_event`).
- **Throttled Callback:** Dispatches `DownloadProgress` events at a controlled rate (~4 updates/sec or every 1 MB) to prevent flooding the UI event queue.

### 5.2 Resilient Download Pipeline
1. Check available disk space in `models/` (requires at least 1.2x expected file size).
2. Generate temporary path: `models/{filename}.download.tmp`.
3. Support resume if server supports `Range: bytes=X-` and partial file exists.
4. Stream chunks (chunk size: 256 KB) via `httpx.stream("GET", url, follow_redirects=True)` or `huggingface_hub.hf_hub_download`.
5. Calculate metrics on each chunk:
   - `bytes_downloaded`
   - `speed_mbps = (bytes_in_window) / (time_window)`
   - `eta_seconds = remaining_bytes / current_speed`
   - `percentage = (bytes_downloaded / total_bytes) * 100.0`
6. Check `cancel_event.is_set()` on each chunk. If cancelled:
   - Close stream immediately.
   - Clean up temporary file or preserve for resume.
   - Emit `status = "cancelled"` callback.
7. Upon successful stream completion:
   - Validate GGUF header on `.tmp` file.
   - Atomically rename `.tmp` to `{filename}`.
   - Emit `status = "completed"` callback.
   - Update internal state to `BrainState.MODEL_READY_ON_DISK`.

---

## 6. Zero-VRAM Browser Offload Fallback

### 6.1 Rationale & Instant Availability
When a user launches ParasiteAI for the first time, downloading 2–5 GB may take 5–15 minutes depending on connection speed. ParasiteAI avoids any mandatory download blocking startup:
- If no `.gguf` file exists in `models/`, `LocalBrainManager` automatically falls back to `BrainMode.BROWSER_OFFLOAD`.
- The user can begin issuing desktop automation tasks immediately.
- Cognitive queries are routed to the **Visible Browser Brain Offloader** (`parasite_ai/mind/offloader.py`), which uses the user's installed Google Chrome or Opera GX to query Gemini Web or ChatGPT visibly, extracting responses via Sentinel Clipboard Verification.

### 6.2 1-Click Dynamic Mode Toggling
Users can dynamically switch between modes at runtime via `LocalBrainManager.toggle_browser_only_mode(enabled: bool)`:
- **Toggled ON (`enabled=True`):**
  - Unloads any local model from VRAM/RAM immediately via `unload_model()`.
  - Sets mode to `BrainMode.BROWSER_OFFLOAD` and state to `BrainState.READY_BROWSER_OFFLOAD`.
  - VRAM consumption drops to 0 MB.
- **Toggled OFF (`enabled=False`):**
  - If a local GGUF model is present in `models/`, automatically loads it into memory.
  - Switches state to `BrainState.READY_LOCAL`.
  - If no model is on disk, alerts UI that download is required while remaining in browser offload.

---

## 7. Unified Inference Dispatch Interface

### 7.1 Backend Protocol Contract

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Generator

class InferenceBackend(ABC):
    """Abstract polymorphic interface for all LLM inference providers."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the backend is initialized and ready to serve inference."""
        pass
        
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False
    ) -> str:
        """Executes synchronous inference and returns generated text."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Releases all allocated memory/VRAM resources."""
        pass
```

### 7.2 Backend Implementations

#### 1. `LlamaCppBackend` (In-Process GGUF Runner)
- Uses `llama_cpp.Llama` if installed.
- Parameters:
  - `model_path`: Path to `models/{filename}`.
  - `n_gpu_layers`: Auto-offloaded (e.g., `-1` for RTX 4060, or dynamically calculated to adhere to `vram_budget_mb = 5500`).
  - `n_ctx`: 4096 tokens.
  - `n_threads`: 8 (matching CPU physical cores).
- Graceful VRAM handling: If CUDA initialization fails or raises OOM, falls back to `n_gpu_layers=0` (CPU) or alerts manager to trigger browser offload.

#### 2. `OpenAIEndpointBackend` (Local Server Adapter)
- Connects to an external local inference server (e.g., `llama-server.exe`, Ollama at `http://127.0.0.1:11434/v1`, vLLM, LM Studio).
- Uses `httpx.Client(timeout=30.0)` to call `POST /v1/chat/completions`.
- Provides zero-code setup for users who already run Ollama or llama-server on their machine.

#### 3. `BrowserOffloadBackend` (Physical Desktop Web AI)
- Coordinates with `parasite_ai/mind/offloader.py`.
- Formats prompts for web AI (Gemini Web or ChatGPT).
- Initiates visible browser navigation and sentinel clipboard capture.
- Returns harvested clean text.

#### 4. `MockBackend` (Automated Testing & Simulation)
- Deterministic backend for unit testing (`pytest`) and CI/CD.
- Configurable response queues or rule-based matching.
- Guarantees `uv run pytest` runs in < 2 seconds without requiring GPU or network.

---

## 8. High-Level Cognitive Dispatchers

`LocalBrainManager` provides two dedicated high-level entry points aligned with the Dual-Mind architecture:

### 8.1 Pass 1: Persona Monologue Generation
```python
def generate_thought(
    self,
    scene_summary: str,
    memory_context: str,
    user_goal: str
) -> str:
    """
    Generates natural language character speech and inner thoughts (Pass 1).
    Does NOT contain strict JSON rules to prevent character lobotomization.
    """
```
- **System Prompt:** Sourced from `config.persona.system_prompt` (cyber companion persona).
- **Context:** Human-readable window title, visible controls list, previous actions from episodic memory.
- **Output:** Expressive string streamed directly to the Companion Dock speech bubble.

### 8.2 Pass 2: Action Command Generation
```python
def generate_action(
    self,
    persona_intent: str,
    som_elements: List[Dict[str, Any]],
    memory_context: str
) -> Dict[str, Any]:
    """
    Translates the Persona's intent and Set-of-Mark numbered elements into a
    deterministic JSON action command (Pass 2).
    """
```
- **System Prompt:** Strict JSON-only action dispatch schema.
- **Context:** `persona_intent` from Pass 1 + compact table of grounded UI elements `[#ID, Role, Label, X, Y]`.
- **Parsing & Resilience:**
  - Extracts JSON payload using regex matching `r"\{[\s\S]*\}"` to tolerate markdown fences (` ```json `).
  - Validates parsed dict against `ActionCommand` schema (`ActionType`, `target_id`, `coordinates`, `text`).
  - If parsing fails or selected element is invalid, returns safe fallback: `ActionCommand(action="WAIT", wait_ms=1000, reasoning="Re-evaluating target...")`.

---

## 9. VRAM Safety & GPU Budget Enforcement

### 9.1 RTX 4060 Profile Constraints
- Total VRAM: 8188 MiB (8 GB).
- Windows 11 DWM (Desktop Window Manager) + Chrome/Opera GX idle consume ~1.5 to 2.5 GB.
- Safe ceiling for local model: **5500 MiB**.
- If memory spills beyond 8 GB into Windows Shared System Memory, inference speed degrades by 10x–20x (from 45 tok/s to 2 tok/s).

### 9.2 VRAM Guard Logic
```python
def check_vram_headroom() -> Tuple[int, int]:
    """
    Returns (used_vram_mb, free_vram_mb) for the primary NVIDIA GPU.
    Falls back gracefully if nvidia-smi / pynvml is unavailable.
    """
```
- Before loading GGUF weights, `LocalBrainManager` verifies `free_vram_mb >= model.vram_required_mb`.
- If headroom is insufficient:
  - Dynamically reduces `n_gpu_layers` to offload upper transformer layers to system RAM while keeping lower layers in VRAM.
  - Or, if free VRAM < 2000 MB, switches automatically to Browser Offload mode to prevent system stutter.

---

## 10. Concrete Code Specifications for Worker

The worker implementing `parasite_ai/mind/brain_manager.py` should follow this class structure:

```python
"""
parasite_ai/mind/brain_manager.py
Zero-Config Local Brain Manager for ParasiteAI.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import threading
import struct
import json
import re

from parasite_ai.config import AppConfig

class LocalBrainManager:
    def __init__(self, config: AppConfig, offloader=None):
        self.config = config
        self.offloader = offloader
        self.models_dir = Path(config.system.models_dir)
        self.mode = BrainMode(config.mind.mode)
        self.state = BrainState.UNINITIALIZED
        self.active_backend: Optional[InferenceBackend] = None
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_download_event = threading.Event()
        self._current_progress: Optional[DownloadProgress] = None
        self._lock = threading.Lock()
        
        # Initialize storage & assess readiness
        self.ensure_models_dir()
        self.refresh_status()

    def ensure_models_dir(self) -> Path: ...
    def scan_models(self) -> List[ModelMetadata]: ...
    def get_status(self) -> BrainStatus: ...
    def refresh_status(self) -> BrainStatus: ...
    
    def start_download(
        self,
        model_id: Optional[str] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> bool: ...
    
    def cancel_download(self) -> None: ...
    def load_model(self, filename: Optional[str] = None) -> bool: ...
    def unload_model(self) -> None: ...
    def toggle_browser_only_mode(self, enabled: bool) -> None: ...
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str: ...
    def generate_thought(self, scene_summary: str, memory_context: str, user_goal: str) -> str: ...
    def generate_action(self, persona_intent: str, som_elements: List[Dict[str, Any]], memory_context: str) -> Dict[str, Any]: ...
```

---

## 11. Automated Testing Strategy (`tests/test_brain_manager.py`)

The test suite must verify all paths with 100% reliability and zero external dependencies:

| Test Case | Description | Verification Logic |
|-----------|-------------|--------------------|
| `test_models_dir_creation` | Directory auto-creation | Asserts `models/` directory is created if missing |
| `test_scan_models_empty` | Empty directory behavior | Asserts empty model list and `NO_MODEL_PRESENT` state |
| `test_gguf_header_validation` | Binary GGUF header check | Asserts valid magic bytes `b"GGUF"` succeed; corrupted bytes fail |
| `test_scan_models_populated` | Valid GGUF discovery | Creates mock GGUF file with valid header; asserts discovery |
| `test_browser_only_mode_toggle` | Zero-VRAM mode toggle | Toggling ON sets state `READY_BROWSER_OFFLOAD`; toggling OFF restores |
| `test_download_streaming_and_callbacks` | Mock download streaming | Simulates chunk streaming; verifies progress callback updates |
| `test_download_cancellation` | Download abort token | Sets `cancel_event`; verifies stream terminates and cleans up `.tmp` |
| `test_inference_dispatch_mock` | Dispatch routing | Verifies `generate_thought` and `generate_action` return valid data |
| `test_action_json_resilience` | Resilient JSON parsing | Tests malformed LLM outputs (markdown backticks, extra text) parse correctly |
| `test_vram_budget_evaluation` | GPU budget checks | Tests layer reduction when simulated free VRAM is low |

---

## 12. Verification & Command Validation

To verify the Local Brain Manager implementation:
```powershell
# Run the dedicated Brain Manager test suite
uv run pytest tests/test_brain_manager.py -v

# Run the full test suite with coverage
uv run pytest tests/ -v
```
