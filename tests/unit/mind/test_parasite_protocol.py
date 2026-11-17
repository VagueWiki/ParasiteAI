"""Unit tests for ParasiteSkill nonce-bound protocol, zero-coordinate guards, and symbolic prompts."""

from __future__ import annotations

import pytest

from parasite_ai.mind.memory import ActionType
from parasite_ai.mind.parasite_protocol import (
    ParasiteAction,
    ParasiteFailure,
    ParasitePhase,
    ParasitePlan,
    ParasitePlanStep,
    ParasiteRequest,
    ParsedParasiteResponse,
    RecoveryTrigger,
    build_parasite_prompt,
    find_coordinate_patterns,
    generate_nonce,
    parse_response,
)
from parasite_ai.mind.plan import StepIntent

pytestmark = pytest.mark.unit


def _valid_plan_json(selected_program: str = "Notepad") -> str:
    return (
        '{\n'
        f'  "selected_program": "{selected_program}",\n'
        '  "rationale": "Native lightweight editor matches goal cleanly.",\n'
        '  "steps": [\n'
        '    {\n'
        '      "intent": "LAUNCH_OR_ACTIVATE",\n'
        '      "description": "Focus or launch chosen editor",\n'
        '      "target_description": "Editor window",\n'
        '      "tool_route": "GUI",\n'
        '      "success_criteria": "Window active on desktop",\n'
        '      "contingency": "Use Start search if minimized"\n'
        '    }\n'
        '  ]\n'
        '}'
    )


def test_parse_valid_proactive_plan_discards_filler_and_preserves_fields() -> None:
    nonce = generate_nonce()
    raw = (
        "Sure! Here is my plan for you:\n"
        f'<parasite_plan nonce="{nonce}">\n{_valid_plan_json("LibreOffice Calc")}\n</parasite_plan>\n'
        "Let me know if you need anything else!"
    )
    res = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert isinstance(res, ParsedParasiteResponse)
    assert res.plan is not None
    assert res.plan.selected_program == "LibreOffice Calc"
    assert res.action is None

    lp = res.plan.to_living_plan("Analyze CSV spreadsheet")
    assert lp.consulted_gemini is True
    assert "[Selected: LibreOffice Calc]" in lp.overall_strategy
    assert lp.steps[0].tool_route == "GUI"


def test_parse_recovery_with_code_fenced_plan_and_semantic_action() -> None:
    nonce = generate_nonce()
    raw = (
        f'<parasite_plan nonce="{nonce}">\n```json\n{_valid_plan_json()}\n```\n</parasite_plan>\n'
        f'<parasite_action nonce="{nonce}">\n```json\n'
        '{"verb": "CLICK", "target_description": "Save As button"}\n'
        '```\n</parasite_action>'
    )
    res = parse_response(raw, nonce=nonce, phase=ParasitePhase.REACTIVE_RECOVERY)
    assert isinstance(res, ParsedParasiteResponse)
    assert res.plan is not None
    assert res.action is not None
    step = res.action.to_contingency_step(step_id=3)
    assert step.step_id == 3
    assert "Save As button" in (step.target_description or "")


def test_proactive_phase_ignores_single_action_block() -> None:
    nonce = generate_nonce()
    raw = (
        f'<parasite_plan nonce="{nonce}">{_valid_plan_json()}</parasite_plan>\n'
        f'<parasite_action nonce="{nonce}">{{"verb": "HOTKEY", "keys": ["ctrl", "s"]}}</parasite_action>'
    )
    res = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert isinstance(res, ParsedParasiteResponse)
    assert res.plan is not None
    assert res.action is None


def test_parse_skill_coauthor_validates_yaml_markdown() -> None:
    nonce = generate_nonce()
    raw = (
        f'<parasite_skill nonce="{nonce}">\n'
        "---\n"
        "schema_version: 1\n"
        "id: quick-save\n"
        "name: Quick Save\n"
        "version: 1\n"
        "type: workflow\n"
        "draft: true\n"
        "state: CANDIDATE\n"
        "provenance: co_authored\n"
        "description: Saves open document.\n"
        "trigger:\n"
        "  keywords: [save]\n"
        "preconditions:\n"
        "  container_process: notepad.exe\n"
        "actions:\n"
        "  steps:\n"
        "    - intent: NAVIGATE\n"
        "      verb: HOTKEY\n"
        "      keys: [ctrl, s]\n"
        "      success_criteria: Save dialog open\n"
        "postconditions:\n"
        "  success_criteria: Document saved\n"
        "---\n# Quick Save\n</parasite_skill>"
    )
    res = parse_response(raw, nonce=nonce, phase=ParasitePhase.SKILL_COAUTHOR)
    assert isinstance(res, ParsedParasiteResponse)
    assert res.parsed_skill is not None
    assert res.parsed_skill.id == "quick-save"


