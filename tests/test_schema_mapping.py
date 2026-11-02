"""
tests/test_schema_mapping.py - Complete Schema Mapping & 64-bit ABI Structure Certification.

Verifies:
  1. All 10 Win32 ctypes structures conform to exact 64-bit Windows ABI memory layouts:
     - POINT: 8 bytes
     - RECT: 16 bytes
     - MSLLHOOKSTRUCT: 32 bytes
     - KBDLLHOOKSTRUCT: 24 bytes
     - MOUSEINPUT: 32 bytes
     - KEYBDINPUT: 24 bytes
     - HARDWAREINPUT: 8 bytes
     - INPUT_UNION: 32 bytes
     - INPUT: 40 bytes
     - GUITHREADINFO: 72 bytes
  2. Field offsets and compiler padding match 64-bit ABI alignment.
  3. Pydantic v2 data models (UIElement, BoundingBox, PlanStep, LivingPlan, ActionPlan, StepRecord, AppConfig).
  4. Core system invariants (Zero silent cloud exfiltration: BrainConfig default 'local_llm').
"""

import ctypes
from ctypes import wintypes
import pytest

# 1. Verification of import from parasite_ai.input.types
from parasite_ai.input.types import (
    POINT,
    RECT,
    MSLLHOOKSTRUCT,
    KBDLLHOOKSTRUCT,
    MOUSEINPUT,
    KEYBDINPUT,
    HARDWAREINPUT,
    INPUT_UNION,
    INPUT,
    GUITHREADINFO,
)

# Also verify direct imports from authoritative runtime modules
from parasite_ai.safety.interrupt_guard import (
    POINT as POINT_IG,
    MSLLHOOKSTRUCT as MSLLHOOKSTRUCT_IG,
    KBDLLHOOKSTRUCT as KBDLLHOOKSTRUCT_IG,
    LLMHF_INJECTED,
    LLKHF_INJECTED,
)
from parasite_ai.safety.window_guard import RECT as RECT_WG
from parasite_ai.hands.keyboard import (
    MOUSEINPUT as MOUSEINPUT_KB,
    KEYBDINPUT as KEYBDINPUT_KB,
    HARDWAREINPUT as HARDWAREINPUT_KB,
    INPUT_UNION as INPUT_UNION_KB,
    INPUT as INPUT_KB,
)
from parasite_ai.mind.dual_mind import (
    GUITHREADINFO as GUITHREADINFO_DM,
    GUI_CARETBLINKING,
)

# Pydantic v2 Models
from parasite_ai.ui.types import UIElement, BoundingBox
from parasite_ai.mind.plan import PlanStep, LivingPlan, StepIntent, StepStatus, GroundedCapabilityContract
from parasite_ai.mind.memory import ActionPlan, ActionType, StepRecord, CadenceTier
from parasite_ai.config import AppConfig, BrainConfig


# ===========================================================================
# 1. Win32 Ctypes Structure Sizes (64-bit ABI)
# ===========================================================================

class TestWin32StructSizes64Bit:
    """Verifies ctypes.sizeof() matches 64-bit Windows ABI specifications (VERIF-9)."""

    def test_point_size(self):
        """POINT: 2x LONG (4 bytes each) = 8 bytes."""
        assert ctypes.sizeof(POINT) == 8
        assert ctypes.sizeof(POINT_IG) == 8

    def test_rect_size(self):
        """RECT: 4x LONG (4 bytes each) = 16 bytes."""
        assert ctypes.sizeof(RECT) == 16
        assert ctypes.sizeof(RECT_WG) == 16
        assert ctypes.sizeof(wintypes.RECT) == 16

    def test_msllhookstruct_size(self):
        """MSLLHOOKSTRUCT: POINT(8) + mouseData(4) + flags(4) + time(4) + pad(4) + dwExtraInfo(8) = 32 bytes."""
        assert ctypes.sizeof(MSLLHOOKSTRUCT) == 32
        assert ctypes.sizeof(MSLLHOOKSTRUCT_IG) == 32

    def test_kbdllhookstruct_size(self):
        """KBDLLHOOKSTRUCT: vkCode(4) + scanCode(4) + flags(4) + time(4) + dwExtraInfo(8) = 24 bytes."""
        assert ctypes.sizeof(KBDLLHOOKSTRUCT) == 24
        assert ctypes.sizeof(KBDLLHOOKSTRUCT_IG) == 24

    def test_mouseinput_size(self):
        """MOUSEINPUT: dx(4) + dy(4) + mouseData(4) + dwFlags(4) + time(4) + pad(4) + dwExtraInfo(8) = 32 bytes."""
        assert ctypes.sizeof(MOUSEINPUT) == 32
        assert ctypes.sizeof(MOUSEINPUT_KB) == 32

    def test_keybdinput_size(self):
        """KEYBDINPUT: wVk(2) + wScan(2) + dwFlags(4) + time(4) + pad(4) + dwExtraInfo(8) = 24 bytes."""
        assert ctypes.sizeof(KEYBDINPUT) == 24
        assert ctypes.sizeof(KEYBDINPUT_KB) == 24

    def test_hardwareinput_size(self):
        """HARDWAREINPUT: uMsg(4) + wParamL(2) + wParamH(2) = 8 bytes."""
        assert ctypes.sizeof(HARDWAREINPUT) == 8
        assert ctypes.sizeof(HARDWAREINPUT_KB) == 8

    def test_input_union_size(self):
        """INPUT_UNION: max(sizeof(mi)=32, sizeof(ki)=24, sizeof(hi)=8) = 32 bytes."""
        assert ctypes.sizeof(INPUT_UNION) == 32
        assert ctypes.sizeof(INPUT_UNION_KB) == 32

    def test_input_size(self):
        """INPUT: type(4) + pad(4) + u(32) = 40 bytes."""
        assert ctypes.sizeof(INPUT) == 40
        assert ctypes.sizeof(INPUT_KB) == 40

    def test_guithreadinfo_size(self):
        """GUITHREADINFO: cbSize(4) + flags(4) + 6x HWND(48) + rcCaret(16) = 72 bytes."""
        assert ctypes.sizeof(GUITHREADINFO) == 72
        assert ctypes.sizeof(GUITHREADINFO_DM) == 72


