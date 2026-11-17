# ParasiteAI - Master Agent Operating Instructions & Engineering Governance

All AI coding assistants, agents, and subagents operating within the ParasiteAI repository MUST strictly adhere to the engineering cadence, release integrity, and architectural invariants defined herein and codified in [`.agents/rules/engineering_cadence.md`](file:///C:/ParasiteAI/.agents/rules/engineering_cadence.md).

---

## 1. Mandatory Operating Charter ([`engineering_cadence.md`](file:///C:/ParasiteAI/.agents/rules/engineering_cadence.md))

Every turn, interaction, and proposed modification is governed by the 8 Invariant Sections of the Engineering Cadence:

1. **Section 1: Single-Unit Execution Boundary (Strict Stint Cadence)**
   - Exactly ONE bounded work unit/stint per conversation turn.
   - Once verified and tested, STOP immediately and await the user's explicit command before starting the next unit. Never cascade unprompted.

2. **Section 2: Mandatory Planning & Approval Gate**
   - Before modifying production code or test files, create a dedicated plan artifact (`<unit_id>_implementation_plan.md`) with `RequestFeedback: true`.
   - Conduct a mandatory self-audit against all 8 sections of the Engineering Cadence.
   - STOP and await explicit user sign-off. Never modify code before approval is registered.
   - **Scheduled Autonomous Automation Exemption (`parasiteai-eval-iterate`):** Unattended `agentapi new-conversation` runs invoked by `parasiteai-eval-iterate` (`UNATTENDED AUTONOMOUS MODE`) waive this interactive approval stop: they MUST NOT set `RequestFeedback: true`, MUST NOT call `ask_question`, and MUST execute at most one bounded `active_stage` sub-stint end-to-end without waiting for human input.

3. **Section 3: Completion Protocol & Verification Gate**
   - Targeted vs. Milestone Test Gate: isolated sub-stints run ONLY the targeted test files covering the touched modules (`-q --tb=short`); reserve the full `500+` test suite for stage/milestone boundaries or cross-cutting core edits.
   - Report exact verification test counts, pass rates, and telemetry.
   - Update `walkthrough.md` and `HANDOFF.md`.
   - HARD STOP: Never draft or generate the next stint's plan unprompted.

4. **Section 4: Changelog & Release Integrity**
   - Update `CHANGELOG.md` under `## [Unreleased]` on EVERY completed stint without exception.
   - Follow Keep a Changelog standard with categorized sections (`Added`, `Changed`, `Fixed`, `Removed`).

5. **Section 5: Roadmap & Stint Identifier Continuity (Roadmap Sanctity)**
   - Respect established roadmap stage numbers. Intermediary sub-stages must use sub-numbering (e.g. `P2.7.2.2`). Never usurp future roadmap milestone labels.

6. **Section 6: Live Benchmark & Batch Script Governance**
   - Physical Win32 graphics (BitBlt) and hardware cursor automation require an interactive desktop session.
   - Live benchmarks and multi-task suites MUST be executed by the user via root batch scripts (`run_benchmark_<stage>.bat` or `run_smoke_probe_<stage>.bat`).
   - The agent MUST NEVER run live multi-task benchmarks directly inside a background tool call.

7. **Section 7: Empirical Root-Cause Verification vs. Downstream Heuristic Proliferation**
   - Unit tests only prove mocked contracts; live failure modes MUST be verified via targeted smoke probes on live hardware.
   - Verify upstream root-cause fixes before considering any downstream compensations.
   - Prohibit hardcoded layout, coordinate, or application-specific heuristics. Downstream logic must be completely general (accessibility trees or OS APIs).
   - **Gated Reflex Micro-Skill Exemption (§7.6):** Narrowly scoped reflex micro-skills (e.g. static keypad grids, compound bursts) may use relative client-window coordinates IF AND ONLY IF verified by: (1) client-relative coordinates only, (2) exact window dimension check, (3) sub-5ms pre-dispatch visual/pHash anchor check, and (4) fail-closed abort to UIA/VLM on any mismatch.
   - **Forensic-Only Screenshot Policy (§7.7):** Saved `.png` captures in `data/logs/parasite_skill/`, `_archive_old_runs/`, or `data/debug_captures/` are strictly historical debugging/testing artifacts, NEVER UI specs for coding heuristics. Always check `app_version` and `timestamp` in the sidecar JSON before inspecting any `.png`, and never derive pixel bands, fixed offsets, or icon-order assumptions from screenshots.

8. **Section 8: Strict Interface Contracts, Prompt Engineering & Working Memory Invariants**
   - Native Screen Pixel Standard: UI-TARS 1.5 (Qwen2.5-VL backbone) outputs absolute screen pixels $[0..W-1, 0..H-1]$ matching the physical frame. Zero normalization division or arbitrary threshold guessing.
   - Zero Numerical Anchoring: Prompt templates, instructions, and few-shot examples MUST NEVER contain plausible or literal runtime coordinates or target values. Use abstract symbolic placeholders only (e.g. `(x, y)`, `<text>`, `<keys>`).
   - Zero Synthetic Guessing in Working Memory: Working memory snapshots report only verified, unmanipulated OS API data (e.g. actual window bounding rectangles). Never inject synthetic guesses of button centers or taskbar controls.

---

## 2. Invariant Hardware Constraints

- **Invariant D1 (VRAM Ceiling):** Dedicated RTX 4060 VRAM budget ceiling is $\le 6,500\text{ MB}$ at all times.
- **Invariant D2 (Sub-Second Latency):** Mouse motion and input dispatch must remain reactive ($<2\text{ms}$ physical interrupt takeover).
