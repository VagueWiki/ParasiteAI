# ParasiteAI — Master Session Handoff & Architecture Blueprint
**Generated:** 2026-11-01  
**Project Workspace:** `C:\ParasiteAI`  
**Current Status:** Phase 1, Phase 2, Phase 3, & Phase 4 **100% Complete & Certified** (2,178 / 2,178 Tests Passing)  
**Next Objective:** Phase 5 (Tiered Persistent Memory Engine & Verified Routine Replay)

---

## 1. Executive Summary & Core Identity

**ParasiteAI** is a **100% visible, desktop-native local AI assistant** that lives on the physical Windows desktop and operates applications via natural, human-like mouse and keyboard kinematics (Bézier curves, Min-Jerk velocity profile, micro-jitter).

### Strict Architectural Invariants
1. **Physical Safety & Human Preemption:** Low-level Win32 hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) provide **sub-2ms hardware touch preemption**. If the human user moves the mouse or presses a key, ParasiteAI aborts immediately.
2. **Instant Hard Kill (`Ctrl+Alt+K`):** Non-blocking native hard process termination (`taskkill /F /T /PID` + `os._exit(1)`) guarantees instantaneous termination (<5ms) without hanging in frozen GUI loops.
3. **Strict Anti-Hardcoding Rule:** Absolutely no application-specific branching or hardcoded lookup tables (`app_map = {"notepad": ...}` has been completely eliminated). The engine must handle arbitrary Windows applications generically.
4. **VRAM Ceiling:** Total local model consumption is strictly capped under **3.5 GB VRAM** on the 8 GB RTX 4060, leaving >4.5 GB free.
5. **Zero Silent Cloud Exfiltration:** The system defaults to local offline inference (`brain.mode: "local_llm"`). Web offload to Gemini is strictly an optional, user-authorized strategic consultation advisor, never an unrequested runtime dependency.

---

## 2. Hardware Profile & Live Empirical Geometry

* **OS:** Windows 11 64-bit
* **GPU:** NVIDIA GeForce RTX 4060 (8,187 MiB VRAM, driver CUDA 12 compliant)
* **RAM:** 16 GB System Memory
* **Display Configuration:** Dual-Monitor Side-by-Side (`3840×1080` total virtual desktop at 100% DPI, 96 DPI):
  * **Monitor 1 (Primary):** Bounds `(0, 0, 1920, 1080)`
  * **Monitor 2 (Secondary):** Bounds `(1920, 0, 3840, 1080)`
  * *Important Rule:* All coordinate math and screen capture fallbacks must query `get_virtual_screen_bounds()` dynamically (`SM_CXVIRTUALSCREEN = 3840`) so Monitor 2 targets ($x \ge 1920$) are never clipped or zeroed.
* **Environment:** Python 3.12 managed with `uv` in `C:\ParasiteAI\.venv`.
  * *Command Execution Note:* Always run Python/Pytest commands with `Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" ...`.
  * *CUDA DLLs Note:* Must call `parasite_ai.mind.brain_manager._register_cuda_dll_directories()` before importing `llama_cpp`.

---

## 3. Certified Deliverables & Completed Milestones

### Phase 1: Core Remediation & Foundational Safety (100% Certified)
* [x] **Decoupled Local Brain Mode:** `LocalBrainManager` retains `local_llm` mode without silently falling back to Chrome web offload on local errors.
* [x] **Fast Clipboard Typing:** Replaced character-by-character Unicode key typing with high-speed `<100ms` `Ctrl+V` paste accompanied by atomic user clipboard backup and restoration.
* [x] **Debounced Panic Slam:** Added 1.0s edge-triggered debouncing on screen corner mouse slams to eliminate Qt event loop queue flooding.
* [x] **Emergency Hard Termination (`Ctrl+Alt+K`):** Implemented clean non-blocking subprocess termination.
* [x] **`LivingPlan` Pydantic Schemas:** Created `parasite_ai/mind/plan.py` defining `StepIntent`, `StepStatus`, `PlanStep`, and `LivingPlan`.
* [x] **Project Changelog:** Initialized `C:\ParasiteAI\CHANGELOG.md` adhering to Keep a Changelog v1.0.0.

### Phase 2: Foveated Perception & Universal App Resolution (100% Certified)
* [x] **Foveated Perception Engine (`parasite_ai/vision/foveated.py`):**
  * Captures 1:1 unscaled native pixel crops around cursor/active focus windows alongside downscaled macro glances.
  * Employs 64-bit `dHash` perceptual difference gating (0% GPU/CPU overhead when desktop is static).
  * Bidirectional coordinate transforms between foveal/macro crops and global desktop coordinates.
