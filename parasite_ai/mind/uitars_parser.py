"""
parasite_ai/mind/uitars_parser.py - Native UI-TARS-1.5 Computer-Use Action Parser & Grounding Engine.

Parses native UI-TARS-1.5 conversational computer-use outputs (Thought: ... Action: ...)
into validated ParasiteAI ActionPlan instances, extracts native screen pixel coordinates
for monitor pixel resolution, performs hybrid UIA element snapping, and guarantees zero
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
Keep your Thought concise (1-2 sentences maximum), then emit exactly one Action.

You MUST respond in the following format:
Thought: <Brief, single-sentence reasoning describing what you see and what you plan to do>
Action: <Action call with arguments>

Supported Action calls:
- click(start_box='(x,y)') : Click on the target UI element or coordinates.
- left_double(start_box='(x,y)') : Double click on the target item.
- right_single(start_box='(x,y)') : Right click on the target item to open context menu.
- drag(start_box='(x1,y1)', end_box='(x2,y2)') : Press left button at start_box, drag to end_box, and release.
- type(content='text') : Type text into currently active/focused control or document. End with '\\n' if Enter should be pressed after typing.
- hotkey(key='ctrl c') : Press keyboard hotkey combination (e.g. 'ctrl s', 'alt f4', 'win r', 'enter').
- scroll(start_box='(x,y)', direction='down') : Scroll wheel down or up.
- wait() : Wait for window to load or render.
- burst([action1, action2, ...]) : Rapid compound burst of micro-actions (clicks, keys, types) executed together.
- finished() : The user goal has been completely achieved.

Coordinates must be exact screen pixels: (x, y) where (0, 0) is top-left and (1920, 1080) is bottom-right.
Derive all coordinates dynamically from the visual layout in the CURRENT screenshot.
Example action syntax (illustration only; never copy placeholder values):
Thought: <Brief, single-sentence observation of target element and planned action>
Action: left_double(start_box='(x, y)')
Thought: <Brief, single-sentence observation and keyboard shortcut action>
Action: hotkey(key='<keys>')
Thought: <Brief, single-sentence observation and text entry action>
Action: type(content='<text>\\n')
Thought: <Brief, single-sentence observation and multi-step sequence action>
Action: burst([click(start_box='(x1, y1)'), click(start_box='(x2, y2)')])

Important Rules:
- Derive all coordinates dynamically from what is visible in the current screenshot. Never use canned or guessed coordinates.
- Never type text onto the bare desktop background expecting Windows Search. If the desktop has focus, press hotkey(key='win') or click the taskbar Search icon first before typing!
- If the Start Menu, a context menu, or a dropdown is ALREADY open on screen, NAVIGATE INSIDE IT. Look at the items, icons, and search inputs visible inside the open menu and click or type into them. NEVER click the Start button or menu trigger button again while the menu is open, as clicking it a second time toggles the menu closed!
- Inside an open menu, if you do not immediately see the target item, type the name of the application to search and filter the menu dynamically.
- STRAY MENU & POPUP RECOVERY: If an unwanted context menu, right-click flyout, or dropdown is open and occluding the workspace or target, dismiss it immediately by pressing Escape:
    Thought: An unwanted menu is blocking the screen, I will dismiss it with Escape.
    Action: hotkey(key='esc')
  Never try to click around, behind, or through an open context menu.
- MODAL DIALOGS & CONFIRMATION PROMPTS: When a dialog box or confirmation prompt appears (e.g. 'Save As', 'Do you want to save?', 'Confirm Save As', 'File already exists', error dialog):
    1. You MUST interact with the modal dialog FIRST. The background application window is disabled until the dialog is closed.
    2. Click the intended dialog button (e.g. 'Save', 'Don't Save', 'Yes', 'OK', 'Cancel', 'Replace') or press Enter / Escape.
    3. Do NOT attempt to click the main application editor, ribbon, or menu bar while a modal dialog is open.
    4. In a 'Save As' dialog, focus the 'File name:' input (e.g. hotkey(key='alt n') or clicking the 'File name:' box) and type the full target path with '\\n' (e.g. type(content='<full_path>\\n')) rather than double-clicking sidebar folders.
- INLINE RENAMES & PROFILE PICKERS: When renaming a file or editing an inline text box, end with '\\n' (or press 'enter') to commit the change. If a browser profile chooser (e.g. 'Who\'s using Chrome?') appears on launch, click the active profile card to enter the browser.
- TEXT SELECTION & CLIPBOARD: Once target text is highlighted, immediately copy it with hotkey(key='ctrl c') (or select all and copy via burst([hotkey(key='ctrl a'), hotkey(key='ctrl c')]) in an editor) rather than repeating drag on already-selected text.
- SEARCH & TEXT INPUT OVERWRITE: If a search bar, filter box, or address bar already contains old text, click inside it and overwrite the existing text directly using ctrl a before typing (e.g. burst([click(start_box='(x,y)'), hotkey(key='ctrl a'), type(content='<query>\\n')]) or hotkey(key='ctrl a') then type(content='<query>\\n')). Do not avoid a search box just because it already has text.
- NESTED FOLDERS: When operating on a file inside a nested directory path (<parent>\\<target>), enter <target> first (double-click it or open it via 'win r' with 'explorer <path>') before creating or renaming items; do not right-click the parent folder itself.
- To launch an application, use whatever path is visible and natural: double-click a desktop shortcut, click an icon inside an open menu, type into a visible search bar, or use hotkeys ('win r', 'win').
- GENERATIVE WRITING TASKS: When asked to write, compose, draft, or summarize original content (e.g. a greeting, overview, poem, or <N> sentences about <topic>), write real, factual body sentences (<sentence 1>. <sentence 2>.) directly in type(content=...). Begin immediately with concrete content rather than repeating the prompt, typing a standalone heading/title, or describing what the sentences cover.
- ALREADY FOCUSED TARGETS: Check Active Window in Working Memory. If your target application (e.g. Notepad) is ALREADY the Active Window, do NOT click it again to "bring it to front" — immediately emit type(content=...) or the next action inside it.
- DO NOT CLOSE UNRELATED WINDOWS: Never close, exit, or click the [X] button of existing open apps, games, terminals, or background windows to "clear the workspace" unless the user explicitly asks to close them. To switch to another app, click its taskbar icon, press 'win' to search, or use 'win r' instead of closing what is currently open.
- COMPLETION & NO UNREQUESTED SAVES: NEVER click the window Close (X) button, press 'ctrl s', 'alt f4', save files, or close windows unless the user task explicitly asks you to save, export, or close. For open/launch/play tasks, NEVER emit finished() just because a search result or menu item is visible — you MUST click/launch the item (or click Play) and confirm it opened first. As soon as all requested items or text are visible and opened on screen, emit finished() immediately.
- Only emit finished() after visually confirming on the current screenshot that the task is 100% completed.
- If Recent History indicates NO SCREEN CHANGE or a rejected finished(), do NOT repeat the same action; try an alternative path (e.g. keyboard shortcuts, double-clicking, or typing to search).
"""

