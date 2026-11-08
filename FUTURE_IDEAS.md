# ParasiteAI — Future Ideas & Architectural Roadmap

This document serves as the permanent, persistent repository for product ideas, architectural innovations, and user-suggested improvements. It lives directly in the root of the project repository so that ideas are never lost across chat sessions or agent context resets.

---

## 1. High-Priority Insights & Discoveries (Recent)

### 1.1 Memory Freshness, Routine Drift & Adaptive Optimization
* **The Problem:** Once ParasiteAI records or commits a sequence of steps to procedural memory (Phase 5), applications can update, desktop shortcuts can move or disappear, or UI layouts can drift. Even if an old routine still "works," blindly replaying a 10-step sequence when a 1-step direct shortcut is sitting on the desktop is inefficient.
* **The Solution — Dual-Track Exploration & Verification:**
  * **Pre-Flight Shortcut Check:** Before executing an expensive procedural routine (e.g., launching an app via Start Search or Run dialog), always scan the visible screen / desktop for direct affordances (running taskbar window, desktop shortcut icon).
  * **Drift & Invalidation Triggers:** Track success rates and visual delta signatures for cached routines. If anchor elements are missing or intermediate steps produce zero visual diff, automatically mark the routine as *Stale / Needs Re-Grounding*.
  * **Opportunistic Optimization (Exploration vs. Exploitation):** Occasionally benchmark alternative launch vectors (e.g., direct desktop click vs. Start Search vs. Win+R) and update the cached routine with the lowest-latency, lowest-step path.

### 1.2 Perception Bottleneck: Full-Screen Grounding vs. Top-30 Truncation
* **The Problem:** In empirical tests (e.g., launching RimWorld), the bot searched through the Start menu instead of clicking an already-visible desktop shortcut.
* **Root Cause Analysis:**
  1. `ScreenGrounder` prioritizes active window controls first.
  2. `brain_manager.py:generate_action` caps elements to the top 30 to stay within small local LLM context limits.
  3. Active window controls consume all 30 slots, completely cutting off desktop icons from Pass 2's sight.
  4. Pass 1 persona monologue only receives a summary count (`Background/Desktop Targets: 40 other items detected`) without their labels.
* **Proposed Solution — Goal-Aware Semantic Slicing:**
  * When the user goal mentions an application or document name, prioritize matching items in the Set-of-Mark list regardless of whether they reside in the active window or the desktop background.
  * Implement two-tier grounding: a lightweight high-level application/shortcut index across all visible windows/desktop, and a detailed control tree only for the target area.

### 1.3 Menu Oscillation Loop Detection (The "More" Button Phenomenon)
* **The Problem:** While searching for an app, the bot clicked target `#5` ("More" button in Windows Search), which opened a popup menu (`Screen Diff: 20.1%`). The escalation engine counted this as a "SUCCESS", then the bot clicked `#5` again to close it (`Screen Diff: 23.7%`), oscillating indefinitely without progressing toward the goal.
* **Proposed Solution — Semantic Progress Gating:**
  * Visual diff alone must not constitute "progress" if the agent is oscillating between binary toggle states on the exact same target element.
  * Add an action cycle detector: if the same element is clicked 2+ times in succession without advancing the active plan step intent, trigger a soft strike or cycle break.

### 1.4 Icon & Graphic Semantic Recognition for Unlabeled Controls
* **The Problem:** Many modern application and web UIs use icon-only buttons (gear icons, hamburger menus, navigation arrows, close buttons) that lack Win32 accessibility text and contain no OCR text. These appear in the prompt as `[#ID] Button (no label)` or are filtered out entirely, forcing the LLM to guess what to click based solely on coordinate positions.
* **Proposed Solution — Local Visual Grounding:**
  * Integrate a lightweight local icon detector/captioner (e.g., OmniParser-style icon classifier or small vision encoder).
  * Crop bounding boxes of unlabeled interactive controls and pass them to a local vision model to attach semantic labels (e.g., `"Settings Gear"`, `"Navigation Hamburger Menu"`, `"Close Window"`).

### 1.5 Spatial-Density OCR Triggering (Window Chrome Fallback Bypass)
* **The Problem:** In hybrid perception mode, OCR fallback is skipped as soon as Tier 1 (Win32 UI Automation) detects 6 or more controls (`_min_uia_threshold = 6`). Standard window chrome alone (Minimize, Maximize, Close, Title bar, Menu bar, Address bar, Tabs) easily accounts for 6+ elements. If the actual application workspace (e.g., a canvas, PDF viewer, game window, or remote desktop) has zero accessibility nodes, OCR is never triggered.
* **Proposed Solution — Spatial Coverage Gating:**
  * Transition from a flat element-count threshold to spatial density/coverage gating.
  * Evaluate whether large geometric regions of the active window's interior canvas contain zero UIA elements, and trigger scoped OCR specifically over those unmapped bounding areas.

