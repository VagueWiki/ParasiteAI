# Adversarial Security & Isolation Challenge Report (Milestone 4D)

**Date**: 2026-11-01T12:48:00Z  
**Agent**: Challenger 1 (Replacement) — Empirical Challenger  
**Role**: critic, specialist  
**Target**: `CLIExecutionSandbox` (`parasite_ai/mind/affordance.py`)  
**Verdict**: **`REQUEST_CHANGES`**

---

## 1. Observation

### 1.1 Process-Tree Child Orphan Leak (`parasite_ai/mind/affordance.py`)
In `CLIExecutionSandbox.execute()`, preemption and timeout handling is coded at lines 264–278 and 281–296 as follows:
```python
264:             if cancellation_token and cancellation_token.is_set():
265:                 preempted = True
266:                 try:
267:                     proc.kill()
268:                 except Exception:
269:                     pass
270:                 try:
271:                     subprocess.run(
272:                         ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
273:                         capture_output=True,
274:                         creationflags=create_no_window,
275:                     )
276:                 except Exception:
277:                     pass
278:                 break
```
Direct empirical observation of this execution sequence:
When `proc.kill()` executes at line 267, Windows terminates the root process handle immediately. When `subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)])` runs at line 271, `taskkill` queries for `proc.pid` and fails:
```
taskkill err: ERROR: The process "<pid>" not found.
taskkill returncode: 128
```
Because the root process was already terminated by `proc.kill()`, `taskkill` halts with return code 128 and never walks the process tree (`/T`). Consequently, any child processes spawned by `proc` are orphaned and continue executing in the background.

Empirical verification via `tests/test_challenger_m4d_security.py::TestPreemptionIsolationAndProcessTree::test_process_tree_child_orphan_vulnerability`:
- A parent Python process spawned a child `python.exe -c "import time; time.sleep(100)"` and wrote the child PID to a marker file.
- The parent was preempted via `cancellation_token`.
- Inspection via `tasklist /FI "PID eq <child_pid>"` confirmed:
```
is p2 alive?: True
```
The child process remained alive and had to be manually reaped.

### 1.2 Binary Whitelist Bypass via Shell Wrapper (`cmd.exe /c`, `powershell.exe -Command`)
In `parasite_ai/mind/affordance.py`:
Lines 165–171:
```python
    PERMITTED_BINARIES: Set[str] = {
        "python", "python.exe",
        "pytest", "pytest.exe",
        "git", "git.exe",
        "powershell", "powershell.exe",
        "cmd", "cmd.exe",
    }
```
Lines 218–223:
```python
    binary_raw = clean_tokens[0]
    binary_base = os.path.basename(binary_raw).lower()
    if binary_base not in cls.PERMITTED_BINARIES:
        raise PermissionError(
            f"Binary '{binary_base}' is not in permitted CLI whitelist ({cls.PERMITTED_BINARIES})"
        )
```
When an unpermitted binary is executed directly (e.g. `calc.exe`, `notepad.exe`), it is rejected with `PermissionError`.
However, if wrapped as `cmd.exe /c "calc"` or `cmd /c notepad` or `powershell.exe -Command "calc"`:
`clean_tokens[0]` is `'cmd.exe'` or `'powershell.exe'`, which matches `PERMITTED_BINARIES`.
The sandbox does not inspect `clean_tokens[1:]` for unpermitted executable targets.
Direct empirical observation via `TestShellMetacharactersAndChaining::test_cmd_execution_bypasses_binary_whitelist_for_unpermitted_tools`:
`CLIExecutionSandbox.sanitize_and_tokenize('cmd.exe /c "calc"')` returns `['cmd.exe', '/c', 'calc']` with 0 errors.

### 1.3 Latency Divergence on `<20ms` Preemption Specification
Master Plan §6.4, §10 Sub-Phase 4D, and §12 VERIF-10 mandate:
> *"cancellation token aborts running subprocess tree in < 20 ms."*

Direct benchmark measurement of `taskkill` process execution on Windows 11:
- `proc.kill()` (Win32 TerminateProcess on open handle): ~0.11ms
- `subprocess.run(["taskkill", "/F", "/T", "/PID", ...])`: 161.2ms – 192.3ms
- Polling loop latency: 10.0ms (`time.sleep(0.010)`)
- Total latency from `cancellation_token.set()` to `execute()` return: 185ms – 215ms.
Spawning an external Win32 executable (`taskkill.exe`) cannot physically complete within 20ms on Windows (typical OS process initialization requires 50–180ms).

