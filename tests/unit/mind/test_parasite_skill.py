"""Unit tests for ParasiteSkill state machine, OS env discovery, §4.7 fail-closed matrix, breaker, and cancellation."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Dict, List, Optional, Tuple
import numpy as np
import pytest

from parasite_ai.config import ParasiteSkillConfig, SafetyConfig
from parasite_ai.hands.clipboard import (
    ClipboardLockedError,
    ClipboardSnapshot,
    DibPackError,
)
from parasite_ai.mind.parasite_protocol import (
    ParasiteFailure,
    ParasitePhase,
    ParasiteRequest,
    RecoveryTrigger,
)
from parasite_ai.mind.parasite_skill import (
    ParasiteSkill,
    Win32EnvironmentDiscovery,
)
from parasite_ai.safety.window_guard import WindowGuard

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Deterministic Mocks (zero OS side effects)
# ---------------------------------------------------------------------------

class _FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _MockClipboard:
    def __init__(self, initial_text: str = "user original clip") -> None:
        self.text: Optional[str] = initial_text
        self.dib: Optional[bytes] = b"USER_DIB"
        self.last_image_shape: Optional[Tuple[int, ...]] = None
        self.last_query_text: Optional[str] = None
        self.restored_snapshots: List[ClipboardSnapshot] = []
        self.fail_lock: bool = False
        self.fail_dib: bool = False

    def snapshot(self) -> ClipboardSnapshot:
        if self.fail_lock:
            raise ClipboardLockedError("Clipboard locked")
        return ClipboardSnapshot(unicode_text=self.text, dib_bytes=self.dib)

    def restore(self, snap: ClipboardSnapshot) -> None:
        self.restored_snapshots.append(snap)
        self.text = snap.unicode_text
        self.dib = snap.dib_bytes

    def set_image_dib(self, frame: np.ndarray) -> None:
        if self.fail_dib:
            raise DibPackError("Bad DIB")
        if self.fail_lock:
            raise ClipboardLockedError("Clipboard locked")
        self.last_image_shape = frame.shape
        self.dib = b"DIB_IMAGE"
        self.text = None

    def set_unicode_text(self, text: str) -> None:
        if self.fail_lock:
            raise ClipboardLockedError("Clipboard locked")
        self.last_query_text = text
        self.text = text
        self.dib = None

    def get_text(self) -> str:
        return self.text or ""

    def set_text(self, text: str) -> None:
        self.text = text


class _MockWindowBackend:
    def __init__(self) -> None:
        self.prior_hwnd = 101
        self.gemini_hwnd = 202
        self.unknown_hwnd = 303
        self.fg_hwnd = self.prior_hwnd
        self.proc_map: Dict[int, str] = {
            101: "notepad.exe",
            202: "chrome.exe",
            303: "discord.exe",
        }
        self.title_map: Dict[int, str] = {
            101: "Notes - Notepad",
            202: "Gemini",
            303: "Discord",
        }
        self.caret_ready = True
        self.copy_pos: Optional[Tuple[int, int]] = (950, 720)
        self.stop_pos: Optional[Tuple[int, int]] = None
        self.minimized_hwnds: List[int] = []
        self.focused_hwnds: List[int] = []
        self.switch_on_alt_g_to: Optional[int] = self.gemini_hwnd
        self.on_poll_hook = None

    def get_foreground_hwnd(self) -> int:
        if self.on_poll_hook:
            self.on_poll_hook()
        return self.fg_hwnd

    def get_process_name(self, hwnd: int) -> str:
        return self.proc_map.get(hwnd, "")

    def get_window_title(self, hwnd: int) -> str:
        return self.title_map.get(hwnd, "")

    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        return (50, 50, 900, 800)

    def minimize_window(self, hwnd: int) -> bool:
        self.minimized_hwnds.append(hwnd)
        return True

    def focus_window(self, hwnd: int) -> bool:
        self.focused_hwnds.append(hwnd)
        self.fg_hwnd = hwnd
        return True

    def ensure_on_primary_monitor(self, hwnd: int) -> bool:
        return False

    def has_input_focus(self, hwnd: int) -> bool:
        return self.caret_ready

    def find_uia_button(
        self, hwnd: int, names: List[str], pick_last: bool = True
    ) -> Optional[Tuple[int, int]]:
        lower = {n.lower() for n in names}
        if "copy" in lower:
            return self.copy_pos
        if "stop response" in lower:
            return self.stop_pos
        return None


class _MockKeyboard:
    def __init__(self, win: _MockWindowBackend, log: List[str]) -> None:
        self.win = win
        self.log = log
        self.fail_on: Optional[Tuple[str, ...]] = None

    def hotkey(self, *keys: str, cancellation_token=None) -> bool:
        chord = "+".join(keys)
        self.log.append(f"hotkey:{chord}")
        if self.fail_on == tuple(keys):
            return False
        if tuple(keys) == ("alt", "g") and self.win.switch_on_alt_g_to is not None:
            self.win.fg_hwnd = self.win.switch_on_alt_g_to
        return True


class _MockMouse:
    def __init__(self, clipboard: _MockClipboard, log: List[str], response_factory=None) -> None:
        self.clipboard = clipboard
        self.log = log
        self.response_factory = response_factory
        self.clicks: List[Tuple[int, int]] = []

    def click(self, x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        self.log.append(f"click:{x},{y}")
        self.clicks.append((int(x), int(y)))
        if self.response_factory is not None:
            self.clipboard.set_text(self.response_factory(self.clipboard.last_query_text or ""))
        return True


class _MockCapturer:
    def __init__(self, log: List[str]) -> None:
        self.log = log
        self.raise_on_screen = False
        self.screen_monitors: List[int] = []
        self.screen_frame: Optional[np.ndarray] = np.full((1080, 1920, 3), 80, dtype=np.uint8)
        self.win_frame = np.full((750, 850, 3), 120, dtype=np.uint8)
        self.mutate_rect_each_call = False
        self._rect_calls = 0

    def capture_screen(self, monitor_idx=None) -> np.ndarray:
        self.log.append(f"capture_screen:{monitor_idx}")
        self.screen_monitors.append(int(monitor_idx))
        if self.raise_on_screen:
            raise RuntimeError("capture failed")
        return self.screen_frame  # type: ignore[return-value]

    def capture_rect(self, rect) -> np.ndarray:
        self._rect_calls += 1
        if self.mutate_rect_each_call:
            arr = np.zeros((40, 40, 3), dtype=np.uint8)
            arr[:, (self._rect_calls * 5) % 35 :] = 255
            return arr
        return self.win_frame


class _MockBridge:
    def __init__(self) -> None:
        self.events = []

    def notify_episode_event(self, event) -> None:
        self.events.append(event)


class _MockWindowGuard:
    def __init__(self, safe: bool = True) -> None:
        self.safe = safe

    def is_safe_to_operate(self) -> bool:
        return self.safe


def _extract_nonce_from_query(query: str) -> str:
    import re
    m = re.search(r'nonce="([A-Za-z0-9_-]+)"', query)
    assert m, f"Missing nonce in query: {query}"
    return m.group(1)


def _valid_response(query: str) -> str:
    nonce = _extract_nonce_from_query(query)
    return (
        f'<parasite_plan nonce="{nonce}">\n'
        '{\n'
        '  "selected_program": "Notepad",\n'
        '  "rationale": "Simple editor works reliably.",\n'
        '  "steps": [{"intent": "NAVIGATE", "description": "Focus editor", "success_criteria": "Focused"}]\n'
        '}\n'
        '</parasite_plan>'
    )


def _harness(tmp_path: Path, safe_guard: bool = True, **cfg_overrides):
    clock = _FakeClock()
    log: List[str] = []
    win = _MockWindowBackend()
    clip = _MockClipboard()
    kbd = _MockKeyboard(win, log)
    mouse = _MockMouse(clip, log, response_factory=_valid_response)
    cap = _MockCapturer(log)
    guard = _MockWindowGuard(safe=safe_guard)
    bridge = _MockBridge()

    def fake_sleep(dt: float) -> None:
        clock.advance(dt)

    cfg = ParasiteSkillConfig(
        enabled=True,
        diagnostics_dir=tmp_path / "diag",
        focus_timeout_sec=1.0,
        attach_settle_ms=300,
        poll_interval_ms=200,
        stream_stability_ms=300,
        generation_timeout_sec=10.0,
        harvest_timeout_sec=1.0,
        **cfg_overrides,
    )
    skill = ParasiteSkill(
        config=cfg,
        keyboard_driver=kbd,
        mouse_driver=mouse,
        capturer=cap,
        window_guard=guard,
        interrupt_guard=None,
        bridge=bridge,
        clipboard=clip,
        window_backend=win,
        env_discovery=type(
            "StubEnv", (), {"collect": staticmethod(lambda **kw: (["notepad.exe: Notes"], ["Audacity", "FFmpeg"]))}
        )(),
        clock=clock,
        sleep_fn=fake_sleep,
    )
    return skill, clock, log, win, clip, kbd, mouse, cap, guard, bridge


# ---------------------------------------------------------------------------
# Happy Path & Ordering
# ---------------------------------------------------------------------------

def test_happy_path_physical_order_and_monitor1_capture_before_alt_g(tmp_path: Path) -> None:
    skill, _, log, win, clip, _, mouse, cap, _, bridge = _harness(tmp_path)

    res = skill.invoke(
        ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Edit text file")
    )

    assert res.ok is True
    assert res.plan is not None and res.plan.selected_program == "Notepad"
    # Monitor 1 captured BEFORE Alt+G
    assert cap.screen_monitors == [1]
    assert log.index("capture_screen:1") < log.index("hotkey:alt+g")
    # Exact input sequence: alt+g -> ctrl+v (image) -> ctrl+v (text) -> enter -> click UIA Copy
    hotkeys_and_clicks = [x for x in log if x.startswith(("hotkey:", "click:"))]
    assert hotkeys_and_clicks == [
        "hotkey:alt+g",
        "hotkey:ctrl+v",
        "hotkey:ctrl+v",
        "hotkey:enter",
        "click:950,720",
    ]
    assert win.minimized_hwnds == [win.gemini_hwnd]
    assert win.focused_hwnds == [win.prior_hwnd]
    assert clip.text == "user original clip"
    assert clip.dib == b"USER_DIB"
    assert bridge.events == []


# ---------------------------------------------------------------------------
# §4.7 Failure Matrix Coverage
# ---------------------------------------------------------------------------

def test_matrix_preflight_sensitive_window_and_budget_breaker(tmp_path: Path) -> None:
    # Sensitive window -> diagnostics + alert + NO breaker strike
    skill, clock, _, _, _, _, _, _, guard, bridge = _harness(tmp_path, safe_guard=False, breaker_failure_threshold=2)
    r1 = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="g1"))
    assert r1.failure == ParasiteFailure.PREFLIGHT_SENSITIVE_WINDOW
    assert r1.diagnostics_path is not None and r1.diagnostics_path.is_file()
    assert len(bridge.events) == 1
    assert skill.is_available() is True  # No breaker strike

    # Budget exhaustion -> log only (no diag file, no alert, no breaker strike)
    guard.safe = True
    skill2, _, _, win2, _, kbd2, _, _, _, bridge2 = _harness(tmp_path / "b", max_invocations_per_episode=1)
    assert skill2.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="ok")).ok is True
    r_budget = skill2.invoke(ParasiteRequest(phase=ParasitePhase.REACTIVE_RECOVERY, user_goal="g2"))
    assert r_budget.failure == ParasiteFailure.BUDGET_EXHAUSTED
    assert r_budget.diagnostics_path is None
    assert bridge2.events == []

    # Breaker trips after threshold and resets after cooldown
    skill3, clk3, _, win3, _, _, _, _, _, bridge3 = _harness(
        tmp_path / "brk", breaker_failure_threshold=2, breaker_cooldown_sec=50.0
    )
    win3.switch_on_alt_g_to = None  # causes FOCUS_TIMEOUT
    assert skill3.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="g1")).failure == ParasiteFailure.FOCUS_TIMEOUT
    assert skill3.is_available() is True
    assert skill3.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="g2")).failure == ParasiteFailure.FOCUS_TIMEOUT
    assert skill3.is_available() is False
    r_open = skill3.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="g3"))
    assert r_open.failure == ParasiteFailure.BREAKER_OPEN
    assert r_open.diagnostics_path is None

    clk3.advance(51.0)
    assert skill3.is_available() is True


@pytest.mark.parametrize(
    "fault,expected_failure,expect_diag,expect_alert,expect_min_gemini",
    [
        ("capture", ParasiteFailure.CAPTURE_FAILED, True, True, False),
        ("hotkey", ParasiteFailure.HOTKEY_INTERRUPTED, True, False, False),
        ("focus_timeout", ParasiteFailure.FOCUS_TIMEOUT, True, True, False),
        ("identity_mismatch", ParasiteFailure.WINDOW_IDENTITY_MISMATCH, True, True, False),
        ("no_caret", ParasiteFailure.CARET_NOT_ACQUIRED, True, True, True),
        ("clip_lock", ParasiteFailure.CLIPBOARD_LOCKED, True, True, True),
        ("dib_pack", ParasiteFailure.DIB_PACK_FAILED, True, True, True),
        ("paste_fail", ParasiteFailure.PASTE_INTERRUPTED, True, True, True),
        ("submit_fail", ParasiteFailure.SUBMIT_INTERRUPTED, True, True, True),
        ("gen_timeout", ParasiteFailure.GENERATION_TIMEOUT, True, True, True),
        ("copy_missing", ParasiteFailure.COPY_BUTTON_NOT_FOUND, True, True, True),
        ("harvest_empty", ParasiteFailure.HARVEST_TIMEOUT, True, True, True),
        ("bad_tags", ParasiteFailure.TAGS_MISSING, True, True, True),
    ],
)
def test_matrix_all_runtime_failures_and_teardown(
    tmp_path: Path,
    fault: str,
    expected_failure: ParasiteFailure,
    expect_diag: bool,
    expect_alert: bool,
    expect_min_gemini: bool,
) -> None:
    skill, _, _, win, clip, kbd, mouse, cap, _, bridge = _harness(tmp_path / fault)

    if fault == "capture":
        cap.raise_on_screen = True
    elif fault == "hotkey":
        kbd.fail_on = ("alt", "g")
    elif fault == "focus_timeout":
        win.switch_on_alt_g_to = None
    elif fault == "identity_mismatch":
        win.switch_on_alt_g_to = win.unknown_hwnd
    elif fault == "no_caret":
        win.caret_ready = False
    elif fault == "clip_lock":
        clip.fail_lock = True
    elif fault == "dib_pack":
        clip.fail_dib = True
    elif fault == "paste_fail":
        kbd.fail_on = ("ctrl", "v")
    elif fault == "submit_fail":
        kbd.fail_on = ("enter",)
    elif fault == "gen_timeout":
        win.stop_pos = (900, 720)
    elif fault == "copy_missing":
        # Stop absent & copy present until generation stabilizes (polls 1..3), vanish at Step 10 harvest
        call_count = [0]
        orig_find = win.find_uia_button

        def vanishing_copy(hwnd, names, pick_last=True):
            if "copy" in [n.lower() for n in names]:
                call_count[0] += 1
                return None if call_count[0] >= 4 else (950, 720)
            return orig_find(hwnd, names, pick_last)

        win.find_uia_button = vanishing_copy  # type: ignore[method-assign]
    elif fault == "harvest_empty":
        mouse.response_factory = lambda _: ""
    elif fault == "bad_tags":
        mouse.response_factory = lambda _: "Plain text without any tags"

    res = skill.invoke(
        ParasiteRequest(
            phase=ParasitePhase.REACTIVE_RECOVERY,
            user_goal="Recover dialog",
            trigger=RecoveryTrigger.OSCILLATION,
        )
    )
    assert res.ok is False
    assert res.failure == expected_failure
    if expect_diag:
        assert res.diagnostics_path is not None and res.diagnostics_path.is_file()
    if expect_alert:
        assert len(bridge.events) == 1
        assert bridge.events[0].kind == "parasite_skill_alert"
    else:
        assert bridge.events == []

    # Never minimize unknown window on identity mismatch; never click Copy when absent
    if fault == "identity_mismatch":
        assert win.unknown_hwnd not in win.minimized_hwnds
    elif expect_min_gemini:
        assert win.gemini_hwnd in win.minimized_hwnds
    if fault == "copy_missing":
        assert mouse.clicks == []


def test_mid_generation_cancellation_aborts_immediately_and_invoke_never_raises(tmp_path: Path) -> None:
    skill, _, _, win, _, _, _, cap, _, bridge = _harness(tmp_path)
    win.stop_pos = (900, 720)
    token = threading.Event()
    gen_polls = [0]
    orig_find = win.find_uia_button

    def cancel_mid_generation(hwnd, names, pick_last=True):
        if "stop response" in [n.lower() for n in names]:
            gen_polls[0] += 1
            if gen_polls[0] >= 2:
                token.set()
        return orig_find(hwnd, names, pick_last)

    win.find_uia_button = cancel_mid_generation  # type: ignore[method-assign]
    res = skill.invoke(
        ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Do work"),
        cancellation_token=token,
    )
    assert res.ok is False
    assert res.failure == ParasiteFailure.INTERRUPTED
    assert gen_polls[0] == 2
    assert bridge.events == []

    # Unexpected internal error is caught cleanly -> never raises
    win.get_foreground_hwnd = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    res2 = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Crash test"))
    assert res2.ok is False
    assert res2.failure == ParasiteFailure.UNEXPECTED_ERROR


def test_os_environment_discovery_collects_stems_registry_and_filters_sensitive(
    tmp_path: Path, monkeypatch
) -> None:
    start_dir = tmp_path / "Programs"
    (start_dir / "Media").mkdir(parents=True)
    (start_dir / "Media" / "Audacity.lnk").write_bytes(b"lnk")
    (start_dir / "Media" / "Uninstall Audacity.lnk").write_bytes(b"lnk")

    guard = WindowGuard(config=SafetyConfig())

    monkeypatch.setattr(
        "parasite_ai.mind.verifier.get_live_windows",
        lambda include_empty_titles=False: [
            {"hwnd": 1, "process_name": "explorer.exe", "title": "Downloads", "is_minimized": False},
            {"hwnd": 2, "process_name": "keepass.exe", "title": "Vault.kdbx - KeePass", "is_minimized": False},
            {"hwnd": 3, "process_name": "notepad.exe", "title": "Minimized", "is_minimized": True},
        ],
    )
    disc = Win32EnvironmentDiscovery(
        window_guard=guard,
        shortcut_roots=[start_dir],
        registry_names_fn=lambda: ["ffmpeg", "Audacity", "chrome"],
    )
    open_wins, avail = disc.collect(max_programs=40, max_windows=15)
    assert open_wins == ["explorer.exe: Downloads"]  # KeePass sensitive & minimized filtered
    assert avail == ["Audacity", "chrome", "ffmpeg"]


# ---------------------------------------------------------------------------
# Stage P4.4.1: Untitled Chrome Overlay, Toggle Safety & Hybrid Local Assist
# ---------------------------------------------------------------------------

def test_untitled_chrome_overlay_verified_via_uia_and_reuses_open_window(tmp_path: Path) -> None:
    skill, _, log, win, _, _, mouse, _, _, _ = _harness(tmp_path)
    win.title_map[win.gemini_hwnd] = ""  # Chrome Alt+G floating widget has empty Win32 title

    uia_queries: List[List[str]] = []
    dismissed: List[int] = []

    def _find_uia_text(hwnd: int, sigs: List[str], max_nodes: int = 250) -> Optional[str]:
        uia_queries.append(list(sigs))
        return "ask away" if hwnd == win.gemini_hwnd else None

    # 1. Closed initially -> Alt+G spawns untitled Chrome overlay -> Stage 2 UIA matches cleanly
    win.list_candidate_windows = lambda procs: []  # type: ignore[attr-defined]
    win.find_uia_text_match = _find_uia_text  # type: ignore[attr-defined]
    win.dismiss_window = lambda hwnd, toggle_hotkey_fn=None: dismissed.append(hwnd) or True  # type: ignore[attr-defined]

    res1 = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Open doc"))
    assert res1.ok is True
    assert res1.identity_mode == "uia_overlay"
    assert res1.rescued_by == "uia_overlay"
    assert dismissed == [win.gemini_hwnd]
    assert len(uia_queries) >= 1

    # 2. Already visible on screen -> focuses directly WITHOUT sending toggle hotkey Alt+G
    log.clear()
    win.fg_hwnd = win.prior_hwnd
    win.list_candidate_windows = lambda procs: [{"hwnd": win.gemini_hwnd, "process_name": "chrome.exe", "title": ""}]  # type: ignore[attr-defined]
    res2 = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Already open"))
    assert res2.ok is True
    assert "hotkey:alt+g" not in log
    assert win.gemini_hwnd in win.focused_hwnds


def test_spawned_chrome_overlay_hwnd_delta_and_fail_closed_guards(tmp_path: Path) -> None:
    skill, _, _, win, _, _, _, _, _, _ = _harness(tmp_path)
    win.title_map[win.gemini_hwnd] = ""
    # Foreground stays stuck on prior_hwnd even after Alt+G, while Chrome popup spawns cleanly
    win.switch_on_alt_g_to = None
    calls = {"n": 0}

    def _cand_windows(procs: List[str]):
        calls["n"] += 1
        # Call 1: pre_existing scan; Call 2: pre_hotkey snapshot; Call 3+: post-hotkey HWND delta!
        if calls["n"] <= 2:
            return []
        return [{"hwnd": win.gemini_hwnd, "process_name": "chrome.exe", "title": ""}]

    win.list_candidate_windows = _cand_windows  # type: ignore[attr-defined]
    win.find_uia_text_match = lambda hwnd, sigs: "gemini" if hwnd == win.gemini_hwnd else None  # type: ignore[attr-defined]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Spawn delta"))
    assert res.ok is True
    assert res.identity_mode == "uia_overlay"

    # Non-generic titled Chrome tab (e.g. "Banking - Google Chrome") or untitled without UIA/assist MUST fail closed
    skill2, _, _, win2, _, _, _, _, _, _ = _harness(tmp_path / "strict")
    win2.title_map[win2.gemini_hwnd] = "Banking - Google Chrome"
    win2.find_uia_text_match = lambda hwnd, sigs: "gemini"  # type: ignore[attr-defined]
    res_tab = skill2.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Unsafe tab"))
    assert res_tab.ok is False
    assert res_tab.failure == ParasiteFailure.WINDOW_IDENTITY_MISMATCH
    assert win2.gemini_hwnd not in win2.minimized_hwnds


def test_step5_composer_focus_assist_and_step10_local_assist_copy_rescue(tmp_path: Path) -> None:
    class _FakeAssist:
        def __init__(self, out_of_bounds: bool = False) -> None:
            self.out_of_bounds = out_of_bounds
            self.copy_calls = 0
            self.input_calls = 0

        def verify_gemini_surface(self, hwnd, rect, signatures):
            return False, "none"

        def locate_input_box(self, hwnd, rect, input_names):
            self.input_calls += 1
            return (1500, 1500, "local_vlm") if self.out_of_bounds else (220, 740, "screen_grounder")

        def locate_copy_button(self, hwnd, rect, copy_names):
            self.copy_calls += 1
            return (1500, 1500, "local_vlm") if self.out_of_bounds else (860, 700, "local_vlm")

    # Happy fallback rescue: caret blind (False), UIA Copy missing (None) -> rescued inside win_rect (50,50,900,800)
    assist_ok = _FakeAssist(out_of_bounds=False)
    skill, _, log, win, _, _, mouse, _, _, _ = _harness(tmp_path / "ok")
    skill.local_assist = assist_ok
    # Step 5 clicks composer before query submission; only emit Gemini response once query text exists
    orig_factory = mouse.response_factory
    mouse.response_factory = lambda q: orig_factory(q) if q.strip() else ""  # type: ignore[misc]
    win.caret_ready = False
    win.copy_pos = None

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Rescue me"))
    assert res.ok is True
    assert assist_ok.input_calls == 1
    assert assist_ok.copy_calls == 1
    assert (220, 740) in mouse.clicks
    assert (860, 700) in mouse.clicks
    assert res.rescued_by is not None

    # Out-of-window bounds assist point MUST be rejected fail-closed (never blind click outside gemini_hwnd)
    assist_bad = _FakeAssist(out_of_bounds=True)
    skill2, _, _, win2, _, _, mouse2, _, _, _ = _harness(tmp_path / "oob")
    skill2.local_assist = assist_bad
    win2.caret_ready = False
    res_bad = skill2.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="OOB check"))
    assert res_bad.ok is False
    assert res_bad.failure == ParasiteFailure.CARET_NOT_ACQUIRED
    assert mouse2.clicks == []


def test_hybrid_local_assist_crop_clamping_and_zero_numerical_anchoring() -> None:
    import re
    from types import SimpleNamespace
    from parasite_ai.mind.memory import ActionPlan, ActionType
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    captured_prompts: List[str] = []

    class _FakeGrounder:
        def __init__(self, elems):
            self._elems = elems

        def ground(self, **kwargs):
            return list(self._elems)

    class _FakeCapturer:
        def capture_rect(self, rect_wh):
            _, _, w, h = rect_wh
            return np.zeros((h, w, 3), dtype=np.uint8)

    class _FakeBrain:
        def __init__(self, px: int, py: int, surface_reply: str = "YES") -> None:
            self.px = px
            self.py = py
            self.surface_reply = surface_reply

        def supports_vision(self) -> bool:
            return True

        def generate(self, *, prompt: str, system_prompt: str = "", **kwargs) -> str:
            captured_prompts.append(f"{system_prompt}\n{prompt}")
            return self.surface_reply

        def generate_cua_step(self, *, user_goal: str, system_prompt: str = "", screen_width: int = 0, screen_height: int = 0, **kwargs):
            captured_prompts.append(f"{system_prompt}\n{user_goal}")
            assert (screen_width, screen_height) == (400, 600)
            return ("located", ActionPlan(action=ActionType.CLICK, coordinates=(self.px, self.py), reasoning="crop click"))

    win_rect = (1000, 200, 1400, 800)  # crop size = (400, 600)
    # Tier 2 filters out-of-rect OCR hits cleanly and resolves in-rect OCR hits without calling VLM
    in_rect_el = SimpleNamespace(label="Ask away", center_x=1150, center_y=280)
    oob_el = SimpleNamespace(label="Copy", center_x=200, center_y=200)
    assist_ocr = HybridLocalAssistBackend(
        screen_grounder=_FakeGrounder([oob_el, in_rect_el]),
        brain_manager=_FakeBrain(2, 598),
        capturer=_FakeCapturer(),
    )
    ok_surf, tier = assist_ocr.verify_gemini_surface(202, win_rect, ["ask away"])
    assert ok_surf is True and tier == "screen_grounder"
    # Out-of-rect OCR "Copy" ignored -> falls back to Tier 3 VLM inside crop (lx=2, ly=598 -> clamped >=4, <=h-5)
    loc_send = assist_ocr.locate_send_button(202, win_rect, ["Send"])
    assert loc_send == (1000 + 4, 200 + 595, "local_vlm")
    assist_copy_clamp = HybridLocalAssistBackend(
        screen_grounder=_FakeGrounder([oob_el, in_rect_el]),
        brain_manager=_FakeBrain(2, 450),
        capturer=_FakeCapturer(),
    )
    loc_copy = assist_copy_clamp.locate_copy_button(202, win_rect, ["Copy"])
    assert loc_copy == (1000 + 4, 200 + 450, "local_vlm")

    # Verify VLM out-of-crop hallucination is rejected fail-closed & prompt contains zero concrete coords (§8.3)
    assist_bad_vlm = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_FakeBrain(999, 999, surface_reply="NO"),
        capturer=_FakeCapturer(),
    )
    assert assist_bad_vlm.verify_gemini_surface(202, win_rect, ["ask away"]) == (False, "none")
    assert assist_bad_vlm.locate_input_box(202, win_rect, ["Ask Gemini"]) is None

    # No prompt passed to VLM may contain literal digits/coordinates (§8.3 strict zero anchoring)
    assert len(captured_prompts) >= 3
    for p in captured_prompts:
        assert not re.search(r"\d", p), f"Found unexpected numeric digit in crop VLM prompt: {p}"


# ---------------------------------------------------------------------------
# Stage P4.4.2: Verified Send-Button Submission, Generation Gate & Spatial Exclusion
# ---------------------------------------------------------------------------

def test_step8_send_button_click_fallback_and_send_copy_spatial_exclusion(tmp_path: Path) -> None:
    class _SendAndCopyAssist:
        def __init__(self) -> None:
            self.send_calls = 0
            self.copy_calls = 0
            self.seen_excludes: List[Optional[List[Tuple[int, int]]]] = []

        def verify_gemini_surface(self, hwnd, rect, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, rect, input_names):
            return None

        def locate_send_button(self, hwnd, rect, send_names):
            self.send_calls += 1
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, rect, copy_names, exclude_points=None):
            self.copy_calls += 1
            self.seen_excludes.append(list(exclude_points) if exclude_points else None)
            if self.copy_calls == 1:
                # Near Send button (dist < 40 px) -> MUST be rejected by ParasiteSkill!
                return (825, 755, "local_vlm")
            return (600, 620, "local_vlm")

    skill, _, log, win, _, _, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.4,
        min_generation_wait_ms=300,
    )
    assist = _SendAndCopyAssist()
    skill.local_assist = assist
    win.copy_pos = None

    # Static win_frame makes Enter leave composer unchanged -> triggers Send click ->
    # after Send click at (820, 760), win_frame mutates on generation and Copy is found at (600, 620).
    submitted_flag = {"done": False}
    orig_click = mouse.click
    orig_capture_rect = cap.capture_rect

    def _click_and_mutate(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        if (x, y) == (820, 760):
            submitted_flag["done"] = True
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    def _capture_rect_mutate(rect_wh):
        frame = orig_capture_rect(rect_wh).copy()
        if submitted_flag["done"]:
            frame[80:360, 40:440] = 235
        return frame

    mouse.click = _click_and_mutate  # type: ignore[method-assign]
    cap.capture_rect = _capture_rect_mutate  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Send fallback"))
    assert res.ok is True
    assert assist.send_calls == 1
    assert assist.copy_calls == 2
    assert assist.seen_excludes == [[(820, 760)], [(820, 760)]]
    assert res.submit_method == "send_button:local_vlm"
    assert (820, 760) in mouse.clicks
    assert (825, 755) not in mouse.clicks
    assert (600, 620) in mouse.clicks
    assert mouse.clicks.index((820, 760)) < mouse.clicks.index((600, 620))


def test_hybrid_local_assist_wait_action_returns_none_and_diagnostic_png_on_harvest_timeout(
    tmp_path: Path,
) -> None:
    import re
    from parasite_ai.mind.memory import ActionPlan, ActionType
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    captured_prompts: List[str] = []

    class _FakeCapturer:
        def capture_rect(self, rect_wh):
            _, _, w, h = rect_wh
            return np.zeros((h, w, 3), dtype=np.uint8)

    class _WaitBrain:
        def supports_vision(self) -> bool:
            return True

        def generate_cua_step(
            self,
            *,
            user_goal: str,
            system_prompt: str = "",
            screen_width: int = 0,
            screen_height: int = 0,
            **kwargs,
        ):
            captured_prompts.append(f"{system_prompt}\n{user_goal}")
            return (
                "not visible",
                ActionPlan(action=ActionType.WAIT, coordinates=None, reasoning="not present"),
            )

    assist = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_WaitBrain(),
        capturer=_FakeCapturer(),
    )
    win_rect = (100, 100, 500, 700)
    assert assist.locate_send_button(202, win_rect, ["Send message"]) is None
    assert assist.locate_copy_button(202, win_rect, ["Copy response"]) is None
    # Locate Copy button with direct exclusion filters near Send even from OCR/Mock
    assert len(captured_prompts) == 2
    for p in captured_prompts:
        assert not re.search(r"\d", p), f"Found unexpected digit in VLM prompt: {p}"

    # Verify HARVEST_TIMEOUT writes companion .png failure frame and JSON submit_method metadata
    skill, _, _, win, _, _, mouse, _, _, _ = _harness(tmp_path)
    mouse.response_factory = lambda _: ""
    res = skill.invoke(
        ParasiteRequest(phase=ParasitePhase.REACTIVE_RECOVERY, user_goal="Timeout diag")
    )
    assert res.ok is False
    assert res.failure == ParasiteFailure.HARVEST_TIMEOUT
    assert res.diagnostics_path is not None and res.diagnostics_path.is_file()
    payload = json.loads(res.diagnostics_path.read_text(encoding="utf-8"))
    assert payload.get("submit_method") == "enter"
    assert Path(payload["failure_frame_path"]).is_file()


# ---------------------------------------------------------------------------
# Stage P4.4.3: 1:1 VLM Crop Padding, Thought Guard, Multi-Tick Submit & Scroll
# ---------------------------------------------------------------------------

def test_pad_crop_for_vlm_preserves_1to1_coords_and_rejects_thought_contradiction_and_clamped_oob() -> None:
    import re
    from parasite_ai.mind.memory import ActionPlan, ActionType
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend
    from parasite_ai.mind.uitars_parser import parse_uitars_action

    small_crop = np.full((655, 414, 3), 90, dtype=np.uint8)
    small_crop[12, 34] = (201, 102, 53)
    padded = HybridLocalAssistBackend._pad_crop_for_vlm(small_crop)
    assert padded.shape == (896, 896, 3)
    assert padded.shape[0] % 28 == 0 and padded.shape[1] % 28 == 0
    assert (padded.shape[0] * padded.shape[1]) // (28 * 28) >= 1024
    assert tuple(int(v) for v in padded[12, 34]) == (201, 102, 53)
    assert tuple(int(v) for v in padded[700, 500]) == (0, 0, 0)

    captured_prompts: List[str] = []

    class _FakeCapturer:
        def capture_rect(self, rect_wh):
            _, _, w, h = rect_wh
            return np.full((h, w, 3), 40, dtype=np.uint8)

    class _MockThoughtAndOobBrain:
        def __init__(self, mode: str) -> None:
            self.mode = mode

        def supports_vision(self) -> bool:
            return True

        def generate_cua_step(
            self,
            *,
            user_goal: str,
            system_prompt: str = "",
            screen_width: int = 0,
            screen_height: int = 0,
            image_base64: Optional[str] = None,
            **kwargs,
        ):
            captured_prompts.append(f"{system_prompt}\n{user_goal}")
            assert image_base64 is not None and image_base64.startswith("data:image/jpeg;base64,")
            if self.mode == "send_thought":
                return (
                    'I see the blue circular button with an upward arrow. This is the "Send" button.',
                    ActionPlan(action=ActionType.CLICK, coordinates=(200, 500), reasoning="click send"),
                )
            # Simulate parse_uitars_action clamping an out-of-crop (665, 1055) coordinate to (cw - 1, ch - 1)
            _, parsed = parse_uitars_action(
                "Thought: clicking bottom right\nAction: click(start_box='(665,1055)')",
                screen_width=screen_width,
                screen_height=screen_height,
            )
            return ("clicking bottom right", parsed)

    win_rect = (100, 100, 514, 755)  # 414 x 655
    assist_send = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockThoughtAndOobBrain("send_thought"),
        capturer=_FakeCapturer(),
    )
    assert assist_send.locate_copy_button(202, win_rect, ["Copy response"]) is None

    assist_clamped = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockThoughtAndOobBrain("clamped_oob"),
        capturer=_FakeCapturer(),
    )
    assert assist_clamped.locate_copy_button(202, win_rect, ["Copy response"]) is None

    for p in captured_prompts:
        assert not re.search(r"\d", p), f"Found unexpected numeric digit in VLM prompt: {p}"


def test_step8_single_tick_newline_diff_triggers_send_button_click_and_step9_scrolls_to_bottom(
    tmp_path: Path,
) -> None:
    class _SendAndScrollAssist:
        def __init__(self) -> None:
            self.send_calls = 0
            self.copy_calls = 0

        def verify_gemini_surface(self, hwnd, rect, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, rect, input_names):
            return None

        def locate_send_button(self, hwnd, rect, send_names):
            self.send_calls += 1
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, rect, copy_names, exclude_points=None):
            self.copy_calls += 1
            return (600, 620, "local_vlm")

    skill, _, log, win, _, _, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.5,
        min_generation_wait_ms=200,
        scroll_before_copy_attempts=3,
    )
    assist = _SendAndScrollAssist()
    skill.local_assist = assist
    win.copy_pos = None

    state = {"phase": "pre_submit", "scrolled": False}

    # Add scroll capability that mutates the viewport once to reveal bottom Copy button
    scroll_calls: List[Tuple[int, int, int]] = []

    def _scroll(delta: int, x: Optional[int] = None, y: Optional[int] = None, cancellation_token=None) -> bool:
        scroll_calls.append((delta, int(x or 0), int(y or 0)))
        state["scrolled"] = True
        win.copy_pos = (610, 630)
        return True

    mouse.scroll = _scroll  # type: ignore[attr-defined]

    orig_hotkey = skill.keyboard.hotkey

    def _hotkey(*keys: str, cancellation_token=None) -> bool:
        ok = orig_hotkey(*keys, cancellation_token=cancellation_token)
        if tuple(keys) == ("enter",):
            state["phase"] = "post_enter_newline"
        return ok

    skill.keyboard.hotkey = _hotkey  # type: ignore[method-assign]

    orig_click = mouse.click

    def _click(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        if (x, y) == (820, 760):
            state["phase"] = "submitted"
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    mouse.click = _click  # type: ignore[method-assign]

    def _dynamic_rect_frame(rect_wh):
        _, _, w, h = rect_wh
        frame = np.full((h, w, 3), 120, dtype=np.uint8)
        if state["phase"] == "post_enter_newline":
            # Single-tick newline shift inside composer (still <15.0% full diff, static across subsequent ticks)
            frame[h - 60 : h - 40, 20:140] = 200
        elif state["phase"] == "submitted":
            frame[80:300, 40:400] = 220
            if state["scrolled"]:
                frame[320:520, 40:400] = 240
        return frame

    cap.capture_rect = _dynamic_rect_frame  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Newline + Scroll"))
    assert res.ok is True
    assert assist.send_calls == 1
    assert res.submit_method == "send_button:local_vlm"
    assert (820, 760) in mouse.clicks
    assert len(scroll_calls) >= 1
    assert res.scroll_steps >= 1
    assert (610, 630) in mouse.clicks
    assert assist.copy_calls == 0


# ---------------------------------------------------------------------------
# Stage P4.4.4: Composer-Strip Rejection, 1-Bit Caret Flicker & Post-Scroll Fallthrough
# ---------------------------------------------------------------------------


def test_locate_copy_button_rejects_bottom_composer_strip_and_attachment_thoughts() -> None:
    import re
    from parasite_ai.mind.memory import ActionPlan, ActionType
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    captured_prompts: List[str] = []

    class _FakeCapturer:
        def capture_rect(self, rect_wh):
            _, _, w, h = rect_wh
            return np.full((h, w, 3), 50, dtype=np.uint8)

    class _MockComposerBrain:
        def __init__(self, mode: str) -> None:
            self.mode = mode

        def supports_vision(self) -> bool:
            return True

        def generate_cua_step(self, *, user_goal: str, system_prompt: str = "", **kwargs):
            captured_prompts.append(f"{system_prompt}\n{user_goal}")
            if self.mode == "composer_strip":
                return (
                    "I see the button with overlapping rectangles.",
                    ActionPlan(action=ActionType.CLICK, coordinates=(34, 618), reasoning="click"),
                )
            if self.mode == "above_composer_copy":
                return (
                    "I see the Copy response icon with two overlapping rectangles in the action row.",
                    ActionPlan(action=ActionType.CLICK, coordinates=(73, 585), reasoning="click copy"),
                )
            if self.mode == "attachment_thought":
                return (
                    "Clicking the plus icon to add attachments.",
                    ActionPlan(action=ActionType.CLICK, coordinates=(97, 552), reasoning="click"),
                )
            return (
                "I see the Copy response icon with two overlapping rectangles in the action row.",
                ActionPlan(action=ActionType.CLICK, coordinates=(97, 552), reasoning="click copy"),
            )

    win_rect = (100, 100, 514, 755)  # 414 x 655 (bottom composer strip >= 607)

    assist_strip = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockComposerBrain("composer_strip"),
        capturer=_FakeCapturer(),
    )
    assert assist_strip.locate_copy_button(202, win_rect, ["Copy response"]) is None

    assist_attach = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockComposerBrain("attachment_thought"),
        capturer=_FakeCapturer(),
    )
    assert assist_attach.locate_copy_button(202, win_rect, ["Copy response"]) is None

    assist_valid = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockComposerBrain("valid_copy"),
        capturer=_FakeCapturer(),
    )
    assert assist_valid.locate_copy_button(202, win_rect, ["Copy response"]) == (197, 652, "local_vlm")

    assist_above_composer = HybridLocalAssistBackend(
        screen_grounder=None,
        brain_manager=_MockComposerBrain("above_composer_copy"),
        capturer=_FakeCapturer(),
    )
    assert assist_above_composer.locate_copy_button(202, win_rect, ["Copy response"]) == (173, 685, "local_vlm")

    for p in captured_prompts:
        assert not re.search(r"\d", p), f"Found unexpected numeric digit in VLM prompt: {p}"


def test_step9_ignores_single_bit_dhash_caret_flicker_and_falls_through_after_scroll(
    tmp_path: Path,
) -> None:
    from parasite_ai.mind.memory import compute_dhash, hamming_distance

    class _FlickerAssist:
        def __init__(self) -> None:
            self.send_calls = 0
            self.copy_calls = 0

        def verify_gemini_surface(self, hwnd, rect, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, rect, input_names):
            return None

        def locate_send_button(self, hwnd, rect, send_names):
            self.send_calls += 1
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, rect, copy_names, exclude_points=None):
            self.copy_calls += 1
            return (600, 620, "local_vlm")

    skill, _, _, win, _, _, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.5,
        min_generation_wait_ms=200,
        scroll_before_copy_attempts=3,
    )
    assist = _FlickerAssist()
    skill.local_assist = assist
    win.copy_pos = None

    state = {"phase": "pre_submit", "scrolled": False, "tick": 0}
    scroll_calls: List[int] = []

    def _scroll(delta: int, x=None, y=None, cancellation_token=None) -> bool:
        scroll_calls.append(delta)
        state["scrolled"] = True
        return True

    mouse.scroll = _scroll  # type: ignore[attr-defined]

    orig_click = mouse.click

    def _click(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        if (x, y) == (820, 760):
            state["phase"] = "submitted"
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    mouse.click = _click  # type: ignore[method-assign]

    def _build_flicker_frame(w: int, h: int, caret_on: bool, *, submitted: bool, scrolled: bool) -> np.ndarray:
        frame = np.full((h, w, 3), 120, dtype=np.uint8)
        if submitted:
            frame[80:300, 40:400] = 220
        if scrolled:
            frame[320:520, 40:400] = 240
        # Tiny 2px caret toggle in bottom composer (<0.4 frame diff, 1-2 bit dHash flip)
        if caret_on:
            frame[h - 32 : h - 24, 90:94] = 255
        return frame

    # Verify our synthetic caret flicker actually causes <= 2 bit dHash flip with < 0.4 frame diff
    f_off = _build_flicker_frame(414, 655, False, submitted=True, scrolled=False)
    f_on = _build_flicker_frame(414, 655, True, submitted=True, scrolled=False)
    assert skill._frame_diff_score(f_on, f_off) < 0.4
    assert hamming_distance(compute_dhash(f_on), compute_dhash(f_off)) <= 2

    def _capture_rect(rect_wh):
        _, _, w, h = rect_wh
        state["tick"] += 1
        caret_on = (state["tick"] % 2) == 1
        return _build_flicker_frame(
            w,
            h,
            caret_on=caret_on,
            submitted=(state["phase"] == "submitted"),
            scrolled=state["scrolled"],
        )

    cap.capture_rect = _capture_rect  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Caret Flicker"))
    assert res.ok is True
    assert assist.send_calls == 1
    assert len(scroll_calls) >= 1
    assert assist.copy_calls == 1
    assert (600, 620) in mouse.clicks


# ---------------------------------------------------------------------------
# Stage P4.4.5: CentroidSnapper Send, Zero-Digit Prompts, 64-Bit UIA & Closed-Loop Copy Masking
# ---------------------------------------------------------------------------

def test_send_centroid_snap_and_step10_closed_loop_copy_requery_with_exclude_masking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes
    from ctypes import wintypes
    import math
    import re
    from parasite_ai.mind.memory import ActionType
    from parasite_ai.mind.parasite_skill import GeminiWindowBackend, HybridLocalAssistBackend

    # 1. Verify 64-bit WPARAM(0) / LPARAM(-4) arguments in GeminiWindowBackend.awaken_accessibility
    sent_msgs: List[Tuple[Any, Any]] = []

    class _FakeUser32:
        def EnumChildWindows(self, hwnd, cb, lparam):
            return True

        def SendMessageTimeoutW(self, hwnd, msg, wparam, lparam, flags, timeout, res):
            sent_msgs.append((wparam, lparam))
            return 1

    class _FakeOleacc:
        def AccessibleObjectFromWindow(self, hwnd, objid, riid, ppv):
            return 0

    fake_windll = type("FakeWindll", (), {"user32": _FakeUser32(), "oleacc": _FakeOleacc()})()
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)
    GeminiWindowBackend().awaken_accessibility(12345)
    assert len(sent_msgs) == 1
    assert isinstance(sent_msgs[0][0], wintypes.WPARAM) and sent_msgs[0][0].value == 0
    assert isinstance(sent_msgs[0][1], wintypes.LPARAM) and sent_msgs[0][1].value == -4

    # 2. Verify HybridLocalAssistBackend: CentroidSnapper on Send, zero-digit prompts, and exclude_points 12px mask
    rect = (100, 100, 514, 755)  # 414 x 655
    crop_img = np.full((655, 414, 3), 245, dtype=np.uint8)
    # Render high-contrast 34x34 Send button centered at local (378, 619)
    crop_img[602:636, 361:395] = (40, 100, 220)
    # Render high-contrast Copy icon at local (97, 533) and adjacent icon at local (121, 533)
    crop_img[525:541, 89:105] = (40, 40, 40)
    crop_img[525:541, 113:129] = (40, 40, 40)

    class _FakeCap:
        def capture_rect(self, r):
            return crop_img.copy()

    seen_prompts: List[str] = []
    seen_frames: List[np.ndarray] = []

    class _FakeBrain:
        def __init__(self) -> None:
            self.calls = 0

        def supports_vision(self) -> bool:
            return True

        def generate_cua_step(
            self,
            *,
            user_goal: str,
            screen_frame: np.ndarray,
            image_base64=None,
            screen_width=0,
            screen_height=0,
            system_prompt: str = "",
            max_tokens: int = 128,
            temperature: float = 0.05,
        ):
            self.calls += 1
            seen_prompts.append(f"{system_prompt}\n{user_goal}")
            seen_frames.append(screen_frame.copy())
            if self.calls == 1:
                # Near-miss Send 28px above (378, 619) -> CentroidSnapper must pull to (378, 619)
                plan = type("Plan", (), {"action": ActionType.CLICK, "coordinates": (378, 591), "reasoning": ""})()
                return "Blue send button", plan
            if self.calls == 2:
                plan = type("Plan", (), {"action": ActionType.CLICK, "coordinates": (121, 533), "reasoning": ""})()
                return "Action row icon", plan
            plan = type("Plan", (), {"action": ActionType.CLICK, "coordinates": (97, 533), "reasoning": ""})()
            return "Copy response icon", plan

    brain = _FakeBrain()
    assist = HybridLocalAssistBackend(brain_manager=brain, capturer=_FakeCap())

    send_loc = assist.locate_send_button(1, rect, ["Send"])
    assert send_loc is not None
    # Snapped from local (378, 591) into button contour (screen x=478, y near 719)
    assert send_loc[0] in (477, 478)
    assert 712 <= send_loc[1] <= 726

    # Copy Attempt 1 (unmasked) -> ~(221, 633)
    copy_1 = assist.locate_copy_button(1, rect, ["Copy"])
    assert copy_1 is not None and copy_1[2] == "local_vlm"
    assert math.hypot(copy_1[0] - 221, copy_1[1] - 633) <= 2.0
    # Copy Attempt 2 (exclude_points=[copy_1[:2]]) -> 12px blackout mask applied at local (121, 533)
    copy_2 = assist.locate_copy_button(1, rect, ["Copy"], exclude_points=[copy_1[:2]])
    assert copy_2 is not None and copy_2[2] == "local_vlm"
    assert math.hypot(copy_2[0] - 197, copy_2[1] - 633) <= 6.0
    assert seen_frames[2][533, 121].tolist() == [0, 0, 0]
    assert "add tabs" not in seen_prompts[1].lower()
    for p in seen_prompts:
        assert not re.search(r"\d", p), f"Found unexpected numeric digit in VLM prompt: {p}"

    # 3. Verify Step 10 closed-loop re-query on harvest miss in ParasiteSkill.invoke
    skill, _, _, win, clip, _, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.3,
        min_generation_wait_ms=100,
        max_local_assist_calls_per_invoke=3,
    )
    win.copy_pos = None

    class _ClosedLoopCopyAssist:
        def __init__(self) -> None:
            self.copy_excludes: List[Optional[List[Tuple[int, int]]]] = []

        def verify_gemini_surface(self, hwnd, r, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, r, input_names):
            return None

        def locate_send_button(self, hwnd, r, send_names, exclude_points=None):
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, r, copy_names, exclude_points=None):
            self.copy_excludes.append(list(exclude_points) if exclude_points else None)
            if not exclude_points or (621, 633) not in exclude_points:
                return (621, 633, "local_vlm")
            return (597, 633, "local_vlm")

    cl_assist = _ClosedLoopCopyAssist()
    skill.local_assist = cl_assist

    orig_click = mouse.click
    orig_cap = cap.capture_rect
    submitted = {"ok": False}

    def _cl_click(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        if (x, y) == (820, 760):
            submitted["ok"] = True
            return True
        if (x, y) == (621, 633):
            # Wrong icon clicked -> do NOT populate clipboard
            mouse.clicks.append((int(x), int(y)))
            return True
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    def _cl_cap(r):
        fr = orig_cap(r).copy()
        if submitted["ok"]:
            fr[80:360, 40:440] = 235
        return fr

    mouse.click = _cl_click  # type: ignore[method-assign]
    cap.capture_rect = _cl_cap  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Closed loop copy"))
    assert res.ok is True
    assert (621, 633) in mouse.clicks
    assert (597, 633) in mouse.clicks
    assert len(cl_assist.copy_excludes) == 2
    assert (621, 633) in (cl_assist.copy_excludes[1] or [])


def test_write_diagnostics_embeds_forensic_only_metadata(tmp_path: Path) -> None:
    import json
    import parasite_ai

    skill, *_ = _harness(tmp_path)
    diag_path = skill._write_diagnostics(
        phase=ParasitePhase.PROACTIVE_PLAN,
        trigger="unit_test",
        nonce="TESTNONCE",
        failure=ParasiteFailure.HARVEST_TIMEOUT,
        detail="forensic metadata check",
        transitions=["HARVESTING"],
        prior_hwnd=1,
        gemini_hwnd=2,
        failure_frame=np.zeros((20, 20, 3), dtype=np.uint8),
    )
    assert diag_path is not None and diag_path.is_file()
    payload = json.loads(diag_path.read_text(encoding="utf-8"))
    assert payload["app_version"] == parasite_ai.__version__
    assert payload["artifact_role"] == "historical_forensic_debug_only"
    assert payload["coding_spec_prohibited"] is True
    assert Path(payload["failure_frame_path"]).is_file()


# ---------------------------------------------------------------------------
# Stage P4.4.8: Drop Zoom, Step 9 Re-Scroll After Wait & RapidOCR Hover Guard
# ---------------------------------------------------------------------------

def test_step9_resumes_scroll_after_wait_and_rapidocr_hover_tooltip_guard(tmp_path: Path) -> None:
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    # 1. Verify RapidOCR-backed verify_hover_tooltip flags "Bad response" around cursor_pt
    rect = (100, 100, 514, 755)
    crop_img = np.full((655, 414, 3), 245, dtype=np.uint8)

    class _FakeCap:
        def capture_rect(self, r):
            return crop_img.copy()

    ocr_seen_shapes: List[Tuple[int, ...]] = []

    class _FakeGrounder:
        def _get_ocr_engine(self):
            def _ocr(img):
                ocr_seen_shapes.append(img.shape)
                return ([[[[0, 0], [10, 0], [10, 10], [0, 10]], "Bad response", 0.96]], 0.01)
            return _ocr

    assist_ocr = HybridLocalAssistBackend(
        screen_grounder=_FakeGrounder(),
        brain_manager=None,
        capturer=_FakeCap(),
    )
    ok_tip, tip_text = assist_ocr.verify_hover_tooltip(rect, cursor_pt=(150, 678))
    assert ok_tip is False
    assert "Bad response" in tip_text
    assert len(ocr_seen_shapes) == 1 and ocr_seen_shapes[0][0] <= 242

    # 2. Verify Step 9 resets scrolled_since_activity=False after locate_copy_button returns None (wait)
    #    and Step 10 hover guard aborts Redo before clicking Copy.
    skill, _, _, win, _, _, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.3,
        min_generation_wait_ms=100,
        scroll_before_copy_attempts=3,
        max_local_assist_calls_per_invoke=4,
    )
    win.copy_pos = None

    state = {"submitted": False, "scrolls": 0, "hovered": None, "wait_returned": False}
    moved_pts: List[Tuple[int, int]] = []

    class _HoverAndRescrollAssist:
        def __init__(self) -> None:
            self.copy_excludes: List[Optional[List[Tuple[int, int]]]] = []

        def verify_gemini_surface(self, hwnd, r, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, r, input_names):
            return None

        def locate_send_button(self, hwnd, r, send_names, exclude_points=None):
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, r, copy_names, exclude_points=None):
            self.copy_excludes.append(list(exclude_points) if exclude_points else None)
            # First time VLM runs (at 7 scrolls), trailing lines haven't been scrolled yet -> None (wait)
            if state["scrolls"] < 8:
                state["wait_returned"] = True
                return None
            if not exclude_points or (574, 651) not in exclude_points:
                return (574, 651, "local_vlm")
            return (598, 651, "local_vlm")

        def verify_hover_tooltip(self, r, cursor_pt=None):
            if (cursor_pt or state["hovered"]) == (574, 651):
                return False, "Redo"
            return True, "Copy"

    hover_assist = _HoverAndRescrollAssist()
    skill.local_assist = hover_assist

    def _scroll(delta: int, x=None, y=None, cancellation_token=None) -> bool:
        state["scrolls"] += 1
        return True

    def _move_to(x: int, y: int, duration=None, cancellation_token=None) -> bool:
        state["hovered"] = (int(x), int(y))
        moved_pts.append((int(x), int(y)))
        return True

    mouse.scroll = _scroll  # type: ignore[attr-defined]
    mouse.move_to = _move_to  # type: ignore[attr-defined]

    orig_click = mouse.click
    orig_cap = cap.capture_rect

    def _hg_click(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs) -> bool:
        if (x, y) == (820, 760):
            state["submitted"] = True
            return True
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    def _hg_cap(r):
        fr = orig_cap(r).copy()
        if state["submitted"]:
            # First scroll pass stops at band=5; after wait(), trailing lines unlock band=6..9
            cap_band = 9 if state["wait_returned"] else 5
            band = min(cap_band, state["scrolls"])
            fr[80 + band * 20 : 300 + band * 20, 40:440] = 235
        return fr

    mouse.click = _hg_click  # type: ignore[method-assign]
    cap.capture_rect = _hg_cap  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Rescroll and RapidOCR hover guard"))
    assert res.ok is True
    assert state["wait_returned"] is True
    assert state["scrolls"] >= 7  # Resumed scrolling after wait()!
    assert (574, 651) in moved_pts
    assert (574, 651) not in mouse.clicks  # Redo tooltip aborted BEFORE clicking!
    assert (598, 651) in mouse.clicks


def test_focus_gemini_window_retries_after_focusing_chrome_on_first_timeout() -> None:
    from unittest.mock import MagicMock

    cfg = ParasiteSkillConfig(focus_timeout_sec=0.5, poll_interval_ms=50)
    kb = MagicMock()
    kb.hotkey.return_value = True
    win = MagicMock()
    win.get_foreground_hwnd.side_effect = lambda: 300 if kb.hotkey.call_count >= 2 else 100
    win.list_candidate_windows.return_value = [{"hwnd": 200}]
    win.get_window_info.side_effect = lambda h: (
        ("chrome.exe", "New Tab - Google Chrome")
        if h == 200
        else ("chrome.exe", "Gemini in Chrome")
        if h == 300
        else ("notepad.exe", "Untitled - Notepad")
    )
    win.focus_window.return_value = True

    skill = ParasiteSkill(
        config=cfg,
        window_backend=win,
        keyboard_driver=kb,
        mouse_driver=MagicMock(),
        capturer=MagicMock(),
    )
    skill.verify_window_identity = MagicMock(
        side_effect=lambda hwnd, **kw: (
            (True, "chrome.exe", "Gemini in Chrome", "win32_title")
            if hwnd == 300
            else (False, "chrome.exe", "New Tab - Google Chrome", "none")
        )
    )

    transitions: list[str] = []
    hwnd, proc, title, mode, fail, detail = skill.resolve_gemini_window(
        prior_hwnd=100,
        transitions=transitions,
        cancellation_token=None,
    )
    assert fail is None
    assert hwnd == 300
    assert kb.hotkey.call_count == 2
    win.focus_window.assert_called_with(200)







def test_verify_hover_tooltip_requires_positive_copy_token(tmp_path):
    from unittest.mock import MagicMock
    import numpy as np
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    fake_frame = np.zeros((200, 200, 3), dtype=np.uint8)
    capturer = MagicMock()
    capturer.capture_rect.return_value = fake_frame
    grounder = MagicMock()
    # Empty OCR -> must fail closed when require_positive=True
    grounder._get_ocr_engine.return_value = lambda img: ([], None)

    backend = HybridLocalAssistBackend(
        brain_manager=MagicMock(),
        screen_grounder=grounder,
        capturer=capturer,
    )
    ok_empty, _ = backend.verify_hover_tooltip((0, 0, 200, 200), cursor_pt=(100, 100))
    assert ok_empty is False

    # Non-Copy text -> fail closed
    grounder._get_ocr_engine.return_value = lambda img: ([[None, "Good response", 0.9]], None)
    ok_other, _ = backend.verify_hover_tooltip((0, 0, 200, 200), cursor_pt=(100, 100))
    assert ok_other is False

    # Positive Copy tooltip -> pass
    grounder._get_ocr_engine.return_value = lambda img: ([[None, "Copy response", 0.95]], None)
    ok_copy, txt = backend.verify_hover_tooltip((0, 0, 200, 200), cursor_pt=(100, 100))
    assert ok_copy is True
    assert "Copy" in txt


def test_ask_vlm_locate_guards_centroid_snap_distance_and_exclusions() -> None:
    """P4.6.6: _ask_vlm_locate must not let CentroidSnapper drift >32px or pull onto exclude_points."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch
    import numpy as np
    from parasite_ai.mind.memory import ActionPlan, ActionType
    from parasite_ai.mind.parasite_skill import HybridLocalAssistBackend

    crop = np.full((300, 300, 3), 240, dtype=np.uint8)
    crop[60:100, 80:140] = 30
    capturer = MagicMock()
    capturer.capture_rect.return_value = crop

    class _DummyVisionBrain:
        def supports_vision(self) -> bool:
            return True

        def generate_cua_step(self, **kwargs):
            return (
                "Located copy icon",
                ActionPlan(action=ActionType.CLICK, coordinates=(120, 80), reasoning="click"),
            )

    backend = HybridLocalAssistBackend(
        brain_manager=_DummyVisionBrain(),
        screen_grounder=MagicMock(),
        capturer=capturer,
    )

    # 1. Snap drift > 32px must be rejected
    with patch(
        "parasite_ai.vision.grounding.CentroidSnapper.snap_with_details",
        return_value=SimpleNamespace(snapped=True, x=160, y=80),
    ):
        pt_far = backend._ask_vlm_locate(
            (10, 20, 310, 320),
            "Copy button",
            snap_button_contour=True,
        )
    assert pt_far == (130, 100)  # (10 + 120, 20 + 80)

    # 2. Snap within 32px onto excluded point (108, 80) -> screen (118, 100) must be rejected
    with patch(
        "parasite_ai.vision.grounding.CentroidSnapper.snap_with_details",
        return_value=SimpleNamespace(snapped=True, x=108, y=80),
    ):
        pt_excl = backend._ask_vlm_locate(
            (10, 20, 310, 320),
            "Copy button",
            exclude_points=[(118, 100)],
            snap_button_contour=True,
        )
    assert pt_excl == (130, 100)


