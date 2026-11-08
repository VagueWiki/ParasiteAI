# ParasiteAI — Master Session Handoff & Stage P1 Planning Blueprint
**Generated:** 2026-11-07  
**Project Workspace:** `C:\ParasiteAI`  
**Current Status:** Stage P0 (`P0.1`–`P0.5`) **100% COMPLETE & VERIFIED**; Empirical Baseline (`baseline_p0`) Captured  
**Next Objective:** Plan and execute **Stage P1: Local CUA Engine Upgrade (`llama-server` + `UI-TARS-1.5-7B`)**

---

## 1. Executive Summary & Architectural Identity

**ParasiteAI** is a **100% visible, desktop-native local AI assistant** operating directly on the physical **Windows 10** desktop via natural, human-like mouse and keyboard kinematics (Cubic Bézier trajectories, Flash & Hogan Min-Jerk velocity profiles, and a click-through `GhostHUD` reticle).

### Ratified Architectural Decisions & Invariants (D1–D6)
| ID | Decision / Invariant | Specification |
| :--- | :--- | :--- |
| **D1** | **VRAM Ceiling & WDDM Governance** | `vram_budget_mb: 6500` (6.5 GB ceiling on the 8,188 MiB RTX 4060). Because Windows 10 desktop compositing + standard apps consume ~1,600–2,400 MiB VRAM (~5,700–6,300 MiB free), active model + `mmproj` + KV cache must stay within **~4.8–5.4 GB** to avoid Windows WDDM PCIe system-RAM spillover. Checked via `scripts/check_gpu_governance.py`. |
| **D2** | **100% Visible Physical Kinematics** | All cursor and keyboard actions must remain 100% visible (`MouseDriver` Bézier paths, `GhostHUD` reticle, `KeyboardDriver` fast clipboard paste / cadence typing) with **< 2ms** physical touch preemption (`InterruptGuard`), **2.5s** human override cooldown (`override_pause_duration_sec: 2.5`), and **< 5ms** `Ctrl+Alt+K` instant hard kill. Structured UIA + VLM coordinate grounding and deterministic launch helpers are permitted under the hood provided actuation is visible. |
| **D3** | **Browser-First / Zero Required Paid API Keys** | Zero required paid API keys. Local computer-use VLM (`TIER_1_LOCAL`) is the primary brain; strategic consultation (`TIER_2_CONSULT`) drives the user's real visible browser (`BrowserOffloader`), with an *opt-in* API planner tier only for users who explicitly configure an API key. |
| **D4** | **Zero Hardcoded App Logic in Core (`parasite_ai/`), Learned App Data Allowed (`data/`)** | Core Python source (`parasite_ai/`) contains zero app-specific branches (`if "warsim" in ...`). Static window rules live in `config.yaml` (`WindowRulesConfig`), and learned per-application schemas/notes/routines live in external `data/` files. |
| **D5** | **Phase 5 Frozen Until Alpha Gate Passes** | Self-learning routine caching / SimuLang compilation (Phase 5) remains frozen until the core loop passes the **Alpha Gate** on the 20-task Windows 10 benchmark: **`L1 >= 70%`**, **`L2 >= 40%`**, **`False-DONE <= 5%`**, **`Median Step <= 5.0s`**. |
| **D6** | **Strict Stint Cadence & Result-Oriented Testing** | Enforced by `.agents/rules/strict_stint_cadence.md`: strictly **one stint per execution turn**, mandatory pre-stint implementation plan (`RequestFeedback: true`) and user approval, post-stint `walkthrough.md` gate, and objective OS outcome tests rather than mocked internal plumbing. |

---

## 2. Host Hardware, OS & Environment Profile

* **OS:** **Windows 10** 64-bit (Classic Win32 `notepad.exe` with `Edit` child HWND, `CalculatorApp.exe`, `mspaint.exe`, `explorer.exe`).
* **GPU:** **NVIDIA GeForce RTX 4060** (`8,188 MiB` dedicated VRAM, Driver `610.74`, CUDA 12).
  * *Empirical VRAM Headroom Note:* Live `check_gpu_governance.py` telemetry on Windows 10 showed `1,859–2,480 MiB` used by desktop compositing and background apps (`5,700–6,329 MiB` free VRAM, or `-171 MB` relative to the 6,500 MB ceiling). In Stage P1, configure `UI-TARS-1.5-7B` (`Q4_K_M` or `IQ4_XS` + `mmproj`) with bounded context (`-c 4096`, quantized KV cache `-ctk q8_0 -ctv q8_0` if supported) so total `llama-server` VRAM stays around **4.8–5.3 GB**, leaving comfortable headroom for Windows 10 apps.
