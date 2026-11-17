"""Unit tests for SKILL.md YAML+Markdown schema validation and §7.6/§8 invariants."""

from __future__ import annotations

from pathlib import Path
import pytest
from pydantic import ValidationError

from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    ReflexSafetyGate,
    SkillActionStep,
    SkillActions,
    SkillDefinition,
    SkillParameter,
    SkillPostconditions,
    SkillPreconditions,
    SkillState,
    SkillTrigger,
    SkillType,
    parse_skill_md,
    render_skill_md,
)

pytestmark = pytest.mark.unit


def _make_workflow_skill(**overrides) -> SkillDefinition:
    base = dict(
        id="sample-workflow",
        name="Sample Semantic Workflow",
        type=SkillType.WORKFLOW,
        state=SkillState.ACTIVE,
        description="Semantic workflow without screen coordinates.",
        trigger=SkillTrigger(
            goal_patterns=[r"^write\s+(?P<note_text>.+)$"],
            keywords=["write", "note"],
            process_names=["notepad.exe"],
            min_score=0.6,
        ),
        parameters=[SkillParameter(name="note_text", description="Text to input", required=True)],
        preconditions=SkillPreconditions(container_process="notepad.exe", requires_launch=True),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    target_description="Document editor canvas",
                    text="{{note_text}}",
                    success_criteria="Entered text appears in editor",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Text persisted in editor"),
        body="# Sample Workflow\n\n## Intent\nSemantic text entry.\n\n## Procedure\n1. Type content.",
    )
    base.update(overrides)
    return SkillDefinition(**base)


def test_template_skill_md_parses_cleanly() -> None:
    tpl_path = Path("data/skills/_template/SKILL.md")
    skill = parse_skill_md(tpl_path.read_text(encoding="utf-8"), source_path=tpl_path)
    assert skill.id == "template-workflow-example"
    assert skill.type == SkillType.WORKFLOW
    assert skill.draft is True


def test_codec_roundtrip_is_byte_stable() -> None:
    skill = _make_workflow_skill()
    first = render_skill_md(skill)
    reparsed = parse_skill_md(first)
    second = render_skill_md(reparsed)
    assert first == second
    assert reparsed.id == skill.id
    assert reparsed.body == skill.body.strip()


def test_yaml_safe_load_rejects_python_object_tag() -> None:
    malicious = (
        "---\n"
        "schema_version: 1\n"
        "id: !!python/object/apply:os.system ['echo pwn']\n"
        "name: Evil\n"
        "---\n# Body\n"
    )
    with pytest.raises(Exception):
        parse_skill_md(malicious)


def test_workflow_rejects_relative_coordinates() -> None:
    with pytest.raises(ValidationError, match="relative_coordinates"):
        _make_workflow_skill(
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.NAVIGATE,
                        verb="CLICK",
                        target_description="Save button",
                        relative_coordinates=(10, 20),
                        success_criteria="Clicked",
                    )
                ]
            )
        )


def test_workflow_rejects_reflex_gate() -> None:
    with pytest.raises(ValidationError, match="reflex_gate"):
        _make_workflow_skill(
            reflex_gate=ReflexSafetyGate(
                expected_window_size=(320, 480),
                phash_anchor="0123456789abcdef",
            )
        )


def test_reflex_micro_skill_valid_accepts_bounded_relative_coordinates() -> None:
    skill = SkillDefinition(
        id="calc-pad-burst",
        name="Calc Static Pad",
        type=SkillType.REFLEX_MICRO_SKILL,
        state=SkillState.ACTIVE,
        description="Static grid micro-skill under §7.6 gate.",
        trigger=SkillTrigger(keywords=["calc"], min_score=0.3),
        preconditions=SkillPreconditions(container_process="calc.exe"),
        reflex_gate=ReflexSafetyGate(
            expected_window_size=(320, 500),
            relative_origin="client_top_left",
            phash_anchor="abcdef0123456789",
            phash_max_hamming=6,
        ),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="CLICK",
                    relative_coordinates=(80, 250),
                    success_criteria="Keypad button depressed",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Digit shown in display"),
    )
    rendered = render_skill_md(skill)
    reparsed = parse_skill_md(rendered)
    assert reparsed.type == SkillType.REFLEX_MICRO_SKILL
    assert reparsed.reflex_gate is not None
    assert reparsed.actions.steps[0].relative_coordinates == (80, 250)


