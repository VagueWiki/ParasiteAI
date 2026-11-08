# ParasiteAI — Master Session Handoff & Stage P2 Planning Blueprint
**Generated:** 2026-11-08  
**Project Workspace:** `C:\ParasiteAI`  
**Current Status:** Stages P0 & P1 **100% COMPLETE & AUDITED**; Empirical Benchmarks (`baseline_p0` and `baseline_p1`) Captured; 4-Tier Test Suite 100% Green (`765/765` passed)  
**Next Objective:** Launch a new session to plan and execute **Stage P2: Thin Perception-to-Action Loop, Resilient Parser & Goal Verification**

---

## 1. Executive Summary & Architectural Identity

**ParasiteAI** is a **100% visible, desktop-native local AI assistant** operating directly on the physical **Windows 10** desktop via natural mouse and keyboard kinematics (Cubic Bézier trajectories, Flash & Hogan Min-Jerk velocity profiles, and a click-through `GhostHUD` reticle).

### Ratified Architectural Decisions & Invariants (D1–D6)
| ID | Decision / Invariant | Specification |
| :--- | :--- | :--- |
| **D1** | **VRAM Ceiling & WDDM Governance** | `vram_budget_mb: 6500` (6.5 GB ceiling on RTX 4060 8,188 MiB). Checked via `scripts/check_gpu_governance.py`. `UI-TARS-1.5-7B.IQ4_XS.gguf` (4.25 GB) + `mmproj-Q8_0` (856 MB) loaded in persistent `llama-server.exe` with single-slot KV cache (`-np 1`), consuming ~4.8–5.4 GB total VRAM. |
| **D2** | **100% Visible Physical Kinematics** | All cursor and keyboard actions must remain 100% visible (`MouseDriver` Bézier paths, `GhostHUD` reticle, `KeyboardDriver` cadence typing) with **< 2ms** physical touch preemption (`InterruptGuard`), **2.5s** human override cooldown, and **< 5ms** `Ctrl+Alt+K` instant hard kill. |
| **D3** | **Browser-First / Zero Required Paid API Keys** | Zero required paid API keys. Local computer-use VLM (`TIER_1_LOCAL`) is the primary brain; strategic consultation (`TIER_2_CONSULT`) drives the user's real visible browser (`BrowserOffloader`), with an *opt-in* API planner tier only for users who explicitly configure an API key. |
| **D4** | **Zero Hardcoded App Logic in Core (`parasite_ai/`), Learned App Data Allowed (`data/`)** | Core Python source (`parasite_ai/`) contains zero app-specific branches (`if "warsim" in ...`). Window rules live in `config.yaml` (`WindowRulesConfig`), and learned routines live in `data/`. |
| **D5** | **Phase 5 Frozen Until Alpha Gate Passes** | Self-learning routine caching / SimuLang compilation (Phase 5) remains frozen until the core loop passes the **Alpha Gate** on the 20-task Windows 10 benchmark: **`L1 >= 70%`**, **`L2 >= 40%`**, **`False-DONE <= 5%`**, **`Median Step <= 5.0s`**. |
| **D6** | **Strict Stint Cadence & Result-Oriented Testing** | Enforced by `.agents/rules/strict_stint_cadence.md`: strictly **one stint per execution turn**, mandatory pre-stint implementation plan (`RequestFeedback: true`) and user approval, post-stint `walkthrough.md` gate, and objective OS outcome verification. |

---

## 2. Host Hardware & Environment Profile

* **OS:** **Windows 10** 64-bit, Build 19045 (Classic Win32 `notepad.exe` with `Edit` child HWND, `CalculatorApp.exe`, `mspaint.exe`, `explorer.exe`).
* **GPU:** **NVIDIA GeForce RTX 4060** (`8,188 MiB` dedicated VRAM, Driver `610.74`, CUDA 12).
* **Display Geometry:** Dual-Monitor Side-by-Side (`3840x1080` virtual screen at 100% DPI / 96 DPI; Monitor 1: `0..1920`, Monitor 2: `1920..3840`). Target Monitor: Monitor 1 (`0 <= x < 1920, 0 <= y < 1080`).
* **Python Environment:** Python 3.12 via `uv` at `C:\ParasiteAI\.venv\Scripts\python.exe`.
* **Test Suite Status:** 4-Tier test architecture fully implemented:
  - **Tier 1 (Unit):** `tests/unit/` — **478 / 478 PASSED** in 17.8s.
  - **Tier 2 (Integration):** `tests/integration/` — **287 / 287 PASSED** in 58.6s.
  - **Total Active Tests:** **765 / 765 PASSED (100% green)** in 74.8s via `python scripts/test.py`.
  - **Tier 3 (Archive):** `tests/archive/` (31 historical milestone challenger & stress tests).
  - **Tier 4 (Live OS):** `tests/live_os/` (1 live desktop harness gated by `pytest.mark.live_os`).