@pytest.mark.parametrize(
    "phase,bad_raw,expected_fail",
    [
        (ParasitePhase.PROACTIVE_PLAN, "No tags at all", ParasiteFailure.TAGS_MISSING),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan nonce="abc">{}'
            '</parasite_plan><parasite_plan nonce="abc">{}</parasite_plan>',
            ParasiteFailure.TAGS_DUPLICATED,
        ),
        (
            ParasitePhase.REACTIVE_RECOVERY,
            '<parasite_plan nonce="abc">' + _valid_plan_json() + "</parasite_plan>"
            '<parasite_action nonce="abc">{"verb":"WAIT"}</parasite_action>'
            '<parasite_action nonce="abc">{"verb":"WAIT"}</parasite_action>',
            ParasiteFailure.TAGS_DUPLICATED,
        ),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan>{"rationale":"screen-echoed","steps":[{"intent":"NAVIGATE","description":"d","success_criteria":"s"}]}</parasite_plan>',
            ParasiteFailure.NONCE_MISMATCH,
        ),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan nonce="wrong_nonce">' + _valid_plan_json() + "</parasite_plan>",
            ParasiteFailure.NONCE_MISMATCH,
        ),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan nonce="abc">outer <parasite_action nonce="abc">{}</parasite_action></parasite_plan>',
            ParasiteFailure.PAYLOAD_INVALID,
        ),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan nonce="abc">{not-json}</parasite_plan>',
            ParasiteFailure.PAYLOAD_INVALID,
        ),
        (
            ParasitePhase.PROACTIVE_PLAN,
            '<parasite_plan nonce="abc">'
            + '{"rationale":"ok","unexpected_field":1,"steps":[{"intent":"NAVIGATE","description":"d","success_criteria":"s"}]}'
            + "</parasite_plan>",
            ParasiteFailure.PAYLOAD_INVALID,
        ),
        (
            ParasitePhase.REACTIVE_RECOVERY,
            '<parasite_plan nonce="abc">' + _valid_plan_json() + "</parasite_plan>"
            '<parasite_action nonce="abc">{"verb":"CLICK","target_description":"Button","coordinates":[120,240]}</parasite_action>',
            ParasiteFailure.PAYLOAD_INVALID,
        ),
        (
            ParasitePhase.REACTIVE_RECOVERY,
            '<parasite_plan nonce="abc">' + _valid_plan_json() + "</parasite_plan>"
            '<parasite_action nonce="abc">{"verb":"CLICK","target_description":"Click (120, 240)"}</parasite_action>',
            ParasiteFailure.PAYLOAD_INVALID,
        ),
    ],
)
def test_strict_parser_rejection_cases(
    phase: ParasitePhase, bad_raw: str, expected_fail: ParasiteFailure
) -> None:
    res = parse_response(bad_raw, nonce="abc", phase=phase)
    assert res == expected_fail


def test_parse_response_oversize_and_control_char_stripping() -> None:
    nonce = generate_nonce()
    assert (
        parse_response("x" * 100, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN, max_response_chars=50)
        == ParasiteFailure.PAYLOAD_OVERSIZE
    )

    step = ParasitePlanStep(
        intent=StepIntent.NAVIGATE,
        description="Focus\x00 editor\x07",
        target_description="Input\x1f",
        success_criteria="Active\x08",
    )
    assert "\x00" not in step.description
    assert "\x07" not in step.description
    assert "\x1f" not in (step.target_description or "")
    assert "\x08" not in step.success_criteria


def test_rendered_prompts_contain_zero_numeric_coordinate_patterns() -> None:
    nonce = generate_nonce()
    requests = [
        ParasiteRequest(
            phase=ParasitePhase.PROACTIVE_PLAN,
            user_goal="Convert media file cleanly using best available app",
            active_window_label="Desktop",
            open_windows=["explorer.exe: File Explorer"],
            available_programs=["Audacity", "VLC media player", "FFmpeg"],
        ),
        ParasiteRequest(
            phase=ParasitePhase.REACTIVE_RECOVERY,
            user_goal="Save modified spreadsheet",
            trigger=RecoveryTrigger.OSCILLATION,
            active_window_label="Calc",
            recent_history="step 1 CLICK Failed",
            active_plan_context="Step 1 IN_PROGRESS",
            open_windows=["soffice.bin: Sheet"],
            available_programs=["LibreOffice Calc"],
        ),
        ParasiteRequest(
            phase=ParasitePhase.SKILL_COAUTHOR,
            user_goal="Create zipped archive",
            trace_payload="step=1 | verb=HOTKEY | keys=ctrl+a",
            include_screenshot=False,
        ),
    ]
    for req in requests:
        rendered = build_parasite_prompt(req, nonce=nonce)
        assert nonce in rendered
        assert find_coordinate_patterns(rendered) == []
        # Also verify sensitive assignment redaction in prompt builder
        assert "password=topsecret" not in build_parasite_prompt(
            ParasiteRequest(
                phase=ParasitePhase.PROACTIVE_PLAN,
                user_goal="Login with password=topsecret",
            ),
            nonce=nonce,
        )


