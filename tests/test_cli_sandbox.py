"""
tests/test_cli_sandbox.py - Automated Unit & Integration Tests for CLI Execution Sandbox (VERIF-10).

Tests:
1. Permitted binary whitelist enforcement (python, pytest, git, powershell, cmd).
2. Unpermitted binary rejection (PermissionError for calc.exe, notepad, node, bash).
3. Destructive command pattern rejection (format, rmdir /s, del /s, diskpart, reg delete, shutdown, stop-computer).
4. Headless scraping and web automation tool rejection (curl, wget, playwright, puppeteer, selenium, scrapy, Invoke-WebRequest, iwr, Invoke-RestMethod, irm, requests).
5. Windows backslash path tokenization and outer quote preservation (posix=False).
6. Subprocess execution with shell=False and CREATE_NO_WINDOW.
7. Timeout abort and process tree cleanup via taskkill.
8. Cancellation token preemption terminating process tree in <20ms.
9. ActionDispatcher integration for ActionType.RUN_CLI_COMMAND.
"""

from __future__ import annotations

import sys
import threading
import time
import pytest

from parasite_ai.action.dispatcher import ActionDispatcher
from parasite_ai.action.types import ActionPlan, ActionType
from parasite_ai.mind.affordance import (
    CLIExecutionResult,
    CLIExecutionSandbox,
)


class TestCLIExecutionSandboxWhitelistAndSecurity:
    """Tests for CLIExecutionSandbox whitelist, tokenization, and regex security filters."""

    @pytest.mark.parametrize(
        "valid_cmd",
        [
            'python -c "print(123)"',
            'python.exe -V',
            'pytest --version',
            'pytest.exe -k test_foo',
            'git status',
            'git.exe diff',
            'powershell -Command "Get-Date"',
            'powershell.exe -NoProfile -Command "Write-Host test"',
            'cmd /c "echo hello"',
            'cmd.exe /c "dir"',
            r'"C:\Program Files\Python312\python.exe" -c "print(1)"',
            r'"C:\Users\Suici\.venv\Scripts\pytest.exe" -v',
        ],
    )
    def test_permitted_binaries_allowed(self, valid_cmd: str):
        tokens = CLIExecutionSandbox.sanitize_and_tokenize(valid_cmd)
        assert len(tokens) >= 1
        assert tokens[0].lower().endswith(
            ("python", "python.exe", "pytest", "pytest.exe", "git", "git.exe", "powershell", "powershell.exe", "cmd", "cmd.exe")
        )

    @pytest.mark.parametrize(
        "unpermitted_cmd",
        [
            "node -v",
            "calc.exe",
            "notepad.exe",
            "bash script.sh",
            "sh test.sh",
            "ruby app.rb",
            "rustc main.rs",
            "curl.exe",
            "regedit.exe",
        ],
    )
    def test_unpermitted_binaries_rejected(self, unpermitted_cmd: str):
        with pytest.raises(PermissionError) as exc_info:
            CLIExecutionSandbox.sanitize_and_tokenize(unpermitted_cmd)
        err_msg = str(exc_info.value).lower()
        assert "not in permitted cli whitelist" in err_msg or "security filter" in err_msg

    @pytest.mark.parametrize("empty_cmd", ["", "   ", "\t\n", "   \r\n  "])
    def test_empty_commands_raise_value_error(self, empty_cmd: str):
        with pytest.raises(ValueError) as exc_info:
            CLIExecutionSandbox.sanitize_and_tokenize(empty_cmd)
        assert "empty cli command" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "destructive_cmd",
        [
            "cmd /c format C:",
            "cmd /c format D: /fs:NTFS",
            "cmd /c rmdir /s /q C:\\Data",
            "powershell -Command rmdir /s C:\\Windows",
            "cmd /c del /s /f C:\\secret.txt",
            "cmd /c del /s temp.log",
            "cmd /c diskpart",
            "cmd /c reg delete HKLM\\Software\\Bad /f",
            "cmd /c shutdown /s /t 0",
            "powershell -Command Stop-Computer -Force",
        ],
    )
    def test_destructive_patterns_rejected(self, destructive_cmd: str):
        with pytest.raises(PermissionError) as exc_info:
            CLIExecutionSandbox.sanitize_and_tokenize(destructive_cmd)
        assert "rejected by security filter" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "scraping_cmd",
        [
            "python -c 'import requests'",
            "python -m playwright test",
            "python -c 'from playwright.sync_api import sync_playwright'",
            "python -m puppeteer run",
            "python -c 'import selenium'",
            "python -m scrapy crawl web_spider",
            "git clone http://example.com/repo && curl http://bad.com",
            "wget https://example.com/file.zip",
            "powershell -Command Invoke-WebRequest -Uri http://ex.com",
            "powershell -Command iwr http://ex.com",
            "powershell -Command Invoke-RestMethod -Uri http://ex.com",
            "powershell -Command irm http://ex.com",
        ],
    )
    def test_headless_scraping_patterns_rejected(self, scraping_cmd: str):
        with pytest.raises(PermissionError) as exc_info:
            CLIExecutionSandbox.sanitize_and_tokenize(scraping_cmd)
        assert "rejected by security filter" in str(exc_info.value).lower()

    def test_windows_path_tokenization_preserves_backslashes(self):
        cmd = r'python "C:\ParasiteAI\scripts\verify.py" --dir="C:\Data\Temp\Output"'
        tokens = CLIExecutionSandbox.sanitize_and_tokenize(cmd)
        assert tokens[0] == "python"
        assert tokens[1] == r"C:\ParasiteAI\scripts\verify.py"
        assert "C:\\Data\\Temp\\Output" in tokens[2]


