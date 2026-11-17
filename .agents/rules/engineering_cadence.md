# Rule: Engineering Cadence, Release Integrity & Documentation Governance

## 1. Single-Unit Execution Boundary (Strict Stint Cadence)
- Under no circumstances may the agent execute more than one bounded task, stint, or milestone in a single conversation turn or session.
- Once the scope of an approved work unit is verified and tested, the agent MUST immediately stop modifying code and await the user's explicit command to proceed to the next unit.
- Never cascade from one work unit into the next without a distinct, standalone plan and explicit user sign-off.

## 2. Mandatory Planning & Approval Gate
Before touching any production code or test files for any new work unit:
1. Formulate a dedicated implementation plan (`<unit_id>_implementation_plan.md`) with `RequestFeedback: true`.
2. Present the technical design, diffs, and verification commands.
3. Conduct a mandatory self-audit against this Engineering Cadence, confirming zero violations of Sections 1 through 8.
4. STOP and wait for the user's explicit approval or feedback.
5. Do NOT execute code changes until approval is explicitly registered.

> **Scheduled Autonomous Automation Exemption (`parasiteai-eval-iterate`):**
> When invoked non-interactively by the scheduled `parasiteai-eval-iterate` automation (`agentapi new-conversation` carrying `UNATTENDED AUTONOMOUS MODE`), the Section 2 interactive approval stop and `<unit_id>_implementation_plan.md` feedback gate are **waived** so the loop runs zero-touch:
> - **NEVER** set `RequestFeedback: true` on any artifact, **NEVER** call `ask_question`, and **NEVER** stop mid-run waiting for human approval.
> - Still perform an internal Cadence audit (§1, §4, §5, §6, §7, §8) and proceed directly to implementing at most **one** bounded sub-stint inside `active_stage` (if a genuine software defect or failing test exists), running `pytest` + `--version`, updating `CHANGELOG.md` / `HANDOFF.md` / `.automation_eval_cursor.json`, and terminating cleanly.
> - Interactive user sessions MUST continue to obey Section 2 in full unless explicitly fast-tracked by the user.

## 3. Completion Protocol & Verification Gate
When a work unit finishes:
1. **Report Results & Verification (Targeted vs. Milestone Test Gate):**
   - For isolated sub-stints (e.g. `P4.4.x`), run and report **only the targeted test files** covering the touched modules (with `-q --tb=short`, plus `--version` if bumped) to avoid needless full-suite token/time overhead.
   - Reserve the full `500+` test regression suite for stage/milestone boundaries (`P4.4`, `P4.5`, `P4.6`) or cross-cutting core edits (`config.py`, `runtime.py`, `memory.py`).
   - Report the exact verification results, test pass counts, and telemetry for the completed unit.
2. **Update Walkthrough & Handoff:** Update `walkthrough.md` and `HANDOFF.md` to reflect the completed state.
3. **Hard Stop (No Proactive Planning):** STOP immediately. **Do NOT generate, draft, or propose the next unit's implementation plan artifact unprompted.** Await the user's explicit prompt/command requesting the next plan before generating it.

## 4. Changelog & Version Release Integrity (Mandatory)
To prevent documentation neglect and ensure complete traceability:
1. **Synchronize `CHANGELOG.md` on Every Milestone / Stint Completion:**
   - Every completed work unit that adds features, fixes defects, modifies architecture, alters config defaults, or updates benchmark results MUST record an entry under `## [Unreleased]` (or the current milestone header) in `CHANGELOG.md`.
   - Follow the Keep a Changelog standard with categorized sections (`Added`, `Changed`, `Fixed`, `Removed`, `Security`).
2. **Include File Paths & Concrete Telemetry:**
   - Mention the exact module/file paths touched.
   - Include objective verification metrics and telemetry deltas (e.g. test pass counts, latency numbers, benchmark pass rates).
3. **Never Defer Changelog Keeping:**
   - Updating `CHANGELOG.md` is an invariant part of closing a work unit—never leave it as an afterthought for future sessions.