def test_plan_step_directives_parsed_and_preserved_in_living_plan() -> None:
    nonce = "feedface12345678"
    raw = (
        f'<parasite_plan nonce="{nonce}">\n'
        "{\n"
        '  "selected_program": "Calculator",\n'
        '  "rationale": "Type arithmetic expression directly.",\n'
        '  "steps": [\n'
        "    {\n"
        '      "intent": "INPUT_DATA",\n'
        '      "description": "Type 12*7 and press Enter",\n'
        '      "target_description": "Calculator input",\n'
        '      "tool_route": "GUI",\n'
        '      "success_criteria": "Result 84 displayed",\n'
        '      "action": {"verb": "TYPE", "text": "12*7", "submit": true}\n'
        "    },\n"
        "    {\n"
        '      "intent": "NAVIGATE",\n'
        '      "description": "Copy result",\n'
        '      "tool_route": "GUI",\n'
        '      "success_criteria": "Result copied",\n'
        '      "action": {"verb": "HOTKEY", "keys": ["ctrl", "c"]}\n'
        "    }\n"
        "  ]\n"
        "}\n"
        f"</parasite_plan>"
    )
    parsed = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert isinstance(parsed, ParsedParasiteResponse)
    assert parsed.plan is not None
    lp = parsed.plan.to_living_plan("calculate 12*7")
    assert lp.steps[0].directive is not None
    assert lp.steps[0].directive.verb == "TYPE"
    assert lp.steps[0].directive.text == "12*7"
    assert lp.steps[0].directive.submit is True
    assert lp.steps[1].directive is not None
    assert lp.steps[1].directive.verb == "HOTKEY"
    assert lp.steps[1].directive.keys == ["ctrl", "c"]


def test_plan_step_without_action_keeps_directive_none() -> None:
    nonce = "feedface12345678"
    raw = (
        f'<parasite_plan nonce="{nonce}">\n'
        '{"rationale": "Legacy format", "steps": [{"intent": "NAVIGATE", "description": "Open menu", "success_criteria": "Menu open"}]}\n'
        "</parasite_plan>"
    )
    parsed = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert isinstance(parsed, ParsedParasiteResponse)
    assert parsed.plan is not None
    lp = parsed.plan.to_living_plan("open menu")
    assert lp.steps[0].directive is None


def test_plan_action_rejects_coordinates_in_text_and_allows_arithmetic() -> None:
    nonce = "feedface12345678"
    bad_raw = (
        f'<parasite_plan nonce="{nonce}">\n'
        '{"rationale": "Bad coords", "steps": [{"intent": "INPUT_DATA", "description": "Type", "success_criteria": "Done", "action": {"verb": "TYPE", "text": "click (100, 200)"}}]}\n'
        "</parasite_plan>"
    )
    bad_res = parse_response(bad_raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert bad_res == ParasiteFailure.PAYLOAD_INVALID

    ok_raw = (
        f'<parasite_plan nonce="{nonce}">\n'
        '{"rationale": "Resize", "steps": [{"intent": "INPUT_DATA", "description": "Type", "success_criteria": "Done", "action": {"verb": "TYPE", "text": "640x480"}}]}\n'
        "</parasite_plan>"
    )
    parsed = parse_response(ok_raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert isinstance(parsed, ParsedParasiteResponse)
    assert parsed.plan is not None
    assert parsed.plan.steps[0].action is not None
    assert parsed.plan.steps[0].action.text == "640x480"


def test_contingency_step_attaches_directive_and_proactive_prompt_omits_cli() -> None:
    from parasite_ai.mind.parasite_protocol import ParasiteAction

    act = ParasiteAction(verb="HOTKEY", keys=["ctrl", "s"])
    step = act.to_contingency_step(step_id=2)
    assert step.directive is not None
    assert step.directive.verb == "HOTKEY"
    assert step.directive.keys == ["ctrl", "s"]

    prompt = build_parasite_prompt(
        ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Save file"),
        nonce="0011223344556677",
    )
    assert '"action"' in prompt
    assert "Valid tool_route values: GUI." in prompt
    assert "Valid tool_route values: GUI, CLI" not in prompt



def test_parse_response_repairs_unescaped_windows_paths_and_intent_aliases():
    nonce = "abc123def456"
    raw = (
        f'<parasite_plan nonce="{nonce}">\n'
        r'{' '\n'
        r'  "selected_program": "Notepad",' '\n'
        r'  "rationale": "Save to C:\ParasiteAI\benchmarks\workspace\note101.txt safely.",' '\n'
        r'  "steps": [' '\n'
        r'    {' '\n'
        r'      "intent": "TYPE",' '\n'
        r'      "description": "Type target file path",' '\n'
        r'      "target_description": "File name box",' '\n'
        r'      "tool_route": "GUI",' '\n'
        r'      "success_criteria": "Path entered",' '\n'
        r'      "action": {"verb": "TYPE", "text": "C:\ParasiteAI\benchmarks\workspace\note101.txt", "submit": true}' '\n'
        r'    }' '\n'
        r'  ]' '\n'
        r'}' '\n'
        '</parasite_plan>'
    )
    parsed = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert not isinstance(parsed, ParasiteFailure)
    assert parsed.plan is not None
    assert parsed.plan.steps[0].intent == StepIntent.INPUT_DATA
    assert "note101.txt" in (parsed.plan.steps[0].action.text or "")
