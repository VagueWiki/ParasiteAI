"""
challenge_empirical_m4b_2.py - Empirical Challenge Harness for Milestone 4B.

Authored by: Challenger 2 (Empirical State Machine & Pipeline Stress Tester)
Target: Sub-Phase 4B: 4-Tier Escalation State Machine (VERIF-1)

Validates:
1. Hardware interrupt immediate transition (< 2ms) from every tier:
   TIER_1_LOCAL, TIER_2_CONSULT, TIER_3_GUIDED, TIER_4_CO_PILOT, USER_OVERRIDE.
   Runs 100,000-cycle high-precision nanosecond latency benchmark (p50, p99, p99.9, max).
2. T4 -> T3 recovery:
   Micro-action success in Tier 4 recovers to Tier 3 with copilot_strikes=0 and guided_strikes=0.
   Validates GUI actions (screen_diff >= 0.02), CLI actions (returncode == 0),
   and verifies passive actions (WAIT, DONE) do NOT falsely trigger recovery.
3. DualMindPipeline step execution under simulated hardware preemption:
   Preemption at step start, in-flight cancellation during dispatch, idempotence in USER_OVERRIDE,
   and clean resumption after reset.
4. DualMindPipeline step execution under simulated visual deadlock:
   Full deterministic end-to-end traversal from T1 -> T2 -> T3 -> T4 -> USER_OVERRIDE,
   as well as persistent advisor failure termination.
5. High-concurrency race condition and thread-safety stress across all transitions.
"""

from __future__ import annotations

import statistics
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import numpy as np

from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodicMemory,
    EscalationStateMachine,
)
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent
from parasite_ai.ui.types import UIElement


def log_test(section: str, name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] [{section}] {name} {details}")
    if not passed:
        raise AssertionError(f"Test failed: [{section}] {name} - {details}")


# ===========================================================================
# 1. Hardware Interrupt Transition & Latency Benchmark (< 2ms)
# ===========================================================================

def run_suite_1_hardware_interrupt():
    print("\n" + "=" * 70)
    print("SUITE 1: Hardware Interrupt Immediate Transition & Latency Benchmark (< 2ms)")
    print("=" * 70)

    # 1.1 Immediate transition from all tiers
    tiers_to_test = [
        CadenceTier.TIER_1_LOCAL,
        CadenceTier.TIER_2_CONSULT,
        CadenceTier.TIER_3_GUIDED,
        CadenceTier.TIER_4_CO_PILOT,
        CadenceTier.USER_OVERRIDE,
    ]

    for tier in tiers_to_test:
        sm = EscalationStateMachine(current_tier=tier)
        sm.on_hardware_interrupt()
        passed = (sm.current_tier == CadenceTier.USER_OVERRIDE)
        log_test("Interrupt Transition", f"From {tier.value} to USER_OVERRIDE", passed)

    # 1.2 High-Precision Latency Benchmark (100,000 iterations)
    iterations = 100_000
    latencies_ns = []

    sm = EscalationStateMachine()
    for i in range(iterations):
        # Vary starting tier
        sm.current_tier = tiers_to_test[i % len(tiers_to_test)]
        t0 = time.perf_counter_ns()
        sm.on_hardware_interrupt()
        t1 = time.perf_counter_ns()
        latencies_ns.append(t1 - t0)

    mean_ns = statistics.mean(latencies_ns)
    median_ns = statistics.median(latencies_ns)
    p95_ns = statistics.quantiles(latencies_ns, n=100)[94]
    p99_ns = statistics.quantiles(latencies_ns, n=100)[98]
    p99_9_ns = statistics.quantiles(latencies_ns, n=1000)[998]
    max_ns = max(latencies_ns)

    mean_us = mean_ns / 1_000.0
    median_us = median_ns / 1_000.0
    p95_us = p95_ns / 1_000.0
    p99_us = p99_ns / 1_000.0
    p99_9_us = p99_9_ns / 1_000.0
    max_us = max_ns / 1_000.0
    max_ms = max_ns / 1_000_000.0

    print(f"Latency Statistics over {iterations:,} calls:")
    print(f"  Mean:   {mean_us:.3f} us ({mean_ns:.0f} ns)")
    print(f"  Median: {median_us:.3f} us ({median_ns:.0f} ns)")
    print(f"  p95:    {p95_us:.3f} us ({p95_ns:.0f} ns)")
    print(f"  p99:    {p99_us:.3f} us ({p99_ns:.0f} ns)")
    print(f"  p99.9:  {p99_9_us:.3f} us ({p99_9_ns:.0f} ns)")
    print(f"  Max:    {max_us:.3f} us ({max_ms:.4f} ms)")

    # Strict invariant: MUST be < 2.0 ms (2,000,000 ns)
    under_2ms = max_ns < 2_000_000
    log_test(
        "Latency Benchmark",
        f"Worst-case latency < 2.0ms (Observed: {max_ms:.4f}ms)",
        under_2ms,
        f"(max={max_us:.1f}us, p99={p99_us:.1f}us)",
    )

    # 1.3 State immutability once in USER_OVERRIDE
    sm = EscalationStateMachine(current_tier=CadenceTier.USER_OVERRIDE)
    res1 = sm.on_action_result(success=True, screen_diff=0.50, action_type=ActionType.CLICK)
    res2 = sm.on_action_result(success=True, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=0)
    res3 = sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
    res4 = sm.on_action_result(success=True, action_type=ActionType.WAIT)
    sm.on_consultation_success()
    sm.on_consultation_failure()

    override_preserved = (
        res1 == CadenceTier.USER_OVERRIDE
        and res2 == CadenceTier.USER_OVERRIDE
        and res3 == CadenceTier.USER_OVERRIDE
        and res4 == CadenceTier.USER_OVERRIDE
        and sm.current_tier == CadenceTier.USER_OVERRIDE
    )
    log_test("Immutability", "USER_OVERRIDE absorbs all actions and advisor events", override_preserved)


