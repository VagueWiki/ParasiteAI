# Handoff Report: Local Brain Manager Architecture (M1)

**Agent:** `teamwork_explorer_m1_3`  
**Milestone:** M1 (Foundation & Zero-Config Setup)  
**Target:** Local Brain Manager (`parasite_ai/mind/brain_manager.py`)  
**Artifact:** `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_3\plan.md`  

---

## 1. Observation

1. **Original Request R1 & R4 Requirements (`ORIGINAL_REQUEST.md:14-16, 23-25`):**
   - *"R1. Foundation & Zero-Config Local Brain Setup: Set up the Python 3.12 project environment using uv with pyproject.toml, configuration in config.yaml, and a local brain manager supporting local model management and browser-offload coordination."*
   - *"R4. Perception, Cognition & Visible Browser Brain Offload: ... dual-mind cognitive pipeline (Persona voice pass + Action Dispatcher pass), and a visible browser offload state machine configured for Google Chrome to physically interact with web AI..."*

2. **Project Specification Contracts (`PROJECT.md:7-10, 35, 55, 128-133`):**
   - Feature 3: *"Local Brain Manager: Pluggable local model manager (GGUF loader/downloader, zero-VRAM browser offload coordinator) | M1 | R1, Survey 1"*
   - Code Layout establishes `parasite_ai/mind/brain_manager.py` as the dedicated module for brain management.

3. **Survey 1 Findings (`survey_report.md:26-35, 216-234, 287-320`):**
   - Host GPU profile verified: NVIDIA GeForce RTX 4060 with 8188 MiB (8 GB) VRAM, idle VRAM usage ~800 MiB, leaving ~7.3 GB usable headroom.
   - Safe VRAM budget ceiling: 5500 MiB to prevent spilling into shared system RAM.
   - Recommended quantized models: `Qwen/Qwen2.5-3B-Instruct-GGUF` (`qwen2.5-3b-instruct-q4_k_m.gguf`, ~2.17 GB) and `Qwen/Qwen2.5-7B-Instruct-GGUF` (`qwen2.5-7b-instruct-q4_k_m.gguf`, ~4.68 GB).
   - Core interface contract: `get_status()`, `start_download()`, `load_model()`, `unload_model()`, `generate_thought()`, `generate_action()`, `toggle_browser_only_mode()`.

4. **Adversarial Traps & Dual-Mind Split (`implementation_plan.md:34-46, 113-116`):**
   - Trap 2: Running Windows 11 + Chrome + 7B LLM simultaneously exceeds 8GB VRAM if unmonitored, dropping token rate from 45 tok/s to 2 tok/s.
   - Trap 3: Mixing character persona voice and strict JSON action formatting in a single prompt causes KV-cache thrashing and degrades persona authenticity.

---

## 2. Logic Chain

1. **From Zero-Config Mandate to Zero-VRAM Default:**
   - Mandating a 2GB–5GB local GGUF download before ParasiteAI can boot violates zero-friction desktop usability (Observation 1, 3).
   - Therefore, `LocalBrainManager` must support an automatic fallback: when `models/` contains no valid `.gguf` file, the state machine defaults to `BrainState.READY_BROWSER_OFFLOAD` and routes cognitive tasks to the visible browser offloader.

2. **From GGUF Integrity to Binary Header Validation:**
   - Aborted or partially downloaded files can corrupt runtime initialization. Relying purely on file extensions (`.gguf`) causes silent crashes in `llama_cpp.Llama` (Observation 3).
   - Therefore, `scan_models()` must inspect the binary header for magic bytes `b"GGUF"` (ASCII `0x47 0x47 0x55 0x46`) and uint32 version (2 or 3) before declaring a model valid.

