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

def test_parse_coordinates_native_point() -> None:
    # 960, 540 on 1920x1080 -> exact screen pixels
    coords = parse_coordinates("(960, 540)", screen_width=1920, screen_height=1080)
    assert coords == (960, 540)


def test_parse_coordinates_box_tokens() -> None:
    # <|box_start|>(192,540)<|box_end|> -> exact screen pixels
    coords = parse_coordinates("<|box_start|>(192,540)<|box_end|>", screen_width=1920, screen_height=1080)
    assert coords == (192, 540)


def test_parse_coordinates_bounding_box_center() -> None:
    # (100, 200, 300, 400) -> center is (200, 300) in physical screen pixels
    coords = parse_coordinates("(100, 200, 300, 400)", screen_width=1920, screen_height=1080)
    assert coords == (200, 300)


def test_parse_coordinates_screen_bounds_clamping() -> None:
    # Values exceeding [0..screen_width-1, 0..screen_height-1] range are clamped to screen edges
    coords = parse_coordinates("(2500, -50)", screen_width=1920, screen_height=1080)
    assert coords == (1919, 0)


def test_parse_coordinates_exact_physical_pixel_grounding_across_entire_screen() -> None:
    """Verifies invariant physical pixel grounding across left, center, right, and taskbar regions without scaling distortion."""
    sw, sh = 1920, 1080
    # 1. Left-half (Notepad++ desktop shortcut)
    assert parse_coordinates("(529, 50)", screen_width=sw, screen_height=sh) == (529, 50)

    # 2. Exact center
    assert parse_coordinates("(960, 540)", screen_width=sw, screen_height=sh) == (960, 540)

    # 3. Right-half (Window Close button 'X')
    assert parse_coordinates("(1365, 45)", screen_width=sw, screen_height=sh) == (1365, 45)

    # 4. Dialog button ('Where did my icons go?' OK button)
    assert parse_coordinates("(1091, 574)", screen_width=sw, screen_height=sh) == (1091, 574)

    # 5. Taskbar bottom-left Start button
    assert parse_coordinates("(24, 1060)", screen_width=sw, screen_height=sh) == (24, 1060)


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
    assert "Keep your Thought concise" in UITARS_SYSTEM_PROMPT
    assert "click(start_box=" in UITARS_SYSTEM_PROMPT
    assert "type(content=" in UITARS_SYSTEM_PROMPT
    assert "hotkey(key=" in UITARS_SYSTEM_PROMPT
    assert "finished()" in UITARS_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 6. Stint P2.1 Regression Tests: baseline_p1 Truncation & Trailing Role Tokens
# ---------------------------------------------------------------------------

def test_parse_uitars_baseline_p1_trailing_assistant_token_and_clipped_paren() -> None:
    """
    Regression test for exact baseline_p1 failure string from logs/parasite_debug.log#L10-L21:
    'click(start_box='(24,980)\\nassistant' must parse as ActionType.CLICK at (46, 1058), NOT ActionType.WAIT.
    """
    raw = (
        "Thought: I will click the Start button to search for Notepad.\n"
        "Action: click(start_box='(24,980)\nassistant"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1920, screen_height=1080)
    assert thought == "I will click the Start button to search for Notepad."
    assert plan.action == ActionType.CLICK
    assert plan.coordinates == (24, 980)
    assert plan.clicks == 1


def test_parse_uitars_truncated_closing_quote_and_paren_click() -> None:
    """
    Verifies click(start_box='(24,980) with missing closing quote and closing paren
    parses cleanly into ActionType.CLICK with both x and y coordinates intact.
    """
    raw = (
        "Thought: Clicking the Start menu button at bottom-left.\n"
        "Action: click(start_box='(24,980)"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1920, screen_height=1080)
    assert plan.action == ActionType.CLICK
    assert plan.coordinates == (24, 980)