# ===========================================================================
# 2. Win32 Ctypes Field Offsets & Alignment (64-bit ABI)
# ===========================================================================

class TestWin32FieldOffsets64Bit:
    """Verifies field offsets match 64-bit Windows ABI alignment rules."""

    def test_point_field_offsets(self):
        assert POINT.x.offset == 0
        assert POINT.y.offset == 4

    def test_rect_field_offsets(self):
        assert RECT.left.offset == 0
        assert RECT.top.offset == 4
        assert RECT.right.offset == 8
        assert RECT.bottom.offset == 12

    def test_msllhookstruct_field_offsets(self):
        assert MSLLHOOKSTRUCT.pt.offset == 0
        assert MSLLHOOKSTRUCT.mouseData.offset == 8
        assert MSLLHOOKSTRUCT.flags.offset == 12
        assert MSLLHOOKSTRUCT.time.offset == 16
        # In 64-bit ABI, 8-byte dwExtraInfo is aligned to 8-byte boundary (offset 24)
        assert MSLLHOOKSTRUCT.dwExtraInfo.offset == 24

    def test_kbdllhookstruct_field_offsets(self):
        assert KBDLLHOOKSTRUCT.vkCode.offset == 0
        assert KBDLLHOOKSTRUCT.scanCode.offset == 4
        assert KBDLLHOOKSTRUCT.flags.offset == 8
        assert KBDLLHOOKSTRUCT.time.offset == 12
        # In 64-bit ABI, 8-byte dwExtraInfo starts at offset 16 (already 8-byte aligned)
        assert KBDLLHOOKSTRUCT.dwExtraInfo.offset == 16

    def test_mouseinput_field_offsets(self):
        assert MOUSEINPUT.dx.offset == 0
        assert MOUSEINPUT.dy.offset == 4
        assert MOUSEINPUT.mouseData.offset == 8
        assert MOUSEINPUT.dwFlags.offset == 12
        assert MOUSEINPUT.time.offset == 16
        # In 64-bit ABI, 8-byte dwExtraInfo is aligned to offset 24
        assert MOUSEINPUT.dwExtraInfo.offset == 24

    def test_keybdinput_field_offsets(self):
        assert KEYBDINPUT.wVk.offset == 0
        assert KEYBDINPUT.wScan.offset == 2
        assert KEYBDINPUT.dwFlags.offset == 4
        assert KEYBDINPUT.time.offset == 8
        # In 64-bit ABI, 8-byte dwExtraInfo is aligned to offset 16
        assert KEYBDINPUT.dwExtraInfo.offset == 16

    def test_hardwareinput_field_offsets(self):
        assert HARDWAREINPUT.uMsg.offset == 0
        assert HARDWAREINPUT.wParamL.offset == 4
        assert HARDWAREINPUT.wParamH.offset == 6

    def test_input_union_field_offsets(self):
        # Union fields all overlap at offset 0
        assert INPUT_UNION.mi.offset == 0
        assert INPUT_UNION.ki.offset == 0
        assert INPUT_UNION.hi.offset == 0

    def test_input_field_offsets(self):
        assert INPUT.type.offset == 0
        # In 64-bit ABI, union 'u' requires 8-byte alignment, placing it at offset 8 (4 bytes padding)
        assert INPUT.u.offset == 8

    def test_guithreadinfo_field_offsets(self):
        assert GUITHREADINFO.cbSize.offset == 0
        assert GUITHREADINFO.flags.offset == 4
        assert GUITHREADINFO.hwndActive.offset == 8
        assert GUITHREADINFO.hwndFocus.offset == 16
        assert GUITHREADINFO.hwndCapture.offset == 24
        assert GUITHREADINFO.hwndMenuOwner.offset == 32
        assert GUITHREADINFO.hwndMoveSize.offset == 40
        assert GUITHREADINFO.hwndCaret.offset == 48
        assert GUITHREADINFO.rcCaret.offset == 56


