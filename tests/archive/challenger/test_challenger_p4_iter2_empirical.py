"""
tests/test_challenger_p4_iter2_empirical.py - Empirical Adversarial Verification Suite
Authored by Challenger 2 (Iter 2: Hardware Preemption, CLI Sandbox & App Resolver).

Verifies the 4 remediated deficiencies in phase_4_master_plan.md:
1. VULN-1: ActionType.RUN_CLI_COMMAND evaluated strictly by returncode == 0 without requiring visual ROI diff (Delta >= 0.02).
2. VULN-2: CLIExecutionSandbox complete specification (timeout 30.0s, 10ms cancellation_token polling, whitelist, injection filtering, process tree kill).
3. VULN-3: UniversalAppResolver Tier 3 (Win+R) dead-code loop resolved with attempt counters (_start_search_attempts, _run_dialog_attempts).
4. VULN-4: UniversalAppResolver Tier 1 substring collision eliminated via PrecisionAppMatcher with word boundaries, exact match, and destructive verb disqualification.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
import time
from enum import Enum
from typing import Any, List, Optional, Set, Tuple
import pytest
from pydantic import BaseModel, Field

from parasite_ai.ui.types import UIElement


# ===========================================================================
# Reference Implementations directly extracted from phase_4_master_plan.md
# ===========================================================================

class CadenceTier(str, Enum):
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_CONSULT = "TIER_2_CONSULT"
    TIER_3_GUIDED = "TIER_3_GUIDED"
    TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
    USER_OVERRIDE = "USER_OVERRIDE"


class Phase4ActionType(str, Enum):
    """Phase 4 Section 9.1 ActionType inventory."""
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    CLICK_AND_TYPE = "CLICK_AND_TYPE"
    TYPE = "TYPE"
    HOTKEY = "HOTKEY"
    SCROLL = "SCROLL"
    WAIT = "WAIT"
    PANIC = "PANIC"
    OFFLOAD_WEB_AI = "OFFLOAD_WEB_AI"
    DONE = "DONE"
    RUN_CLI_COMMAND = "RUN_CLI_COMMAND"


class MasterPlanEscalationStateMachine(BaseModel):
    """Section 3.3 implementation from phase_4_master_plan.md."""
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0)
    guided_strikes: int = Field(default=0, ge=0)
    copilot_strikes: int = Field(default=0, ge=0)
    consultation_failures: int = Field(default=0, ge=0)
    total_escalation_cycles: int = Field(default=0, ge=0)
    max_escalation_cycles: int = Field(default=3)
    max_consultation_failures: int = Field(default=2)

    def on_action_result(
        self,
        success: bool,
        screen_diff: float = 0.0,
        action_type: Optional[Phase4ActionType] = None,
        is_interactive: bool = True,
        cli_returncode: Optional[int] = None,
        diff_threshold: float = 0.02,
    ) -> CadenceTier:
        # Category 1: Headless CLI actions
        if action_type == Phase4ActionType.RUN_CLI_COMMAND:
            effective_success = success and (cli_returncode == 0 if cli_returncode is not None else True)

        # Category 2: Passive / Non-visual actions
        elif action_type in (Phase4ActionType.WAIT, Phase4ActionType.DONE) or not is_interactive:
            if success:
                return self.current_tier
            effective_success = False

        # Category 3: Interactive GUI actions
        else:
            effective_success = success and (screen_diff >= diff_threshold)

        if self.current_tier == CadenceTier.TIER_1_LOCAL:
            if effective_success:
                self.local_strikes = 0
            else:
                self.local_strikes += 1
                if self.local_strikes >= 2:
                    self.current_tier = CadenceTier.TIER_2_CONSULT

        elif self.current_tier == CadenceTier.TIER_3_GUIDED:
            if effective_success:
                self.guided_strikes = 0
            else:
                self.guided_strikes += 1
                if self.guided_strikes >= 2:
                    self.total_escalation_cycles += 1
                    if self.total_escalation_cycles >= self.max_escalation_cycles:
                        self.current_tier = CadenceTier.USER_OVERRIDE
                    else:
                        self.current_tier = CadenceTier.TIER_4_CO_PILOT
                        self.copilot_strikes = 0

        elif self.current_tier == CadenceTier.TIER_4_CO_PILOT:
            if effective_success:
                self.copilot_strikes = 0
                self.guided_strikes = 0
                self.current_tier = CadenceTier.TIER_3_GUIDED
            else:
                self.copilot_strikes += 1
                if self.copilot_strikes >= 3:
                    self.current_tier = CadenceTier.USER_OVERRIDE

        return self.current_tier

    def on_consultation_success(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.guided_strikes = 0
            self.consultation_failures = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.consultation_failures += 1
            if self.consultation_failures >= self.max_consultation_failures:
                self.current_tier = CadenceTier.USER_OVERRIDE
            else:
                self.local_strikes = 0
                self.current_tier = CadenceTier.TIER_1_LOCAL

    def on_hardware_interrupt(self) -> None:
        self.current_tier = CadenceTier.USER_OVERRIDE


class MasterPlanCLIExecutionResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    preempted: bool = False


class MasterPlanCLIExecutionSandbox:
    """Section 6.4 implementation from phase_4_master_plan.md."""
    DEFAULT_TIMEOUT_S: float = 30.0

    PERMITTED_BINARIES: Set[str] = {
        "python", "python.exe",
        "pytest", "pytest.exe",
        "git", "git.exe",
        "powershell", "powershell.exe",
        "cmd", "cmd.exe",
    }

    FORBIDDEN_PATTERNS: List[str] = [
        r"\bcurl\b",
        r"\bwget\b",
        r"\bplaywright\b",
        r"\bpuppeteer\b",
        r"\bselenium\b",
        r"\bscrapy\b",
        r"\bformat\b",
        r"\brmdir\s+/[sq]\b",
        r"\bdel\s+/[sqf]\b",
        r"\bdiskpart\b",
        r"\breg\s+delete\b",
        r"\bshutdown\b",
        r"\bstop-computer\b",
    ]

    @classmethod
    def sanitize_and_tokenize(cls, command_str: str) -> List[str]:
        if not command_str or not command_str.strip():
            raise ValueError("Empty CLI command string")

        for pat in cls.FORBIDDEN_PATTERNS:
            if re.search(pat, command_str, re.IGNORECASE):
                raise PermissionError(f"Command rejected by security filter: pattern '{pat}' detected")

        raw_tokens = shlex.split(command_str, posix=False)
        if not raw_tokens:
            raise ValueError("Command string produced no tokens")

        clean_tokens = [
            t[1:-1] if (t.startswith(('"', "'")) and t.endswith(('"', "'")) and len(t) >= 2) else t
            for t in raw_tokens
        ]

        binary_raw = clean_tokens[0]
        binary_base = os.path.basename(binary_raw).lower()
        if binary_base not in cls.PERMITTED_BINARIES:
            raise PermissionError(
                f"Binary '{binary_base}' is not in permitted CLI whitelist ({cls.PERMITTED_BINARIES})"
            )

        return clean_tokens

    @classmethod
    def execute(
        cls,
        command_str: str,
        cwd: str = "C:\\ParasiteAI",
        timeout: float = DEFAULT_TIMEOUT_S,
        cancellation_token: Optional[threading.Event] = None,
    ) -> MasterPlanCLIExecutionResult:
        clean_tokens = cls.sanitize_and_tokenize(command_str)
        t0 = time.perf_counter()

        proc = subprocess.Popen(
            clean_tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            shell=False,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
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
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                )
                break

            elapsed = time.perf_counter() - t0
            if elapsed > timeout:
                timed_out = True
                proc.kill()
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                )
                break

            time.sleep(0.010)

        stdout, stderr = (
            proc.communicate()
            if not (preempted or timed_out)
            else ("", "Subprocess terminated by preemption token or timeout")
        )
        t1 = time.perf_counter()

        return MasterPlanCLIExecutionResult(
            command=command_str,
            exit_code=-1 if (preempted or timed_out) else proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_ms=(t1 - t0) * 1000.0,
            timed_out=timed_out,
            preempted=preempted,
        )


class MasterPlanPrecisionAppMatcher:
    """Section 8.3 implementation from phase_4_master_plan.md."""
    NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}
    PREFERRED_ROLES = {
        "button", "listitem", "menuitem", "hyperlink", "image",
        "pane", "icon", "treeitem", "tabitem", "window"
    }

    @classmethod
    def score_match(cls, label: str, target: str) -> float:
        l_norm = label.strip().lower()
        t_norm = target.strip().lower()
        if not l_norm or not t_norm:
            return 0.0

        if l_norm == t_norm:
            return 1.0

        tokens = re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", l_norm)
        if not tokens:
            return 0.0

        if any(v in tokens for v in cls.NEGATIVE_VERBS):
            return 0.0

        if (
            l_norm.startswith(t_norm + " ")
            or l_norm.startswith(t_norm + " -")
            or l_norm.startswith(t_norm + ":")
        ):
            return 0.95

        pattern = r"\b" + re.escape(t_norm) + r"\b"
        if re.search(pattern, l_norm, re.IGNORECASE):
            idx = l_norm.find(t_norm)
            pos_ratio = max(0.0, 1.0 - (idx / max(1, len(l_norm))))
            return 0.80 + (0.10 * pos_ratio)

        return 0.0

    @classmethod
    def find_best_element(
        cls, target: str, elements: List[UIElement], threshold: float = 0.80
    ) -> Optional[Tuple[UIElement, float]]:
        candidates = []
        for elem in elements:
            role = (elem.role or "").lower()
            if not any(r in role for r in cls.PREFERRED_ROLES):
                continue
            score = cls.score_match(elem.label or "", target)
            if score >= threshold:
                candidates.append((elem, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]


class ActionPlan(BaseModel):
    action: Phase4ActionType
    keys: List[str] = Field(default_factory=list)
    text: Optional[str] = None
    target_element_id: Optional[int] = None
    submit: bool = False
    wait_ms: int = 0
    reason: Optional[str] = None


class MasterPlanUniversalAppResolver:
    """Section 8.2 implementation from phase_4_master_plan.md."""
    def __init__(self):
        self._target_app: Optional[str] = None
        self._start_search_attempts: int = 0
        self._search_opened: bool = False
        self._run_dialog_attempts: int = 0
        self._run_opened: bool = False

    def reset_state(self, app_name: str) -> None:
        self._target_app = app_name
        self._start_search_attempts = 0
        self._search_opened = False
        self._run_dialog_attempts = 0
        self._run_opened = False

    def resolve_launch_action(self, target_app: str, elements: List[UIElement]) -> ActionPlan:
        if self._target_app != target_app:
            self.reset_state(target_app)

        # Tier 1: Check visible grounded controls via PrecisionAppMatcher
        best = MasterPlanPrecisionAppMatcher.find_best_element(target_app, elements)
        if best:
            elem, _score = best
            self.reset_state(target_app)
            return ActionPlan(action=Phase4ActionType.CLICK, target_element_id=elem.id)

        # Tier 2: Windows Start Search Chord
        if self._start_search_attempts == 0:
            if not self._search_opened:
                self._search_opened = True
                return ActionPlan(action=Phase4ActionType.HOTKEY, keys=["win"], wait_ms=250)
            else:
                self._search_opened = False
                self._start_search_attempts = 1
                return ActionPlan(action=Phase4ActionType.TYPE, text=f"{target_app}\n", submit=True)

        # Tier 3: Windows Run Dialog Fallback
        if self._run_dialog_attempts == 0:
            if not self._run_opened:
                self._run_opened = True
                return ActionPlan(action=Phase4ActionType.HOTKEY, keys=["win", "r"], wait_ms=250)
            else:
                self._run_opened = False
                self._run_dialog_attempts = 1
                return ActionPlan(action=Phase4ActionType.TYPE, text=f"{target_app}\n", submit=True)

        # Both tiers exhausted cleanly: yield to cognitive replanning
        return ActionPlan(action=Phase4ActionType.WAIT, reason=f"App resolution exhausted for '{target_app}'")


# ===========================================================================
# Empirical Adversarial Test Suites
# ===========================================================================

class TestVuln1ActionAwareStrikeEvaluation:
    """VULN-1: Action-Aware Evaluation for Headless CLI vs GUI vs Passive."""

    def test_cli_success_with_zero_screen_diff_resets_strikes(self):
        fsm = MasterPlanEscalationStateMachine()
        fsm.local_strikes = 1

        tier = fsm.on_action_result(
            success=True,
            screen_diff=0.000,
            action_type=Phase4ActionType.RUN_CLI_COMMAND,
            cli_returncode=0,
        )
        assert tier == CadenceTier.TIER_1_LOCAL
        assert fsm.local_strikes == 0, "CLI exit 0 with 0.0 screen diff must reset local_strikes to 0"

    def test_cli_failure_with_nonzero_returncode_increments_strikes(self):
        fsm = MasterPlanEscalationStateMachine()
        assert fsm.local_strikes == 0

        # Attempt 1 fails
        tier1 = fsm.on_action_result(
            success=False,
            screen_diff=0.000,
            action_type=Phase4ActionType.RUN_CLI_COMMAND,
            cli_returncode=1,
        )
        assert tier1 == CadenceTier.TIER_1_LOCAL
        assert fsm.local_strikes == 1

        # Attempt 2 fails -> transition to TIER_2_CONSULT
        tier2 = fsm.on_action_result(
            success=False,
            screen_diff=0.000,
            action_type=Phase4ActionType.RUN_CLI_COMMAND,
            cli_returncode=2,
        )
        assert tier2 == CadenceTier.TIER_2_CONSULT
        assert fsm.local_strikes == 2

    def test_passive_action_exempt_from_visual_diff(self):
        fsm = MasterPlanEscalationStateMachine()
        fsm.local_strikes = 1

        tier = fsm.on_action_result(
            success=True,
            screen_diff=0.000,
            action_type=Phase4ActionType.WAIT,
        )
        assert tier == CadenceTier.TIER_1_LOCAL
        assert fsm.local_strikes == 1, "Successful passive action must leave strike counter unchanged"

    def test_interactive_gui_action_evaluated_by_roi_diff(self):
        fsm = MasterPlanEscalationStateMachine()

        # GUI action with diff 0.015 (< 0.02) triggers strike
        tier1 = fsm.on_action_result(
            success=True,
            screen_diff=0.015,
            action_type=Phase4ActionType.CLICK,
            diff_threshold=0.02,
        )
        assert tier1 == CadenceTier.TIER_1_LOCAL
        assert fsm.local_strikes == 1

        # GUI action with diff 0.025 (>= 0.02) resets strike
        tier2 = fsm.on_action_result(
            success=True,
            screen_diff=0.025,
            action_type=Phase4ActionType.CLICK,
            diff_threshold=0.02,
        )
        assert tier2 == CadenceTier.TIER_1_LOCAL
        assert fsm.local_strikes == 0

    def test_tier_3_guided_cli_success_advances_step(self):
        fsm = MasterPlanEscalationStateMachine(current_tier=CadenceTier.TIER_3_GUIDED)
        fsm.guided_strikes = 1

        tier = fsm.on_action_result(
            success=True,
            screen_diff=0.000,
            action_type=Phase4ActionType.RUN_CLI_COMMAND,
            cli_returncode=0,
        )
        assert tier == CadenceTier.TIER_3_GUIDED
        assert fsm.guided_strikes == 0, "CLI exit 0 in Tier 3 must reset guided_strikes"


class TestVuln2CLIExecutionSandbox:
    """VULN-2: CLIExecutionSandbox Security, Tokenization, Preemption & Timeout."""

    def test_permitted_binaries_allowed(self):
        valid_commands = [
            'python -c "print(123)"',
            'pytest --version',
            'git status',
            'powershell -Command "Get-Date"',
            'cmd /c "echo hello"',
        ]
        for cmd in valid_commands:
            tokens = MasterPlanCLIExecutionSandbox.sanitize_and_tokenize(cmd)
            assert len(tokens) >= 1

    def test_unpermitted_binaries_rejected(self):
        bad_commands = [
            "node -v",
            "bash script.sh",
            "sh test.sh",
            "notepad.exe",
            "calc.exe",
        ]
        for cmd in bad_commands:
            with pytest.raises(PermissionError) as exc_info:
                MasterPlanCLIExecutionSandbox.sanitize_and_tokenize(cmd)
            assert "not in permitted CLI whitelist" in str(exc_info.value)

    def test_destructive_and_scraping_patterns_rejected(self):
        forbidden_commands = [
            "python -m playwright test",
            "python -m scrapy crawl myspider",
            "git clone http://example.com/repo && curl http://bad.com",
            "cmd /c del /f C:\\secret.txt",
            "cmd /c format D:",
            "powershell -Command rmdir /s /q C:\\data",
            "python -c 'import selenium'",
            "powershell -Command Stop-Computer",
            "cmd /c shutdown /s /t 0",
            "cmd /c reg delete HKLM\\Software\\Bad",
            "cmd /c diskpart",
        ]
        for cmd in forbidden_commands:
            with pytest.raises(PermissionError) as exc_info:
                MasterPlanCLIExecutionSandbox.sanitize_and_tokenize(cmd)
            assert "rejected by security filter" in str(exc_info.value)

    def test_windows_path_tokenization_preserves_backslashes(self):
        cmd = r'python "C:\ParasiteAI\scripts\verify.py" --dir="C:\Data\Temp"'
        tokens = MasterPlanCLIExecutionSandbox.sanitize_and_tokenize(cmd)
        assert tokens[0] == "python"
        assert tokens[1] == r"C:\ParasiteAI\scripts\verify.py"
        assert tokens[2] == r'--dir="C:\Data\Temp"' or tokens[2] == r'--dir=C:\Data\Temp'

    def test_live_execution_success(self):
        res = MasterPlanCLIExecutionSandbox.execute(
            'python -c "print(\'SANDBOX_SUCCESS\')"',
            timeout=5.0,
        )
        assert res.exit_code == 0
        assert "SANDBOX_SUCCESS" in res.stdout
        assert not res.timed_out
        assert not res.preempted
        assert res.duration_ms > 0

    def test_live_execution_cancellation_preemption(self):
        token = threading.Event()

        def signal_token():
            time.sleep(0.050)
            token.set()

        t = threading.Thread(target=signal_token)
        t.start()

        t0 = time.perf_counter()
        res = MasterPlanCLIExecutionSandbox.execute(
            'python -c "import time; time.sleep(5.0)"',
            timeout=10.0,
            cancellation_token=token,
        )
        t1 = time.perf_counter()
        t.join()

        assert res.preempted is True
        assert res.exit_code == -1
        elapsed_ms = (t1 - t0) * 1000.0
        assert elapsed_ms < 500.0, f"Preemption took {elapsed_ms:.1f}ms (expected < 500ms)"

    def test_live_execution_timeout(self):
        t0 = time.perf_counter()
        res = MasterPlanCLIExecutionSandbox.execute(
            'python -c "import time; time.sleep(5.0)"',
            timeout=0.200,
        )
        t1 = time.perf_counter()

        assert res.timed_out is True
        assert res.exit_code == -1
        elapsed_s = t1 - t0
        assert 0.150 <= elapsed_s <= 0.600, f"Timeout took {elapsed_s:.3f}s"


class TestVuln3UniversalAppResolverAttemptTracking:
    """VULN-3: Tier 3 (Win+R) Reachability & Loop Termination."""

    def test_tier_3_win_r_is_fully_reachable_when_tier_2_fails(self):
        resolver = MasterPlanUniversalAppResolver()
        target = "unregistered_test_app"

        trajectory = []
        for _ in range(5):
            plan = resolver.resolve_launch_action(target, elements=[])
            trajectory.append((plan.action, plan.keys, plan.text))

        # Step 1: Tier 2 Step A -> Win key
        assert trajectory[0][0] == Phase4ActionType.HOTKEY
        assert trajectory[0][1] == ["win"]

        # Step 2: Tier 2 Step B -> Type app name
        assert trajectory[1][0] == Phase4ActionType.TYPE
        assert trajectory[1][2] == f"{target}\n"

        # Step 3: Tier 3 Step A -> Win+R Chord (PROVES TIER 3 IS REACHABLE)
        assert trajectory[2][0] == Phase4ActionType.HOTKEY
        assert trajectory[2][1] == ["win", "r"], "Tier 3 Win+R chord MUST be reached on Step 3"

        # Step 4: Tier 3 Step B -> Type app name in Run box
        assert trajectory[3][0] == Phase4ActionType.TYPE
        assert trajectory[3][2] == f"{target}\n"

        # Step 5: Clean exhaustion -> ActionType.WAIT
        assert trajectory[4][0] == Phase4ActionType.WAIT, "Resolver must yield to cognitive replan when both tiers exhausted"

    def test_resolver_does_not_loop_infinitely(self):
        resolver = MasterPlanUniversalAppResolver()
        target = "ghost_app"

        actions = [resolver.resolve_launch_action(target, []).action for _ in range(10)]
        assert actions[4:] == [Phase4ActionType.WAIT] * 6


class TestVuln4PrecisionAppMatcherCollisionPrevention:
    """VULN-4: PrecisionAppMatcher Substring Collision Elimination."""

    def test_subword_collision_rejected(self):
        score = MasterPlanPrecisionAppMatcher.score_match("SmartScreen", "art")
        assert score == 0.0, "Sub-word collision 'art' in 'SmartScreen' must score 0.0"

        score2 = MasterPlanPrecisionAppMatcher.score_match("Certificate Manager", "cat")
        assert score2 == 0.0, "Sub-word collision 'cat' in 'Certificate Manager' must score 0.0"

    def test_destructive_negative_verbs_disqualified(self):
        negative_labels = [
            "Exit Notepad",
            "Close Notepad",
            "Quit Notepad",
            "Cancel Notepad",
            "Uninstall Notepad",
            "Delete Notepad",
            "Kill Notepad",
        ]
        for label in negative_labels:
            score = MasterPlanPrecisionAppMatcher.score_match(label, "notepad")
            assert score == 0.0, f"Destructive element '{label}' must score 0.0"

    def test_exact_and_prefix_matches_score_high(self):
        assert MasterPlanPrecisionAppMatcher.score_match("Notepad", "notepad") == 1.0
        assert MasterPlanPrecisionAppMatcher.score_match("Notepad - Untitled", "notepad") == 0.95
        assert MasterPlanPrecisionAppMatcher.score_match("Notepad: Document", "notepad") == 0.95

    def test_word_boundary_fuzzy_match(self):
        score = MasterPlanPrecisionAppMatcher.score_match("Art Studio", "art")
        assert score >= 0.80, f"Word boundary match 'Art Studio' for 'art' must score >= 0.80 (got {score})"

    def test_find_best_element_resolves_correct_element_from_adversarial_pool(self):
        pool = [
            UIElement(id=1, role="Button", label="SmartScreen", x=10, y=10, width=50, height=20, center_x=35, center_y=20),
            UIElement(id=2, role="MenuItem", label="Certificate Manager", x=10, y=40, width=50, height=20, center_x=35, center_y=50),
            UIElement(id=3, role="Button", label="Exit Notepad", x=10, y=70, width=50, height=20, center_x=35, center_y=80),
            UIElement(id=4, role="Button", label="Notepad", x=10, y=100, width=50, height=20, center_x=35, center_y=110),
            UIElement(id=5, role="Button", label="Art Studio", x=10, y=130, width=50, height=20, center_x=35, center_y=140),
        ]

        best_art = MasterPlanPrecisionAppMatcher.find_best_element("art", pool)
        assert best_art is not None
        assert best_art[0].id == 5
        assert best_art[0].label == "Art Studio"

        best_notepad = MasterPlanPrecisionAppMatcher.find_best_element("notepad", pool)
        assert best_notepad is not None
        assert best_notepad[0].id == 4
        assert best_notepad[0].label == "Notepad"
        assert best_notepad[1] == 1.0

        best_cat = MasterPlanPrecisionAppMatcher.find_best_element("cat", pool)
        assert best_cat is None
