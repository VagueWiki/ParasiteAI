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

### 1.2 [SUPERSEDED — Stage P1/P2.7] Perception Bottleneck: Full-Screen Grounding vs. Top-30 Truncation
* **Status:** **SUPERSEDED & RETIRED.**
* **Historical Context:** In early 3B dual-pass Set-of-Mark prototypes, `ScreenGrounder` capped elements to the top 30 to fit within small local LLM context limits, truncating desktop icons.
* **Current Resolution:** Decommissioned in Stage P1 and P2.7. `UI-TARS-1.5-7B` operates on native 1080p frame captures ($1920 \times 1080$) in a single multimodal pass with 8,192-token context headroom, grounding both active windows and desktop targets visually without Set-of-Mark truncation.

### 1.3 Menu Oscillation Loop Detection (The "More" Button Phenomenon)
* **Status:** **ACTIVE — HIGH PRIORITY (Stage P3.1).**
* **The Problem:** While searching for an app, the bot clicked target `#5` ("More" button in Windows Search), which opened a popup menu (`Screen Diff: 20.1%`). The escalation engine counted this as a "SUCCESS", then the bot clicked `#5` again to close it (`Screen Diff: 23.7%`), oscillating indefinitely without progressing toward the goal. A similar loop was diagnosed in live probe `L1-01` (repeatedly opening and closing Notepad++ vs classic Notepad).
* **Proposed Solution — Semantic Progress & Spatial Radius Gating:**
  * Visual diff alone must not constitute "progress" if the agent is oscillating between binary toggle states on the exact same target element or alternating focus between two colliding apps.
  * Add an action cycle detector: if the same element or coordinate cluster ($r \le 24\text{px}$) is toggled 2+ times in succession without advancing the active sub-goal checklist, trigger a strategy shift, app disambiguation, or Tier 1 escalation.

### 1.4 [DROPPED / OBSOLETE] Icon & Graphic Semantic Recognition for Unlabeled Controls (OmniParser)
* **Status:** **DROPPED (Invariant D1 Violation).**
* **Resolution:** OmniParser v2 (YOLOv8 + PaddleOCR + Florence-2) requires ~10.8 GB VRAM, directly violating the **6,500 MB VRAM ceiling (Invariant D1)** on the host RTX 4060. Furthermore, `UI-TARS-1.5-7B` natively localizes unlabeled icons and standard chrome controls directly from the 1080p visual frame (empirically verified in live probe `L1-06` targeting the window close button at $(1369, 45)$).

### 1.5 [SUPERSEDED — Stage P1/P2.7] Spatial-Density OCR Triggering (Window Chrome Fallback Bypass)
* **Status:** **SUPERSEDED & RETIRED.**
* **Resolution:** In the single-pass multimodal architecture (`UI-TARS-1.5-7B`), the VLM directly parses text and canvas elements visually across the full 1080p display, eliminating reliance on heuristic UIA element count thresholds (`_min_uia_threshold = 6`) or CPU OCR fallback gating on interior canvases.

### 1.6 [IMPLEMENTED — Stage P2.6/P2.7] Active Window Metadata & Spatial Hierarchy in Working Memory
* **Status:** **IMPLEMENTED & CERTIFIED.**
* **Resolution:** Implemented via `RuntimeGoalVerifier.build_working_memory_snapshot()`, which queries live Win32 window handles in $<3\text{ms}$ on CPU (0 MB added VRAM) and injects active window titles, process names, and exact physical screen bounding boxes `[Bounds: x=..., y=..., w=..., h=...]` into the prefix-stable context prompt.

### 1.7 [IMPLEMENTED — Stage P2/Phase 4] Localized Target-BBox Diff Verification & Dynamic Settle Latency
* **Status:** **IMPLEMENTED & CERTIFIED.**
* **Resolution:** Implemented via `extract_action_target_roi()` (evaluating pixel diffs within padded action bounding boxes) and verified by `RuntimeGoalVerifier` objective OS state checks before accepting completion.

### 1.8 Temporal Action-Window Capture & Animation Filmstrips (Pixel Diff Delta Tracking)
* **The Problem:** A single static screenshot at $t=0$ gives the VLM zero awareness of animation transitions, loading spinners, state changes occurring during a click, or delayed UI reveals. However, continuously feeding raw video or dozens of full 1080p frames destroys the VLM token budget and balloons prompt evaluation latency.
* **Proposed Architecture — Fixed-Window Differential Filmstrips:**
  * **Event-Triggered Micro-Burst:** Immediately after a key action (mouse click or Enter submission), trigger a lightweight background CPU capture burst across a fixed window (e.g., $t+0\text{ms}, t+150\text{ms}, t+350\text{ms}, t+600\text{ms}$).
  * **Sub-5ms NumPy Pixel Diffing:** Compute pixel delta masks across the burst frames on the CPU at 0% GPU load. Identify the exact bounding box of motion/animation.
  * **Temporal Composite Filmstrip:** Instead of sending multiple full 1080p images to the VLM (which cost 2,691 tokens each), compose a single horizontal thumbnail filmstrip (`[Pre-Click] -> [Mid-Animation] -> [Post-Settle]`) or a delta motion heatmap into a single compact image ($\sim 600\text{ tokens}$).
  * **VLM Motion Understanding:** The VLM perceives cause-and-effect over time in a single inference turn without inflating context limits.

### 1.9 Hierarchical Layered Cognition for Games & Continuous Complex Simulation Under Budget
* **The Problem:** Complex interactive environments (e.g. strategy games like RimWorld/Factorio, simulators, CAD/Blender node graphs, video editors) require deep multi-step reasoning, spatial interpretation, and state awareness. A monolithic 7B VLM taking 4.5s per turn is both too slow for real-time dynamics and too computationally expensive to run continuously on an 8GB GPU.
* **Proposed Architecture — 3-Tier Asymmetric Cognitive Stack:**
  * **Layer 0: Peripheral Reflex Engine (CPU / OpenCV / Win32, 30–60 FPS, 0 VRAM, 0 Tokens):**
    * Optical flow, bounding box change detection, template matching for critical indicators (health bars, resource counters, minimap alerts, active dialog popups).
    * Filters out 90% of idle time; only notifies higher layers when meaningful state transitions occur.
  * **Layer 1: Tactical Visual Grounder (UI-TARS 7B Local VLM, ~2–4s Cadence, ~6 GB VRAM):**
    * Operates on cropped regions of interest (ROIs) or action filmstrips.
    * Decides immediate micro-actions: where to click, inventory sorting, selecting menu items, or dismissing game prompts.
  * **Layer 2: Strategic Macro Planner (Stage P3 Strategic Escalation / Cloud VLM or Async Local LLM):**
    * High-level architectural reasoning: quest objectives, resource balancing, long-term build orders, or tool workflows.
    * Evaluates once every 30–60 seconds (or upon tactical deadlock) via ultra-compact symbolic state summaries, maintaining strict adherence to consumer hardware constraints.