def test_reflex_micro_skill_requires_reflex_gate_and_container_process() -> None:
    with pytest.raises(ValidationError, match="reflex_gate"):
        SkillDefinition(
            id="bad-reflex-1",
            name="Missing Gate",
            type=SkillType.REFLEX_MICRO_SKILL,
            description="Missing gate.",
            trigger=SkillTrigger(keywords=["x"], min_score=0.3),
            preconditions=SkillPreconditions(container_process="calc.exe"),
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.NAVIGATE,
                        verb="CLICK",
                        relative_coordinates=(10, 10),
                        success_criteria="Done",
                    )
                ]
            ),
            postconditions=SkillPostconditions(success_criteria="Done"),
        )

    with pytest.raises(ValidationError, match="container_process"):
        SkillDefinition(
            id="bad-reflex-2",
            name="Missing Process",
            type=SkillType.REFLEX_MICRO_SKILL,
            description="Missing process.",
            trigger=SkillTrigger(keywords=["x"], min_score=0.3),
            preconditions=SkillPreconditions(container_process=None),
            reflex_gate=ReflexSafetyGate(
                expected_window_size=(300, 400),
                phash_anchor="abcdef0123456789",
            ),
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.NAVIGATE,
                        verb="CLICK",
                        relative_coordinates=(10, 10),
                        success_criteria="Done",
                    )
                ]
            ),
            postconditions=SkillPostconditions(success_criteria="Done"),
        )


@pytest.mark.parametrize("bad_coords", [(320, 10), (10, 500), (-1, 10), (10, -5)])
def test_reflex_micro_skill_rejects_out_of_bounds_relative_coordinates(bad_coords) -> None:
    with pytest.raises(ValidationError, match="out of bounds"):
        SkillDefinition(
            id="bad-reflex-bounds",
            name="OOB",
            type=SkillType.REFLEX_MICRO_SKILL,
            description="OOB relative coord.",
            trigger=SkillTrigger(keywords=["x"], min_score=0.3),
            preconditions=SkillPreconditions(container_process="calc.exe"),
            reflex_gate=ReflexSafetyGate(
                expected_window_size=(320, 500),
                phash_anchor="abcdef0123456789",
            ),
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.NAVIGATE,
                        verb="CLICK",
                        relative_coordinates=bad_coords,
                        success_criteria="Done",
                    )
                ]
            ),
            postconditions=SkillPostconditions(success_criteria="Done"),
        )


@pytest.mark.parametrize(
    "poison",
    ["Click at (450, 320)", "Use box [100, 200]", "Move to x=512 then click"],
)
def test_no_coordinates_in_prose_and_body_rejected_for_both_types(poison: str) -> None:
    with pytest.raises(ValidationError, match="zero-coordinate"):
        _make_workflow_skill(
            body=f"# Bad\n\n## Procedure\n1. {poison}"
        )

    with pytest.raises(ValidationError, match="zero-coordinate"):
        SkillDefinition(
            id="reflex-prose-poison",
            name="Poisoned Reflex",
            type=SkillType.REFLEX_MICRO_SKILL,
            description="Bad prose.",
            trigger=SkillTrigger(keywords=["x"], min_score=0.3),
            preconditions=SkillPreconditions(container_process="calc.exe"),
            reflex_gate=ReflexSafetyGate(
                expected_window_size=(300, 400),
                phash_anchor="abcdef0123456789",
            ),
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.NAVIGATE,
                        verb="CLICK",
                        target_description=poison,
                        relative_coordinates=(10, 10),
                        success_criteria="Done",
                    )
                ]
            ),
            postconditions=SkillPostconditions(success_criteria="Done"),
        )


def test_undeclared_parameter_placeholder_rejected() -> None:
    with pytest.raises(ValidationError, match="Undeclared parameter"):
        _make_workflow_skill(
            parameters=[],
            actions=SkillActions(
                steps=[
                    SkillActionStep(
                        intent=StepIntent.INPUT_DATA,
                        verb="TYPE",
                        text="{{missing_param}}",
                        success_criteria="Typed",
                    )
                ]
            ),
        )


def test_verb_shape_validation() -> None:
    with pytest.raises(ValidationError, match="HOTKEY"):
        SkillActionStep(intent=StepIntent.NAVIGATE, verb="HOTKEY", success_criteria="Ok")

    with pytest.raises(ValidationError, match="TYPE"):
        SkillActionStep(intent=StepIntent.INPUT_DATA, verb="TYPE", success_criteria="Ok")

    with pytest.raises(ValidationError, match="CLICK"):
        SkillActionStep(intent=StepIntent.NAVIGATE, verb="CLICK", success_criteria="Ok")