### 1.6 Active Window Metadata & Spatial Hierarchy in SoM Prompt
* **The Problem:** The Set-of-Mark list provided to Pass 1 and Pass 2 is a flattened 1D array of coordinates. It lacks the active window title and process name in the summary header, leaving the LLM without high-level context of what software it is interacting with unless it infers it from button labels.
* **Proposed Solution — Structured Scene Context:**
  * Prepend active foreground window metadata directly to the Set-of-Mark header (e.g., `Active Window: "Untitled - Notepad" [notepad.exe]`).
  * Group elements by functional screen regions (Header / Navigation, Main Content Area, Sidebar, Footer / Status bar) so the LLM understands structural relationships rather than just raw `(x, y)` coordinates.

### 1.7 Localized Target-BBox Diff Verification & Dynamic Settle Latency
* **The Problem:**
  1. The fixed 50ms settle delay before taking the post-action verification screenshot is too brief for heavier web pages or desktop apps that take 200–500ms to render.
  2. The 2% whole-screen diff threshold means subtle but successful UI changes (like toggling a checkbox, focusing a text box, or opening a small combobox) register as `< 2%` of a 1080p/4K display, triggering false failure strikes and premature panic loops.
* **Proposed Solution — Context-Aware Visual Verification:**
  * **Dynamic Settle Wait:** Allow configurable or action-dependent settle delays before taking the post-action screenshot based on application type.
  * **Localized Diff Inspection:** Evaluate pixel change ratios specifically within and immediately around the clicked target's bounding box (`bbox`), rather than requiring a 2% change across the entire monitor.

---

## 2. Flagship Product Pillars (Vision Blueprint)

### Pillar 1: Symbiotic Human-AI Control
* **Sub-2ms "Touch & Resume" Handshake:** The instant the user touches their mouse or keyboard, ParasiteAI yields control in under 2ms. Once idle, it seamlessly highlights what changed and resumes.
* **Holographic Ghost HUD & Predictive Reticle:** Transparent click-through HUD projecting numbered Set-of-Mark target boxes and a 300ms pre-action targeting reticle.
* **"Ghost Desk" (Background Multi-Desktop Execution):** Leveraging Windows Virtual Desktops (`IVirtualDesktopManager`) so ParasiteAI works on an isolated virtual desktop without monopolizing the physical screen.
* **Risk-Tiered Consent Gate:** Green (Read/Scroll), Yellow (Edit/Type), Red (Delete/Send/Execute). Red actions require one-click user authorization.

### Pillar 2: "Watch & Learn" Procedural Routines (No-Code RPA)
* **Demonstration-to-Skill Macro Synthesizer ("Shadow Learner"):** User clicks "Watch Me", performs a repetitive workflow, and ParasiteAI compiles it into an executable, parameterized `LivingRoutine`.
* **Self-Healing Grounding Engine:** Multimodal semantic grounding (Qwen2.5-VL + OCR + UI Automation) so updated buttons and changed themes don't break stored routines.
* **Data-Driven Batch Execution:** Execute a routine across 500 rows of an Excel spreadsheet or CSV.

### Pillar 3: Sovereign Security & Enterprise Air-Gap Compliance
* **100% Local Sovereign Brain:** Fully functional offline within 3.5 GB VRAM on consumer GPUs (e.g. RTX 4060). Zero cloud telemetry.
* **Dynamic "Red Zone" Hardware Shielding:** Automatic blur/masking over password managers, banking sites, and terminal credentials before vision frames reach memory.
* **Cryptographic "Black-Box" Flight Recorder:** Append-only SQLite WAL audit log of every action vector and visual diff with an interactive scrubber.

### Pillar 4: Multi-App Universal Workflow Engine
* **Cross-Ecosystem Orchestrator:** Drive workflows across legacy Win32, Qt, WPF, and modern web apps without APIs.
* **Real-Time Dynamic Contingency & Modal Interception:** Automatically detect and dismiss unexpected dialogs ("Save changes?", "Update available", "Network reconnecting").
* **Creative Tool & Non-Standard Canvas Manipulation:** Extending Min-Jerk Bézier curves and drag-and-drop primitives to manipulate visual interfaces where UI trees are sparse (node graphs in Blender/Unreal, timeline scrubbing in Premiere/DaVinci, drawing and slider adjustments in Photoshop, CAD, or Paint).

