r"""
Forensic Audit Script for Milestone 4B: 4-Tier Escalation State Machine
Location: C:\ParasiteAI\.agents\teamwork\teamwork_auditor_m4b\audit_m4b.py
"""

import sys
import subprocess
import ctypes
from ctypes import wintypes
import inspect
import re

def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def audit():
    print("=" * 70)
    print("STARTING FORENSIC AUDIT: MILESTONE 4B (4-TIER ESCALATION STATE MACHINE)")
    print("=" * 70)

    failures = []

    # -----------------------------------------------------------------------
    # 1. Anti-Cheat & Authenticity Check: memory.py & dual_mind.py
    # -----------------------------------------------------------------------
    print("\n[CHECK 1] Anti-Cheat & Source Code Authenticity Analysis...")
    try:
        from parasite_ai.mind.memory import (
            CadenceTier,
            EscalationStateMachine,
            ActionPlan,
            ActionType,
            INTERACTIVE_ACTION_TYPES,
            StepRecord,
            EpisodicMemory,
        )

        # Inspect EscalationStateMachine source for facade implementations
        sm_src = inspect.getsource(EscalationStateMachine)
        print("  Inspecting EscalationStateMachine source for dummy/facade implementations...")
        # Check for standalone 'pass' statement
        for line in sm_src.splitlines():
            stripped = line.strip()
            if stripped == "pass":
                print(f"  [WARN] Found bare 'pass' in EscalationStateMachine: {line}")
            if re.match(r"^return\s+(True|False|None|\d+|[\"'][^\"']*[\"'])$", stripped):
                print(f"  [WARN] Potential constant return: {line}")

        # Verify genuine state machine logic
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL, "Initial tier must be TIER_1_LOCAL"
        assert sm.local_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.copilot_strikes == 0
        assert sm.consultation_failures == 0
        assert sm.total_escalation_cycles == 0

        # Test T1 -> T2 transition on 2 strikes
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.local_strikes == 1 and sm.current_tier == CadenceTier.TIER_1_LOCAL, "Strike 1 failed"
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.local_strikes == 2 and sm.current_tier == CadenceTier.TIER_2_CONSULT, "T1->T2 transition failed"

        # Test T2 -> T3 on consultation success
        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED, "T2->T3 success transition failed"
        assert sm.local_strikes == 0, "local_strikes must reset to 0 to prevent strike leakage"
        assert sm.guided_strikes == 0, "guided_strikes must reset to 0"

        # Test T3 -> T4 transition on 2 strikes
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.guided_strikes == 1 and sm.current_tier == CadenceTier.TIER_3_GUIDED, "Guided strike 1 failed"
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.guided_strikes == 2 and sm.current_tier == CadenceTier.TIER_4_CO_PILOT, "T3->T4 transition failed"
        assert sm.total_escalation_cycles == 1, "total_escalation_cycles must increment"

        # Test T4 micro-success recovery to T3
        sm.on_action_result(success=True, screen_diff=0.05, action_type=ActionType.CLICK)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED, "T4->T3 recovery failed"
        assert sm.copilot_strikes == 0 and sm.guided_strikes == 0, "T4 recovery strike reset failed"

        # Test T3 -> T4 -> USER_OVERRIDE on 3 total cycles
        # Cycle 2:
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT and sm.total_escalation_cycles == 2
        sm.on_action_result(success=True, screen_diff=0.05, action_type=ActionType.CLICK)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        # Cycle 3:
        sm.on_action_result(success=False, screen_diff=0.0)
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.USER_OVERRIDE and sm.current_tier == CadenceTier.USER_OVERRIDE, "Cycle cap 3 failed"
        assert sm.total_escalation_cycles == 3

        # Test T4 -> USER_OVERRIDE on 3 co-pilot strikes directly
        sm2 = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT)
        sm2.on_action_result(success=False, screen_diff=0.0)
        sm2.on_action_result(success=False, screen_diff=0.0)
        assert sm2.current_tier == CadenceTier.TIER_4_CO_PILOT and sm2.copilot_strikes == 2
        res2 = sm2.on_action_result(success=False, screen_diff=0.0)
        assert res2 == CadenceTier.USER_OVERRIDE and sm2.copilot_strikes == 3, "T4 3-strike override failed"

        # Test Advisor failure loop termination (max 2 failures)
        sm3 = EscalationStateMachine(current_tier=CadenceTier.TIER_2_CONSULT)
        sm3.on_consultation_failure()
        assert sm3.current_tier == CadenceTier.TIER_1_LOCAL and sm3.consultation_failures == 1
        sm3.current_tier = CadenceTier.TIER_2_CONSULT
        sm3.on_consultation_failure()
        assert sm3.current_tier == CadenceTier.USER_OVERRIDE and sm3.consultation_failures == 2, "Advisor failure override failed"

        # Test Hardware interrupt from all tiers
        for tier in CadenceTier:
            sm_int = EscalationStateMachine(current_tier=tier)
            sm_int.on_hardware_interrupt()
            assert sm_int.current_tier == CadenceTier.USER_OVERRIDE, f"Hardware interrupt failed from {tier}"

        # Test Action-aware evaluation:
        # CLI action returncode == 0
        sm_cli = EscalationStateMachine()
        sm_cli.local_strikes = 1
        sm_cli.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=0)
        assert sm_cli.local_strikes == 0, "CLI returncode 0 must reset strikes even with 0.0 diff"
        # CLI action returncode == 1
        sm_cli.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=1)
        assert sm_cli.local_strikes == 1, "CLI returncode 1 must increment strikes"

        # Passive action WAIT with 0.0 diff
        sm_passive = EscalationStateMachine()
        sm_passive.local_strikes = 1
        sm_passive.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.WAIT, is_interactive=False)
        assert sm_passive.local_strikes == 1, "Passive WAIT must NOT increment strikes on zero diff"

        # Passive action DONE with 0.0 diff
        sm_passive.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.DONE, is_interactive=False)
        assert sm_passive.local_strikes == 1, "Passive DONE must NOT increment strikes on zero diff"

        print("  [PASS] EscalationStateMachine empirical behavior verified 100% authentic.")
    except Exception as e:
        print(f"  [FAIL] EscalationStateMachine check failed: {e}")
        failures.append(f"EscalationStateMachine check: {e}")

    # Inspect dual_mind.py pipeline integration
    print("  Inspecting DualMindPipeline integration in dual_mind.py...")
    try:
        from parasite_ai.mind.dual_mind import DualMindPipeline
        pipe_src = inspect.getsource(DualMindPipeline)
        assert "self.escalation_sm" in pipe_src, "DualMindPipeline missing self.escalation_sm"
        assert "on_hardware_interrupt" in pipe_src, "DualMindPipeline missing on_hardware_interrupt"
        assert "on_consultation_success" in pipe_src, "DualMindPipeline missing on_consultation_success"
        assert "on_consultation_failure" in pipe_src, "DualMindPipeline missing on_consultation_failure"
        assert "on_action_result" in pipe_src, "DualMindPipeline missing on_action_result"
        print("  [PASS] DualMindPipeline integration points verified.")
    except Exception as e:
        print(f"  [FAIL] DualMindPipeline inspection failed: {e}")
        failures.append(f"DualMindPipeline inspection: {e}")

    # -----------------------------------------------------------------------
    # 2. Anti-Hardcoding Invariant Check: git grep -i "app_map" parasite_ai/
    # -----------------------------------------------------------------------
    print("\n[CHECK 2] Anti-Hardcoding Invariant Check (app_map)...")
    rc, stdout, stderr = run_cmd(["git", "grep", "-i", "app_map", "parasite_ai/"])
    if rc == 0 and stdout.strip():
        print(f"  [FAIL] Detected hardcoded app_map entries:\n{stdout}")
        failures.append(f"Hardcoded app_map detected: {stdout}")
    elif rc == 1:
        print("  [PASS] git grep -i 'app_map' parasite_ai/ returned 0 matches.")
    else:
        print(f"  [WARN/FAIL] Unexpected git grep returncode {rc}: {stderr}")
        failures.append(f"git grep error: {stderr}")

    # -----------------------------------------------------------------------
    # 3. Zero Silent Exfiltration Check: BrainConfig().mode == "local_llm"
    # -----------------------------------------------------------------------
    print("\n[CHECK 3] Zero Silent Cloud Exfiltration Check (BrainConfig.mode)...")
    try:
        from parasite_ai.config import BrainConfig
        bc = BrainConfig()
        print(f"  BrainConfig().mode = {bc.mode!r}")
        assert bc.mode == "local_llm", f"Default mode must be 'local_llm', got {bc.mode!r}"
        print("  [PASS] BrainConfig mode is locked to 'local_llm'.")
    except Exception as e:
        print(f"  [FAIL] BrainConfig mode check failed: {e}")
        failures.append(f"BrainConfig mode check: {e}")

    # -----------------------------------------------------------------------
    # 4. Win32 Struct 64-bit ABI Sizing ctypes reflection check
    # -----------------------------------------------------------------------
    print("\n[CHECK 4] Win32 Struct 64-bit ABI Sizing ctypes Reflection...")
    try:
        from parasite_ai.safety.interrupt_guard import POINT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT
        from parasite_ai.hands.keyboard import (
            INPUT,
            MOUSEINPUT,
            KEYBDINPUT,
            HARDWAREINPUT,
            INPUT_UNION,
        )
        from parasite_ai.mind.dual_mind import GUITHREADINFO

        expected_sizes = {
            "POINT": (POINT, 8),
            "RECT": (wintypes.RECT, 16),
            "MSLLHOOKSTRUCT": (MSLLHOOKSTRUCT, 32),
            "KBDLLHOOKSTRUCT": (KBDLLHOOKSTRUCT, 24),
            "MOUSEINPUT": (MOUSEINPUT, 32),
            "KEYBDINPUT": (KEYBDINPUT, 24),
            "HARDWAREINPUT": (HARDWAREINPUT, 8),
            "INPUT_UNION": (INPUT_UNION, 32),
            "INPUT": (INPUT, 40),
            "GUITHREADINFO": (GUITHREADINFO, 72),
        }

        all_structs_ok = True
        for name, (struct_cls, exp_sz) in expected_sizes.items():
            actual_sz = ctypes.sizeof(struct_cls)
            print(f"  {name:16}: actual={actual_sz:2} bytes, expected={exp_sz:2} bytes -> {'OK' if actual_sz == exp_sz else 'MISMATCH'}")
            if actual_sz != exp_sz:
                all_structs_ok = False
                failures.append(f"{name} size mismatch: actual {actual_sz} != expected {exp_sz}")

        if all_structs_ok:
            print("  [PASS] All 10 Win32 structures strictly conform to 64-bit Windows ABI.")
        else:
            print("  [FAIL] Win32 structure sizing mismatch detected.")
    except Exception as e:
        print(f"  [FAIL] Win32 struct check failed: {e}")
        failures.append(f"Win32 struct reflection error: {e}")

    # -----------------------------------------------------------------------
    # 5. VERIF-1 Forensic Test Execution: pytest
    # -----------------------------------------------------------------------
    print("\n[CHECK 5] VERIF-1 Pytest Suite Execution...")
    python_exe = sys.executable
    print(f"  Executing: {python_exe} -m pytest tests/test_escalation_cadence.py tests/test_challenger_p4_empirical.py -v")
    rc, stdout, stderr = run_cmd([
        python_exe, "-m", "pytest",
        "tests/test_escalation_cadence.py",
        "tests/test_challenger_p4_empirical.py",
        "-v",
    ])
    print("  Test output summary:")
    for line in stdout.splitlines()[-10:]:
        print(f"    {line}")
    if rc != 0:
        print(f"  [FAIL] VERIF-1 tests failed! Returncode={rc}")
        if stderr:
            print(f"  stderr:\n{stderr}")
        failures.append(f"VERIF-1 test execution failed with exit code {rc}")
    else:
        print("  [PASS] All VERIF-1 tests passed 100% green.")

    # Also verify test_dual_mind.py and test_memory.py to ensure zero regression in modified files
    print("\n[CHECK 5b] Regression Check on Modified Files (test_memory.py, test_dual_mind.py)...")
    rc2, stdout2, stderr2 = run_cmd([
        python_exe, "-m", "pytest",
        "tests/test_memory.py",
        "tests/test_dual_mind.py",
        "-v",
    ])
    for line in stdout2.splitlines()[-5:]:
        print(f"    {line}")
    if rc2 != 0:
        print(f"  [FAIL] Regression detected in test_memory or test_dual_mind: rc={rc2}")
        failures.append(f"Regression in modified modules: rc={rc2}")
    else:
        print("  [PASS] Zero regression in modified modules.")

    # -----------------------------------------------------------------------
    # 5c. Adversarial Stress Testing & Edge Cases
    # -----------------------------------------------------------------------
    print("\n[CHECK 5c] Adversarial Stress Testing & Edge Case Mining...")
    try:
        from parasite_ai.mind.memory import EscalationStateMachine, CadenceTier, ActionType

        # Edge Case 1: Post-terminal calls to on_action_result() must remain inert
        sm_term = EscalationStateMachine(current_tier=CadenceTier.USER_OVERRIDE, copilot_strikes=3)
        res = sm_term.on_action_result(success=True, screen_diff=0.50, action_type=ActionType.CLICK)
        assert res == CadenceTier.USER_OVERRIDE
        assert sm_term.current_tier == CadenceTier.USER_OVERRIDE
        assert sm_term.copilot_strikes == 3, "Terminal state counters must not mutate"

        # Edge Case 2: Out-of-order consultation callbacks when not in TIER_2_CONSULT
        sm_noop = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        sm_noop.on_consultation_success()
        assert sm_noop.current_tier == CadenceTier.TIER_1_LOCAL, "on_consultation_success outside T2 must be no-op"
        sm_noop.on_consultation_failure()
        assert sm_noop.current_tier == CadenceTier.TIER_1_LOCAL, "on_consultation_failure outside T2 must be no-op"

        # Edge Case 3: Failed passive action (e.g. WAIT raising error) MUST incur a strike
        sm_fail_passive = EscalationStateMachine()
        sm_fail_passive.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.WAIT)
        assert sm_fail_passive.local_strikes == 1, "Failed passive action must incur strike"

        # Edge Case 4: Negative or abnormal CLI return codes (e.g. -9 SIGKILL or 127 command not found)
        sm_sigkill = EscalationStateMachine()
        sm_sigkill.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=-9)
        assert sm_sigkill.local_strikes == 1, "Negative CLI returncode must incur strike"

        # Edge Case 5: Custom diff_threshold parameter
        sm_custom = EscalationStateMachine()
        sm_custom.on_action_result(success=True, screen_diff=0.03, action_type=ActionType.CLICK, diff_threshold=0.05)
        assert sm_custom.local_strikes == 1, "Custom diff_threshold not enforced"
        sm_custom.on_action_result(success=True, screen_diff=0.06, action_type=ActionType.CLICK, diff_threshold=0.05)
        assert sm_custom.local_strikes == 0, "Custom diff_threshold reset failed"

        # Edge Case 6: Multiple consecutive hardware interrupts idempotency
        sm_hi = EscalationStateMachine(current_tier=CadenceTier.TIER_3_GUIDED)
        sm_hi.on_hardware_interrupt()
        assert sm_hi.current_tier == CadenceTier.USER_OVERRIDE
        sm_hi.on_hardware_interrupt()
        assert sm_hi.current_tier == CadenceTier.USER_OVERRIDE

        print("  [PASS] All 6 adversarial edge case scenarios passed cleanly.")
    except Exception as e:
        print(f"  [FAIL] Adversarial stress test failed: {e}")
        failures.append(f"Adversarial stress test failure: {e}")

    # -----------------------------------------------------------------------
    # Summary & Verdict
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("FORENSIC AUDIT SUMMARY")
    print("=" * 70)
    if not failures:
        print("VERDICT: CLEAN")
        print("All forensic integrity checks passed without defect.")
        return 0
    else:
        print("VERDICT: INTEGRITY VIOLATION")
        print(f"Failures ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1

if __name__ == "__main__":
    code = audit()
    sys.exit(code)
