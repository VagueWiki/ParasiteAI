"""
Verification script to audit all 8 remediation items in phase_4_master_plan.md
"""
import sys
from pathlib import Path

TARGET_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md")

def audit():
    text = TARGET_PATH.read_text(encoding="utf-8")
    print(f"Auditing {TARGET_PATH} ({len(text)} chars, {len(text.splitlines())} lines)...")

    checks = [
        # Item 1: DualChannelRouter Blueprint Hydration
        ("Item 1: Recommended strategy and steps check in router",
         '"recommended_strategy" in blueprint_json' in text and '"steps" in blueprint_json' in text),
        
        # Item 2: Escalation State Machine cycle limits & advisor failure bounds
        ("Item 2a: max_escalation_cycles = 3 in state machine",
         "max_escalation_cycles: int = Field(default=3" in text or "max_escalation_cycles: int = 3" in text or "total_escalation_cycles >= self.max_escalation_cycles" in text),
        ("Item 2b: max_consultation_failures = 2 in state machine",
         "max_consultation_failures: int = Field(default=2" in text or "consultation_failures >= self.max_consultation_failures" in text),
        ("Item 2c: Strike reset on consultation success",
         "self.local_strikes = 0" in text and "self.guided_strikes = 0" in text and "self.consultation_failures = 0" in text),
        ("Item 2d: on_hardware_interrupt method exists",
         "def on_hardware_interrupt(self)" in text),

        # Item 3: Speech Bubble Sanitization
        ("Item 3a: Code block regex stripping in _sanitize_text",
         r're.sub(r"```[\w]*[\s\S]*?```", "", text)' in text or '```[\\w]*[\\s\\S]*?```' in text),
        ("Item 3b: Backtick stripping in _sanitize_text",
         r're.sub(r"`[^`]*`", "", text)' in text),
        ("Item 3c: Error keyword filtering in translate_to_persona_voice",
         'any(kw in clean_text.lower() for kw in ("error:", "exception", "resource_exhausted"))' in text),
        ("Item 3d: Translation table contains error outage row",
         "External Advisor Error / Outage" in text and "RESOURCE_EXHAUSTED" in text),

        # Item 4: Action-Aware Strike Evaluation
        ("Item 4a: Headless CLI returncode evaluation",
         "cli_returncode == 0" in text or "returncode == 0" in text),
        ("Item 4b: Passive action exemption from visual diff",
         "ActionType.WAIT, ActionType.DONE" in text and "is_interactive" in text),
        ("Item 4c: Interactive GUI visual diff threshold evaluation",
         "screen_diff >= diff_threshold" in text),

        # Item 5: Grounded Capability Contract Sealing
        ("Item 5a: Headless scraping prohibition in contract",
         "ZERO headless scraping" in text and "curl" in text and "playwright" in text),
        ("Item 5b: Programmatic UIA pattern invocation prohibition",
         "ZERO programmatic accessibility pattern invocation" in text and "ValuePattern" in text and "InvokePattern" in text),
        ("Item 5c: Dynamic virtual screen bounds in contract",
         "get_virtual_screen_bounds()" in text),

        # Item 6: CLIExecutionSandbox Specification
        ("Item 6a: 30.0s default timeout in sandbox",
         "DEFAULT_TIMEOUT_S: float = 30.0" in text or "DEFAULT_TIMEOUT_SECONDS" in text),
        ("Item 6b: 10ms cancellation token polling",
         "time.sleep(0.010)" in text or "poll_interval_s = 0.010" in text),
        ("Item 6c: Process tree kill via taskkill /F /T /PID",
         'taskkill", "/F", "/T", "/PID' in text or "taskkill /F /T /PID" in text),
        ("Item 6d: Binary whitelist and forbidden pattern filtering",
         "PERMITTED_BINARIES" in text and "FORBIDDEN_PATTERNS" in text),
        ("Item 6e: Safe tokenization with posix=False",
         "shlex.split(command_str, posix=False)" in text or "posix=False" in text),

        # Item 7: UniversalAppResolver Robustness
        ("Item 7a: Resolver state variables for attempt tracking",
         "_start_search_attempts" in text and "_run_dialog_attempts" in text),
        ("Item 7b: Tier 3 Win+R fallback progression",
         "keys=[\"win\", \"r\"]" in text or "keys=['win', 'r']" in text),
        ("Item 7c: PrecisionAppMatcher with word boundaries and negative verbs",
         "class PrecisionAppMatcher" in text and "NEGATIVE_VERBS" in text and "score_match" in text),

        # Item 8: Sub-Phases & Victory Matrix
        ("Item 8a: Sub-Phase 4B action-aware deliverables",
         "Sub-Phase 4B: 4-Tier Escalation State Machine" in text and "on_hardware_interrupt" in text),
        ("Item 8b: Sub-Phase 4D CLIExecutionSandbox deliverables",
         "Sub-Phase 4D: Tool-Aware Reasoning & Antigravity Meta-Tooling" in text and "CLIExecutionSandbox" in text),
        ("Item 8c: Sub-Phase 4E UniversalAppResolver deliverables",
         "Sub-Phase 4E: Universal Living Plan" in text and "PrecisionAppMatcher" in text),
        ("Item 8d: Sub-Phase 4F test suite expansion",
         "tests/test_cli_sandbox.py" in text and "tests/test_resolver_precision.py" in text),
        ("Item 8e: VERIF-10 in Victory Matrix",
         "VERIF-10" in text and "CLI Execution Sandbox & Preemption" in text),
        ("Item 8f: VERIF-11 in Victory Matrix",
         "VERIF-11" in text and "Resolver 3-Tier Fallback & Precision Matching" in text),

        # Invariants Check
        ("Invariant 1: Sub-2ms hardware touch preemption",
         "Sub-2ms Hardware Touch Preemption" in text),
        ("Invariant 2: Instant hard process kill Ctrl+Alt+K < 5ms",
         "Instant Hard Process Termination" in text and "Ctrl+Alt+K" in text),
        ("Invariant 3: Zero silent cloud exfiltration local_llm default",
         "Zero Silent Cloud Exfiltration" in text and '"local_llm"' in text),
        ("Invariant 4: Strict anti-hardcoding invariant",
         "Strict Anti-Hardcoding Invariant" in text and "app_map = {}" in text),
    ]

    passed = 0
    failed = 0
    for name, condition in checks:
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            failed += 1

    print(f"\nAudit complete: {passed}/{len(checks)} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    audit()
