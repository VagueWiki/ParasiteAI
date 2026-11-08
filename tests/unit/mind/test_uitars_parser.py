"""
Tests for ParasiteAI UI-TARS-1.5 Action Parser, Coordinate Grounding & Schema Recovery.
"""

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from parasite_ai.mind.memory import ActionPlan, ActionType, VERB_SYNONYMS
from parasite_ai.mind.uitars_parser import (
    UITARS_SYSTEM_PROMPT,
    extract_thought_and_action,
    parse_coordinates,
    parse_uitars_action,
    snap_coordinates_to_element,
)


class DummyUIElement:
    """Mock UIElement for snapping tests."""
    def __init__(self, name: str, cx: int, cy: int) -> None:
        self.name = name
        self.center_x = cx
        self.center_y = cy


# ---------------------------------------------------------------------------
# 1. Thought & Action Extraction Tests
# ---------------------------------------------------------------------------

def test_extract_thought_and_action_standard() -> None:
    raw = (
        "Thought: The user wants to open Notepad. I will click the Start button.\n"
        "Action: click(start_box='(25,975)')"
    )
    thought, action = extract_thought_and_action(raw)
    assert thought == "The user wants to open Notepad. I will click the Start button."
    assert action == "click(start_box='(25,975)')"


def test_extract_thought_and_action_markdown_code_block() -> None:
    raw = (
        "```text\n"
        "Thought: Saving the file via File menu.\n"
        "Action: click(start_box='(45,70)')\n"
        "```"
    )
    thought, action = extract_thought_and_action(raw)
    assert thought == "Saving the file via File menu."
    assert action == "click(start_box='(45,70)')"


def test_extract_thought_and_action_missing_prefix_direct_call() -> None:
    raw = (
        "I need to type the filename.\n"
        "type(content='test_document.txt\\n')"
    )
    thought, action = extract_thought_and_action(raw)
    assert "I need to type the filename." in thought
    assert action == "type(content='test_document.txt\\n')"


def test_extract_thought_and_action_plain_text_only() -> None:
    raw = "I am waiting for the window to finish loading."
    thought, action = extract_thought_and_action(raw)
    assert thought == "I am waiting for the window to finish loading."
    assert action == ""


# ---------------------------------------------------------------------------
# 2. Coordinate Parsing & Scaling Tests
# ---------------------------------------------------------------------------

def test_parse_coordinates_normalized_point() -> None:
    # 500, 200 on 1920x1080 -> 50% width = 960, 20% height = 216
    coords = parse_coordinates("(500, 200)", screen_width=1920, screen_height=1080)
    assert coords == (960, 216)


def test_parse_coordinates_box_tokens() -> None:
    # <|box_start|>(100,500)<|box_end|> -> 10% width = 192, 50% height = 540
    coords = parse_coordinates("<|box_start|>(100,500)<|box_end|>", screen_width=1920, screen_height=1080)
    assert coords == (192, 540)


def test_parse_coordinates_bounding_box_center() -> None:
    # (100, 200, 300, 400) -> center is (200, 300) -> 20% of 1920 = 384, 30% of 1080 = 324
    coords = parse_coordinates("(100, 200, 300, 400)", screen_width=1920, screen_height=1080)
    assert coords == (384, 324)


def test_parse_coordinates_raw_pixel_clamping() -> None:
    # Raw pixel values > 1000 should not be double-scaled, but clamped
    coords = parse_coordinates("(2500, -50)", screen_width=1920, screen_height=1080)
    assert coords == (1919, 0)


def test_parse_coordinates_invalid() -> None:
    assert parse_coordinates("invalid string") is None
    assert parse_coordinates("(single_number)") is None


# ---------------------------------------------------------------------------
# 3. Hybrid UIA Element Snapping Tests
# ---------------------------------------------------------------------------

def test_snap_coordinates_within_radius() -> None:
    elems = [
        DummyUIElement("Notepad Button", 500, 200),
        DummyUIElement("Other Icon", 900, 800),
    ]
    # Point at (510, 205) is ~11.18px away from (500, 200) -> within 35px radius
    snapped, elem = snap_coordinates_to_element((510, 205), elems, snap_radius_px=35.0)
    assert snapped == (500, 200)
    assert elem.name == "Notepad Button"


def test_snap_coordinates_outside_radius() -> None:
    elems = [DummyUIElement("Far Element", 500, 200)]
    # Point at (600, 300) is >100px away -> outside 35px radius
    snapped, elem = snap_coordinates_to_element((600, 300), elems, snap_radius_px=35.0)
    assert snapped == (600, 300)
    assert elem is None


# ---------------------------------------------------------------------------
# 4. Functional UI-TARS Action Call Parsing Tests
# ---------------------------------------------------------------------------

def test_parse_uitars_click_action() -> None:
    raw = (
        "Thought: Clicking the File menu.\n"
        "Action: click(start_box='(100, 50)')"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1000, screen_height=1000)
    assert thought == "Clicking the File menu."
    assert plan.action == ActionType.CLICK
    assert plan.coordinates == (100, 50)
    assert plan.clicks == 1


def test_parse_uitars_double_click_action() -> None:
    raw = (
        "Thought: Double clicking desktop icon.\n"
        "Action: left_double(start_box='(200, 300)')"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1000, screen_height=1000)
    assert plan.action == ActionType.DOUBLE_CLICK
    assert plan.coordinates == (200, 300)
    assert plan.clicks == 2


def test_parse_uitars_right_click_action() -> None:
    raw = (
        "Thought: Opening context menu.\n"
        "Action: right_single(start_box='(350, 450)')"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1000, screen_height=1000)
    assert plan.action == ActionType.RIGHT_CLICK
    assert plan.coordinates == (350, 450)


