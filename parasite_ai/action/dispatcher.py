"""
parasite_ai/action/dispatcher.py - Deterministic Action Dispatcher with CLI Sandbox Execution.
"""
from parasite_ai.mind.dual_mind import ActionDispatcher, ActionResult
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.affordance import CLIExecutionSandbox

__all__ = [
    "ActionDispatcher",
    "ActionResult",
    "ActionPlan",
    "ActionType",
    "CLIExecutionSandbox",
]
