# Project: ParasiteAI

## 1. Executive Identity & Core Philosophy
**ParasiteAI** is a **100% visible, desktop-native local AI assistant** operating directly on the physical **Windows 10** desktop with zero headless browsers, zero invisible scrapers, and zero required paid API keys.

### Core Architectural Invariants & Ratified Decisions (D1–D6)
1. **Physical Safety & Sub-2ms Human Preemption**:
   - Win32 low-level hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) inspect `LLMHF_INJECTED` and `LLKHF_INJECTED` flags and trigger an atomic cancellation token halting synthetic mouse/keyboard actions in **< 2ms** when physical human input occurs.
   - Human override pause duration is locked at **2.5s** (`override_pause_duration_sec: 2.5`).
   - **Instant Hard Kill (`Ctrl+Alt+K`)** terminates the process tree in **< 5ms** (`taskkill /F /T /PID` + `os._exit(1)`).
2. **D1 — 6.5 GB VRAM Ceiling & Windows 10 WDDM Awareness**:
   - Maximum local model VRAM budget is **6,500 MB (6.5 GB)** (`vram_budget_mb: 6500`) on the host **NVIDIA GeForce RTX 4060 (8,188 MiB total VRAM)**.
   - Because Windows 10 desktop compositing (`dwm.exe`) and standard desktop apps consume ~1,600–2,400 MiB VRAM (~5,700–6,300 MiB free), active model + KV cache + multimodal projector (`mmproj`) footprint must stay within **~4.8–5.4 GB** to prevent Windows WDDM Shared System Memory (PCIe) spillover.
   - Enforced via `scripts/check_gpu_governance.py`.
3. **D2 — 100% Visible Physical Actuation**:
   - All mouse movements use visible human-like Cubic Bézier trajectories, Flash & Hogan Min-Jerk velocity profiles, and a `GhostHUD` pre-click reticle.
   - All text entry uses visible desktop focus + fast clipboard paste (`Ctrl+V` with atomic clipboard backup/restore) or cadence-jittered physical typing.
   - Under the hood, structured UIA + VLM coordinate grounding and deterministic window/app launch helpers are permitted provided cursor/keyboard actuation remains visible and preemptible.
4. **D3 — Browser-First & Zero Required Paid API Keys**:
   - ParasiteAI operates out-of-the-box with **zero paid API keys**.
   - Local computer-use VLM inference (`TIER_1_LOCAL`) is the primary brain; when strategic escalation is needed, the primary consultation path drives the user's real visible web browser (`BrowserOffloader`), with an *opt-in* API planner tier (`T2_API_OPTIN`) only for users who explicitly configure an API key.
5. **D4 — Strict Anti-Hardcoding in Core Code (`parasite_ai/`), Learned App Data Allowed (`data/`)**:
   - Core Python modules (`parasite_ai/`) must contain **zero application-specific branching** (e.g., no hardcoded game or app names in prompts, resolvers, or grounders).
   - Window rules and process categories live in `config.yaml` (`WindowRulesConfig`), and learned per-application knowledge, UI schemas, and routines are stored in external data files (`data/`).
6. **D5 — Phase 5 Freeze Until Alpha Gate Passes**:
   - Phase 5 (Self-Learning Routine Cache / SimuLang compilation) is frozen until the core Perception-to-Action loop passes the **Alpha Gate** on the 20-task Windows 10 benchmark suite:
     - **L1 Pass Rate**: `>= 70%` (7/10 tasks)
     - **L2 Pass Rate**: `>= 40%` (3/7 tasks)
     - **False-DONE Rate**: `<= 5%` (`<= 1/20` tasks)
     - **Median Step Latency**: `<= 5.0s`
7. **D6 — Strict Stint Cadence & Result-Oriented Verification (`.agents/rules/strict_stint_cadence.md`)**:
   - Every stint requires an approved implementation plan before code execution, a post-stint walkthrough verification gate, and objective OS outcome tests (processes, windows, files, exit codes) rather than mocked internal plumbing.

---

## 2. Strategic Pivot Roadmap (Stages P0 – P4)

