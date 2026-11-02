"""
C:\\ParasiteAI\\.agents\\teamwork\\teamwork_challenger_m4a_2\\stress_test_m4a_challenger2.py

Empirical Challenger 2 Test Suite for Milestone 4A:
1. BrainConfig.mode default invariance across config instantiations (BrainConfig, AppConfig, load_config with missing/empty keys, env overrides, zero silent cloud fallback).
2. Multi-turn clarification hooks under malformed JSON, partial queries, ambiguous controls with overlapping coordinates, and candidate volume scaling.
3. Backward compatibility of format_gemini_consultation_prompt (legacy kwargs, partial args, positional args, extra kwargs, template alias).
"""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import List, Any
import pytest
from pydantic import ValidationError

from parasite_ai.config import AppConfig, BrainConfig, load_config
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.memory import CadenceTier
from parasite_ai.mind.plan import (
    ConsultationClarificationNeeded,
    GEMINI_CONSULTATION_TEMPLATE,
    GroundedCapabilityContract,
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    extract_strategic_blueprint_json,
    format_gemini_consultation_prompt,
    is_clarification_response,
    parse_gemini_consultation_response,
    resolve_clarification_query,
    serialize_textual_scene_brief,
)
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement


# ===========================================================================
# Suite 1: BrainConfig.mode Default Invariance & Zero Cloud Exfiltration Tests
# ===========================================================================

class TestBrainConfigModeInvariance:
    """Empirically tests that BrainConfig.mode defaults to 'local_llm' across all instantiation paths."""

    def test_brainconfig_direct_instantiation(self):
        bc = BrainConfig()
        assert bc.mode == "local_llm", f"Expected default mode 'local_llm', got '{bc.mode}'"
        assert bc.local_model.model_id == "Qwen/Qwen2.5-3B-Instruct-GGUF"

    def test_appconfig_direct_instantiation(self):
        cfg = AppConfig()
        assert cfg.brain.mode == "local_llm", f"Expected AppConfig.brain.mode 'local_llm', got '{cfg.brain.mode}'"
        assert cfg.mind.mode == "local_llm", f"Expected AppConfig.mind.mode 'local_llm', got '{cfg.mind.mode}'"

    def test_load_config_missing_brain_key(self):
        yaml_content = """
system:
  log_level: "WARNING"
safety:
  interrupt_enabled: true
"""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
            f.write(yaml_content)
            temp_path = f.name
        try:
            cfg = load_config(temp_path)
            assert cfg.brain.mode == "local_llm", f"Missing brain key did not default to 'local_llm': {cfg.brain.mode}"
            assert cfg.mind.mode == "local_llm"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_config_empty_brain_key(self):
        yaml_content = """
system:
  log_level: "INFO"
brain: {}
"""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
            f.write(yaml_content)
            temp_path = f.name
        try:
            cfg = load_config(temp_path)
            assert cfg.brain.mode == "local_llm", f"Empty brain key did not default to 'local_llm': {cfg.brain.mode}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_config_mind_alias_without_mode(self):
        yaml_content = """
mind:
  local_model:
    gpu_layers: 24
"""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
            f.write(yaml_content)
            temp_path = f.name
        try:
            cfg = load_config(temp_path)
            assert cfg.brain.mode == "local_llm", f"mind alias without mode did not default to 'local_llm': {cfg.brain.mode}"
            assert cfg.brain.local_model.gpu_layers == 24
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_config_empty_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
            f.write("")
            temp_path = f.name
        try:
            cfg = load_config(temp_path)
            assert cfg.brain.mode == "local_llm", f"Empty YAML file did not default to 'local_llm': {cfg.brain.mode}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_config_nonexistent_file_self_healing(self):
        nonexistent = Path(tempfile.gettempdir()) / "nonexistent_parasite_config_test_4a.yaml"
        if nonexistent.exists():
            nonexistent.unlink()
        try:
            cfg = load_config(str(nonexistent))
            assert cfg.brain.mode == "local_llm", f"Self-healed config did not default to 'local_llm': {cfg.brain.mode}"
        finally:
            if nonexistent.exists():
                nonexistent.unlink()

    def test_brainconfig_mode_validation_rejects_exfiltration_modes(self):
        with pytest.raises(ValidationError):
            BrainConfig(mode="cloud_exfiltration")

        with pytest.raises(ValidationError):
            BrainConfig(mode="external_api")

        with pytest.raises(ValidationError):
            BrainConfig(mode="")

        with pytest.raises(ValidationError):
            BrainConfig(mode=None)

    def test_brainmanager_initializes_with_local_llm_mode(self):
        cfg = AppConfig()
        bm = LocalBrainManager(cfg)
        assert bm.mode == BrainMode.LOCAL_LLM, f"BrainManager initialized with mode '{bm.mode}', expected BrainMode.LOCAL_LLM"
        assert bm.mode.value == "local_llm"

    def test_env_var_override_behavior(self, monkeypatch):
        # 1. PARASITE_BRAIN_MODE set to valid alternative
        monkeypatch.setenv("PARASITE_BRAIN_MODE", "mock")
        cfg_mock = AppConfig()
        assert cfg_mock.brain.mode == "mock"

        # 2. PARASITE_BRAIN_MODE set to invalid
        monkeypatch.setenv("PARASITE_BRAIN_MODE", "unauthorized_cloud_pipeline")
        with pytest.raises(ValidationError):
            AppConfig()

        # 3. PARASITE_BRAIN_MODE unset restores invariant default
        monkeypatch.delenv("PARASITE_BRAIN_MODE", raising=False)
        cfg_default = AppConfig()
        assert cfg_default.brain.mode == "local_llm"