## 5. Roadmap & Stage/Stint Identifier Continuity (Roadmap Sanctity)
To prevent drift, confusion, and accidental re-labeling of future roadmap phases:
1. **Respect Established Roadmap Numbering:**
   - The agent MUST respect the high-level roadmap and milestone/stage definitions as recorded in primary roadmap documents.
   - Future stages with defined charters MUST NOT be renamed, overwritten, or repurposed for intermediary tasks.
2. **Intermediary Scope Sub-Numbering:**
   - Any necessary intermediary stabilization, housecleaning, optimization, or context-scaling stages that precede a ratified roadmap stage MUST be versioned as intermediary sub-stages rather than advancing or usurping the major milestone label.
3. **Explicit User Approval for Roadmap Revisions:**
   - A major milestone stage name or charter may only be updated or redefined if the user explicitly directs or approves a formal roadmap re-architecture. Never introduce milestone relabeling implicitly or unprompted.

## 6. Live Benchmark Execution & Batch Script Governance (Mandatory)
Because the agent interacts with the physical Windows desktop via Win32 graphics (BitBlt screen captures) and low-level input hardware:
1. **Interactive Desktop Token Invariant:**
   - Background tools and non-interactive sessions cannot reliably perform BitBlt screen captures or real Win32 cursor movements without hitting sandbox permissions or cursor lock.
   - Live multi-task benchmarks MUST be executed from the user's interactive Windows desktop session via a dedicated root batch script (`run_benchmark_<stage>.bat`).
2. **Mandatory Root Batch Script Creation:**
   - Whenever a stint or milestone involves running a full or partial benchmark baseline certification, the agent MUST create or update the dedicated root batch script and present it to the user.
   - The agent MUST NEVER attempt to silently or directly execute the live multi-task benchmark inside a background tool call.
   - The script must automate pre-flight daemon health checks, GPU governance validation, checkpointed execution (`--resume`), and comparative scorecard generation against earlier baselines.
3. **Hands-Off Execution Protocol:**
   - Direct the user to launch the generated batch script from their own interactive terminal/console window, providing clear reminders regarding hands-off etiquette (e.g. not moving the mouse or typing on the active display during the run).

## 7. Empirical Root-Cause Verification vs. Downstream Heuristic Proliferation (No Hardcoding)
To preserve architectural anti-fragility and avoid brittle, app-specific technical debt:
1. **Targeted Smoke Probing on Failing Cases:**
   - Unit tests only verify code contracts and mocked arguments; they NEVER prove that a live visual-spatial or model failure mode is resolved.
   - When an upstream fix is implemented, the agent MUST verify it by running a targeted smoke probe on the specific failing interaction and inspecting the resulting live episode receipt.
   - If the targeted receipt confirms the model now outputs correct physical actions and coordinates, the defect is empirically resolved.
2. **Verify Root-Cause Fixes Before Layering Workarounds:**
   - When an upstream root-cause defect is identified and fixed (e.g. visual resolution scaling, coordinate domain alignment, aspect ratio distortion, or prompt ordering), the agent MUST empirically verify the smoke probe receipt BEFORE proposing or implementing any downstream synthetic compensations or heuristic snapping layers.
3. **Prohibition of Fragile Layout & App-Specific Heuristics:**
   - The agent MUST NEVER introduce hardcoded, app-specific geometry assumptions (e.g. assuming standard window title bar dimensions, fixed button offsets, or standard window chrome).
   - In a general-purpose vision agent, custom-rendered applications and web containers draw custom chrome where fixed geometric heuristics fail.
4. **Avoid Speculative Bulk Multi-Stint Cascades:**
   - When drafting an intermediary roadmap or multi-stint stage, downstream stints MUST be treated as contingent hypotheses, NOT foregone conclusions.
   - Never rigidly commit to or implement downstream workarounds before evaluating whether the upstream root-cause fix already resolved the problem on physical hardware. If the upstream smoke probe resolves the failure mode, downstream compensatory stints MUST be pruned immediately.
5. **Empirical Gate for Compensatory Code:**
   - Downstream compensatory logic (such as snapping, bounding box clamping, or coordinate overrides) may ONLY be considered if:
     a) The upstream root-cause fix is fully verified and proven active in production paths, AND
     b) A live smoke probe or benchmark receipt proves the foundation model still fails on that specific interaction, AND
     c) The compensatory mechanism is completely general (e.g. backed by live accessibility trees or universal OS hit-testing APIs, never hardcoded coordinate offsets), AND
     d) The user explicitly approves the compensatory design in a standalone implementation plan.
