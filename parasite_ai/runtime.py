"""
parasite_ai/runtime.py - Central Runtime Orchestrator & Closed-Loop Runner.

Coordinates the lifecycle and cross-thread communications between:
1. Decoupled UI & C2 Layer (UIBridge, Discord Bot) via pure-Python signals and queues.
2. Cognitive & Hand Execution (DualMindPipeline, Hand Drivers, Screen Grounding,
   LocalBrainManager, EpisodicMemory) on a dedicated background worker thread.
3. Win32 Low-Level Safety Guards (InterruptGuard, WindowGuard) on native hook threads.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from parasite_ai.config import AppConfig
from parasite_ai.hands.keyboard import KeyboardDriver, MockInputBackend
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.mind.app_memory import AppMemory
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodicMemory,
    EpisodeReceipt,
    StepRecord,
    StepRecordSummary,
)
from parasite_ai.mind.offloader import BrowserOffloader
from parasite_ai.mind.parasite_skill import (
    HybridLocalAssistBackend,
    ParasiteSkill,
)
from parasite_ai.mind.plan import StepIntent
from parasite_ai.mind.skills import (
    SkillActionStep,
    SkillActions,
    SkillDefinition,
    SkillLearner,
    SkillParameter,
    SkillPostconditions,
    SkillPreconditions,
    SkillProvenance,
    SkillRegistry,
    SkillState,
    SkillTrigger,
    TraceRecorder,
    Win32ContainerWindowProbe,
)
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.safety.window_guard import WindowGuard
from parasite_ai.ui.bridge import EpisodeEvent, GoalRequest, UIBridge
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder

logger = logging.getLogger("parasite_ai.runtime")

_SLOT_WIN_PATH_RE = re.compile(r"[a-zA-Z]:\\[^\s'\"<>|?*]+")
_SLOT_EXPR_RE = re.compile(r"\d+(?:\.\d+)?(?:\s*[+\-*/]\s*\d+(?:\.\d+)?)+")
_SLOT_QUOTED_RE = re.compile(r"(['\"])(.+?)\1")


def _extract_slot_template(
    goal_norm: str,
    action_steps: List[SkillActionStep],
) -> Tuple[List[SkillParameter], List[str], List[SkillActionStep]]:
    """
    Parameterizes shared Windows paths ({{path}}), arithmetic expressions ({{expr}}),
    and quoted literals ({{text}}) between goal_norm and non-launch TYPE steps.
    """
    if not goal_norm or not action_steps:
        return [], [], list(action_steps)

    eligible_indices: List[int] = []
    for idx, st in enumerate(action_steps):
        if st.verb != "TYPE" or not st.text:
            continue
        if st.intent == StepIntent.LAUNCH_OR_ACTIVATE:
            continue
        if (
            idx > 0
            and action_steps[idx - 1].verb == "HOTKEY"
            and action_steps[idx - 1].keys
            and any(k.lower() == "win" for k in action_steps[idx - 1].keys)
        ):
            continue
        eligible_indices.append(idx)

    if not eligible_indices:
        return [], [], list(action_steps)

    texts: List[Optional[str]] = [st.text for st in action_steps]
    replacements: List[Tuple[int, int, str]] = []
    params: List[SkillParameter] = []
    used_names: set[str] = set()

    def _alloc_name(base: str) -> str:
        if base not in used_names:
            used_names.add(base)
            return base
        n = 2
        while f"{base}_{n}" in used_names:
            n += 1
        cand = f"{base}_{n}"
        used_names.add(cand)
        return cand

    def _overlaps(start: int, end: int) -> bool:
        return any(not (end <= rs or start >= re_) for rs, re_, _ in replacements)

    # 1. Windows paths ({{path}})
    for m in _SLOT_WIN_PATH_RE.finditer(goal_norm):
        gs, ge = m.span()
        if _overlaps(gs, ge):
            continue
        pval = m.group(0)
        pval_low = pval.lower()
        matched_steps = [i for i in eligible_indices if pval_low in (texts[i] or "").lower()]
        if not matched_steps:
            continue
        sname = _alloc_name("path")
        pat_sub = re.compile(re.escape(pval), re.IGNORECASE)
        for i in matched_steps:
            texts[i] = pat_sub.sub(f"{{{{{sname}}}}}", texts[i] or "")
        params.append(SkillParameter(name=sname, description="File or directory path", required=True))
        replacements.append((gs, ge, rf"(?P<{sname}>[A-Za-z]:\\[^\s'\"]+)"))

    # 2. Arithmetic expressions ({{expr}}, whitespace-normalized)
    for m in _SLOT_EXPR_RE.finditer(goal_norm):
        gs, ge = m.span()
        if _overlaps(gs, ge):
            continue
        expr_norm = re.sub(r"\s+", "", m.group(0))
        matched_steps: List[int] = []
        for i in eligible_indices:
            cur_t = texts[i] or ""
            if any(re.sub(r"\s+", "", sm.group(0)) == expr_norm for sm in _SLOT_EXPR_RE.finditer(cur_t)):
                matched_steps.append(i)
        if not matched_steps:
            continue
        sname = _alloc_name("expr")
        for i in matched_steps:
            cur_t = texts[i] or ""
            texts[i] = _SLOT_EXPR_RE.sub(
                lambda sm: f"{{{{{sname}}}}}" if re.sub(r"\s+", "", sm.group(0)) == expr_norm else sm.group(0),
                cur_t,
            )
        params.append(SkillParameter(name=sname, description="Arithmetic expression", required=True))
        replacements.append(
            (gs, ge, rf"(?P<{sname}>\d+(?:\.\d+)?(?:\s*[+\-*/]\s*\d+(?:\.\d+)?)+)")
        )

    # 3. Quoted literals ({{text}})
    for m in _SLOT_QUOTED_RE.finditer(goal_norm):
        gs, ge = m.span()
        if _overlaps(gs, ge):
            continue
        inner = m.group(2).strip()
        if not inner:
            continue
        inner_low = inner.lower()
        matched_steps = [i for i in eligible_indices if inner_low in (texts[i] or "").lower()]
        if not matched_steps:
            continue
        sname = _alloc_name("text")
        pat_sub = re.compile(re.escape(inner), re.IGNORECASE)
        for i in matched_steps:
            texts[i] = pat_sub.sub(f"{{{{{sname}}}}}", texts[i] or "")
        params.append(SkillParameter(name=sname, description="Text literal to enter", required=True))
        replacements.append((gs, ge, rf"['\"]?(?P<{sname}>.+?)['\"]?"))

    if not replacements:
        return [], [], list(action_steps)

    replacements.sort(key=lambda item: item[0])
    parts: List[str] = ["^"]
    cursor = 0
    for rs, re_, frag in replacements:
        gap = goal_norm[cursor:rs]
        if gap:
            parts.append(re.sub(r"(?:\\ )+", r"\\s+", re.escape(gap)))
        parts.append(frag)
        cursor = re_
    tail = goal_norm[cursor:]
    if tail:
        parts.append(re.sub(r"(?:\\ )+", r"\\s+", re.escape(tail)))
    parts.append(r"[.!?,;:]*$")
    pattern = "".join(parts)

    if len(pattern) > 256:
        return [], [], list(action_steps)
    try:
        re.compile(pattern)
    except re.error:
        return [], [], list(action_steps)

    updated_steps = [
        st.model_copy(update={"text": texts[i]}) if texts[i] != st.text else st
        for i, st in enumerate(action_steps)
    ]
    return params, [pattern], updated_steps


class RuntimeOrchestrator:
    """
    Master Runtime Orchestrator binding all ParasiteAI subsystems into a closed loop.
    Coordinates C2 events, background cognition, physical input dispatch, and
    Win32 hardware hook safety with zero Qt event-loop dependencies.
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        bridge: Optional[UIBridge] = None,
        simulation_mode: bool = False,
        headless: bool = False,
        parent: Optional[Any] = None,
        episode_report_path: Optional[str] = None,
    ) -> None:
        self.config = config or AppConfig()
        self.bridge = bridge or UIBridge()
        self.simulation_mode = simulation_mode
        self.headless = headless or getattr(self.config, "headless", False)
        self.auto_exit_on_complete: bool = False
        self.default_max_steps: int = 30
        self.episode_report_path: Optional[str] = episode_report_path
        self.last_episode_receipt: Optional[EpisodeReceipt] = None

        # Operational Flags
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_in_cognitive_step: bool = False
        self._last_single_step_goal: Optional[str] = None
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # 1. Instantiate Safety Guards
        self.interrupt_guard = InterruptGuard(
            cooldown_seconds=self.config.safety.override_pause_duration_sec,
            on_interrupt_callback=self._on_hardware_interrupt,
            on_panic_callback=self._on_hardware_panic,
            on_rearm_callback=self._on_hardware_rearm,
        )
        self.window_guard = WindowGuard(config=self.config.safety)

        # 2. Instantiate Hand Drivers
        self.mouse_driver = MouseDriver(
            config=self.config.hands.mouse,
            reticle_callback=self._on_reticle_requested,
            simulation_mode=self.simulation_mode,
        )
        self.keyboard_driver = KeyboardDriver(
            config=self.config.hands.keyboard,
            backend=MockInputBackend() if self.simulation_mode else None,
        )
        if getattr(self.interrupt_guard, "panic_manager", None) is not None:
            self.interrupt_guard.panic_manager.backend = self.keyboard_driver.backend

        # 3. Instantiate Perception Subsystems
        self.screen_capture = ScreenCapture(
            backend=self.config.vision.capture_backend,
            monitor_index=getattr(self.config.vision, "monitor_index", 1),
        )
        self.screen_grounder = ScreenGrounder(
            config=self.config.vision,
            capturer=self.screen_capture,
        )

        # 4. Instantiate Cognition Subsystems
        self.browser_offloader = BrowserOffloader(
            config=self.config.brain.offload,
            bridge=self.bridge,
            mouse_driver=self.mouse_driver,
            keyboard_driver=self.keyboard_driver,
            grounder=self.screen_grounder,
        )
        self.brain_manager = LocalBrainManager(
            config=self.config,
            offloader=self.browser_offloader,
        )

        # 5. Instantiate P4.4 Autonomous Skill Engine & Titular ParasiteSkill
        skills_cfg = self.config.skills
        ps_cfg = self.config.parasite_skill
        self._skill_lock = threading.RLock()
        self._container_probe = Win32ContainerWindowProbe()
        self.skill_registry = SkillRegistry(
            config=skills_cfg,
            window_probe=self._container_probe,
            capturer=self.screen_capture,
        )
        if skills_cfg.enabled:
            self.skill_registry.load_all()

        self.local_assist_backend = HybridLocalAssistBackend(
            screen_grounder=self.screen_grounder,
            brain_manager=self.brain_manager,
            capturer=self.screen_capture,
        )
        self.parasite_skill = ParasiteSkill(
            config=ps_cfg,
            keyboard_driver=self.keyboard_driver,
            mouse_driver=self.mouse_driver,
            capturer=self.screen_capture,
            window_guard=self.window_guard,
            interrupt_guard=self.interrupt_guard,
            bridge=self.bridge,
            local_assist=self.local_assist_backend,
        )
        self.trace_recorder = TraceRecorder(
            skills_dir=skills_cfg.skills_dir,
            window_probe=self._container_probe,
            capturer=self.screen_capture,
        )
        self.skill_learner = SkillLearner(
            config=skills_cfg,
            registry=self.skill_registry,
            parasite_skill=self.parasite_skill,
        )

        self.app_memory: Optional[AppMemory] = (
            AppMemory(self.config.app_memory)
            if self.config.app_memory.enabled
            else None
        )

        # 6. Instantiate Dual-Mind Pipeline & bind EpisodicMemory
        self.pipeline = DualMindPipeline(
            brain_manager=self.brain_manager,
            mouse_driver=self.mouse_driver,
            keyboard_driver=self.keyboard_driver,
            screen_grounder=self.screen_grounder,
            capturer=self.screen_capture,
            interrupt_guard=self.interrupt_guard,
            window_guard=self.window_guard,
            bridge=self.bridge,
            offloader=self.browser_offloader,
            config=self.config,
            skill_registry=self.skill_registry,
            parasite_skill=self.parasite_skill,
            trace_recorder=self.trace_recorder,
            app_memory=self.app_memory,
        )
        self.memory = self.pipeline.memory
        self._step_interrupted_latched = False

        # 7. Wire Bridge Signal Listeners
        self._wire_bridge_signals()

    def _promote_farmed_plans(self) -> List[SkillDefinition]:
        """Promotes repeatedly successful directive-complete farmed plans to SKILL.md without Gemini."""
        if self.app_memory is None:
            return []
        stopwords = {"and", "the", "for", "with", "into", "from"}
        known_procs = {
            "notepad": "notepad.exe",
            "calculator": "CalculatorApp.exe",
            "calc": "CalculatorApp.exe",
            "paint": "mspaint.exe",
            "mspaint": "mspaint.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
        }
        promoted: List[SkillDefinition] = []
        for plan_id, goal_norm, plan in self.app_memory.promotion_candidates():
            slug_base = re.sub(r"[^a-z0-9]+", "-", goal_norm).strip("-")[:48] or f"farmed-{plan_id}"
            if len(slug_base) < 3:
                slug_base = f"farmed-{slug_base}"
            unique_id = self.skill_learner._allocate_unique_id(slug_base)
            raw_tokens = re.findall(r"[a-z0-9]+", goal_norm.lower())
            seen_kw: set[str] = set()
            keywords: List[str] = []
            for tok in raw_tokens:
                if len(tok) >= 3 and tok not in stopwords and tok not in seen_kw:
                    seen_kw.add(tok)
                    keywords.append(tok)
                    if len(keywords) >= 6:
                        break
            if not keywords:
                keywords = [unique_id]

            action_steps: List[SkillActionStep] = []
            for s in plan.steps:
                d = s.action
                assert d is not None
                action_steps.append(
                    SkillActionStep(
                        intent=s.intent,
                        verb=d.verb,
                        target_description=s.target_description,
                        text=d.text,
                        keys=list(d.keys) if d.keys else None,
                        submit=bool(getattr(d, "submit", False)),
                        clear_first=bool(getattr(d, "clear_first", False)),
                        wait_ms=d.wait_ms,
                        success_criteria=s.success_criteria,
                    )
                )

            # Parameterize shared slots ({{path}}, {{expr}}, {{text}}) while keeping keywords intact
            extracted_params, goal_patterns, parameterized_steps = _extract_slot_template(
                goal_norm, action_steps
            )

            # Coordinate-free keyboard/wait skills enter live candidate probation immediately
            is_coord_free = bool(parameterized_steps) and all(
                st.verb in ("HOTKEY", "TYPE", "WAIT") and st.relative_coordinates is None
                for st in parameterized_steps
            )
            prog_key = (plan.selected_program or "").strip().lower()
            resolved_proc = known_procs.get(prog_key)
            if not resolved_proc and prog_key and self.app_memory is not None:
                resolved_proc = self.app_memory.get_last_process(prog_key)
            first_step = plan.steps[0]
            first_dir = first_step.action
            has_explicit_launch = bool(
                first_step.intent == StepIntent.LAUNCH_OR_ACTIVATE
                or (
                    first_dir is not None
                    and first_dir.verb == "HOTKEY"
                    and first_dir.keys
                    and any(k.lower() == "win" for k in first_dir.keys)
                )
            )

            skill = SkillDefinition(
                id=unique_id,
                name=(plan.selected_program or unique_id).strip()[:64],
                draft=not is_coord_free,
                state=SkillState.CANDIDATE,
                provenance=SkillProvenance.FARMED,
                description=plan.rationale[:200],
                trigger=SkillTrigger(
                    goal_patterns=goal_patterns,
                    keywords=keywords,
                    process_names=[resolved_proc] if resolved_proc else [],
                    min_score=0.6,
                ),
                parameters=extracted_params,
                preconditions=SkillPreconditions(
                    container_process=resolved_proc,
                    requires_launch=bool(resolved_proc) and not has_explicit_launch,
                ),
                actions=SkillActions(steps=parameterized_steps),
                postconditions=SkillPostconditions(
                    success_criteria=plan.steps[-1].success_criteria,
                    expected_process=resolved_proc,
                ),
            )
            self.skill_registry.save(skill)
            self.app_memory.mark_promoted(plan_id, unique_id)
            promoted.append(skill)
            logger.info(
                "Promoted farmed plan #%d -> skill '%s' (draft=%s, provenance=farmed).",
                plan_id,
                unique_id,
                skill.draft,
            )
        return promoted

    def approve_learned_skill(self, skill_id: str) -> SkillDefinition:
        """Thread-safe operator sign-off promoting a draft skill to active/candidate matching."""
        with self._skill_lock:
            return self.skill_registry.approve_draft(skill_id)

    def reject_learned_skill(self, skill_id: str, reason: str = "Operator rejected draft via C2") -> Any:
        """Thread-safe operator rejection moving a draft skill into _quarantine/."""
        with self._skill_lock:
            return self.skill_registry.reject_draft(skill_id, reason=reason)

    @property
    def is_running(self) -> bool:
        """Returns True if background worker thread is active."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Returns True if actions are currently paused by the user."""
        return self._is_paused

    def _wire_bridge_signals(self) -> None:
        """Connects signals emitted from GUI/C2 controls to runtime handlers."""
        self.bridge.sig_pause_toggled.connect(self._on_gui_pause_toggled)
        self.bridge.sig_panic_triggered.connect(self._on_gui_panic_triggered)
        self.bridge.sig_brain_mode_changed.connect(self._on_gui_brain_mode_changed)

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Starts background worker thread and low-level hardware hooks."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()

        # Start low-level hook thread (unless simulated in CI / unit tests)
        if not self.simulation_mode:
            try:
                self.interrupt_guard.start()
            except Exception as exc:
                logger.warning(f"Could not start native Win32 hardware hooks: {exc}")

        # Start Cognitive Worker Thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="ParasiteCognitiveWorker",
            daemon=True,
        )
        self._worker_thread.start()

        # Notify initial state
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Ready for user goal")

    def stop(self, timeout_sec: float = 6.0) -> None:
        """Gracefully halts worker thread, unhooks Win32 hooks, and neutralizes hands."""
        if not self._is_running:
            return
        self._is_running = False
        self._stop_event.set()

        # Signal cancellation token to wake up any sleeping or moving drivers
        token = self.interrupt_guard.get_cancellation_token()
        token.set()

        # Stop interrupt guard
        try:
            self.interrupt_guard.stop()
        except Exception:
            pass

        # Neutralize any pressed buttons/keys
        self._neutralize_inputs()

        # Clear HUD overlay
        self.bridge.clear_reticle()
        self.bridge.clear_hud_targets()

        # Close screen capture resources
        try:
            self.screen_capture.close()
        except Exception:
            pass

        # Join worker thread
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_sec)
            self._worker_thread = None

    def _neutralize_inputs(self) -> None:
        """Releases all mouse buttons and keys."""
        try:
            self.mouse_driver.release_all_buttons()
        except Exception:
            pass
        try:
            self.keyboard_driver.emergency_release_keys()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Background Cognitive Worker Loop
    # -----------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main loop dequeuing goals and executing closed-loop episodes."""
        logger.info("Cognitive worker loop started.")
        last_idle_scan = 0.0
        while not self._stop_event.is_set():
            goal_req = self.bridge.get_next_goal_request(timeout_sec=0.25)
            if goal_req is None or self._stop_event.is_set():
                if (
                    not self.simulation_mode
                    and not self.headless
                    and not self._is_paused
                    and not self._stop_event.is_set()
                    and (time.time() - last_idle_scan) >= 1.0
                ):
                    last_idle_scan = time.time()
                    try:
                        if not self.window_guard.is_safe_to_operate():
                            self.bridge.notify_state("PROTECTED", "Cautious")
                            self.bridge.clear_hud_targets()
                        else:
                            frame = self.screen_capture.capture_screen()
                            elems = self.screen_grounder.ground(image_override=frame)
                            self.bridge.notify_perception(frame, elems)
                            self.bridge.set_hud_targets(elems)
                    except Exception as exc:
                        logger.debug("Idle perception refresh skipped: %s", exc)
                continue

            goal = goal_req.goal
            max_steps = goal_req.max_steps or self.default_max_steps
            # Attach consent callback if provided by C2 (e.g. Discord)
            if goal_req.consent_callback:
                self.pipeline.consent_handler = goal_req.consent_callback
            else:
                self.pipeline.consent_handler = None

            try:
                self.bridge.notify_episode_event(
                    EpisodeEvent(
                        kind="started",
                        goal=goal,
                        step=0,
                        data={"source": goal_req.source, "metadata": goal_req.metadata},
                    )
                )
                self.memory.clear()
                self.memory.reset_loop_detector(reset_escalation=True)
                self._execute_goal_episode(goal, max_steps=max_steps)
            except Exception as exc:
                logger.critical(
                    f"Unhandled exception during goal episode '{goal}': {exc}",
                    exc_info=True,
                )
                self._neutralize_inputs()
                self.bridge.clear_hud_targets()
                self.bridge.clear_reticle()
                self.bridge.notify_speech(f"An internal error occurred: {exc}")
                self.bridge.notify_state("WATCHING", "Curious")
                self.bridge.notify_telemetry(f"Episode aborted due to internal error: {exc}")
            finally:
                self.pipeline.consent_handler = None
                if self.auto_exit_on_complete:
                    logger.info("auto_exit_on_complete enabled; requesting application close after episode.")
                    self.bridge.sig_close_requested.emit()
                    break

        logger.info("Cognitive worker loop terminated.")

    def _build_episode_receipt(
        self,
        *,
        goal: str,
        step_summaries: List[StepRecordSummary],
        max_steps: int,
        duration_sec: float,
        exit_reason: str,
        episode_success: bool,
        episode_error: Optional[str],
    ) -> EpisodeReceipt:
        """Builds an EpisodeReceipt snapshot including P4.6.6 plan/skill telemetry."""
        active_window_info = None
        if hasattr(self, "window_guard") and self.window_guard:
            try:
                winfo = self.window_guard.get_active_window_info()
                title = getattr(winfo, "title", "")
                proc = getattr(winfo, "process_name", "")
                active_window_info = {
                    "title": title if isinstance(title, str) else "",
                    "process_name": proc if isinstance(proc, str) else "",
                }
            except Exception:
                pass

        step_latencies = [s.duration_sec for s in step_summaries]
        interrupt_count = getattr(self.interrupt_guard, "interrupt_count", 0)
        if not isinstance(interrupt_count, int) or isinstance(interrupt_count, bool):
            interrupt_count = 0
        total_strikes = getattr(self.memory, "consecutive_strikes", 0)
        if not isinstance(total_strikes, int) or isinstance(total_strikes, bool):
            total_strikes = 0

        highest_tier = "TIER_1_LOCAL"
        if hasattr(self.memory, "history") and self.memory.history:
            try:
                tier_vals = [getattr(r, "tier_level", CadenceTier.TIER_1_LOCAL) for r in self.memory.history]
                max_tier = max(tier_vals, key=lambda t: getattr(t, "value", str(t)))
                highest_tier = str(max_tier.value if hasattr(max_tier, "value") else max_tier)
            except Exception:
                pass

        pipeline = getattr(self, "pipeline", None)
        raw_source = getattr(pipeline, "_episode_plan_source", "local") if pipeline is not None else "local"
        plan_source = raw_source if isinstance(raw_source, str) else "local"
        raw_skill_id = getattr(pipeline, "_episode_skill_id", None) if pipeline is not None else None
        skill_id = raw_skill_id if isinstance(raw_skill_id, str) else None
        raw_farmed_id = getattr(pipeline, "_episode_farmed_plan_id", None) if pipeline is not None else None
        farmed_plan_id = (
            raw_farmed_id if (isinstance(raw_farmed_id, int) and not isinstance(raw_farmed_id, bool)) else None
        )
        raw_fp = getattr(pipeline, "_episode_fast_path_steps", 0) if pipeline is not None else 0
        fast_path_steps = raw_fp if (isinstance(raw_fp, int) and not isinstance(raw_fp, bool)) else 0
        raw_ps_inv = getattr(pipeline, "_episode_parasite_invocations", 0) if pipeline is not None else 0
        parasite_invocations = (
            raw_ps_inv if (isinstance(raw_ps_inv, int) and not isinstance(raw_ps_inv, bool)) else 0
        )
        raw_ps_status = getattr(pipeline, "_episode_parasite_status", None) if pipeline is not None else None
        parasite_status = raw_ps_status if isinstance(raw_ps_status, str) else None
        raw_veto = getattr(pipeline, "_episode_veto_count", 0) if pipeline is not None else 0
        veto_count = raw_veto if (isinstance(raw_veto, int) and not isinstance(raw_veto, bool)) else 0
        raw_fp_abort = getattr(pipeline, "_episode_fast_path_abort_reason", None) if pipeline is not None else None
        fast_path_abort_reason = raw_fp_abort if isinstance(raw_fp_abort, str) else None

        return EpisodeReceipt(
            goal=goal,
            success=episode_success,
            claimed_done=(exit_reason == "DONE"),
            total_steps=len(step_summaries),
            max_steps=max_steps,
            duration_sec=round(max(0.0, duration_sec), 3),
            exit_reason=exit_reason,
            step_latencies_sec=step_latencies,
            total_strikes=total_strikes,
            highest_tier_reached=str(highest_tier),
            hardware_interrupt_count=interrupt_count,
            final_active_window=active_window_info,
            steps=list(step_summaries),
            error=episode_error,
            plan_source=plan_source,
            skill_id=skill_id,
            farmed_plan_id=farmed_plan_id,
            fast_path_steps=fast_path_steps,
            parasite_invocations=parasite_invocations,
            parasite_status=parasite_status,
            veto_count=veto_count,
            fast_path_abort_reason=fast_path_abort_reason,
        )

    def _save_checkpoint_receipt(
        self,
        *,
        goal: str,
        step_summaries: List[StepRecordSummary],
        max_steps: int,
        start_time: float,
        exit_reason: str,
        episode_success: bool,
        episode_error: Optional[str],
    ) -> None:
        """Persists an incremental IN_PROGRESS receipt without triggering auto-exit."""
        if not self.episode_report_path:
            return
        try:
            receipt = self._build_episode_receipt(
                goal=goal,
                step_summaries=step_summaries,
                max_steps=max_steps,
                duration_sec=time.time() - start_time,
                exit_reason=exit_reason,
                episode_success=episode_success,
                episode_error=episode_error,
            )
            receipt.save(self.episode_report_path)
        except Exception as exc:
            logger.debug("Incremental episode receipt checkpoint skipped: %s", exc)

    def _execute_goal_episode(self, goal: str, max_steps: int = 30) -> None:
        """Executes a multi-step goal until completion, panic, loop, or max steps."""
        logger.info(f"Beginning goal episode: '{goal}'")
        if hasattr(self.pipeline, "start_debug_episode"):
            self.pipeline.start_debug_episode(goal)

        # 0. If recovering from previous hardware/GUI panic, re-arm on new goal
        if self.interrupt_guard.is_panic():
            logger.info("New goal received post-panic; auto re-arming system.")
            self.reset_panic()

        if hasattr(self.interrupt_guard, "reset_interrupt_counters"):
            self.interrupt_guard.reset_interrupt_counters()
        self._step_interrupted_latched = False

        self.bridge.notify_state("THINKING", "Focused")
        self.bridge.notify_telemetry(f"Starting goal: {goal}", 0, max_steps)
        was_panic_or_loop = False
        start_time = time.time()
        step_summaries: List[StepRecordSummary] = []
        exit_reason = "MAX_STEPS"
        episode_success = False
        episode_error: Optional[str] = None

        if self.episode_report_path:
            self._save_checkpoint_receipt(
                goal=goal,
                step_summaries=step_summaries,
                max_steps=max_steps,
                start_time=start_time,
                exit_reason="IN_PROGRESS",
                episode_success=False,
                episode_error=None,
            )

        for step_idx in range(1, max_steps + 1):
            if self._stop_event.is_set():
                exit_reason = "STOPPED"
                break

            # 1. Handle Paused State
            while self._is_paused and not self._stop_event.is_set():
                self.bridge.notify_telemetry("Hands paused by user", step_idx, max_steps)
                time.sleep(0.2)

            if self._stop_event.is_set():
                exit_reason = "STOPPED"
                break

            # 2. Handle Hardware Override State (including touch latched mid-step during VLM latency)
            if self.interrupt_guard.is_interrupted() or self._step_interrupted_latched:
                latched_only = self._step_interrupted_latched and not self.interrupt_guard.is_interrupted()
                self._step_interrupted_latched = False
                logger.info("Hardware touch active, waiting for cooldown...")
                self.bridge.notify_state("USER_OVERRIDE", "Curious")
                if latched_only:
                    cooldown = float(getattr(self.config.safety, "override_pause_duration_sec", 2.5))
                    deadline = time.monotonic() + cooldown
                    while time.monotonic() < deadline and not self._stop_event.is_set():
                        time.sleep(0.2)
                while self.interrupt_guard.is_interrupted() and not self._stop_event.is_set():
                    time.sleep(0.2)
                if self._stop_event.is_set():
                    exit_reason = "STOPPED"
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # 3. Handle Sensitive Window Protection (bypassed in simulation mode)
            if not self.simulation_mode and not self.window_guard.is_safe_to_operate():
                logger.warning("Active window is sensitive/protected. Pausing observation.")
                self.bridge.notify_state("PROTECTED", "Cautious")
                self.bridge.clear_hud_targets()
                while not self.window_guard.is_safe_to_operate() and not self._stop_event.is_set():
                    time.sleep(0.5)
                if self._stop_event.is_set():
                    exit_reason = "STOPPED"
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # 4. Execute Atomic Cognitive Step with Error Boundary
            self.bridge.notify_telemetry(f"Step {step_idx}/{max_steps}: Perceiving & Reasoning", step_idx, max_steps)
            self._is_in_cognitive_step = True
            t_step_start = time.time()
            try:
                step_record = self.pipeline.step(user_goal=goal)
                step_dur = time.time() - t_step_start
                step_summary = step_record.to_summary(duration_sec=round(step_dur, 3))
                step_summaries.append(step_summary)

                if self.episode_report_path:
                    self._save_checkpoint_receipt(
                        goal=goal,
                        step_summaries=step_summaries,
                        max_steps=max_steps,
                        start_time=start_time,
                        exit_reason="IN_PROGRESS",
                        episode_success=False,
                        episode_error=None,
                    )

                # Emit step completed event
                self.bridge.notify_episode_event(
                    EpisodeEvent(
                        kind="step_completed",
                        goal=goal,
                        step=step_idx,
                        data={
                            "step_summary": step_summary,
                            "step_record": step_record,
                            "duration_sec": step_dur,
                        },
                    )
                )
            except Exception as exc:
                logger.error(f"Step {step_idx} failed with unhandled exception: {exc}", exc_info=True)
                episode_error = str(exc)
                exit_reason = "ERROR"
                self.bridge.notify_speech(f"An internal error occurred: {exc}")
                self.bridge.notify_state("WATCHING", "Curious")
                self.bridge.notify_telemetry(f"Step error: {exc}", step_idx, max_steps)
                break
            finally:
                self._is_in_cognitive_step = False

            action_type = step_record.action.action
            logger.info(f"Step {step_idx} executed: {action_type} (success={step_record.success})")

            # Terminal / Special States:
            # Done Condition
            if action_type == ActionType.DONE:
                exit_reason = "DONE"
                episode_success = True
                self.bridge.notify_speech("I've completed your goal!")
                self.bridge.notify_state("WATCHING", "Amused")
                self.bridge.notify_telemetry("Goal completed successfully!", max_steps, max_steps)
                break

            # Panic Condition
            if action_type == ActionType.PANIC or self.interrupt_guard.is_panic():
                was_panic_or_loop = True
                exit_reason = "PANIC"
                self.bridge.notify_speech("Emergency abort triggered! Backing off.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Goal aborted by emergency panic", step_idx, max_steps)
                break

            # Cognitive Loop Detection (3-strike failure loop)
            if self.memory.is_in_loop():
                was_panic_or_loop = True
                exit_reason = "LOOP_STAGNATION"
                self.bridge.notify_speech("I noticed we're repeating actions without screen change. Pausing.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Paused: 3 consecutive failure strikes detected", step_idx, max_steps)
                break

            # Settle delay between steps
            time.sleep(0.1)

        total_dur = max(0.0, time.time() - start_time)
        receipt = self._build_episode_receipt(
            goal=goal,
            step_summaries=step_summaries,
            max_steps=max_steps,
            duration_sec=total_dur,
            exit_reason=exit_reason,
            episode_success=episode_success,
            episode_error=episode_error,
        )
        self.last_episode_receipt = receipt
        if self.episode_report_path:
            try:
                receipt.save(self.episode_report_path)
                logger.info("Saved episode receipt to %s", self.episode_report_path)
            except Exception as save_err:
                logger.error("Failed to save episode receipt to %s: %s", self.episode_report_path, save_err)

        # Notify C2 / UI of episode finish
        self.bridge.notify_episode_event(
            EpisodeEvent(
                kind="finished",
                goal=goal,
                step=len(step_summaries),
                data={"receipt": receipt},
            )
        )

        # P4.4 Skill Outcome Tracking, Trace Persistence & Autonomous Co-Authoring
        if self.config.skills.enabled:
            try:
                with self._skill_lock:
                    used_skill_id = getattr(self.pipeline, "_episode_skill_id", None)
                    stale_match = getattr(self.pipeline, "_stale_skill_match", None)
                    stale_skill_id = stale_match.skill.id if stale_match is not None else None
                    anchor = (
                        self.trace_recorder.captured_anchors[0]
                        if self.trace_recorder.captured_anchors
                        else None
                    )
                    if used_skill_id and used_skill_id in self.skill_registry.skills:
                        if episode_success:
                            self.skill_registry.record_outcome(
                                used_skill_id, success=True, anchor=anchor
                            )
                        elif exit_reason in ("LOOP_STAGNATION", "ERROR", "MAX_STEPS"):
                            self.skill_registry.record_outcome(
                                used_skill_id, success=False
                            )
                    elif (
                        episode_success
                        and stale_skill_id
                        and stale_skill_id in self.skill_registry.skills
                        and not self.trace_recorder.had_user_override
                    ):
                        self.skill_registry.record_outcome(
                            stale_skill_id, success=True, anchor=anchor
                        )

                    if self.trace_recorder.entries:
                        self.trace_recorder.save_trace(goal)

                    learned = self.skill_learner.maybe_learn(receipt, self.trace_recorder)
                    if learned is not None:
                        self.bridge.notify_episode_event(
                            EpisodeEvent(
                                kind="skill_learned",
                                goal=goal,
                                step=len(step_summaries),
                                data={
                                    "skill_id": learned.id,
                                    "name": learned.name,
                                    "summary": learned.description,
                                    "steps": len(learned.actions.steps),
                                    "skill_path": str(learned.source_path or ""),
                                },
                            )
                        )
                    else:
                        deferred_path = getattr(self.skill_learner, "_last_deferred_path", None)
                        skip_paths = {deferred_path} if deferred_path is not None else None
                        for drained in self.skill_learner.process_pending_coauthor(
                            max_items=1, skip_paths=skip_paths
                        ):
                            self.bridge.notify_episode_event(
                                EpisodeEvent(
                                    kind="skill_learned",
                                    goal=drained.name or goal,
                                    step=len(step_summaries),
                                    data={
                                        "skill_id": drained.id,
                                        "name": drained.name,
                                        "summary": drained.description,
                                        "steps": len(drained.actions.steps),
                                        "skill_path": str(drained.source_path or ""),
                                    },
                                )
                            )
            except Exception as skill_err:
                logger.warning("Skill post-episode lifecycle step skipped: %s", skill_err)

        # P4.5 Persistent AppMemory Outcome Tracking & Zero-Gemini Draft Promotion
        if self.app_memory is not None:
            try:
                farmed_id = getattr(self.pipeline, "_episode_farmed_plan_id", None)
                used_skill_id = getattr(self.pipeline, "_episode_skill_id", None)
                plan_source = (
                    "skill" if used_skill_id else ("farmed" if farmed_id is not None else "local")
                )
                plan_ref = str(used_skill_id or farmed_id or "") or None
                self.app_memory.record_episode(
                    goal=goal,
                    plan_source=plan_source,
                    plan_ref=plan_ref,
                    success=episode_success,
                    exit_reason=exit_reason,
                    steps=len(step_summaries),
                    duration_sec=round(total_dur, 3),
                    fast_path_steps=getattr(self.pipeline, "_episode_fast_path_steps", 0),
                )
                if farmed_id is not None:
                    self.app_memory.record_outcome(farmed_id, success=episode_success)
                if self.window_guard and hasattr(self.window_guard, "get_active_window"):
                    win_info = self.window_guard.get_active_window()
                    if win_info and getattr(win_info, "process_name", ""):
                        self.app_memory.record_app_seen(
                            process_name=win_info.process_name,
                            window_title=getattr(win_info, "title", "") or "",
                            launch_ok=episode_success,
                        )
                if self.config.skills.enabled:
                    self._promote_farmed_plans()
            except Exception as mem_err:
                logger.warning("AppMemory post-episode step skipped: %s", mem_err)

        # Episode Teardown & Reset Loop Detector
        self.memory.clear()
        self.memory.reset_loop_detector(reset_escalation=True)
        self.bridge.clear_hud_targets()
        self.bridge.clear_reticle()
        if not self._stop_event.is_set() and not self.interrupt_guard.is_panic() and not was_panic_or_loop:
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Ready for next goal")

    # -----------------------------------------------------------------------
    # Synchronous Step Execution (Unit & Integration Testing API)
    # -----------------------------------------------------------------------

    def run_goal_sync(self, goal: str, max_steps: int = 30) -> EpisodeReceipt:
        """Executes a full goal episode synchronously and returns the EpisodeReceipt."""
        self._execute_goal_episode(goal, max_steps=max_steps)
        if self.last_episode_receipt is not None:
            return self.last_episode_receipt
        return EpisodeReceipt(
            goal=goal,
            success=False,
            exit_reason="ERROR",
            error="No receipt recorded",
        )

    def run_single_step(
        self,
        goal: str,
        screen_frame: Optional[np.ndarray] = None,
        grounded_elements: Optional[List[UIElement]] = None,
        override_action: Optional[ActionPlan] = None,
    ) -> StepRecord:
        """Executes one deterministic closed-loop step synchronously."""
        if hasattr(self, "_last_single_step_goal") and self._last_single_step_goal != goal:
            self.memory.reset_loop_detector(reset_escalation=True)
            if hasattr(self, "trace_recorder") and self.trace_recorder is not None:
                self.trace_recorder.reset()
        self._last_single_step_goal = goal

        self._is_in_cognitive_step = True
        try:
            return self.pipeline.step(
                user_goal=goal,
                screen_frame=screen_frame,
                grounded_elements=grounded_elements,
                override_action=override_action,
            )
        finally:
            self._is_in_cognitive_step = False

    # -----------------------------------------------------------------------
    # Callbacks & Signal Handlers
    # -----------------------------------------------------------------------

    def _on_reticle_requested(self, x: int, y: int, duration_ms: int) -> None:
        """Dispatches pre-click reticle request via UIBridge."""
        self.bridge.show_reticle(x, y, duration_ms)

    def _on_hardware_interrupt(self, reason: str) -> None:
        """Invoked when physical human touch preempts synthetic movement."""
        # Only log at debug level during idle periods; warn only if an active cognitive step or task was running
        if self._is_in_cognitive_step or (hasattr(self, "_worker_thread") and self.is_running and getattr(self, "pipeline", None) and getattr(self.pipeline, "active_plan", None)):
            logger.warning(f"Hardware interrupt detected: {reason}")
            self._step_interrupted_latched = True
        else:
            logger.debug(f"Hardware touch during idle: {reason}")
        self.bridge.clear_reticle()
        self.bridge.notify_state("USER_OVERRIDE", "Curious")
        self.bridge.notify_telemetry(f"Physical touch override: {reason}")

    def _on_hardware_panic(self, reason: str) -> None:
        """Invoked when emergency panic hotkey/trigger trips."""
        logger.critical(f"Global panic abort detected: {reason}")
        self._neutralize_inputs()
        self.bridge.clear_goals()
        self.bridge.clear_reticle()
        self.bridge.clear_hud_targets()
        self.bridge.notify_state("WATCHING", "Panic-Averted")
        self.bridge.notify_telemetry(f"EMERGENCY PANIC: {reason}")

    def reset_panic(self) -> None:
        """Resets emergency panic state, clears tokens, and re-arms interrupt guard."""
        logger.info("Resetting emergency panic state and re-arming.")
        self.interrupt_guard.reset_interrupt()
        self.memory.reset_loop_detector(reset_escalation=True)
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Re-armed: Ready for goals")

    def _on_hardware_rearm(self) -> None:
        """Invoked when hardware interrupt cooldown expires."""
        logger.info("Hardware interrupt cooldown elapsed. System re-armed.")
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Re-armed: Ready for goals")

    def _on_gui_pause_toggled(self, is_paused: bool) -> None:
        """Handles Pause Hands toggle from C2 button or bridge."""
        self._is_paused = is_paused
        logger.info(f"Hands pause state updated: {is_paused}")
        token = self.interrupt_guard.get_cancellation_token()
        if is_paused:
            token.set()
            self._neutralize_inputs()
            self.bridge.clear_reticle()
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Hands paused by user")
        else:
            token.clear()
            self.bridge.notify_telemetry("Hands resumed by user")

    def _on_gui_panic_triggered(self) -> None:
        """Handles PANIC signal from C2 button or bridge."""
        if getattr(self, "_is_in_cognitive_step", False):
            # Cognitive loop panic: Decoupled from hardware PanicManager!
            logger.warning("Cognitive strategy reset triggered by 3-strike loop.")
            self._neutralize_inputs()
            self.bridge.clear_reticle()
            self.bridge.clear_hud_targets()
            self.bridge.notify_state("WATCHING", "Panic-Averted")
            self.bridge.notify_telemetry("Cognitive loop: strategy reset")
            return

        logger.critical("PANIC triggered via C2/GUI.")
        self.bridge.clear_goals()
        self._neutralize_inputs()
        self.interrupt_guard.panic_manager.trigger_panic("C2 PANIC command")
        self._on_hardware_panic("C2 command")

    def _on_gui_brain_mode_changed(self, mode: str) -> None:
        """Handles Brain Mode selection change."""
        logger.info(f"Brain mode selection updated: {mode}")
        clean_mode = mode.lower()
        if "browser" in clean_mode:
            self.brain_manager.toggle_browser_only_mode(True)
        elif "local" in clean_mode:
            self.brain_manager.toggle_browser_only_mode(False)
        elif "mock" in clean_mode:
            self.brain_manager.mode = BrainMode.MOCK

    def request_course_correction(self, instruction: str) -> bool:
        """Forwards an operator course-correction instruction to the active DualMindPipeline."""
        if self.pipeline is not None and hasattr(self.pipeline, "request_course_correction"):
            self.pipeline.request_course_correction(instruction)
            return True
        return False

    def request_parasite_consult(self, hint: Optional[str] = None) -> bool:
        """Triggers an immediate Gemini ParasiteSkill consultation on the active DualMindPipeline."""
        if self.pipeline is not None and hasattr(self.pipeline, "request_parasite_consult"):
            self.pipeline.request_parasite_consult(hint=hint)
            return True
        return False