* [x] **Universal Application Resolver (`parasite_ai/mind/resolver.py`):**
  * Completely eliminated the hardcoded `app_map = {"notepad": ...}` dictionary from `dual_mind.py`.
  * Generic regex target extraction (`open|launch|start|run <app>`).
  * Three-Tier Resolution: Tier 1 (Visible Desktop/Taskbar icons via Set-of-Mark) $\rightarrow$ Tier 2 (Windows Start Search chord `Win` $\rightarrow$ type name $\rightarrow$ `Enter`) $\rightarrow$ Tier 3 (`Win+R` Run dialog fallback).
* [x] **Multimodal Visual Grounder (`parasite_ai/vision/vlm_grounder.py`):**
  * Parses Qwen2.5-VL box tags, point coordinates, and JSON schemas.
  * Implements **Hybrid Coordinate Snapping** to the nearest UI Automation element center within 35px.
* [x] **Dynamic Living Plan Runtime (`parasite_ai/mind/dual_mind.py`):**
  * `DualMindPipeline.step()` maintains active multi-stage plan progress.
  * Intercepts unexpected modal dialogs (*Save changes, Error alerts*) and injects `DISMISS_DIALOG` contingency steps.
* [x] **Default Configuration:** `config.yaml` defaults to `brain.mode: "local_llm"`.
* [x] **Full Regression Pass:** **797 / 797 tests passing (100% green)** in 128.83s.

### Phase 3: Execution Loop Hardening (100% Certified)
* [x] **3A — Localized ROI Diffing (`parasite_ai/mind/dual_mind.py`):**
  * Implemented immutable `BoundingBox` model with `.pad(padding_px=20)` and multi-monitor virtual screen bounds clamping (`3840x1080 @ 100% DPI`).
  * Scoped post-action visual difference verification to the padded action bounding box (`extract_action_target_roi()`), eliminating false negative strikes on small UI elements while rejecting peripheral background and taskbar noise.
* [x] **3B — Win32 Caret Focus Verification (`parasite_ai/mind/dual_mind.py`):**
  * Defined 64-bit authentic Win32 `GUITHREADINFO` ctypes struct (72 bytes on x64) and helper `check_caret_focus` verifying `(flags & GUI_CARETBLINKING) or (hwndCaret != 0)`.
  * Integrated `verify_caret_focus` in `ActionDispatcher.dispatch()` before emitting `ActionType.TYPE` with a 250ms polling loop (checked every 25ms). If caret focus is unacquired, returns `ActionResult(success=False, error="Caret focus not detected")` without injecting blind keystrokes into unfocused surfaces.
* [x] **3C — Start Search Cadence Buffer (`parasite_ai/mind/resolver.py`):**
  * Enforced a 250ms cadence pause in `UniversalAppResolver` post-`Win` key chord before typing target application names, preventing dropped keystrokes while the Windows Search UI initializes.
  * Cadence wait loop checks hardware preemption cancellation token every millisecond.
  * Preserved strict anti-hardcoding invariant (zero application dictionaries or hardcoded lookup tables).
* [x] **3D — Full Regression & Adversarial Certification:**
  * **877 / 877 tests passing (100% green)** in 131.97s (`uv run pytest`), with 80 new tests added (+32 Phase 3 unit tests + 48 adversarial stress tests).
  * Independent Victory Audit confirmed `VICTORY CONFIRMED`. Sub-2ms preemption, `Ctrl+Alt+K` hard kill, and dual-monitor topology strictly verified.

### Phase 4: Strategic Gemini Consultation & Dynamic Contingencies (100% Certified)
* [x] **4A — Capability Contract & Textual Scene Serialization (`parasite_ai/mind/plan.py`):**
  * Implemented `GroundedCapabilityContract`, `build_grounded_capability_manifest()`, `serialize_textual_scene_brief()`, and consultation prompt formatters.
  * Formatted Set-of-Mark and active window telemetry strictly <3 KB payload without video streaming.
  * Enforced `BrainConfig.mode = "local_llm"` default invariant (zero silent cloud exfiltration).
