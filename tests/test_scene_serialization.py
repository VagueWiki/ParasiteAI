"""
tests/test_scene_serialization.py - Milestone 4A Test Suite.

Verifies:
1. GroundedCapabilityContract Pydantic model and build_grounded_capability_manifest()
   - Dynamic virtual desktop bounds
   - Physical actuator limits (cubic Bézier mouse, atomic Ctrl+V, 120Hz polling)
   - Perception constraints (Set-of-Mark tags, 1:1 foveal crop, ROI diffing, caret focus)
   - Hard safety constraints (zero scraping/curl/playwright, zero programmatic UIA pattern calls, sub-2ms preemption, Ctrl+Alt+K, zero app_map)
2. serialize_textual_scene_brief()
   - Formats Active Window Brief YAML (<1 KB)
   - Formats Set-of-Mark Markdown table (<2 KB)
   - Guarantees total payload is strictly under 3 KB (< 3072 bytes) of pure text
   - Safe truncation under large element pools
3. format_gemini_consultation_prompt()
   - Embeds Grounded Capability Contract
   - Embeds Textual Scene Brief
   - Formats LivingPlan schema inside instructions
   - Backward compatibility with legacy callers
4. BrainConfig.mode default invariant ("local_llm")
5. Multi-turn clarification parsing and resolution hooks
6. PlanStep and LivingPlan schema extensions (tool_route, escalation_tier, tier_strikes, CadenceTier)
"""

from __future__ import annotations

import json
from typing import List
import pytest

from parasite_ai.config import AppConfig, BrainConfig
from parasite_ai.mind.memory import CadenceTier
from parasite_ai.mind.plan import (
    ConsultationClarificationNeeded,
    GroundedCapabilityContract,
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    build_grounded_capability_manifest,
    format_gemini_consultation_prompt,
    is_clarification_response,
    parse_gemini_consultation_response,
    resolve_clarification_query,
    serialize_textual_scene_brief,
)
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Grounded Capability Contract & Manifest Tests
# ===========================================================================

class TestGroundedCapabilityContract:
    """Verifies GroundedCapabilityContract model and manifest generation."""

    def test_default_contract_instantiation(self):
        contract = GroundedCapabilityContract()
        assert contract.version == "4.0.0"
        assert contract.target_environment == "Windows 11 64-bit Desktop"
        assert contract.virtual_desktop_bounds == (0, 0, 3840, 1080)
        assert "left_click(x, y)" in contract.actuators_mouse["primitives"]
        assert "Win+R (Run Dialog)" in contract.actuators_keyboard["supported_chords"]
        assert len(contract.hard_safety_constraints) >= 8

    def test_manifest_yaml_content_and_invariants(self):
        manifest = build_grounded_capability_manifest(vbounds=(0, 0, 3840, 1080))

        # Core headers
        assert "Parasite_Capability_Contract:" in manifest
        assert 'Version: "4.0.0"' in manifest
        assert 'Target_Environment: "Windows 11 64-bit Desktop"' in manifest
        assert "[0, 0, 3840, 1080]" in manifest

        # Physical actuator limits
        assert "Human-curved cubic Bézier trajectories" in manifest
        assert "5th-order Min-Jerk velocity profiling" in manifest
        assert "120 Hz update loop" in manifest
        assert "Atomic Ctrl+V paste (<100ms)" in manifest
        assert "KEYEVENTF_UNICODE with 25-75ms human cadence jitter" in manifest

        # Perception limits
        assert "1:1 unscaled cursor foveal crop" in manifest
        assert "Numbered Set-of-Mark (SOM) tags" in manifest
        assert "64-bit dHash gating" in manifest
        assert "GUITHREADINFO (cbSize=72)" in manifest

        # Explicit bans & hard safety constraints (VERIF-2)
        assert "ZERO headless browser automation" in manifest
        assert "ZERO headless scraping" in manifest
        assert "curl" in manifest and "playwright" in manifest and "requests" in manifest and "selenium" in manifest
        assert "ZERO programmatic accessibility pattern invocation" in manifest
        assert "ValuePattern.SetValue" in manifest and "InvokePattern.Invoke" in manifest
        assert "read-only for element discovery" in manifest
        assert "ZERO private OS message injection (WM_SETTEXT)" in manifest
        assert "Sub-2ms physical hardware preemption" in manifest
        assert "Ctrl+Alt+K" in manifest
        assert "app_map = {} is strictly forbidden" in manifest

    def test_manifest_dynamic_bounds(self):
        # Multi-monitor setup with negative primary offset
        manifest = build_grounded_capability_manifest(vbounds=(-1920, 0, 3840, 1080))
        assert "[-1920, 0, 3840, 1080]" in manifest
        assert "[-1920, 1920) x [0, 1080)" in manifest