_TRAILING_ROLE_PATTERN = re.compile(
    r"(?:<\|im_end\|>|<\|endoftext\|>|<\|im_start\|>|\n\s*(?:assistant|user|system|observation)\s*(?::|$|\n)).*$",
    re.IGNORECASE | re.DOTALL,
)


def _strip_role_artifacts(text: str) -> str:
    """Strips trailing chat role tokens and special EOS markers from raw model output."""
    if not text:
        return ""
    return _TRAILING_ROLE_PATTERN.sub("", text).strip()


def extract_thought_and_action(raw_output: str) -> Tuple[str, str]:
    """
    Extracts the 'Thought:' and 'Action:' strings from raw model output.
    Handles varied casing, missing blocks, trailing role markers, and markdown code fencing.
    """
    cleaned = raw_output.strip()

    # Strip markdown formatting or code blocks if wrapped
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    cleaned = _strip_role_artifacts(cleaned)

    thought = ""
    action = ""

    # Look for explicit Thought: and Action: patterns
    thought_match = re.search(r"(?:^|\n)\s*Thought\s*:\s*(.*?)(?=\n\s*Action\s*:|\Z)", cleaned, re.IGNORECASE | re.DOTALL)
    if thought_match:
        thought = _strip_role_artifacts(thought_match.group(1))

    action_match = re.search(r"(?:^|\n)\s*Action\s*:\s*(.*?)(?=\n\s*(?:Thought|Action)\s*:|\Z)", cleaned, re.IGNORECASE | re.DOTALL)
    if action_match:
        action = _strip_role_artifacts(action_match.group(1))
    else:
        # If Action: prefix is omitted, check if there is a known action signature directly (even if closing paren is clipped)
        direct_call = re.search(
            r"\b(burst|sequence|chain|click|left_double|double_click|right_single|right_click|drag|mouse_drag|drag_and_drop|type|hotkey|press|scroll|wait|sleep|finished|finish|done)\s*\((?:.*?\)|.*$)",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if direct_call:
            action = _strip_role_artifacts(direct_call.group(0))
            # Everything before the call can be treated as thought if thought was empty
            if not thought:
                thought = _strip_role_artifacts(cleaned[:direct_call.start()])
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
    
    Transforms extracted coordinate values into screen pixels (e.g. 1920x1080).
    In accordance with UI-TARS 1.5's Qwen2.5-VL backbone, coordinates are output directly
    in absolute screen pixels. Clamps values strictly within [0, screen_width-1] and [0, screen_height-1].
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
        raw_x = (x1 + x2) / 2.0
        raw_y = (y1 + y2) / 2.0
    elif len(nums) >= 2:
        raw_x = nums[0]
        raw_y = nums[1]
    else:
        return None

    # Enforce strict Native Screen Pixel invariant (Rule 8)
    # UI-TARS 1.5 (Qwen2.5-VL backbone) outputs coordinates directly in physical screen pixel space.
    # Clamp coordinates strictly within [0, screen_width - 1] and [0, screen_height - 1] without scaling distortion.
    px_x = int(round(raw_x))
    px_y = int(round(raw_y))

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


def _extract_kwarg(args_content: str, key: str) -> Optional[str]:
    """
    Extracts a keyword argument value from args_content, supporting:
    1. Properly closed single or double quoted strings: key='...' or key="..."
    2. Unclosed trailing quoted strings clipped at max_tokens: key='...$
    3. Unquoted scalar arguments: key=value
    """
    # 1. Closed single or double quoted string
    closed_match = re.search(
        rf"\b{re.escape(key)}\s*=\s*(?:'([^']*)'|\"([^\"]*)\")",
        args_content,
        re.IGNORECASE | re.DOTALL,
    )
    if closed_match:
        val = closed_match.group(1) if closed_match.group(1) is not None else closed_match.group(2)
        return (val or "").strip()

    # 2. Unclosed trailing quoted string (when output was truncated before closing quote/paren)
    unclosed_match = re.search(
        rf"\b{re.escape(key)}\s*=\s*['\"]([^'\"]*)$",
        args_content,
        re.IGNORECASE | re.DOTALL,
    )
    if unclosed_match:
        return (unclosed_match.group(1) or "").strip()

    # 3. Unquoted scalar token
    scalar_match = re.search(
        rf"\b{re.escape(key)}\s*=\s*([^,\)\s'\"][^,\)]*)",
        args_content,
        re.IGNORECASE,
    )
    if scalar_match:
        return (scalar_match.group(1) or "").strip()

    return None


def _extract_all_kwargs(args_content: str) -> Dict[str, str]:
    """
    Extracts all key=value pairs from args_content with fallback for unclosed trailing quotes.
    """
    kwargs: Dict[str, str] = {}
    for key_match in re.finditer(r"\b([a-zA-Z_][a-zA-Z_0-9]*)\s*=", args_content):
        k = key_match.group(1).lower()
        val = _extract_kwarg(args_content, k)
        if val is not None:
            kwargs[k] = val
    return kwargs


def _extract_box_coords(
    args_content: str,
    kwargs: Dict[str, str],
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> Optional[Tuple[int, int]]:
    """
    Extracts and scales (x, y) coordinates from kwargs ('start_box', 'point', 'box', 'end_box')
    or directly from args_content even when closing quotes or parentheses were clipped.
    """
    box_val = (
        kwargs.get("start_box")
        or kwargs.get("point")
        or kwargs.get("box")
        or kwargs.get("end_box")
    )
    if box_val:
        coords = parse_coordinates(box_val, screen_width, screen_height)
        if coords is not None:
            return coords

    # Direct regex fallback for clipped coordinate tuples: e.g. start_box='(24,980
    direct_box = re.search(
        r"(?:start_box|point|box|end_box)\s*=\s*['\"]?\s*(?:<\|box_start\|>)?\s*[\(\[]?\s*([-+]?\d*\.?\d+\s*,\s*[-+]?\d*\.?\d+(?:\s*,\s*[-+]?\d*\.?\d+\s*,\s*[-+]?\d*\.?\d+)?)",
        args_content,
        re.IGNORECASE,
    )
    if direct_box:
        coords = parse_coordinates(direct_box.group(1), screen_width, screen_height)
        if coords is not None:
            return coords

    # Positional coordinate fallback: e.g. click('(24, 980)') or click(24, 980)
    if re.search(r"[-+]?\d*\.?\d+\s*,\s*[-+]?\d*\.?\d+", args_content):
        return parse_coordinates(args_content, screen_width, screen_height)

    return None


def _split_top_level_calls(expr: str) -> List[str]:
    """
    Splits top-level action calls separated by commas or semicolons, respecting
    quoted strings, parentheses, and brackets.
    """
    calls: List[str] = []
    current: List[str] = []
    in_quote: Optional[str] = None
    paren_depth = 0
    bracket_depth = 0
    escape = False

    cleaned = expr.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()

    for ch in cleaned:
        if escape:
            current.append(ch)
            escape = False
            continue

        if ch == "\\":
            escape = True
            current.append(ch)
            continue

        if in_quote:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
            continue

        if ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
            continue

        if ch in ("(", "{"):
            paren_depth += 1
            current.append(ch)
            continue

        if ch in (")", "}"):
            paren_depth = max(0, paren_depth - 1)
            current.append(ch)
            continue

        if ch == "[":
            bracket_depth += 1
            current.append(ch)
            continue

        if ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
            current.append(ch)
            continue

        if (ch in (",", ";", "\n")) and paren_depth == 0 and bracket_depth == 0:
            token = "".join(current).strip()
            if token:
                calls.append(token)
            current = []
            continue

        current.append(ch)

    token = "".join(current).strip()
    if token:
        calls.append(token)
    return calls


def parse_uitars_action(
    raw_output: str,
    screen_width: int = 1920,
    screen_height: int = 1080,
    candidate_elements: Optional[List[Any]] = None,
    snap_radius_px: float = 35.0,
) -> Tuple[str, ActionPlan]:
    """
    Parses UI-TARS-1.5 model output into a (thought, ActionPlan) tuple.
    Supports single actions and compound burst sequences (burst([...]), sequence([...]), chain([...])).
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
        return thought, ActionPlan(
            action=ActionType.WAIT,
            reasoning=thought or "No action command detected in model output.",
        )

    action_str = _strip_role_artifacts(action_str)

    # 2. Check for compound burst wrapper: burst(...), sequence(...), chain(...)
    burst_match = re.search(r"^(?:burst|sequence|chain)\s*\(\s*(.*)", action_str, re.IGNORECASE | re.DOTALL)
    is_burst_wrapper = bool(burst_match)
    if is_burst_wrapper:
        inner_content = burst_match.group(1).strip()
        if inner_content.endswith(")"):
            inner_content = inner_content[:-1].strip()
        raw_sub_calls = _split_top_level_calls(inner_content)
    else:
        # Check if top-level action_str contains multiple chained action calls
        raw_sub_calls = _split_top_level_calls(action_str)
        if len(raw_sub_calls) > 1:
            deduped_calls: List[str] = []
            for call_item in raw_sub_calls:
                norm_item = call_item.strip().strip(",;")
                if not norm_item:
                    continue
                if not deduped_calls or norm_item != deduped_calls[-1]:
                    deduped_calls.append(norm_item)
            # Collapse clipped/degenerate multi-line token loops (> 4 unprompted calls)
            if len(deduped_calls) > 4:
                raw_sub_calls = [deduped_calls[0]]
            else:
                raw_sub_calls = deduped_calls

    if (is_burst_wrapper or len(raw_sub_calls) > 1):
        if not raw_sub_calls and is_burst_wrapper:
            return thought, ActionPlan(
                action=ActionType.WAIT,
                reasoning=thought or "Empty or unparseable burst action sequence.",
            )
        parsed_sub_actions: List[ActionPlan] = []
        for call_item in raw_sub_calls:
            call_cleaned = call_item.strip().strip(",;")
            if not call_cleaned:
                continue
            _, sub_plan = _parse_single_action_call(
                call_str=call_cleaned,
                thought=thought,
                screen_width=screen_width,
                screen_height=screen_height,
                candidate_elements=candidate_elements,
                snap_radius_px=snap_radius_px,
            )
            # Flatten any sub-bursts if nested
            if sub_plan.action == ActionType.BURST and sub_plan.burst_actions:
                parsed_sub_actions.extend(sub_plan.burst_actions)
            elif sub_plan.action not in (ActionType.PANIC, ActionType.OFFLOAD_WEB_AI):
                parsed_sub_actions.append(sub_plan)

        if parsed_sub_actions:
            burst_plan = ActionPlan(
                action=ActionType.BURST,
                burst_actions=parsed_sub_actions,
                reasoning=thought or f"Reflex burst of {len(parsed_sub_actions)} actions",
            )
            return thought, burst_plan
        elif is_burst_wrapper:
            return thought, ActionPlan(
                action=ActionType.WAIT,
                reasoning=thought or "Empty or unparseable burst action sequence.",
            )

    # 3. Standard single action parsing
    return _parse_single_action_call(
        call_str=action_str,
        thought=thought,
        screen_width=screen_width,
        screen_height=screen_height,
        candidate_elements=candidate_elements,
        snap_radius_px=snap_radius_px,
    )


def _parse_single_action_call(
    call_str: str,
    thought: str = "",
    screen_width: int = 1920,
    screen_height: int = 1080,
    candidate_elements: Optional[List[Any]] = None,
    snap_radius_px: float = 35.0,
) -> Tuple[str, ActionPlan]:
    """Parses an individual action call string into an ActionPlan."""
    call_str = _strip_role_artifacts(call_str).strip()
    if not call_str:
        return thought, ActionPlan(action=ActionType.WAIT, reasoning=thought)

    fn_name = ""
    args_content = ""
    call_match = re.search(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)", call_str, re.DOTALL)
    if call_match:
        fn_name = call_match.group(1).strip().lower()
        args_content = call_match.group(2).strip()
        if args_content.endswith(")"):
            args_content = args_content[:-1].strip()
    else:
        # Fallback: check if the string itself is a verb synonym (e.g. 'SELECT', 'FINISHED')
        return thought, ActionPlan(
            action=ActionPlan._coerce_null_fields({"action": call_str})["action"],
            reasoning=thought or f"Raw verb call: {call_str}",
        )

    # Parse key=value arguments
    kwargs = _extract_all_kwargs(args_content)

    # Determine coordinates from start_box, point, end_box, or positional args_content
    coords = _extract_box_coords(args_content, kwargs, screen_width, screen_height)

    # Apply hybrid element snapping if coordinates found and candidate elements supplied
    if coords is not None and candidate_elements:
        coords, _ = snap_coordinates_to_element(coords, candidate_elements, snap_radius_px)

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

    elif fn_name in ("drag", "mouse_drag", "drag_and_drop"):
        end_coords = None
        if kwargs.get("end_box"):
            end_coords = parse_coordinates(kwargs["end_box"], screen_width, screen_height)
            if end_coords is not None and candidate_elements:
                end_coords, _ = snap_coordinates_to_element(end_coords, candidate_elements, snap_radius_px)
        return thought, ActionPlan(
            action=ActionType.DRAG,
            coordinates=coords,
            end_coordinates=end_coords,
            reasoning=thought or f"Drag from {coords} to {end_coords}",
        )

    elif fn_name in ("type", "write", "input"):
        raw_text = kwargs.get("content") or kwargs.get("text") or kwargs.get("string") or ""
        submit = False
        if raw_text.endswith(("\\n", "\n", "\r\n")):
            submit = True
            raw_text = re.sub(r"(?:\\n|\r?\n)+$", "", raw_text)
        elif (
            kwargs.get("submit", "").lower() in ("true", "1", "yes")
            or kwargs.get("enter", "").lower() in ("true", "1", "yes")
            or kwargs.get("press_enter", "").lower() in ("true", "1", "yes")
        ):
            submit = True
        clear_first = kwargs.get("clear_first", "false").lower() in ("true", "1", "yes")

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
        # Support python list strings: ['ctrl', 's'] or "['ctrl', 's']"
        raw_key = re.sub(r"[\[\]'\",]+", " ", raw_key)
        keys_list = [k.strip().lower() for k in re.split(r"[\s\+]+", raw_key) if k.strip()]
        if not keys_list:
            keys_list = ["enter"]

        key_alias_map = {
            "escape": "esc",
            "return": "enter",
        }
        keys_list = [key_alias_map.get(k, k) for k in keys_list]

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
        # Support positional duration: wait(100) or wait(wait_ms=100)
        pos_num = None
        if not kwargs and args_content:
            m_num = re.search(r"\d+", args_content)
            if m_num:
                pos_num = int(m_num.group(0))
        wait_ms = int(kwargs.get("wait_ms") or kwargs.get("duration") or pos_num or 500)
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
        coerced = ActionPlan._coerce_null_fields({"action": fn_name, "reasoning": thought})
        return thought, ActionPlan.model_validate(coerced)


# Alias for callers referencing parse_uitars_response
parse_uitars_response = parse_uitars_action