def test_parse_uitars_truncated_type_with_comma_in_text() -> None:
    """
    Verifies type(content='Hello, world! Welcome to Notepad (truncated before closing quote/paren)
    extracts the full string including commas without coercing to WAIT or truncating at the comma.
    """
    raw = (
        "Thought: Typing the polite greeting into the Notepad editor.\n"
        "Action: type(content='Hello, world! Welcome to Notepad"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.TYPE
    assert plan.text == "Hello, world! Welcome to Notepad"
    assert plan.submit is False


def test_parse_uitars_truncated_hotkey_with_trailing_role_marker() -> None:
    """
    Verifies hotkey(key='win r\\nassistant' or unclosed hotkey call parses cleanly into ActionType.HOTKEY.
    """
    raw = (
        "Thought: Opening Run dialog via shortcut.\n"
        "Action: hotkey(key='win r\nassistant"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.HOTKEY
    assert plan.keys == ["win", "r"]


def test_parse_uitars_im_end_control_token_stripped() -> None:
    """
    Verifies <|im_end|> and <|endoftext|> trailing markers are stripped cleanly.
    """
    raw = (
        "Thought: Double-clicking the file icon.\n"
        "Action: left_double(start_box='(500, 500)')<|im_end|>\nuser: something"
    )
    thought, plan = parse_uitars_action(raw, screen_width=1920, screen_height=1080)
    assert plan.action == ActionType.DOUBLE_CLICK
    assert plan.coordinates == (500, 500)


def test_parse_uitars_type_action_chaining_with_newline() -> None:
    """Verifies type action ending with \\n or \\r\\n flags submit=True with clean text."""
    raw = "Thought: Typing app name into search.\nAction: type(content='calculator\\n')"
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.TYPE
    assert plan.text == "calculator"
    assert plan.submit is True


def test_parse_uitars_type_action_chaining_with_submit_kwarg() -> None:
    """Verifies type action with submit=True or enter=True flags submit=True."""
    raw = "Thought: Typing query.\nAction: type(content='notepad', submit=True)"
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.TYPE
    assert plan.text == "notepad"
    assert plan.submit is True

    raw2 = "Thought: Typing query.\nAction: type(content='paint', enter='true')"
    thought2, plan2 = parse_uitars_action(raw2)
    assert plan2.action == ActionType.TYPE
    assert plan2.text == "paint"
    assert plan2.submit is True


# ---------------------------------------------------------------------------
# 7. Stint P4.2 Layer 0.5 Chained Reflex Burst Tests
# ---------------------------------------------------------------------------

def test_parse_uitars_burst_action_call() -> None:
    """Verifies burst([...]) parses into ActionType.BURST with individual sub-actions."""
    raw = (
        "Thought: Calculating 7 * 8 = in one burst.\n"
        "Action: burst([click(start_box='(45,320)'), click(start_box='(120,280)'), click(start_box='(80,320)'), click(start_box='(200,320)')])"
    )
    thought, plan = parse_uitars_action(raw)
    assert thought == "Calculating 7 * 8 = in one burst."
    assert plan.action == ActionType.BURST
    assert plan.burst_actions is not None
    assert len(plan.burst_actions) == 4
    assert plan.burst_actions[0].action == ActionType.CLICK
    assert plan.burst_actions[0].coordinates == (45, 320)
    assert plan.burst_actions[1].coordinates == (120, 280)
    assert plan.burst_actions[2].coordinates == (80, 320)
    assert plan.burst_actions[3].coordinates == (200, 320)


def test_parse_uitars_multi_call_comma_separated_chain() -> None:
    """Verifies top-level comma-separated multi-call sequences parse into ActionType.BURST."""
    raw = (
        "Thought: Saving file and closing.\n"
        "Action: hotkey(key='ctrl s'), wait(100), click(start_box='(1900, 15)')"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.BURST
    assert plan.burst_actions is not None
    assert len(plan.burst_actions) == 3
    assert plan.burst_actions[0].action == ActionType.HOTKEY
    assert plan.burst_actions[0].keys == ["ctrl", "s"]
    assert plan.burst_actions[1].action == ActionType.WAIT
    assert plan.burst_actions[1].wait_ms == 100
    assert plan.burst_actions[2].action == ActionType.CLICK
    assert plan.burst_actions[2].coordinates == (1900, 15)


def test_parse_uitars_burst_with_quoted_commas_in_type() -> None:
    """Verifies commas inside quoted type strings do not get incorrectly split."""
    raw = (
        "Thought: Clicking search and typing greeting.\n"
        "Action: burst([click(start_box='(50, 50)'), type(content='Hello, world! Welcome, user\\n')])"
    )
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.BURST
    assert len(plan.burst_actions) == 2
    assert plan.burst_actions[1].action == ActionType.TYPE
    assert plan.burst_actions[1].text == "Hello, world! Welcome, user"
    assert plan.burst_actions[1].submit is True


def test_parse_uitars_burst_empty_or_malformed_falls_back_to_wait() -> None:
    """Verifies empty or corrupted burst calls safely fall back to WAIT without crashing."""
    raw = "Thought: Trying empty burst.\nAction: burst([])"
    thought, plan = parse_uitars_action(raw)
    assert plan.action == ActionType.WAIT


def test_uitars_system_prompt_reflex_and_desktop_invariants() -> None:
    """Verifies system prompt documents burst syntax without numerical coordinate anchoring."""
    assert "burst(" in UITARS_SYSTEM_PROMPT
    assert "Never type text onto the bare desktop background" in UITARS_SYSTEM_PROMPT
    # Cadence §8 invariant: no plausible concrete coordinates in few-shot prompt examples
    assert "(960, 540)" not in UITARS_SYSTEM_PROMPT
    assert "(1414, 632)" not in UITARS_SYSTEM_PROMPT



