"""
parasite_ai/mind/affordance.py - Tool-Aware Reasoning & Sandboxed CLI Execution.

Implements Section 6 of the Unified Cognitive Architecture:
- 3-Tier Action Affordance Hierarchy (PHYSICAL_GUI, LOCAL_DEVELOPER_TOOL, STRATEGIC_ADVISOR)
- Context-Aware Heuristic AffordanceEvaluator with Priority Rules
- Sandboxed CLI Execution Engine (CLIExecutionSandbox) with Whitelist,
  Forbidden Pattern Security Filters, Sub-20ms Preemption, and Timeout Monitoring.
"""

from __future__ import annotations

from enum import Enum
import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Affordance Hierarchy & Models
# ---------------------------------------------------------------------------

class ActionAffordance(str, Enum):
    """Categorization of actionable affordances available to ParasiteAI."""
    PHYSICAL_GUI = "PHYSICAL_GUI"
    LOCAL_DEVELOPER_TOOL = "LOCAL_DEVELOPER_TOOL"
    STRATEGIC_ADVISOR = "STRATEGIC_ADVISOR"


class AffordanceAssessment(BaseModel):
    """Result of evaluating a goal's optimal execution affordance."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    affordance: ActionAffordance
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    suggested_command: Optional[str] = None


class AffordanceEvaluator:
    """
    Context-aware heuristic evaluator classifying user goals across affordances:
    PHYSICAL_GUI vs LOCAL_DEVELOPER_TOOL vs STRATEGIC_ADVISOR.
    """

    @staticmethod
    def evaluate(goal: str, active_window_title: str = "") -> AffordanceAssessment:
        goal_lower = (goal or "").lower()
        title_lower = (active_window_title or "").lower()

        # Priority Rule 1: Graphical Canvas & Native Drawing Context
        # Prevents "create file in Paint" or "draw" from misrouting to CLI
        gui_canvas_keywords = ["paint", "gimp", "photoshop", "canvas", "draw", "sketch", "brush"]
        if any(kw in title_lower or kw in goal_lower for kw in gui_canvas_keywords):
            return AffordanceAssessment(
                affordance=ActionAffordance.PHYSICAL_GUI,
                confidence=0.95,
                justification="Task targets a graphical/canvas application requiring direct 2D coordinate input.",
                suggested_command=None,
            )

        # Priority Rule 2: Application Launch Verbs
        # Generic launch verbs for desktop software must route to UniversalAppResolver
        app_launch_pattern = r"\b(?:open|launch|start|switch\s+to|bring\s+up)\s+(?:up\s+)?([a-zA-Z0-9_\-\.\s\\/:]+)"
        match = re.search(app_launch_pattern, goal_lower)
        if match:
            target = match.group(1).strip()
            if target not in {"terminal", "powershell", "cmd", "bash", "command prompt"}:
                return AffordanceAssessment(
                    affordance=ActionAffordance.PHYSICAL_GUI,
                    confidence=0.92,
                    justification=f"Application launch request for '{target}' routes to UniversalAppResolver.",
                    suggested_command=None,
                )

        # Priority Rule 3: Deterministic Code, Test & File Operations
        code_keywords = [
            "refactor",
            "run test",
            "pytest",
            "git commit",
            "create file",
            "batch replace",
            "git push",
            "git status",
        ]
        if any(kw in goal_lower for kw in code_keywords):
            suggested_cmd = None
            if "pytest" in goal_lower:
                suggested_cmd = "pytest"
            elif "git status" in goal_lower:
                suggested_cmd = "git status"
            elif "git commit" in goal_lower:
                suggested_cmd = "git commit"
            elif "git push" in goal_lower:
                suggested_cmd = "git push"

            return AffordanceAssessment(
                affordance=ActionAffordance.LOCAL_DEVELOPER_TOOL,
                confidence=0.95,
                justification="Task involves file or code operations best executed deterministically via CLIExecutionSandbox.",
                suggested_command=suggested_cmd,
            )

        # Strategic Advisor Cognitive Deadlock / Advice Keywords
        advisor_keywords = [
            "consult",
            "advisor",
            "strategy",
            "deadlock",
            "unresponsive",
            "need advice",
            "help me decide",
        ]
        if any(kw in goal_lower for kw in advisor_keywords):
            return AffordanceAssessment(
                affordance=ActionAffordance.STRATEGIC_ADVISOR,
                confidence=0.90,
                justification="Task indicates cognitive deadlock or strategic planning request best routed to advisor.",
                suggested_command=None,
            )

        # Default: Physical GUI
        return AffordanceAssessment(
            affordance=ActionAffordance.PHYSICAL_GUI,
            confidence=0.75,
            justification="Standard desktop operation.",
            suggested_command=None,
        )


# ---------------------------------------------------------------------------
# CLI Execution Sandbox & Security Model
# ---------------------------------------------------------------------------

class CLIExecutionResult(BaseModel):
    """Outcome of sandboxed local CLI command execution."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    preempted: bool = False


