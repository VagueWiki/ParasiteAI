"""
tests/test_gemini_consultation_protocol.py - Unit Tests for Gemini Strategic Consultation Protocol.

Validates:
- format_gemini_consultation_prompt parameter binding, whitespace normalization, and fallbacks
- extract_strategic_blueprint_json multi-pass resilient extraction (raw, fenced, conversational, trailing commas)
- parse_gemini_consultation_response conversion into validated LivingPlan instances and error handling
"""

import pytest

from parasite_ai.mind.plan import (
    LivingPlan,
    StepIntent,
    StepStatus,
    extract_strategic_blueprint_json,
    format_gemini_consultation_prompt,
    parse_gemini_consultation_response,
)


class TestGeminiConsultationPromptFormatter:
    """Verifies format_gemini_consultation_prompt output and default bindings."""

    def test_format_prompt_full_arguments(self):
        prompt = format_gemini_consultation_prompt(
            goal="Export sales spreadsheet to PDF",
            active_window_title="Excel - Q4_Report.xlsx",
            process_name="excel.exe",
            open_apps_summary="Excel, Chrome, Slack",
            visual_scene_summary="Spreadsheet visible with ribbon toolbar at top",
            dilemma_description="File menu is open but 'Export' option is obscured",
        )

        assert "[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]" in prompt
        assert "User Goal: Export sales spreadsheet to PDF" in prompt
        assert "Active Window: Excel - Q4_Report.xlsx (excel.exe)" in prompt
        assert "Visible Applications: Excel, Chrome, Slack" in prompt
        assert "Visual Scene Observation: Spreadsheet visible with ribbon toolbar at top" in prompt
        assert "Current Dilemma / Status: File menu is open but 'Export' option is obscured" in prompt
        assert "```json ... ```" in prompt
        assert '"recommended_strategy": [' in prompt

    def test_format_prompt_defaults(self):
        prompt = format_gemini_consultation_prompt(goal="Organize files")

        assert "User Goal: Organize files" in prompt
        assert "Active Window: Desktop (explorer.exe)" in prompt
        assert "Visible Applications: None" in prompt
        assert "Visual Scene Observation: Default desktop view" in prompt
        assert "Current Dilemma / Status: Initial plan formulation" in prompt

    def test_format_prompt_handles_whitespace_and_none(self):
        prompt = format_gemini_consultation_prompt(
            goal="   Launch Calculator   ",
            active_window_title="   ",
            process_name="",
            open_apps_summary=None,
            visual_scene_summary="",
            dilemma_description="   ",
        )

        assert "User Goal: Launch Calculator" in prompt
        assert "Active Window: Desktop (explorer.exe)" in prompt
        assert "Visible Applications: None" in prompt
        assert "Visual Scene Observation: Default desktop view" in prompt
        assert "Current Dilemma / Status: Initial plan formulation" in prompt


class TestStrategicBlueprintExtractor:
    """Verifies resilient JSON extraction from varied LLM outputs."""

    def test_extract_direct_raw_json(self):
        raw = """{
            "rationale": "Direct plan formulation",
            "recommended_strategy": [
                {
                    "step_id": 1,
                    "intent": "NAVIGATE",
                    "description": "Click start menu",
                    "success_criteria": "Start menu open"
                }
            ]
        }"""
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert extracted["rationale"] == "Direct plan formulation"
        assert len(extracted["recommended_strategy"]) == 1

    def test_extract_markdown_json_codeblock(self):
        raw = """Here is the strategic plan you requested:
```json
{
    "rationale": "Restore minimized window first",
    "recommended_strategy": [
        {
            "step_id": 1,
            "intent": "LAUNCH_OR_ACTIVATE",
            "description": "Click taskbar icon for Notepad",
            "target_description": "Taskbar Notepad rectangle",
            "success_criteria": "Notepad window active in foreground"
        }
    ]
}
```
Please let me know if you need adjustments."""
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert extracted["rationale"] == "Restore minimized window first"
        assert extracted["recommended_strategy"][0]["intent"] == "LAUNCH_OR_ACTIVATE"

    def test_extract_markdown_codeblock_without_json_tag(self):
        raw = """```
{
    "rationale": "Untagged fence block",
    "recommended_strategy": []
}
```"""
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert extracted["rationale"] == "Untagged fence block"

    def test_extract_conversational_embedded_json(self):
        raw = (
            "Certainly! Based on your desktop situation, here is the diagnosis: "
            '{"rationale": "Dialog needs dismissal", "recommended_strategy": ['
            '{"step_id": 1, "intent": "DISMISS_DIALOG", "description": "Click Cancel", "success_criteria": "Dialog gone"}'
            "]} Hope that solves the issue!"
        )
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert extracted["rationale"] == "Dialog needs dismissal"
        assert len(extracted["recommended_strategy"]) == 1

    def test_extract_json_with_trailing_commas(self):
        raw = """{
            "rationale": "Trailing comma resilience test",
            "recommended_strategy": [
                {
                    "step_id": 1,
                    "intent": "SELECT_OPTION",
                    "description": "Click Save As",
                    "success_criteria": "Save As dialog opens",
                },
            ],
        }"""
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert extracted["rationale"] == "Trailing comma resilience test"
        assert len(extracted["recommended_strategy"]) == 1

    def test_extract_json_with_nested_strings_and_braces(self):
        raw = """{
            "rationale": "Handling curly braces inside {strings} like '{foo}' correctly",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "INPUT_DATA",
                    "description": "Type text containing {escaped} brackets",
                    "success_criteria": "Confirmed {all}"
                }
            ]
        }"""
        extracted = extract_strategic_blueprint_json(raw)
        assert extracted is not None
        assert "Handling curly braces inside {strings}" in extracted["rationale"]
        assert len(extracted["steps"]) == 1

    def test_extract_non_plan_returns_none(self):
        assert extract_strategic_blueprint_json("") is None
        assert extract_strategic_blueprint_json(None) is None
        assert extract_strategic_blueprint_json("Hello, I am Gemini. What can I do for you today?") is None
        # Valid JSON but irrelevant keys
        assert extract_strategic_blueprint_json('{"weather": "sunny", "temperature": 72}') is None


