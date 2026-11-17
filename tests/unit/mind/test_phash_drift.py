"""Unit tests for pure-NumPy 64-bit DCT pHash and container visual drift quarantine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image
import pytest

from parasite_ai.config import SkillsConfig
from parasite_ai.mind.memory import compute_phash, hamming_distance
from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    ContainerWindowSnapshot,
    InvalidationCriteria,
    SkillActionStep,
    SkillActions,
    SkillDefinition,
    SkillPostconditions,
    SkillPreconditions,
    SkillProvenance,
    SkillRegistry,
    SkillState,
    SkillTrigger,
    VisualAnchor,
)

pytestmark = pytest.mark.unit


def _textured_image(width: int = 320, height: int = 240) -> np.ndarray:
    """Builds a realistic asymmetric UI-like frame with rich low-frequency spectral structure."""
    img = np.full((height, width, 3), 210, dtype=np.uint8)
    # Header bar
    img[: height // 8, :, :] = [45, 70, 120]
    # Left navigation rail
    img[height // 8 :, : width // 4, :] = [180, 185, 195]
    # Content cards with diagonal ramp (bounded inside [35..220] to avoid clipping)
    gx = np.linspace(40, 190, width)[None, :]
    gy = np.linspace(30, 170, height)[:, None]
    grad = ((gx + gy) * 0.5).astype(np.uint8)
    img[height // 4 : (3 * height) // 4, width // 3 : (5 * width) // 6, 0] = grad[
        height // 4 : (3 * height) // 4, width // 3 : (5 * width) // 6
    ]
    # Button highlight block
    img[(5 * height) // 8 : (6 * height) // 8, (5 * width) // 8 : (7 * width) // 8] = [30, 140, 90]
    return img


def test_compute_phash_deterministic_and_identical_zero_distance() -> None:
    img = _textured_image()
    h1 = compute_phash(img)
    h2 = compute_phash(img.copy())
    assert len(h1) == 16
    assert h1 == h2
    assert hamming_distance(h1, h2) == 0


def test_compute_phash_noise_and_brightness_resilience() -> None:
    img = _textured_image()
    h_orig = compute_phash(img)

    # +/- 10% brightness + mild Gaussian noise should remain within threshold (<= 10)
    rng = np.random.default_rng(123)
    bright = np.clip(img.astype(np.float32) * 1.10 + rng.normal(0, 3.0, img.shape), 0, 255).astype(np.uint8)
    dim = np.clip(img.astype(np.float32) * 0.90, 0, 255).astype(np.uint8)

    assert hamming_distance(h_orig, compute_phash(bright)) <= 10
    assert hamming_distance(h_orig, compute_phash(dim)) <= 10


def test_compute_phash_structurally_different_layouts_exceed_threshold() -> None:
    grad_h = np.tile(np.linspace(0, 255, 240, dtype=np.uint8)[:, None, None], (1, 320, 3))
    checker = np.zeros((240, 320, 3), dtype=np.uint8)
    checker[:120, :160] = 255
    checker[120:, 160:] = 255

    dist = hamming_distance(compute_phash(grad_h), compute_phash(checker))
    assert dist > 10


def test_compute_phash_scale_invariance() -> None:
    base = _textured_image(320, 240)
    scaled = np.asarray(Image.fromarray(base).resize((640, 480), Image.Resampling.LANCZOS))
    assert hamming_distance(compute_phash(base), compute_phash(scaled)) <= 4


def test_compute_phash_empty_and_invalid_sentinel() -> None:
    assert compute_phash(np.zeros((0, 0, 3), dtype=np.uint8)) == "0000000000000000"
    assert compute_phash(None) == "0000000000000000"  # type: ignore[arg-type]


class _SpyCapturer:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.captured_rects = []

    def capture_rect(self, rect):
        self.captured_rects.append(rect)
        return self.frame


class _Probe:
    def __init__(self, snap: ContainerWindowSnapshot) -> None:
        self.snap = snap

    def get_active_container(self, process_name: str, title_regex: Optional[str] = None):
        return self.snap

    def get_window_by_hwnd(self, hwnd: int):
        return self.snap if self.snap.hwnd == hwnd else None


def test_drift_verdict_uses_exact_os_rect_and_min_over_anchors(tmp_path: Path) -> None:
    img_a = _textured_image(400, 300)
    hash_a = compute_phash(img_a)
    different_hash = "ffffffff00000000"

    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    cap = _SpyCapturer(img_a)
    snap = ContainerWindowSnapshot(
        hwnd=77,
        process_name="notepad.exe",
        title="Untitled - Notepad",
        window_rect=(50, 60, 450, 360),
        client_origin=(58, 92),
        client_size=(384, 260),
    )
    reg = SkillRegistry(
        SkillsConfig(enabled=True, skills_dir=tmp_path),
        clock=lambda: now,
        window_probe=_Probe(snap),
        capturer=cap,
    )

    skill = SkillDefinition(
        id="anchored-skill",
        name="Anchored",
        state=SkillState.ACTIVE,
        provenance=SkillProvenance.LEARNED,
        description="Anchored workflow.",
        trigger=SkillTrigger(keywords=["test"], min_score=0.3),
        preconditions=SkillPreconditions(container_process="notepad.exe"),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.NAVIGATE,
                    verb="HOTKEY",
                    keys=["ctrl", "s"],
                    success_criteria="Save open",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Saved"),
        invalidation=InvalidationCriteria(
            phash_max_hamming=10,
            visual_anchors=[
                VisualAnchor(phash=different_hash, window_size=(400, 300), captured_at=now),
                VisualAnchor(phash=hash_a, window_size=(400, 300), captured_at=now),
            ],
        ),
    )
    reg.save(skill)

    # First check matches the second anchor (min hamming == 0)
    verdict = reg.check_visual_drift(skill, hwnd=77)
    assert verdict.checked is True
    assert verdict.drifted is False
    assert verdict.min_hamming == 0
    # Strictly queried OS rect (left, top, width, height) with zero synthetic offsets
    assert cap.captured_rects == [(50, 60, 400, 300)]

    # Mutate live frame to an orthogonal layout -> drift detected -> quarantine moves skill
    checker = np.zeros((300, 400, 3), dtype=np.uint8)
    checker[:150, :200] = 255
    checker[150:, 200:] = 255
    cap.frame = checker
    drift = reg.check_visual_drift(skill, hwnd=77)
    if drift.drifted:
        q_dest = reg.quarantine(skill.id, drift.reason)
        assert q_dest.exists()
    assert drift.drifted is True
    assert not (tmp_path / "anchored-skill").exists()


def test_dual_mind_does_not_quarantine_workflow_skill_on_phash_drift(tmp_path: Path) -> None:
    """Coordinate-free WORKFLOW skills must not be quarantined by full-window pHash differences."""
    from unittest.mock import MagicMock
    from parasite_ai.config import AppConfig, SkillsConfig
    from parasite_ai.mind.dual_mind import DualMindPipeline
    from parasite_ai.mind.skills import SkillMatch, SkillType

    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=tmp_path))
    workflow_skill = SkillDefinition(
        id="wf-paint",
        name="Paint WF",
        type=SkillType.WORKFLOW,
        state=SkillState.ACTIVE,
        description="Keyboard workflow",
        trigger=SkillTrigger(keywords=["paint"], min_score=0.5),
        preconditions=SkillPreconditions(container_process="mspaint.exe", requires_launch=True),
        actions=SkillActions(
            steps=[
                SkillActionStep(
                    intent=StepIntent.NAVIGATE,
                    verb="HOTKEY",
                    keys=["ctrl", "s"],
                    target_description="Save",
                    success_criteria="Save open",
                )
            ]
        ),
        postconditions=SkillPostconditions(success_criteria="Saved"),
        invalidation=InvalidationCriteria(
            phash_max_hamming=8,
            visual_anchors=[
                VisualAnchor(
                    phash="0000000000000000",
                    window_size=(400, 300),
                    captured_at=datetime.now(timezone.utc),
                )
            ],
        ),
    )
    reg.save(workflow_skill)
    reg.check_visual_drift = MagicMock()  # type: ignore[method-assign]
    reg.quarantine = MagicMock()  # type: ignore[method-assign]

    cfg = AppConfig(skills=SkillsConfig(enabled=True, skills_dir=tmp_path))
    brain = MagicMock()
    brain.is_cua_mode.return_value = False
    pipeline = DualMindPipeline(brain_manager=brain, config=cfg, skill_registry=reg)
    pipeline._active_skill_match = SkillMatch(skill=workflow_skill, score=1.0, parameters={})
    pipeline.active_plan = reg.compile_to_living_plan(
        pipeline._active_skill_match, user_goal="save paint", active_process="mspaint.exe"
    )
    pipeline.step("save paint")

    reg.quarantine.assert_not_called()
    assert (tmp_path / "wf-paint" / "SKILL.md").exists()