def test_step10_sends_pagedown_and_retries_after_parasite_plan_tail(tmp_path: Path) -> None:
    """P4.6.6: Step 10 sends real KeyboardDriver.hotkey('pagedown') on </parasite_plan> tooltip abort."""
    skill, _, _, win, _, kb, mouse, cap, _, _ = _harness(
        tmp_path,
        submit_verify_timeout_sec=0.2,
        min_generation_wait_ms=50,
        scroll_before_copy_attempts=2,
        max_local_assist_calls_per_invoke=4,
    )
    win.copy_pos = None

    state = {"submitted": False, "pagedowns": 0}

    class _TailScrollAssist:
        def verify_gemini_surface(self, hwnd, r, signatures):
            return True, "screen_grounder"

        def locate_input_box(self, hwnd, r, input_names):
            return None

        def locate_send_button(self, hwnd, r, send_names, exclude_points=None):
            return (820, 760, "local_vlm")

        def locate_copy_button(self, hwnd, r, copy_names, exclude_points=None):
            if exclude_points and (574, 651) in exclude_points:
                return (598, 651, "local_vlm")
            return (574, 651, "local_vlm")

        def verify_hover_tooltip(self, r, cursor_pt=None):
            if cursor_pt == (574, 651):
                return False, "</parasite_plan>"
            return True, "Copy response"

    skill.local_assist = _TailScrollAssist()

    orig_hotkey = kb.hotkey

    def _track_hotkey(*keys, cancellation_token=None):
        if list(keys) == ["pagedown"]:
            state["pagedowns"] += 1
        return orig_hotkey(*keys, cancellation_token=cancellation_token)

    kb.hotkey = _track_hotkey  # type: ignore[method-assign]
    mouse.move_to = lambda x, y, duration=None, cancellation_token=None: True  # type: ignore[attr-defined]

    orig_click = mouse.click
    orig_cap = cap.capture_rect

    def _click(x=None, y=None, button="left", clicks=1, cancellation_token=None, **kwargs):
        if (x, y) == (820, 760):
            state["submitted"] = True
            return True
        return orig_click(x=x, y=y, button=button, clicks=clicks, cancellation_token=cancellation_token, **kwargs)

    def _cap(r):
        fr = orig_cap(r).copy()
        if state["submitted"]:
            fr[100:260, 40:440] = 235
        return fr

    mouse.click = _click  # type: ignore[method-assign]
    cap.capture_rect = _cap  # type: ignore[method-assign]

    res = skill.invoke(ParasiteRequest(phase=ParasitePhase.PROACTIVE_PLAN, user_goal="Step 10 pagedown retry"))
    assert res.ok is True
    assert state["pagedowns"] >= 1
    assert (574, 651) not in mouse.clicks
    assert (598, 651) in mouse.clicks