* **Display Geometry:** Dual-Monitor Side-by-Side (`3840x1080` virtual screen at 100% DPI / 96 DPI; Monitor 1: `0..1920`, Monitor 2: `1920..3840`).
* **Python Environment:** Python 3.12 via `uv` at `C:\ParasiteAI\.venv\Scripts\python.exe`.
* **Sandbox vs. Interactive Desktop Constraint:**
  * Processes spawned inside Antigravity's `run_command` tool run under a restricted sandbox token where Win32 GDI `BitBlt` and root UIA tree enumeration are blocked (`ScreenCapture.last_capture_backend_used == "synthetic"`).
  * `benchmarks/run_benchmark.py` includes `check_interactive_desktop_access()` to detect this immediately. Full live benchmark runs (`run_baseline_p0.bat`) are executed by the user in an interactive Windows 10 console, while `--dry-verify` and unit/subsystem tests run directly inside `run_command`.

---

## 3. Stage P0 Empirical Baseline Post-Mortem (`baseline_p0`)

All 5 stints of Stage P0 (`P0.1` Core De-Hardcoding, `P0.2` GPU Governance, `P0.3` `EpisodeReceipt` & Exit Codes, `P0.4` 20-Task Windows 10 Verifiers, `P0.5` Hands-Off Baseline Runner) are complete.

On **2026-11-07 03:07**, the full 20-task interactive baseline (`run_baseline_p0.bat` -> `benchmarks/results/baseline_p0.md` & `baseline_p0.json`) was executed against the legacy in-process `qwen2.5-3b-instruct-q4_k_m.gguf` brain (`--max-steps-cap 5`).

### 3.1 Topline Scorecard (`baseline_p0` vs. Alpha Gate)
| Metric | `baseline_p0` Result | Alpha Gate Target | Status |
| :--- | :---: | :---: | :---: |
| **Ground-Truth Pass Rate (All 20 Tasks)** | **5.0% (1 / 20)** | `>= 50.0%` | ❌ Baseline Established |
| **Level 1 Pass Rate (Basic Single-App, 10 Tasks)** | **10.0% (1 / 10)** | **`>= 70.0%`** | ❌ Only `L1-07` (*Minimize Notepad*) passed |
| **Level 2 Pass Rate (Multi-Step / File / Dialog, 7 Tasks)** | **0.0% (0 / 7)** | **`>= 40.0%`** | ❌ 4/7 claimed `FALSE_DONE`, 3/7 hit `MAX_STEPS` |
| **Level 3 Pass Rate (Complex Multi-App / Recovery, 3 Tasks)** | **0.0% (0 / 3)** | Informational | ❌ 1 `ERROR` (`SELECT MenuItem`), 1 `MAX_STEPS`, 1 `TIMEOUT` |
| **Agent Claimed `DONE` Rate** | **25.0% (5 / 20)** | — | 4 of 5 `DONE` claims were hallucinations (`80%` false) |
| **False-`DONE` Rate** | **20.0% (4 / 20)** | **`<= 5.0%`** | ❌ `L2-02`, `L2-05`, `L2-06`, `L2-07` |
| **Median Step Latency** | **5.986s** (P90: **9.798s**) | **`<= 5.0s`** | ❌ Exceeds 5.0s budget + 5 cold-start timeouts |
| **Hardware Interrupts** | **0** | `0` | ✅ Sub-2ms hook clean (0 false self-triggers) |

### 3.2 Five Empirical Root-Cause Failure Patterns (From `L*_receipt.json`)
Inspecting `benchmarks/results/baseline_p0.json` and the individual task receipts (`L1-03_receipt.json` .. `L3-02_receipt.json`) reveals **five concrete engineering root causes** that Stage P1 and Stage P2 must solve:

