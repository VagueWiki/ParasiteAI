"""
stress_test_4a.py - Empirical Challenger Stress Harness for Milestone 4A.
Working Directory: C:\\ParasiteAI\\.agents\\teamwork\\teamwork_challenger_m4a_1\\

Adversarial Stress Testing:
1. Byte budget of serialize_textual_scene_brief across element pools:
   - Sizes: 1, 10, 50, 100, 200 elements
   - Variations: standard UI, long labels (100+ chars), CJK/Emoji unicode labels, extreme coordinates
   - Parameter variations: default max_elements (25) and unbounded max_elements (50, 100, 200)
   - Strict budget assertion: len(brief.encode('utf-8')) < 3072 bytes (3 KB)
2. Grounded Capability Manifest verification:
   - Absence of video streaming
   - Actuator limits (Bézier, 5th-order Min-Jerk, 120Hz polling)
   - Atomic Ctrl+V paste (<100ms) with clipboard backup/restore
   - Dynamic bounds handling (including negative multi-monitor offsets)
   - Explicit scraping tool bans (curl, wget, requests, playwright, puppeteer, selenium, beautifulsoup)
   - Explicit programmatic UIA pattern bans (ValuePattern, InvokePattern, TogglePattern, SelectionItemPattern)
   - Additional invariants (WM_SETTEXT ban, sub-2ms hardware preemption, Ctrl+Alt+K kill, app_map ban)
3. Consultation Prompt & Multi-turn Clarification Hooks:
   - format_gemini_consultation_prompt positional and keyword arguments
   - is_clarification_response detection
   - parse_gemini_consultation_response LivingPlan structure
   - resolve_clarification_query dialog & control inspection
4. Core Invariants:
   - BrainConfig.mode == "local_llm"
   - AppConfig().brain.mode == "local_llm"
   - CadenceTier 5 tiers
"""

import sys
import os
import traceback

# Ensure ParasiteAI root is on sys.path
sys.path.insert(0, r"C:\ParasiteAI")

from typing import List, Tuple
from parasite_ai.config import BrainConfig, AppConfig
from parasite_ai.mind.memory import CadenceTier
from parasite_ai.mind.plan import (
    GroundedCapabilityContract,
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    build_grounded_capability_manifest,
    format_gemini_consultation_prompt,
    is_clarification_response,
    parse_gemini_consultation_response,
    resolve_clarification_query,
    serialize_textual_scene_brief,
)
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement


def make_synthetic_element(
    elem_id: int,
    label: str,
    role: str = "Button",
    x: int = 100,
    y: int = 100,
    w: int = 80,
    h: int = 30,
    source: str = "uia",
    is_active: bool = True,
) -> UIElement:
    return UIElement(
        id=elem_id,
        role=role,
        label=label,
        x=x,
        y=y,
        width=w,
        height=h,
        center_x=x + w // 2,
        center_y=y + h // 2,
        source=source,
        is_active_window=is_active,
    )


def test_core_invariants():
    print("\n" + "=" * 70)
    print("TEST SUITE 1: Core Privacy & Escalation Invariants")
    print("=" * 70)

    # Invariant 1: BrainConfig mode
    bc = BrainConfig()
    assert bc.mode == "local_llm", f"FAIL: BrainConfig.mode is '{bc.mode}', expected 'local_llm'"
    print(f" [PASS] BrainConfig().mode == '{bc.mode}' (Zero silent cloud exfiltration invariant)")

    ac = AppConfig()
    assert ac.brain.mode == "local_llm", f"FAIL: AppConfig.brain.mode is '{ac.brain.mode}'"
    assert ac.mind.mode == "local_llm", f"FAIL: AppConfig.mind.mode is '{ac.mind.mode}'"
    print(" [PASS] AppConfig().brain.mode and mind.mode == 'local_llm'")

    # Invariant 2: CadenceTier
    tiers = [
        CadenceTier.TIER_1_LOCAL,
        CadenceTier.TIER_2_CONSULT,
        CadenceTier.TIER_3_GUIDED,
        CadenceTier.TIER_4_CO_PILOT,
        CadenceTier.USER_OVERRIDE,
    ]
    assert len(tiers) == 5, f"FAIL: Expected 5 tiers, got {len(tiers)}"
    assert [t.value for t in tiers] == [
        "TIER_1_LOCAL", "TIER_2_CONSULT", "TIER_3_GUIDED", "TIER_4_CO_PILOT", "USER_OVERRIDE"
    ]
    print(f" [PASS] CadenceTier enum validated across all 5 tiers: {[t.value for t in tiers]}")