def test_parse_uitars_type_with_newline_submits() -> None:
    raw = (
        "Thought: Searching for calculator.\n"
        "Action: type(content='calculator\\n')"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.TYPE
    assert plan.text == "calculator"
    assert plan.submit is True


def test_parse_uitars_type_without_newline() -> None:
    raw = (
        "Thought: Typing text into notepad buffer.\n"
        "Action: type(content='Hello World')"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.TYPE
    assert plan.text == "Hello World"
    assert plan.submit is False


def test_parse_uitars_hotkey_action() -> None:
    raw = (
        "Thought: Saving file using keyboard shortcut.\n"
        "Action: hotkey(key='ctrl s')"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.HOTKEY
    assert plan.keys == ["ctrl", "s"]


def test_parse_uitars_hotkey_plus_syntax() -> None:
    raw = "Action: hotkey(key='ctrl+shift+esc')"
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.HOTKEY
    assert plan.keys == ["ctrl", "shift", "esc"]


def test_parse_uitars_scroll_action() -> None:
    raw = "Action: scroll(direction='down')"
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.SCROLL
    assert plan.scroll_amount == -3

    raw_up = "Action: scroll(direction='up')"
    _, plan_up = parse_uitars_action(raw_up)
    assert plan_up.scroll_amount == 3


def test_parse_uitars_finished_action() -> None:
    raw = (
        "Thought: The calculation is complete and displayed.\n"
        "Action: finished()"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.DONE


def test_parse_uitars_wait_action() -> None:
    raw = "Action: wait(duration=1500)"
    _, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.WAIT
    assert plan.wait_ms == 1500


def test_parse_uitars_hybrid_json_fallback() -> None:
    raw = (
        "Here is the plan:\n"
        '{"action": "CLICK", "target_id": 5, "reasoning": "Clicking button 5"}'
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.CLICK
    assert plan.target_id == 5
    assert plan.reasoning == "Clicking button 5"


# ---------------------------------------------------------------------------
# 5. Verb Synonym Normalization & Zero-Crash Resilience Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_verb,expected_action",
    [
        ("SELECT", ActionType.CLICK),
        ("SELECT MenuItem", ActionType.CLICK),
        ("SELECT Button", ActionType.CLICK),
        ("SELECT_MENUITEM", ActionType.CLICK),
        ("LEFT_CLICK", ActionType.CLICK),
        ("TAP", ActionType.CLICK),
        ("MOUSE_CLICK", ActionType.CLICK),
        ("CHOOSE", ActionType.CLICK),
        ("DOUBLE_TAP", ActionType.DOUBLE_CLICK),
        ("DBLCLICK", ActionType.DOUBLE_CLICK),
        ("LEFT_DOUBLE", ActionType.DOUBLE_CLICK),
        ("RIGHT_TAP", ActionType.RIGHT_CLICK),
        ("CONTEXT_CLICK", ActionType.RIGHT_CLICK),
        ("RIGHT_SINGLE", ActionType.RIGHT_CLICK),
        ("PRESS", ActionType.HOTKEY),
        ("KEY", ActionType.HOTKEY),
        ("KEY_PRESS", ActionType.HOTKEY),
        ("SHORTCUT", ActionType.HOTKEY),
        ("TYPE_TEXT", ActionType.TYPE),
        ("INPUT", ActionType.TYPE),
        ("WRITE", ActionType.TYPE),
        ("FINISH", ActionType.DONE),
        ("FINISHED", ActionType.DONE),
        ("COMPLETE", ActionType.DONE),
        ("COMPLETED", ActionType.DONE),
        ("PAUSE", ActionType.WAIT),
        ("SLEEP", ActionType.WAIT),
    ],
)
def test_action_plan_verb_synonym_normalization(raw_verb: str, expected_action: ActionType) -> None:
    """Verifies all common LLM verb synonyms map cleanly to canonical ActionType enums."""
    plan = ActionPlan.model_validate({"action": raw_verb})
    assert plan.action == expected_action


def test_action_plan_unknown_verb_zero_crash_resilience() -> None:
    """Verifies completely unknown/gibberish verbs coerce to ActionType.WAIT without raising ValidationError."""
    plan = ActionPlan.model_validate({"action": "GIBBERISH_VERB_XYZ", "reasoning": "Testing resilience"})
    assert plan.action == ActionType.WAIT
    assert "[Unrecognized verb: GIBBERISH_VERB_XYZ]" in plan.reasoning


def test_uitars_parser_malformed_output_zero_crash() -> None:
    """Verifies unparseable gibberish or corrupt tokens safely produce a valid ActionPlan."""
    malformed_inputs = [
        "",
        "   ",
        "!!!@@@###$$$%%%",
        "Action: corrupted_syntax_no_closing_paren((((",
        "Thought: I don't know what to do.\nAction: ???",
        "🎉🚀🤖💻",
    ]
    for raw in malformed_inputs:
        thought, plan = parse_uitars_action(raw)
        assert isinstance(thought, str)
        assert isinstance(plan, ActionPlan)
        assert plan.action == ActionType.WAIT


def test_uitars_system_prompt_structure() -> None:
    """Verifies UITARS_SYSTEM_PROMPT includes required schema tokens and action signatures."""
    assert "Thought:" in UITARS_SYSTEM_PROMPT
    assert "Action:" in UITARS_SYSTEM_PROMPT
    assert "click(start_box=" in UITARS_SYSTEM_PROMPT
    assert "type(content=" in UITARS_SYSTEM_PROMPT
    assert "hotkey(key=" in UITARS_SYSTEM_PROMPT
    assert "finished()" in UITARS_SYSTEM_PROMPT
