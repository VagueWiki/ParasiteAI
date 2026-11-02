## 2026-11-01T09:21:45Z

You are Worker M4D for Phase 4 Milestone 4D (Tool-Aware Reasoning & CLI Execution Sandbox) in ParasiteAI.

Working Directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4d\
Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Reference Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md (§6, §10 Sub-Phase 4D, §12 VERIF-4, VERIF-10)
Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TASK & DELIVERABLES:
1. Implement `parasite_ai/mind/affordance.py` per Master Plan Section 6:
   - `ActionAffordance(str, Enum)`: `PHYSICAL_GUI`, `LOCAL_DEVELOPER_TOOL`, `STRATEGIC_ADVISOR`.
   - `AffordanceAssessment(BaseModel)`: `affordance: ActionAffordance`, `confidence: float`, `justification: str`, `suggested_command: Optional[str] = None`.
   - `AffordanceEvaluator`:
     - Context-aware heuristic evaluating `PHYSICAL_GUI` vs `LOCAL_DEVELOPER_TOOL` vs `STRATEGIC_ADVISOR`.
     - Priority Rule 1: Graphical Canvas / Native Drawing context (paint, gimp, photoshop, canvas, draw, sketch, brush) -> `PHYSICAL_GUI` (confidence 0.95).
     - Priority Rule 2: Application Launch Verbs (open/launch/start/switch to/bring up <target>) where target is not terminal/powershell/cmd/bash -> `PHYSICAL_GUI` (confidence 0.92) to route to `UniversalAppResolver`.
     - Priority Rule 3: Deterministic Code, Test & File Operations (refactor, run test, pytest, git commit, create file, batch replace, git push, git status) -> `LOCAL_DEVELOPER_TOOL` (confidence 0.95).
     - Default: `PHYSICAL_GUI` (confidence 0.75).
   - `CLIExecutionResult(BaseModel)`: `command: str`, `exit_code: int`, `stdout: str`, `stderr: str`, `duration_ms: float`, `timed_out: bool = False`, `preempted: bool = False`.
   - `CLIExecutionSandbox`:
     - `DEFAULT_TIMEOUT_S: float = 30.0`
     - Whitelist `PERMITTED_BINARIES`: `python`, `python.exe`, `pytest`, `pytest.exe`, `git`, `git.exe`, `powershell`, `powershell.exe`, `cmd`, `cmd.exe`.
     - Forbidden patterns (`FORBIDDEN_PATTERNS`): destructive commands (`format`, `rmdir /s`, `del /s`, `diskpart`, `reg delete`, `shutdown`, `stop-computer`) AND headless scraping/web automation tools (`curl`, `wget`, `playwright`, `puppeteer`, `selenium`, `scrapy`, `Invoke-WebRequest`, `iwr`, `Invoke-RestMethod`, `irm`, `requests`). Reject matching commands with `PermissionError`.
     - `sanitize_and_tokenize(command_str: str) -> List[str]`: uses `shlex.split(command_str, posix=False)` to preserve Windows paths, strips outer matching quotes, validates permitted binary.
     - `execute(command_str: str, cwd: str = "C:\\ParasiteAI", timeout: float = 30.0, cancellation_token: Optional[threading.Event] = None) -> CLIExecutionResult`:
       - Spawns subprocess with `shell=False` and `creationflags=0x08000000` (`CREATE_NO_WINDOW`).
       - Polls `cancellation_token` every 10ms. If set, marks `preempted=True`, kills proc, and invokes `taskkill /F /T /PID <pid>` to terminate entire process tree in <20ms.
       - Monitors timeout (default 30s). If exceeded, marks `timed_out=True`, kills proc, and invokes `taskkill /F /T /PID <pid>`.
2. Integrate with Action System & Mind:
   - Check `parasite_ai/action/types.py`: Ensure `ActionType.RUN_CLI_COMMAND` exists (or add it cleanly).
   - In `parasite_ai/action/dispatcher.py`: Support `ActionType.RUN_CLI_COMMAND` using `CLIExecutionSandbox.execute()`.
   - In `parasite_ai/mind/dual_mind.py`: Integrate affordance assessment where appropriate, or expose `AffordanceEvaluator` in mind pipeline.
3. Author Comprehensive Test Suites:
   - `tests/test_tool_aware_reasoning.py` (VERIF-4): Test affordance evaluations across canvas tasks, launch verbs, code/test refactoring tasks, and defaults.
   - `tests/test_cli_sandbox.py` (VERIF-10): Test permitted binary execution (e.g. `python -c "print('hello')"`), forbidden binary rejection (`curl`, `playwright`, `calc.exe`), destructive command rejection, quote preservation for Windows paths, timeout abort, and sub-20ms cancellation token abort via `taskkill`.
4. Verification & Regression:
   - Run: `.\.venv\Scripts\python.exe -m pytest tests/test_tool_aware_reasoning.py tests/test_cli_sandbox.py -v`
   - Run full regression: `.\.venv\Scripts\python.exe -m pytest tests/ -q`
5. Write complete handoff report to `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4d\handoff.md`.
6. Send completion message to parent via `send_message`.
