## 2026-11-01T12:47:43Z
You are Worker M4D Iteration 2 for Phase 4 Milestone 4D (Tool-Aware Reasoning & CLI Execution Sandbox) remediation in ParasiteAI.

Working Directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4d_iter2\
Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Reference Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md (§6, §10 Sub-Phase 4D, §12 VERIF-10)
Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
Challenger 1 Report: C:\ParasiteAI\.agents\teamwork\challenger_m4d_1_rep\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

REMEDIATION TASK:
Address the critical defects identified by Challenger 1 in `parasite_ai/mind/affordance.py`:

1. **Process-Tree Child Orphan Fix (Critical)**:
   In `CLIExecutionSandbox.execute()`:
   Currently, `proc.kill()` is invoked before `taskkill /F /T /PID str(proc.pid)`. This causes `taskkill` to fail with "process not found" (code 128) because the root process was already killed, orphaning all child processes.
   Fix this in both preemption (lines 264-278) and timeout (lines 281-296):
   Invert the order so `taskkill /F /T /PID str(proc.pid)` runs FIRST while `proc` is alive, terminating the entire process tree, followed by `proc.kill()`:
   ```python
   # Execute taskkill FIRST to terminate child tree before killing root
   try:
       subprocess.run(
           ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
           capture_output=True,
           creationflags=create_no_window,
       )
   except Exception:
       pass
   try:
       proc.kill()
   except Exception:
       pass
   ```

2. **Shell Wrapper Whitelist Evasion Protection**:
   In `CLIExecutionSandbox.sanitize_and_tokenize()`:
   When `binary_base in {"cmd", "cmd.exe", "powershell", "powershell.exe"}`:
   Inspect the command arguments passed after `/c`, `/k`, `-c`, `-command` (or similar invocation switches).
   If the target being invoked by cmd or powershell is an executable binary (e.g. `calc`, `calc.exe`, `notepad.exe`, `whoami`, `rundll32`), verify that it is in `PERMITTED_BINARIES` or raise `PermissionError` (e.g., `f"Subcommand '{target}' invoked via {binary_base} is not in permitted CLI whitelist"`).

3. **Empirical Verification**:
   Execute:
   - `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4d_security.py -v` (Verify all tests pass, including `test_process_tree_child_orphan_vulnerability`)
   - `.\.venv\Scripts\python.exe -m pytest tests/test_cli_sandbox.py tests/test_tool_aware_reasoning.py tests/test_challenger_m4d_affordance.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/ -q` (Full repository regression pass)

4. Write your complete handoff report to `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4d_iter2\handoff.md`.
5. Send completion message to parent via `send_message`.
