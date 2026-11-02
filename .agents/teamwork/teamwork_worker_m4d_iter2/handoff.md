# Handoff Report: Phase 4 Milestone 4D Remediation (Iteration 2)

**Agent**: Worker M4D Iteration 2  
**Role**: implementer, qa, specialist  
**Working Directory**: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4d_iter2\`  
**Date**: 2026-11-01T12:58:00Z  
**Target**: `parasite_ai/mind/affordance.py` (`CLIExecutionSandbox`)  

---

## 1. Observation

### 1.1 Process-Tree Child Orphan Defect
In `parasite_ai/mind/affordance.py` (prior lines 266–275 and 284–295):
```python
if cancellation_token and cancellation_token.is_set():
    preempted = True
    try:
        proc.kill()
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=create_no_window,
        )
    except Exception:
        pass
    break
```
Direct empirical observation:
When `proc.kill()` executed before `taskkill /F /T /PID str(proc.pid)`, the root process was immediately terminated by Win32 `TerminateProcess`. When `taskkill` subsequently attempted to query `proc.pid`, it returned code 128:
```
ERROR: The process "<pid>" not found.
```
Because the root process was already dead, `taskkill` aborted without walking the process tree (`/T`), orphaning any child processes spawned by `proc`.

### 1.2 Binary Whitelist Evasion via Shell Wrappers
In `CLIExecutionSandbox.sanitize_and_tokenize()`, `clean_tokens[0]` was checked against `PERMITTED_BINARIES` (`cmd`, `cmd.exe`, `powershell`, `powershell.exe`).
When a command was invoked as `cmd.exe /c "calc"` or `powershell.exe -Command "calc"`:
`clean_tokens[0]` was `'cmd.exe'` or `'powershell.exe'`, which was in `PERMITTED_BINARIES`.
The sandbox did not inspect arguments following `/c`, `/k`, `-c`, `-command` for unpermitted executable targets (`calc`, `notepad`, `whoami`, `rundll32`, `.exe` binaries), permitting indirect execution of arbitrary unwhitelisted binaries.

---

## 2. Logic Chain

1. **Process-Tree Child Orphan Remediation**:
   - Inverted the termination order in both the hardware preemption block and the timeout abort loop in `CLIExecutionSandbox.execute()`.
   - `taskkill /F /T /PID str(proc.pid)` now executes **first** while `proc` is still alive. Windows walks the entire process tree (`/T`) and terminates all child processes and the root process.
   - `proc.kill()` is subsequently called in a `try...except` block as a fallback.
   - Verified via `tests/test_challenger_m4d_security.py::TestPreemptionIsolationAndProcessTree::test_process_tree_child_orphan_vulnerability`: a parent Python script spawning a child process running `time.sleep(100)` is cancelled, and `tasklist` confirms `child_is_alive is False`.

2. **Shell Wrapper Whitelist Evasion Remediation**:
   - In `CLIExecutionSandbox.sanitize_and_tokenize()`, added inspection when `binary_base in {"cmd", "cmd.exe", "powershell", "powershell.exe"}`.
   - Identified invocation switches (`/c`, `/k`, `/r`, `-c`, `-k`, `-r` for `cmd`; `-command`, `-c`, `/command`, `/c`, `-file`, `/file` for `powershell`).
   - Parsed and unquoted subcommand clauses, supporting chained command operators (`&&`, `||`, `;`, `\n`, `&`) and call operators (`&`, `start`, `Start-Process`).
   - Defined `CMD_BUILTINS` (`dir`, `echo`, `type`, etc.) and `PS_BUILTINS` (`Write-Host`, `Get-Date`, etc.) to permit legitimate shell built-ins and PowerShell cmdlets while catching unpermitted executables (`calc`, `calc.exe`, `notepad.exe`, `whoami`, `rundll32`, arbitrary `.exe` binaries, and system binaries found via `shutil.which`).
   - When an unpermitted executable is detected, raises:
     ```python
     PermissionError(f"Subcommand '{target}' invoked via {binary_base} is not in permitted CLI whitelist")
     ```
   - Verified via `tests/test_challenger_m4d_security.py::TestShellMetacharactersAndChaining::test_cmd_execution_bypasses_binary_whitelist_for_unpermitted_tools` and unit suite `tests/test_cli_sandbox.py::TestShellWrapperSubcommandInspection`.

---

## 3. Caveats

- Win32 external process invocation (`taskkill.exe`) requires ~160–190ms on Windows 11 due to OS process initialization. While polling loop detection occurs within 10ms, total preemption latency is ~180–210ms rather than theoretical sub-20ms. This empirical reality is documented in `test_preemption_latency_benchmark_against_20ms_target`.
- Shell wrapper argument parsing inspects static tokens and clauses. Dynamic PowerShell constructs (e.g. `Invoke-Expression` decoding base64 strings at runtime) should be restricted by locking down PowerShell script execution policies or eliminating shell interpreters from the whitelist in locked-down production environments.

---

## 4. Conclusion

Both critical defects identified in Challenger 1's report have been remediated:
1. Process-tree child processes are terminated cleanly during preemption and timeout by invoking `taskkill /F /T /PID` before root termination, preventing child orphaning.
2. Shell wrappers (`cmd.exe /c`, `cmd /k`, `powershell.exe -Command`, etc.) inspect subcommands and block unpermitted executables (`calc`, `notepad`, `whoami`, `rundll32`, `.exe` binaries) with `PermissionError`, while preserving access to legitimate shell built-ins (`echo`, `dir`, `Get-Date`, `Write-Host`) and whitelisted developer tools (`python`, `git`, `pytest`).

---

## 5. Verification Method

Independent verification commands:

1. **Adversarial Security Suite (56 tests)**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4d_security.py -v
   ```
   *Expected: 56 passed.*

2. **Milestone 4D Core Suites (263 tests)**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_cli_sandbox.py tests/test_tool_aware_reasoning.py tests/test_challenger_m4d_affordance.py tests/test_challenger_m4d_security.py -v
   ```
   *Expected: 263 passed.*

3. **Full Repository Regression Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/ -q
   ```
   *Expected: All 1300+ passed.*

Files to inspect:
- `parasite_ai/mind/affordance.py` (Lines 173–218, 260–348, 388–424)
- `tests/test_challenger_m4d_security.py` (Lines 62–77, 398–404)
- `tests/test_cli_sandbox.py` (Lines 134–177)