# ===========================================================================
# 2. T4 -> T3 Recovery on Micro-Action Success
# ===========================================================================

def run_suite_2_t4_to_t3_recovery():
    print("\n" + "=" * 70)
    print("SUITE 2: Tier 4 -> Tier 3 Recovery & Strike Clearing")
    print("=" * 70)

    # 2.1 GUI micro-action success with screen_diff >= 0.02
    sm = EscalationStateMachine(
        current_tier=CadenceTier.TIER_4_CO_PILOT,
        copilot_strikes=2,
        guided_strikes=2,
        local_strikes=1,
    )
    res = sm.on_action_result(
        success=True,
        screen_diff=0.035,
        action_type=ActionType.CLICK,
    )
    passed_gui = (
        res == CadenceTier.TIER_3_GUIDED
        and sm.current_tier == CadenceTier.TIER_3_GUIDED
        and sm.copilot_strikes == 0
        and sm.guided_strikes == 0
    )
    log_test(
        "T4->T3 Recovery",
        "GUI action (diff=0.035 >= 0.02) recovers to T3 and zeroes copilot/guided strikes",
        passed_gui,
        f"(copilot_strikes={sm.copilot_strikes}, guided_strikes={sm.guided_strikes})",
    )

    # 2.2 Boundary check at exact diff threshold (0.0200)
    sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=1, guided_strikes=2)
    res = sm.on_action_result(success=True, screen_diff=0.0200, action_type=ActionType.CLICK)
    passed_exact = (
        res == CadenceTier.TIER_3_GUIDED
        and sm.copilot_strikes == 0
        and sm.guided_strikes == 0
    )
    log_test("T4->T3 Boundary", "Exact diff threshold 0.0200 recovers to T3", passed_exact)

    # 2.3 Boundary check just below threshold (0.0199) -> Must NOT recover
    sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=1, guided_strikes=2)
    res = sm.on_action_result(success=True, screen_diff=0.0199, action_type=ActionType.CLICK)
    passed_sub = (
        res == CadenceTier.TIER_4_CO_PILOT
        and sm.copilot_strikes == 2
        and sm.current_tier == CadenceTier.TIER_4_CO_PILOT
    )
    log_test("T4 Sub-threshold", "Diff 0.0199 (< 0.02) increments copilot_strikes to 2 without recovering", passed_sub)

    # 2.4 Headless CLI micro-action in T4
    sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=2, guided_strikes=2)
    res = sm.on_action_result(
        success=True,
        screen_diff=0.0,
        action_type=ActionType.RUN_CLI_COMMAND,
        cli_returncode=0,
    )
    passed_cli = (
        res == CadenceTier.TIER_3_GUIDED
        and sm.copilot_strikes == 0
        and sm.guided_strikes == 0
    )
    log_test("T4 CLI Action", "CLI returncode=0 recovers to T3 even with 0.0 screen diff", passed_cli)

    # 2.5 Passive action (WAIT, DONE) in T4 -> Must NOT falsely recover to T3
    sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=1, guided_strikes=2)
    res_wait = sm.on_action_result(
        success=True,
        screen_diff=0.0,
        action_type=ActionType.WAIT,
        is_interactive=False,
    )
    passed_wait = (
        res_wait == CadenceTier.TIER_4_CO_PILOT
        and sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        and sm.copilot_strikes == 1
    )
    log_test("T4 Passive Action", "Successful WAIT in T4 does NOT recover to T3 and keeps strikes unchanged", passed_wait)

    # 2.6 Consecutive failures in T4 -> USER_OVERRIDE on strike 3
    sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=0)
    sm.on_action_result(success=False, screen_diff=0.0)
    assert sm.copilot_strikes == 1 and sm.current_tier == CadenceTier.TIER_4_CO_PILOT

    sm.on_action_result(success=False, screen_diff=0.0)
    assert sm.copilot_strikes == 2 and sm.current_tier == CadenceTier.TIER_4_CO_PILOT

    res_override = sm.on_action_result(success=False, screen_diff=0.0)
    passed_override = (
        res_override == CadenceTier.USER_OVERRIDE
        and sm.current_tier == CadenceTier.USER_OVERRIDE
        and sm.copilot_strikes == 3
    )
    log_test("T4 Termination", "3 consecutive failures in T4 transition directly to USER_OVERRIDE", passed_override)


