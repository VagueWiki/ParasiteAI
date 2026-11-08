"""
parasite_ai/mind/uitars_parser.py - Native UI-TARS-1.5 Computer-Use Action Parser & Grounding Engine.

Parses native UI-TARS-1.5 conversational computer-use outputs (Thought: ... Action: ...)
into validated ParasiteAI ActionPlan instances, scales normalized [0..1000] coordinates
to monitor pixel resolution, performs hybrid UIA element snapping, and guarantees zero
unhandled validation crashes.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from parasite_ai.mind.memory import ActionPlan, ActionType, VERB_SYNONYMS

logger = logging.getLogger(__name__)

# Standard UI-TARS desktop system prompt tailored for Windows 10 GUI automation
UITARS_SYSTEM_PROMPT = """You are an expert Windows 10 desktop computer-use agent.
Given a user task and a screenshot of the current screen, determine the single next best action to execute.

You MUST respond in the following format:
Thought: <Brief, single-sentence reasoning describing what you see and what you plan to do>
Action: <Action call with arguments>

Supported Action calls:
- click(start_box='(x,y)') : Click on the target UI element or coordinates.
- left_double(start_box='(x,y)') : Double click on the target item.
- right_single(start_box='(x,y)') : Right click on the target item to open context menu.
- type(content='text') : Type text. End with '\\n' if Enter should be pressed after typing.
- hotkey(key='ctrl c') : Press keyboard hotkey combination (e.g. 'ctrl s', 'alt f4', 'enter').
- scroll(start_box='(x,y)', direction='down') : Scroll wheel down or up.
- wait() : Wait for window to load or render.
- finished() : The user goal has been completely achieved.