### Pillar 5: The Intelligent Companion Experience & Desktop Presence
* **Modern WinUI 3 / Glassmorphic Floating Dock:** Upgrading from raw PyQt6 to an ultra-sleek desktop dock featuring animated avatar states (`OBSERVING`, `THINKING`, `DRIVING`, `STUCK`), ambient goal progress meters, and real-time live monologue.
* **Push-to-Talk Local Voice Companion:** On-device Whisper speech-to-text paired with low-latency local TTS (Piper or Kokoro). Holding a hotkey (e.g., `Caps Lock`) enables natural spoken commands (*"Organize my downloads folder by project and date"*) with complete offline execution.
* **Companion Mobile App / Web Remote for Long Jobs:** A local end-to-end encrypted mobile companion. While Parasite runs a long multi-hour batch routine on your workstation, you receive push notifications upon completion and can remotely approve Yellow/Red actions from your phone.

---

## 3. Tool-Aware Reasoning & Meta-Tooling (GUI vs. CLI)

* **"Smartest Path" Affordance Engine:** Rather than treating Windows purely as a 2D canvas of clickable pixels, ParasiteAI evaluates whether a user goal is faster, cheaper, and safer to accomplish via:
  1. Direct sandboxed CLI execution (PowerShell commands, Python scripts, git commands),
  2. Physical mouse/keyboard GUI driving, or
  3. Strategic cognitive planning.
* **Sandboxed CLI Execution with Touch Preemption:** Command whitelisting, scraping prohibitions, 30s timeouts, and sub-10ms hardware touch preemption terminating the subprocess tree.

---

## 4. Cognitive Escalation Architecture & Protocols (Phase 4 Additions)

* **4-Tier Escalation State Machine:** Replaces binary aborts or flat strike counters with a structured 4-tier cadence:
  - *Tier 1:* Autonomous Local Exploration (up to 2 local strikes).
  - *Tier 2:* Deep Strategic Gemini Consultation (LivingPlan blueprint ingestion).
  - *Tier 3:* Guided Local Execution (up to 2 guided strikes using the blueprint).
  - *Tier 4:* Continuous Gemini Visual Co-Pilot handholding.
  - *Tier 5:* Clean yield to `USER_OVERRIDE` if permanently stuck.
* **Dual-Channel Output Separation:** Strict separation between:
  - **Channel A:** Internal machine-readable structured JSON feeding `LivingPlan`.
  - **Channel B:** Wholesome character monologue for the user, strictly sanitized so raw JSON, code blocks, or regex tokens never leak into the companion dock speech bubble.
* **Grounded Capability Contract:** Injected into external model prompts to enforce physical human actuator limits (no headless browser scrapers, no invisible DOM manipulation; only Bézier curves, clipboard pastes, and visible Set-of-Mark grounding).
* **Textual Scene Serialization Protocol:** Replacing bandwidth-heavy video streaming with ultra-compact (<3 KB) structured Set-of-Mark bounding box tables and active window briefs.

---

## 5. Tiered Persistent Memory & Routine Caching Engine (Phase 5 Additions)

* **SQLite WAL Procedural Store (`~/.parasite/memory.sqlite`):** Moving from in-memory ring buffers to an atomic, durable SQLite store with Write-Ahead Logging (WAL) to persist UI landmarks, learned routines, and user habits across PC restarts.
* **Deterministic Routine Caching & Fast Replay:** Bypassing LLM inference latency entirely for frequent, verified routines by replaying validated mouse/keyboard trajectories directly.
* **Multi-App E2E Certified Test Harness:** Automated test harness across standard Windows desktop applications (Notepad, Calculator, Paint, Discord, Browser).

---

## 6. Go-to-Market Packaging, Tiers & Native Distribution

* **Product Packaging Tiers:**
  - *Parasite Personal:* Local VLM inference, Companion Dock, Holographic Ghost HUD, Sub-2ms Touch Preemption, Universal App Launcher, 5 saved Routines. (Free / Open Core / One-Time License).
  - *Parasite Pro:* Unlimited "Watch & Learn" Routine Synthesizer, Ghost Desk background execution, Voice I/O, Mobile Remote, Advanced Batch Data Ingestion. ($15/mo or $149 lifetime).
  - *Parasite Enterprise:* Air-gapped offline compliance, Hardware Red Zone PII masks, Encrypted Flight Recorder DVR, Multi-Seat Central Policy Manager. ($50–$100 / seat / month).
* **Zero-Friction Windows Distribution:** Single-command installer (`winget install parasite-ai` or `.msi` single-click bundle) packaging the Python runtime, CUDA DLLs, and default quantized VLM without requiring developer setup.