### 1.10 Rapid Chained Micro-Actions & Per-App Spatial Landmark Memory
* **The Problem:** In 2D games, turn-based games, and fixed productivity interfaces (e.g. inventory grids, spell bars, dialog choices, calculator buttons, form inputs), UI elements are 100% stationary. Pausing 4.5 seconds for VLM inference between every single click makes multi-click operations (like moving 5 inventory items or typing an address) feel agonizingly slow and wastes GPU cycles.
* **Proposed Architecture — Chained Blind Bursts & Per-App Spatial Schemas:**
  * **Per-App Spatial Memory (`~/.parasite/app_profiles/<app_id>.json`):**
    * Stores learned, static screen landmarks relative to the app window bounds (e.g. `RimWorld`: `architect_button` at `(window.left + 45, window.bottom - 25)`, `inventory_slot_grid` at `(x_offset, y_offset, stride_x, stride_y)`).
    * When launching or switching to a known app, the agent instantly loads its cached spatial map into memory without requiring fresh vision recognition.
  * **Chained Blind Action Execution (Sub-50ms Burst Cadence):**
    * When an intention requires interacting with known static elements (e.g., "Haul items from slot A to slot B", or "Fill out standard form fields"), the model emits a compound action vector: `[click(loc_a), drag_to(loc_b), press_key('E')]`.
    * The driver executes the sequence in rapid succession (~50ms per action) without intermediate screenshot captures or VLM pauses.
  * **Optimistic Execution with Interrupt & Anomaly Guard:**
    * Full touch preemption (`InterruptGuard` < 2ms) remains active during the burst.
    * A verification screenshot is captured only *after* the entire burst completes, checking expected final state (e.g. via fast pixel diff or CPU verifier). If an unexpected dialog or miss occurs, it immediately drops back to single-step perception.

### 1.11 Autonomous Desktop "Skill" Synthesis & Context Retrieval (The Dynamic SKILL.md Playbook)
* **The Problem:** How does ParasiteAI learn from past successes and failures so it gets permanently smarter without expensive model fine-tuning or VRAM overhead?
* **Proposed Architecture — Markdown App Skills (`~/.parasite/skills/<app>/SKILL.md`):**
  * **Human-Readable & User-Editable Knowledge Files:**
    * Each application or game gets its own modular skill directory (e.g. `skills/rimworld/SKILL.md`, `skills/discord/SKILL.md`, `skills/blender/SKILL.md`).
    * Stores 4 distinct categories of learned expertise:
      1. *Spatial Landmarks:* Verified coordinates of static controls (e.g. "Inventory button is at (45, 1055)").
      2. *Hotkeys & Muscle Memory:* High-speed keyboard alternatives (e.g. "Space toggles pause", "Shift+Enter creates a newline without sending").
      3. *Anti-Patterns & Pitfalls Learned from Failures:* Mistakes to never repeat (e.g. "Do not click outside modal #32770 while saving; wait for spinner"). *Subject to Section 1.20 drift review and TTL decay to prevent stale rules.*
      4. *Proven Sub-Goal Recipes:* Multi-step micro sequences that have a 100% verified track record.
  * **Post-Episode Reflection Loop (Autonomous Learning):**
    * When a run finishes (or when a human corrects the agent), a lightweight reflection summarizer distills new learnings: *"What did we discover? What caused a strike? What resolved it?"*
    * Appends concise, high-signal rules directly to the app's `SKILL.md`.
  * **Dual Code-Readable + Legible English Architecture (YAML Frontmatter + Markdown):**
    * *Top Section (YAML Frontmatter):* Machine-readable dictionary parsed by Python in <1ms (`landmarks: {architect: [45, 1055]}`, `shortcuts: {pause: "Space"}`). Enables direct programmatic execution without LLM inference.
    * *Bottom Section (Markdown Prose):* Human-legible English strategy and rules injected directly into the VLM prompt context.
  * **Just-In-Time Context Injection (Zero Training, ~100 Tokens):**
    * When the active window switches to `notepad.exe` or `RimWorldWin64.exe`, the runtime automatically pulls only the matching `SKILL.md` and injects it into the prompt header.
    * Uses negligible token context (~100–150 tokens), consumes 0 MB extra VRAM, never suffers catastrophic forgetting, and can be edited or customized by the user at any time.

### 1.12 Windowed Sub-Resolution Play & Dynamic Window-Relative Coordinate Mapping
* **The Problem:** Running games or rich 2D applications in full-screen 1080p or 4K forces the VLM to process 2.07M–8.3M pixels per turn, burning 2,690+ tokens and inflating prompt evaluation latency to 2.2s–6.0s.
* **The Solution — Windowed Sub-Resolution Execution:**
  * **Intentionally Lowering Application Resolution:** As an initialization step for supported games/apps, ParasiteAI sets or configures the target window to run in a compact windowed mode (e.g. $1280 \times 720$ or $960 \times 540$).
  * **Scattered Token Reduction:** Capturing only a $960 \times 540$ window shrinks image area to $518,400\text{ px}$—slashing vision tokens to **only $\sim 650\text{ tokens}$** and cutting prompt evaluation time to **$< 0.6\text{ seconds}$**!
  * **Offset-Invariant Coordinate Translation (Handling Moving/Floating Windows — Rule 8 Compliant):**
    * If the game window moves or is dragged around the virtual desktop, pixel locations do not break.
    * The capture engine crops strictly to the client rectangle via Win32 `GetClientRect(hwnd)` and `ClientToScreen(hwnd)`.
    * Per **Engineering Cadence Rule 8 (Native Screen Pixel Contract)**, UI-TARS 1.5 outputs physical pixel coordinates $(x_{\text{crop}}, y_{\text{crop}})$ directly within the crop's coordinate space $[0..W_{\text{crop}}-1, 0..H_{\text{crop}}-1]$, eliminating arithmetic normalization division distortion.
    * The dispatcher resolves global desktop mouse coordinates instantaneously via exact integer translation:
      $$X_{\text{screen}} = W_{\text{left}} + x_{\text{crop}}$$
      $$Y_{\text{screen}} = W_{\text{top}} + y_{\text{crop}}$$
    * Where $(W_{\text{left}}, W_{\text{top}}, W_{\text{width}}, W_{\text{height}})$ is queried live from Win32 `GetWindowRect(hwnd)` in $< 0.05\text{ms}$ at the exact millisecond of click dispatch.
    * **Zero Drift Guarantee:** The window can be resized, dragged to another monitor, or shifted across the desktop; the click lands with 100% millimeter accuracy inside the window.

### 1.13 Scale-Invariant Spatial Skills & Multi-Resolution Profiles
* **The Problem:** If a skill hardcodes raw physical pixel coordinates (e.g., `architect_menu: [45, 1055]` on a 1080p display), running the game at $1280 \times 720$ or $960 \times 540$ causes clicks to miss completely.
* **The Solution — Three Harmonized Spatial Portability Strategies:**
  1. **Normalized Coordinates ($[0..1000]$ or $[0.0..1.0]$):**
     * Instead of raw pixels, store coordinates normalized to the window dimensions:
       `architect_menu: [23, 976]` (representing $2.3\%$ width, $97.6\%$ height).
     * For games and apps with responsive or proportionally scaled UIs (Unity/Unreal canvas scalers, Qt, web apps), multiplying normalized coordinates by the live window dimensions ($W_w, W_h$) lands accurately at any resolution.
  2. **Corner/Edge Anchored Offsets (Game Engine Docking Anchors):**
     * In many 2D games, HUD elements don't stretch proportionally; they dock to screen edges with fixed pixel padding.
     * Skills support anchor notation:
       `minimap: {anchor: "top-right", offset: [-120, 20]}`
       `speed_pause: {anchor: "bottom-right", offset: [-140, -30]}`
       `architect_menu: {anchor: "bottom-left", offset: [45, -25]}`
     * Even if the window shrinks from 1080p to 540p, an anchor from the bottom-left corner remains 100% accurate.
  3. **Multi-Resolution Skill Profiles:**
     * For games where UI layouts rearrange fundamentally between aspect ratios or resolutions, `SKILL.md` frontmatter supports resolution-keyed profile blocks:
       ```yaml
       landmarks:
         "1920x1080":
           architect_menu: [45, 1055]
         "1280x720":
           architect_menu: [30, 703]
         "960x540":
           architect_menu: [23, 527]
         default:
           architect_menu: {anchor: "bottom-left", offset: [45, -25]}
       ```
     * Python queries the window's live resolution, selects the matching profile, and dispatches the action without any guessing.

