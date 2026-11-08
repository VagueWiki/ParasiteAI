# ParasiteAI — Milestone & Pivot Gate Audit Status

## 1. Strategic Pivot Gate Status (Stages P0 – P4)

Following the Architectural Feasibility & Ground-Truth Audit (2026-11-06), ParasiteAI adopted a 5-stage pivot (**P0–P4**) governed by objective OS outcome verification on Windows 10 rather than mocked unit test pass counts alone.

| Stage | Scope | Status | Empirical Gate / Outcome |
| :--- | :--- | :--- | :--- |
| **Stage P0** | Measure, De-Hardcode & Baseline Benchmark (`P0.1`–`P0.5`) | **PASS (COMPLETE)** | 0 hardcoded app literals; 6,500 MB GPU governance active; 20/20 dry-verify OS verifiers green; `baseline_p0` recorded (**5.0%** pass rate, **20.0%** False-DONE). |
| **Stage P1** | Local CUA Engine Upgrade (`llama-server` + `UI-TARS-1.5-7B`) | **PASS (COMPLETE)** | 0 cold-start timeouts (was 5), 0 enum crashes, median step latency 4.741s (target <= 5.0s), False-DONE dropped to 5.0% (was 20.0%). |
| **Stage P2** | Thin Perception-to-Action Loop & Pre-`DONE` Verification | UPCOMING | **Alpha Gate Target**: `L1 >= 70%`, `L2 >= 40%`, `False-DONE <= 5%`, `Median Step <= 5.0s`. Resolves CUA token truncation, unclosed action parsing, caret focus guard, and dynamic Windows 10 OS alignment. |
| **Stage P3** | Free Visible Browser Consultation & Opt-In API Tier | PLANNED | Target: `L2 >= 60%`, `L3 >= 33%` on multi-app & dialog recovery tasks. |
| **Stage P4** | Unfreeze Phase 5 (Learned App Memory) & Packaging | PLANNED | Target: Zero L1/L2 regression + measurable speedup on cached workflows. |

---

## 2. Stage P0 Stint Audit & Empirical Baseline Scorecard (`baseline_p0`)

### 2.1 Completed Stage P0 Stints
| Stint | Deliverable | Verification Result |
| :--- | :--- | :--- |
| **P0.1** | Core De-Hardcoding (`grounding.py`, `dual_mind.py`, `brain_manager.py`, `config.py`) | **PASS** — Zero game/app-specific literals in `parasite_ai/`; window rules externalized to `WindowRulesConfig`. |
| **P0.2** | Config Invariants & GPU Governance (`scripts/check_gpu_governance.py`) | **PASS** — `vram_budget_mb: 6500`, `override_pause_duration_sec: 2.5`; live RTX 4060 telemetry verified (`8,188 MiB` total, WDDM headroom check active). |
| **P0.3** | Episode Telemetry Receipts (`EpisodeReceipt`) & Deterministic Exit Codes (`0`/`1`/`2`) | **PASS** — Atomic `--episode-report` JSON persistence and real Windows subprocess exit code tests (`9/9` passed). |
| **P0.4** | 20-Task Windows 10 Benchmark Suite (`suite.yaml` v1.1) & Ground-Truth Verifiers (`verifiers.py`) | **PASS** — Replaced all stub `return True` verifiers with 12 live OS verifiers (`WM_GETTEXT` classic Notepad buffer, `IsIconic`, filesystem, clipboard); `--dry-verify` `20/20 PASSED`. |
| **P0.5** | Hands-Off Baseline Runner (`run_benchmark.py`, `run_baseline_p0.bat`), Pre-Flight Guard & Checkpointing | **PASS** — Interactive Windows 10 baseline executed across all 20 tasks (`benchmarks/results/baseline_p0.md`). |

### 2.2 Official Stage P0 Empirical Baseline vs. Alpha Gate Targets
**Run Date:** 2026-11-07 03:07:01 | **Host:** Windows 10 / NVIDIA GeForce RTX 4060 (8,188 MiB VRAM, Driver 610.74)  
**Model Under Test:** `qwen2.5-3b-instruct-q4_k_m.gguf` (in-process `llama-cpp-python`, `--max-steps-cap 5`)

| Metric | Stage P0 Baseline (`baseline_p0`) | Alpha Gate Target (End of P2) | Gap / Diagnostic Note |
| :--- | :---: | :---: | :--- |
| **Overall Ground-Truth Pass Rate** | **5.0% (1 / 20)** | `>= 50.0%` | Only `L1-07` (*Minimize Pre-Opened Notepad*) passed. |
| **Level 1 (Basic Single-App) Pass Rate** | **10.0% (1 / 10)** | **`>= 70.0%`** | `-60.0%` gap; 4 tasks timed out on cold start, 4 hit `MAX_STEPS`, 1 crashed on `SELECT` enum. |
| **Level 2 (Multi-Step / File / Dialog) Pass Rate** | **0.0% (0 / 7)** | **`>= 40.0%`** | `-40.0%` gap; 4 of 7 tasks resulted in `FALSE_DONE` hallucinations. |
| **Level 3 (Complex Multi-App / Recovery) Pass Rate** | **0.0% (0 / 3)** | Informational | 1 crashed on `SELECT MenuItem`, 1 hit `MAX_STEPS`, 1 timed out. |
| **Agent Claimed `DONE` Rate** | **25.0% (5 / 20)** | — | 4 of the 5 `DONE` claims were false (`80%` hallucination rate when claiming `DONE`). |
| **False-`DONE` Rate** | **20.0% (4 / 20)** | **`<= 5.0%`** | `+15.0%` over ceiling; blind 3B text LLM claims `DONE` after random menu clicks. |
| **Median Step Latency** | **5.986s** (P90: **9.798s**) | **`<= 5.0s`** | `+0.986s` over target (plus `45s–90s` cold-start subprocess timeouts on 5 tasks). |
| **Hardware Interrupt Count** | **0** | `0` | Sub-2ms hook clean; zero false self-interruptions across 20 episodes. |

