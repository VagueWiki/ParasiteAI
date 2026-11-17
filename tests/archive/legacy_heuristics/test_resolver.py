"""
tests/test_resolver.py - Unit Tests for Universal Application Resolver.

Verifies:
1. Target application extraction from diverse natural language goals without hardcoding.
2. Tier 1 Set-of-Mark icon/window detection and direct clicking.
3. Active Windows Run dialog typing and submission.
4. Active Windows Start Search typing and submission.
5. Multi-stage chord triggering (Win key -> Type name -> Enter).
6. Generic resolution across arbitrary third-party application names.
"""

from __future__ import annotations

import pytest
from parasite_ai.mind.memory import ActionType
from parasite_ai.mind.resolver import UniversalAppResolver
from parasite_ai.ui.types import UIElement


def test_extract_target_app() -> None:
    # Verifies extraction across diverse phrasings and arbitrary app names
    assert UniversalAppResolver.extract_target_app("open notepad and then write yourself an introduction") == "notepad"
    assert UniversalAppResolver.extract_target_app("launch visual studio code and create a file") == "visual studio code"
    assert UniversalAppResolver.extract_target_app("start Spotify please") == "Spotify"
    assert UniversalAppResolver.extract_target_app("run powershell") == "powershell"
    assert UniversalAppResolver.extract_target_app("switch to Discord") == "Discord"
    assert UniversalAppResolver.extract_target_app("open up Chrome to google.com") == "Chrome"
    assert UniversalAppResolver.extract_target_app("bring up ArbitraryCustomTool_v2") == "ArbitraryCustomTool_v2"
    assert UniversalAppResolver.extract_target_app("just click on the screen") is None


def test_tier1_visible_element_match() -> None:
    resolver = UniversalAppResolver()
    elements = [
        UIElement.from_bbox(1, (10, 10, 50, 50), label="Recycle Bin", role="ListItem"),
        UIElement.from_bbox(2, (10, 80, 50, 50), label="ArbitraryPlayer", role="ListItem"),
        UIElement.from_bbox(3, (100, 1050, 40, 30), label="ArbitraryApp", role="Button"),
    ]

    action = resolver.resolve_launch_action("arbitraryapp", elements)
    assert action.action == ActionType.CLICK
    assert action.target_id == 3
    assert "Found visible" in (action.reasoning or "")


def test_run_dialog_active() -> None:
    resolver = UniversalAppResolver()
    elements = [
        UIElement.from_bbox(1, (500, 500, 300, 30), label="Open:", role="Edit"),
    ]

    action = resolver.resolve_launch_action("some_custom_utility", elements)
    assert action.action == ActionType.CLICK_AND_TYPE
    assert action.target_id == 1
    assert action.text == "some_custom_utility"
    assert action.submit is True


def test_start_search_box_active() -> None:
    resolver = UniversalAppResolver()
    elements = [
        UIElement.from_bbox(1, (100, 950, 400, 40), label="Type here to search", role="Edit"),
    ]

    action = resolver.resolve_launch_action("blender", elements)
    assert action.action == ActionType.CLICK_AND_TYPE
    assert action.target_id == 1
    assert "blender" in (action.text or "")
    assert action.submit is True


def test_tier2_start_chord_sequence() -> None:
    resolver = UniversalAppResolver()
    elements: list[UIElement] = []

    # First step: Trigger Start Search via Win key
    action1 = resolver.resolve_launch_action("davinci resolve", elements)
    assert action1.action == ActionType.HOTKEY
    assert action1.keys == ["win"]

    # Second step: Start search is now active -> types application name and presses Enter
    action2 = resolver.resolve_launch_action("davinci resolve", elements)
    assert action2.action == ActionType.TYPE
    assert "davinci resolve\n" in (action2.text or "")
    assert action2.submit is True