# ===========================================================================
# 3. Critical Win32 Constants & Bitmasks
# ===========================================================================

class TestWin32Constants:
    """Verifies critical hook bitmasks and constants match Windows specifications."""

    def test_mouse_ll_hook_injected_bitmask(self):
        assert LLMHF_INJECTED == 0x00000001

    def test_keyboard_ll_hook_injected_bitmask(self):
        assert LLKHF_INJECTED == 0x00000010

    def test_gui_caret_blinking_constant(self):
        assert GUI_CARETBLINKING == 0x00000001


# ===========================================================================
# 4. Pydantic v2 Models Schema Mapping (Master Plan §9.1)
# ===========================================================================

class TestPydanticV2SchemaMapping:
    """Verifies Pydantic v2 models instantiate and validate required schemas."""

    def test_ui_element_schema(self):
        elem = UIElement(
            id=1,
            role="Button",
            label="OK",
            x=100,
            y=200,
            width=80,
            height=30,
            center_x=140,
            center_y=215,
            source="uia",
            is_active_window=True,
        )
        assert elem.id == 1
        assert elem.bbox == (100, 200, 80, 30)
        assert elem.center == (140, 215)
        assert elem.control_type == "Button"
        padded = elem.pad(padding_px=10)
        assert isinstance(padded, BoundingBox)
        assert padded.x == 90
        assert padded.y == 190
        assert padded.width == 100
        assert padded.height == 50

    def test_bounding_box_schema(self):
        bbox = BoundingBox(x=50, y=50, width=100, height=100)
        padded = bbox.pad(padding_px=20, bounds=(0, 0, 1920, 1080))
        assert padded.as_tuple() == (30, 30, 140, 140)

    def test_plan_step_schema(self):
        step = PlanStep(
            step_id=1,
            intent=StepIntent.LAUNCH_OR_ACTIVATE,
            description="Launch Notepad",
            target_description="Notepad",
            success_criteria="Notepad window appears",
            tool_route="GUI",
        )
        assert step.step_id == 1
        assert step.intent == StepIntent.LAUNCH_OR_ACTIVATE
        assert step.status == StepStatus.PENDING
        assert step.tool_route == "GUI"

    def test_living_plan_schema(self):
        plan = LivingPlan(
            user_goal="Edit text document",
            overall_strategy="Launch and type",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.LAUNCH_OR_ACTIVATE,
                    description="Open Notepad",
                    success_criteria="Window active",
                ),
                PlanStep(
                    step_id=2,
                    intent=StepIntent.INPUT_DATA,
                    description="Type greeting",
                    success_criteria="Text visible",
                ),
            ],
            current_step_id=1,
            escalation_tier=CadenceTier.TIER_1_LOCAL,
            tier_strikes=0,
        )
        assert plan.get_current_step().step_id == 1
        adv = plan.advance_step()
        assert adv is not None
        assert adv.step_id == 2
        assert plan.current_step_id == 2
        assert not plan.is_completed()

    def test_action_plan_schema(self):
        action = ActionPlan(
            action=ActionType.CLICK,
            target_id=5,
            coordinates=(250, 400),
            wait_ms=250,
            reasoning="Click confirm button",
        )
        assert action.action == ActionType.CLICK
        assert action.coordinates == (250, 400)

        cli_action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command="pytest tests/ -q",
            reasoning="Run automated tests",
        )
        assert cli_action.action == ActionType.RUN_CLI_COMMAND
        assert cli_action.cli_command == "pytest tests/ -q"

    def test_step_record_schema(self):
        action = ActionPlan(action=ActionType.WAIT, wait_ms=500)
        rec = StepRecord(
            step_id=1,
            user_goal="Wait for settling",
            action=action,
            screen_diff=0.03,
            success=True,
            tier_level=CadenceTier.TIER_1_LOCAL,
        )
        assert rec.step_id == 1
        assert rec.screen_diff == 0.03
        assert rec.success is True

    def test_brain_config_default_mode_invariant(self):
        """Zero silent cloud exfiltration invariant: BrainConfig.mode defaults to 'local_llm'."""
        cfg = BrainConfig()
        assert cfg.mode == "local_llm", (
            f"Zero silent cloud exfiltration violation: expected 'local_llm', got '{cfg.mode}'"
        )