### 1.14 Dynamic Resolution Switching & Contextual Research Escalation (Wiki/Advisor Modes)
* **The Problem:** The agent needs fast, low-token execution while playing a game or interacting with a compact app (e.g. $960 \times 540$ windowed mode at $\sim 650\text{ tokens}$), but occasionally needs high-resolution full-monitor vision to read complex text (e.g. opening a browser to look up a game wiki, reading detailed documentation, or asking Gemini an offload question).
* **The Solution — Context-Adaptive Vision Modes:**
  * **Dual Vision Pipeline (Micro-Gaming vs. Macro-Research):**
    * *Game / Task Mode (Window-Scoped):* When the active window is the target game/application, capture *only* the application's window rect at native/sub-resolution ($\sim 650\text{ tokens}$, $< 0.6\text{s}$ latency).
    * *Research Mode (Full-Monitor 1080p):* When the active window switches to a browser (`chrome.exe`, `msedge.exe`) or when the agent triggers an `OFFLOAD_WEB_AI` research sub-goal, dynamically switch capture to full $1920 \times 1080$. Full 1:1 pixel fidelity ensures small wiki text, tables, and browser tabs are completely legible.
  * **Primary Monitor Focus & Window Flipping:**
    * Keeps the user's secondary monitor completely free and uncluttered.
    * Both the game and the research browser reside on Monitor 1. ParasiteAI flips between them cleanly via `Alt+Tab`, taskbar clicking, or `SetForegroundWindow`.
    * When research is complete and committed to `SKILL.md`, the browser is minimized/dismissed, instantly returning the game window to focus.
  * **Monitor 2 Out-of-Bounds Auto-Relocation Guard:**
    * If an application, modal dialog, or new browser window accidentally spawns or opens on Monitor 2 ($X_{\text{bounds}} \ge 1920$):
    * The runtime detects the out-of-bounds window via `GetWindowRect(hwnd)` and automatically relocates it to Monitor 1 (using Win32 `SetWindowPos` or Windows hotkey `Win + Shift + Left`).
    * Guarantees all active agent processing, HUD projections, and user observations remain strictly centered on the primary display.
  * **Direct Skill Synthesis from Wiki / Gemini Research:**
    * When the agent reads a wiki page or asks Gemini for a crafting recipe (e.g., *"How do I craft solar panels in RimWorld?"*):
    * The research output is immediately distilled and committed directly into the game's `SKILL.md` (Section 1.11).
    * Once written to the skill file, the agent closes the browser, drops back into fast windowed sub-resolution mode, and executes the newly learned recipe with zero future research overhead.

### 1.15 Architectural Pivot: Decommissioning GhostHUD & CompanionDock in Favor of a Discord Bot Interface
* **Status:** **RATIFIED PROPOSAL (Post-Alpha / Stage P5 UX Architecture).**
* **The Core Problems with On-Screen Overlays (GhostHUD & CompanionDock):**
  1. *Visual Self-Occlusion:* A desktop overlay (even semi-transparent or click-through) physically occupies screen real estate. We already had to build complex evasion logic (`_evade_companion_dock_if_needed`) because the dock blocked bottom-right system tray icons and buttons.
  2. *Capture Contamination:* Transparent overlay reticles or dock speech bubbles risk being captured by the vision pipeline (`mss`), adding visual noise, triggering false pixel diffs, or confusing UI-TARS's grounding.
  3. *Local-Only Tether:* The user must be sitting directly in front of the physical workstation monitor to see the HUD or read the companion's thought stream.
  4. *Qt Event Loop Overhead:* Maintaining a 60 FPS PyQt6 rendering loop on top of full-screen games or productivity apps introduces needless compositing overhead and window-focus friction.
* **The New Architecture — Headless Local Agent + Discord Command & Control Bot:**
  * **Zero Screen Occlusion:** The host desktop remains 100% clean. No floating avatars, no reticle overlays, and zero self-occlusion evasions required.
  * **Remote Mobile & Desktop Control:** Control your PC from your phone, laptop, or another device through a private Discord server or DM channel:
    * Run tasks via slash commands: `/task goal:"Open Steam, start the RimWorld update, and let me know when it's done"`.
    * Streamlined task parameters: `/routine name:"morning_launch"`.
  * **Live Asynchronous Feed (Thought Stream & Snapshots):**
    * Parasite streams its in-character monologue (`Thought:`) into a Discord thread or message stream.
    * Automatically uploads compressed before/after screenshot embeds so you can visually verify progress from anywhere.
  * **Remote Intervention & One-Click Emergency Panic:**
    * If the agent encounters a strike or requests confirmation (Yellow/Red actions), it posts a Discord message with interactive buttons (`[Approve]`, `[Retry]`, `[Cancel]`).
    * Includes an instant emergency stop button or `/panic` command that triggers `InterruptGuard` within $<2\text{ms}$ over WebSocket.
  * **Resource Efficiency:** A `discord.py` / `nextcord` async daemon consumes $<25\text{ MB}$ of RAM and **0 MB of VRAM**, running entirely on the CPU without touching the GPU graphics pipeline.

### 1.16 Multimodal Visual Browser Offloading: Feeding Desktop Screenshots to Gemini via Clipboard Attachment
* **Status:** **RATIFIED PROPOSAL (Stage P4 / P5 Escalation Hardening).**
* **The Problem with Text-Only Browser Offloading:**
  * When local UI-TARS encounters tactical deadlock (e.g. 3 strikes), `BrowserOffloader` opens the web browser and pastes a pure text consultation prompt summarizing the goal and recent action failures.
  * However, text descriptions inherently lose spatial and visual grounding: a bizarre modal popup, an unusual application error, a game UI element, or subtle visual state changes (like a disabled button or greyed-out menu item) are difficult to summarize in text alone.
  * Gemini (via `gemini.google.com`) is a world-class multimodal vision model capable of directly inspecting high-resolution desktop frames.