# ===========================================================================
# 3. Oscillation Limit & Loop Protection
# ===========================================================================

def run_suite_3_oscillation_limits():
    print("\n" + "=" * 70)
    print("SUITE 3: Oscillation Limits & Loop Protection Stress")
    print("=" * 70)

    # 3.1 Cumulative T3 <-> T4 oscillation termination at 3 cycles
    sm = EscalationStateMachine(max_escalation_cycles=3)
    sm.current_tier = CadenceTier.TIER_3_GUIDED

    for cycle in range(1, 4):
        # 2 strikes in Tier 3 -> advances to Tier 4
        sm.on_action_result(success=False, screen_diff=0.0)
        res = sm.on_action_result(success=False, screen_diff=0.0)

        if cycle < 3:
            assert res == CadenceTier.TIER_4_CO_PILOT
            assert sm.total_escalation_cycles == cycle
            # Micro-action recovers back to T3
            rec = sm.on_action_result(success=True, screen_diff=0.05)
            assert rec == CadenceTier.TIER_3_GUIDED
            assert sm.copilot_strikes == 0
            assert sm.guided_strikes == 0
        else:
            # On 3rd cycle, max_escalation_cycles terminates to USER_OVERRIDE!
            assert res == CadenceTier.USER_OVERRIDE
            assert sm.current_tier == CadenceTier.USER_OVERRIDE
            assert sm.total_escalation_cycles == 3

    log_test("Oscillation Cap", "T3 <-> T4 oscillation terminates to USER_OVERRIDE after exactly 3 cycles", True)

    # 3.2 Persistent advisor failure termination at 2 failures
    sm2 = EscalationStateMachine(max_consultation_failures=2)
    # T1 fails twice -> T2
    sm2.on_action_result(success=False, screen_diff=0.0)
    sm2.on_action_result(success=False, screen_diff=0.0)
    assert sm2.current_tier == CadenceTier.TIER_2_CONSULT

    # Advisor failure 1 -> fallback to T1
    sm2.on_consultation_failure()
    assert sm2.current_tier == CadenceTier.TIER_1_LOCAL
    assert sm2.consultation_failures == 1
    assert sm2.local_strikes == 0

    # T1 fails twice -> T2 again
    sm2.on_action_result(success=False, screen_diff=0.0)
    sm2.on_action_result(success=False, screen_diff=0.0)
    assert sm2.current_tier == CadenceTier.TIER_2_CONSULT

    # Advisor failure 2 -> terminates directly to USER_OVERRIDE
    sm2.on_consultation_failure()
    passed_adv = (
        sm2.current_tier == CadenceTier.USER_OVERRIDE
        and sm2.consultation_failures == 2
    )
    log_test("Advisor Loop Protection", "Persistent advisor failures terminate to USER_OVERRIDE after 2 failures", passed_adv)


