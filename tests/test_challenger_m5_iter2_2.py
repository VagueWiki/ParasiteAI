"""
tests/test_challenger_m5_iter2_2.py - Adversarial Stress & Hardening Test Suite.
Challenge 2 Empirical Suite for Milestone 5 Iteration 2:
- MouseDriver coordinate normalization across virtual desktop boundaries, multi-monitor topologies, negative origins.
- KinematicsEngine bounds clamping, border overshoot clamping, and ZeroDivisionError protection.
- BrowserOffloader grounded selector resolution, bottom-most ranking, multilingual labels, and graceful fallback.
- GGUF model asset integrity, header parser validation, and RTX 4060 VRAM headroom verification.
"""

from __future__ import annotations

import math
from pathlib import Path
import random
import struct
import subprocess
import threading
from typing import Any, List, Tuple
from unittest.mock import MagicMock
import pytest

from parasite_ai.config import BrowserOffloadConfig
from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.mind.brain_manager import (
    CURATED_MODELS,
    validate_gguf_header,
)
from parasite_ai.mind.offloader import (
    BrowserOffloader,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
)
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Adversarial MouseDriver Coordinate Normalization
# ===========================================================================

class TestAdversarialMouseDriverCoordinateNormalization:
    """Stress tests MouseDriver.normalize_coordinates across diverse virtual topologies."""

    def test_single_monitor_extreme_boundaries(self):
        # 1080p display (0, 0) to (1920, 1080)
        vx, vy, vcx, vcy = 0, 0, 1920, 1080

        # Exact corners
        assert MouseDriver.normalize_coordinates(0, 0, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(1919, 1079, vx, vy, vcx, vcy) == (65535, 65535)

        # One pixel out of bounds
        assert MouseDriver.normalize_coordinates(-1, 0, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(0, -1, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(1920, 1079, vx, vy, vcx, vcy) == (65535, 65535)
        assert MouseDriver.normalize_coordinates(1919, 1080, vx, vy, vcx, vcy) == (65535, 65535)

        # Extreme values (no integer wrapping or negative outputs)
        assert MouseDriver.normalize_coordinates(-100_000, -100_000, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(100_000, 100_000, vx, vy, vcx, vcy) == (65535, 65535)

    def test_quad_monitor_2x2_topology(self):
        # 2x2 grid of 1080p monitors:
        # Top-Left: (-1920, -1080) to (-1, -1)
        # Top-Right: (0, -1080) to (1919, -1)
        # Bottom-Left: (-1920, 0) to (-1, 1079)
        # Bottom-Right (Primary): (0, 0) to (1919, 1079)
        # Total virtual desktop: vx = -1920, vy = -1080, vcx = 3840, vcy = 2160
        vx, vy, vcx, vcy = -1920, -1080, 3840, 2160

        # Far top-left corner
        assert MouseDriver.normalize_coordinates(-1920, -1080, vx, vy, vcx, vcy) == (0, 0)
        # Far bottom-right corner
        assert MouseDriver.normalize_coordinates(1919, 1079, vx, vy, vcx, vcy) == (65535, 65535)

        # Center intersection point (0, 0)
        norm_x, norm_y = MouseDriver.normalize_coordinates(0, 0, vx, vy, vcx, vcy)
        # (0 - (-1920)) / 3839 = 1920 / 3839 ~= 0.50013
        assert 32700 <= norm_x <= 32800
        # (0 - (-1080)) / 2159 = 1080 / 2159 ~= 0.50023
        assert 32700 <= norm_y <= 32800

        # Out-of-bounds in negative and positive quadrant
        assert MouseDriver.normalize_coordinates(-5000, -5000, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(5000, 5000, vx, vy, vcx, vcy) == (65535, 65535)

    def test_ultrawide_and_portrait_monitors(self):
        # 32:9 Super Ultrawide: 5120x1440
        vx, vy, vcx, vcy = 0, 0, 5120, 1440
        assert MouseDriver.normalize_coordinates(0, 0, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(5119, 1439, vx, vy, vcx, vcy) == (65535, 65535)

        # Vertical / Portrait display: 1080x1920
        vx, vy, vcx, vcy = 0, 0, 1080, 1920
        assert MouseDriver.normalize_coordinates(0, 0, vx, vy, vcx, vcy) == (0, 0)
        assert MouseDriver.normalize_coordinates(1079, 1919, vx, vy, vcx, vcy) == (65535, 65535)

    def test_degenerate_dimensions_zero_division_protection(self):
        # 1x1 pixel display
        norm = MouseDriver.normalize_coordinates(0, 0, 0, 0, 1, 1)
        assert norm == (0, 0)

        # Degenerate zero or negative virtual dimensions
        norm_zero = MouseDriver.normalize_coordinates(50, 50, 0, 0, 0, 0)
        assert norm_zero == (0, 0)

    def test_coordinate_normalization_monotonicity(self):
        # Scan 1000 horizontal points across 1080p desktop with negative padding
        vx, vy, vcx, vcy = 0, 0, 1920, 1080
        prev_norm_x = -1
        for x in range(-200, 2120, 2):
            nx, ny = MouseDriver.normalize_coordinates(x, 500, vx, vy, vcx, vcy)
            assert nx >= prev_norm_x, f"Monotonicity broken at x={x}: {nx} < {prev_norm_x}"
            assert 0 <= nx <= 65535
            assert 0 <= ny <= 65535
            prev_norm_x = nx


# ===========================================================================
# 2. Adversarial Kinematics Bounds & ZeroDivision Protection
# ===========================================================================

class TestAdversarialKinematicsBoundsAndZeroDivision:
    """Stress tests KinematicsEngine boundary conditions, zero-dist, and waypoint clamping."""

    def test_zero_division_guard_direct_single_phase(self):
        engine = KinematicsEngine()
        # Zero distance directly passed
        traj_zero = engine._generate_single_phase_trajectory((300, 300), (300, 300), dist=0.0, duration=0.2)
        assert len(traj_zero) > 0
        for pt in traj_zero:
            assert pt == (300, 300)

        # Micro distance (< 1e-6)
        traj_micro = engine._generate_single_phase_trajectory((300, 300), (300, 300), dist=1e-10, duration=0.2)
        assert len(traj_micro) > 0
        for pt in traj_micro:
            assert pt == (300, 300)

    def test_border_target_overshoot_clamping_fallback(self):
        # Target is at the exact right screen border x=1920
        # bounds = (0, 0, 1920, 1080).
        # Unclamped overshoot would place p_over at x=1923, which is > 1920.
        # Clamping forces p_over to 1920, causing d_corr == 0.0.
        # Engine must smoothly fallback to single-phase trajectory without crash.
        engine = KinematicsEngine(seed=42)
        p0 = (1500, 500)
        p_target = (1920, 500)
        bounds = (0, 0, 1920, 1080)

        traj = engine.generate_trajectory(p0, p_target, bounds=bounds)

        assert traj[0] == p0
        assert traj[-1] == p_target
        # Verify no points exceed the 1920 border
        for pt in traj:
            assert 0 <= pt[0] <= 1920, f"Waypoint {pt} exceeded x bounds [0, 1920]"
            assert 0 <= pt[1] <= 1080, f"Waypoint {pt} exceeded y bounds [0, 1080]"

    def test_all_four_screen_borders_with_overshoot(self):
        engine = KinematicsEngine(seed=999)
        bounds = (0, 0, 1920, 1080)

        # Test reaches terminating at Top, Bottom, Left, and Right borders
        border_targets = [
            ((500, 500), (500, 0)),      # Top border
            ((500, 500), (500, 1080)),   # Bottom border
            ((500, 500), (0, 500)),      # Left border
            ((500, 500), (1920, 500)),   # Right border
            ((500, 500), (0, 0)),        # Top-Left corner
            ((500, 500), (1920, 1080)),  # Bottom-Right corner
        ]

        for p_start, p_end in border_targets:
            traj = engine.generate_trajectory(p_start, p_end, bounds=bounds)
            assert traj[0] == p_start
            assert traj[-1] == p_end
            for pt in traj:
                assert bounds[0] <= pt[0] <= bounds[2], f"x out of bounds: {pt}"
                assert bounds[1] <= pt[1] <= bounds[3], f"y out of bounds: {pt}"

    def test_negative_bounds_dual_monitor_clamping(self):
        engine = KinematicsEngine(seed=777)
        # Dual monitor setup: vx = -1920 to 1920, vy = 0 to 1080
        bounds = (-1920, 0, 1920, 1080)

        p_start = (500, 500)
        p_end = (-1900, 200)

        traj = engine.generate_trajectory(p_start, p_end, bounds=bounds)
        assert traj[0] == p_start
        assert traj[-1] == p_end

        for pt in traj:
            assert -1920 <= pt[0] <= 1920, f"Dual monitor x out of bounds: {pt}"
            assert 0 <= pt[1] <= 1080, f"Dual monitor y out of bounds: {pt}"

    def test_stress_500_random_trajectories_within_bounds(self):
        engine = KinematicsEngine()
        rng = random.Random(12345)
        bounds = (0, 0, 1920, 1080)

        for _ in range(500):
            p0 = (rng.randint(0, 1920), rng.randint(0, 1080))
            p1 = (rng.randint(0, 1920), rng.randint(0, 1080))
            traj = engine.generate_trajectory(p0, p1, bounds=bounds)

            assert traj[0] == p0
            assert traj[-1] == p1
            for pt in traj:
                assert 0 <= pt[0] <= 1920
                assert 0 <= pt[1] <= 1080


# ===========================================================================
# 3. Adversarial BrowserOffloader Grounded Selector Resolution & Fallback
# ===========================================================================

class TestAdversarialBrowserOffloaderSelectors:
    """Stress tests BrowserOffloader grounded target ranking, fallback, and resilience."""

    def test_grounded_prompt_ranks_bottom_most(self):
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=1111)
        mock_mouse = MagicMock()
        mock_kbd = MagicMock()

        # Mock grounder with multiple edit fields (e.g. search bar, URL bar, chat box)
        mock_grounder = MagicMock()
        mock_grounder.ground.return_value = [
            UIElement.from_bbox(id=1, bbox=(100, 50, 400, 40), label="Search web", role="Edit"),
            UIElement.from_bbox(id=2, bbox=(200, 950, 600, 60), label="Ask a question...", role="Edit"),
            UIElement.from_bbox(id=3, bbox=(100, 120, 500, 30), label="Address bar", role="Edit"),
        ]

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            mouse_driver=mock_mouse,
            keyboard_driver=mock_kbd,
            grounder=mock_grounder,
        )
        offloader.verifier.execute_harvest = MagicMock(return_value="Model answer")

        offloader.query_web_ai("Prompt")

        # The bottom-most edit field is id=2 with bbox center_y = 950 + 30 = 980, center_x = 200 + 300 = 500
        clicked_coords = [(call.args[0], call.args[1]) for call in mock_mouse.click.call_args_list]
        assert (500, 980) in clicked_coords

    def test_grounded_copy_button_ranks_latest_response(self):
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=2222)
        mock_mouse = MagicMock()
        mock_kbd = MagicMock()

        # Mock grounder with multiple Copy buttons from chat history
        mock_grounder = MagicMock()
        mock_grounder.ground.return_value = [
            UIElement.from_bbox(id=1, bbox=(400, 800, 500, 60), label="Chat input", role="Edit"),
            UIElement.from_bbox(id=2, bbox=(600, 200, 40, 20), label="Copy message", role="Button"),
            UIElement.from_bbox(id=3, bbox=(600, 450, 40, 20), label="Copy message", role="Button"),
            UIElement.from_bbox(id=4, bbox=(600, 720, 40, 20), label="Copy message", role="Button"),  # Latest
        ]

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            mouse_driver=mock_mouse,
            keyboard_driver=mock_kbd,
            grounder=mock_grounder,
        )

        def mock_harvest(trigger_copy_action, **kwargs):
            trigger_copy_action()
            return "Harvested text"

        offloader.verifier.execute_harvest = mock_harvest

        offloader.query_web_ai("Prompt")

        # The bottom-most copy button is id=4 at center_x = 620, center_y = 730
        clicked_coords = [(call.args[0], call.args[1]) for call in mock_mouse.click.call_args_list]
        assert (620, 730) in clicked_coords

    def test_multilingual_copy_button_recognition(self):
        win = MockBrowserWindowBackend(existing_hwnd=3333)

        # Test German, French, and Indonesian labels
        test_labels = ["Kopieren", "Copier", "Salin", "Copy to clipboard"]
        for lbl in test_labels:
            mock_grounder = MagicMock()
            mock_grounder.ground.return_value = [
                UIElement.from_bbox(id=1, bbox=(100, 100, 40, 20), label=lbl, role="Button"),
            ]
            offloader = BrowserOffloader(window_backend=win, grounder=mock_grounder)
            coords = offloader._find_copy_button(hwnd=3333)
            assert coords is not None, f"Failed to recognize copy button with label '{lbl}'"
            assert coords == (120, 110)

    def test_grounder_failure_resilience_and_heuristic_fallback(self):
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=4444)
        win.rect = (100, 100, 1100, 900)  # width=1000, height=800, center_x = 600, bottom = 900
        mock_mouse = MagicMock()
        mock_kbd = MagicMock()

        # Grounder crashes with RPC/COM exception
        mock_grounder = MagicMock()
        mock_grounder.ground.side_effect = RuntimeError("COM connection terminated")

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            mouse_driver=mock_mouse,
            keyboard_driver=mock_kbd,
            grounder=mock_grounder,
        )

        def mock_harvest(trigger_copy_action, **kwargs):
            trigger_copy_action()
            return "Heuristic harvest"

        offloader.verifier.execute_harvest = mock_harvest

        resp = offloader.query_web_ai("Prompt")
        assert resp == "Heuristic harvest"

        # Prompt must have fallen back to window heuristic: center_x = 600, prompt_y = 900 - 120 = 780
        clicked_coords = [(call.args[0], call.args[1]) for call in mock_mouse.click.call_args_list]
        assert (600, 780) in clicked_coords

        # Copy trigger must have fallen back to Tier 2: click canvas + Ctrl+C
        assert mock_kbd.hotkey.called
        assert mock_kbd.hotkey.call_args_list[1].args == ("ctrl", "c")