* **The Solution — Physical Clipboard Image Attachment (0 MB VRAM, 0 Paid API Keys):**
  * **Freeze & Copy Pre-Escalation Screen State:**
    * At the exact moment Tier 1 escalation is triggered, the runtime captures the final failing Monitor 1 frame before opening the browser.
    * Copies the screenshot image directly into the Windows system clipboard as bitmap data (`CF_DIB` / `CF_BITMAP`).
  * **Physical Paste into Gemini Web Interface (`Ctrl+V`):**
    * `BrowserOffloader` opens or focuses the browser on Monitor 1, navigates to `gemini.google.com`, and clicks the prompt input field.
    * Dispatches `hotkey(["ctrl", "v"])` to paste the image directly from the clipboard.
    * The Gemini web app natively recognizes clipboard image data and attaches it as an image chip in $<1\text{s}$.
  * **Follow-Up Prompt Injection:**
    * Appends the sanitized consultation text below the image:
      * *"I am trying to achieve: [Goal]. Look at the screenshot above of what is currently on screen. The local agent got stuck trying to click [X, Y]. What exact visual element or menu should I click next to complete this task? Return a step-by-step recovery plan."*
  * **Unmatched Diagnostic Accuracy:**
    * Gemini literally sees the exact visual scene that confused UI-TARS.
    * It spots subtle UI quirks (modal focus traps, hidden scrollbars, obscured tabs) and generates a pinpoint grounded recovery blueprint that feeds back into local working memory.
  * **Air-Gap / Privacy Safety Gate:**
    * Before copying to the clipboard, applies `WindowGuard` sensitive region masking (blurring password fields, banking data, or terminal credentials) to guarantee privacy before external transmission.

### 1.17 Symbiotic Shadowing & Active Observation During Human Control (The "Watch & Learn" Engine)
* **Status:** **RATIFIED PROPOSAL (Stage P4 / P5 Core Learning Architecture).**
* **The Concept:**
  * When a human operator interacts with the PC—either taking over control via `InterruptGuard` or explicitly entering "Demonstration Mode"—ParasiteAI does not go blind or sleep.
  * Instead, it activates **Passive Shadowing Mode**: silently observing human mouse clicks, typing inputs, window focus shifts, and before/after visual deltas in real time.
* **Three Transformative Use Cases:**
  1. **Correction-Based Learning (The "Show, Don't Tell" Recovery):**
     * If Parasite gets stuck on a task (e.g. searching for Paint or handling a tricky game dialog), the user nudges the mouse, performs the action correctly, and lets go.
     * Rather than blindly re-trying its failed strategy, Parasite observes:
       * Which window was focused.
       * What exact coordinate or element the human clicked.
       * What visual change resulted on screen.
     * Parasite distills this demonstration into its `SKILL.md` playbook as an immediate, verified recovery recipe, seamlessly resuming the task from the human's new state.
  2. **Demonstration-to-Skill Recording (No-Code Macro Synthesis):**
     * The user says: *"Watch how I export this spreadsheet"* or *"Watch how I buy items in this game"*.
     * The human executes the 10-step sequence naturally.
     * Parasite’s background logger records the event stream (click coordinates, keypresses, active window titles, and screen diffs) on CPU (<1% load, 0 MB VRAM).
     * At the end of the demonstration, UI-TARS synthesizes the recording into a parameterized, reusable `LivingRoutine` or `SKILL.md` procedure that can be replayed autonomously forever.
  3. **Ambient Proactive Assistance (Repetition Detection):**
     * While the human works normally, Parasite passively observes repetitive behavioral loops (e.g., copying data from 50 rows of a PDF table into an Excel sheet, or renaming files in File Explorer).
     * Upon detecting a repeating 3-step loop, Parasite pings via Discord:
       > *"I noticed you're doing this repetitive data entry task. Would you like me to take over and finish the remaining 47 items for you?"*
     * The human clicks `[Approve]` in Discord, and Parasite takes over execution hands-free.
* **Zero Performance & Zero Safety Overhead:**
  * While the human is in control, Parasite generates **0 physical hardware events** (`MouseDriver` and `KeyboardDriver` are locked out).
  * **Mouse Path & Keystroke Shadow Stream:** Tracks the user's continuous Bézier trajectory velocity and raw keystroke sequence (with automatic PII and password field redaction via `WindowGuard`).
  * **Post-Click Animation Burst (Micro-Filmstrip):** On every human mouse click or Enter key, triggers a lightweight 3-frame background CPU burst (e.g. at $t+0\text{ms}$, $t+150\text{ms}$, $t+400\text{ms}$) to observe popup reveals, button depress states, and loading transitions.
  * Frame captures are strictly **event-driven on human mouse release (`WM_LBUTTONUP`) or Enter keystrokes**, consuming near-zero CPU and zero continuous VRAM.
  * `WindowGuard` PII masking remains 100% active during passive capture, ensuring sensitive passwords or private banking inputs are automatically blacked out from observation logs.

### 1.18 Center-of-Mass (Centroid) Button Snapping for Dense Grids & Small Controls
* **Status:** **RATIFIED PROPOSAL (Stage P4 Spatial Precision Engine).**
* **The Problem Observed in Benchmarks (e.g. Calculator & Dense Grids):**
  * In dense button matrices (like Windows Calculator `7, 8, 9, *` or tightly packed toolbars in Paint and File Explorer), UI-TARS sometimes predicts coordinates that land on the extreme edge or border of a button, or 10–15px off into an adjacent key.
  * A 10px error on an open desktop area doesn't matter, but a 10px error on Calculator clicks `8` instead of `7` or misses the decimal point entirely.
* **The Solution — Local Contour Center-of-Mass (Centroid) Snapper:**
  * When UI-TARS emits a target coordinate $(x_{\text{target}}, y_{\text{target}})$:
  * Extract a local $64 \times 64\text{ px}$ bounding patch around the coordinate.
  * Compute the button's boundary via fast CPU contour detection (Sobel/Canny edge or UIA element bounding box).
  * Calculate the button's **Center of Mass (Centroid)**:
    $$x_{\text{center}} = \frac{x_{\min} + x_{\max}}{2}, \quad y_{\text{center}} = \frac{y_{\min} + y_{\max}}{2}$$
  * Snap the mouse trajectory to land squarely on the centroid $(x_{\text{center}}, y_{\text{center}})$.
  * Guarantees that clicks hit the absolute physical center of buttons, checkboxes, and menu items, eliminating edge-clipping misses.

### 1.19 Pre-Click Foveated Verification (Zoom-In Optical Confirmation)
* **Status:** **RATIFIED PROPOSAL (Stage P4 Verification Subsystem).**
* **The Concept:**
  * An airline pilot checks instruments before pulling a lever; a precision agent should verify what lies beneath the cursor before committing a physical click.
* **How Pre-Click Foveated Verification Works:**
  * When the agent decides to click button `"7"` on Calculator or `"Save"` in a dialog:
  * The mouse moves to the target coordinate via human kinematics.
  * A tiny $128 \times 128\text{ px}$ foveated crop centered at the cursor is grabbed in $<1\text{ms}$ on CPU.
  * Fast Optical Check:
    1. *Text / Glyph Matching:* Runs an ultra-lightweight string check (or compact optical template match) on the crop.
    2. *Semantic Confirmation:* Verifies that the crop actually contains the intended target (e.g. the glyph `"7"` or icon `💾`).
    3. *Dynamic Recalibration:* If the crop shows `"8"` instead of `"7"`, the spatial offset is immediately known ($x - \text{stride}$), allowing the click to snap to the correct adjacent button before physical dispatch occurs!
  * Prevents costly wasted turns, strike penalties, and misclicks on tightly packed UIs.