### 1.4 PowerShell Alias and Escape Surface
- Direct aliases `iwr`, `irm`, `Invoke-WebRequest`, `Invoke-RestMethod` and case variations (`cUrL`, `pLaYwRiGhT`, `wGeT`, `SeLeNiUm`, `sCrApY`, `rEqUeStS`) are 100% caught by `re.IGNORECASE` regex.
- However, PowerShell backtick syntax (e.g. `powershell -Command i`wr http://...`) evades static regex `\biwr\b` while resolving to `iwr` inside PowerShell runtime.

### 1.5 Execution of Standalone Adversarial Suite
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4d_security.py -v
```
Result:
```
============================= 56 passed in 4.72s ==============================
```

---

## 2. Logic Chain

1. **Child Process Orphan Vulnerability**:
   - `CLIExecutionSandbox.execute` issues `proc.kill()` before `taskkill /F /T /PID str(proc.pid)`.
   - `proc.kill()` terminates the process associated with `proc.pid`.
   - `taskkill` requires the target process to be alive to query its process tree.
   - Calling `proc.kill()` first guarantees `taskkill` fails with `ERROR: The process not found`.
   - As a direct consequence, any background subprocesses spawned by the target (compilers, test runners, child python scripts) leak and persist indefinitely, violating the sub-20ms process-tree isolation invariant.
   - **Fix**: Invert execution order: call `taskkill /F /T /PID str(proc.pid)` FIRST while `proc` is alive, then call `proc.kill()` as fallback. Alternatively, bind child processes to a Win32 Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.

2. **Whitelist Evasion**:
   - `PERMITTED_BINARIES` includes shell interpreters (`cmd.exe`, `powershell.exe`).
   - The whitelist validation checks only `clean_tokens[0]`.
   - Any executable forbidden by the whitelist (e.g., `calc.exe`, `whoami.exe`, `rundll32.exe`) can be executed by invoking it through `cmd.exe /c <executable>` or `powershell -Command <executable>`.
   - **Fix**: Remove `cmd` and `powershell` from `PERMITTED_BINARIES`, or restrict `cmd` and `powershell` invocation arguments strictly to vetted internal helper scripts.

3. **Preemption Latency Claim Invalidation**:
   - Spawning `taskkill.exe` takes ~170ms on Windows.
   - VERIF-10 pass criterion specifies: "cancellation token aborts running subprocess tree in < 20 ms."
   - The current implementation takes ~200ms.
   - **Fix**: Update the specification in VERIF-10 to reflect realistic Windows process spawning latency (<300ms), OR replace external `taskkill.exe` invocation with a native Win32 Job Object handle termination (`TerminateJobObject`), which executes in <1ms without spawning external binaries.

---

## 3. Caveats

- Tests were run on Windows 11 64-bit environment using Python 3.12.13 in `C:\ParasiteAI\.venv`.
- Single-process commands (commands that do not spawn child subprocesses) are cleanly terminated by `proc.kill()`. The child leak vulnerability specifically affects commands that spawn sub-subprocesses (e.g., build scripts, `pytest -n auto`, or multi-process Python tools).
- No implementation code was modified in `parasite_ai/`, adhering strictly to the `Review-only` constraint.

---

## 4. Conclusion

**Verdict: `REQUEST_CHANGES`**

While `CLIExecutionSandbox` successfully enforces case-insensitive pattern blocking (`cUrL`, `pLaYwRiGhT`, `wGeT`, `SeLeNiUm`), blocks direct path obfuscations (`C:\Windows\System32\calc.exe`), and safely executes non-shell commands without parameter injection via `shell=False`, two concrete remediation items must be resolved:
1. **Critical**: Invert the termination sequence in `CLIExecutionSandbox.execute` so `taskkill /F /T /PID` is invoked before `proc.kill()`, preventing child process orphaning on cancellation and timeout.
2. **Security**: Address the binary whitelist bypass allowing unpermitted executables to be invoked via `cmd.exe /c` and `powershell.exe -Command`.
3. **Spec Alignment**: Align the VERIF-10 `<20ms` requirement with the empirical reality of `taskkill.exe` process creation (~180ms), or implement Win32 Job Object termination.

---

## 5. Verification Method

To independently reproduce all observations and verify findings:

1. Run the standalone adversarial suite:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4d_security.py -v
   ```
2. Verify child process orphan leak reproduction specifically:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4d_security.py -k "test_process_tree_child_orphan_vulnerability" -v -s
   ```
3. Inspect `parasite_ai/mind/affordance.py` lines 266–275 and 284–295.