# ===========================================================================
# 2. Textual Scene Serialization Tests
# ===========================================================================

class TestTextualSceneSerialization:
    """Verifies serialize_textual_scene_brief formatting, layout, and payload size budget."""

    @pytest.fixture
    def sample_elements(self) -> List[UIElement]:
        return [
            UIElement(
                id=1,
                role="Button",
                label="File",
                x=10,
                y=32,
                width=48,
                height=24,
                center_x=34,
                center_y=44,
                source="uia",
                is_active_window=True,
            ),
            UIElement(
                id=2,
                role="Button",
                label="Edit",
                x=58,
                y=32,
                width=48,
                height=24,
                center_x=82,
                center_y=44,
                source="uia",
                is_active_window=True,
            ),
            UIElement(
                id=3,
                role="Edit",
                label="Text Editor",
                x=0,
                y=60,
                width=1920,
                height=1020,
                center_x=960,
                center_y=570,
                source="uia",
                is_active_window=True,
            ),
            UIElement(
                id=4,
                role="Button",
                label="Close",
                x=1880,
                y=0,
                width=40,
                height=30,
                center_x=1900,
                center_y=15,
                source="uia",
                is_active_window=True,
            ),
        ]

    @pytest.fixture
    def sample_window_info(self) -> WindowInfo:
        return WindowInfo(
            hwnd=65892,
            title="Untitled - Notepad",
            class_name="Notepad",
            process_name="notepad.exe",
            process_path="C:\\Windows\\notepad.exe",
            pid=4520,
            rect=(0, 0, 1920, 1080),
            is_sensitive=False,
            reason="Nominal user application",
        )

    def test_serialize_scene_brief_standard(self, sample_elements, sample_window_info):
        brief = serialize_textual_scene_brief(
            elements=sample_elements,
            window_info=sample_window_info,
            recent_diff=0.0012,
            caret_active=True,
            active_tier="TIER_1_LOCAL",
            consecutive_strikes=1,
        )

        # 1. Payload size constraint (< 3 KB = 3072 bytes) (VERIF-5)
        payload_bytes = len(brief.encode("utf-8"))
        assert payload_bytes < 3072, f"Payload size {payload_bytes} exceeds 3 KB limit!"

        # 2. Active Window Brief YAML structure
        assert "Active_Window_Brief:" in brief
        assert 'Title: "Untitled - Notepad"' in brief
        assert 'Process_Name: "notepad.exe"' in brief
        assert "HWND: 65892" in brief
        assert "Bounds: [0, 0, 1920, 1080]" in brief
        assert 'Caret_Status: "Active (Blinking)"' in brief
        assert "Recent_Diff_Ratio: 0.0012" in brief

        # 3. Set-of-Mark Markdown table structure
        assert "Textual_Set_of_Mark_Inventory:" in brief
        assert "| ID | Control Type | Label / Accessible Name | Bounding Box [x, y, w, h] | Center (x, y) | Source | Flags |" in brief
        assert '| #1 | Button | "File" | [10, 32, 48, 24] | (34, 44) | UIA | ACTIVE |' in brief
        assert '| #2 | Button | "Edit" | [58, 32, 48, 24] | (82, 44) | UIA | ACTIVE |' in brief
        assert '| #3 | Edit | "Text Editor" | [0, 60, 1920, 1020] | (960, 570) | UIA | ACTIVE, CARET |' in brief
        assert '| #4 | Button | "Close" | [1880, 0, 40, 30] | (1900, 15) | UIA | ACTIVE |' in brief

    def test_serialize_scene_brief_empty_elements(self, sample_window_info):
        brief = serialize_textual_scene_brief(
            elements=[],
            window_info=sample_window_info,
            recent_diff=0.0,
            caret_active=False,
        )
        assert len(brief.encode("utf-8")) < 3072
        assert "No interactive controls detected" in brief
        assert 'Caret_Status: "Inactive / Hidden"' in brief

    def test_serialize_scene_brief_none_window_info(self, sample_elements):
        brief = serialize_textual_scene_brief(
            elements=sample_elements,
            window_info=None,
        )
        assert len(brief.encode("utf-8")) < 3072
        assert 'Title: "Desktop"' in brief
        assert 'Process_Name: "explorer.exe"' in brief
        assert "HWND: 0" in brief

    def test_serialize_scene_brief_large_element_pool_strictly_under_3kb(self, sample_window_info):
        # Create a large pool of 80 elements
        large_pool = [
            UIElement(
                id=i,
                role="Button",
                label=f"Action Button Number {i:03d} In Toolbar",
                x=i * 20,
                y=100,
                width=18,
                height=25,
                center_x=i * 20 + 9,
                center_y=112,
                source="uia",
            )
            for i in range(1, 81)
        ]

        brief = serialize_textual_scene_brief(
            elements=large_pool,
            window_info=sample_window_info,
            max_elements=25,
        )

        payload_bytes = len(brief.encode("utf-8"))
        assert payload_bytes < 3072, f"Payload size {payload_bytes} bytes exceeds 3 KB limit!"
        assert "Truncated" in brief
        assert "#1" in brief


