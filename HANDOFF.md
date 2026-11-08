# ParasiteAI — Master Session Handoff & Stage P2 Bootstrap Guide

**Generated:** 2026-11-08  
**Project Workspace:** `C:\ParasiteAI`  
**Current Status:**
- **Stage P0 (Measure, De-Hardcode & Baseline):** **100% COMPLETE** ([`p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md) | [`baseline_p0.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0.md))
- **Stage P1 (Local CUA Engine Upgrade — `llama-server` + `UI-TARS-1.5-7B`):** **100% COMPLETE** ([`p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md) | [`baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p1.md) | [`stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md))
- **4-Tier Test Suite Restructuring:** **100% GREEN** (`765 / 765` active unit + integration tests passing in `74.8s` via [`scripts/test.py`](file:///C:/ParasiteAI/scripts/test.py))
**Next Objective:** Execute **Stage P2: Thin Perception-to-Action Loop, Resilient CUA Parser & Pre-`DONE` Verification** (`P2.1`–`P2.4`) as grounded in [`p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md).

---

## 1. Executive Summary & Architectural Identity

**ParasiteAI** is a **100% visible, desktop-native local AI assistant** operating directly on the physical **Windows 10** desktop via natural mouse and keyboard kinematics (Cubic Bézier trajectories, Flash & Hogan Min-Jerk velocity profiles, and a click-through `GhostHUD` reticle) with zero headless browsers, zero invisible scrapers, and zero required paid API keys.

### Ratified Architectural Decisions & Invariants (D1–D6)
| ID | Decision / Invariant | Specification |
| :--- | :--- | :--- |
| **D1** | **VRAM Ceiling & WDDM Governance** | `vram_budget_mb: 6500` (6.5 GB ceiling on RTX 4060 `8,188 MiB`). Verified via [`scripts/check_gpu_governance.py`](file:///C:/ParasiteAI/scripts/check_gpu_governance.py). `UI-TARS-1.5-7B.IQ4_XS.gguf` (`4.25 GB`) + `mmproj-Q8_0.gguf` (`856 MB`) runs in persistent `llama-server.exe` with single-slot KV cache (`-np 1 -c 4096 --image-min-tokens 1024`), consuming `~5.2 GB` total VRAM. |
| **D2** | **100% Visible Physical Kinematics** | All cursor and keyboard actions remain 100% visible (`MouseDriver` Bézier paths, `GhostHUD` reticle, `KeyboardDriver` clipboard/cadence typing) with **< 2ms** physical touch preemption (`InterruptGuard`), **2.5s** human override cooldown (`override_pause_duration_sec: 2.5`), and **< 5ms** `Ctrl+Alt+K` instant hard kill. |
| **D3** | **Browser-First / Zero Required Paid API Keys** | Zero required paid API keys. Local computer-use VLM (`TIER_1_LOCAL`) is the primary brain; strategic consultation (`TIER_2_CONSULT`) drives the user's real visible browser (`BrowserOffloader`), with an *opt-in* API planner tier only for users who explicitly configure an API key. |
| **D4** | **Zero Hardcoded App Logic in Core (`parasite_ai/`), Learned App Data Allowed (`data/`)** | Core Python source (`parasite_ai/`) contains zero app-specific branches (`if "warsim" in ...`) or benchmark task ID shortcuts. Window rules live in `config.yaml` (`WindowRulesConfig`), and learned routines live in `data/`. |
| **D5** | **Phase 5 Frozen Until Alpha Gate Passes** | Self-learning routine caching / SimuLang compilation (Phase 5) remains frozen until the core loop passes the **Alpha Gate** on the 20-task Windows 10 benchmark: **`L1 >= 70%`**, **`L2 >= 40%`**, **`False-DONE <= 5%`**, **`Median Step <= 5.0s`**. |
| **D6** | **Strict Stint Cadence & Result-Oriented Testing** | Enforced by [`.agents/rules/strict_stint_cadence.md`](file:///C:/ParasiteAI/.agents/rules/strict_stint_cadence.md): strictly **one stint per execution turn**, mandatory pre-stint implementation plan (`RequestFeedback: true`) and user approval, post-stint `walkthrough.md` gate, and objective OS outcome verification. |

---

## 2. Host Hardware, OS & 4-Tier Test Suite Profile

* **OS:** **Windows 10** 64-bit, Build 19045 (Classic Win32 `notepad.exe` with `Edit` child HWND, `CalculatorApp.exe`, `mspaint.exe`, `explorer.exe`).
* **GPU:** **NVIDIA GeForce RTX 4060** (`8,188 MiB` dedicated VRAM, Driver `610.74`, CUDA 12).
* **Display Geometry:** Dual-Monitor Side-by-Side (`3840x1080` virtual screen at 100% DPI / 96 DPI; Monitor 1: `0..1920`, Monitor 2: `1920..3840`). Target Benchmark Monitor: Monitor 1 (`0 <= x < 1920, 0 <= y < 1080`).
* **Python Environment:** Python 3.12 via `uv` at `C:\ParasiteAI\.venv\Scripts\python.exe` (automatically detected by [`scripts/test.py`](file:///C:/ParasiteAI/scripts/test.py)).
* **4-Tier Test Suite Commands & Status:**
  - `python scripts/test.py unit` $\rightarrow$ **Tier 1 (`tests/unit/`):** **478 / 478 PASSED** in `17.8s`
  - `python scripts/test.py integration` $\rightarrow$ **Tier 2 (`tests/integration/`):** **287 / 287 PASSED** in `58.6s`
  - `python scripts/test.py` $\rightarrow$ **All Active Tests (Tier 1 + Tier 2):** **765 / 765 PASSED (100% green)** in `74.8s`
  - `python scripts/test.py live_os` $\rightarrow$ **Tier 4 (`tests/live_os/`):** Live desktop harness (`pytest.mark.live_os`)
  - `python scripts/test.py archive` $\rightarrow$ **Tier 3 (`tests/archive/`):** 31 historical milestone challenger/stress suites

---

## 3. Architectural Continuity: From `feasibility_review.md` to Stage P2

The entire pivot is anchored by the **Architectural Feasibility & Ground-Truth Review** ([`feasibility_review.md`](file:///C:/ParasiteAI/feasibility_review.md)) and tracked across three root-level Stint Maps:

1. **[`p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md) (Stage P0 — Complete):**
   - Stripped app-specific literals (`P0.1`), locked the 6,500 MB VRAM ceiling (`P0.2`), added `EpisodeReceipt` & deterministic exit codes (`P0.3`), built the 20-task Windows 10 ground-truth verifiers (`P0.4`), and recorded [`baseline_p0.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0.md) (`5.0%` pass, `20.0%` False-DONE, `5` cold-start timeouts, `2` enum crashes, `5.986s` median step).
2. **[`p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md) & [`stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md) (Stage P1 — Complete):**
   - Deployed persistent CUDA `llama-server.exe` + `UI-TARS-1.5-7B` (`IQ4_XS` + `mmproj-Q8_0`) (`P1.1`), built `uitars_parser.py` & `ActionPlan` verb recovery (`P1.2`), merged persona + action into single-pass `generate_cua_step()` & excluded `CompanionDock`/`os.getpid()` from grounding (`P1.3`), and executed [`baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p1.md) (`P1.4`).
   - **What `baseline_p1` Solved:** Cold-start timeouts dropped **`5 -> 0`** (`0ms` warm attach), unhandled enum crashes dropped **`2 -> 0`**, median step latency dropped **`5.986s -> 4.741s`** (P90 `9.798s -> 5.635s`), and False-`DONE` dropped **`20.0% -> 5.0%`**.
   - **What `baseline_p1` Exposed (Full forensic trace in [`stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md)):**
     1. **RC #1 (`brain_manager.py#L1875`):** `max_tokens: int = 128` truncated `Action: click(start_box='(24,980)'` after a ~75-token `Thought:` monologue or allowed trailing `\nassistant` role tokens due to missing stop sequences.
     2. **RC #2 (`uitars_parser.py#L66,L206`):** `if "(" in action_str and action_str.endswith(")")` failed whenever the closing `)` was clipped or followed by `\nassistant`, falling through to `ActionPlan._coerce_null_fields` which coerced valid `click(...)` calls into **`ActionType.WAIT`** on `19/20` tasks.
     3. **RC #3 (`dual_mind.py#L2612`):** When `TYPE` (`"notepad"`) did execute on `L2-01`, `dual_mind.py` blocked it twice with `"Caret focus not detected"` and then escalated to a **`47.914s` Tier 2 Google Gemini browser consultation** during a local Notepad task.
     4. **RC #4 (`plan.py#L330,L522`):** `CapabilityContract` and the Strategic Advisor prompt hardcoded `"Windows 11 64-bit Desktop"` instead of the actual **Windows 10 (Build 19045)** host.
3. **[`p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md) (Stage P2 — Ready for Implementation):**
   - Synthesizes [`feasibility_review.md`](file:///C:/ParasiteAI/feasibility_review.md) (§2.2, §8 *"Same Body, New Mind"*, §9 *Alpha Gate*) with the 4 empirical `baseline_p1` root causes across 4 bounded stints (`P2.1`–`P2.4`):
     - **Stint P2.1:** CUA Output Budget (`max_tokens=256` + stop sequences), Resilient Regex Action Parser (`uitars_parser.py`), and Windows 10 Host Alignment (`plan.py`).
     - **Stint P2.2:** Decommissioning the `dual_mind.py` Heuristic Web & Caret Guard Relaxation (`Perceive -> Decide -> Act` CUA fast-path).
     - **Stint P2.3:** Objective Pre-`DONE` Goal Verifiers (`parasite_ai/mind/verifier.py`) & Anti-Stagnation Visual History.
     - **Stint P2.4:** Stage P2 Alpha Gate Benchmark Certification (`baseline_p2`: `L1 >= 70%`, `L2 >= 40%`, `False-DONE <= 5%`, `Median Step <= 5.0s`).

---

## 4. Key File Reference Index

### Strategic & Grounding Documents
- [`C:\ParasiteAI\feasibility_review.md`](file:///C:/ParasiteAI/feasibility_review.md) — Master Architectural Feasibility & Ground-Truth Review
- [`C:\ParasiteAI\p0_stint_map.md`](file:///C:/ParasiteAI/p0_stint_map.md) — Stage P0 Stint Map (Completed)
- [`C:\ParasiteAI\p1_stint_map.md`](file:///C:/ParasiteAI/p1_stint_map.md) — Stage P1 10-Dimension Stint Map (Completed)
- [`C:\ParasiteAI\stage_p1_postmortem.md`](file:///C:/ParasiteAI/stage_p1_postmortem.md) — Standalone Stage P1 Empirical Post-Mortem (`baseline_p0` vs. `baseline_p1`)
- [`C:\ParasiteAI\p2_stint_map.md`](file:///C:/ParasiteAI/p2_stint_map.md) — **Canonical Stage P2 10-Dimension Stint Map (`P2.1`–`P2.4`)**
- [`C:\ParasiteAI\PROJECT.md`](file:///C:/ParasiteAI/PROJECT.md) — System Architecture, D1–D6 Invariants & Repository Layout
- [`C:\ParasiteAI\GATE_STATUS.md`](file:///C:/ParasiteAI/GATE_STATUS.md) — Milestone & Pivot Stage Gate Audit Status
- [`C:\ParasiteAI\.agents\rules\strict_stint_cadence.md`](file:///C:/ParasiteAI/.agents/rules/strict_stint_cadence.md) — Mandatory 1-Stint-Per-Turn Cadence Rule

### Core Code Files Targeted in Stage P2
- [`parasite_ai/mind/brain_manager.py`](file:///C:/ParasiteAI/parasite_ai/mind/brain_manager.py#L1868-L1955) — `LlamaServerBackend` & `generate_cua_step()` (`max_tokens: 128` at line 1875)
- [`parasite_ai/mind/uitars_parser.py`](file:///C:/ParasiteAI/parasite_ai/mind/uitars_parser.py#L60-L240) — `parse_uitars_response()` (`action_str.endswith(")")` at line 206)
- [`parasite_ai/mind/plan.py`](file:///C:/ParasiteAI/parasite_ai/mind/plan.py#L330-L530) — `CapabilityContract` & Strategic Advisor prompt (`"Windows 11"` at lines 330 & 522)
- [`parasite_ai/mind/dual_mind.py`](file:///C:/ParasiteAI/parasite_ai/mind/dual_mind.py#L2200-L2750) — `DualMindPipeline.step()` & `_verify_caret_focus()` (line 2612)
- [`parasite_ai/mind/memory.py`](file:///C:/ParasiteAI/parasite_ai/mind/memory.py) — `ActionPlan`, `StepRecord`, `EpisodeReceipt`, and `EpisodicMemory`

### Benchmark & Test Harness
- [`scripts/test.py`](file:///C:/ParasiteAI/scripts/test.py) — 4-Tier Test Runner (`unit`, `integration`, `live_os`, `archive`)
- [`scripts/serve_llama.py`](file:///C:/ParasiteAI/scripts/serve_llama.py) — Persistent `llama-server` supervisor CLI (`start`, `warm`, `status`, `stop`)
- [`scripts/check_gpu_governance.py`](file:///C:/ParasiteAI/scripts/check_gpu_governance.py) — RTX 4060 6,500 MB VRAM budget & WDDM spillover verifier
- [`scripts/compare_benchmarks.py`](file:///C:/ParasiteAI/scripts/compare_benchmarks.py) — Automated side-by-side benchmark comparator
- [`benchmarks/results/baseline_p0.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0.md) & [`baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p1.md) & [`baseline_p0_vs_baseline_p1.md`](file:///C:/ParasiteAI/benchmarks/results/baseline_p0_vs_baseline_p1.md)

---

## 5. Copy-Pasteable Bootstrap Prompt for the New Stage P2 Chat Session

Copy and paste the following block into a brand-new chat session to start Stage P2 with complete grounding:

```markdown
/plan We are starting Stage P2 (Thin Perception-to-Action Loop, Resilient CUA Parser & Pre-DONE Verification) in `C:\ParasiteAI`.

Before proposing the Stint P2.1 implementation plan, read these grounding documents in full:
1. `C:\ParasiteAI\HANDOFF.md` (Master context, D1–D6 invariants, and exact file/line map)
2. `C:\ParasiteAI\p2_stint_map.md` (Canonical 10-Dimension Stage P2 Stint Map covering P2.1–P2.4 and how it maps to `feasibility_review.md` §2.2, §8, §9)
3. `C:\ParasiteAI\stage_p1_postmortem.md` (Empirical retrospective of `baseline_p0` vs `baseline_p1` and the 4 wrapper root causes)
4. `C:\ParasiteAI\.agents\rules\strict_stint_cadence.md` (Mandatory 1-stint-per-turn cadence rule)

Then inspect `parasite_ai/mind/brain_manager.py` (line 1875), `parasite_ai/mind/uitars_parser.py` (lines 60–240), and `parasite_ai/mind/plan.py` (lines 330, 522), and present the implementation plan artifact (`RequestFeedback: true`, `UserFacing: true`) for **Stint P2.1: CUA Output Budget, Resilient Action Parser & Windows 10 Host Alignment**.
```
