import os
import re
import shlex
import subprocess
import threading
import time
from typing import List, Optional, Set
from pydantic import BaseModel

class CLIExecutionResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    preempted: bool = False

class CLIExecutionSandbox:
    DEFAULT_TIMEOUT_S: float = 30.0
    PERMITTED_BINARIES: Set[str] = {
        "python", "python.exe",
        "pytest", "pytest.exe",
        "git", "git.exe",
        "powershell", "powershell.exe",
        "cmd", "cmd.exe"
    }
    FORBIDDEN_PATTERNS: List[str] = [
        r"\bformat\b",
        r"\brmdir\s+/[sq]\b",
        r"\bdel\s+/[sqf]\b",
        r"\bdiskpart\b",
        r"\breg\s+delete\b",
        r"\bshutdown\b",
        r"\bstop-computer\b"
    ]

    @classmethod
    def sanitize_and_tokenize(cls, command_str: str) -> List[str]:
        if not command_str or not command_str.strip():
            raise ValueError("Empty CLI command string")
        for pat in cls.FORBIDDEN_PATTERNS:
            if re.search(pat, command_str, re.IGNORECASE):
                raise PermissionError(f"Command rejected by security filter: pattern '{pat}' detected")
        tokens = shlex.split(command_str, posix=False)
        if not tokens:
            raise ValueError("Command string produced no tokens")
        binary_raw = tokens[0].strip("\"'")
        binary_base = os.path.basename(binary_raw).lower()
        if binary_base not in cls.PERMITTED_BINARIES:
            raise PermissionError(f"Binary '{binary_base}' is not in permitted CLI whitelist")
        return tokens

    @classmethod
    def execute(
        cls,
        command_str: str,
        cwd: str = "C:\\ParasiteAI",
        timeout: float = DEFAULT_TIMEOUT_S,
        cancellation_token: Optional[threading.Event] = None
    ) -> CLIExecutionResult:
        tokens = cls.sanitize_and_tokenize(command_str)
        t0 = time.perf_counter()
        proc = subprocess.Popen(
            tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            shell=False,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        preempted = False
        timed_out = False
        while True:
            ret = proc.poll()
            if ret is not None:
                break
            if cancellation_token and cancellation_token.is_set():
                preempted = True
                proc.kill()
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=0x08000000)
                break
            elapsed = time.perf_counter() - t0
            if elapsed > timeout:
                timed_out = True
                proc.kill()
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=0x08000000)
                break
            time.sleep(0.010)

        stdout, stderr = proc.communicate() if not (preempted or timed_out) else ("", "Subprocess aborted by preemption or timeout")
        t1 = time.perf_counter()
        return CLIExecutionResult(
            command=command_str,
            exit_code=-1 if (preempted or timed_out) else proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_ms=(t1 - t0) * 1000.0,
            timed_out=timed_out,
            preempted=preempted
        )

if __name__ == "__main__":
    cmd = r'python -c "print(123)"'
    tokens = shlex.split(cmd, posix=False)
    # Strip enclosing quotes for subprocess.Popen
    clean_tokens = [t[1:-1] if (t.startswith(('"', "'")) and t.endswith(('"', "'")) and len(t) >= 2) else t for t in tokens]
    print("Clean tokens:", clean_tokens)
    p = subprocess.run(clean_tokens, capture_output=True, text=True)
    print("Clean tokens run:", p.returncode, p.stdout)
    assert p.returncode == 0 and "123" in p.stdout

    # Test 2: Forbidden pattern
    try:
        CLIExecutionSandbox.execute("cmd /c rmdir /s /q testdir")
        assert False, "Should have raised PermissionError"
    except PermissionError:
        print("Test 2 Passed: Forbidden pattern blocked")

    # Test 3: Unlisted binary
    try:
        CLIExecutionSandbox.execute("notepad.exe")
        assert False, "Should have raised PermissionError"
    except PermissionError:
        print("Test 3 Passed: Unlisted binary blocked")

    # Test 4: Preemption token abort
    cancel = threading.Event()
    threading.Timer(0.05, cancel.set).start()
    res_cancel = CLIExecutionSandbox.execute("python -c \"import time; time.sleep(5)\"", cancellation_token=cancel)
    assert res_cancel.preempted
    print(f"Test 4 Passed: Preemption cancellation in {res_cancel.duration_ms:.2f} ms")