# ===========================================================================
# 3. Gemini Consultation Prompt Formatting Tests
# ===========================================================================

class TestGeminiConsultationPrompt:
    """Verifies format_gemini_consultation_prompt embeds manifest, SOM, and schema."""

    def test_prompt_embeds_capability_contract_and_som_brief(self):
        elements = [
            UIElement(id=1, role="Button", label="File", x=10, y=10, width=50, height=20, center_x=35, center_y=20),
            UIElement(id=2, role="Edit", label="Input Box", x=70, y=10, width=200, height=30, center_x=170, center_y=25),
        ]
        win_info = WindowInfo(
            hwnd=12345,
            title="Calculator",
            class_name="CalcFrame",
            process_name="calc.exe",
            process_path="C:\\Windows\\calc.exe",
            pid=999,
            rect=(100, 100, 500, 600),
            is_sensitive=False,
            reason="Calculator app",
        )

        prompt = format_gemini_consultation_prompt(
            user_goal="Calculate 25 * 4",
            elements=elements,
            window_info=win_info,
            dilemma="Calculation result not updating",
            recent_history="Action 1: click #1; Action 2: type 25",
            caret_active=True,
            recent_diff=0.005,
        )

        # 1. Preamble & Contract Constraints
        assert "[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]" in prompt
        assert "# CAPABILITY CONTRACT & CONSTRAINTS" in prompt
        assert "Human-curved cubic Bézier trajectories" in prompt
        assert "ZERO headless scraping" in prompt
        assert "ZERO programmatic accessibility pattern invocation" in prompt

        # 2. Active Desktop State
        assert "# ACTIVE DESKTOP STATE" in prompt
        assert 'Foreground Window: "Calculator"' in prompt
        assert "calc.exe" in prompt
        assert "HWND: 12345" in prompt
        assert "Caret Focus: Active (Blinking)" in prompt

        # 3. SOM Inventory
        assert "# TEXTUAL SET-OF-MARK (SOM) INVENTORY" in prompt
        assert "| #1 | Button | \"File\" | [10, 10, 50, 20] |" in prompt
        assert "| #2 | Edit | \"Input Box\" | [70, 10, 200, 30] |" in prompt

        # 4. Current Goal & Dilemma
        assert "# CURRENT GOAL & FAILURE DILEMMA" in prompt
        assert "User Goal: Calculate 25 * 4" in prompt
        assert "Calculation result not updating" in prompt
        assert "Action 1: click #1" in prompt

        # 5. Instructions & Schema
        assert "# INSTRUCTIONS" in prompt
        assert "```json ... ```" in prompt
        assert '"recommended_strategy": [' in prompt
        assert '"step_id": 1' in prompt

    def test_prompt_backward_compatibility_with_legacy_kwargs(self):
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


# ===========================================================================
# 4. Config Invariant Fix Tests
# ===========================================================================

class TestConfigInvariantFix:
    """Verifies BrainConfig.mode defaults to 'local_llm' (zero silent cloud exfiltration)."""

    def test_brain_config_default_mode(self):
        bc = BrainConfig()
        assert bc.mode == "local_llm", "BrainConfig.mode must default to 'local_llm' to satisfy privacy invariant!"

    def test_app_config_default_mode(self):
        cfg = AppConfig()
        assert cfg.brain.mode == "local_llm"
        assert cfg.mind.mode == "local_llm"


# ===========================================================================
# 5. Multi-Turn Clarification Protocol Tests
# ===========================================================================