class TestParseGeminiConsultationResponse:
    """Verifies parse_gemini_consultation_response translation into LivingPlan instances."""

    def test_parse_valid_standard_response(self):
        raw_text = """```json
{
  "rationale": "Notepad is running in background. Needs activation before typing.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "LAUNCH_OR_ACTIVATE",
      "description": "Activate Notepad from taskbar",
      "target_description": "Notepad button on taskbar",
      "success_criteria": "Notepad window has focus",
      "contingency": "If not found on taskbar, search via start menu"
    },
    {
      "step_id": 2,
      "intent": "INPUT_DATA",
      "description": "Type introductory greeting",
      "target_description": "Notepad text area",
      "success_criteria": "Text appears in document",
      "contingency": "If focus lost, click text area again"
    },
    {
      "step_id": 3,
      "intent": "CONCLUDE",
      "description": "Confirm task completion",
      "success_criteria": "Document ready",
      "contingency": null
    }
  ]
}
```"""
        plan = parse_gemini_consultation_response(raw_text, user_goal="Write a greeting in Notepad")

        assert isinstance(plan, LivingPlan)
        assert plan.user_goal == "Write a greeting in Notepad"
        assert plan.overall_strategy == "Notepad is running in background. Needs activation before typing."
        assert plan.consulted_gemini is True
        assert plan.replan_count == 0
        assert len(plan.steps) == 3

        # First step must be active (IN_PROGRESS)
        assert plan.current_step_id == 1
        assert plan.steps[0].status == StepStatus.IN_PROGRESS
        assert plan.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE
        assert plan.steps[0].contingency == "If not found on taskbar, search via start menu"

        # Subsequent steps must be PENDING
        assert plan.steps[1].status == StepStatus.PENDING
        assert plan.steps[1].intent == StepIntent.INPUT_DATA
        assert plan.steps[2].status == StepStatus.PENDING
        assert plan.steps[2].intent == StepIntent.CONCLUDE

    def test_parse_alternative_keys_and_intent_fallbacks(self):
        raw_text = """{
            "overall_strategy": "Alternative strategy key",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "click",
                    "description": "Click the submit button",
                    "target_description": "Submit button"
                },
                {
                    "step_id": 2,
                    "intent": "write",
                    "description": "Enter the verification code"
                },
                {
                    "step_id": 3,
                    "intent": "SOMETHING_STRANGE",
                    "description": "Fallback to navigate"
                }
            ]
        }"""
        plan = parse_gemini_consultation_response(raw_text, user_goal="Submit form")

        assert plan.overall_strategy == "Alternative strategy key"
        assert len(plan.steps) == 3
        # "click" mapped to NAVIGATE
        assert plan.steps[0].intent == StepIntent.NAVIGATE
        # "write" mapped to INPUT_DATA
        assert plan.steps[1].intent == StepIntent.INPUT_DATA
        # unknown verb mapped to NAVIGATE
        assert plan.steps[2].intent == StepIntent.NAVIGATE

    def test_parse_empty_steps_blueprint(self):
        raw_text = '{"rationale": "No actions needed at this time", "recommended_strategy": []}'
        plan = parse_gemini_consultation_response(raw_text, user_goal="Idle check")

        assert plan.overall_strategy == "No actions needed at this time"
        assert len(plan.steps) == 0
        assert plan.current_step_id == 1
        assert plan.consulted_gemini is True

    def test_parse_invalid_response_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to extract strategic blueprint from Gemini response"):
            parse_gemini_consultation_response("I apologize, but I cannot fulfill this request.", user_goal="Test")

        with pytest.raises(ValueError, match="Failed to extract strategic blueprint"):
            parse_gemini_consultation_response("", user_goal="Test")