### 1.20 Anti-Pattern Staleness, Drift Invalidation & Human Review Protocol
* **Status:** **RATIFIED PROPOSAL (Stage P4 / P5 Memory Governance).**
* **The Problem with Raw or Permanent Anti-Patterns:**
  * As identified by the operator, recording negative behaviors or failures (e.g., *"Do not click (794, 630)"* or *"Option X fails when dialog Y opens"*) is powerful in theory, but easily becomes outdated as software evolves, layouts update, or dynamic application state changes.
  * An obsolete anti-pattern permanently poisons the agent's action space, preventing it from taking valid, updated actions or creating false negative assumptions.
* **The Solution — Four-Pillar Anti-Pattern Lifecycle & Review Protocol:**
  1. **Strict Semantic Grounding (Zero Raw Coordinates - Rule 8 Compliant):**
     * Anti-patterns MUST NEVER store hardcoded $(x, y)$ coordinates.
     * Stored as semantic descriptions tied to visual/structural contexts:
       - *Bad:* `avoid_click: [412, 890]`
       - *Good:* `anti_pattern: {context: "notepad_save_as_dialog", trigger_text: "Cancel", reason: "dismisses unsaved document"}`
  2. **Visual & Structural Hash Check (Drift Invalidation):**
     * Each anti-pattern is anchored to a lightweight structural signature:
       - Target window class name and process version.
       - A perceptual hash (pHash) or edge feature signature of the parent control container.
     * *Runtime Invalidation Check:* Before an anti-pattern suppresses an action, the agent compares the live container's hash against the stored signature. If the layout, button style, or dialog version has changed, the anti-pattern is marked `STALE_OR_DRIFTED` and temporarily bypassed.
  3. **Confidence Scoring, TTL Decay & Exploratory Probing:**
     * Every anti-pattern carries a `confidence_score` and `last_verified_timestamp`.
     * If an anti-pattern has not caused or prevented a failure in 30 days, its confidence decays.
     * When confidence drops below threshold or an application update is detected, the agent schedules a low-risk **Exploratory Probe** (or asks the user during an interactive run) to re-verify if the pitfall still exists.
  4. **Human Review & Discord Bot Pruning Interface:**
     * The Discord Bot C2 interface surfaces a monthly or on-demand summary: `/review anti_patterns app:calculator`.
     * Displays a clean review card showing:
       - The rule description and why it was created.
       - A cropped thumbnail of the visual scene when it was triggered.
       - Quick action buttons: `[Keep]`, `[Update]`, `[Delete / Retire]`.
     * Gives the operator effortless veto power and zero-maintenance auditability over Parasite's learned memory.

### 1.21 Biological Humanized Mouse Engine (WindMouse / HumanCurve Physics vs. Pure Bézier)
* **Status:** **RATIFIED PROPOSAL (Stage P4 Kinematic Realism Engine).**
* **The Limitation of Pure Mathematical Bézier Curves:**
  * Currently, ParasiteAI uses cubic Bézier curves with a minimum-jerk velocity profile.
  * While smooth, pure Bézier curves remain mathematically idealized: they follow rigid parametric polynomials without organic micro-irregularities, muscle twitch, gravitational inertia, or physical overshoot.
  * Sophisticated anti-cheat engines (in games), anti-bot behavioral systems, and discerning human eyes can spot mathematically perfect spline paths.
* **The Solution — Physical Biological Trajectory Simulation (WindMouse / HumanCurve Engine):**
  * Implements an organic, physics-based mouse simulation script inspired by biological human kinematics (e.g. `pyclick` / `HumanCurve`, Ben Land's `WindMouse` algorithm, and Fitts's Law ballistic modeling).
* **Core Physics Components:**
  1. **Gravitational Target Pull & Wind Force:**
     * The cursor is treated as a physical particle with mass, velocity, and momentum moving through a fluid medium towards a gravitational attractor (the target coordinate).
     * Random "wind" force vectors dynamically perturb the trajectory mid-flight, simulating muscle tremor and uneven desk friction without ever losing convergence on the destination.
  2. **Fitts's Law Two-Phase Motion (Ballistic + Corrective Sub-Movement):**
     * *Phase 1 (Ballistic Sprint):* Rapid, high-velocity traversal covering ~85–90% of the distance with slight asymmetric acceleration.
     * *Phase 2 (Terminal Deceleration & Corrective Homing):* The cursor decelerates smoothly, making 1–2 micro-corrective adjustments as it enters the target boundary.
  3. **Human Overshoot & Micro-Snapback:**
     * In human motion studies, the hand frequently overshoots a small button target by 2–8 pixels before the visual feedback loop snaps it back into the centroid.
     * The simulation script introduces stochastic, human-like overshoot probability based on target size and approach speed, followed by a natural sub-50ms settling arc.
  4. **Micro-Tremor & Biological Jitter (Perlin Noise / Gaussian Drift):**
     * Continuous 8–12 Hz micro-tremor is superimposed onto the position updates, perfectly replicating human hand physiology.
  5. **Pre-Click and Post-Movement Hesitation:**
     * Real humans do not click at the exact millisecond motion ceases. A realistic variable pause (15ms–65ms) occurs between cursor arrival and `WM_LBUTTONDOWN`, matching cognitive motor preparation time.
* **Seamless Drop-In Replacement for `MouseDriver`:**
  * Runs entirely on CPU in $<0.2\text{ms}$ calculation time.
  * Adheres 100% to **Invariant D2**: `InterruptGuard` remains active at $<2\text{ms}$, yielding instantly if the physical user touches the hardware mouse during trajectory generation.

---

## 2. Flagship Product Pillars (Vision Blueprint)

### Pillar 1: Symbiotic Human-AI Control
* **Sub-2ms "Touch & Resume" Handshake:** The instant the user touches their mouse or keyboard, ParasiteAI yields control in under 2ms. Once idle, it seamlessly highlights what changed and resumes.
* **Holographic Ghost HUD & Predictive Reticle:** Transparent click-through HUD projecting pre-action targeting reticles and visual focus indicators.
* **[DROPPED — Invariant D2 / C2 Conflict] "Ghost Desk" (Background Multi-Desktop Execution):** Explicitly rejected in `feasibility_review.md §10.2`. Windows `SendInput` shares one global physical cursor/input queue across all virtual desktops; running hidden background actuation destroys the core product invariant of 100% visible, natural kinematics (`Invariant D2`). ParasiteAI operates visibly on the primary desktop, yielding instantly when the operator touches hardware.
* **Risk-Tiered Consent Gate:** Green (Read/Scroll), Yellow (Edit/Type), Red (Delete/Send/Execute). Red actions require one-click user authorization.

### Pillar 2: "Watch & Learn" Procedural Routines (No-Code RPA)
* **Demonstration-to-Skill Macro Synthesizer ("Shadow Learner"):** User clicks "Watch Me", performs a repetitive workflow, and ParasiteAI compiles it into an executable, parameterized `LivingRoutine`.
* **Self-Healing Grounding Engine:** Multimodal semantic grounding (Qwen2.5-VL + OCR + UI Automation) so updated buttons and changed themes don't break stored routines.
* **Data-Driven Batch Execution:** Execute a routine across 500 rows of an Excel spreadsheet or CSV.