# ===========================================================================
# Suite 2: Multi-Turn Clarification Hooks Under Adversarial & Malformed Stress
# ===========================================================================

class TestMultiTurnClarificationHooks:
    """Stress-tests multi-turn clarification hooks against malformed JSON, partial queries, and edge coordinates."""

    def test_is_clarification_response_canonical(self):
        raw = '{"need_clarification": true, "question": "Which monitor is active?"}'
        is_clar, q = is_clarification_response(raw)
        assert is_clar is True
        assert q == "Which monitor is active?"

    def test_is_clarification_response_markdown_fenced_with_surrounding_text(self):
        raw = """
Strategic Advisor Analysis:
The screen has multiple potential submit targets.

```json
{
  "need_clarification": true,
  "question": "Is the Save As window an OS dialog or in-app modal?"
}
```

Awaiting your confirmation.
"""
        is_clar, q = is_clarification_response(raw)
        assert is_clar is True
        assert q == "Is the Save As window an OS dialog or in-app modal?"

    def test_is_clarification_response_with_trailing_comma(self):
        raw = '{"need_clarification": true, "question": "Is the button visible?", }'
        is_clar, q = is_clarification_response(raw)
        assert is_clar is True
        assert q == "Is the button visible?"

    def test_is_clarification_response_multiple_fences_with_first_broken(self):
        raw = """
```json
{this is broken json
```

```json
{
  "need_clarification": true,
  "question": "Which tab is currently focused?"
}
```
"""
        is_clar, q = is_clarification_response(raw)
        assert is_clar is True
        assert q == "Which tab is currently focused?"

    def test_is_clarification_response_malformed_unbalanced_braces(self):
        # Truncated json
        raw = '{"need_clarification": true, "question": "Where is the button?'
        is_clar, q = is_clarification_response(raw)
        assert is_clar is False
        assert q is None

    def test_is_clarification_response_arbitrary_text_and_html(self):
        raw = "<html><body><h1>502 Bad Gateway</h1>Cloud consultation unavailable.</body></html>"
        is_clar, q = is_clarification_response(raw)
        assert is_clar is False
        assert q is None

    def test_is_clarification_response_missing_question_key(self):
        raw = '{"need_clarification": true}'
        is_clar, q = is_clarification_response(raw)
        assert is_clar is True
        assert q == "Clarification required"

    def test_is_clarification_response_empty_and_null_question(self):
        raw_empty = '{"need_clarification": true, "question": ""}'
        is_clar_1, q_1 = is_clarification_response(raw_empty)
        assert is_clar_1 is True
        assert q_1 == "Clarification required"

        raw_null = '{"need_clarification": true, "question": null}'
        is_clar_2, q_2 = is_clarification_response(raw_null)
        assert is_clar_2 is True
        # Note: str(None) evaluates to "None" in plan.py:664
        assert q_2 in ("None", "Clarification required")

    def test_is_clarification_response_strict_boolean_type(self):
        # String 'true' should NOT be accepted as boolean True
        raw_str = '{"need_clarification": "true", "question": "Q?"}'
        is_clar_str, _ = is_clarification_response(raw_str)
        assert is_clar_str is False

        # Integer 1 should NOT be accepted as boolean True
        raw_int = '{"need_clarification": 1, "question": "Q?"}'
        is_clar_int, _ = is_clarification_response(raw_int)
        assert is_clar_int is False

        # Boolean False
        raw_false = '{"need_clarification": false, "question": "Q?"}'
        is_clar_false, _ = is_clarification_response(raw_false)
        assert is_clar_false is False

    def test_parse_gemini_consultation_response_clarification_hydration(self):
        raw = """```json
{
  "need_clarification": true,
  "question": "Is the prompt asking to overwrite existing draft?"
}
```"""
        plan = parse_gemini_consultation_response(raw, user_goal="Save draft document")
        assert plan.needs_clarification is True
        assert plan.clarification_question == "Is the prompt asking to overwrite existing draft?"
        assert plan.consulted_gemini is True
        assert len(plan.steps) == 1

        step = plan.steps[0]
        assert step.intent == StepIntent.CONSULT_ADVISOR
        assert step.status == StepStatus.IN_PROGRESS
        assert "Clarification requested:" in step.description
        assert "WS_POPUP / IsModal" in step.contingency

    def test_parse_gemini_consultation_response_malformed_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to extract strategic blueprint"):
            parse_gemini_consultation_response("This response has no JSON at all", user_goal="Goal")

        with pytest.raises(ValueError, match="Failed to extract strategic blueprint"):
            parse_gemini_consultation_response("```json\n[1, 2, 3]\n```", user_goal="Goal")

        with pytest.raises(ValueError, match="Failed to extract strategic blueprint"):
            parse_gemini_consultation_response("", user_goal="Goal")

    def test_parse_gemini_consultation_response_resilience_to_partial_steps(self):
        # Blueprint with sparse step fields and non-dict items
        raw = """```json
{
  "rationale": "Resilient recovery",
  "steps": [
    "invalid non-dict entry",
    null,
    {
      "step_id": -99,
      "intent": "INVALID_INTENT_STRING",
      "description": ""
    },
    {
      "step_id": 2,
      "intent": "INPUT",
      "description": "Type into field",
      "success_criteria": ""
    }
  ]
}
```"""
        plan = parse_gemini_consultation_response(raw, user_goal="Partial steps goal")
        assert len(plan.steps) == 2
        # First valid step should have normalized step_id and mapped fallback intent
        assert plan.steps[0].step_id == 3  # normalized from enumerate index
        assert plan.steps[0].intent == StepIntent.NAVIGATE  # fallback from invalid intent
        assert plan.steps[0].description == "Step 3"
        # Second valid step
        assert plan.steps[1].step_id == 2
        assert plan.steps[1].intent == StepIntent.INPUT_DATA
        assert plan.steps[1].success_criteria == "Visual confirmation of step completion"

    def test_resolve_clarification_query_empty_inputs(self):
        resp_empty = resolve_clarification_query("", window_info=None, elements=[])
        assert resp_empty == "No additional modal or element disambiguation anomalies detected."

        resp_none = resolve_clarification_query(None, window_info=None, elements=None)
        assert resp_none == "No additional modal or element disambiguation anomalies detected."

    def test_resolve_clarification_query_modal_window_detection(self):
        win_normal = WindowInfo(
            hwnd=1001,
            title="Save As",
            class_name="#32770",
            process_name="notepad.exe",
            process_path="C:\\Windows\\notepad.exe",
            pid=2000,
            rect=(100, 100, 700, 500),
            is_sensitive=False,
            reason="Standard Save Dialog",
        )
        res1 = resolve_clarification_query("Is this a modal dialog or popup?", window_info=win_normal)
        assert "Window 'Save As'" in res1
        assert "active foreground window (sensitive=False)" in res1

        win_sensitive = WindowInfo(
            hwnd=1002,
            title="Windows Security Prompt",
            class_name="Credential Dialog",
            process_name="credentialui.exe",
            process_path="C:\\Windows\\System32\\credentialui.exe",
            pid=3000,
            rect=(200, 200, 600, 400),
            is_sensitive=True,
            reason="UAC credential entry",
        )
        res2 = resolve_clarification_query("Is the window a security dialog?", window_info=win_sensitive)
        assert "Window 'Windows Security Prompt'" in res2
        assert "sensitive=True" in res2

    def test_resolve_clarification_query_overlapping_coordinates_disambiguation(self):
        # Two elements with identical center coordinates (overlapping UI elements)
        elem1 = UIElement(
            id=10,
            role="Button",
            label="Search In App",
            x=200,
            y=150,
            width=80,
            height=30,
            center_x=240,
            center_y=165,
            source="uia",
        )
        elem2 = UIElement(
            id=11,
            role="Button",
            label="Search Web",
            x=200,
            y=150,
            width=80,
            height=30,
            center_x=240,
            center_y=165,
            source="ocr",
        )
        elem3 = UIElement(
            id=25,
            role="Button",
            label="Search Taskbar",
            x=50,
            y=1040,
            width=40,
            height=40,
            center_x=70,
            center_y=1060,
            source="uia",
        )

        res = resolve_clarification_query(
            question="Which search button should be clicked?",
            elements=[elem1, elem2, elem3],
        )

        assert "[#10] Button 'Search In App' at (240, 165)" in res
        assert "[#11] Button 'Search Web' at (240, 165)" in res
        assert "[#25] Button 'Search Taskbar' at (70, 1060)" in res

    def test_resolve_clarification_query_negative_and_multi_monitor_bounds(self):
        elem_neg = UIElement(
            id=99,
            role="MenuItem",
            label="Negative Display Control",
            x=-1800,
            y=50,
            width=100,
            height=25,
            center_x=-1750,
            center_y=62,
            source="uia",
        )
        res = resolve_clarification_query(
            question="Where is the display control located?",
            elements=[elem_neg],
        )
        assert "[#99] MenuItem 'Negative Display Control' at (-1750, 62)" in res

    def test_resolve_clarification_query_candidate_list_truncation(self):
        # 30 elements matching keyword 'button'
        elements = [
            UIElement(
                id=i,
                role="Button",
                label=f"Action Button {i}",
                x=i * 10,
                y=100,
                width=30,
                height=20,
                center_x=i * 10 + 15,
                center_y=110,
                source="uia",
            )
            for i in range(1, 31)
        ]
        res = resolve_clarification_query("Which button to press?", elements=elements)
        # Should cap candidates at 5
        matches = [f"[#{i}]" for i in range(1, 31) if f"[#{i}]" in res]
        assert len(matches) == 5, f"Expected 5 candidates capped, got {len(matches)}: {matches}"

    def test_resolve_clarification_query_handles_duck_typed_elements_with_none_fields(self):
        class DuckElem:
            id = 42
            role = None
            label = None
            center_x = 25
            center_y = 40

        # Should not raise AttributeError when searching words
        res = resolve_clarification_query("Which button is active?", elements=[DuckElem()])
        assert res == "No additional modal or element disambiguation anomalies detected."