| Stage | Name | Core Deliverables | Gate / Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **Measure, De-Hardcode & Baseline Benchmark** ([`p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md)) | Purge app-specific literals (`P0.1`), 6.5 GB VRAM ceiling & `check_gpu_governance.py` (`P0.2`), `EpisodeReceipt` & deterministic exit codes (`P0.3`), 20-task Windows 10 ground-truth verifiers (`P0.4`), hands-off runner & `baseline_p0` scorecard (`P0.5`). | Establish honest empirical baseline (`5.0%` pass, `20.0%` False-DONE). | **DONE** |
| **P1** | **Local CUA Engine Upgrade (`llama-server` + `UI-TARS-1.5-7B`)** ([`p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md)) | Persistent out-of-process `llama-server` supervisor (`P1.1`), `UI-TARS-1.5-7B` `IQ4_XS` + `mmproj` & `uitars_parser.py` (`P1.2`), single-pass CUA execution & `CompanionDock` self-exclusion (`P1.3`), `baseline_p1` benchmark & post-mortem (`P1.4`). | `0` cold-start timeouts (`was 5`), `0` enum crashes (`was 2`), median step `4.741s` (`<= 5.0s`), False-DONE `5.0%` (`was 20.0%`). | **DONE** |
| **P2** | **Thin Perception-to-Action Loop, Resilient Parser & Pre-`DONE` Verification** ([`p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md)) | Fix `max_tokens=256` + stop sequences, resilient regex action extraction & Windows 10 prompt alignment (`P2.1`); strip `dual_mind.py` heuristics & relax caret guard (`P2.2`); objective pre-`DONE` goal verifier & ROI diff history (`P2.3`); Alpha Gate run (`P2.4`). | Pass **Alpha Gate**: `L1 >= 70%`, `L2 >= 40%`, `False-DONE <= 5%`, `Median step <= 5.0s`. | **NEXT (PLANNING)** |
| **P3** | **Free Visible Browser Consultation & Opt-In API Tier** | Clean 3-tier escalation (`T0` deterministic/UIA -> `T1` local 7B CUA -> `T2` visible browser AI consultation / opt-in API planner). | Lift L2 (`>= 60%`) and L3 (`>= 33%`) multi-app & recovery tasks. | PLANNED |
| **P4** | **Unfreeze Phase 5 (Learned App Memory) & Packaging** | Re-enable verified episode trace compilation into `data/` app notes/routines; standalone Windows 10 packaging & crash recovery. | Zero regression on L1/L2 + measurable speedup on repeated workflows. | PLANNED |

---

## 3. System Subsystems & Interface Contracts

### 1. Foundation, Governance & Config (`parasite_ai/config.py`, `config.yaml`, `scripts/check_gpu_governance.py`)
- Environment managed via `uv` on Python 3.12 (`C:\ParasiteAI\.venv`).
- `ParasiteConfig` validates `SafetyConfig` (`override_pause_duration_sec: 2.5`), `BrainConfig` (`vram_budget_mb: 6500`), and `WindowRulesConfig`.
- `scripts/check_gpu_governance.py` inspects live `nvidia-smi` telemetry (`total_mb`, `used_mb`, `free_mb`, WDDM spillover risk) and enforces the 6,500 MB ceiling.

### 2. Safety & Physical Input Layer (`parasite_ai/safety/`, `parasite_ai/hands/`)
- `InterruptGuard`:
  - `start() / stop()`: Manages Win32 `WH_MOUSE_LL` and `WH_KEYBOARD_LL` hooks.
  - `get_cancellation_token() -> threading.Event`: Set in `< 2ms` on physical touch.
  - `interrupt_count -> int` & `reset_interrupt_counters() -> None`: Tracks physical human interventions per episode for `EpisodeReceipt`.
- `WindowGuard`:
  - `is_safe_to_operate() -> bool`: Blocks operation on sensitive windows (password managers, elevated admin prompts).
  - `get_active_window_info() -> WindowInfo`: Returns foreground window `title`, `process_name`, `hwnd`, and `rect`.
- `MouseDriver` & `KeyboardDriver`:
  - Visible Cubic Bézier trajectories (`move_to`, `click`, `double_click`, `right_click`) and fast clipboard paste / Unicode typing (`type_text`, `hotkey`).

### 3. Visible UI Layer (`parasite_ai/ui/`)
- `CompanionDock(QWidget)`: Always-on-top frameless widget showing persona state (`WATCHING`, `THINKING`, `DRIVING`, `OFFLOADING`, `USER OVERRIDE`), speech/thought bubbles, and pause/panic controls.
- `GhostHUD(QWidget)`: Click-through transparent Win32 layered overlay (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST`) rendering Set-of-Mark bounding boxes and pre-click reticles.

### 4. Perception, Cognition & Telemetry (`parasite_ai/vision/`, `parasite_ai/mind/`, `parasite_ai/runtime.py`)
- `ScreenCapture`:
  - Multi-monitor virtual desktop (`3840x1080 @ 100% DPI`) screen capture via `mss` / `PIL` with `last_capture_backend_used` (`"mss"`, `"pillow"`, `"synthetic"`) telemetry.
- `ScreenGrounder`:
  - Tier 1 Win32 UI Automation tree walk (`2,000`-node ceiling, `os.getpid()` + `CompanionDock` / `GhostHUD` self-exclusion) + Tier 2 Scoped RapidOCR (CPU ONNX) + Tier 3 spatial deduplication.
- `LocalBrainManager` & `LlamaServerBackend`:
  - Manages persistent CUDA `llama-server.exe` hosting `UI-TARS-1.5-7B.IQ4_XS.gguf` + `mmproj-Q8_0.gguf` (`-np 1 -c 4096 --image-min-tokens 1024`) and single-pass `generate_cua_step()` parsed via `uitars_parser.py`.
- `EpisodeReceipt` (`parasite_ai/mind/memory.py`) & `RuntimeOrchestrator` (`parasite_ai/runtime.py`):
  - Every CLI `--goal` execution writes an atomic JSON `EpisodeReceipt` (`--episode-report <path>`) recording `goal`, `success`, `claimed_done`, `exit_reason`, `step_latencies_sec`, `hardware_interrupt_count`, `final_active_window`, and per-step `StepRecordSummary` entries.
  - Deterministic process exit codes in `main.py`: `0` (`DONE`), `1` (`MAX_STEPS` / `LOOP_STAGNATION` / `ERROR`), `2` (`PANIC`).

### 5. Objective OS Benchmark & 4-Tier Test Harness (`benchmarks/`, `tests/`, `scripts/test.py`)
- `benchmarks/suite.yaml`: 20 core Windows 10 tasks (`L1-01`..`L1-10`, `L2-01`..`L2-07`, `L3-01`..`L3-03`) + 3 stretch tasks (`S-01`..`S-03`).
- `benchmarks/verifiers.py`: `SETUP_REGISTRY` (7 pre-task setup hooks) and `VERIFIER_REGISTRY` (12 objective OS ground-truth verifiers inspecting live Win32 processes, `WM_GETTEXT` classic Notepad edit buffers, `IsIconic` window state, filesystem state, and clipboard contents).
- `benchmarks/run_benchmark.py`, `run_baseline_p0.bat`, `run_benchmark_p1.bat`, and `scripts/compare_benchmarks.py`.
- `scripts/test.py`: 4-tier test runner (`unit`: 478 tests, `integration`: 287 tests, `live_os`: 1 harness, `archive`: 31 legacy suites).

---

## 4. Repository Layout
```text
C:\ParasiteAI\
├── .agents/
│   └── rules/
│       └── strict_stint_cadence.md   # Workspace rule: 1 stint per turn, plan/walkthrough gates
├── benchmarks/
│   ├── suite.yaml                    # 20-task Windows 10 benchmark definition (v1.1)
│   ├── verifiers.py                  # Objective OS setup hooks & ground-truth verifiers
│   ├── run_benchmark.py              # Benchmark runner with pre-flight guard & checkpointing
│   ├── workspace/                    # Ephemeral file/folder scratchpad for benchmark tasks
│   └── results/
│       ├── baseline_p0.json / .md    # Stage P0 empirical baseline scorecard
│       ├── baseline_p1.json / .md    # Stage P1 empirical candidate scorecard
│       ├── baseline_p0_vs_baseline_p1.md # Side-by-side P0 vs P1 delta report
│       └── L*_receipt.json           # Per-task EpisodeReceipt artifacts
├── parasite_ai/
│   ├── config.py                     # Pydantic config schema (6500 MB VRAM, 2.5s cooldown)
│   ├── runtime.py                    # RuntimeOrchestrator & EpisodeReceipt emission
│   ├── safety/                       # InterruptGuard (<2ms hook), WindowGuard, PanicHandler
│   ├── hands/                        # Kinematics, MouseDriver, KeyboardDriver
│   ├── ui/                           # CompanionDock, GhostHUD, UIBridge, Win32 styles
│   ├── vision/                       # ScreenCapture, ScreenGrounder, Foveated, VLMGrounder
│   └── mind/                         # BrainManager, UITarsParser, DualMind, Memory, Plan, Resolver
├── scripts/
│   ├── test.py                       # 4-tier test suite runner (unit, integration, live_os, archive)
│   ├── serve_llama.py                # Persistent CUDA llama-server supervisor CLI
│   ├── check_gpu_governance.py       # RTX 4060 VRAM budget & WDDM spillover check
│   └── compare_benchmarks.py         # Side-by-side benchmark scorecard generator
├── tests/
│   ├── unit/                         # Tier 1: Fast isolated unit tests (478 tests)
│   ├── integration/                  # Tier 2: Subsystem & pipeline integration tests (287 tests)
│   ├── archive/                      # Tier 3: Historical milestone stress/challenger tests
│   └── live_os/                      # Tier 4: Physical desktop OS tests (@pytest.mark.live_os)
├── config.yaml                       # Active runtime configuration
├── main.py                           # CLI & GUI bootstrapper with deterministic exit codes
├── launch_parasite.bat               # Interactive desktop launcher
├── run_baseline_p0.bat               # Stage P0 benchmark launcher
├── run_benchmark_p1.bat              # Stage P1 benchmark launcher (warms llama-server + compares)
├── feasibility_review.md             # Master Architectural Feasibility & Ground-Truth Review
├── p0_stint_map.md                   # Stage P0 Stint Map (Complete)
├── p1_stint_map.md                   # Stage P1 10-Dimension Stint Map (Complete)
├── stage_p1_postmortem.md            # Standalone Stage P1 Post-Mortem & Root-Cause Audit
├── p2_stint_map.md                   # Stage P2 10-Dimension Stint Map (Active Roadmap)
├── PROJECT.md                        # Canonical architecture & roadmap reference
├── GATE_STATUS.md                    # Milestone & Pivot Stage gate audit records
└── HANDOFF.md                        # Master session handoff & Stage P2 bootstrap guide
```
