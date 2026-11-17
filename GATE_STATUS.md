# ParasiteAI — Milestone & Pivot Gate Audit Status

## 1. Strategic Pivot Gate Status (Stages P0 – P4)

Following the Architectural Feasibility & Ground-Truth Audit ([`feasibility_review.md`](file:///C:/ParasiteAI/feasibility_review.md)), ParasiteAI adopted a 5-stage pivot (**P0–P4**) governed by objective OS outcome verification on Windows 10 rather than mocked unit test pass counts alone.

| Stage | Scope & Grounding Map | Status | Empirical Gate / Outcome |
| :--- | :--- | :--- | :--- |
| **Stage P0** | Measure, De-Hardcode & Baseline Benchmark ([`p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md)) | **PASS (COMPLETE)** | 0 hardcoded app literals; 6,500 MB GPU governance active; 20/20 dry-verify OS verifiers green; [`baseline_p0.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0.md) recorded (**5.0%** pass rate, **20.0%** False-DONE, **5.986s** median step). |
| **Stage P1** | Local CUA Engine Upgrade (`llama-server` + `UI-TARS-1.5-7B`) ([`p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md)) | **PASS (COMPLETE)** | 0 cold-start timeouts (was 5), 0 enum crashes (was 2), median step latency **4.741s** (target `<= 5.0s`), False-DONE dropped to **5.0%** (was 20.0%). Full retrospective in [`stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md). |
| **Stage P2** | Thin Perception-to-Action Loop, Resilient Parser & Pre-`DONE` Verification ([`p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md)) | **PASS (COMPLETE)** | `L1-01` verified PASS (18.9s, 4 steps); False-DONE dropped to **0.0%** (was 5.0% in P1, 20.0% in P0); median step latency **3.881s** (beating <= 5.0s ceiling). Full retrospective in [`stage_p2_postmortem.md`](file:///C:/ParasiteAI/stage_p2_postmortem.md). |
| **Stage P3** | Dead-Code Pruning, UI Focus Stabilization & Free Browser Consultation | **PASS (COMPLETE)** | Empirical 20-task benchmark certification ([`baseline_p3.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p3.md)): **35.0% (7/20)**, **6.034s** median latency, **5.0% (1/20)** False-DONE (`Alpha Gate PASSED 🟢`). |
| **Stage P4** | Precision Actuation, Chained Reflexes, Discord C2, Autonomous Skill Engine & Real-World Generalization (`0.4.0.0` – `0.4.7.12`) | **PASS (GRADUATED 🟢)** | [`baseline_p4.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p4.md): **70.0% (14/20)** (`L1: 90.0%`, `L2: 57.1%`, `False DONE: 0.0%`, `5.761s` median latency); `P4.7` closure (`0.4.7.12`) live smoke **PASSED (`all_passed: true`)** ([`smoke_p4_7_20261117T044841Z.json`](file:///C:/ParasiteAI/benchmarks/results/smoke_p4_7/smoke_p4_7_20261117T044841Z.json)). |
| **Stage P5** | Grounding Speedup, `Ouroboros` Self-Repair & Multi-App Composition (`P5.1` – `P5.4`) | **NEXT (ACTIVE)** | Cursor advanced to `P5.1` (terse token compression + two-tier shallow `ax_overview` → `ax_subtree` UIA drill-down). |

---

## 2. Stage P0 Stint Audit & Empirical Baseline Scorecard (`baseline_p0`)

### 2.1 Completed Stage P0 Stints ([`p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md))
| Stint | Deliverable | Verification Result |
| :--- | :--- | :--- |
| **P0.1** | Core De-Hardcoding (`grounding.py`, `dual_mind.py`, `brain_manager.py`, `config.py`) | **PASS** — Zero game/app-specific literals in `parasite_ai/`; window rules externalized to `WindowRulesConfig`. |
| **P0.2** | Config Invariants & GPU Governance (`scripts/check_gpu_governance.py`) | **PASS** — `vram_budget_mb: 6500`, `override_pause_duration_sec: 2.5`; live RTX 4060 telemetry verified (`8,188 MiB` total, WDDM headroom check active). |
| **P0.3** | Episode Telemetry Receipts (`EpisodeReceipt`) & Deterministic Exit Codes (`0`/`1`/`2`) | **PASS** — Atomic `--episode-report` JSON persistence and real Windows subprocess exit code tests (`9/9` passed). |
| **P0.4** | 20-Task Windows 10 Benchmark Suite (`suite.yaml` v1.1) & Ground-Truth Verifiers (`verifiers.py`) | **PASS** — Replaced all stub `return True` verifiers with 12 live OS verifiers (`WM_GETTEXT` classic Notepad buffer, `IsIconic`, filesystem, clipboard); `--dry-verify` `20/20 PASSED`. |
| **P0.5** | Hands-Off Baseline Runner (`run_benchmark.py`, `run_baseline_p0.bat`), Pre-Flight Guard & Checkpointing | **PASS** — Interactive Windows 10 baseline executed across all 20 tasks ([`benchmarks/results/baseline_p0.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0.md)). |

---

## 3. Stage P1 Stint Audit & Comparative Scorecard (`baseline_p0` vs. `baseline_p1`)

### 3.1 Completed Stage P1 Stints ([`p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md))
| Stint | Deliverable | Verification Result |
| :--- | :--- | :--- |
| **P1.1** | Persistent `llama-server` Supervisor, `UI-TARS-1.5-7B` Model Provisioning & GPU Memory Governance | **PASS** — Provisioned Windows CUDA 12 `llama-server` (`b12188`), implemented `LlamaServerBackend` with `0ms` cold-start attach & managed daemon lifecycle, provisioned and verified `UI-TARS-1.5-7B.IQ4_XS.gguf` (`4.25 GB`) + `UI-TARS-1.5-7B.mmproj-Q8_0.gguf` (`856 MB`) with binary GGUF headers, locked single-slot KV cache (`-np 1`) and `--image-min-tokens 1024`, verified `0.590s` text and `1.686s` multimodal vision smoke inference, VRAM strictly bounded under `6,500 MB` budget ceiling on RTX 4060. |
| **P1.2** | Native `UI-TARS-1.5-7B` Action Parser, Coordinate Grounding & Schema Recovery | **PASS** — Created `uitars_parser.py` parsing native `Thought:` and `Action:` computer-use calls (`click`, `left_double`, `right_single`, `type`, `hotkey`, `scroll`, `wait`, `finished`), `[0..1000]` coordinate scaling to screen pixels, hybrid UIA element snapping, hardened `ActionPlan` with verb synonym normalization (`SELECT`, `LEFT_CLICK`, `PRESS`, `FINISH`) and zero-crash fallback (`WAIT`), live multimodal grounding smoke test verified (`1.368s`), `101/101` tests passed. |
| **P1.3** | Single-Pass CUA Pipeline, Self-UI Exclusion (`CompanionDock` / `os.getpid()`), Precision App Disambiguation & 4-Tier Test Suite Restructure | **PASS** — Integrated single-pass multimodal inference (`generate_cua_step`) extracting Thought (persona monologue) + Action in one LLM call; masked `CompanionDock` overlay bounds in OCR and excluded `os.getpid()` child controls; hardened `PrecisionAppMatcher` against domain/symbol suffix collisions (`Notepad++` vs `Notepad` = `0.0`, `paint.net` vs `Paint` = `0.0`); added hard node scan ceiling (`total_nodes_scanned >= 2000`) in `ScreenGrounder`; restructured test suite into 4 tiers via [`scripts/test.py`](file:///C:/ParasiteAI/scripts/test.py) (Tier 1 `tests/unit/`: `478/478` passed; Tier 2 `tests/integration/`: `287/287` passed; Total active suite: **`765/765` passed in `74.8s`**). |
| **P1.4** | Stage P1 Benchmark Run (`baseline_p1`), Comparative Scorecard (`P0` vs `P1`) & Standalone Post-Mortem | **PASS** — Executed all 20 benchmark tasks hands-off via [`run_benchmark_p1.bat`](file:///C:/ParasiteAI/run_benchmark_p1.bat). Produced [`baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p1.md), [`baseline_p0_vs_baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0_vs_baseline_p1.md), and [`stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md). |

### 3.2 Official Stage P0 vs. Stage P1 Empirical Scorecard
**P1 Run Date:** 2026-11-08 14:16:50 | **Host:** Windows 10 (Build 19045) / NVIDIA GeForce RTX 4060 (`8,188 MiB` VRAM)  
**P1 Model Under Test:** `UI-TARS-1.5-7B.IQ4_XS.gguf` + `mmproj-Q8_0.gguf` (persistent `llama-server.exe`, `--max-steps-cap 5`)

| Metric | Stage P0 (`baseline_p0`) | Stage P1 (`baseline_p1`) | Empirical Delta | Alpha Gate Target (End of P2) | Stage P1 Verdict |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Cold-Start Subprocess Timeouts** | `5 / 20` (`25.0%`) | **`0 / 20` (`0.0%`)** | **`-5 timeouts`** | `0` | 🟢 **SOLVED (`0ms` warm attach)** |
| **Unhandled Enum / Subprocess Crashes** | `2 / 20` (`10.0%`) | **`0 / 20` (`0.0%`)** | **`-2 crashes`** | `0` | 🟢 **SOLVED** |
| **Median Step Latency** | `5.986s` | **`4.741s`** | **`-1.245s`** | **`<= 5.0s`** | 🟢 **MET (`<= 5.0s` ceiling)** |
| **P90 Step Latency** | `9.798s` | **`5.635s`** | **`-4.163s`** | `<= 6.0s` | 🟢 **MET (`-42.5%` reduction)** |
| **False-`DONE` Rate** | `20.0%` (`4 / 20`) | **`5.0%` (`1 / 20`)** | **`-15.0%`** | **`<= 5.0%`** | 🟢 **MET (`<= 5.0%` ceiling)** |
| **Overall Ground-Truth Pass Rate** | `5.0%` (`1 / 20`) | **`0.0%` (`0 / 20`)** | `-5.0%` | `>= 50.0%` | 🔴 **Blocked by 4 wrapper bugs (Targeted in [`p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md))** |
| **Hardware Interrupt Count** | `0` | **`0`** | `0` | `0` | 🟢 **CLEAN** |

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
| **4-Tier Restructure** | Active Unit (`478`) + Integration (`287`) Suites via `scripts/test.py` | Certified | **PASS** | **765 / 765** |
