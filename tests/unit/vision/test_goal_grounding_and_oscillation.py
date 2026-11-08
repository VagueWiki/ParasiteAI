import pytest
import numpy as np
from unittest.mock import MagicMock
from parasite_ai.config import VisionConfig
from parasite_ai.vision.grounding import ScreenGrounder, RawElement
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.dual_mind import DualMindPipeline, ActionResult
from parasite_ai.ui.types import UIElement


def test_goal_relevance_prioritizes_background_target():
    """Verify that an element matching the goal keyword is ranked at index #1 even if not active window."""
    config = VisionConfig(max_som_elements=10)
    grounder = ScreenGrounder(config=config)

    raw = [
        RawElement(x=10, y=10, width=50, height=20, center_x=35, center_y=20, role="Button", label="Active Win Button 1", source="uia", is_active_window=True),
        RawElement(x=10, y=40, width=50, height=20, center_x=35, center_y=50, role="Button", label="Active Win Button 2", source="uia", is_active_window=True),
        RawElement(x=500, y=500, width=40, height=40, center_x=520, center_y=520, role="ListItem", label="RimWorld", source="uia", is_active_window=False),
    ]

    # Without goal keywords: active window elements are first
    elements_default = grounder._normalize_elements(raw)
    assert elements_default[0].label == "Active Win Button 1"

    # With goal keywords "rimworld": RimWorld is prioritized to index #1
    elements_prioritized = grounder._normalize_elements(raw, goal_keywords=["rimworld"])
    assert elements_prioritized[0].label == "RimWorld"
    assert elements_prioritized[0].id == 1


def test_element_paging_offset():
    """Verify offset parameter allows cycling to the next batch of elements."""
    config = VisionConfig(max_som_elements=5)
    grounder = ScreenGrounder(config=config)

    raw = [
        RawElement(x=10, y=10, width=20, height=20, center_x=20, center_y=20, role="Button", label="Elem 1", source="uia"),
        RawElement(x=10, y=40, width=20, height=20, center_x=20, center_y=50, role="Button", label="Elem 2", source="uia"),
        RawElement(x=10, y=70, width=20, height=20, center_x=20, center_y=80, role="Button", label="Elem 3", source="uia"),
        RawElement(x=10, y=100, width=20, height=20, center_x=20, center_y=110, role="Button", label="Elem 4", source="uia"),
    ]

    batch1 = grounder._normalize_elements(raw, offset=0)
    assert len(batch1) == 4
    assert batch1[0].label == "Elem 1"

    batch2 = grounder._normalize_elements(raw, offset=2)
    assert len(batch2) == 2
    assert batch2[0].label == "Elem 3"
    assert batch2[1].label == "Elem 4"


def test_toggle_oscillation_detection():
    """Verify that repeatedly clicking the same target element triggers an oscillation strike."""
    memory = EpisodicMemory(capacity=10)
    brain = MagicMock()
    pipeline = DualMindPipeline(brain_manager=brain, memory=memory)

    mock_driver = MagicMock()
    mock_driver.click.return_value = True
    pipeline.mouse_driver = mock_driver

    frame1 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 100

    mock_capturer = MagicMock()
    mock_capturer.capture_screen.return_value = frame2
    pipeline.capturer = mock_capturer

    plan = ActionPlan(action=ActionType.CLICK, target_id=5, reasoning="Click More")
    som = [
        UIElement(id=5, role="Button", label="More", x=100, y=100, width=50, height=20, center_x=125, center_y=110, source="uia")
    ]

    # Step 1: Click target #5 (Diff is large, first click -> no strike)
    pipeline.step(user_goal="Search", screen_frame=frame1, grounded_elements=som, override_action=plan)
    assert pipeline.escalation_sm.current_strikes == 0

    # Step 2: Click target #5 again (Diff is large, 2nd click -> no strike yet)
    mock_capturer.capture_screen.return_value = frame1
    pipeline.step(user_goal="Search", screen_frame=frame2, grounded_elements=som, override_action=plan)
    assert pipeline.escalation_sm.current_strikes == 0

    # Step 3: Click target #5 a 3rd time (oscillation detected!) -> registers failure strike despite visual diff
    mock_capturer.capture_screen.return_value = frame2
    pipeline.step(user_goal="Search", screen_frame=frame1, grounded_elements=som, override_action=plan)
    assert pipeline.escalation_sm.current_strikes == 1