# ===========================================================================
# 4. GGUF Model Asset Integrity & RTX 4060 VRAM Headroom
# ===========================================================================

class TestGGUFModelIntegrityAndVRAMBudget:
    """Verifies physical GGUF binary integrity, header parser, and GPU VRAM headroom."""

    def test_gguf_file_physical_integrity(self):
        model_path = Path("models/qwen2.5-3b-instruct-q4_k_m.gguf")
        assert model_path.is_file(), f"Model file missing at {model_path.resolve()}"

        file_size = model_path.stat().st_size
        assert file_size == 2_104_932_768, f"Unexpected model size: {file_size} bytes"

        # Validate header via brain_manager
        is_valid = validate_gguf_header(model_path)
        assert is_valid is True, "validate_gguf_header returned False on model file"

        # Direct binary verification of GGUF v3 structure
        with open(model_path, "rb") as f:
            magic = f.read(4)
            version = struct.unpack("<I", f.read(4))[0]
            n_tensors = struct.unpack("<Q", f.read(8))[0]
            n_kv = struct.unpack("<Q", f.read(8))[0]

        assert magic == b"GGUF", f"Expected magic b'GGUF', got {magic}"
        assert version == 3, f"Expected GGUF version 3, got {version}"
        assert n_tensors == 435, f"Expected 435 tensors, got {n_tensors}"
        assert n_kv == 26, f"Expected 26 KV metadata entries, got {n_kv}"

    def test_gguf_header_corrupt_rejection(self, tmp_path: Path):
        # Truncated file
        short_file = tmp_path / "short.gguf"
        short_file.write_bytes(b"GGU")
        assert validate_gguf_header(short_file) is False

        # Invalid magic
        bad_magic = tmp_path / "bad_magic.gguf"
        bad_magic.write_bytes(b"GGML" + struct.pack("<I", 3))
        assert validate_gguf_header(bad_magic) is False

        # Unsupported version
        bad_version = tmp_path / "bad_version.gguf"
        bad_version.write_bytes(b"GGUF" + struct.pack("<I", 99))
        assert validate_gguf_header(bad_version) is False

    def test_nvidia_gpu_vram_headroom_rtx4060(self):
        # Query host GPU memory via nvidia-smi
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
            )
            line = res.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            gpu_name = parts[0]
            total_mb = int(parts[1])
            free_mb = int(parts[2])

            assert "RTX 4060" in gpu_name or total_mb >= 8000, f"Host GPU mismatch: {gpu_name}"
            # Required VRAM for Qwen2.5-3B-Instruct Q4_K_M is 3200 MiB
            qwen_budget_mb = 3200
            assert free_mb >= qwen_budget_mb, f"Insufficient free VRAM: {free_mb} MB free < {qwen_budget_mb} MB required"
            # Verify substantial safety headroom (> 1000 MB margin)
            headroom_mb = free_mb - qwen_budget_mb
            assert headroom_mb >= 1000, f"VRAM headroom too tight: only {headroom_mb} MB buffer"
        except FileNotFoundError:
            pytest.skip("nvidia-smi not available on system")