1. **Root Cause #1: Subprocess In-Process `llama-cpp-python` Cold-Start & Dual-Pass Latency (`5/20` Tasks Timed Out: `L1-01`, `L1-02`, `L1-05`, `L1-06`, `L3-03`)**
   - Every task spawns `main.py` as a fresh subprocess. Loading the GGUF model in-process via `llama-cpp-python` + initializing RapidOCR/UIA + running **two** sequential LLM calls per step (Pass 1 Persona monologue + Pass 2 Action JSON) caused 5 tasks to hit their `45s–90s` wall-clock timeout before completing (`total_steps: 0`, `exit_reason: "TIMEOUT"`), and pushed Step 1 latency to `6.5s–12.1s`.
   - **Stage P1 Fix:** Replace in-process `llama-cpp-python` loading with a persistent out-of-process **`llama-server` daemon** (`LlamaServerBackend` on `127.0.0.1:8080`) that keeps model weights pinned in VRAM across episodes (`0ms` cold-start per task), and switch to **single-pass CUA inference** (generating thought + action in one completion, decoupling persona speech from the critical action path).

2. **Root Cause #2: Blind Text-Only 3B Model Hallucinating `DONE` (`4/20` Tasks = `FALSE_DONE`: `L2-02`, `L2-05`, `L2-06`, `L2-07`)**
   - `qwen2.5-3b-instruct` is a **text-only** 3B model reading noisy UIA text lists without seeing the screen.
   - In `L2-02_receipt.json` (*Open seed.txt in Notepad and append ' - Approved'*), the agent double-clicked `Open Folder as Workspace...` in Notepad++, double-clicked its own Companion Dock speech bubble, double-clicked `File`, and emitted `DONE` on Step 4!
   - In `L2-06_receipt.json` (*Close the error dialog and then open Notepad*), the agent completely ignored the modal `ParasiteAI Benchmark Alert` dialog, clicked `File -> Close Ctrl+W` inside a background Notepad++ window, and emitted `DONE` on Step 5!
   - **Stage P1 / P2 Fix:** Upgrade the brain to a true vision-language computer-use model (**`UI-TARS-1.5-7B`** with `--mmproj`) that directly perceives the desktop screenshot, and enforce pre-`DONE` state verification in Stage P2.

3. **Root Cause #3: Self-UI Grounding Pollution & App Name Collisions (`L1-03`, `L1-10`, `L2-02`, `L2-06`)**
   - **Self-UI Clicking:** In `L2-02` Step 2, `ScreenGrounder` indexed ParasiteAI's own `CompanionDock` window (`target_label: "Ah, looking at the scene, I see Discord is active..."` at `[204, 120]`), and the agent double-clicked its own UI!
   - **App Collisions (`Notepad++` vs `Notepad`, `Paint.NET` vs `Paint`):**
     - In `L1-03_receipt.json` (*Open Paint*), the agent saw a desktop shortcut `paint.net` (`[37, 710]`) and launched `paintdotnet.exe` instead of Windows Paint (`mspaint.exe`).
     - In `L1-10_receipt.json` and `L2-02_receipt.json`, the agent clicked taskbar icon `Notepad++` (`notepad++.exe`) instead of Windows `Notepad` (`notepad.exe`).
   - **Stage P1 Fix:** Filter out ParasiteAI's own process ID (`os.getpid()`) and window titles (`CompanionDock`, `GhostHUD`) inside `ScreenGrounder.ground()`, and enforce exact system app disambiguation (`notepad.exe` vs `notepad++.exe`, `mspaint.exe` vs `paintdotnet.exe`) during app resolution.