# ===========================================================================
# Suite 3: Backward Compatibility of format_gemini_consultation_prompt
# ===========================================================================

class TestPromptBackwardCompatibility:
    """Verifies that old callers calling format_gemini_consultation_prompt execute without deprecation crashes."""

    def test_legacy_keyword_arguments_full(self):
        prompt = format_gemini_consultation_prompt(
            goal="Compile and test project",
            active_window_title="Visual Studio Code - ParasiteAI",
            process_name="code.exe",
            open_apps_summary="VS Code, Chrome, Terminal",
            visual_scene_summary="Editor showing plan.py with integrated terminal",
            dilemma_description="Build command output is non-zero",
        )

        # Legacy caller assertions
        assert "[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]" in prompt
        assert "User Goal: Compile and test project" in prompt
        assert 'Foreground Window: "Visual Studio Code - ParasiteAI"' in prompt
        assert "code.exe" in prompt
        assert "Active Window: Visual Studio Code - ParasiteAI (code.exe)" in prompt
        assert "Visible Applications: VS Code, Chrome, Terminal" in prompt
        assert "Visual Scene Observation: Editor showing plan.py with integrated terminal" in prompt
        assert "Current Dilemma / Status: Build command output is non-zero" in prompt
        assert "Failure Reason: Build command output is non-zero" in prompt

        # Invariant contract checks (VERIF-2)
        assert "# CAPABILITY CONTRACT & CONSTRAINTS" in prompt
        assert "ZERO headless scraping" in prompt
        assert "ZERO programmatic accessibility pattern invocation" in prompt
        assert "Human-curved cubic Bézier trajectories" in prompt
        assert "Atomic Ctrl+V paste (<100ms)" in prompt

    def test_legacy_keyword_arguments_partial(self):
        prompt = format_gemini_consultation_prompt(goal="Launch Notepad")

        assert "User Goal: Launch Notepad" in prompt
        assert "Active Window: Desktop (explorer.exe)" in prompt
        assert "Visible Applications: None" in prompt
        assert "Visual Scene Observation: Default desktop view" in prompt
        assert "Current Dilemma / Status: Initial plan formulation" in prompt

    def test_legacy_keyword_arguments_none_values(self):
        prompt = format_gemini_consultation_prompt(
            goal=None,
            active_window_title=None,
            process_name=None,
            open_apps_summary=None,
            visual_scene_summary=None,
            dilemma_description=None,
        )

        assert "User Goal: " in prompt
        assert "Active Window: Desktop (explorer.exe)" in prompt
        assert "Visible Applications: None" in prompt
        assert "Current Dilemma / Status: Initial plan formulation" in prompt

    def test_positional_arguments_compatibility(self):
        elements = [
            UIElement(id=1, role="Button", label="OK", x=10, y=10, width=50, height=25, center_x=35, center_y=22),
        ]
        win = WindowInfo(
            hwnd=999,
            title="Options",
            class_name="Dialog",
            process_name="app.exe",
            process_path="C:\\app.exe",
            pid=111,
            rect=(0, 0, 800, 600),
            is_sensitive=False,
            reason="Test dialog",
        )

        prompt = format_gemini_consultation_prompt(
            "Configure settings",
            elements,
            win,
            "Cannot click checkbox",
            "Action 1: click #1",
        )

        assert "User Goal: Configure settings" in prompt
        assert 'Foreground Window: "Options"' in prompt
        assert "app.exe" in prompt
        assert "| #1 | Button | \"OK\" |" in prompt
        assert "Current Dilemma / Status: Cannot click checkbox" in prompt
        assert "Action 1: click #1" in prompt

    def test_extra_unexpected_kwargs_do_not_crash(self):
        prompt = format_gemini_consultation_prompt(
            goal="Test extra kwargs",
            legacy_flag=True,
            unused_parameter_1=42,
            deprecated_timeout_ms=5000,
        )
        assert "User Goal: Test extra kwargs" in prompt

    def test_gemini_consultation_template_alias_present(self):
        assert isinstance(GEMINI_CONSULTATION_TEMPLATE, str)
        assert len(GEMINI_CONSULTATION_TEMPLATE) > 1000
        assert "[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]" in GEMINI_CONSULTATION_TEMPLATE
        assert "# CAPABILITY CONTRACT & CONSTRAINTS" in GEMINI_CONSULTATION_TEMPLATE
        assert "# ACTIVE DESKTOP STATE" in GEMINI_CONSULTATION_TEMPLATE
        assert "# INSTRUCTIONS" in GEMINI_CONSULTATION_TEMPLATE

    def test_scene_brief_sanitization_of_pipe_and_newline_labels(self):
        elem_weird = UIElement(
            id=1,
            role="Button",
            label="Click | Here\nNow | Fast",
            x=10,
            y=10,
            width=50,
            height=25,
            center_x=35,
            center_y=22,
        )
        brief = serialize_textual_scene_brief(elements=[elem_weird])
        assert "Click / Here Now / Fast" in brief
        # Must not contain unescaped raw newlines within table cell
        assert "\nNow" not in brief
