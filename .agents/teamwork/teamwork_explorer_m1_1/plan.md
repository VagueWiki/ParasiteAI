# Milestone M1: Foundation & Zero-Config Setup — Implementation Plan

**Target Agent:** Worker / Sub-orchestrator  
**Prepared by:** `teamwork_explorer_m1_1`  
**Milestone:** M1 — Foundation & Zero-Config Setup  
**Scope:** `pyproject.toml`, `.python-version`, Hatchling build system, uv configuration, and `parasite_ai` package directory layout.

---

## 1. Executive Summary & Objective

The objective of Milestone M1 is to establish a deterministic, zero-config Python 3.12 environment managed via `uv` using modern PEP 621/PEP 735 standards, a Hatchling build backend, and a clean, modular directory structure for `parasite_ai`.

This plan specifies:
1. Exact contents of `.python-version` ensuring uv picks Python 3.12 on hosts with multiple Python versions installed.
2. Complete, drop-in `pyproject.toml` containing all core runtime dependencies, development dependencies, build system configuration, and pytest settings.
3. Exact package directory hierarchy with `__init__.py` skeletons.
4. Step-by-step implementation instructions and concrete verification commands for the Worker.

---

## 2. Environment & Version Specifications

- **Python Version:** Pinned strictly to `3.12` (`>=3.12,<3.13`).
  - System verification confirmed `cpython-3.12.13-windows-x86_64-none` is already installed in `C:\Users\Suici\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`.
  - `.python-version` must contain `3.12`.
- **Package Manager:** `uv 0.11.7` (MSVC x86_64).
- **Build Backend:** `hatchling` (`hatchling.build`).

---

## 3. Complete `pyproject.toml` Specification

The Worker must create `g:\__Docs\ParasiteAI\pyproject.toml` with the exact contents below:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "parasite-ai"
version = "0.1.0"
description = "100% visible, desktop-native local AI assistant operating on the physical Windows desktop"
readme = "README.md"
requires-python = ">=3.12,<3.13"
license = { text = "MIT" }
authors = [
    { name = "ParasiteAI Team" }
]
keywords = [
    "ai-assistant",
    "desktop-automation",
    "computer-vision",
    "kinematics",
    "win32",
    "local-ai"
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Win32 (MS Windows)",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows :: Windows 11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Desktop Environment",
]
dependencies = [
    # Core schema & configuration
    "pydantic>=2.6.0,<3.0.0",
    "pyyaml>=6.0.1",
    
    # Desktop GUI & Overlay
    "pyqt6>=6.6.0",
    
    # Perception & Screen capture
    "mss>=9.0.1",
    "pillow>=10.2.0",
    "numpy>=1.26.0",
    
    # Win32 Grounding & OCR
    "uiautomation>=2.0.19",
    "rapidocr-onnxruntime>=1.3.8",
    
    # Physical input & Kinematics
    "pyautogui>=0.9.54",
    "pytweening>=1.2.0",
    "pynput>=1.7.6",
    
    # Clipboard & Offloader
    "pyperclip>=1.8.2",
    "httpx>=0.27.0",
    "huggingface-hub>=0.23.0",
]

[project.optional-dependencies]
# Optional local GGUF engine (if CUDA compilation available)
local-llm = [
    "llama-cpp-python>=0.2.80",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "pytest-qt>=4.4.0",
]

[project.scripts]
parasite = "parasite_ai.main:main"

[tool.hatch.build.targets.wheel]
packages = ["parasite_ai"]

