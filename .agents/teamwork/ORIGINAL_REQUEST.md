# Original User Request

## Initial Request — 2026-11-01T02:22:00Z

Summarize all preplanning changes and update the Phase 4 master plan document for ParasiteAI to prepare for implementation, incorporating the agreed architectural additions.

Working directory: C:\ParasiteAI
Integrity mode: development

Reference material:
- Existing Master Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
- Project Handoff: C:\ParasiteAI\HANDOFF.md

## Requirements

### R1. Preplanning Summary & Master Plan Finalization
Update `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` directly to summarize all architectural changes and decisions reached since the initial document, producing an updated, comprehensive implementation plan for Phase 4. Incorporate the 7 agreed architectural additions:
1. 4-Tier Escalation Cadence: 2 local attempts -> deep Gemini consultation -> 2 guided local attempts with Gemini blueprint -> continuous Gemini handholding / visual co-pilot -> user override.
2. Grounded Capability Contract: Gemini receives an explicit manifest of physical actuators (Bézier mouse, atomic Ctrl+V paste, Set-of-Mark perception, ROI diffing) and constraints (no headless scraping, touch preemption).
3. Dual-Channel Output: Internal machine-interpretable LivingPlan JSON vs. visible Companion Dock character monologue (no raw JSON shown to user).
4. Tool-Aware Reasoning & Antigravity Meta-Tooling: Evaluating whether goals are best achieved via GUI manipulation, local developer tools (Antigravity CLI / scripts), or Gemini consultation.
5. Textual Scene Serialization: No video streaming; scenes are serialized into structured Set-of-Mark + active window briefs.
6. Strict Anti-Hardcoding Invariant: Zero hardcoded app maps, hints, or canned workflows.
7. Schema mapping: Complete inventory of Pydantic models (UIElement, BoundingBox, PlanStep, LivingPlan, ActionPlan, StepRecord, AppConfig) and Win32 structs mapped to runtime hooks.

### R2. Maintain Core Invariants
Ensure the updated plan explicitly preserves all core system invariants: sub-2ms hardware touch preemption, Ctrl+Alt+K instant hard kill, brain.mode: "local_llm" default (zero silent cloud exfiltration), and the strict anti-hardcoding rule across all sub-phases.

## Acceptance Criteria

### Master Plan & Architectural Completeness
- [ ] `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` is updated with a summary of changes and a finalized Phase 4 architecture and implementation roadmap.
- [ ] The updated document fully details all 7 key architectural additions:
  - 4-Tier Escalation Cadence with explicit strike counters, trigger conditions, and transition logic.
  - Grounded Capability Contract specifying actuator limits and perception constraints for consultations.
  - Dual-Channel Output routing internal JSON to LivingPlan and character monologues to Companion Dock.
  - Tool-Aware Reasoning heuristics evaluating GUI vs. CLI / Antigravity meta-tooling vs. advisor consultation.
  - Textual Scene Serialization using Set-of-Mark representations without video streaming.
  - Strict Anti-Hardcoding Invariant forbidding app-specific lookup tables and canned workflows.
  - Complete Schema Mapping inventory of Pydantic models and Win32 structs mapped to runtime hooks.
- [ ] Core system invariants (sub-2ms touch preemption, Ctrl+Alt+K kill, brain.mode: "local_llm" default, zero silent cloud exfiltration) are explicitly maintained in all sub-phase specifications.


## Follow-up — 2026-11-01T07:36:36Z

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