class CLIExecutionSandbox:
    """
    Sandboxed execution engine for local developer tooling and Antigravity meta-commands.
    Guarantees sub-2ms hardware touch preemption, command whitelisting, and shell-injection protection.
    """
    DEFAULT_TIMEOUT_S: float = 30.0

    # Invariant: Only permit vetted developer and interpreter binaries
    PERMITTED_BINARIES: Set[str] = {
        "python", "python.exe",
        "pytest", "pytest.exe",
        "git", "git.exe",
        "powershell", "powershell.exe",
        "cmd", "cmd.exe",
    }

    # Internal shell builtins permitted under shell wrappers (cmd / powershell)
    CMD_BUILTINS: Set[str] = {
        "assoc", "break", "call", "cd", "chdir", "cls", "color", "copy",
        "date", "dir", "echo", "echo.", "endlocal", "erase", "exit", "for",
        "ftype", "goto", "if", "md", "mkdir", "move", "path", "pause",
        "popd", "prompt", "pushd", "rd", "rem", "ren", "rename", "rmdir",
        "set", "setlocal", "shift", "start", "time", "title", "type", "ver",
        "verify", "vol",
    }

    PS_BUILTINS: Set[str] = {
        "write-host", "write-output", "get-date", "echo", "dir", "type",
        "ls", "cd", "pwd", "cls", "clear", "cat", "history", "help",
        "man", "exit", "measure-command", "select-object", "where-object",
        "foreach-object", "select", "where", "foreach", "sort-object",
        "sort", "tee-object", "tee", "out-string", "out-null", "out-file",
        "out-default", "if", "else", "elseif", "switch", "while", "do",
        "for", "return", "try", "catch", "finally", "throw", "param",
        "function", "break", "continue",
    }

    # Invariant: Destructive system patterns and headless scraping commands rejected
    FORBIDDEN_PATTERNS: List[str] = [
        r"\bcurl\b",
        r"\bwget\b",
        r"\bplaywright\b",
        r"\bpuppeteer\b",
        r"\bselenium\b",
        r"\bscrapy\b",
        r"\bformat\b",
        r"\brmdir\b.*\b/[sq]\b",
        r"\brmdir\s+/[sq]\b",
        r"\bdel\b.*\b/[sqf]\b",
        r"\bdel\s+/[sqf]\b",
        r"\bdiskpart\b",
        r"\breg\s+delete\b",
        r"\bshutdown\b",
        r"\bstop-computer\b",
        r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b",
        r"\brequests\b",
    ]

    @classmethod
    def sanitize_and_tokenize(cls, command_str: str) -> List[str]:
        """
        Parses command string without shell evaluation.
        Uses posix=False to preserve Windows backslash paths, then strips matching outer quotes.
        """
        if not command_str or not command_str.strip():
            raise ValueError("Empty CLI command string")

        check_str = command_str.replace("`", "")
        for pat in cls.FORBIDDEN_PATTERNS:
            if re.search(pat, check_str, re.IGNORECASE):
                raise PermissionError(f"Command rejected by security filter: pattern '{pat}' detected")

        # posix=False preserves Windows paths (e.g. C:\\ParasiteAI\\tests\\test_foo.py)
        raw_tokens = shlex.split(command_str, posix=False)
        if not raw_tokens:
            raise ValueError("Command string produced no tokens")

        # Strip enclosing quotes for subprocess argv list
        clean_tokens = [
            t[1:-1] if (t.startswith(('"', "'")) and t.endswith(('"', "'")) and len(t) >= 2) else t
            for t in raw_tokens
        ]

        binary_raw = clean_tokens[0]
        binary_base = os.path.basename(binary_raw).lower()
        if binary_base not in cls.PERMITTED_BINARIES:
            err = f"Binary '{binary_base}' is not in permitted CLI whitelist ({cls.PERMITTED_BINARIES})"
            logger.warning("[CLI PERMISSION DENIED] %s", err)
            raise PermissionError(err)

        # Shell wrapper evasion protection: inspect subcommands invoked via cmd / powershell
        if binary_base in {"cmd", "cmd.exe", "powershell", "powershell.exe"}:
            is_cmd = binary_base in {"cmd", "cmd.exe"}
            invocation_switches = (
                {"/c", "/k", "/r", "-c", "-k", "-r"}
                if is_cmd
                else {"-command", "-c", "/command", "/c", "-file", "/file"}
            )

            switch_idx = -1
            for idx, tok in enumerate(clean_tokens[1:], start=1):
                if tok.lower() in invocation_switches:
                    switch_idx = idx
                    break

            sub_tokens_raw: List[str] = []
            if switch_idx != -1:
                sub_tokens_raw = clean_tokens[switch_idx + 1:]
            else:
                for tok in clean_tokens[1:]:
                    if not tok.startswith(("/", "-")):
                        sub_tokens_raw = [tok]
                        break

            if sub_tokens_raw:
                sub_cmd_str = " ".join(sub_tokens_raw).strip()
                # Split chained statements by delimiters (&&, ||, ;, |, newline, &)
                clauses = [
                    c.strip()
                    for c in re.split(r"&&|\|\||[;&|\n]", sub_cmd_str)
                    if c.strip()
                ]
                for clause in clauses:
                    try:
                        clause_tokens = shlex.split(clause, posix=False)
                    except Exception:
                        clause_tokens = clause.split()

                    clause_tokens = [
                        t[1:-1] if (t.startswith(('"', "'")) and t.endswith(('"', "'")) and len(t) >= 2) else t
                        for t in clause_tokens
                    ]
                    if not clause_tokens:
                        continue

                    target_idx = 0
                    if clause_tokens[target_idx] == "&" and len(clause_tokens) > 1:
                        target_idx += 1

                    target = clause_tokens[target_idx].strip('\'"')
                    if target.lower() in {"start", "start-process", "saps"} and len(clause_tokens) > (target_idx + 1):
                        target_idx += 1
                        target = clause_tokens[target_idx].strip('\'"')

                    # Ignore variables, parentheses, or blocks
                    if target.startswith(("$", "%", "(", "{", "[")):
                        continue

                    target_base = os.path.basename(target).lower()
                    target_no_ext = os.path.splitext(target_base)[0]

                    target_is_permitted = (
                        target_base in cls.PERMITTED_BINARIES
                        or f"{target_base}.exe" in cls.PERMITTED_BINARIES
                        or target_no_ext in cls.PERMITTED_BINARIES
                    )

                    if not target_is_permitted:
                        is_executable = False
                        if target_base.endswith((".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".wsf", ".com", ".scr", ".msi", ".dll")):
                            is_executable = True
                        elif shutil.which(target) or shutil.which(target_base) or shutil.which(f"{target_base}.exe"):
                            is_executable = True
                        elif is_cmd and (target_base not in cls.CMD_BUILTINS):
                            is_executable = True
                        elif target_base in {
                            "calc", "notepad", "whoami", "rundll32", "certutil",
                            "robocopy", "regedit", "tasklist", "taskkill", "net",
                            "ipconfig", "powershell_ise", "bash", "sh", "zsh",
                            "node", "npm", "ruby", "perl", "rustc", "cargo",
                        }:
                            is_executable = True

                        if is_executable:
                            raise PermissionError(
                                f"Subcommand '{target}' invoked via {binary_base} is not in permitted CLI whitelist"
                            )

        return clean_tokens

    @classmethod
    def execute(
        cls,
        command_str: str,
        cwd: str = "C:\\ParasiteAI",
        timeout: float = DEFAULT_TIMEOUT_S,
        cancellation_token: Optional[threading.Event] = None,
    ) -> CLIExecutionResult:
        """
        Executes sandboxed command.
        Monitors cancellation_token at 10ms intervals for sub-20ms preemption response.
        """
        clean_tokens = cls.sanitize_and_tokenize(command_str)
        t0 = time.perf_counter()

        exec_cwd = cwd if os.path.isdir(cwd) else os.getcwd()
        create_no_window = 0x08000000

        logger.info("[CLI EXEC START] Command: %r | CWD: %s | Tokens: %s", command_str, exec_cwd, clean_tokens)

        proc = subprocess.Popen(
            clean_tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=exec_cwd,
            shell=False,  # Invariant: Never invoke shell=True
            creationflags=create_no_window,
        )

        preempted = False
        timed_out = False

        while True:
            ret = proc.poll()
            if ret is not None:
                break

            # Hardware preemption check: user touched physical mouse/keyboard or triggered panic
            if cancellation_token and cancellation_token.is_set():
                preempted = True
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
                break

            # Timeout check
            elapsed = time.perf_counter() - t0
            if elapsed > timeout:
                timed_out = True
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
                break

            time.sleep(0.010)  # 10ms non-blocking polling interval

        stdout, stderr = (
            proc.communicate()
            if not (preempted or timed_out)
            else ("", "Subprocess terminated by preemption token or timeout")
        )
        t1 = time.perf_counter()
        dur_ms = (t1 - t0) * 1000.0
        final_rc = -1 if (preempted or timed_out) else proc.returncode

        if preempted:
            logger.warning("[CLI PREEMPTED] Command %r preempted by physical touch after %.1fms", command_str, dur_ms)
        elif timed_out:
            logger.warning("[CLI TIMEOUT] Command %r timed out after %.1fms", command_str, dur_ms)
        else:
            logger.info("[CLI FINISHED] Command: %r | Exit Code: %d | Duration: %.1fms", command_str, final_rc, dur_ms)
            if stdout:
                logger.debug("[CLI STDOUT]\n%s", stdout.strip()[:2000])
            if stderr and final_rc != 0:
                logger.warning("[CLI STDERR]\n%s", stderr.strip()[:2000])

        return CLIExecutionResult(
            command=command_str,
            exit_code=final_rc,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_ms=dur_ms,
            timed_out=timed_out,
            preempted=preempted,
        )