def test_extra_forbid_rejects_smuggled_coordinate_fields() -> None:
    bad_yaml = (
        "---\n"
        "schema_version: 1\n"
        "id: smuggle-test\n"
        "name: Smuggle\n"
        "description: Test.\n"
        "trigger:\n  keywords: [a]\n"
        "preconditions: {}\n"
        "actions:\n  steps:\n"
        "    - intent: NAVIGATE\n"
        "      verb: CLICK\n"
        "      target_description: Save button\n"
        "      coordinates: [100, 200]\n"
        "      success_criteria: Clicked\n"
        "postconditions:\n  success_criteria: Saved\n"
        "---\n"
    )
    with pytest.raises(ValidationError):
        parse_skill_md(bad_yaml)


def test_invalid_or_oversized_regex_and_bad_id_rejected() -> None:
    with pytest.raises(ValidationError):
        SkillTrigger(goal_patterns=["[unclosed"])

    with pytest.raises(ValidationError, match="max length"):
        SkillTrigger(goal_patterns=["a" * 257])

    with pytest.raises(ValidationError, match="Skill id"):
        _make_workflow_skill(id="-Bad_ID!")


def test_draft_boolean_persists_in_frontmatter() -> None:
    skill = _make_workflow_skill(draft=True, state=SkillState.CANDIDATE)
    rendered = render_skill_md(skill)
    assert "draft: true" in rendered
    assert parse_skill_md(rendered).draft is True


def test_step_directive_validation_and_plan_step_default() -> None:
    from parasite_ai.mind.plan import PlanStep, StepDirective, StepIntent

    default_step = PlanStep(
        step_id=1,
        intent=StepIntent.NAVIGATE,
        description="Open menu",
        success_criteria="Menu visible",
    )
    assert default_step.directive is None

    with pytest.raises(ValidationError):
        StepDirective(verb="TYPE", text=None)

    with pytest.raises(ValidationError):
        StepDirective(verb="HOTKEY", keys=[])

    with pytest.raises(ValidationError):
        StepDirective(verb="CLICK", coordinates=(100, 200))


def test_skill_preconditions_launch_query_and_method_compile(tmp_path: Path) -> None:
    from parasite_ai.config import SkillsConfig
    from parasite_ai.mind.skills import SkillMatch, SkillRegistry

    skill = _make_workflow_skill(
        preconditions=SkillPreconditions(
            container_process="CalculatorApp.exe",
            requires_launch=True,
            launch_query="calc",
            launch_method="win_r",
        )
    )
    reg = SkillRegistry(SkillsConfig(skills_dir=tmp_path))
    plan = reg.compile_to_living_plan(
        SkillMatch(skill=skill, score=1.0, parameters={"note_text": "hello"}),
        user_goal="write hello",
        active_process="explorer.exe",
    )
    assert plan.steps[0].directive is not None
    assert plan.steps[0].directive.verb == "HOTKEY"
    assert plan.steps[0].directive.keys == ["win", "r"]
    assert plan.steps[1].directive is not None
    assert plan.steps[1].directive.verb == "TYPE"
    assert plan.steps[1].directive.text == "calc"
    assert plan.steps[1].directive.submit is True


def test_uwp_application_frame_host_skips_redundant_launch(tmp_path: Path) -> None:
    from parasite_ai.config import SkillsConfig
    from parasite_ai.mind.skills import SkillMatch, SkillRegistry

    skill = _make_workflow_skill(
        preconditions=SkillPreconditions(
            container_process="CalculatorApp.exe",
            requires_launch=True,
            launch_query="calc",
            launch_method="win_r",
        )
    )
    reg = SkillRegistry(SkillsConfig(skills_dir=tmp_path))
    plan = reg.compile_to_living_plan(
        SkillMatch(skill=skill, score=1.0, parameters={"note_text": "12*7"}),
        user_goal="calculate 12*7",
        active_process="ApplicationFrameHost.exe",
        active_title="Calculator",
    )
    assert all(not (s.rationale or "").startswith("launch:") for s in plan.steps)


def test_skill_action_step_submit_and_clear_first_roundtrip() -> None:
    from parasite_ai.mind.plan import StepDirective

    skill = _make_workflow_skill(
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    target_description="Input box",
                    text="{{note_text}}",
                    submit=True,
                    clear_first=True,
                    success_criteria="Input submitted",
                )
            ]
        )
    )
    rendered = render_skill_md(skill)
    reparsed = parse_skill_md(rendered)
    assert reparsed.actions.steps[0].submit is True
    assert reparsed.actions.steps[0].clear_first is True

    directive = StepDirective(verb="TYPE", text="abc", submit=True, clear_first=True)
    assert directive.submit is True
    assert directive.clear_first is True


