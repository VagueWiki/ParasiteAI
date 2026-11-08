# Rule: Strict Stint Cadence & Gated Milestone Execution

## 1. Single-Stint Execution Boundary
- Under no circumstances may the agent execute more than one stint or milestone in a single conversation turn or session.
- Once the scope of an approved stint is verified and tested, the agent MUST immediately stop modifying code and await the user's explicit command to proceed to the next stint.
- Never cascade from one stint into the next (e.g. from P0.1 into P0.2, or P0.2 into P0.3) without a distinct, standalone plan and explicit user sign-off.

## 2. Mandatory Stint Planning & Approval Gate
Before touching any production code or test files for a new stint:
1. Formulate a dedicated implementation plan (`<stint_id>_implementation_plan.md`) with `RequestFeedback: true`.
2. Present the technical design, diffs, and verification commands.
3. STOP and wait for the user's explicit approval or feedback.
4. Do NOT execute code changes until approval is explicitly registered.

## 3. Verification & Walkthrough Gate
Upon completing the implementation steps for an approved stint:
1. Run all specified automated and manual verification commands.
2. Generate or update a comprehensive walkthrough artifact (`walkthrough.md`).
3. Report the exact verification results and telemetry to the user.
4. STOP and prompt the user for review. Do not announce readiness for subsequent stages or milestones until the current stint is acknowledged and closed.