---

## 3. Stage P1 Stint Audit (Local CUA Engine Upgrade)

| Stint | Deliverable | Verification Result |
| :--- | :--- | :--- |
| **P1.1** | Persistent `llama-server` Supervisor, `UI-TARS-1.5-7B` Model Provisioning & GPU Memory Governance | **PASS** — Provisioned Windows CUDA 12 `llama-server` (`b12188`), implemented `LlamaServerBackend` with 0ms cold-start attach & managed daemon lifecycle, provisioned and verified `UI-TARS-1.5-7B.IQ4_XS.gguf` (4.25 GB) + `UI-TARS-1.5-7B.mmproj-Q8_0.gguf` (856 MB) with binary GGUF headers, locked single-slot KV cache (`-np 1`) and `--image-min-tokens 1024`, verified 0.590s text and 1.686s multimodal vision smoke inference, 49/49 tests passed, VRAM strictly bounded under 6,500 MB budget ceiling on RTX 4060. |
| **P1.2** | Native `UI-TARS-1.5-7B` Action Parser, Coordinate Grounding & Schema Recovery | **PASS** — Created `uitars_parser.py` parsing native `Thought:` and `Action:` computer-use calls (`click`, `left_double`, `right_single`, `type`, `hotkey`, `scroll`, `wait`, `finished`), `[0..1000]` coordinate scaling to screen pixels, hybrid UIA element snapping, hardened `ActionPlan` with verb synonym normalization (`SELECT`, `LEFT_CLICK`, `PRESS`, `FINISH`) and zero-crash fallback (`WAIT`), live multimodal grounding smoke test verified (`1.368s`), 101/101 tests passed. |
| **P1.3** | Single-Pass CUA Pipeline, Self-UI Exclusion (`CompanionDock` / `os.getpid()`) & Precision App Disambiguation | **PASS** — Integrated single-pass multimodal inference (`generate_cua_step`) extracting Thought (persona monologue) + Action in one LLM call; masked `CompanionDock` overlay bounds in OCR and excluded `os.getpid()` child controls to prevent self-clicking speech bubbles; hardened `PrecisionAppMatcher` against domain/symbol suffix collisions (`Notepad++` vs `Notepad` = `0.0`, `paint.net` vs `Paint` = `0.0`); added hard node scan ceiling (`total_nodes_scanned >= 2000`) in `ScreenGrounder` to prevent infinite generator hangs; executed 4-tier test restructuring (Tier 1 `tests/unit/`: 478/478 passed; Tier 2 `tests/integration/`: 287/287 passed; Total active suite: 765/765 passed in 74.8s). |
| **P1.4** | Stage P1 Benchmark Run (`baseline_p1`) & Comparative Scorecard (`P0` vs `P1`) | **PASS** — Executed all 20 benchmark tasks hands-off via `run_benchmark_p1.bat`. Verified: 0 cold-start timeouts (was 5), 0 subprocess exit crashes (was 2), median step latency 4.741s (P90: 5.635s, improved by 1.25s), False-DONE rate reduced from 20.0% to 5.0%. Root cause analysis identified 4 pipeline bugs (`max_tokens: 128` truncation, brittle `endswith(")")` parser fallback, Win32 caret focus guard, hardcoded Windows 11 strings) handed off to Stage P2. |

---

## 4. Historical Foundation Milestones (M1 – M5)

All 5 foundational engineering milestones (**M1–M5**) passed unit and subsystem verification prior to the Stage P0 empirical benchmark pivot:

| Milestone | Scope | Gate Iteration | Verdict | Test Count |
| --- | --- | --- | --- | --- |
| **M1** | Foundation, Pydantic Config & Local Brain Manager | Iteration 4 | **PASS** | 178 / 178 |
| **M2** | Win32 Low-Level Hooks (`<2ms` Interrupt), Window Guard & Bézier Kinematics | Iteration 1 | **PASS** | 321 / 321 |
| **M3** | Desktop Companion Dock & Click-Through Ghost-Hand HUD Overlay | Iteration 2 | **PASS** | 424 / 424 |
| **M4** | Hybrid Screen Grounding, Episodic Memory, Dual-Mind & Chrome Offloader | Iteration 1 | **PASS** | 552 / 552 |
| **M5** | Runtime Orchestrator, Entry Points (`main.py`, `launch_parasite.bat`) & E2E Hardening | Iteration 2 | **PASS** | 660 / 660 |
| **Phases 1–4** | Foveated Perception, Universal Resolver, Caret Focus, 64-bit Win32 ABI Structs | Certified | **PASS** | 2,178 / 2,178 |
