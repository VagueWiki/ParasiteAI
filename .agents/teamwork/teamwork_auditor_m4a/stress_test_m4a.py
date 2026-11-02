"""
Adversarial stress-test script for Milestone 4A: Capability Contract & Textual Scene Serialization
Location: C:\ParasiteAI\.agents\teamwork\teamwork_auditor_m4a\stress_test_m4a.py
"""

import json
import pytest
from parasite_ai.mind.plan import (
    GroundedCapabilityContract,
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    build_grounded_capability_manifest,
    format_gemini_consultation_prompt,
    serialize_textual_scene_brief,
    extract_strategic_blueprint_json,
    parse_gemini_consultation_response,
    is_clarification_response,
    resolve_clarification_query,
)
from parasite_ai.mind.memory import CadenceTier
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement

def stress_test_serialization_payload_budget():
    print("[STRESS TEST] Testing serialize_textual_scene_brief with 1000 pathological elements...")
    # Create 1000 elements with huge multiline labels, emojis, pipes, and control chars
    pathological_elements = []
    for i in range(1000):
        pathological_elements.append(
            UIElement(
                id=i + 1,
                role="VeryLongCustomRoleNameThatExceedsNormalBounds" if i % 2 == 0 else "Button",
                label=f"Label | with pipes | \n newlines \r\t and emojis 🚀🔥💡 and super long string " * 5,
                x=-1000 + i,
                y=-500 + i,
                width=i,
                height=i,
                center_x=-1000 + i,
                center_y=-500 + i,
                source="merged" if i % 3 == 0 else "uia",
            )
        )

    win = WindowInfo(
        hwnd=99999999,
        title="Complex | Window \n With \t Weird / Characters 🔥",
        class_name="WeirdClass",
        process_name="weird_process.exe",
        process_path="C:\\weird\\path.exe",
        pid=12345,
        rect=(-1920, 0, 1920, 1080),
        is_sensitive=False,
        reason="Stress testing",
    )

    brief = serialize_textual_scene_brief(
        elements=pathological_elements,
        window_info=win,
        recent_diff=0.99999,
        caret_active=True,
        max_elements=100,
    )

    payload_size = len(brief.encode("utf-8"))
    print(f"Pathological payload size: {payload_size} bytes (limit is 3072 bytes)")
    assert payload_size < 3072, f"STRESS TEST FAILED: Payload size {payload_size} >= 3072 bytes!"
    assert "Active_Window_Brief:" in brief
    assert "Textual_Set_of_Mark_Inventory:" in brief
    print("[STRESS TEST] PASS: Payload size strictly remains under 3 KB even with 1000 pathological elements.")

def stress_test_extreme_manifest_bounds():
    print("[STRESS TEST] Testing build_grounded_capability_manifest with extreme bounds...")
    bounds_cases = [
        (-3840, -1080, 7680, 2160),
        (0, 0, 0, 0),
        (-10000, -10000, 20000, 20000),
    ]
    for b in bounds_cases:
        manifest = build_grounded_capability_manifest(vbounds=b)
        assert "Parasite_Capability_Contract:" in manifest
        assert f"[{b[0]}, {b[1]}, {b[2]}, {b[3]}]" in manifest
    print("[STRESS TEST] PASS: Dynamic bounds handled gracefully across extreme bounds.")

def stress_test_blueprint_extraction_resilience():
    print("[STRESS TEST] Testing extract_strategic_blueprint_json with messy and adversarial strings...")

    # Case 1: Trailing commas
    trailing_comma_json = """```json
    {
      "rationale": "Testing trailing commas",
      "recommended_strategy": [
        {
          "step_id": 1,
          "intent": "NAVIGATE",
          "description": "Click ok",
          "success_criteria": "Ok clicked",
        },
      ],
    }
    ```"""
    parsed1 = extract_strategic_blueprint_json(trailing_comma_json)
    assert parsed1 is not None, "Failed to parse JSON with trailing commas!"
    plan1 = parse_gemini_consultation_response(trailing_comma_json, user_goal="Test goal")
    assert len(plan1.steps) == 1

    # Case 2: Deeply embedded JSON in conversational chatter
    chatter = """
    Certainly! Based on my review of the situation, here is the diagnosis.
    The primary reason for the failure is that the window was not in focus.
    
    ```json
    {
      "rationale": "Window focus missing",
      "steps": [
        {"step_id": 1, "intent": "LAUNCH_OR_ACTIVATE", "description": "Focus window", "success_criteria": "Window focused"}
      ]
    }
    ```
    
    I hope this helps! Let me know if you run into any issues.
    """
    parsed2 = extract_strategic_blueprint_json(chatter)
    assert parsed2 is not None
    plan2 = parse_gemini_consultation_response(chatter, user_goal="Focus window")
    assert len(plan2.steps) == 1
    assert plan2.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE

    # Case 3: Completely invalid / non-blueprint text raises ValueError
    non_json = "Hello, I cannot help you with that task because reasons."
    with pytest.raises(ValueError) as excinfo:
        parse_gemini_consultation_response(non_json, user_goal="Test")
    assert "Failed to extract strategic blueprint" in str(excinfo.value)

    print("[STRESS TEST] PASS: JSON extraction and fallback parsing demonstrated high resilience.")

def stress_test_cadence_tier_validation():
    print("[STRESS TEST] Testing CadenceTier validation and LivingPlan roundtrip...")
    from pydantic import ValidationError

    # Invalid tier string should fail validation
    with pytest.raises(ValidationError):
        LivingPlan(user_goal="Test", escalation_tier="TIER_99_NONEXISTENT")

    valid_plan = LivingPlan(
        user_goal="Refactor code",
        escalation_tier=CadenceTier.TIER_3_GUIDED,
        tier_strikes=2,
    )
    dumped = valid_plan.model_dump_json()
    reloaded = LivingPlan.model_validate_json(dumped)
    assert reloaded.escalation_tier == CadenceTier.TIER_3_GUIDED
    assert reloaded.tier_strikes == 2
    print("[STRESS TEST] PASS: CadenceTier and LivingPlan roundtrip verified.")

if __name__ == "__main__":
    print("=== STARTING MILESTONE 4A ADVERSARIAL STRESS TESTS ===")
    stress_test_serialization_payload_budget()
    stress_test_extreme_manifest_bounds()
    stress_test_blueprint_extraction_resilience()
    stress_test_cadence_tier_validation()
    print("=== ALL MILESTONE 4A ADVERSARIAL STRESS TESTS PASSED ===")