# ===========================================================================
# 4. DualMindPipeline Step Execution Under Simulated Hardware Preemption
# ===========================================================================

def run_suite_4_pipeline_preemption():
    print("\n" + "=" * 70)
    print("SUITE 4: DualMindPipeline Step Execution Under Simulated Hardware Preemption")
    print("=" * 70)

    # 4.1 Preemption before step execution
    mock_brain = MagicMock()
    mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}
    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True
    mock_interrupt = MagicMock()
    mock_interrupt.is_interrupted.return_value = True

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=mock_mouse,
        interrupt_guard=mock_interrupt,
    )
    pipeline.escalation_sm.current_tier = CadenceTier.TIER_1_LOCAL

    rec = pipeline.step(user_goal="Test preemption")

    passed_p1 = (
        rec.success is False
        and "User override active" in (rec.error_message or "")
        and pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        and rec.tier_level == CadenceTier.USER_OVERRIDE
        and mock_brain.generate_action.call_count == 0
        and mock_mouse.click.call_count == 0
    )
    log_test("Pipeline Preemption", "Step halts immediately, zeroes actuator invocations, sets USER_OVERRIDE", passed_p1)

    # 4.2 Preemption from Tier 3 & Tier 4 collapses to USER_OVERRIDE
    for start_tier in (CadenceTier.TIER_3_GUIDED, CadenceTier.TIER_4_CO_PILOT):
        pipeline.escalation_sm.current_tier = start_tier
        rec = pipeline.step(user_goal="Test preemption in high tier")
        passed = (
            pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
            and rec.tier_level == CadenceTier.USER_OVERRIDE
        )
        log_test("Pipeline Preemption", f"From {start_tier.value} collapses to USER_OVERRIDE", passed)

    # 4.3 Idempotence while in USER_OVERRIDE
    mock_interrupt.is_interrupted.return_value = False  # Guard un-flags, but SM is still in USER_OVERRIDE
    for i in range(5):
        rec = pipeline.step(user_goal="Step while overridden")
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec.action.action == ActionType.WAIT
        assert rec.success is False
        assert mock_mouse.click.call_count == 0
    log_test("Override Idempotence", "Subsequent steps safely yield with WAIT while in USER_OVERRIDE", True)

    # 4.4 In-flight cancellation token during dispatch
    cancellation_token = threading.Event()
    cancellation_token.set()  # Pre-fired token simulates touch mid-motion

    mock_interrupt.get_cancellation_token.return_value = cancellation_token
    mock_interrupt.is_interrupted.return_value = False
    pipeline.escalation_sm.reset()  # Reset to T1

    # Override action to trigger click
    rec = pipeline.step(
        user_goal="Click during mid-flight touch",
        override_action=ActionPlan(action=ActionType.CLICK, coordinates=(100, 100)),
    )
    # ActionDispatcher handles preemption
    passed_inflight = (
        mock_mouse.release_all_buttons.called or not rec.success
    )
    log_test("In-flight Preemption", "Action dispatcher safely neutralizes inputs upon token trigger", passed_inflight)

    # 4.5 Clean resumption after manual reset
    pipeline.escalation_sm.reset()
    mock_interrupt.is_interrupted.return_value = False
    mock_interrupt.get_cancellation_token.return_value = threading.Event()
    rec_resume = pipeline.step(
        user_goal="Resume normal driving",
        override_action=ActionPlan(action=ActionType.WAIT, wait_ms=10),
    )
    passed_resume = (
        pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        and rec_resume.success is True
    )
    log_test("Pipeline Resumption", "Pipeline resumes nominal T1 driving after reset()", passed_resume)