### Pillar 3: Sovereign Security & Enterprise Air-Gap Compliance
* **100% Local Sovereign Brain:** Fully functional offline within the 6,500 MB VRAM ceiling (`Invariant D1`) on consumer GPUs (e.g. RTX 4060 8 GB). Zero cloud telemetry or required network traffic.
* **Dynamic "Red Zone" Hardware Shielding:** Automatic blur/masking over password managers, banking sites, and terminal credentials before vision frames reach memory.
* **Cryptographic "Black-Box" Flight Recorder:** Append-only SQLite WAL audit log of every action vector and visual diff with an interactive scrubber.

### Pillar 4: Multi-App Universal Workflow Engine
* **Cross-Ecosystem Orchestrator:** Drive workflows across legacy Win32, Qt, WPF, and modern web apps without APIs.
* **Real-Time Dynamic Contingency & Modal Interception:** Automatically detect and dismiss unexpected dialogs ("Save changes?", "Update available", "Network reconnecting").
* **Creative Tool & Non-Standard Canvas Manipulation:** Extending Min-Jerk Bézier curves and drag-and-drop primitives to manipulate visual interfaces where UI trees are sparse (node graphs in Blender/Unreal, timeline scrubbing in Premiere/DaVinci, drawing and slider adjustments in Photoshop, CAD, or Paint).

### Pillar 5: The Intelligent Companion Experience & Discord Bot Interface
* **Discord Command & Control Bot (Replacing GhostHUD / Desktop Overlays):** Complete decoupling from physical desktop UI rendering. Parasite operates as an asynchronous Discord bot interface in your private server:
  - Stream thoughts, progress milestones, and step receipts into a dedicated Discord channel/thread.
  - Send tasks via slash commands (`/task goal:"..."`) from desktop, phone, or tablet.
  - Upload thumbnail screen verification embeds after key actions or task completion.
  - Interactive approval buttons (`[Approve]`, `[Cancel]`, `[Panic Stop]`) for Yellow/Red risk actions.
* **Push-to-Talk Local Voice Companion:** On-device Whisper speech-to-text paired with low-latency local TTS (Piper or Kokoro) or Discord voice channel presence. Holding a hotkey enables natural spoken commands (*"Organize my downloads folder by project and date"*) with complete offline execution.
* **Zero Desktop Clutter:** 0% VRAM usage, zero screen capture contamination, and zero self-occlusion evasions.

---

## 3. Tool-Aware Reasoning & Meta-Tooling (GUI vs. CLI)

* **"Smartest Path" Affordance Engine:** Rather than treating Windows purely as a 2D canvas of clickable pixels, ParasiteAI evaluates whether a user goal is faster, cheaper, and safer to accomplish via:
  1. Direct sandboxed CLI execution (PowerShell commands, Python scripts, git commands),
  2. Physical mouse/keyboard GUI driving, or
  3. Strategic cognitive planning.
* **Sandboxed CLI Execution with Touch Preemption:** Command whitelisting, scraping prohibitions, 30s timeouts, and sub-10ms hardware touch preemption terminating the subprocess tree.

---

## 4. Cognitive Escalation Architecture & Protocols

* **Cognitive Escalation State Machine (Free & Local-First — Invariant D3):**
  - *Tier 0 (Local Perception-to-Action):* Autonomous Local Exploration via `UI-TARS-1.5-7B` single-pass CUA and CPU working memory (up to 2 local strikes). Default for all tasks.
  - *Tier 1 (Visible Browser Consultation):* When tactical deadlock occurs, the agent opens the user's real browser (`BrowserOffloader`) to consult free web AI / documentation using physical kinematics, harvesting the response via the sentinel clipboard verifier without API keys.
  - *[POSTPONED] Tier 2 (Direct Cloud API Planner):* Direct API integration (Gemini/Anthropic/OpenAI) is explicitly postponed per operator decision. ParasiteAI remains 100% free and functional without external API credentials.
  - *Clean Yield:* Transparent fallback to `USER_OVERRIDE` if permanently stuck.
* **Dual-Channel Output Separation:** Strict separation between:
  - **Channel A:** Internal machine-readable structured JSON feeding `LivingPlan`.
  - **Channel B:** Wholesome character monologue for the user, strictly sanitized so raw JSON, code blocks, or regex tokens never leak into the companion dock speech bubble.
* **Grounded Capability Contract:** Injected into external model prompts to enforce physical human actuator limits (no headless browser scrapers, no invisible DOM manipulation; only Bézier curves, clipboard pastes, and visible Set-of-Mark grounding).
* **Textual Scene Serialization Protocol:** Replacing bandwidth-heavy video streaming with ultra-compact (<3 KB) structured Set-of-Mark bounding box tables and active window briefs.

---

## 5. Tiered Persistent Memory & Routine Caching Engine (Phase 5 Additions)

* **SQLite WAL Procedural Store (`~/.parasite/memory.sqlite`):** Moving from in-memory ring buffers to an atomic, durable SQLite store with Write-Ahead Logging (WAL) to persist UI landmarks, learned routines, and user habits across PC restarts.
* **Per-App Spatial Landmark Profiles (`~/.parasite/app_profiles/`):** Persistent coordinate anchors indexed by executable name and window dimensions. Stores bounding boxes of stationary controls (game HUDs, tool palettes, inventory grids, status ribbons) to enable immediate zero-latency action dispatch.
* **Deterministic Routine Caching & Fast Replay:** Bypassing LLM inference latency entirely for frequent, verified routines by replaying validated mouse/keyboard trajectories directly.
* **Multi-App E2E Certified Test Harness:** Automated test harness across standard Windows desktop applications (Notepad, Calculator, Paint, Discord, Browser).

---

## 6. Go-to-Market Packaging, Tiers & Native Distribution

* **Product Packaging Tiers:**
  - *Parasite Personal:* Local VLM inference, Companion Dock, Holographic Ghost HUD, Sub-2ms Touch Preemption, Universal App Launcher, 5 saved Routines. (Free / Open Core / One-Time License).
  - *Parasite Pro:* Unlimited "Watch & Learn" Routine Synthesizer, Ghost Desk background execution, Voice I/O, Mobile Remote, Advanced Batch Data Ingestion. ($15/mo or $149 lifetime).
  - *Parasite Enterprise:* Air-gapped offline compliance, Hardware Red Zone PII masks, Encrypted Flight Recorder DVR, Multi-Seat Central Policy Manager. ($50–$100 / seat / month).
* **Zero-Friction Windows Distribution:** Single-command installer (`winget install parasite-ai` or `.msi` single-click bundle) packaging the Python runtime, CUDA DLLs, and default quantized VLM without requiring developer setup.

---

## 7. Stage P4.4 Architectural Follow-Ups & Behavioral Benchmarks

### 7.1 Track-B Behavioral Benchmark Suite (`benchmarks/behavior_suite.yaml`)
* **Context:** The canonical Core 20 Benchmark (`benchmarks/run_benchmark.py`) remains strictly locked per Engineering Cadence §5 and Stint P4.6 certification comparability (`baseline_p0` through `baseline_p4`).
* **Proposal (Targeted for Post-P4 / Track-B):** Create a separate, non-Core-20 behavioral evaluation track (`benchmarks/behavior_suite.yaml`) testing capabilities intentionally outside Core 20:
  - Open-ended program selection & tool composition (e.g., *"Convert this image to grayscale and save beside original"* across varied installed apps discovered dynamically via `Win32EnvironmentDiscovery`).
  - Live `ParasiteSkill` fail-closed recovery under synthetic UIA/focus/clipboard faults.
  - Self-learning skill co-authoring roundtrips (`TraceRecorder` -> `SkillLearner` -> Discord `SkillApprovalView` -> replay speedups on repeat runs).
  - §7.6 Gated Reflex Micro-Skill drift abort & seamless fallbacks to local UI-TARS on resized or restyled windows.

