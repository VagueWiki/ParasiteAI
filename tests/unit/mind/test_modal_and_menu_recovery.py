"""
tests/unit/mind/test_modal_and_menu_recovery.py

Unit tests for Stint P2.5.3:
1. Normalization of Escape/Return/Space aliases in uitars_parser.py
2. Positional and keyword hotkey calls
3. Modal dialog and stray menu prompt rules in UITARS_SYSTEM_PROMPT
4. Modal dialog (#32770) focus preservation in ActionDispatcher
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT, parse_uitars_action
from parasite_ai.mind.dual_mind import ActionDispatcher


class TestModalAndMenuRecoveryParser(unittest.TestCase):
    """Tests key alias normalization and argument parsing for menu and dialog recovery."""

    def test_escape_key_normalization_various_forms(self) -> None:
        raw_outputs = [
            "Thought: Stray menu open.\nAction: hotkey(key='Escape')",
            "Thought: Stray menu open.\nAction: hotkey(key='escape')",
            "Thought: Stray menu open.\nAction: hotkey(key='ESC')",
            "Thought: Stray menu open.\nAction: press(key='Escape')",
            "Thought: Stray menu open.\nAction: press(key='esc')",
            "Thought: Stray menu open.\nAction: hotkey('escape')",
            "Thought: Stray menu open.\nAction: press('Escape')",
        ]
        for raw in raw_outputs:
            with self.subTest(raw=raw):
                thought, plan = parse_uitars_action(raw)
                self.assertEqual(plan.action, ActionType.HOTKEY)
                self.assertEqual(plan.keys, ["esc"])

    def test_enter_and_return_key_normalization(self) -> None:
        raw_outputs = [
            "Thought: Confirm dialog.\nAction: hotkey(key='Return')",
            "Thought: Confirm dialog.\nAction: press(key='return')",
            "Thought: Confirm dialog.\nAction: hotkey(key='Enter')",
            "Thought: Confirm dialog.\nAction: press(key='enter')",
            "Thought: Confirm dialog.\nAction: press('Return')",
        ]
        for raw in raw_outputs:
            with self.subTest(raw=raw):
                thought, plan = parse_uitars_action(raw)
                self.assertEqual(plan.action, ActionType.HOTKEY)
                self.assertEqual(plan.keys, ["enter"])

    def test_space_key_normalization(self) -> None:
        thought, plan = parse_uitars_action("Thought: Toggle checkbox.\nAction: press(key='Space')")
        self.assertEqual(plan.action, ActionType.HOTKEY)
        self.assertEqual(plan.keys, ["space"])

    def test_multi_key_combination_with_aliases(self) -> None:
        thought, plan = parse_uitars_action("Thought: Cancel with combo.\nAction: hotkey(key='ctrl+escape')")
        self.assertEqual(plan.action, ActionType.HOTKEY)
        self.assertEqual(plan.keys, ["ctrl", "esc"])

    def test_prompt_contains_stray_menu_and_modal_directives(self) -> None:
        """Verifies UITARS_SYSTEM_PROMPT contains stray menu and modal dialog recovery rules."""
        self.assertIn("STRAY MENU & POPUP RECOVERY", UITARS_SYSTEM_PROMPT)
        self.assertIn("hotkey(key='esc')", UITARS_SYSTEM_PROMPT)
        self.assertIn("MODAL DIALOGS & CONFIRMATION PROMPTS", UITARS_SYSTEM_PROMPT)
        self.assertIn("MUST interact with the modal dialog FIRST", UITARS_SYSTEM_PROMPT)


class TestActionDispatcherModalAwareness(unittest.TestCase):
    """Tests ActionDispatcher modal dialog (#32770) detection and focus handling."""

    @patch("sys.platform", "win32")
    def test_modal_dialog_preserves_dialog_focus(self) -> None:
        dispatcher = ActionDispatcher()

        mock_user32 = MagicMock()
        mock_user32.WindowFromPoint.return_value = 1001  # Parent editor HWND
        mock_user32.GetAncestor.return_value = 1001
        mock_user32.IsWindow.return_value = True

        # Active foreground window is HWND 2002 which is a modal dialog (#32770)
        mock_user32.GetForegroundWindow.return_value = 2002

        def fake_get_class_name(hwnd, buf, max_len):
            if hwnd == 2002:
                buf.value = "#32770"
            else:
                buf.value = "Notepad"
            return len(buf.value)

        mock_user32.GetClassNameW.side_effect = fake_get_class_name

        with patch("ctypes.windll.user32", mock_user32):
            result = dispatcher._activate_target_window_if_needed(coords=(400, 300))
            self.assertTrue(result)
            # Should NOT attempt to force SetForegroundWindow on the background parent (1001)
            mock_user32.SetForegroundWindow.assert_not_called()
            mock_user32.ShowWindow.assert_not_called()


class TestPreDispatchLoopBreaker(unittest.TestCase):
    """Tests CUA pre-dispatch loop breaking for repetitive typing and double-click clusters."""

    def test_repetitive_typing_loop_breaker_converts_to_enter(self) -> None:
        """Verifies that typing the exact same text across consecutive steps converts to Enter hotkey."""
        from parasite_ai.mind.dual_mind import DualMindPipeline, ActionResult
        import numpy as np

        mock_brain = MagicMock()
        mock_brain.supports_vision.return_value = True
        planned_act = ActionPlan(action=ActionType.TYPE, text="Calculator", reasoning="Type Calculator")
        mock_brain.generate_cua_step.return_value = ("Typing Calculator", planned_act)

        pipeline = DualMindPipeline(brain_manager=mock_brain)
        dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Record step 1: typed Calculator
        pipeline.memory.record_step(
            action=ActionPlan(action=ActionType.TYPE, text="Calculator"),
            screen_diff=0.05,
            success=True,
            persona_thought="Step 1 typing",
        )

        with patch.object(
            pipeline.action_dispatcher,
            "dispatch",
            return_value=ActionResult(success=True, action_executed=planned_act),
        ) as mock_dispatch:
            step_rec = pipeline.step(
                user_goal="Launch Calculator",
                screen_frame=dummy_frame,
            )

        # Step 2 should have converted the repeated typing into Enter hotkey
        self.assertEqual(step_rec.action.action, ActionType.HOTKEY)
        self.assertEqual(step_rec.action.keys, ["enter"])

    def test_desktop_double_click_loop_breaker_converts_to_enter(self) -> None:
        """Verifies that consecutive double clicks within 24px on desktop convert to Enter hotkey."""
        from parasite_ai.mind.dual_mind import DualMindPipeline, ActionResult
        from types import SimpleNamespace
        import numpy as np

        mock_brain = MagicMock()
        mock_brain.supports_vision.return_value = True
        planned_act = ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(30, 893), reasoning="Double click icon")
        mock_brain.generate_cua_step.return_value = ("Double clicking icon", planned_act)

        pipeline = DualMindPipeline(brain_manager=mock_brain)
        dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Record step 1: double-clicked at (38, 905) (within 24px of (30, 893))
        pipeline.memory.record_step(
            action=ActionPlan(action=ActionType.DOUBLE_CLICK, coordinates=(38, 905)),
            screen_diff=0.5,
            success=True,
            persona_thought="Step 1 double click",
        )

        # Mock effective window as desktop surface
        with patch.object(
            pipeline,
            "_get_effective_active_window",
            return_value=SimpleNamespace(process_name="explorer.exe", title="Desktop", rect=(0, 0, 1920, 1080)),
        ), patch.object(
            pipeline.action_dispatcher,
            "dispatch",
            return_value=ActionResult(success=True, action_executed=planned_act),
        ):
            step_rec = pipeline.step(
                user_goal="Open Chrome",
                screen_frame=dummy_frame,
            )

        # Step 2 should have converted repeated double click to Enter hotkey to launch selected item
        self.assertEqual(step_rec.action.action, ActionType.HOTKEY)
        self.assertEqual(step_rec.action.keys, ["enter"])


if __name__ == "__main__":
    unittest.main()