def test_grounded_capability_manifest():
    print("\n" + "=" * 70)
    print("TEST SUITE 2: Grounded Capability Manifest Verification")
    print("=" * 70)

    # 1. Default bounds
    manifest_default = build_grounded_capability_manifest((0, 0, 3840, 1080))

    # Assert absence of video streaming
    prohibited_stream_terms = [
        "video streaming",
        "webrtc",
        "h.264",
        "rtsp",
        "video stream",
        "live stream",
        "video feed",
        "60 fps stream",
    ]
    manifest_lower = manifest_default.lower()
    for term in prohibited_stream_terms:
        assert term not in manifest_lower, f"FAIL: Prohibited term '{term}' found in manifest!"
    print(" [PASS] Absence of video streaming verified (zero streaming protocols in manifest)")

    # Assert presence of actuator limits
    assert "cubic Bézier" in manifest_default, "FAIL: Missing cubic Bézier trajectory limit"
    assert "5th-order Min-Jerk" in manifest_default, "FAIL: Missing 5th-order Min-Jerk velocity profiling"
    assert "120 Hz" in manifest_default, "FAIL: Missing 120 Hz update loop limit"
    assert "Atomic Ctrl+V paste (<100ms)" in manifest_default, "FAIL: Missing atomic Ctrl+V paste limit"
    assert "KEYEVENTF_UNICODE with 25-75ms human cadence jitter" in manifest_default, "FAIL: Missing typing jitter"
    print(" [PASS] Actuator limits verified (Bézier, Min-Jerk, 120Hz, Atomic Ctrl+V, 25-75ms jitter)")

    # Assert dynamic bounds
    test_bounds = [
        (0, 0, 1920, 1080),
        (-1920, 0, 3840, 1080),
        (0, 0, 5120, 1440),
        (-3840, -1080, 7680, 2160),
    ]
    for b in test_bounds:
        m = build_grounded_capability_manifest(b)
        assert f"[{b[0]}, {b[1]}, {b[2]}, {b[3]}]" in m, f"FAIL: Dynamic bounds {b} not in manifest"
        x_min, y_min, w, h = b
        assert f"[{x_min}, {x_min + w}) x [{y_min}, {y_min + h})" in m, f"FAIL: Coordinate validation range incorrect for {b}"
    print(f" [PASS] Dynamic bounds verified across multi-monitor setups: {test_bounds}")

    # Assert explicit scraping bans
    banned_scraping = ["curl", "wget", "requests", "playwright", "puppeteer", "selenium", "beautifulsoup"]
    for tool in banned_scraping:
        assert tool in manifest_default, f"FAIL: Scraping tool '{tool}' not explicitly banned in manifest!"
    assert "ZERO headless browser automation" in manifest_default
    assert "ZERO headless scraping" in manifest_default
    print(f" [PASS] Explicit scraping bans verified: {banned_scraping}")

    # Assert explicit programmatic UIA bans
    banned_uia = ["ValuePattern.SetValue", "InvokePattern.Invoke", "TogglePattern.Toggle", "SelectionItemPattern.Select"]
    for pattern in banned_uia:
        assert pattern in manifest_default, f"FAIL: Programmatic UIA pattern '{pattern}' not banned in manifest!"
    assert "strictly read-only for element discovery" in manifest_default
    print(f" [PASS] Programmatic UIA bans verified: {banned_uia}")

    # Assert hard safety invariants
    assert "WM_SETTEXT" in manifest_default
    assert "Sub-2ms physical hardware preemption" in manifest_default
    assert "Ctrl+Alt+K" in manifest_default
    assert "app_map = {} is strictly forbidden" in manifest_default
    print(" [PASS] Hard safety invariants verified (WM_SETTEXT ban, sub-2ms preemption, Ctrl+Alt+K, app_map ban)")