# ===========================================================================
# 5. DualMindPipeline Step Execution Under Simulated Visual Deadlock
# ===========================================================================

def run_suite_5_pipeline_visual_deadlock():
    print("\n" + "=" * 70)
    print("SUITE 5: DualMindPipeline Full 4-Tier Traversal Under Visual Deadlock")
    print("=" * 70)

    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Driving forward."
    mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    mock_offloader = MagicMock()
    # Strategic blueprint returned by advisor
    mock_offloader.query_web_ai.return_value = """```json
{
  "rationale": "Focus window before clicking element.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Focus window",
      "success_criteria": "Window focused"
    }
  ]
}
```"""

    elements = [UIElement.from_bbox(1, (50, 50, 60, 30), label="Submit", role="Button")]
    static_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=mock_mouse,
        offloader=mock_offloader,
    )

    # --- Phase 1: Tier 1 Local Deadlock (2 strikes -> Tier 2) ---
    # Step 1: Click button, screen diff = 0.0 -> Strike 1
    rec1 = pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements)
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
    assert pipeline.escalation_sm.local_strikes == 1
    assert rec1.tier_level == CadenceTier.TIER_1_LOCAL

    # Step 2: Click button, screen diff = 0.0 -> Strike 2 -> Escalates to TIER_2_CONSULT!
    rec2 = pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements)
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
    assert pipeline.escalation_sm.local_strikes == 2
    assert rec2.tier_level == CadenceTier.TIER_2_CONSULT

    log_test("Deadlock Phase 1", "T1 deadlocks after 2 failed visual diffs and reaches TIER_2_CONSULT", True)

    # --- Phase 2: Tier 2 Consultation Execution -> Tier 3 ---
    # Step 3: Executes consultation query
    rec3 = pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements)
    assert rec3.success is True
    assert rec3.action.action == ActionType.WAIT
    # Invariant: Transitioned to TIER_3_GUIDED and local_strikes cleared to 0
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
    assert pipeline.escalation_sm.local_strikes == 0
    assert pipeline.escalation_sm.guided_strikes == 0
    assert len(pipeline.active_plan.steps) == 1

    log_test("Deadlock Phase 2", "T2 consultation succeeds, hydrates LivingPlan, advances to TIER_3_GUIDED", True)

    # --- Phase 3: Vulnerability Verification — Strike Leakage & Infinite Panic Lockout ---
    # Step 4: First guided step executed in Tier 3, produces screen diff = 0.0
    rec4 = pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements)
    assert pipeline.escalation_sm.guided_strikes == 1
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED

    # CRITICAL OBSERVATION: Check memory._consecutive_strikes
    leaked_strikes = pipeline.memory.get_consecutive_strikes()
    is_in_loop = pipeline.memory.is_in_loop()

    # Step 5: Second guided step should be executed or escalate to Tier 4
    rec5 = pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements)

    # Check if pipeline was hijacked by legacy is_in_loop() detector
    if rec5.action.action == ActionType.PANIC:
        print("\n" + "!" * 70)
        print("EMPIRICAL DEFECT DETECTED IN DUALMINDPILINE:")
        print(f"  Step 4 consecutive strikes in memory: {leaked_strikes}")
        print(f"  Step 4 memory.is_in_loop(): {is_in_loop}")
        print(f"  Step 5 action emitted: {rec5.action.action.value} (Expected: guided action or TIER_4 escalation)")
        print(f"  Step 5 reasoning: {rec5.action.reasoning}")
        print(f"  EscalationStateMachine current_tier: {pipeline.escalation_sm.current_tier.value}")
        print(f"  EscalationStateMachine guided_strikes: {pipeline.escalation_sm.guided_strikes}")

        # Check subsequent steps to confirm infinite panic loop
        subsequent_actions = [
            pipeline.step(user_goal="Submit form", screen_frame=static_frame, grounded_elements=elements).action.action
            for _ in range(5)
        ]
        all_panic = all(a == ActionType.PANIC for a in subsequent_actions)
        print(f"  Subsequent 5 steps actions: {[a.value for a in subsequent_actions]}")
        print(f"  Infinite PANIC loop confirmed: {all_panic}")
        print("!" * 70 + "\n")

        log_test(
            "Deadlock Progression",
            "Pipeline traverses T3 -> T4 -> USER_OVERRIDE under visual deadlock",
            False,
            "CRITICAL FLAW: Leaked strikes trip memory.is_in_loop(), locking pipeline in infinite PANIC and preventing escalation to T4 and USER_OVERRIDE",
        )

    # Nominal assertion if fixed
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_4_CO_PILOT


