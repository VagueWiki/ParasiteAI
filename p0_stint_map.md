# Stage P0 Stint Map: Measure, De-Hardcode & Baseline Benchmark

**Parent Review:** [feasibility_review.md](file:///C:/Users/Suici/.gemini/antigravity/brain/e08f71d9-0960-44dd-99c8-c3319e9081d6/feasibility_review.md) (§5, §6, §8, §10)  
**Objective:** Establish an honest, automated **20-task Windows benchmark** with independent ground-truth verifiers, strip canned outputs and app-specific code branches from the cognitive core, align config/invariants to the resolved decisions (6.5 GB VRAM ceiling, visible cursor actuation, browser-first offload), and record the **P0 Baseline Scorecard** on the current `Qwen2.5-VL-3B` stack before swapping in `UI-TARS-1.5-7B` in P1.

---

## 1. Stint Dependency & Execution Flow

```mermaid
flowchart LR
    S1["Stint P0.1\nDe-Hardcode Core\n& Canned Intro"] --> S2["Stint P0.2\nConfig, Docs &\nGPU Governance"]
    S2 --> S3["Stint P0.3\nEpisode Receipt\n& Exit Codes"]
    S3 --> S4["Stint P0.4\n20-Task Benchmark\n& OS Verifiers"]
    S4 --> S5["Stint P0.5\nHands-Off Baseline\nRun & Scorecard"]
```

| Stint | Name | Primary Files Touched | Est. Effort | Verification Gate |
|---|---|---|---|---|
| **P0.1** | De-Hardcode Core & Canned Outputs | [`dual_mind.py`](file:///c:/ParasiteAI/parasite_ai/mind/dual_mind.py), [`brain_manager.py`](file:///c:/ParasiteAI/parasite_ai/mind/brain_manager.py), [`test_phase3_execution_loop.py`](file:///c:/ParasiteAI/tests/test_phase3_execution_loop.py) | ~2 hrs | Zero canned text overrides; zero game/app name literals in `parasite_ai/mind/`; pytest green |
| **P0.2** | Config, Invariants & GPU Governance | [`config.yaml`](file:///c:/ParasiteAI/config.yaml), [`config.py`](file:///c:/ParasiteAI/parasite_ai/config.py), [`PROJECT.md`](file:///c:/ParasiteAI/PROJECT.md), [`HANDOFF.md`](file:///c:/ParasiteAI/HANDOFF.md), `scripts/check_gpu_governance.py` | ~1 hr | `vram_budget_mb = 6500`, `override_pause_duration_sec = 2.5` synced; GPU check script passes |
| **P0.3** | Episode Telemetry Receipt & Exit Codes | [`main.py`](file:///c:/ParasiteAI/parasite_ai/main.py), [`runtime.py`](file:///c:/ParasiteAI/parasite_ai/runtime.py), [`memory.py`](file:///c:/ParasiteAI/parasite_ai/mind/memory.py) | ~2 hrs | `--episode-report <path.json>` writes full timing/strike/DONE receipt; exit code matches outcome |
| **P0.4** | 20-Task Benchmark Harness & Verifiers | `benchmarks/suite.yaml`, `benchmarks/verifiers.py`, `benchmarks/run_benchmark.py` | ~3 hrs | Dry-run verifier self-test passes on all 20 L1–L3 tasks + 3 stretch probes |
| **P0.5** | Baseline Execution & P0 Scorecard | `benchmarks/results/baseline_p0.json`, `benchmarks/results/baseline_p0_report.md` | ~1–2 hrs (runtime) | Immutable baseline recorded for L1/L2/L3 success, false-`DONE` rate, and step latency |

---

## 2. Detailed Stint Breakdown

### Stint P0.1 — De-Hardcode Core & Strip Canned Outputs
**Why first:** Until the canned intro text and app-name branches are removed, benchmark scores are polluted by code shortcuts that fake task completion.

1. **Remove Canned Introduction Text Override:**
   - In [`DualMindPipeline.step`](file:///c:/ParasiteAI/parasite_ai/mind/dual_mind.py#L2807-L2860), delete the block that replaces instruction echoes with `intro_text = "Hello! I am Parasite, an autonomous desktop companion."`.
   - If the model echoes the prompt instead of generating the requested content, let it fail honestly or handle it via generic prompt formatting—never by injecting a hardcoded sentence.
2. **Replace App-Literal Lists with Structural Window Classification (or Config Data):**
   - In [`parasite_ai/mind/dual_mind.py`](file:///c:/ParasiteAI/parasite_ai/mind/dual_mind.py#L403-L631), remove hardcoded third-party app/game sets (`GAME_PLATFORM_LAUNCHER_PROCESSES`, `"steam"`, `"epic games"`, `"riot client"`, `"discord"`, `"warsim"`, etc.) from core code.
   - Move user-protected workspace process rules (if desired as user preferences) into `config.yaml` data, and make [`is_intermediate_launcher_window`](file:///c:/ParasiteAI/parasite_ai/mind/dual_mind.py#L499-L555) rely strictly on **structural UIA signals** (e.g., modal dialog window styles, child radio/button controls matching generic launch confirmation patterns) rather than process-name allowlists.
3. **Scrub Specific Game/App Names from System Prompts:**
   - In [`LocalBrainManager.generate_action`](file:///c:/ParasiteAI/parasite_ai/mind/brain_manager.py#L1384-L1400) and [`DualMindPipeline`](file:///c:/ParasiteAI/parasite_ai/mind/dual_mind.py#L2244), remove specific game examples (`Rift Wizard`, `Warsim The Realm of Aslona`, `Steam`) from prompt strings so prompts remain domain-general.
4. **Update Unit Tests:**
   - Update [`tests/test_phase3_execution_loop.py`](file:///c:/ParasiteAI/tests/test_phase3_execution_loop.py#L554-L765) to test structural window disposition and config-driven rules rather than hardcoded game literals.

---

### Stint P0.2 — Config, Invariant & Host GPU Governance Alignment
**Why second:** Locks in Decisions D1–D6 from [feasibility_review.md §10](file:///C:/Users/Suici/.gemini/antigravity/brain/e08f71d9-0960-44dd-99c8-c3319e9081d6/feasibility_review.md#L246-L311) before any benchmark runs.

1. **Config & Schema Sync ([`config.yaml`](file:///c:/ParasiteAI/config.yaml) & [`parasite_ai/config.py`](file:///c:/ParasiteAI/parasite_ai/config.py)):**
   - Update `brain.local_model.vram_budget_mb` from `5500` to `6500` in both [`config.yaml:31`](file:///c:/ParasiteAI/config.yaml#L31) and [`LocalModelConfig`](file:///c:/ParasiteAI/parasite_ai/config.py#L128-L133).
   - Fix drift on `safety.override_pause_duration_sec`: set [`config.yaml:47`](file:///c:/ParasiteAI/config.yaml#L47) from `10.0` to `2.5` to match [`SafetyConfig`](file:///c:/ParasiteAI/parasite_ai/config.py#L220-L225) and [`CHANGELOG.md:116`](file:///c:/ParasiteAI/CHANGELOG.md#L116).
2. **Documentation & Invariant Sync:**
   - Update [`PROJECT.md`](file:///c:/ParasiteAI/PROJECT.md) (fix `g:\__Docs\ParasiteAI\` path drift to `C:\ParasiteAI\`) and [`HANDOFF.md`](file:///c:/ParasiteAI/HANDOFF.md) (record the P0–P4 pivot roadmap, 6.5 GB VRAM ceiling, Visible Cursor Actuation invariant, Browser-First T0/T1/T2 planner tiers, and freeze of Phase 5).
3. **Host GPU & WDDM Governance Check (`scripts/check_gpu_governance.py`):**
   - Lightweight diagnostic script run via `uv run python scripts/check_gpu_governance.py` that queries `nvidia-smi` for total/free/used VRAM, checks whether Dedicated vs. Shared GPU memory spillover is occurring, and prints the exact 1-step instruction if `CUDA - Sysmem Fallback Policy` is not yet set to `Prefer No Sysmem Fallback`.

---

### Stint P0.3 — Episode Telemetry Receipt & Deterministic Exit Codes
**Why third:** Right now, [`ParasiteApp._on_dock_close_requested`](file:///c:/ParasiteAI/parasite_ai/main.py#L262-L268) always exits `0` when `--auto-exit-on-complete` fires, regardless of whether the episode ended in `DONE`, a 3-strike loop, or max-steps exhaustion. The benchmark runner needs structured telemetry and truthful exit codes.

1. **`EpisodeReceipt` Model ([`parasite_ai/mind/memory.py`](file:///c:/ParasiteAI/parasite_ai/mind/memory.py)):**
   - Fields:
     - `goal: str`
     - `terminal_reason: Literal["DONE", "MAX_STEPS", "LOOP_ABORT", "PANIC", "ERROR"]`
     - `claimed_done: bool`
     - `steps_executed: int`
     - `max_steps: int`
     - `total_duration_sec: float`
     - `step_latencies_sec: List[float]` (plus breakdown: `grounding_ms`, `llm_pass1_ms`, `llm_pass2_ms`, `actuation_ms`)
     - `total_strikes: int`
     - `highest_tier_reached: str`
     - `hardware_interrupt_count: int`
     - `final_active_window: Dict[str, str]` (`title`, `process_name`)
     - `step_trace: List[Dict[str, Any]]`
2. **CLI & Runtime Wiring ([`parasite_ai/main.py`](file:///c:/ParasiteAI/parasite_ai/main.py), [`parasite_ai/runtime.py`](file:///c:/ParasiteAI/parasite_ai/runtime.py)):**
   - Add `--episode-report <path.json>` to [`parse_args`](file:///c:/ParasiteAI/parasite_ai/main.py#L33-L92).
   - In [`RuntimeOrchestrator._execute_goal_episode`](file:///c:/ParasiteAI/parasite_ai/runtime.py#L279-L376), populate `self.last_episode_receipt` and write it atomically to `--episode-report` on episode completion.
   - Set exit code `0` iff `terminal_reason == "DONE"`, and `1` on `MAX_STEPS`, `LOOP_ABORT`, `PANIC`, or `ERROR`.

---

### Stint P0.4 — The 20-Task Windows Benchmark Suite & OS Ground-Truth Verifiers
**Why fourth:** Replaces mock-only unit testing with real, repeatable desktop task evaluation on Monitor 1 (`0 <= x < 1920, 0 <= y < 1080`) using visible mouse & keyboard actuation.

#### Benchmark Architecture (`benchmarks/`)
- `benchmarks/suite.yaml` — Declarative task definitions (`id`, `tier`, `goal`, `max_steps`, `setup`, `verifier`, `teardown`).
- `benchmarks/verifiers.py` — Independent OS ground-truth checks that inspect reality **after** the episode exits:
  - `window_open(process_name, title_substring)`
  - `window_closed(process_name)`
  - `window_minimized(process_name)`
  - `uia_edit_contains(process_name, expected_substrings, min_chars, forbid_goal_echo=True)`
  - `file_exists_and_contains(path, expected_substrings)`
  - `clipboard_contains(expected_substring)`
- `benchmarks/run_benchmark.py` — Automated runner that:
  1. Resets the clean scratch workspace (`benchmarks/workspace/`),
  2. Runs pre-task `setup` (e.g. closing leftover Notepad/Calc windows or seeding a test file),
  3. Invokes `python main.py --goal "<goal>" --max-steps <N> --auto-exit-on-complete --episode-report <tmp.json>`,
  4. Runs the independent `verifier` against OS state,
  5. Runs `teardown` to leave the desktop clean,
  6. Computes aggregate metrics (`true_success`, `false_done`, `median_step_sec`, `p90_step_sec`).

#### The 20 Core Benchmark Tasks + 3 Live Stretch Probes

| ID | Tier | User Goal Prompt | Ground-Truth Verifier (External OS Check) |
|---|---|---|---|
| **L1-01** | L1 | `"Open Notepad"` | `notepad.exe` window visible & foreground |
| **L1-02** | L1 | `"Open Calculator"` | `CalculatorApp.exe` window visible |
| **L1-03** | L1 | `"Open Paint"` | `mspaint.exe` window visible |
| **L1-04** | L1 | `"Open Notepad and type 'Benchmark Alpha Test 42'"` | UIA `Document`/`Edit` value in `notepad.exe` contains `"Benchmark Alpha Test 42"` |
| **L1-05** | L1 | `"Open Notepad and write a short two-sentence greeting"` | UIA `Document`/`Edit` in `notepad.exe` has $\ge 30$ chars, $\ge 1$ period, and does **not** merely echo `"write a short two-sentence greeting"` |
| **L1-06** | L1 | `"Close Notepad"` *(setup: Notepad pre-opened)* | Zero visible `notepad.exe` top-level windows |
| **L1-07** | L1 | `"Minimize Notepad"` *(setup: Notepad pre-opened)* | `notepad.exe` window exists with `IsIconic(hwnd) == True` |
| **L1-08** | L1 | `"Open Calculator and compute 7 * 8"` | UIA Calculator results element contains `"56"` |
| **L1-09** | L1 | `"Open File Explorer"` | `explorer.exe` `CabinetWClass` window visible |
| **L1-10** | L1 | `"Open Notepad, type 'Draft', and select all text"` | `notepad.exe` active + UIA selection or `Ctrl+C` probe equals `"Draft"` |
| **L2-01** | L2 | `"Open Notepad, type 'Saved Note 101', and save it as C:\ParasiteAI\benchmarks\workspace\note101.txt"` | File `note101.txt` exists on disk and contains `"Saved Note 101"` |
| **L2-02** | L2 | `"Open C:\ParasiteAI\benchmarks\workspace\seed.txt in Notepad and append ' - Approved' to the end"` | UIA text in `notepad.exe` (or saved file) contains both seed text and `" - Approved"` |
| **L2-03** | L2 | `"Open Calculator, compute 144 / 12, and type the result into the open Notepad window"` | `notepad.exe` UIA editor contains `"12"` |
| **L2-04** | L2 | `"Open File Explorer to C:\ParasiteAI\benchmarks\workspace and rename old_name.txt to new_name.txt"` | `new_name.txt` exists and `old_name.txt` does not |
| **L2-05** | L2 | `"Create a new folder named 'Reports' inside C:\ParasiteAI\benchmarks\workspace in File Explorer"` | Directory `benchmarks/workspace/Reports` exists |
| **L2-06** | L2 | `"Close the error dialog and then open Notepad"` *(setup: modal error box + closed Notepad)* | Error dialog dismissed and `notepad.exe` visible |
| **L2-07** | L2 | `"Copy the text from the open Notepad window 'Source' and paste it into the 'Destination' Notepad window"` | Destination window UIA text matches Source string |
| **L3-01** | L3 | `"Open Notepad with unsaved text, close it, and choose Don't Save on the prompt"` *(setup: dirty Notepad)* | `notepad.exe` closed cleanly without modal hanging |
| **L3-02** | L3 | `"Compute 25 * 4 in Calculator, write 'Total: <result>' in Notepad, and save to C:\ParasiteAI\benchmarks\workspace\total.txt"` | `total.txt` exists on disk and contains `"Total: 100"` |
| **L3-03** | L3 | `"Open Chrome, search the web for 'Python PEP 8 line length', and write the number of characters in Notepad"` | `notepad.exe` UIA editor contains `"79"` |
| **S-01** *(Stretch)* | Probe | `"Launch Warsim The Realm of Aslona and start a new game"` | `Warsim.exe` / game console active & past title screen ($\ge 3$ verified state transitions) |
| **S-02** *(Stretch)* | Probe | `"Launch Rift Wizard 2 and enter the first level"` | Rift Wizard 2 window active & past main menu |
| **S-03** *(Stretch)* | Probe | `"Launch RimWorld"` | RimWorld process/window active on Monitor 1 |

---

### Stint P0.5 — Hands-Off Baseline Run & Scorecard Generation
**Why fifth:** Produces the empirical "Before" snapshot so every subsequent change in P1–P4 is judged by delta on the exact same benchmark.

1. **Hands-Off Execution Protocol:**
   - Run `uv run python benchmarks/run_benchmark.py --tier L1,L2,L3 --output benchmarks/results/baseline_p0.json` with zero physical mouse/keyboard touch on Monitor 1 (`hardware_interrupt_count == 0` verified per task).
2. **Generated Baseline Report (`benchmarks/results/baseline_p0_report.md`):**
   - Summary table of L1 (10), L2 (7), L3 (3), and Stretch (3):
     - **True Success Rate (%)** vs. **Claimed `DONE` Rate (%)**
     - **False-`DONE` Rate (%)** (`claimed_done and not ground_truth_pass`)
     - **Median & P90 Step Latency (s)** (split by Grounding vs. VLM Inference vs. Cursor Motion)
     - **Peak VRAM Used (MB)**
     - **Failure Mode Breakdown** (Grounding miss, Wrong target ID, Instruction echo, Premature `DONE`, Context overflow, Loop abort).

---

## 3. Ready to Execute

If this P0 Stint Map looks right to you, say the word (or click **Proceed**) and I will start executing **Stint P0.1 → P0.3** immediately in the codebase, verify the test suite, and build the `benchmarks/` harness (**Stint P0.4**).