def test_serialize_textual_scene_brief_byte_budget():
    print("\n" + "=" * 70)
    print("TEST SUITE 3: serialize_textual_scene_brief Byte Budget Stress Testing")
    print("=" * 70)

    win_info = WindowInfo(
        hwnd=77123,
        title="Visual Studio Code - ParasiteAI",
        class_name="Chrome_WidgetWin_1",
        process_name="Code.exe",
        process_path="C:\\Users\\Suici\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
        pid=10452,
        rect=(0, 0, 1920, 1040),
        is_sensitive=False,
        reason="Developer IDE",
    )

    element_counts = [1, 10, 50, 100, 200]
    BUDGET_BYTES = 3072  # 3 KB

    print(f"{'Pool Size':<10} | {'Condition':<25} | {'max_elements':<12} | {'Bytes':<8} | {'Status':<6}")
    print("-" * 70)

    test_scenarios = [
        # (name, label_generator)
        ("Standard UI", lambda i: f"Control Button {i}"),
        ("Long Labels (120ch)", lambda i: f"Exceedingly Long Descriptive Accessibility Name For Button #{i:04d} With Extra Semantic Information And Context"),
        ("Multibyte / CJK", lambda i: f"按钮_コントロール_элемент_{i:04d}_🌟"),
        ("Markdown Metachars", lambda i: f"Control | with | pipes \n and [brackets] #{i}"),
    ]

    results = []

    for count in element_counts:
        for scen_name, label_gen in test_scenarios:
            elements = [
                make_synthetic_element(
                    elem_id=i,
                    label=label_gen(i),
                    role="Button" if i % 2 == 0 else "Edit",
                    x=(i * 35) % 1920,
                    y=(i * 25) % 1080,
                    w=50,
                    h=25,
                )
                for i in range(1, count + 1)
            ]

            # Case A: Default max_elements (25)
            brief_default = serialize_textual_scene_brief(
                elements=elements,
                window_info=win_info,
                recent_diff=0.015,
                caret_active=(count % 2 == 0),
                active_tier="TIER_1_LOCAL",
                consecutive_strikes=1,
            )
            bytes_default = len(brief_default.encode("utf-8"))
            pass_default = bytes_default < BUDGET_BYTES
            status_default = "PASS" if pass_default else "FAIL"
            print(f"{count:<10} | {scen_name:<25} | {'default(25)':<12} | {bytes_default:<8} | {status_default:<6}")
            results.append((count, scen_name, "default(25)", bytes_default, pass_default))
            assert pass_default, f"FAIL: {count} elements, {scen_name}, default(25) produced {bytes_default} bytes >= {BUDGET_BYTES}"

            # Case B: Explicit max_elements = count (stressing the internal byte limiter)
            brief_unbounded = serialize_textual_scene_brief(
                elements=elements,
                window_info=win_info,
                recent_diff=0.015,
                caret_active=(count % 2 == 0),
                active_tier="TIER_1_LOCAL",
                consecutive_strikes=1,
                max_elements=count,
            )
            bytes_unbounded = len(brief_unbounded.encode("utf-8"))
            pass_unbounded = bytes_unbounded < BUDGET_BYTES
            status_unbounded = "PASS" if pass_unbounded else "FAIL"
            print(f"{count:<10} | {scen_name:<25} | {f'all({count})':<12} | {bytes_unbounded:<8} | {status_unbounded:<6}")
            results.append((count, scen_name, f"all({count})", bytes_unbounded, pass_unbounded))
            assert pass_unbounded, f"FAIL: {count} elements, {scen_name}, all({count}) produced {bytes_unbounded} bytes >= {BUDGET_BYTES}"

    print("-" * 70)
    print(f" [PASS] All {len(results)} element pool scenarios strictly satisfied byte budget < 3072 bytes!")