### 7.2 Deprecating Legacy `BrowserOffloader` Hardcoded Input Bar Offset (`rect[3] - 68`)
* **Problem:** `parasite_ai/mind/offloader.py` still retains a legacy hardcoded bottom-offset coordinate fallback (`rect[3] - 68`) for general browser offloading.
* **Status:** P4.4 `ParasiteSkill` cleanly eliminated layout math by relying on `Alt + G` activation + GUITHREADINFO/UIA caret verification + read-only UIA tree walking for `Copy`/`Stop` controls. Once legacy callers are retired or migrated onto `GeminiWindowBackend`, remove `rect[3] - 68` from `offloader.py` for full §7.3 compliance across all browser pathways.

### 7.3 Live Adaptive Benchmarking & In-Flight Approach Mutator (Exploration vs. Exploitation)
* **Target Stint:** **Stage P4, Stint P4.5 (`App Memory Integration & Local Playbooks`)** with live multi-app evaluation in **Stint P4.6 (`Stage P4 Certification Run`)**.
* **The Problem:** When running a skill or complex task live, if an agent merely checks binary pass/fail or relies silently on fallback chains (e.g. Tier-1 UIA failing into Tier-2 RapidOCR or Tier-3 VLM grounding), it risks cognitive stagnation. The agent appears to "succeed", but operates in a degraded, high-latency state without realizing its primary approach has drifted or broken, and without empirical data to switch strategies dynamically.
* **Architecture & Mechanics to Implement in P4.5:**
  1. **Fallback Degradation Telemetry:**
     - Instrument skills and symbiosis modules to track *fallback rescue rate* alongside execution latency.
     - When a routine repeatedly relies on Tier-2/Tier-3 rescue (`fallback_rescues >= 2`), flag the routine state as `DEGRADED` rather than clean `ACTIVE`.
  2. **In-Flight Strategy Competition (Active Live Benchmarking):**
     - Maintain lightweight competing execution vectors (e.g., launching an app via desktop icon vs. Start Search vs. Win+R; finding controls via UIA centroid vs. OCR bounding boxes).
     - Run micro-benchmarks during real tasks by probabilistically testing alternate viable vectors (ε-greedy exploration under safety bounds).
     - Score approaches on: (a) sub-second latency, (b) visual diff stability, and (c) zero required fallback interventions.
  3. **Autonomous Approach Adaptation & Self-Healing:**
     - If the primary approach suffers degraded performance or repeated fallback invocations, trigger `ParasiteSkill` or local planning to regenerate the playbook (`SKILL_COAUTHOR`), re-ground the visual anchors, and promote the winning vector to the primary fast path in SQLite WAL memory (`~/.parasite/memory.sqlite`).

---

## 8. Post-`4.X` Master Roadmap (`Stage P5` – `Stage P7`, Grounded to `feasibility_review.md`)

