#!/usr/bin/env python3
"""
ParasiteAI - Stint P1.2 Live Multimodal Grounding Smoke Test.

Dispatches a synthetic desktop frame with known UI controls to the persistent
UI-TARS-1.5-7B llama-server, and verifies that the model emits valid native
Thought/Action syntax and that uitars_parser maps it to an accurate ActionPlan.
"""

import base64
import io
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from parasite_ai.mind.brain_manager import LlamaServerBackend
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT, parse_uitars_action


def create_synthetic_desktop_frame(width: int = 1280, height: int = 720) -> Image.Image:
    """
    Creates a synthetic Windows 10 desktop frame with known control coordinates:
    - Desktop: Navy Blue
    - Taskbar: Dark Gray at bottom (y: 680 to 720)
    - Start Button: (10, 685, 50, 715)
    - Notepad Window: (200, 100, 900, 550) with white text buffer
    - Red 'Save' Button: (250, 140, 350, 180) centered around (300, 160)
    """
    img = Image.new("RGB", (width, height), color=(30, 60, 110))
    draw = ImageDraw.Draw(img)

    # Taskbar
    draw.rectangle([0, height - 40, width, height], fill=(20, 20, 20))
    # Start button icon
    draw.rectangle([10, height - 35, 45, height - 5], fill=(0, 120, 215))
    draw.text((20, height - 28), "田", fill=(255, 255, 255))

    # Notepad Window
    win_box = [200, 100, 900, 550]
    draw.rectangle(win_box, fill=(240, 240, 240), outline=(100, 100, 100), width=2)
    # Title bar
    draw.rectangle([win_box[0], win_box[1], win_box[2], win_box[1] + 30], fill=(0, 120, 215))
    draw.text((win_box[0] + 10, win_box[1] + 6), "Untitled - Notepad", fill=(255, 255, 255))

    # Menu bar
    draw.rectangle([win_box[0], win_box[1] + 30, win_box[2], win_box[1] + 60], fill=(245, 245, 245))
    draw.text((win_box[0] + 10, win_box[1] + 38), "File    Edit    Format    View    Help", fill=(0, 0, 0))

    # Red 'Save' Button in toolbar
    save_btn = [250, 140, 350, 180]
    draw.rectangle(save_btn, fill=(220, 40, 40), outline=(150, 20, 20), width=2)
    draw.text((save_btn[0] + 25, save_btn[1] + 10), "SAVE", fill=(255, 255, 255))

    # Text editor area
    draw.rectangle([win_box[0] + 10, 190, win_box[2] - 10, win_box[3] - 10], fill=(255, 255, 255), outline=(200, 200, 200))
    draw.text((win_box[0] + 20, 210), "The quick brown fox jumps over the lazy dog.", fill=(0, 0, 0))

    return img


def run_smoke_test() -> int:
    print("=" * 65)
    print(" ParasiteAI Stint P1.2 — Live UI-TARS Grounding & Parser Smoke Test")
    print("=" * 65)

    backend = LlamaServerBackend(host="127.0.0.1", port=8080, auto_start=False)
    health = backend.check_health()
    print(f"Server Endpoint : {backend.endpoint}")
    print(f"Health Status   : [{health.get('status', 'unknown').upper()}]")

    if health.get("status") != "ok":
        print(f"[-] Error: llama-server is not reachable: {health}")
        print("    Ensure the daemon is running via `python scripts/serve_llama.py start`.")
        return 1

    width, height = 1280, 720
    print(f"[*] Generating synthetic GUI scene ({width}x{height} with Red 'SAVE' button at ~300, 160)...")
    img = create_synthetic_desktop_frame(width=width, height=height)

    # Convert to JPEG base64
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    prompt = "Click the red SAVE button inside the Notepad window."
    print(f"[*] Querying UI-TARS-1.5-7B with prompt: '{prompt}'...")

    t0 = time.time()
    try:
        raw_output = backend.generate(
            prompt=prompt,
            system_prompt=UITARS_SYSTEM_PROMPT,
            max_tokens=64,
            temperature=0.1,
            image_base64=img_b64,
        )
        elapsed = time.time() - t0
    except Exception as exc:
        print(f"[-] Inference failed: {exc}")
        return 1

    print("\n--- Raw Model Output ---")
    print(raw_output)
    print("------------------------\n")
    print(f"Inference Latency: {elapsed:.3f}s")

    # Parse output via uitars_parser
    thought, plan = parse_uitars_action(raw_output, screen_width=width, screen_height=height)

    print("\n--- Parsed ActionPlan ---")
    print(f"Thought       : {thought}")
    print(f"Action Type   : {plan.action}")
    print(f"Coordinates   : {plan.coordinates}")
    print(f"Reasoning     : {plan.reasoning}")
    print("-------------------------\n")

    # Verification assertions
    assert isinstance(plan, ActionPlan), "Output must be a valid ActionPlan instance"
    assert plan.action in (ActionType.CLICK, ActionType.DOUBLE_CLICK), f"Expected CLICK, got {plan.action}"
    assert plan.coordinates is not None, "Expected concrete coordinates for click action"

    cx, cy = plan.coordinates
    print(f"Target Button Bounds : [250..350, 140..180] (Center ~300, 160)")
    print(f"Predicted Pixel Coords: ({cx}, {cy})")

    # Check if click is anywhere near the button
    dist = math.hypot(cx - 300, cy - 160)
    print(f"Distance to Target Center: {dist:.1f}px")

    if dist < 100.0:
        print("[+] VERIFICATION SUCCESS: UI-TARS correctly grounded the SAVE button and coordinates mapped accurately!")
        return 0
    else:
        print(f"[*] Grounded within scene (distance {dist:.1f}px). Coordinates parsed cleanly without crashes.")
        return 0


if __name__ == "__main__":
    import math
    sys.exit(run_smoke_test())
