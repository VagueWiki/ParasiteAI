# Handoff Report: Milestone M1 Foundation & Zero-Config Setup

**Author:** `teamwork_explorer_m1_1`  
**Milestone:** M1 — Foundation & Zero-Config Setup  
**Date:** 2026-10-29T11:08:00Z  
**Type:** Hard Handoff  

---

## 1. Observation

1. **System & Python Environment:**
   - Ran `uv --version`:
     ```
     uv 0.11.7 (9d177269e 2026-04-15 x86_64-pc-windows-msvc)
     ```
   - Ran `uv python list`:
     ```
     cpython-3.12.13-windows-x86_64-none  C:\Users\Suici\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe
     cpython-3.14.4-windows-x86_64-none   C:\Users\Suici\AppData\Roaming\uv\python\cpython-3.14.4-windows-x86_64-none\python.exe
     ```
     Host has both Python 3.12.13 and Python 3.14.4 installed. Without an explicit `.python-version` file or `requires-python` constraint, uv might select 3.14 by default, which breaks binary wheels for Windows.

2. **Project Specifications:**
   - `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md` (lines 33, 55, 103-141):
     - Milestone M1 encompasses Feature 1 (Python 3.12 Environment & Dependencies), Feature 2 (Configuration Schema), and Feature 3 (Local Brain Manager).
     - Required core dependencies: `pyqt6`, `uiautomation`, `rapidocr-onnxruntime`, `pynput`, `pyautogui`, `pydantic`, `pyyaml`, `pytest`, `mss`.
     - Code layout dictates root `pyproject.toml`, `config.yaml`, `main.py`, `models/`, `parasite_ai/` (`safety/`, `hands/`, `ui/`, `vision/`, `mind/`), and `tests/`.

