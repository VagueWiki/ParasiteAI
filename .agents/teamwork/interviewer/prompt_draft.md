Implement Phase 4 (Strategic Gemini Consultation Protocol & Dynamic Contingency Branching) in full across Sub-Phases 4A through 4F for ParasiteAI as a production implementation, following the certified master plan.

Working directory: C:\ParasiteAI
Integrity mode: development

Reference document: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md

## Requirements

### R1. Sub-Phases 4A through 4F Implementation
Implement all Phase 4 sub-phases as specified in the certified master plan:
- Sub-Phase 4A: Dual-Channel Output & Grounded Capability Contract
- Sub-Phase 4B: 4-Tier Escalation State Machine
- Sub-Phase 4C: Tool-Aware Reasoning & CLI Execution Sandbox
- Sub-Phase 4D: Textual Scene Serialization
- Sub-Phase 4E: UniversalAppResolver Hardening
- Sub-Phase 4F: End-to-End Certified System Integration & Full Regression Gate

### R2. Strict Maintenance of Core Invariants
Strictly preserve all four system invariants throughout all implementations:
1. Sub-2ms low-level Win32 hardware touch preemption (LLMHF_INJECTED, LLKHF_INJECTED bitmasks).
2. Instant hard kill (Ctrl+Alt+K, taskkill /F /T /PID in <5ms).
3. brain.mode: "local_llm" default (zero silent cloud exfiltration).
4. Strict anti-hardcoding rule (no app-specific lookup tables, dynamic 3-tier UniversalAppResolver only).

## Verification Resources
- Master Plan Section 12 Victory Verification Matrix (VERIF-1 through VERIF-11) at `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`
- Pytest test suites (existing 877 passing tests plus new Phase 4 test suites)

## Acceptance Criteria

### Invariant Verification
- [ ] Synthetic input aborts within <2ms upon physical hardware mouse or keyboard event (LLMHF_INJECTED / LLKHF_INJECTED bitmasks cleared).
- [ ] Emergency hotkey Ctrl+Alt+K terminates process tree in <5ms via native taskkill.
- [ ] brain.mode defaults to "local_llm" across all configuration models with zero silent cloud exfiltration.
- [ ] No application-specific lookup tables or static coordinate mappings exist (git grep -i "app_map" parasite_ai/ yields 0 matches).

### Sub-Phase Deliverables & Verification
- [ ] Sub-Phase 4A: Grounded capability manifest and textual scene brief (<3 KB Set-of-Mark table) implemented and embedded in consultation prompt (VERIF-2, VERIF-5).
- [ ] Sub-Phase 4B: 4-tier escalation state machine implemented in DualMindPipeline, advancing T1->T2 on 2 local strikes, T3->T4 on 2 guided strikes, and transitioning to USER_OVERRIDE on 3 co-pilot strikes, 2 consultation failures, 3 escalation cycles, or hardware interrupt; passive actions and CLI returncode 0 do not incur strikes (VERIF-1).
- [ ] Sub-Phase 4C: Dual-channel output router implemented, extracting LivingPlan JSON (Channel A) supporting both steps and recommended_strategy keys, and sanitizing persona monologues (Channel B) with zero raw JSON, code blocks, backticks, or error tokens leaked to UIBridge.notify_speech() (VERIF-3).
- [ ] Sub-Phase 4D: Tool-aware affordance evaluator and CLI execution sandbox implemented with command whitelisting, scraping tool prohibition, 30s timeout, and 10ms cancellation token preemption terminating subprocess tree in <20ms (VERIF-4, VERIF-10).
- [ ] Sub-Phase 4E: UniversalAppResolver transitions from Tier 2 to Tier 3 (Win+R) on Start Search failure without looping, and PrecisionAppMatcher eliminates substring collisions (VERIF-11).
- [ ] Sub-Phase 4F: All 10 Win32 ctypes struct sizes match 64-bit Windows ABI (VERIF-9).
- [ ] Full regression gate: 100% passing tests via pytest across all existing 877 baseline tests plus all new Phase 4 test suites.
