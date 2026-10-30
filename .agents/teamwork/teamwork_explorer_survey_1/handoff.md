# Handoff Report: Foundation, System Architecture & Local Brain Manager (R1)

**Agent:** `teamwork_explorer_survey_1`  
**Milestone:** Phase 0 Scope Survey & Architecture  
**Deliverable File:** `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_1\survey_report.md`  

---

## 1. Observation

1. **Host Environment & Tooling:**
   - Ran `uv --version; python --version`:
     ```
     uv 0.11.7 (9d177269e 2026-04-15 x86_64-pc-windows-msvc)
     Python 3.14.3
     ```
   - Ran `uv python list`: Shows `cpython-3.12.13-windows-x86_64-none` is directly downloadable via `uv`.
   - Ran `uv run --python 3.12 python -c "import sys; print(sys.version, sys.platform)"`: Successfully downloaded and ran `cpython-3.12.13` (`3.12.13 (main, Apr 14 2026, 14:31:26) [MSC v.1944 64 bit (AMD64)] win32`).
   - Ran `uv run --python 3.12 python -c "import tkinter; print(tkinter.TkVersion)"`: Returned `8.6` confirming native Tkinter availability in Python 3.12.
   - Ran `uv run --python 3.12 python -c "import ctypes, ctypes.wintypes; print('user32 available:', hasattr(ctypes.windll, 'user32'))"`: Returned `user32 available: True`.

2. **GPU & VRAM Headroom:**
   - Ran `nvidia-smi`: NVIDIA GeForce RTX 4060 with `8188 MiB` total VRAM, driver `610.74`, CUDA `13.3`. Active usage is `802 MiB`, leaving `7386 MiB` (~7.3 GB) free.

3. **Installed Browsers:**
   - Checked App Paths in Registry:
     - Google Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe`
     - Opera GX: `C:\Users\Suici\AppData\Local\Programs\Opera GX\opera.exe`

4. **Existing Repository State:**
   - Listed `g:\__Docs\ParasiteAI`: Currently only contains `.agents/` folder. No source code or config files exist yet.

5. **Reference Requirements & Implementation Plan:**
   - Inspected `ORIGINAL_REQUEST.md`: R1 requires Python 3.12 project environment using `uv` with `pyproject.toml`, configuration in `config.yaml`, and a local brain manager supporting local model management and browser-offload coordination.
   - Inspected `implementation_plan.md`: Details zero-config local brain setup, 8 GB VRAM budget allocation, dual-mind pipeline (Pass 1 Persona + Pass 2 Action Dispatcher), browser offload, and test specifications.

---

## 2. Logic Chain

1. **Python Runtime Pinning (Obs 1):**
   - The host system has `uv 0.11.7` capable of fetching Python 3.12.13. Python 3.12 has pre-built Windows wheels for `uiautomation`, `rapidocr-onnxruntime`, `numpy`, and `pynput`, avoiding MSVC C++ build issues. Tkinter 8.6 is bundled in this distribution, allowing zero-dependency native GUI creation and Win32 layered transparent windowing via `ctypes.windll.user32`.
   - Therefore, `pyproject.toml` should pin `requires-python = ">=3.12,<3.13"` and build with `hatchling`.

2. **VRAM Safety & Dual-Mode Local Brain (Obs 2 & 5):**
   - The RTX 4060 has 8 GB total VRAM. Running Windows DWM and browsers consumes ~2 GB.
   - A 3B quantized model (`Qwen2.5-3B-Instruct-Q4_K_M`) requires ~2.0 GB VRAM, fitting easily within headroom. A 7B model (`Qwen2.5-7B-Instruct-Q4_K_M`) requires ~4.7 GB VRAM, which fits if layers are safely bounded.
   - To guarantee zero-friction immediate startup without downloading gigabytes of weights on day one, the Local Brain Manager must feature a **Browser-Only Zero-VRAM Mode** that routes reasoning to web AI via Chrome or Opera GX.

3. **Module Layout & Directory Architecture (Obs 4 & 5):**
   - To follow the single-responsibility principle and avoid KV cache thrashing, code is partitioned into:
     - `parasite_ai/config.py`: Schema validation (`pydantic` + `pyyaml`).
     - `parasite_ai/mind/brain_manager.py`: Local GGUF management, downloader, and zero-VRAM mode.
     - `parasite_ai/mind/dual_mind.py`: Pass 1 PersonaEngine + Pass 2 ActionDispatcher.
     - `parasite_ai/mind/memory.py`: Episodic working memory.
     - `parasite_ai/mind/offloader.py`: Visible browser offloading.
     - `parasite_ai/vision/`: Screen capture (`mss`) and hybrid grounding (`uiautomation` + `rapidocr-onnxruntime`).
     - `parasite_ai/hands/`: Bezier curves (`pytweening`) and Unicode typing.
     - `parasite_ai/safety/`: Win32 low-level hooks (`LLMHF_INJECTED`) and window guard.
     - `parasite_ai/ui/`: Companion dock and Ghost-Hand transparent HUD overlay.

---

## 3. Caveats

1. `llama-cpp-python` pre-built wheels with CUDA support on Windows can sometimes require specific wheel index URLs depending on CUDA version. The Local Brain Manager is designed with a pluggable architecture so it can operate via direct GGUF inference, local HTTP server (`llama-server.exe` / Ollama), or Browser-Only Zero-VRAM mode.
2. This survey is strictly read-only; no code was authored outside `.agents/teamwork/teamwork_explorer_survey_1/`. Implementation is delegated to subsequent implementation milestones.

---

## 4. Conclusion

The architectural blueprint, directory layout, dependency manifest (`pyproject.toml`), configuration schema (`config.yaml`), and Local Brain Manager (R1) specification are fully defined, verified against host system hardware and software capabilities, and documented in detail in `survey_report.md`. The project is primed for Phase 1 implementation.

---

## 5. Verification Method

1. **Verify Report Files Exist:**
   - Inspect `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_1\survey_report.md`
   - Inspect `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_1\handoff.md`
2. **Verify Python 3.12 & Win32 Capabilities:**
   - Execute: `uv run --python 3.12 python -c "import sys, tkinter, ctypes; print(sys.version); print(tkinter.TkVersion); print(hasattr(ctypes.windll, 'user32'))"`
   - Expected: Prints Python 3.12.x, Tkinter 8.6, and True for user32.
3. **Verify Host GPU Headroom:**
   - Execute: `nvidia-smi --query-gpu=memory.total,memory.free --format=csv`
   - Expected: Confirms >= 7000 MiB free VRAM.
4. **Verify Browser Paths:**
   - Google Chrome: `Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"` -> `True`
   - Opera GX: `Test-Path "C:\Users\Suici\AppData\Local\Programs\Opera GX\opera.exe"` -> `True`