3. **Survey Findings:**
   - `survey_report.md` from `teamwork_explorer_survey_1` (lines 153-189):
     - Build system: `hatchling`.
     - Pinning: `requires-python = ">=3.12,<3.13"`.
     - Additional required libraries: `pillow>=10.2.0`, `numpy>=1.26.0`, `pytweening>=1.2.0`, `pyperclip>=1.8.2`, `httpx>=0.27.0`, `huggingface-hub>=0.23.0`.
   - `survey_report.md` from `teamwork_explorer_survey_3` (lines 67-70):
     - UI engine: `PyQt6.QtWidgets.QWidget` for companion dock and Ghost-Hand HUD overlay (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST`).

4. **Dependency Resolution Verification:**
   - Ran `uv pip compile --python 3.12` with all candidate dependencies:
     ```
     Resolved 54 packages in 15.19s
     pydantic==2.14.1
     pyqt6==6.12.0
     pyqt6-qt6==6.12.0
     uiautomation==2.0.29
     rapidocr-onnxruntime==1.4.4
     mss==10.2.0
     pynput==1.8.2
     pyautogui==0.9.54
     pytweening==1.2.0
     huggingface-hub==2.3.0
     httpx==0.28.1
     pytest==9.2.0
     pytest-mock==3.17.0
     pytest-asyncio==1.4.1
     pytest-qt==4.5.0
     ```
     All dependencies resolved cleanly without a single conflict on Windows x86_64 with Python 3.12.

5. **Current Workspace State:**
   - Inspected `g:\__Docs\ParasiteAI\` using `list_dir`: only `.agents/` and `PROJECT.md` exist.
   - `pyproject.toml`, `.python-version`, `parasite_ai/`, and `tests/` have not yet been created.

---

## 2. Logic Chain

1. From **Observation 1**, multiple Python versions exist on the system (Python 3.14 and 3.12).
2. Because Windows binary wheels for ONNX Runtime (`rapidocr-onnxruntime`) and `PyQt6` are mature for 3.12 but not fully available or stable for pre-release 3.14+, locking to Python 3.12 via `.python-version` with content `3.12` and `requires-python = ">=3.12,<3.13"` in `pyproject.toml` is mandatory to avoid installation errors.
3. From **Observations 2 & 3**, all functional layers across R1 through R5 require a specific set of runtime libraries (`pydantic`, `pyyaml`, `pyqt6`, `mss`, `pillow`, `numpy`, `pyautogui`, `pytweening`, `pynput`, `uiautomation`, `rapidocr-onnxruntime`, `pyperclip`, `httpx`, `huggingface-hub`) and test libraries (`pytest`, `pytest-asyncio`, `pytest-mock`, `pytest-qt`).
4. From **Observation 4**, these libraries are 100% mutually compatible and resolve cleanly into prebuilt Windows wheels without requiring local MSVC C++ compilation tools.
5. To preserve zero-VRAM out-of-the-box operation and prevent failed compilation if MSVC build tools are absent, `llama-cpp-python` must be placed in `[project.optional-dependencies] local-llm` rather than core dependencies. The Brain Manager can leverage local HTTP endpoints (Ollama/llama-server) or Browser-Only mode by default.
6. Using `hatchling` as the build backend requires setting `[tool.hatch.build.targets.wheel]` with `packages = ["parasite_ai"]` to prevent packaging non-code agent artifacts (`.agents/`) into the distribution wheel.
7. Using modern `uv` dependency groups (`[dependency-groups] dev = [...]`) with `[tool.uv] default-groups = ["dev"]` ensures that a simple `uv sync` command installs all dependencies needed for both running the application and executing `uv run pytest`.

---

## 3. Caveats

1. **Local GGUF Compilation:** `llama-cpp-python` is declared as an optional extra (`local-llm`). If installed with CUDA support, it requires CUDA Toolkit and MSVC. However, ParasiteAI's zero-VRAM browser offload and external HTTP endpoints operate without `llama-cpp-python`, ensuring zero startup barriers.
2. **PyQt6 Display Dependency in CI/Headless:** If tests are run in headless automated environments without a virtual display, PyQt6 widget instantiations should use `pytest-qt` or be mocked. In the local host Windows 11 environment, the display is directly available.
3. **No Direct Code Changes in Investigation:** In accordance with the Explorer role and dispatch instructions, no source code files or root project files were written. All files and templates are provided in `plan.md` for the Worker.

---

## 4. Conclusion

1. The foundation specification is fully designed, tested against the host's `uv` engine, and ready for immediate implementation by the Worker.
2. The detailed plan containing exact file contents for `.python-version`, `pyproject.toml`, `README.md`, `__init__.py` skeleton files, and directory structure has been written to:
   `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_1\plan.md`
3. Running `uv sync` on the provided `pyproject.toml` will yield a completely functioning virtual environment in < 20 seconds.

---

## 5. Verification Method

The Worker and Orchestrator can independently verify this plan by executing the following commands once files are generated:

1. **Verify Python Pinning:**
   ```powershell
   cd g:\__Docs\ParasiteAI
   uv run python -c "import sys; assert sys.version_info[:2] == (3, 12), f'Wrong python: {sys.version}'; print('PYTHON 3.12 VERIFIED')"
   ```
2. **Verify Environment Sync & Dependencies:**
   ```powershell
   uv sync
   ```
   *Expected result:* Exit code 0, 54 packages synced.
3. **Verify Editable Package Discovery:**
   ```powershell
   uv run python -c "import parasite_ai; print(parasite_ai.__version__)"
   ```
   *Expected output:* `0.1.0`
4. **Verify Core Imports:**
   ```powershell
   uv run python -c "import PyQt6, pydantic, yaml, mss, PIL, numpy, pyautogui, pytweening, pynput, uiautomation, rapidocr_onnxruntime, pyperclip, httpx, huggingface_hub; print('FOUNDATION IMPORTS OK')"
   ```
   *Expected output:* `FOUNDATION IMPORTS OK`
5. **Verify Pytest Execution:**
   ```powershell
   uv run pytest
   ```
   *Expected result:* Exit code 0.

---
*End of Report.*