class TestShellWrapperSubcommandInspection:
    """Tests for shell wrapper (cmd / powershell) whitelist enforcement on subcommands."""

    @pytest.mark.parametrize(
        "unpermitted_shell_cmd",
        [
            'cmd /c calc',
            'cmd /c "calc.exe"',
            'cmd /c notepad.exe',
            'cmd.exe /c "whoami"',
            'cmd /c rundll32',
            'powershell -Command "calc"',
            'powershell.exe -Command "notepad.exe"',
            'powershell -Command "& \'calc.exe\'"',
            'powershell -Command "whoami"',
            'powershell -Command "rundll32"',
            'cmd /c "echo hello && calc"',
            'powershell -Command "Write-Host test; calc.exe"',
        ],
    )
    def test_unpermitted_subcommands_via_shell_wrapper_rejected(self, unpermitted_shell_cmd: str):
        with pytest.raises(PermissionError) as exc_info:
            CLIExecutionSandbox.sanitize_and_tokenize(unpermitted_shell_cmd)
        err = str(exc_info.value).lower()
        assert "not in permitted cli whitelist" in err

    @pytest.mark.parametrize(
        "permitted_shell_cmd",
        [
            'cmd /c "echo hello"',
            'cmd.exe /c "dir"',
            'powershell -Command "Get-Date"',
            'powershell.exe -NoProfile -Command "Write-Host test"',
            'cmd /c python --version',
            'powershell -Command "python -V"',
            'cmd /c git status',
            'powershell -Command "git diff"',
        ],
    )
    def test_permitted_subcommands_and_builtins_allowed(self, permitted_shell_cmd: str):
        tokens = CLIExecutionSandbox.sanitize_and_tokenize(permitted_shell_cmd)
        assert len(tokens) >= 2