4. **Root Cause #4: Unhandled Pydantic `ActionPlan` Enum Crashes on Hallucinated Verbs (`2/20` Tasks = `ERROR`: `L1-10`, `L3-01`)**
   - In `L1-10_receipt.json` (Step 3), the model emitted `"action": "SELECT"`.
   - In `L3-01_receipt.json` (Step 2), the model emitted `"action": "SELECT MenuItem"`.
   - Because `ActionPlan` strictly requires one of `'CLICK'`, `'DOUBLE_CLICK'`, `'RIGHT_CLICK'`, `'CLICK_AND_TYPE'`, `'TYPE'`, `'HOTKEY'`, `'SCROLL'`, `'MINIMIZE_WINDOW'`, `'CLOSE_WINDOW'`, `'WAIT'`, `'PANIC'`, `'OFFLOAD_WEB_AI'`, `'DONE'`, `'RUN_CLI_COMMAND'`, the raw Pydantic `ValidationError` crashed the episode (`exit_reason: "ERROR"`).
   - **Stage P1 Fix:** Implement the native `UI-TARS-1.5-7B` action output parser (`click(start_box=...)`, `left_double(...)`, `right_single(...)`, `type(content=...)`, `hotkey(key=...)`, `scroll(...)`, `wait()`, `finished()`) plus verb normalization (`SELECT*` -> `CLICK`) and graceful retry on malformed model outputs so a single bad token never crashes an episode.

5. **Root Cause #5: Brittle `dual_mind.py` Heuristic Override Loops (`L1-04_receipt.json`)**
   - In `L1-04` (*Open Notepad and type 'Benchmark Alpha Test 42'*), Step 1 pressed `enter`, Step 2 pressed `win` (opening the Start menu), and Steps 3, 4, and 5 spammed `CLOSE_WINDOW` three times in a row until `MAX_STEPS`!
   - **Stage P1 / P2 Fix:** Bypass legacy `dual_mind.py` heuristic overrides when running the CUA pipeline so the grounded VLM + clean resolver drive actions directly.

---

## 4. Stage P1 Architecture Blueprint & Proposed Stint Map

**Stage P1 Goal:** Replace the slow, blind in-process 3B text model (`llama-cpp-python` + `qwen2.5-3b-instruct`) with a persistent out-of-process **`llama-server`** hosting a fine-tuned Vision-Language Computer-Use Agent (**`UI-TARS-1.5-7B`** GGUF + `mmproj`), wired into a fast single-pass multimodal client with self-UI filtering and crash-proof action parsing.

### Proposed Stage P1 Stints (To Be Planned One by One via `/plan`)

1. **Stint P1.1 — Persistent `llama-server` Supervisor & GPU Memory Governance**
   - Acquire/configure `llama-server.exe` (CUDA 12 build) and `UI-TARS-1.5-7B` GGUF + `mmproj` weights in `models/` (sized to ~4.8–5.3 GB total VRAM on Windows 10 RTX 4060).
   - Implement `LlamaServerBackend` & persistent daemon lifecycle in `parasite_ai/mind/brain_manager.py` (attaching to an already-running `127.0.0.1:8080` `/health` server across benchmark subprocesses so per-task cold start drops to **0ms**).
   - Verify live VRAM footprint and zero WDDM PCIe spillover using `scripts/check_gpu_governance.py`.

2. **Stint P1.2 — Multimodal CUA Client & Crash-Proof `UI-TARS` Action Parser**
   - Implement OpenAI-compatible multimodal `/v1/chat/completions` vision payload formatting (downscaled desktop screenshot + prompt/history) in `LlamaServerBackend`.
   - Build `parasite_ai/mind/uitars_parser.py` translating native UI-TARS outputs (`Thought: ... Action: click(start_box='(x,y)')`, `type(content='...')`, `hotkey(key='...')`, `finished()`) and normalized `1000x1000` / pixel coordinates into `ActionPlan` with hybrid UIA coordinate snapping (`vlm_grounder.py`).
   - Add defensive verb normalization (`SELECT` / `SELECT MenuItem` -> `CLICK`) and fallback `WAIT` recovery so malformed LLM tokens never raise an unhandled Pydantic `ValidationError`.

3. **Stint P1.3 — Single-Pass CUA Execution Path, Self-UI Filtering & App Disambiguation**
   - Decouple Pass 1 Persona monologue from the critical step loop: extract `Thought:` directly from the single-pass UI-TARS response for `CompanionDock` speech/thought display, cutting LLM calls per step from **2 to 1** (targeting median step latency **`<= 5.0s`**).
   - Update `ScreenGrounder.ground()` (`parasite_ai/vision/grounding.py`) to exclude ParasiteAI's own PID (`os.getpid()`) and overlay windows so the agent never clicks its own `CompanionDock`.
   - Harden system app launch disambiguation so `"Open Notepad"` resolves to Windows `notepad.exe` (not `notepad++.exe`) and `"Open Paint"` resolves to `mspaint.exe` (not `paintdotnet.exe`).