3. **From UI Responsiveness to Non-Blocking Streaming Hooks:**
   - Downloading large files on the main application thread will freeze the Tkinter/PyQt6 GUI and violate the 60 FPS target (Observation 2, 3).
   - Therefore, downloads must execute on a daemon worker thread with a thread-safe `threading.Event()` cancellation token and emit throttled `DownloadProgress` events to UI hooks.

4. **From Dual-Mind Separation to Unified Dispatch Interface:**
   - Pass 1 requires unconstrained creative character prose; Pass 2 requires strict JSON action commands (Observation 4).
   - Furthermore, the cognitive engine must execute identically whether running against in-process GGUF (`LlamaCppBackend`), local server (`OpenAIEndpointBackend`), web AI (`BrowserOffloadBackend`), or unit test mocks (`MockBackend`).
   - Therefore, `LocalBrainManager` must implement a unified dispatch interface exposing `generate_thought()` and `generate_action()` backed by polymorphic `InferenceBackend` implementations.

5. **From 8GB VRAM Constraint to Dynamic Budget Guard:**
   - The RTX 4060 has 8188 MiB VRAM with ~2.5 GB reserved for DWM and browsers (Observation 3, 4).
   - Therefore, `LocalBrainManager` must verify available VRAM before loading weights and support auto-splitting layers between GPU and CPU (`n_gpu_layers`) to ensure memory never spills into shared system RAM.

---

## 3. Caveats

1. **Optional `llama-cpp-python` Compilation:** On Windows, compiling `llama-cpp-python` with CUDA support requires MSVC and CUDA Toolkit. If the user does not have prebuilt wheels installed, `LocalBrainManager` handles this gracefully by detecting the absence of `llama_cpp` and falling back to `OpenAIEndpointBackend` or `BrowserOffloadBackend`.
2. **Web AI UI Variation:** When in Browser Offload mode, changes to web AI DOM layouts (e.g. Gemini or ChatGPT redesigns) are handled by the browser offloader state machine (`parasite_ai/mind/offloader.py`) and Sentinel Clipboard Verification, which is decoupled from the Brain Manager dispatch interface.
3. **Download Bandwidth Variations:** Download speeds depend on HuggingFace Hub network conditions. Resumable downloading via `.tmp` files ensures partial downloads can be safely resumed or restarted.

---

## 4. Conclusion

The architecture for `LocalBrainManager` (`parasite_ai/mind/brain_manager.py`) is fully designed, documented, and specified in `plan.md`. It provides:
- Clean directory management in `models/` with binary GGUF header validation.
- Zero-VRAM Browser Offload mode enabling immediate out-of-the-box desktop assistant operation.
- Non-blocking streaming downloads with granular UI progress reporting and cancellation.
- Polymorphic inference dispatch routing across local GGUF, local servers, browser offload, and test mocks.
- Dual-mind cognitive integration cleanly separating Pass 1 (Persona monologue) from Pass 2 (Action Dispatcher JSON commands).
- Full automated test blueprint for `tests/test_brain_manager.py`.

The Worker can proceed directly with implementing `parasite_ai/mind/brain_manager.py` and `tests/test_brain_manager.py`.

---

## 5. Verification Method

To independently verify the architecture and its implementation:

1. **File Inspection:**
   - Inspect architectural specification: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_3\plan.md`
   - Review class definitions, state machine enums, and data models in Section 3 and Section 10 of `plan.md`.

2. **Automated Unit Test Verification:**
   Once implemented by the Worker, run:
   ```powershell
   uv run pytest tests/test_brain_manager.py -v
   ```
   Expected: All unit tests pass, verifying models directory creation, GGUF magic header validation, streaming download callback hooks, zero-VRAM browser offload toggle, and unified inference dispatch.

3. **Invalidation Conditions:**
   - If the implementation requires mandatory multi-gigabyte GGUF model downloads to launch without fallback.
   - If model downloads run on the main UI thread, causing GUI unresponsiveness.
   - If partial or corrupted GGUF files without valid `b"GGUF"` magic bytes are loaded without error trapping.