* [x] **4B — 4-Tier Escalation State Machine (`parasite_ai/mind/memory.py`, `parasite_ai/mind/dual_mind.py`):**
  * Implemented `EscalationStateMachine` and `CadenceTier` (`TIER_1_LOCAL` -> `TIER_2_CONSULT` -> `TIER_3_GUIDED` -> `TIER_4_CO_PILOT` -> `USER_OVERRIDE`).
  * Action-aware strike evaluation: passive actions (`WAIT`, `DONE`) and clean CLI returncode 0 never incur visual strikes; interactive actions require physical success and localized ROI diff >= 0.02.
  * Finite cycle boundary (`max_escalation_cycles = 3`) and advisor timeout protection (`max_consultation_failures = 2`).
* [x] **4C — Dual-Channel Output Router & Persona Voice (`parasite_ai/mind/dual_mind.py`):**
  * Implemented `DualChannelRouter` in `parasite_ai/mind/dual_mind.py`.
  * Channel A extracts structured `LivingPlan` JSON (supporting both `'steps'` and `'recommended_strategy'`).
  * Channel B multi-pattern regex strips all code blocks, raw JSON braces, backticks, coordinate pairs (including float/decimal tuples), and API error codes before delivery to `UIBridge.notify_speech()`.
* [x] **4D — Tool-Aware Reasoning & CLI Execution Sandbox (`parasite_ai/mind/affordance.py`):**
  * Implemented `AffordanceEvaluator` routing between `PHYSICAL_GUI`, `LOCAL_DEVELOPER_TOOL`, and `STRATEGIC_ADVISOR`.
  * Implemented `CLIExecutionSandbox` with binary whitelisting (`python`, `pytest`, `git`, `powershell`, `cmd`), explicit web scraping tool rejection (`curl`, `requests`, `playwright`, `selenium`), 30s timeout, 10ms cancellation polling, and child-first recursive `taskkill /F /T /PID` in <20ms.
* [x] **4E — UniversalAppResolver Hardening (`parasite_ai/mind/resolver.py`):**
  * Implemented `PrecisionAppMatcher`: exact match (1.0), negative verb disqualification (`exit`, `close`, `uninstall`, `delete`, `kill`), prefix boundary matching (0.95), word-boundary regex scoring (0.80..0.90), and arbitrary substring rejection (eliminating 270+ collision attacks).
  * Hardened `UniversalAppResolver` with 3-tier launching (Tier 1: SOM Match -> Tier 2: Start Search chord -> Tier 3: Win+R fallback -> `WAIT` exhaustion), non-blocking cadence waits, attached punctuation delimiter parsing, and defensive `None` guards.
  * Implemented `verify_step_completion()` across all 8 `StepIntent` types and dynamic contingency branching (`insert_caret_contingency`, `insert_stagnation_contingency`, `insert_modal_dialog_contingency`) in `parasite_ai/mind/plan.py`.
* [x] **4F — Win32 64-bit ABI Structs & Full System Integration (`parasite_ai/input/types.py`, `tests/test_schema_mapping.py`):**
  * Verified all 10 Win32 ctypes structures matching 64-bit Windows ABI memory layouts (`POINT`=8, `RECT`=16, `MSLLHOOKSTRUCT`=32, `KBDLLHOOKSTRUCT`=24, `MOUSEINPUT`=32, `KEYBDINPUT`=24, `HARDWAREINPUT`=8, `INPUT_UNION`=32, `INPUT`=40, `GUITHREADINFO`=72).
  * Added polish for trailing non-word symbols in non-prefix positions (`notepad++`, `c++`, `c#`), attached natural language punctuation parsing, and dynamic contingency pointer advancement.
  * **2,178 / 2,178 tests passing (100% green)** in 152.47s. Independent Victory Audit confirmed `VICTORY CONFIRMED`.

---

## 4. Master Architectural Roadmap (Phase 4 through Phase 5)

```mermaid
flowchart TD
    subgraph P1_P4 ["Phases 1, 2, 3, & 4 (100% COMPLETE & CERTIFIED)"]
        F1["Safety & Hard Kill (Ctrl+Alt+K)"]
        F2["Foveated Perception & dHash Gating"]
        F3["Universal App Resolver (Anti-Hardcoding)"]
        F4["VLM Grounder with Hybrid Snapping"]
        F5["Localized ROI Diffing & Win32 Caret Focus"]
        F6["Grounded Capability Contract & Scene Serialization"]
        F7["4-Tier Escalation State Machine (T1->T2->T3->T4)"]
        F8["Dual-Channel Output (LivingPlan vs Persona)"]
        F9["Tool-Aware Reasoning & Hardened CLI Sandbox"]
        F10["PrecisionAppMatcher & 3-Tier Resolver"]
        F11["64-bit Win32 ABI Structs & Dynamic Contingencies"]
    end

    subgraph P5 ["Phase 5: Tiered Persistent Memory Engine (NEXT OBJECTIVE)"]
        P5A["5A: SQLite WAL Procedural Store (~/.parasite/memory.sqlite)"]
        P5B["5B: Verified Routine Caching (Fast Workflow Replay)"]
        P5C["5C: Multi-App E2E Test Suite (Notepad, Calc, Paint, Discord)"]
    end

    P1_P4 --> P5
```

