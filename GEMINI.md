# ParasiteAI - Master Agent Operating Instructions & Engineering Governance

This workspace is governed by the rules codified in [`AGENTS.md`](file:///C:/ParasiteAI/AGENTS.md) and [`.agents/rules/engineering_cadence.md`](file:///C:/ParasiteAI/.agents/rules/engineering_cadence.md).

All agents, tools, and subagents MUST strictly adhere to the 8 Invariant Sections of the Engineering Cadence:
1. §1 Single-Unit Execution Boundary (One stint per turn, no auto-cascading).
2. §2 Mandatory Planning Gate (`<unit_id>_implementation_plan.md` with `RequestFeedback: true`, Cadence compliance checklist, stop and await user approval — **waived exclusively for unattended `parasiteai-eval-iterate` scheduled runs in `UNATTENDED AUTONOMOUS MODE`, which MUST NOT set `RequestFeedback: true`, MUST NOT call `ask_question`, and execute one bounded `active_stage` stint without halting**).
3. §3 Completion Protocol & Verification Gate (Test verification, `walkthrough.md`, `HANDOFF.md`, hard stop).
4. §4 Mandatory Changelog Release Integrity (Update `CHANGELOG.md` on every completed unit).
5. §5 Roadmap & Stint Identifier Continuity (Roadmap sanctity).
6. §6 Live Benchmark & Batch Script Governance (Interactive desktop batch scripts, hands-off etiquette).
7. §7 Empirical Root-Cause Verification (No hardcoding, no layout guessing, verify upstream root cause on live desktop; §7.6 Gated Reflex Micro-Skill Exemption).
8. §8 Strict Interface Contracts, Prompt Engineering & Working Memory Invariants (Native screen pixel standard, zero numerical anchoring in prompt examples, zero synthetic layout guessing in working memory).