class TestMultiTurnClarificationProtocol:
    """Verifies handling of advisor clarification requests ('need_clarification': true)."""

    def test_is_clarification_response(self):
        clarification_json = """```json
{
  "need_clarification": true,
  "question": "Is the Save As dialog modal or an embedded pane?"
}
```"""
        is_clar, q = is_clarification_response(clarification_json)
        assert is_clar is True
        assert q == "Is the Save As dialog modal or an embedded pane?"

        standard_json = """```json
{
  "rationale": "Direct execution",
  "steps": [{"step_id": 1, "intent": "NAVIGATE", "description": "Click ok"}]
}
```"""
        is_clar_std, q_std = is_clarification_response(standard_json)
        assert is_clar_std is False
        assert q_std is None

    def test_parse_clarification_response_returns_consult_advisor_step(self):
        raw_clarification = """{
            "need_clarification": true,
            "question": "Is the dialog modal or embedded?"
        }"""
        plan = parse_gemini_consultation_response(raw_clarification, user_goal="Save file")

        assert isinstance(plan, LivingPlan)
        assert plan.needs_clarification is True
        assert plan.clarification_question == "Is the dialog modal or embedded?"
        assert len(plan.steps) == 1
        assert plan.steps[0].intent == StepIntent.CONSULT_ADVISOR
        assert "Clarification requested:" in plan.steps[0].description

    def test_resolve_clarification_query_dialog_inspection(self):
        win_info = WindowInfo(
            hwnd=54321,
            title="Confirm Overwrite",
            class_name="#32770",
            process_name="notepad.exe",
            process_path="C:\\Windows\\notepad.exe",
            pid=123,
            rect=(200, 200, 600, 400),
            is_sensitive=False,
            reason="Standard dialog",
        )
        response = resolve_clarification_query(
            question="Is this dialog modal?",
            window_info=win_info,
        )
        assert "Window 'Confirm Overwrite'" in response
        assert "active foreground window" in response

    def test_resolve_clarification_query_control_disambiguation(self):
        elements = [
            UIElement(id=4, role="Button", label="Search Taskbar", x=100, y=1040, width=40, height=40, center_x=120, center_y=1060),
            UIElement(id=18, role="Button", label="Search in App", x=500, y=80, width=60, height=25, center_x=530, center_y=92),
        ]
        response = resolve_clarification_query(
            question="Which search button should be clicked?",
            elements=elements,
        )
        assert "[#4] Button 'Search Taskbar'" in response
        assert "[#18] Button 'Search in App'" in response


# ===========================================================================
# 6. Schema Extensions Tests (PlanStep, LivingPlan, CadenceTier)
# ===========================================================================

class TestSchemaExtensions:
    """Verifies PlanStep tool_route, LivingPlan escalation fields, and CadenceTier."""

    def test_cadence_tier_enum_values(self):
        assert CadenceTier.TIER_1_LOCAL == "TIER_1_LOCAL"
        assert CadenceTier.TIER_2_CONSULT == "TIER_2_CONSULT"
        assert CadenceTier.TIER_3_GUIDED == "TIER_3_GUIDED"
        assert CadenceTier.TIER_4_CO_PILOT == "TIER_4_CO_PILOT"
        assert CadenceTier.USER_OVERRIDE == "USER_OVERRIDE"

    def test_plan_step_tool_route(self):
        step_gui = PlanStep(
            step_id=1,
            intent=StepIntent.NAVIGATE,
            description="Click button",
            success_criteria="Button clicked",
            tool_route="GUI",
        )
        assert step_gui.tool_route == "GUI"

        step_cli = PlanStep(
            step_id=2,
            intent=StepIntent.INPUT_DATA,
            description="Run pytest",
            success_criteria="Tests pass",
            tool_route="CLI",
        )
        assert step_cli.tool_route == "CLI"

        step_advisor = PlanStep(
            step_id=3,
            intent=StepIntent.CONSULT_ADVISOR,
            description="Consult Gemini",
            success_criteria="Plan received",
            tool_route="ADVISOR",
        )
        assert step_advisor.tool_route == "ADVISOR"

        step_default = PlanStep(
            step_id=4,
            intent=StepIntent.CONCLUDE,
            description="Finished",
            success_criteria="Complete",
        )
        assert step_default.tool_route is None

    def test_living_plan_escalation_fields(self):
        plan = LivingPlan(
            user_goal="Test goal",
            escalation_tier=CadenceTier.TIER_2_CONSULT,
            tier_strikes=1,
        )
        assert plan.escalation_tier == CadenceTier.TIER_2_CONSULT
        assert plan.tier_strikes == 1
        assert plan.needs_clarification is False
        assert plan.clarification_question is None

        # Roundtrip serialization
        dumped = plan.model_dump()
        assert dumped["escalation_tier"] == "TIER_2_CONSULT"
        assert dumped["tier_strikes"] == 1
        restored = LivingPlan.model_validate(dumped)
        assert restored.escalation_tier == CadenceTier.TIER_2_CONSULT
        assert restored.tier_strikes == 1