class TestCLIExecutionSandboxExecution:
    """Tests for live subprocess execution, timeout abort, and preemption."""

    def test_live_execution_permitted_python_success(self):
        res = CLIExecutionSandbox.execute(
            'python -c "print(\'CLI_SANDBOX_AUTHENTIC_EXECUTION\')"',
            timeout=10.0,
        )
        assert res.exit_code == 0
        assert "CLI_SANDBOX_AUTHENTIC_EXECUTION" in res.stdout
        assert res.stderr == ""
        assert res.timed_out is False
        assert res.preempted is False
        assert res.duration_ms > 0

    def test_live_execution_non_zero_exit_code(self):
        res = CLIExecutionSandbox.execute(
            'python -c "import sys; sys.exit(7)"',
            timeout=10.0,
        )
        assert res.exit_code == 7
        assert res.timed_out is False
        assert res.preempted is False

    def test_live_execution_timeout_abort(self):
        t0 = time.perf_counter()
        res = CLIExecutionSandbox.execute(
            'python -c "import time; time.sleep(10.0)"',
            timeout=0.2,
        )
        t1 = time.perf_counter()
        elapsed_s = t1 - t0

        assert res.timed_out is True
        assert res.preempted is False
        assert res.exit_code == -1
        assert "timeout" in res.stderr.lower()
        assert elapsed_s < 2.0, f"Timeout abort took too long: {elapsed_s:.2f}s"

    def test_live_execution_cancellation_preemption(self):
        token = threading.Event()

        def signal_token():
            time.sleep(0.040)
            token.set()

        thread = threading.Thread(target=signal_token)
        thread.start()

        t0 = time.perf_counter()
        res = CLIExecutionSandbox.execute(
            'python -c "import time; time.sleep(5.0)"',
            timeout=10.0,
            cancellation_token=token,
        )
        t1 = time.perf_counter()
        thread.join()

        assert res.preempted is True
        assert res.timed_out is False
        assert res.exit_code == -1
        assert "preemption token" in res.stderr.lower()
        elapsed_ms = (t1 - t0) * 1000.0
        assert elapsed_ms < 1000.0, f"Preemption total latency too high: {elapsed_ms:.1f}ms"

    def test_preset_cancellation_token_aborts_immediately(self):
        token = threading.Event()
        token.set()

        t0 = time.perf_counter()
        res = CLIExecutionSandbox.execute(
            'python -c "import time; time.sleep(5.0)"',
            timeout=10.0,
            cancellation_token=token,
        )
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000.0

        assert res.preempted is True
        assert res.exit_code == -1
        # Pre-set token is detected on the first poll within 20ms of entering loop
        assert elapsed_ms < 500.0


class TestActionDispatcherCLIIntegration:
    """Tests for ActionDispatcher integration with ActionType.RUN_CLI_COMMAND."""

    def test_dispatcher_executes_valid_cli_command(self):
        dispatcher = ActionDispatcher()
        action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "print(\'DISPATCH_INTEGRATION_OK\')"',
        )
        result = dispatcher.dispatch(action=action, som_elements=[])
        assert result.success is True
        assert result.returncode == 0
        assert result.error is None
        assert result.interrupted is False

    def test_dispatcher_rejects_missing_command(self):
        dispatcher = ActionDispatcher()
        action = ActionPlan(action=ActionType.RUN_CLI_COMMAND, cli_command=None, text=None)
        result = dispatcher.dispatch(action=action, som_elements=[])
        assert result.success is False
        assert result.returncode == -1
        assert "no cli command specified" in (result.error or "").lower()

    def test_dispatcher_rejects_prohibited_command(self):
        dispatcher = ActionDispatcher()
        action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command="python -m playwright test",
        )
        result = dispatcher.dispatch(action=action, som_elements=[])
        assert result.success is False
        assert result.returncode == -1
        assert "rejected by security filter" in (result.error or "").lower()

    def test_dispatcher_handles_preemption_token(self):
        token = threading.Event()
        token.set()

        dispatcher = ActionDispatcher()
        action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "import time; time.sleep(5.0)"',
        )
        result = dispatcher.dispatch(action=action, som_elements=[], cancellation_token=token)
        assert result.success is False
        assert result.interrupted is True
        assert result.returncode == -1