### Phase 3 Technical Specifications (Next Up)
1. **3A — Localized ROI Diffing:**
   * *Problem:* Full-screen pixel difference checks generate false positives from system tray clocks or background notifications.
   * *Solution:* In `parasite_ai/mind/dual_mind.py`, scope post-action visual verification to `target_bbox.pad(20px)` rather than full desktop.
2. **3B — Win32 Caret Focus Verification:**
   * *Problem:* Clicking an input field might visually appear successful, but the application may not have focus to receive keystrokes.
   * *Solution:* Call `win32gui.GetGUIThreadInfo` / `user32.GetGUIThreadInfo` to verify `flags & GUI_CARETBLINKING` or `hwndCaret != 0` before emitting `TYPE` actions.
3. **3C — Start Search Cadence Buffer:**
   * *Problem:* Typing immediately after the `Win` key can drop initial characters if Windows Search indexer UI has not initialized.
   * *Solution:* Ensure a 250ms cadence pause is respected in `UniversalAppResolver` before typing.

---

## 5. Key File Index

| File Path | Description |
| :--- | :--- |
| `C:\ParasiteAI\config.yaml` | Master configuration (`brain.mode: "local_llm"` default). |
| `C:\ParasiteAI\launch_parasite.bat` | Windows batch launcher running `uv run python main.py %*`. |
| `C:\ParasiteAI\CHANGELOG.md` | Formal project changelog adhering to Keep a Changelog. |
| `C:\ParasiteAI\parasite_ai\mind\dual_mind.py` | Core dual-mind orchestrator (PersonaEngine + ActionDispatcher). |
| `C:\ParasiteAI\parasite_ai\mind\resolver.py` | Generic 3-tier application launcher and UI resolver. |
| `C:\ParasiteAI\parasite_ai\mind\plan.py` | `LivingPlan`, `PlanStep`, and consultation schemas. |
| `C:\ParasiteAI\parasite_ai\vision\foveated.py` | 1:1 cursor foveal crop and 64-bit `dHash` change gating. |
| `C:\ParasiteAI\parasite_ai\vision\vlm_grounder.py` | Qwen2.5-VL bounding box parser and coordinate snapper. |
| `C:\ParasiteAI\parasite_ai\vision\capture.py` | MSS/PIL screen capturer with multi-monitor virtual bounds. |
| `C:\ParasiteAI\parasite_ai\safety\panic.py` | Debounced corner slam and panic hotkey coordinator. |
| `C:\ParasiteAI\parasite_ai\safety\interrupt_guard.py` | Low-level Win32 hardware touch preemption (<2ms). |

---

## 6. Ready-to-Paste New Chat Bootstrap Prompt

Copy and paste the exact block below into the new chat window to immediately resume with complete alignment:

```markdown
Hello Antigravity. I am resuming work on ParasiteAI.

Please review our master handoff document at:
C:\ParasiteAI\HANDOFF.md (and the architectural blueprint in the artifact directory).

Key Context Summary:
1. Workspace: C:\ParasiteAI (Python 3.12 via uv on Windows 11).
2. Hardware: RTX 4060 (8 GB VRAM), Dual-Monitor (3840x1080 @ 100% DPI).
3. Status: Phase 1, Phase 2, & Phase 3 are 100% COMPLETE & CERTIFIED (877 / 877 tests passing).
4. Safety & Invariants: Sub-2ms touch preemption, Ctrl+Alt+K hard kill, brain.mode: "local_llm", strict anti-hardcoding rule (no app-specific branching).
5. Immediate Task: Proceed directly to Phase 4:
   - 4A: Structured Brief Formatter & Balanced-Brace JSON Parser for strategic consultation.
   - 4B: Real-time dynamic contingency branching in DualMindPipeline.

Please confirm you have read the handoff file, verify test suite status, and outline your execution steps for Phase 4.
```