[tool.uv]
default-groups = ["dev"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers"
asyncio_mode = "auto"
```

### Dependency Validation Record
All 54 transitive dependencies were resolved and compiled with zero conflicts via `uv pip compile --python 3.12`:
- `pydantic` -> `2.14.1`
- `pyqt6` -> `6.12.0` (with `pyqt6-qt6` 6.12.0)
- `uiautomation` -> `2.0.29`
- `rapidocr-onnxruntime` -> `1.4.4` (with `onnxruntime` 1.31.1, `opencv-python` 5.0.0.93)
- `mss` -> `10.2.0`
- `pynput` -> `1.8.2`
- `pyautogui` -> `0.9.54`
- `huggingface-hub` -> `2.3.0`
- `httpx` -> `0.28.1`
- `pytest` -> `9.2.0`, `pytest-mock` -> `3.17.0`, `pytest-asyncio` -> `1.4.1`, `pytest-qt` -> `4.5.0`

---

## 4. Package Directory Layout & File Manifest

The Worker must create the following directory structure under `g:\__Docs\ParasiteAI\`:

```
g:\__Docs\ParasiteAI\
├── .python-version
├── pyproject.toml
├── README.md
├── models\                                # Directory for local GGUF models
├── parasite_ai\
│   ├── __init__.py                        # Version & package exports
│   ├── config.py                          # Implemented per teamwork_explorer_m1_2
│   ├── core.py                            # Application coordinator placeholder
│   ├── safety\
│   │   └── __init__.py
│   ├── hands\
│   │   └── __init__.py
│   ├── ui\
│   │   └── __init__.py
│   ├── vision\
│   │   └── __init__.py
│   └── mind\
│       ├── __init__.py
│       └── brain_manager.py               # Implemented per teamwork_explorer_m1_3
└── tests\
    ├── __init__.py
    ├── conftest.py                        # Common test fixtures (QApplication, dummy configs)
    ├── test_config.py                     # Assigned in M1
    └── test_brain_manager.py              # Assigned in M1
```

### File Template: `.python-version`
```
3.12
```

### File Template: `README.md`
```markdown
# ParasiteAI

A 100% visible, desktop-native local AI assistant operating on the user's physical Windows desktop with zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces.

## Quickstart

```bash
# Sync environment and dependencies
uv sync

# Run tests
uv run pytest

# Launch companion
uv run python main.py
```
```

### File Template: `parasite_ai/__init__.py`
```python
"""ParasiteAI: 100% visible, desktop-native local AI assistant."""

__version__ = "0.1.0"
__author__ = "ParasiteAI Team"

__all__ = ["__version__"]
```

### File Template: `parasite_ai/safety/__init__.py`, `hands/__init__.py`, `ui/__init__.py`, `vision/__init__.py`, `mind/__init__.py`
```python
"""Subsystem package initialization."""
```

### File Template: `tests/__init__.py`
```python
"""ParasiteAI test suite."""
```

### File Template: `tests/conftest.py`
```python
"""Global pytest fixtures for ParasiteAI."""
import os
import sys
import pytest

# Ensure parasite_ai root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

---

## 5. Worker Execution Instructions (Step-by-Step)

The Worker should execute the following steps in sequence:

1. **Write `.python-version`** with `3.12`.
2. **Write `pyproject.toml`** with the full specification in Section 3.
3. **Write `README.md`** placeholder with quickstart.
4. **Create package directories**:
   - `models`
   - `parasite_ai`
   - `parasite_ai/safety`
   - `parasite_ai/hands`
   - `parasite_ai/ui`
   - `parasite_ai/vision`
   - `parasite_ai/mind`
   - `tests`
5. **Create `__init__.py` files**:
   - `parasite_ai/__init__.py`
   - `parasite_ai/safety/__init__.py`
   - `parasite_ai/hands/__init__.py`
   - `parasite_ai/ui/__init__.py`
   - `parasite_ai/vision/__init__.py`
   - `parasite_ai/mind/__init__.py`
   - `tests/__init__.py`
   - `tests/conftest.py`
6. **Execute `uv sync`** to create the virtual environment (`.venv`) and install all dependencies in editable mode.
7. **Run verification commands** detailed in Section 6.

---

## 6. Worker Verification Commands & Expected Outputs

The Worker must execute and verify all of the following commands:

### Command 1: Environment Synchronization
```powershell
uv sync
```
- **Expected Result:** Exit code 0. `.venv` created with Python 3.12, 54+ packages installed, `parasite-ai` installed in editable mode (`parasite-ai (0.1.0, editable)`).

### Command 2: Package Import & Version Verification
```powershell
uv run python -c "import parasite_ai; print(f'ParasiteAI version: {parasite_ai.__version__}')"
```
- **Expected Output:**
  ```
  ParasiteAI version: 0.1.0
  ```
- **Expected Exit Code:** 0

### Command 3: Core Dependencies Smoke Test
```powershell
uv run python -c "import PyQt6, pydantic, yaml, mss, PIL, numpy, pyautogui, pytweening, pynput, uiautomation, rapidocr_onnxruntime, pyperclip, httpx, huggingface_hub; print('FOUNDATION DEPS OK')"
```
- **Expected Output:**
  ```
  FOUNDATION DEPS OK
  ```
- **Expected Exit Code:** 0

### Command 4: Pytest Suite Run
```powershell
uv run pytest
```
- **Expected Result:** `pytest` runs and exits 0 (or reports passing collected tests).

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| System default Python is 3.14 on host | uv might pick 3.14 without restriction, breaking binary wheels like onnxruntime/PyQt6 | Explicit `.python-version` with `3.12` and `requires-python = ">=3.12,<3.13"` in `pyproject.toml`. |
| Hatchling wheel includes non-code directories (`.agents`, `tests`) | Bloated build, namespace leakage | Explicit `[tool.hatch.build.targets.wheel]` with `packages = ["parasite_ai"]`. |
| PyQt6 headless test execution | Tests hanging without a display server | Use `pytest-qt` and standard offscreen/mocking patterns in conftest. |
| Incompatible PyTorch / llama-cpp compile requirement | Build failure during `uv sync` | `llama-cpp-python` relegated to `[project.optional-dependencies] local-llm`. Zero-VRAM browser offload works out of the box with zero compilation. |