# ===========================================================================
# 6. High-Concurrency Stress & Thread-Safety Verification
# ===========================================================================

def run_suite_6_concurrency_stress():
    print("\n" + "=" * 70)
    print("SUITE 6: Multi-Threaded Concurrency & Race Condition Stress")
    print("=" * 70)

    sm = EscalationStateMachine()
    num_threads = 8
    cycles_per_thread = 5_000
    stop_event = threading.Event()
    exceptions = []

    def worker_action_results(tid: int):
        try:
            for i in range(cycles_per_thread):
                if stop_event.is_set():
                    break
                success = (i % 3 != 0)
                diff = 0.03 if (i % 2 == 0) else 0.005
                sm.on_action_result(success=success, screen_diff=diff)
        except Exception as e:
            exceptions.append((tid, "on_action_result", e))

    def worker_interrupts(tid: int):
        try:
            for i in range(cycles_per_thread):
                if stop_event.is_set():
                    break
                if i % 10 == 0:
                    sm.on_hardware_interrupt()
                elif i % 25 == 0:
                    sm.reset()
        except Exception as e:
            exceptions.append((tid, "on_hardware_interrupt", e))

    def worker_consultations(tid: int):
        try:
            for i in range(cycles_per_thread):
                if stop_event.is_set():
                    break
                if i % 5 == 0:
                    sm.on_consultation_success()
                else:
                    sm.on_consultation_failure()
        except Exception as e:
            exceptions.append((tid, "on_consultation", e))

    threads = []
    # 3 action result workers
    for i in range(3):
        t = threading.Thread(target=worker_action_results, args=(i,))
        threads.append(t)
    # 3 interrupt / reset workers
    for i in range(3, 6):
        t = threading.Thread(target=worker_interrupts, args=(i,))
        threads.append(t)
    # 2 consultation workers
    for i in range(6, 8):
        t = threading.Thread(target=worker_consultations, args=(i,))
        threads.append(t)

    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    t_elapsed = time.perf_counter() - t_start

    passed_concurrency = (len(exceptions) == 0 and not any(t.is_alive() for t in threads))
    log_test(
        "Concurrency Stress",
        f"8 concurrent threads across {num_threads * cycles_per_thread:,} calls completed in {t_elapsed:.2f}s with 0 errors",
        passed_concurrency,
        f"(exceptions={len(exceptions)})",
    )


# ===========================================================================
# Main Execution Runner
# ===========================================================================

def main():
    print("=" * 70)
    print("PARASITE AI - MILESTONE 4B CHALLENGER 2 EMPIRICAL SUITE")
    print("=" * 70)

    try:
        run_suite_1_hardware_interrupt()
        run_suite_2_t4_to_t3_recovery()
        run_suite_3_oscillation_limits()
        run_suite_4_pipeline_preemption()
        run_suite_5_pipeline_visual_deadlock()
        run_suite_6_concurrency_stress()

        print("\n" + "=" * 70)
        print("ALL EMPIRICAL CHALLENGE SUITES PASSED SUCCESSFULLY (100% GREEN)")
        print("VERDICT: APPROVE")
        print("=" * 70)
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print("\n" + "!" * 70)
        print(f"EMPIRICAL CHALLENGE FAILED: {exc}")
        print("VERDICT: REQUEST_CHANGES")
        print("!" * 70)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