> **Status:** **ACTIVE MASTER BACKLOG (Updated 2026-11-16).** The initial 5-stage feasibility roadmap (`P0`–`P4` in [`feasibility_review.md`](file:///c:/Users/Suici/.gemini/antigravity/brain/e08f71d9-0960-44dd-99c8-c3319e9081d6/feasibility_review.md)) concludes with **Stint `P4.7` (`0.4.7.0`)**. All external Fatiao framework/Electron integration ideas are **scrapped**; only Fatiao-free, sovereign Python patterns live below, ordered strictly to compound reliability while preventing `feasibility_review.md §7.3 F7` operational sprawl.

```text
[P4.7 Close 4.X] -> [P5 Ouroboros, UIA Drill-Down & Multi-App] -> [P6 Watch & Learn + Games/Canvas] -> [P7 Sovereign Release & Voice]
```

### 8.1 `P4.7` (`0.4.7.0`) — Real-World Skill Generalization & `4.X` Closure *(Immediate Next Stint)*
* Closes the remaining 10% of the initial `P0`–`P4` roadmap:
  1. **Literal vs. Generative Intent Gate (`skills.py`):** Prevent literal text-entry skills from hijacking creative prompts (`L1-05` literal-echo bug).
  2. **Automatic `{{slot}}` Parameterization (`runtime.py` + `app_memory.py`):** Parameterize paths, filenames, math expressions, and quoted literals on farmed-plan promotion + resolve processes via `app_profiles`.
  3. **Protected Shipped Slugs + `ContentScanner` Gate:** Protect authored baseline playbooks from `_quarantine/` eviction (`refineCore` pattern) and scan external harvests for prompt injection/secrets before persisting to `AppMemory` or `data/skills/`.
  4. **Monitor-1 Shell & Focus Guard (`dual_mind.py`):** Fix multi-monitor `Program Manager` (`x=1920`) false off-monitor hotkey blocks (`L2-07`) and recover focus onto Monitor 1 (`L2-06`).
  5. **Long-Horizon Trace Support (`max_trace_steps=40`) & Deferred `SKILL_COAUTHOR` Queue** + 1 unseen non-benchmark smoke probe (e.g. Slide/Web workflow).

### 8.2 Stage `P5` (`0.5.x`) — Grounding Speedup, Ouroboros Self-Repair & Multi-App Composition
* **`P5.1` Cognitive Compression & Shallow UIA Drill-Down:**
  * Apply `caveman`-style terse token compression (`~50-65%` fewer output tokens) to internal CUA thoughts and `ParasiteSkill` co-authoring schemas.
  * Add two-tier shallow UIA inspection (`ax_overview` depth-3 summary -> targeted `ax_subtree(node_id)`) in `ScreenGrounder` so complex Explorer file lists (`L2-04`) and nested dialogs resolve in `<50ms` with visible Bézier clicks intact (`D2`).
* **`P5.2` Partial Sequence Splice & `Ouroboros` Self-Repair (Before Multi-App):**
  * Record step-level transitions `(step_id, pre_proc, post_proc, success)` so working prefix/suffix steps are preserved and spliced when `UI-TARS` rescues a middle step.
  * Track `fallback_rescues >= 2` (`DEGRADED` status per `§7.3`), save pre-apply `.snapshots/<timestamp>_<slug>/` backups, and run `ParasitePhase.SKILL_REPAIR` with strict YAML validation and auto-rollback on regression.
* **`P5.3` Multi-App Composition (`P4.5.5`) & Progressive Skill Packs:**
  * Decompose multi-app goals (`L2-03`, `L3-02`, `L3-03`, cross-app workflows) into app-scoped `SubGoal` pipelines sharing an `EpisodeBlackboard` (`{{clipboard}}`, `{{last_output}}`).
  * Upgrade `SkillRegistry` to progressive skill folders (`SKILL.md` `<150` tokens + optional `scripts/` & `references/` loaded on demand) with `Ask` multi-choice disambiguation (`risk_gate.py` / Discord) and zero-LLM `correctionDetect` feedback logging.
* **`P5.4` Track-B Open-Ended Behavioral Suite (`benchmarks/behavior_suite.yaml`):**
  * Evaluate unseen multi-app composition, drift self-repair, and skill co-authoring roundtrips without modifying Core-20 comparability (`§7.1`).

### 8.3 Stage `P6` (`0.6.x`) — "Watch & Learn" Human Shadowing & Adaptive Canvas/Game Cognition
* **`P6.1` Passive Shadowing Mode & "Show, Don't Tell" Recovery (`§1.17`):** Event-driven recording of human `WM_LBUTTONUP` clicks, masked keystrokes (`WindowGuard`), and window transitions on `InterruptGuard` or `/watch`.
* **`P6.2` Demonstration-to-`SKILL.md` Synthesizer:** Compile human demonstrations into parameterized progressive `SKILL.md` packs with `Ouroboros` verification.
* **`P6.3` Windowed Sub-Resolution & Scale-Invariant Landmarks (`§1.9`, `§1.12–1.13`):** `960x540` client-rect fast vision mode + normalized/corner-anchored coordinates for sparse visual canvases and live game stretch probes (`Warsim`, `Rift Wizard`, `RimWorld`).

### 8.4 Stage `P7` (`0.7.x`) — Sovereign Hardening, Audit DVR, Voice & Packaging
* **`P7.1`:** Retire legacy `offloader.py` `rect[3] - 68` offset (`§7.2`) + Dynamic Red-Zone PII hardware blur masking on captured frames.
* **`P7.2`:** Immutable SQLite WAL Black-Box DVR & Discord `/review` skill/anti-pattern pruning cards (`§1.20`).
* **`P7.3`:** CPU-only Push-to-Talk Voice Companion (Whisper STT + lightweight CPU TTS) & single-click Windows distribution (`.msi` / `winget`).

---

## 9. Standalone Harvested Techniques & Side-Tools *(Scrapped Fatiao Shell Removed)*

*Extracted algorithmic patterns and self-contained Python/CLI patterns evaluated strictly against `feasibility_review.md` (`D1 <= 6,500 MB VRAM`, `D2 100% Visible Actuation`, `D3 Sovereign/Free`, `D4 Anti-Hardcoding`, `F7 Anti-Sprawl`). Any heavyweight Electron wrapper, competing runtime, or channel bloat is permanently excluded.*

### 9.1 Core-Aligned Patterns *(Scheduled into `P4.7` – `P5`)*
1. **Memory & Skill `ContentScanner` (`P4.7`, 0 MB VRAM, ~60 LOC stdlib):**
   * Synchronous regex gate in `parasite_ai/safety/` blocking indirect prompt injection (`ignore previous instructions`, `<|im_start|>`, `<|endoftext|>`, role hijacks) and redacting credentials/tokens before persisting any harvested `SKILL.md` or `AppMemory` row.
2. **Protected Factory Slugs & Atomic Rollback Snapshots (`P4.7` / `P5.2`):**
   * Protect baseline authored `SKILL.md` playbooks from silent `_quarantine/` eviction (`refineCore` pattern); before any autonomous `Ouroboros` repair mutates a skill, save `.snapshots/<timestamp>_<slug>/` and revert automatically if YAML validation or post-edit verification regresses.
3. **Terse Output Compression Mode (`P5.1`):**
   * Apply concise schema-first rules (stripping conversational filler/articles while preserving exact JSON/action tokens) to `UI-TARS` `Thought:` lines and `ParasiteSkill` co-authoring prompts to cut generation latency by ~50–65% with 0 MB VRAM overhead.
4. **Shallow `ax_overview` -> `ax_subtree` UIA Drill-Down (`P5.1`, `<50ms` CPU):**
   * Two-tier UIA tree inspector in `ScreenGrounder`: fast depth-3 container overview first, drilling into `ax_subtree(node_id)` only on target file lists or dialogs while keeping physical cursor actuation intact (`D2`).
5. **Progressive Skill Packs (`SKILL.md` + `scripts/` + `references/`, `P5.3`):**
   * Support optional `scripts/` and on-demand `references/` subfolders under `data/skills/<slug>/` while keeping top-level `SKILL.md` prompt injection `<150` tokens.
6. **Zero-LLM User Correction Detector & Structured `Ask` Disambiguation (`P5.3`):**
   * Two-pass regex filter on Discord/CLI messages catching explicit negative user corrections (`"don't use..."`, `"wrong window"`, filtering pasted tracebacks) into failure notes, paired with multi-choice Discord `Ask` cards (`risk_gate.py`) before executing ambiguous multi-step goals.

### 9.2 Selective Sandboxed CLI Side-Tools *(Opt-In Only Under `D2` Visible-First Policy — Never Replace GUI Viewing by Default)*
*Per `feasibility_review.md §10.2`, pure CLI/headless Python tools may be invoked as **announced sandboxed side-tools** only for bulk file/data inspection where mouse-scrolling has zero user value:*
* **Bulk Document / Spreadsheet Extraction (`pypdf` / `python-docx` / `openpyxl` CSV export):** Light pure-Python helpers for reading multi-page `.pdf`/`.docx`/`.xlsx` inputs without pulling heavy `marker`/PaddleOCR/Playwright browser stacks.
* **Lightweight Keyless Search (`duckduckgo_search` / Python `urllib` + HTML-to-Markdown):** Fast query/article text lookup when a task only needs raw reference text (`<300ms` CPU, 0 MB VRAM), avoiding heavy browser emulation (`crawl4ai` Playwright dependency skipped).
* **Grounded Citation Ledger (`url -> [n]`):** Verify verbatim quotes against fetched text when synthesizing reference knowledge so `SKILL.md` notes do not hallucinate facts.

### 9.3 Delegated / Quarantined `F7` Operational Sprawl *(Excluded from Core Roadmap `P4.7`–`P7`)*
*Per `feasibility_review.md §7.3 (F7)` and `§7.4`, these optional/unrelated utilities do **not** advance core desktop reliability or hardware invariants and are parked here out of the active engineering critical path (revisit strictly post-`P7` as optional third-party plugins, if ever):*
* ❌ **Scrapped Runtime Wrappers:** External agent containers/Electron shells, competing local Ollama models (`>6.5 GB` VRAM conflict), bundled rate-limited cloud API wrappers, external agent stdio bridges (`OpenClaw`/`OpenCode`/MCP server wrapper).
* ❌ **Heavy Duplicate Vision/ML Bloat (`F7`):** Playwright `crawl4ai` container, `marker`/PaddleOCR second OCR stack (duplicates existing `UIA` + `RapidOCR` + `UI-TARS`), `laya-multilingual-onnx` / `mmBERT` 35 MB secondary classifier (unnecessary over `UI-TARS` + deterministic rules).
* ❌ **Unrelated Consumer Niche Side-Skills:** `qwen3-tts-voice-clone`, `easy-subtitle`, `youtube-content`, `maps`, `himalaya` CLI email, `excalidraw`/`architecture-diagram`, `html/slides` generators, `product-price-monitor`, `weekly-review-planning`, `humanizer`, `todo.json` duplicate planner, `comfyui` (VRAM violation), `crypto`, and localization packs.