4. **Stint P1.4 — Stage P1 Benchmark Validation (`stage_p1` vs `baseline_p0`)**
   - Create `run_baseline_p1.bat` (pre-warming `llama-server` before launching `benchmarks.run_benchmark --output-name stage_p1 --resume --max-steps-cap 5`).
   - Execute the 20-task Windows 10 benchmark suite and compare `stage_p1.md` against `baseline_p0.md` on L1/L2 pass rates, False-DONE rate, cold-start timeouts (target: `0`), and median step latency (target: `<= 5.0s`).

---

## 5. Key Repository Reference Index

| File Path | Role |
| :--- | :--- |
| `C:\ParasiteAI\.agents\rules\strict_stint_cadence.md` | **Mandatory Workspace Rule:** 1 stint per turn, plan approval gate, post-stint walkthrough gate. |
| `C:\ParasiteAI\PROJECT.md` | Canonical architecture, Decisions D1–D6, Stage P0–P4 roadmap, and subsystem contracts. |
| `C:\ParasiteAI\GATE_STATUS.md` | Official Stage P0 stint audit & `baseline_p0` scorecard vs. Alpha Gate targets. |
| `C:\ParasiteAI\benchmarks\results\baseline_p0.md` | Human-readable 20-task Stage P0 empirical baseline report. |
| `C:\ParasiteAI\benchmarks\results\baseline_p0.json` | Full JSON telemetry & per-task failure modes for `baseline_p0`. |
| `C:\ParasiteAI\benchmarks\suite.yaml` | 20-task Windows 10 benchmark suite definition (v1.1). |
| `C:\ParasiteAI\benchmarks\verifiers.py` | 7 pre-task setup hooks & 12 live Windows 10 OS ground-truth verifiers. |
| `C:\ParasiteAI\benchmarks\run_benchmark.py` | Hands-off benchmark runner with pre-flight sandbox guard, `--resume`, and `--max-steps-cap`. |
| `C:\ParasiteAI\scripts\check_gpu_governance.py` | RTX 4060 VRAM ceiling (`6500 MB`) and Windows 10 WDDM spillover governance script. |
| `C:\ParasiteAI\parasite_ai\mind\brain_manager.py` | Local model manager (target for `LlamaServerBackend` in Stint P1.1). |
| `C:\ParasiteAI\parasite_ai\mind\dual_mind.py` | Cognitive pipeline & `ActionDispatcher` (target for single-pass CUA path in P1.2–P1.3). |
| `C:\ParasiteAI\parasite_ai\vision\grounding.py` | UIA + RapidOCR screen grounder (target for self-PID exclusion in P1.3). |

---

## 6. Ready-to-Paste New Session Bootstrap Prompt (Stage P1)

Copy and paste the exact block below into a new chat session to start Stage P1 planning immediately:

```markdown
Hello Antigravity. We are starting Stage P1 of ParasiteAI on Windows 10.

Please read the following files first to load our complete context, architectural invariants (D1-D6), and empirical Stage P0 baseline findings:
1. `C:\ParasiteAI\.agents\rules\strict_stint_cadence.md`
2. `C:\ParasiteAI\HANDOFF.md`
3. `C:\ParasiteAI\PROJECT.md`
4. `C:\ParasiteAI\GATE_STATUS.md`
5. `C:\ParasiteAI\benchmarks\results\baseline_p0.md`

Key Context Summary:
- Host: Windows 10 (64-bit), NVIDIA GeForce RTX 4060 (8,188 MiB VRAM; ~5,700-6,300 MiB free after Windows 10 desktop compositing; 6,500 MB ceiling).
- Stage P0 is 100% complete (`baseline_p0` scored 5.0% [1/20] pass rate, 20.0% [4/20] False-DONE rate, 5.986s median step latency, and 5 subprocess cold-start timeouts).
- Strictly follow `.agents/rules/strict_stint_cadence.md` (one stint at a time, plan approval gate before any code changes, result-oriented OS verification).

Let's begin with `/plan p1.1` (Persistent `llama-server` Supervisor, `UI-TARS-1.5-7B` Model Provisioning & GPU Memory Governance).
```
