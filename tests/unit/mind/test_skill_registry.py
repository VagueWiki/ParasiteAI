"""Unit tests for SkillRegistry matching, draft approval gate, TTL decay, quarantine, and §7.6 4-gate check."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import numpy as np
import pytest

from parasite_ai.config import SkillsConfig
from parasite_ai.mind.memory import ActionType, compute_phash
from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    ContainerWindowSnapshot,
    ReflexSafetyGate,
    SkillActionStep,
    SkillActions,
    SkillDefinition,
    SkillParameter,
    SkillPostconditions,
    SkillPreconditions,
    SkillProvenance,
    SkillRegistry,
    SkillState,
    SkillStats,
    SkillTrigger,
    SkillType,
    VisualAnchor,
    verify_and_resolve_reflex_skill,
)

pytestmark = pytest.mark.unit


class _FakeCapturer:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.calls: int = 0

    def capture_rect(self, rect):
        self.calls += 1
        return self.frame


class _FakeWindowProbe:
    def __init__(self, snap: Optional[ContainerWindowSnapshot]) -> None:
        self.snap = snap

    def get_active_container(
        self, process_name: str, title_regex: Optional[str] = None
    ) -> Optional[ContainerWindowSnapshot]:
        return self.snap

    def get_window_by_hwnd(self, hwnd: int) -> Optional[ContainerWindowSnapshot]:
        if self.snap and self.snap.hwnd == hwnd:
            return self.snap
        return None


def _build_skill(
    skill_id: str,
    *,
    draft: bool = False,
    state: SkillState = SkillState.ACTIVE,
    provenance: SkillProvenance = SkillProvenance.AUTHORED,
    patterns=None,
    keywords=None,
    process_names=None,
    min_score: float = 0.6,
    success_count: int = 0,
    params=None,
    verified_at: Optional[datetime] = None,
) -> SkillDefinition:
    now = verified_at or datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    return SkillDefinition(
        id=skill_id,
        name=f"Skill {skill_id}",
        type=SkillType.WORKFLOW,
        draft=draft,
        state=state,
        provenance=provenance,
        description=f"Semantic skill {skill_id}.",
        trigger=SkillTrigger(
            goal_patterns=patterns or [r"^save note (?P<title>.+)$"],
            keywords=keywords or ["save", "note"],
            process_names=process_names or ["notepad.exe"],
            min_score=min_score,
        ),
        parameters=params or [SkillParameter(name="title", required=True)],
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    target_description="Filename field",
                    text="{{title}}",
                    success_criteria="Filename filled",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Note saved"),
        stats=SkillStats(
            created_at=now,
            last_verified_at=now,
            success_count=success_count,
        ),
    )


def test_load_all_skips_underscore_dirs_and_malformed_files(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path)
    (tmp_path / "_template").mkdir()
    (tmp_path / "_template" / "SKILL.md").write_text("---\ninvalid: [", encoding="utf-8")
    (tmp_path / "_quarantine" / "old-skill").mkdir(parents=True)
    (tmp_path / "_quarantine" / "old-skill" / "SKILL.md").write_text("---\nbad", encoding="utf-8")
    (tmp_path / "broken-skill").mkdir()
    (tmp_path / "broken-skill" / "SKILL.md").write_text("---\nnot_a_skill: true\n---\n", encoding="utf-8")

    fixed_now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(cfg, clock=lambda: fixed_now)
    good = _build_skill("good-skill", verified_at=fixed_now)
    reg.save(good)

    report = reg.load_all()
    assert report.loaded == 1
    assert len(report.errors) == 1
    assert "good-skill" in reg.skills


def test_draft_skills_excluded_until_approve_draft_and_reject_quarantines(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path)
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(cfg, clock=lambda: now)

    draft_skill = _build_skill("learned-note", draft=True, state=SkillState.CANDIDATE, verified_at=now)
    reg.save(draft_skill)

    # Draft skills must NEVER match automatically
    assert reg.match("save note shopping_list", "notepad.exe") is None

    approved = reg.approve_draft("learned-note")
    assert approved.draft is False
    matched = reg.match("save note shopping_list", "notepad.exe")
    assert matched is not None
    assert matched.skill.id == "learned-note"
    assert matched.parameters["title"] == "shopping_list"

    # Rejecting a second draft moves it cleanly to _quarantine/ without unlink
    bad_draft = _build_skill("rejected-note", draft=True, state=SkillState.CANDIDATE, verified_at=now)
    reg.save(bad_draft)
    q_path = reg.reject_draft("rejected-note", "Unwanted pattern")
    assert q_path.exists()
    assert not (tmp_path / "rejected-note").exists()
    assert "rejected-note" not in reg.skills


def test_deterministic_scoring_tiebreak_and_required_param_miss(tmp_path: Path) -> None:
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path)
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(cfg, clock=lambda: now)

    s1 = _build_skill("alpha-skill", success_count=3, verified_at=now)
    s2 = _build_skill("beta-skill", success_count=10, verified_at=now)
    s3 = _build_skill("gamma-skill", success_count=10, verified_at=now)
    reg.save(s1)
    reg.save(s2)
    reg.save(s3)

    # Highest success_count breaks score tie; lowest id breaks success_count tie
    best = reg.match("save note journal", "notepad.exe")
    assert best is not None
    assert best.skill.id == "beta-skill"

    # Required parameter missing (pattern doesn't match to populate 'title') -> None even if keyword+proc match >= 0.4
    no_param_match = _build_skill(
        "needs-param",
        patterns=[r"^export (?P<title>.+)$"],
        keywords=["save", "note"],
        min_score=0.3,
        verified_at=now,
    )
    reg2 = SkillRegistry(SkillsConfig(enabled=True, skills_dir=tmp_path / "sub"), clock=lambda: now)
    reg2.save(no_param_match)
    assert reg2.match("save note", "notepad.exe") is None


def test_ttl_decay_boundaries_and_stale_reverification(tmp_path: Path) -> None:
    t0 = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    current = [t0]
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, ttl_days=30)
    reg = SkillRegistry(cfg, clock=lambda: current[0])

    s = _build_skill("ttl-skill", state=SkillState.ACTIVE, verified_at=t0)
    reg.save(s)

    # Day 29 & exact Day 30 -> ACTIVE
    current[0] = t0 + timedelta(days=29)
    assert not reg.evaluate_freshness(s, persist=True).expired
    current[0] = t0 + timedelta(days=30)
    assert not reg.evaluate_freshness(s, persist=True).expired
    assert s.state == SkillState.ACTIVE

    # Day 31 -> decays to STALE and excluded from match()
    current[0] = t0 + timedelta(days=31)
    report = reg.load_all()
    assert report.decayed_to_stale == 1
    assert reg.get("ttl-skill").state == SkillState.STALE
    assert reg.match("save note demo", "notepad.exe") is None
    assert reg.find_stale_match("save note demo", "notepad.exe") is not None

    # Successful guided re-verification restores ACTIVE and refreshes verified timestamp
    anchor = VisualAnchor(phash="0123456789abcdef", window_size=(640, 480), captured_at=current[0])
    updated = reg.record_outcome("ttl-skill", success=True, anchor=anchor)
    assert updated.state == SkillState.ACTIVE
    assert updated.stats.last_verified_at == current[0]


def test_consecutive_failures_quarantines_and_moves_directory(tmp_path: Path) -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, max_consecutive_failures=2)
    reg = SkillRegistry(cfg, clock=lambda: now)

    skill = _build_skill(
        "flaky-skill",
        state=SkillState.ACTIVE,
        provenance=SkillProvenance.LEARNED,
        verified_at=now,
    )
    reg.save(skill)
    assert (tmp_path / "flaky-skill" / "SKILL.md").is_file()

    reg.record_outcome("flaky-skill", success=False)
    assert reg.get("flaky-skill").stats.consecutive_failures == 1
    assert (tmp_path / "flaky-skill" / "SKILL.md").is_file()

    reg.record_outcome("flaky-skill", success=False)
    assert "flaky-skill" not in reg.skills
    assert not (tmp_path / "flaky-skill").exists()
    q_file = tmp_path / "_quarantine" / "flaky-skill" / "SKILL.md"
    assert q_file.is_file()
    assert "INVALIDATED" in q_file.read_text(encoding="utf-8")


def test_authored_skill_degrades_to_stale_instead_of_quarantine(tmp_path: Path) -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    cfg = SkillsConfig(enabled=True, skills_dir=tmp_path, max_consecutive_failures=2)
    reg = SkillRegistry(cfg, clock=lambda: now)

    skill = _build_skill(
        "protected-authored",
        state=SkillState.ACTIVE,
        provenance=SkillProvenance.AUTHORED,
        verified_at=now,
    )
    reg.save(skill)

    reg.record_outcome("protected-authored", success=False)
    reg.record_outcome("protected-authored", success=False)
    assert "protected-authored" in reg.skills
    assert reg.get("protected-authored").state == SkillState.STALE
    assert (tmp_path / "protected-authored" / "SKILL.md").is_file()
    assert not (tmp_path / "_quarantine" / "protected-authored").exists()

    # Non-forced quarantine() call also degrades AUTHORED to STALE rather than moving
    reg.quarantine("protected-authored", reason="Drift check")
    assert "protected-authored" in reg.skills
    assert reg.get("protected-authored").state == SkillState.STALE
    assert not (tmp_path / "_quarantine" / "protected-authored").exists()


def test_compile_to_living_plan_substitutes_parameters(tmp_path: Path) -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=tmp_path), clock=lambda: now)
    skill = _build_skill("param-skill", verified_at=now)
    reg.save(skill)

    match = reg.match("save note quarterly_report", "notepad.exe")
    assert match is not None
    plan = reg.compile_to_living_plan(match, "save note quarterly_report")
    assert len(plan.steps) == 1
    assert "quarterly_report" in plan.steps[0].description
    assert plan.steps[0].tool_route == "GUI"
    assert "skill:param-skill@v1" in plan.steps[0].rationale


def test_reflex_micro_skill_4gate_checks_pass_and_fail_closed() -> None:
    # Textured frame matching compute_phash anchor
    rng = np.random.default_rng(7)
    base_frame = rng.integers(0, 255, size=(400, 300, 3), dtype=np.uint8)
    expected_phash = compute_phash(base_frame)

    skill = SkillDefinition(
        id="static-pad",
        name="Static Keypad",
        type=SkillType.REFLEX_MICRO_SKILL,
        state=SkillState.ACTIVE,
        description="Static client-relative reflex.",
        trigger=SkillTrigger(keywords=["pad"], min_score=0.3),
        preconditions=SkillPreconditions(container_process="calc.exe"),
        reflex_gate=ReflexSafetyGate(
            expected_window_size=(300, 400),
            relative_origin="client_top_left",
            phash_anchor=expected_phash,
            phash_max_hamming=4,
        ),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="CLICK",
                    relative_coordinates=(50, 120),
                    success_criteria="Key pressed",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Digit visible"),
    )

    good_snap = ContainerWindowSnapshot(
        hwnd=999,
        process_name="calc.exe",
        title="Calculator",
        window_rect=(100, 200, 416, 639),
        client_origin=(108, 232),
        client_size=(300, 400),
    )

    # Gate 1–4 pass: client_origin (108, 232) + relative (50, 120) -> (158, 352)
    ok_res = verify_and_resolve_reflex_skill(
        skill, _FakeWindowProbe(good_snap), _FakeCapturer(base_frame)
    )
    assert ok_res.ok is True
    assert ok_res.target_hwnd == 999
    assert ok_res.action_plan is not None
    assert ok_res.action_plan.action == ActionType.BURST
    assert ok_res.action_plan.burst_actions[0].coordinates == (158, 352)

    # Gate 2 fail: dimension mismatch must fail closed BEFORE capture/pHash
    wrong_size_snap = ContainerWindowSnapshot(
        hwnd=999,
        process_name="calc.exe",
        title="Calculator",
        window_rect=(100, 200, 500, 700),
        client_origin=(108, 232),
        client_size=(350, 400),
    )
    fake_cap = _FakeCapturer(base_frame)
    bad_dim = verify_and_resolve_reflex_skill(skill, _FakeWindowProbe(wrong_size_snap), fake_cap)
    assert bad_dim.ok is False
    assert fake_cap.calls == 0
    assert bad_dim.fallback == "uia_vlm"

    # Gate 3 fail: structurally different frame -> pHash drift -> fail closed
    different_frame = np.zeros((400, 300, 3), dtype=np.uint8)
    different_frame[:, :150] = 255
    bad_phash = verify_and_resolve_reflex_skill(
        skill, _FakeWindowProbe(good_snap), _FakeCapturer(different_frame)
    )
    assert bad_phash.ok is False
    assert bad_phash.drifted is True
    assert bad_phash.fallback == "uia_vlm"


def test_compile_to_living_plan_attaches_directives_without_reflex_coords(tmp_path: Path) -> None:
    from parasite_ai.mind.skills import SkillRegistry, render_skill_md

    skills_dir = tmp_path / "skills"
    (skills_dir / "note-writer").mkdir(parents=True)
    skill = SkillDefinition(
        id="note-writer",
        name="Note Writer",
        description="Write a note",
        trigger=SkillTrigger(goal_patterns=[r"^write (?P<note>.+)$"], keywords=["write"]),
        parameters=[SkillParameter(name="note", description="Text body", required=True)],
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    text="{{note}}",
                    success_criteria="Typed",
                ),
                SkillActionStep(
                    intent=StepIntent.NAVIGATE,
                    verb="HOTKEY",
                    keys=["ctrl", "s"],
                    success_criteria="Saved",
                ),
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Saved"),
    )
    (skills_dir / "note-writer" / "SKILL.md").write_text(render_skill_md(skill), encoding="utf-8")

    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=skills_dir))
    reg.load_all()
    match = reg.match("write hello world", active_process="notepad.exe")
    assert match is not None

    lp = reg.compile_to_living_plan(match, "write hello world")
    assert lp.steps[0].directive is not None
    assert lp.steps[0].directive.verb == "TYPE"
    assert lp.steps[0].directive.text == "hello world"
    assert lp.steps[1].directive is not None
    assert lp.steps[1].directive.verb == "HOTKEY"
    assert lp.steps[1].directive.keys == ["ctrl", "s"]


def test_compile_to_living_plan_prepends_launch_triple_when_requires_launch(tmp_path: Path) -> None:
    from parasite_ai.mind.skills import SkillRegistry, render_skill_md

    skills_dir = tmp_path / "skills"
    (skills_dir / "notepad-launch").mkdir(parents=True)
    skill = SkillDefinition(
        id="notepad-launch",
        name="Notepad Launch",
        description="Launch Notepad and type",
        trigger=SkillTrigger(goal_patterns=[r"^open notepad$"], keywords=["notepad"]),
        preconditions=SkillPreconditions(container_process="notepad.exe", requires_launch=True),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    text="hello",
                    success_criteria="Typed",
                ),
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Done"),
    )
    (skills_dir / "notepad-launch" / "SKILL.md").write_text(render_skill_md(skill), encoding="utf-8")

    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=skills_dir))
    reg.load_all()
    match = reg.match("open notepad")
    assert match is not None

    # Active process != notepad.exe -> prepends Win + Type "notepad" (submit=True)
    lp_launch = reg.compile_to_living_plan(match, "open notepad", active_process="explorer.exe")
    assert len(lp_launch.steps) == 3
    assert lp_launch.steps[0].rationale == "launch:open_start"
    assert lp_launch.steps[0].directive is not None
    assert lp_launch.steps[0].directive.verb == "HOTKEY"
    assert lp_launch.steps[0].directive.keys == ["win"]
    assert lp_launch.steps[1].rationale == "launch:submit_search"
    assert lp_launch.steps[1].directive is not None
    assert lp_launch.steps[1].directive.verb == "TYPE"
    assert lp_launch.steps[1].directive.text == "notepad"
    assert lp_launch.steps[1].directive.submit is True
    assert lp_launch.steps[2].step_id == 3
    assert lp_launch.steps[2].directive is not None
    assert lp_launch.steps[2].directive.text == "hello"

    # Active process == notepad.exe -> skips launch steps
    lp_in_app = reg.compile_to_living_plan(match, "open notepad", active_process="notepad.exe")
    assert len(lp_in_app.steps) == 1
    assert lp_in_app.steps[0].directive is not None
    assert lp_in_app.steps[0].directive.text == "hello"


def test_keyword_only_skill_matches_above_min_score(tmp_path: Path) -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=tmp_path), clock=lambda: now)

    kw_skill = _build_skill(
        "kw-minimize",
        draft=False,
        state=SkillState.CANDIDATE,
        patterns=[],
        keywords=["minimize", "notepad"],
        process_names=["notepad.exe"],
        params=[],
        min_score=0.6,
        verified_at=now,
    )
    kw_skill.trigger.goal_patterns = []
    kw_skill.parameters = []
    kw_skill.actions.steps[0].text = "done"
    reg.save(kw_skill)

    # Full keyword match scores 0.85 even when active_process != notepad.exe (>= 0.6)
    hit = reg.match("Minimize Notepad", active_process="explorer.exe")
    assert hit is not None
    assert hit.skill.id == "kw-minimize"
    assert hit.score >= 0.85

    # Partial keyword match (1/2) without process hit stays below 0.6 -> no false match
    assert reg.match("Open Notepad", active_process="explorer.exe") is None


def test_score_skill_strips_outer_quotes_and_compiles_submit_clear_first(tmp_path: Path) -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=tmp_path), clock=lambda: now)

    skill = SkillDefinition(
        id="quoted-writer",
        name="Quoted Writer",
        type=SkillType.WORKFLOW,
        draft=False,
        state=SkillState.ACTIVE,
        description="Write quoted text and submit",
        trigger=SkillTrigger(
            goal_patterns=[r"^open notepad and write (?P<text>.+)$"],
            keywords=["notepad", "write"],
            process_names=["notepad.exe"],
            min_score=0.6,
        ),
        parameters=[SkillParameter(name="text", required=True)],
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.INPUT_DATA,
                    verb="TYPE",
                    text="{{text}}",
                    submit=True,
                    clear_first=True,
                    success_criteria="Text submitted",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Done"),
        stats=SkillStats(created_at=now, last_verified_at=now),
    )
    reg.save(skill)

    m = reg.match("Open Notepad and write 'Benchmark Alpha Test 42'", active_process="notepad.exe")
    assert m is not None
    assert m.parameters["text"] == "Benchmark Alpha Test 42"

    lp = reg.compile_to_living_plan(m, "Open Notepad and write 'Benchmark Alpha Test 42'", active_process="notepad.exe")
    assert lp.steps[0].directive is not None
    assert lp.steps[0].directive.text == "Benchmark Alpha Test 42"
    assert lp.steps[0].directive.submit is True
    assert lp.steps[0].directive.clear_first is True