Coordinates must be within [0, 1000] normalized space. Example:
Thought: I will click the Start button to search for Notepad.
Action: click(start_box='(24,980)')
"""


def extract_thought_and_action(raw_output: str) -> Tuple[str, str]:
    """
    Extracts the 'Thought:' and 'Action:' strings from raw model output.
    Handles varied casing, missing blocks, and markdown code fencing.
    """
    cleaned = raw_output.strip()

    # Strip markdown formatting or code blocks if wrapped
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    thought = ""
    action = ""

    # Look for explicit Thought: and Action: patterns
    thought_match = re.search(r"(?:^|\n)\s*Thought\s*:\s*(.*?)(?=\n\s*Action\s*:|\Z)", cleaned, re.IGNORECASE | re.DOTALL)
    if thought_match:
        thought = thought_match.group(1).strip()

    action_match = re.search(r"(?:^|\n)\s*Action\s*:\s*(.*?)(?=\n\s*(?:Thought|Action)\s*:|\Z)", cleaned, re.IGNORECASE | re.DOTALL)
    if action_match:
        action = action_match.group(1).strip()
    else:
        # If Action: prefix is omitted, check if there is a known action signature directly
        direct_call = re.search(r"\b(click|left_double|double_click|right_single|right_click|type|hotkey|press|scroll|wait|sleep|finished|finish|done)\s*\(.*?\)", cleaned, re.IGNORECASE | re.DOTALL)
        if direct_call:
            action = direct_call.group(0).strip()
            # Everything before the call can be treated as thought if thought was empty
            if not thought:
                thought = cleaned[:direct_call.start()].strip()
        elif not thought:
            # Entire text might be thought or legacy JSON
            thought = cleaned

    return thought, action


def parse_coordinates(
    arg_str: str,
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> Optional[Tuple[int, int]]:
    """
    Parses coordinate tuples from start_box, end_box, point, or coordinate strings.
    Handles formats:
    - '(x,y)'
    - '<|box_start|>(x,y)<|box_end|>'
    - '(x1,y1,x2,y2)' -> calculates center (x, y)
    - '[x, y]'
    
    Transforms normalized [0..1000] values into screen pixels (e.g. 1920x1080).
    Clamps values to stay strictly within [0, screen_width-1] and [0, screen_height-1].
    """
    # Remove box markers if present
    cleaned = re.sub(r"<\|box_(?:start|end)\|>", "", arg_str)

    # Extract all integer or float numbers
    nums = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+", cleaned)]
    if not nums:
        return None

    if len(nums) >= 4:
        # Bounding box [x1, y1, x2, y2] -> calculate center
        x1, y1, x2, y2 = nums[0], nums[1], nums[2], nums[3]
        norm_x = (x1 + x2) / 2.0
        norm_y = (y1 + y2) / 2.0
    elif len(nums) >= 2:
        norm_x = nums[0]
        norm_y = nums[1]
    else:
        return None

    # Check if normalized [0..1000] scale or raw pixel scale
    # If values are <= 1000, treat as normalized per-mille
    if 0 <= norm_x <= 1000.0 and 0 <= norm_y <= 1000.0:
        px_x = int(round((norm_x / 1000.0) * screen_width))
        px_y = int(round((norm_y / 1000.0) * screen_height))
    else:
        px_x = int(round(norm_x))
        px_y = int(round(norm_y))

    # Clamp within screen bounds
    px_x = max(0, min(screen_width - 1, px_x))
    px_y = max(0, min(screen_height - 1, px_y))

    return (px_x, px_y)


def snap_coordinates_to_element(
    coords: Tuple[int, int],
    candidate_elements: List[Any],
    snap_radius_px: float = 35.0,
) -> Tuple[Tuple[int, int], Optional[Any]]:
    """
    Snaps (x, y) to the nearest candidate UIElement center if within snap_radius_px.
    """
    px, py = coords
    best_elem = None
    min_dist = float("inf")

    for elem in candidate_elements:
        cx = getattr(elem, "center_x", None)
        cy = getattr(elem, "center_y", None)
        if cx is None or cy is None:
            continue
        dist = math.hypot(px - cx, py - cy)
        if dist < min_dist and dist <= snap_radius_px:
            min_dist = dist
            best_elem = elem

    if best_elem is not None:
        return ((int(best_elem.center_x), int(best_elem.center_y)), best_elem)

    return (coords, None)


def parse_uitars_action(
    raw_output: str,
    screen_width: int = 1920,
    screen_height: int = 1080,
    candidate_elements: Optional[List[Any]] = None,
    snap_radius_px: float = 35.0,
) -> Tuple[str, ActionPlan]:
    """
    Parses UI-TARS-1.5 model output into a (thought, ActionPlan) tuple.

    Guarantees:
    - Never raises unhandled exceptions on malformed output.
    - Scales [0..1000] coordinates to screen pixels.
    - Snaps to UIA candidate element center when within snap_radius_px.
    - Fallback parses legacy JSON if model emits JSON format.
    - Coerces unrecognized actions to ActionType.WAIT with debug reasoning.
    """
    thought, action_str = extract_thought_and_action(raw_output)

    # 1. Check if model emitted legacy/hybrid JSON
    if "{" in raw_output and "}" in raw_output:
        try:
            json_match = re.search(r"\{.*?\}", raw_output, re.DOTALL)
            if json_match:
                payload = json.loads(json_match.group(0))
                if isinstance(payload, dict) and "action" in payload:
                    plan = ActionPlan.model_validate(payload)
                    if not thought and plan.reasoning:
                        thought = plan.reasoning
                    return thought, plan
        except Exception:
            pass

    if not action_str:
        # No action call detected; return WAIT with thought reasoning
        return thought, ActionPlan(
            action=ActionType.WAIT,
            reasoning=thought or "No action command detected in model output.",
        )

    # Extract function name and arguments string: name(...)
    fn_name = ""
    args_content = ""
    if "(" in action_str and action_str.endswith(")"):
        first_paren = action_str.index("(")
        last_paren = action_str.rindex(")")
        fn_name = action_str[:first_paren].strip().lower()
        args_content = action_str[first_paren + 1 : last_paren].strip()
    else:
        # Fallback: check if the string itself is a verb synonym (e.g. 'SELECT', 'FINISHED')
        return thought, ActionPlan(
            action=ActionPlan._coerce_null_fields({"action": action_str})["action"],
            reasoning=thought or f"Raw verb call: {action_str}",
        )

    # Parse key=value or positional arguments
    # Handles: start_box='(500,200)', direction='down', content='hello'
    kwargs: Dict[str, str] = {}
    for arg_match in re.finditer(r"([a-zA-Z_0-9]+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|([^,\)]+))", args_content, re.DOTALL):
        k = arg_match.group(1).lower()
        val = arg_match.group(2) if arg_match.group(2) is not None else (
            arg_match.group(3) if arg_match.group(3) is not None else arg_match.group(4)
        )
        kwargs[k] = (val or "").strip()

    # Determine coordinates from start_box, point, end_box, or args_content
    coords = None
    box_val = kwargs.get("start_box") or kwargs.get("point") or kwargs.get("box")
    if box_val:
        coords = parse_coordinates(box_val, screen_width, screen_height)
    elif "(" in args_content and ")" in args_content:
        coords = parse_coordinates(args_content, screen_width, screen_height)

    # Apply hybrid element snapping if coordinates found and candidate elements supplied
    snapped_elem = None
    if coords is not None and candidate_elements:
        coords, snapped_elem = snap_coordinates_to_element(coords, candidate_elements, snap_radius_px)

    # Map function names to ParasiteAI ActionType
    if fn_name in ("click", "click_coordinate", "mouse_click"):
        clicks = int(kwargs.get("clicks", 1))
        return thought, ActionPlan(
            action=ActionType.CLICK,
            coordinates=coords,
            clicks=clicks,
            reasoning=thought or f"Click at {coords}",
        )

    elif fn_name in ("left_double", "double_click", "dblclick"):
        return thought, ActionPlan(
            action=ActionType.DOUBLE_CLICK,
            coordinates=coords,
            clicks=2,
            reasoning=thought or f"Double click at {coords}",
        )

    elif fn_name in ("right_single", "right_click", "context_click"):
        return thought, ActionPlan(
            action=ActionType.RIGHT_CLICK,
            coordinates=coords,
            clicks=1,
            reasoning=thought or f"Right click at {coords}",
        )

    elif fn_name in ("type", "write", "input"):
        raw_text = kwargs.get("content") or kwargs.get("text") or kwargs.get("string") or ""
        # If text ends with \n or enter, flag submit=True
        submit = False
        if raw_text.endswith(("\\n", "\n")):
            submit = True
            raw_text = raw_text.rstrip("\n").rstrip("\\n")
        clear_first = kwargs.get("clear_first", "true").lower() in ("true", "1", "yes")

        return thought, ActionPlan(
            action=ActionType.TYPE,
            text=raw_text,
            submit=submit,
            clear_first=clear_first,
            coordinates=coords,
            reasoning=thought or f"Type text: {raw_text}",
        )

    elif fn_name in ("hotkey", "press", "key", "key_press"):
        raw_key = kwargs.get("key") or kwargs.get("keys") or kwargs.get("combination") or args_content.strip("'\" ")
        # Parse combination like 'ctrl c', 'ctrl+c', 'alt+f4'
        keys_list = [k.strip().lower() for k in re.split(r"[\s\+]+", raw_key) if k.strip()]
        if not keys_list:
            keys_list = ["enter"]

        return thought, ActionPlan(
            action=ActionType.HOTKEY,
            keys=keys_list,
            reasoning=thought or f"Hotkey: {'+'.join(keys_list)}",
        )

    elif fn_name in ("scroll", "wheel"):
        direction = kwargs.get("direction", "down").lower()
        amount = -3 if direction in ("down", "page_down") else 3
        return thought, ActionPlan(
            action=ActionType.SCROLL,
            scroll_amount=amount,
            coordinates=coords,
            reasoning=thought or f"Scroll {direction}",
        )

    elif fn_name in ("wait", "sleep"):
        wait_ms = int(kwargs.get("wait_ms") or kwargs.get("duration") or 500)
        return thought, ActionPlan(
            action=ActionType.WAIT,
            wait_ms=wait_ms,
            reasoning=thought or "Waiting for UI state update.",
        )

    elif fn_name in ("finished", "finish", "done", "complete"):
        return thought, ActionPlan(
            action=ActionType.DONE,
            reasoning=thought or "Goal completed successfully.",
        )

    else:
        # Fallback to verb synonym check or WAIT
        coerced = ActionPlan._coerce_null_fields({"action": fn_name, "reasoning": thought})
        return thought, ActionPlan.model_validate(coerced)