---

## 3. The Pivot Roadmap vs. The Feasibility Review

The project structure is governed by the **Architectural Feasibility & Ground-Truth Review** (`feasibility_review.md`):

| Stage | Feasibility Review Scope | Empirical Status | Key Deliverables & Outcome |
| :--- | :--- | :---: | :--- |
| **Stage P0** | **Measure & Baseline** | **COMPLETE (PASS)** | De-hardcoded app literals; GPU governance active; 20-task benchmark suite & Win32 verifiers; `baseline_p0` recorded (**5.0%** pass rate, **20.0%** False-DONE). |
| **Stage P1** | **Model Spike** | **COMPLETE (PASS)** | Persistent CUDA `llama-server.exe` (`b12188`); `UI-TARS-1.5-7B` (IQ4_XS + mmproj) provisioned; native CUA action parser (`uitars_parser.py`); single-pass multimodal pipeline; `baseline_p1` recorded. |
| **Stage P2** | **Structured-First / Thin Loop** | **UPCOMING** | Retire `dual_mind.py` heuristic shell; fix token budget & unclosed parser fallback; relax caret guard; dynamic Windows 10 OS alignment; pre-`DONE` goal verifier. Exit gate: **`L1 >= 70%`**, **`False-DONE <= 5%`**. |
| **Stage P3** | **Planner Tiers** | PLANNED | Keep free visible browser consultation (T1); add opt-in API planner tier (T2); local UI-TARS remains grounder. Exit gate: **`L2 >= 40%`**. |
| **Stage P4** | **Learned Memory (Phase 5)** | PLANNED | Compile verified trajectories into replayable routines. Exit gate: 5x speedup on repeat tasks. |

---

## 4. Empirical Benchmark Post-Mortem: `baseline_p0` vs `baseline_p1`

The hands-off benchmark runner (`run_benchmark_p1.bat`) was executed across all 20 Windows 10 tasks on Monitor 1, producing `benchmarks/results/baseline_p1.json`, `baseline_p1.md`, and `baseline_p0_vs_baseline_p1.md`.

### 4.1 Side-by-Side Topline Scorecard

| Metric | Stage P0 Baseline (`baseline_p0`) | Stage P1 Candidate (`baseline_p1`) | Empirical Delta | Status / Finding |
| :--- | :---: | :---: | :---: | :--- |
| **Cold-Start Timeouts** | **5 tasks timed out** (45s–90s) | **0 tasks timed out** (0ms) | **-5 timeouts** | 🟢 **SOLVED** (Persistent daemon works) |
| **Subprocess Exit Crashes** | 2 tasks crashed on `SELECT` enum | **0 crashes** | **-2 crashes** | 🟢 **SOLVED** (Schema recovery works) |
| **Median Step Latency** | **5.986s** (P90: 9.798s) | **4.741s** (P90: 5.635s) | **-1.245s** | 🟢 **IMPROVED** (1.25s faster per step) |
| **False-`DONE` Rate** | **20.0%** (4 tasks) | **5.0%** (1 task) | **-15.0%** | 🟢 **IMPROVED** (75% drop in hallucinations) |
| **Overall Pass Rate** | **5.0%** (1 / 20) | **0.0%** (0 / 20) | -5.0% | 🔴 **UNRESOLVED** (Hit MAX_STEPS on `WAIT`) |
| **Hardware Interrupts** | 0 | 0 | 0 | 🟢 **CLEAN** (Zero false self-interrupts) |

### 4.2 Four Root Causes Discovered from Raw Receipts & Logs

Detailed inspection of the receipts (`benchmarks/results/L*.json`) and debug logs revealed why the pass rate was 0.0% despite the model reasoning correctly:

1. **CUA Token Truncation (`max_tokens: 128`):**
   - In `LocalBrainManager.generate_cua_step()`, `max_tokens` was capped at 128.
   - `UI-TARS-1.5-7B` outputs a detailed persona monologue first (`Thought: ...`, ~70 tokens).
   - When emitting `Action: click(start_box='(24,980)`, it hit the 128-token limit and was truncated mid-string before emitting the closing parenthesis `')'`.
2. **Brittle Parser Fallback Coerced Actions to `WAIT`:**
   - In `uitars_parser.py:206`, the parser checked `action_str.endswith(")")`.
   - Because the action was truncated or had trailing tokens (e.g. `\nassistant`), `endswith(")")` evaluated to `False`.
   - The parser fell through to treating the entire truncated string as an unknown enum verb, which failed validation and coerced into **`ActionType.WAIT`**.
   - The agent sat idling in `WAIT` for 5 steps until `MAX_STEPS_EXHAUSTED` fired on 19 of the 20 tasks.
3. **Overly Restrictive Win32 Caret Guard on `TYPE`:**
   - In tasks where the agent attempted to type into Windows Search (e.g. `L2-01`), the action aborted with `"Caret focus not detected"`.
   - Modern Windows DirectUI/XAML search bars do not report classic blinking carets via `GetGUIThreadInfo`, causing keyboard inputs to be blocked unnecessarily.
4. **Hardcoded Windows 11 in Gemini Consultation Prompts:**
   - In `parasite_ai/mind/plan.py` (lines 330 and 522), the prompt hardcoded:
     `You are the Strategic Cognitive Advisor for ParasiteAI, a 100% visible, desktop-native Windows 11 AI companion.`
     `target_environment: str = Field(default="Windows 11 64-bit Desktop")`
   - Gemini was instructed that the system was **Windows 11** rather than the host **Windows 10** (`Build 19045`), causing it to advise centered-taskbar Start clicks and tabbed WinUI 3 Notepad operations that do not match the desktop.

---

## 5. Scope & Work Breakdown for the Stage P2 Chat

When opening the new chat session, invoke `/plan` to formulate the Stage P2 stint sequence. The concrete engineering deliverables for Stage P2 are:

### Deliverable 1: Token Budget & Prompt Tuning (`brain_manager.py`)
- Increase `max_tokens` from `128` to `256` or `384` in `generate_cua_step()`.
- Add stop tokens `["\n\n", "User:", "Observation:"]` to cleanly terminate generation immediately after the `Action:` line.

### Deliverable 2: Resilient Regex Action Extraction (`uitars_parser.py`)
- Replace rigid `action_str.endswith(")")` check with regex matching:
  `re.search(r"([a-zA-Z_0-9]+)\s*\((.*?)(?:\)|\Z)", action_str, re.DOTALL)`
- Automatically extract function name and arguments even if closing paren is omitted or trailing text exists, guaranteeing valid actions are never coerced to `WAIT`.

### Deliverable 3: Keyboard Caret Guard Relaxation (`dual_mind.py`)
- Only enforce strict Win32 caret detection if typing into an active document/editor.
- For application launch typing (Windows Start Menu, Run dialog, Explorer address bar), permit keypresses without blocking on `Caret focus not detected`.

### Deliverable 4: Dynamic Host OS Detection (`plan.py`)
- Dynamically detect host OS (`platform.release()`) so prompts correctly identify the host as `Windows 10 64-bit Desktop`.
- Guarantee Gemini provides accurate bottom-left Start button coordinates (`24, 1056`) and classic Win32 Notepad instructions.

### Deliverable 5: Pre-`DONE` Ground-Truth Verification (`dual_mind.py`)
- Implement objective state check before accepting `ActionType.DONE` (or `finished()`).
- Verify target window/process is visible; if target is missing, intercept `DONE` and continue episode.

### Deliverable 6: Stage P2 Benchmark Execution (`baseline_p2`)
- Re-run `run_benchmark_p1.bat --output-name baseline_p2` hands-off across the 20 tasks.
- Verify exit gate: **`L1 >= 70%`**, **`False-DONE <= 5%`**, **`Median Step <= 5.0s`**.

---

## 6. How to Bootstrap the New Session

In the new chat session, prompt the agent with:
```text
I am starting Stage P2: Thin Perception-to-Action Loop, Resilient Parser & Goal Verification.
Please read HANDOFF.md, GATE_STATUS.md, and feasibility_review.md.
Review the Stage P1 Post-Mortem in stage_p1_postmortem.md.
Let's begin by formulating the implementation plan (/plan) for Stint P2.1.
```