6. **The Gated Reflex Micro-Skill Exemption Contract:**
   - While general high-level skills, workflows, and core reasoning paths MUST remain coordinate-free and backed by accessibility trees (UIA) or visual grounding:
   - A narrowly scoped "Reflex Micro-Skill" (e.g. static calculator numpad, fixed confirmation dialogs, or sub-200ms compound bursts) MAY store relative client-window coordinates IF AND ONLY IF all four Invariant Safety Gates are satisfied:
     1. *Window-Relative Only:* Coordinates MUST be relative to the target window client rectangle ($[0..\text{ClientW}-1, 0..\text{ClientH}-1]$), never absolute desktop screen coordinates.
     2. *Rigid Dimension Assertion:* The target window's current dimensions must match expected recorded dimensions $(W, H)$ prior to dispatch.
     3. *Pre-Flight Visual Anchor / pHash Gate:* A sub-5ms pre-dispatch visual check (perceptual hash or anchor pixel check) MUST verify that the target surface has not reflowed, changed theme, or scrolled.
     4. *Non-Destructive Fail-Closed Fallback:* If either geometry or visual hash check fails, the reflex burst MUST NOT execute blindly. It must abort in $<2\text{ms}$ and fall back cleanly to Tier 2 (UIA) or Tier 4 (VLM Re-grounding).
7. **Historical & Test Screenshots Are Forensic-Only, Never Coding Specs (§7.7):**
   - Saved `.png` captures in `data/logs/parasite_skill/`, `_archive_old_runs/`, or `data/debug_captures/` are strictly **post-mortem debugging evidence and regression test fixtures**, NEVER UI design specifications.
   - Agents MUST verify the sidecar JSON's `app_version` and `timestamp` before inspecting any screenshot, and MUST treat captures from prior builds or `_archive_old_runs/` as superseded historical records.
   - Agents MUST NEVER derive pixel bands, fixed offsets, window dimensions, or icon-order assumptions from any saved screenshot.

## 8. Strict Interface Contracts, Prompt Engineering & Working Memory Invariants
To prevent silent mathematical landmines, coordinate bifurcation, and prompt anchoring:
1. **Strict Invariant Interface Contracts:**
   - The spatial coordinate contract between the visual capture subsystem, model output, and OS execution layer MUST be explicitly defined and adhered to across all adapters.
   - Adapters MUST NEVER apply arbitrary threshold guessing or dynamic multiplexing between conflicting coordinate domains.
   - Coordinates must be clamped strictly within valid screen boundaries without arbitrary scaling distortion.
2. **Prompt-Parser Unit Consistency Invariant:**
   - All spatial units, bounds, coordinates, and anchors presented across system prompts, instructions, recent memory, and OS working memory MUST strictly match the output parser's expected domain.
3. **Zero Numerical Anchoring in Prompt Engineering:**
   - System prompts, few-shot examples, and instructional templates MUST NEVER contain plausible or literal runtime coordinates, file paths, or target data.
   - All syntax demonstrations and examples MUST use abstract symbolic placeholders (e.g. `(x, y)`, `<text>`, `<keys>`).
   - Vision-language models are highly susceptible to few-shot numerical anchoring; passing concrete numbers in examples causes models to echo canned coordinates rather than grounding actions dynamically from live visual perception.
4. **Zero Synthetic Layout Guessing in Working Memory:**
   - OS Working Memory snapshots MUST ONLY report verified, unmanipulated operating system API data (e.g. actual window bounding rectangles queried directly from OS window managers).
   - Working memory MUST NEVER inject synthetic coordinate guesses of buttons, icons, or taskbar controls. All fine-grained UI controls must be discovered and localized by the model through visual perception.
5. **End-to-End Ground-Truth Test Coverage:**
   - Unit tests for spatial parsers MUST test symmetric edges, centers, and boundaries, asserting exact physical grounding without normalization distortion across the entire virtual desktop.
