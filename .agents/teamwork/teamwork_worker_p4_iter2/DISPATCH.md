# Worker (Iter 2) Dispatch: Apply Adversarial Remediations to Phase 4 Master Plan

Working directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter2
Target file to update: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
Original request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md

Input Reports:
- Explorer 1 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_1\handoff.md
  (Patches for Blueprint Drop on recommended_strategy, T3/T4 ping-pong termination, advisor failure limit, codeblock/JSON leakage sanitization)
- Explorer 2 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_2\handoff.md
  (Patches for passive action exemption from visual diff, CLI exit code evaluation, Grounded Capability Contract CLI-scraping/UIA-injection bans)
- Explorer 3 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_3\handoff.md
  (Patches for CLIExecutionSandbox in Sub-Phase 4D, UniversalAppResolver Tier 3 dead-code break, Tier 1 PrecisionAppMatcher substring fix, VERIF-10/11)

Objective:
Directly edit and update `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` to incorporate all formulated remediations from Explorers 1, 2, and 3.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Preserve all core invariants:
- Sub-2ms hardware touch preemption
- Ctrl+Alt+K instant hard kill (<5ms)
- brain.mode: "local_llm" default (zero silent cloud exfiltration)
- Strict anti-hardcoding invariant across all sub-phases

Deliver your completion report in:
C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter2\handoff.md


## 2026-11-01T02:52:43Z
You are Worker (Iter 2: Master Plan Remediation Writer).
Your working directory is: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter2\
Read C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md first (mandatory).
Read your dispatch instructions at: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter2\DISPATCH.md

Target File to update:
`c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`

Input Material from Explorers:
- Explorer 1 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_1\handoff.md
- Explorer 2 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_2\handoff.md
- Explorer 3 Report: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_iter2_3\handoff.md

Your Task:
Directly update and integrate all formulated replacement blocks into `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`:
1. DualChannelRouter Blueprint Hydration: Check for both `"recommended_strategy"` and `"steps"` so blueprints are never dropped.
2. Escalation State Machine: Add cumulative cycle limit (`max_escalation_cycles = 3`) to eliminate infinite T3/T4 ping-pong loops, and track `consecutive_advisor_failures = 2` to prevent infinite advisor loops, escalating cleanly to `USER_OVERRIDE`.
3. Speech Bubble Sanitization: Rigorous `_sanitize_text` stripping all code blocks (```` ```...``` ````), raw JSON dictionaries, and error strings.
4. Action-Aware Strike Evaluation: Exempt passive actions (`WAIT`, `DONE`, non-visual `HOTKEY`) from the visual diff check, and evaluate headless CLI commands (`RUN_CLI_COMMAND`) by `returncode == 0` rather than visual diff.
5. Sealing Grounded Capability Contract: Explicitly forbid CLI-based headless scraping (`curl`, `requests`, `playwright`, `puppeteer`, `selenium`) and programmatic UI Automation pattern injection (`ValuePattern.SetValue`, `InvokePattern.Invoke`).
6. CLIExecutionSandbox Specification (Sub-Phase 4D): Explicit execution timeout (30.0s), 10ms `cancellation_token` polling for process tree termination (`taskkill /F /T /PID`), command whitelisting, and shell injection protection.
7. UniversalAppResolver Robustness: Fix Tier 3 (`Win+R`) dead-code with explicit progression counters (`_start_search_attempts`, `_run_dialog_attempts`), and fix Tier 1 substring collisions via `PrecisionAppMatcher` with word boundaries, exact match prioritization, and destructive verb disqualification.
8. Sub-Phases & Victory Matrix: Update Sub-Phases 4B, 4D, 4E, 4F and add `VERIF-10` and `VERIF-11`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Deliver your completion report in:
C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter2\handoff.md
Send a completion message back to your orchestrator when finished.