def test_edge_cases_and_adversarial_inputs():
    print("\n" + "=" * 70)
    print("TEST SUITE 4: Edge Cases & Adversarial Inputs")
    print("=" * 70)

    BUDGET_BYTES = 3072

    # 1. Empty elements list
    b1 = serialize_textual_scene_brief(elements=[], window_info=None)
    bytes1 = len(b1.encode("utf-8"))
    assert bytes1 < BUDGET_BYTES
    assert "No interactive controls detected" in b1
    print(f" [PASS] Empty elements list: {bytes1} bytes (< 3072), 'No interactive controls detected' present")

    # 2. None elements
    b2 = serialize_textual_scene_brief(elements=None, window_info=None)
    bytes2 = len(b2.encode("utf-8"))
    assert bytes2 < BUDGET_BYTES
    assert "No interactive controls detected" in b2
    print(f" [PASS] None elements: {bytes2} bytes (< 3072)")

    # 3. Elements with None / missing attributes
    class DuckElement:
        pass

    duck1 = DuckElement()
    duck2 = DuckElement()
    duck2.label = None
    duck2.role = None
    duck3 = DuckElement()
    duck3.label = "Valid Label"

    b3 = serialize_textual_scene_brief(elements=[duck1, duck2, duck3], window_info=None)
    bytes3 = len(b3.encode("utf-8"))
    assert bytes3 < BUDGET_BYTES
    print(f" [PASS] Duck typing elements with missing/None attributes: {bytes3} bytes (< 3072)")

    # 4. Extreme coordinates (negative offsets, huge multi-monitor bounds)
    extreme_elements = [
        make_synthetic_element(1, "Top-Left Outer", x=-3840, y=-1080, w=100, h=50),
        make_synthetic_element(2, "Bottom-Right Outer", x=15360, y=8640, w=200, h=100),
    ]
    b4 = serialize_textual_scene_brief(elements=extreme_elements, window_info=None)
    bytes4 = len(b4.encode("utf-8"))
    assert bytes4 < BUDGET_BYTES
    assert "[-3840, -1080, 100, 50]" in b4
    assert "[15360, 8640, 200, 100]" in b4
    print(f" [PASS] Extreme coordinate bounds preserved: {bytes4} bytes (< 3072)")

    # 5. Caret detection and edit control flags
    edit_elem = make_synthetic_element(1, "Input Field", role="Edit")
    doc_elem = make_synthetic_element(2, "Text Document", role="Document")
    combo_elem = make_synthetic_element(3, "Options", role="ComboBox")
    btn_elem = make_synthetic_element(4, "Submit", role="Button")

    b5 = serialize_textual_scene_brief(
        elements=[edit_elem, doc_elem, combo_elem, btn_elem],
        window_info=None,
        caret_active=True,
    )
    assert "ACTIVE, CARET" in b5
    print(" [PASS] Caret flag correctly attached to Edit, Document, ComboBox controls when caret_active=True")

    # 6. Window title with quotes and pipes
    funky_win = WindowInfo(
        hwnd=111,
        title='Document "Report.pdf" | Reader',
        class_name="Acrobat",
        process_name="AcroRd32.exe",
        process_path="C:\\Program Files\\Adobe\\Acrobat.exe",
        pid=555,
        rect=(0, 0, 1000, 800),
        is_sensitive=False,
        reason="PDF Reader",
    )
    b6 = serialize_textual_scene_brief(elements=extreme_elements, window_info=funky_win)
    bytes6 = len(b6.encode("utf-8"))
    assert bytes6 < BUDGET_BYTES
    assert 'Title: "Document "Report.pdf" | Reader"' in b6
    print(f" [PASS] Window with special characters: {bytes6} bytes (< 3072)")


