"""
parasite_ai/safety/risk_gate.py - Deterministic Action Risk Classifier & Interactive Consent Gate.

Evaluates ActionPlans produced by the VLM / Planner and classifies their risk into:
- GREEN: Safe, read-only, non-destructive navigation / typing / observation.
- YELLOW: State-mutating actions (closing apps, sending messages, submitting forms, general CLI).
- RED: Irreversible destruction, credential manipulation, system commands (del, format, wipe).
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from parasite_ai.mind.memory import ActionPlan, ActionType


class ActionRisk(str, Enum):
    """Categorical risk severity tiers."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class RiskAssessment(BaseModel):
    """Result of an action risk evaluation."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    risk: ActionRisk = ActionRisk.GREEN
    reason: str = "Safe observational or navigation action."
    matched_pattern: Optional[str] = None


class ActionConsentRequest(BaseModel):
    """Payload presented to human operator or C2 interface for authorization."""
    model_config = ConfigDict(extra="ignore", validate_default=True)

    step_id: int = 0
    action_plan: ActionPlan
    risk: ActionRisk
    reason: str
    foreground_title: str = ""
    foreground_process: str = ""


# Destructive shell / system command patterns (RED)
RED_CLI_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\b(rm|del|erase|rmdir|rd|remove-item)\b", re.IGNORECASE),
    re.compile(r"\b(format|diskpart|fdisk|mkfs)\b", re.IGNORECASE),
    re.compile(r"\b(reg\s+delete|reg\s+add)\b", re.IGNORECASE),
    re.compile(r"\b(shutdown|restart-computer|stop-computer)\b", re.IGNORECASE),
    re.compile(r"\b(net\s+user|net\s+localgroup)\b", re.IGNORECASE),
    re.compile(r"\bpowershell(\.exe)?\s+(-(e|enc|encodedcommand))\b", re.IGNORECASE),
    re.compile(r"\b(drop\s+database|drop\s+table|truncate\s+table)\b", re.IGNORECASE),
    re.compile(r"\b(curl|wget|iwr|irm).*\|\s*(sh|bash|powershell|cmd)\b", re.IGNORECASE),
]

# Irreversible GUI operations / credential exfiltration patterns (RED)
RED_TEXT_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\b(delete\s+permanently|permanently\s+delete)\b", re.IGNORECASE),
    re.compile(r"\b(empty\s+recycle\s+bin|empty\s+trash)\b", re.IGNORECASE),
    re.compile(r"\b(uninstall|format\s+drive|wipe\s+disk)\b", re.IGNORECASE),
    re.compile(r"\b(private\s+key|id_rsa|master\s+password)\b", re.IGNORECASE),
    re.compile(r"\b(credit\s+card|cvv|bank\s+account|routing\s+number)\b", re.IGNORECASE),
]

# Risky keyboard shortcuts (YELLOW)
YELLOW_HOTKEY_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\b(alt\+f4|ctrl\+w|ctrl\+q|win\+x|win\+r)\b", re.IGNORECASE),
    re.compile(r"\b(ctrl\+shift\+(esc|delete|del))\b", re.IGNORECASE),
    re.compile(r"\b(ctrl\+alt\+delete)\b", re.IGNORECASE),
]

# Mutating or financial/comm verbs in reasoning / text / target (YELLOW)
YELLOW_VERB_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\b(delete|remove|erase|clear\s+all|purge)\b", re.IGNORECASE),
    re.compile(r"\b(send|submit|publish|post|tweet|broadcast)\b", re.IGNORECASE),
    re.compile(r"\b(buy|purchase|checkout|pay|transfer|order|subscribe)\b", re.IGNORECASE),
    re.compile(r"\b(close|quit|exit|terminate|kill)\b", re.IGNORECASE),
    re.compile(r"\b(overwrite|replace|save\s+over|drop)\b", re.IGNORECASE),
]


def classify_action_risk(
    action_plan: ActionPlan,
    foreground_title: str = "",
    foreground_process: str = "",
) -> RiskAssessment:
    """
    Evaluates an ActionPlan and returns deterministic RiskAssessment.
    """
    # 1. Evaluate BURST actions hierarchically
    if action_plan.action == ActionType.BURST and action_plan.burst_actions:
        highest_risk = ActionRisk.GREEN
        worst_assessment = RiskAssessment(risk=ActionRisk.GREEN, reason="Safe burst sequence.")
        for sub_plan in action_plan.burst_actions:
            sub_res = classify_action_risk(sub_plan, foreground_title, foreground_process)
            if sub_res.risk == ActionRisk.RED:
                return sub_res
            if sub_res.risk == ActionRisk.YELLOW:
                highest_risk = ActionRisk.YELLOW
                worst_assessment = sub_res
        return worst_assessment

    combined_text = " ".join([
        action_plan.text or "",
        action_plan.reasoning or "",
        " ".join(action_plan.keys or []),
        action_plan.cli_command or "",
    ]).strip()

    # -------------------------------------------------------------------------
    # 2. Check for RED severity triggers
    # -------------------------------------------------------------------------

    # CLI Command Red Checks
    if action_plan.action == ActionType.RUN_CLI_COMMAND and action_plan.cli_command:
        cmd = action_plan.cli_command.strip()
        for pat in RED_CLI_PATTERNS:
            if pat.search(cmd):
                return RiskAssessment(
                    risk=ActionRisk.RED,
                    reason=f"Destructive or high-privilege CLI command detected: {pat.pattern}",
                    matched_pattern=pat.pattern,
                )

    # Text / Reasoning / Hotkey Red Checks
    for pat in RED_TEXT_PATTERNS:
        if pat.search(combined_text):
            return RiskAssessment(
                risk=ActionRisk.RED,
                reason=f"Irreversible or credential-sensitive operation detected: {pat.pattern}",
                matched_pattern=pat.pattern,
            )

    # -------------------------------------------------------------------------
    # 3. Check for YELLOW severity triggers
    # -------------------------------------------------------------------------

    # Any non-red CLI command is YELLOW
    if action_plan.action == ActionType.RUN_CLI_COMMAND:
        return RiskAssessment(
            risk=ActionRisk.YELLOW,
            reason=f"Execution of shell command on host: {action_plan.cli_command or 'CLI command'}",
            matched_pattern="RUN_CLI_COMMAND",
        )

    # Risky hotkeys
    if action_plan.action == ActionType.HOTKEY and action_plan.keys:
        chord = "+".join(action_plan.keys).lower()
        for pat in YELLOW_HOTKEY_PATTERNS:
            if pat.search(chord):
                return RiskAssessment(
                    risk=ActionRisk.YELLOW,
                    reason=f"Disruptive shortcut combination detected: {chord}",
                    matched_pattern=pat.pattern,
                )

    # Window close actions
    if action_plan.action == ActionType.CLOSE_WINDOW:
        return RiskAssessment(
            risk=ActionRisk.YELLOW,
            reason=f"Window close requested for active window '{foreground_title or foreground_process}'",
            matched_pattern="CLOSE_WINDOW",
        )

    # State-mutating text / click verbs
    for pat in YELLOW_VERB_PATTERNS:
        if pat.search(combined_text):
            return RiskAssessment(
                risk=ActionRisk.YELLOW,
                reason=f"Potentially state-mutating or communications action: {pat.pattern}",
                matched_pattern=pat.pattern,
            )

    # Explicit submit flag on text input
    if action_plan.submit:
        return RiskAssessment(
            risk=ActionRisk.YELLOW,
            reason="Text entry requests automatic form/message submission (Enter key).",
            matched_pattern="submit=True",
        )

    # -------------------------------------------------------------------------
    # 4. Default to GREEN
    # -------------------------------------------------------------------------
    return RiskAssessment(
        risk=ActionRisk.GREEN,
        reason="Safe observational, navigation, or benign input action.",
    )