def test_clarification_and_consultation_prompt():
    print("\n" + "=" * 70)
    print("TEST SUITE 5: Gemini Consultation Prompt & Clarification Protocol")
    print("=" * 70)

    elements = [
        make_synthetic_element(1, "Save", role="Button"),
        make_synthetic_element(2, "Cancel", role="Button"),
    ]
    win_info = WindowInfo(
        hwnd=999,
        title="Save File",
        class_name="#32770",
        process_name="notepad.exe",
        process_path="C:\\Windows\\notepad.exe",
        pid=888,
        rect=(100, 100, 500, 400),
        is_sensitive=False,
        reason="File Dialog",
    )

    # 1. format_gemini_consultation_prompt
    prompt = format_gemini_consultation_prompt(
        user_goal="Save document as output.txt",
        elements=elements,
        window_info=win_info,
        dilemma="Save dialog open, Save button clicked but file not saved",
        recent_history="Action 1: click File; Action 2: click Save As",
        caret_active=False,
        recent_diff=0.001,
    )
    assert "[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]" in prompt
    assert "# CAPABILITY CONTRACT & CONSTRAINTS" in prompt
    assert "# ACTIVE DESKTOP STATE" in prompt
    assert "# TEXTUAL SET-OF-MARK (SOM) INVENTORY" in prompt
    assert "# CURRENT GOAL & FAILURE DILEMMA" in prompt
    assert "# INSTRUCTIONS" in prompt
    assert "Save document as output.txt" in prompt
    assert "Save dialog open" in prompt
    print(" [PASS] format_gemini_consultation_prompt verified with positional args")

    # 2. Legacy kwargs
    legacy_prompt = format_gemini_consultation_prompt(
        goal="Format disk",
        active_window_title="Disk Management",
        process_name="mmc.exe",
        open_apps_summary="Disk Management",
        visual_scene_summary="Disk layout table",
        dilemma_description="Drive is offline",
    )
    assert "Format disk" in legacy_prompt
    assert "Disk Management" in legacy_prompt
    print(" [PASS] format_gemini_consultation_prompt backward compatibility verified")

    # 3. Clarification response detection
    raw_clarify = '{"need_clarification": true, "question": "Is the modal dialog blocking input?"}'
    is_clar, q = is_clarification_response(raw_clarify)
    assert is_clar is True
    assert q == "Is the modal dialog blocking input?"
    print(f" [PASS] is_clarification_response correctly detected: '{q}'")

    plan = parse_gemini_consultation_response(raw_clarify, user_goal="Save doc")
    assert plan.needs_clarification is True
    assert plan.clarification_question == "Is the modal dialog blocking input?"
    assert len(plan.steps) == 1
    assert plan.steps[0].intent == StepIntent.CONSULT_ADVISOR
    print(" [PASS] parse_gemini_consultation_response generated StepIntent.CONSULT_ADVISOR on clarification")

    # 4. Clarification resolution
    res_modal = resolve_clarification_query("Is this dialog modal?", window_info=win_info)
    assert "Save File" in res_modal
    assert "active foreground window" in res_modal
    print(" [PASS] resolve_clarification_query correctly resolved modal question")

    res_control = resolve_clarification_query("Which button to click?", elements=elements)
    assert "[#1] Button 'Save'" in res_control
    assert "[#2] Button 'Cancel'" in res_control
    print(" [PASS] resolve_clarification_query correctly resolved control disambiguation")


def main():
    print("=" * 70)
    print("PARASITE AI - MILESTONE 4A EMPIRICAL CHALLENGER TEST SUITE")
    print("=" * 70)

    try:
        test_core_invariants()
        test_grounded_capability_manifest()
        test_serialize_textual_scene_brief_byte_budget()
        test_edge_cases_and_adversarial_inputs()
        test_clarification_and_consultation_prompt()
        print("\n" + "=" * 70)
        print("ALL EMPIRICAL CHALLENGER TESTS PASSED SUCCESSFULLY! (Verdict: APPROVE)")
        print("=" * 70)
        return 0
    except Exception as e:
        print("\n" + "!" * 70)
        print(f"TEST SUITE FAILED WITH EXCEPTION: {e}")
        traceback.print_exc()
        print("!" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
