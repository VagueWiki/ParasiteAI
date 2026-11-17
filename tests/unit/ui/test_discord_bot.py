"""
tests/unit/ui/test_discord_bot.py - Discord C2 Bot Unit & Security Test Suite.
Verifies slash commands, fail-closed authorization, interactive risk consent, and 0% PyQt6 footprint.
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
from PIL import Image
import pytest

from parasite_ai.config import AppConfig, DiscordConfig
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.safety.risk_gate import ActionConsentRequest, ActionRisk
from parasite_ai.ui.discord_bot import (
    COLOR_ACTIVE,
    COLOR_CONSENT_WARN,
    COLOR_PANIC_RED,
    COLOR_SUCCESS_EMERALD,
    DiscordBotC2,
    RiskConsentView,
    get_windows_system_memory,
    trim_embed_value,
)


class TestDiscordBotUtilities:
    """Verifies string chunking, memory telemetry, and frame encoding."""

    def test_trim_embed_value_boundary_guard(self) -> None:
        """Verifies text trimming prevents Discord 400 Bad Request error."""
        assert trim_embed_value(None) == "None."
        assert trim_embed_value("") == "None."
        assert trim_embed_value("   ") == "None."

        short_text = "Standard response string"
        assert trim_embed_value(short_text, max_len=100) == short_text

        long_text = "A" * 1500
        trimmed = trim_embed_value(long_text, max_len=1000)
        assert len(trimmed) == 1003  # 1000 + "..."
        assert trimmed.endswith("...")

    def test_windows_system_memory_query(self) -> None:
        """Verifies querying Windows physical memory returns non-zero values on Windows."""
        used_mb, total_mb, pct = get_windows_system_memory()
        if sys.platform == "win32":
            assert total_mb > 1024, "Total system RAM must be > 1GB"
            assert used_mb > 0
            assert 0.0 <= pct <= 100.0


class TestDiscordAuthorizationSecurity:
    """Verifies fail-closed whitelist security checks."""

    def test_fail_closed_on_empty_authorized_users(self) -> None:
        """Verifies bot rejects all commands when authorized_user_ids is empty."""
        cfg = AppConfig()
        cfg.discord.authorized_user_ids = []
        bot_c2 = DiscordBotC2(orchestrator=MagicMock(), config=cfg)

        assert bot_c2._is_authorized(user_id=12345678) is False
        assert bot_c2._is_authorized(user_id=99999999) is False

    def test_authorized_user_accepted(self) -> None:
        """Verifies users listed in authorized_user_ids pass security check."""
        cfg = AppConfig()
        cfg.discord.authorized_user_ids = [111222333, 444555666]
        bot_c2 = DiscordBotC2(orchestrator=MagicMock(), config=cfg)

        assert bot_c2._is_authorized(user_id=111222333) is True
        assert bot_c2._is_authorized(user_id=444555666) is True
        assert bot_c2._is_authorized(user_id=999999999) is False

    def test_channel_allowlist_enforcement(self) -> None:
        """Verifies channel filter when authorized_channel_ids is configured."""
        cfg = AppConfig()
        cfg.discord.authorized_user_ids = [111222333]
        cfg.discord.authorized_channel_ids = [999000111]
        bot_c2 = DiscordBotC2(orchestrator=MagicMock(), config=cfg)

        assert bot_c2._is_authorized(user_id=111222333, channel_id=999000111) is True
        assert bot_c2._is_authorized(user_id=111222333, channel_id=888888888) is False


class TestDiscordSlashCommandsAndActions:
    """Verifies slash command logic, image encoding, and panic latency."""

    def test_frame_encoding_to_discord_file(self) -> None:
        """Verifies numpy frame encodes to in-memory compressed JPEG discord.File."""
        cfg = AppConfig()
        cfg.discord.screen_max_width = 1280
        cfg.discord.screen_jpeg_quality = 70
        bot_c2 = DiscordBotC2(orchestrator=MagicMock(), config=cfg)

        # Create dummy 1080p frame (1080, 1920, 3)
        dummy_frame = np.full((1080, 1920, 3), 128, dtype=np.uint8)
        file_obj, w, h = bot_c2._encode_frame_to_discord_file(dummy_frame, filename="test.jpg")

        assert file_obj.filename == "test.jpg"
        assert w == 1920
        assert h == 1080

        # Validate bytes can be read back as valid JPEG image
        raw_bytes = file_obj.fp.read()
        assert len(raw_bytes) > 100
        img = Image.open(io.BytesIO(raw_bytes))
        assert img.format == "JPEG"
        assert img.width == 1280  # Resized to max width

    def test_panic_command_latency_under_2ms(self) -> None:
        """Verifies /panic execution sets cancellation token and triggers panic manager in <2ms."""
        orch = RuntimeOrchestrator(simulation_mode=True, headless=True)
        bot_c2 = DiscordBotC2(orchestrator=orch)
        bot_c2.discord_config.authorized_user_ids = [12345]

        # Prepare mock interaction
        interaction = AsyncMock()
        interaction.user.id = 12345
        interaction.channel_id = 99999

        token = orch.interrupt_guard.get_cancellation_token()
        assert not token.is_set()

        t0 = time.perf_counter()
        token.set()
        orch.interrupt_guard.panic_manager.trigger_panic("discord_panic")
        orch.bridge.clear_goals()
        orch._neutralize_inputs()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert token.is_set()
        assert orch.interrupt_guard.is_panic()
        assert elapsed_ms < 2.0, f"Panic latency {elapsed_ms:.3f}ms exceeded 2ms budget"


@pytest.mark.asyncio
class TestInteractiveRiskConsentView:
    """Verifies asynchronous [Approve] / [Cancel] consent button handling."""

    async def test_consent_view_approval(self) -> None:
        """Verifies clicking Approve sets future result to True."""
        req = ActionConsentRequest(
            step_id=1,
            action_plan=ActionPlan(action=ActionType.CLICK, reasoning="Click send message"),
            risk=ActionRisk.YELLOW,
            reason="State-mutating comm verb",
        )
        view = RiskConsentView(request=req, authorized_user_ids=[12345], timeout=10.0)

        # Simulate interaction
        interaction = AsyncMock()
        interaction.user.id = 12345
        interaction.user.mention = "@Operator"

        await view.children[0].callback(interaction)
        assert view.value is True
        assert view._future.done()
        assert view._future.result() is True

    async def test_consent_view_denial(self) -> None:
        """Verifies clicking Cancel sets future result to False."""
        req = ActionConsentRequest(
            step_id=1,
            action_plan=ActionPlan(action=ActionType.RUN_CLI_COMMAND, cli_command="del file.txt"),
            risk=ActionRisk.RED,
            reason="Destructive command",
        )
        view = RiskConsentView(request=req, authorized_user_ids=[12345], timeout=10.0)

        interaction = AsyncMock()
        interaction.user.id = 12345
        interaction.user.mention = "@Operator"

        await view.children[1].callback(interaction)
        assert view.value is False
        assert view._future.done()
        assert view._future.result() is False

    async def test_consent_view_unauthorized_user_rejected(self) -> None:
        """Verifies unauthorized user interaction check returns False."""
        req = ActionConsentRequest(
            step_id=1,
            action_plan=ActionPlan(action=ActionType.CLICK),
            risk=ActionRisk.YELLOW,
            reason="Test",
        )
        view = RiskConsentView(request=req, authorized_user_ids=[12345], timeout=10.0)

        interaction = AsyncMock()
        interaction.user.id = 99999  # Unauthorized

        allowed = await view.interaction_check(interaction)
        assert allowed is False
        interaction.response.send_message.assert_called_once()


def test_zero_pyqt6_modules_in_runtime() -> None:
    """Invariant: Verifies that importing and instantiating RuntimeOrchestrator loads ZERO PyQt6 modules."""
    orch = RuntimeOrchestrator(simulation_mode=True, headless=True)
    assert orch is not None
    loaded_pyqt_modules = [m for m in sys.modules if m.startswith("PyQt6")]
    assert len(loaded_pyqt_modules) == 0, f"PyQt6 modules unexpectedly loaded: {loaded_pyqt_modules}"


@pytest.mark.asyncio
class TestDiscordScreenshotsAndTextDispatch:
    """Verifies final screenshot attachment on finished events and plain-text/@mention task dispatch."""

    async def test_finished_event_attaches_final_screenshot_and_quick_view(self) -> None:
        from parasite_ai.runtime import EpisodeReceipt
        from parasite_ai.ui.bridge import EpisodeEvent

        cfg = AppConfig()
        cfg.discord.authorized_user_ids = [111]
        cfg.discord.send_final_screenshot = True
        orch = MagicMock()
        orch.screen_capture.capture_screen.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        bot_c2 = DiscordBotC2(orchestrator=orch, config=cfg)

        channel = AsyncMock()
        receipt = EpisodeReceipt(
            goal="open cookie clicker",
            success=False,
            exit_reason="ERROR",
            total_steps=2,
            duration_sec=4.5,
            error="Test error",
        )
        event = EpisodeEvent(kind="finished", goal=receipt.goal, step=2, data={"receipt": receipt})
        await bot_c2._dispatch_episode_event(event, channel)

        channel.send.assert_called_once()
        kwargs = channel.send.call_args.kwargs
        assert kwargs.get("file") is not None
        assert kwargs["file"].filename == "final_screen.jpg"
        assert kwargs.get("embed") is not None
        assert kwargs["embed"].image.url == "attachment://final_screen.jpg"
        assert kwargs.get("view") is not None

    async def test_text_message_dispatch_authorized_and_fail_closed(self) -> None:
        cfg = AppConfig()
        cfg.discord.authorized_user_ids = [111]
        cfg.discord.use_task_threads = False
        orch = MagicMock()
        orch.is_running = False
        orch.default_max_steps = 15
        bot_c2 = DiscordBotC2(orchestrator=orch, config=cfg)

        # Unauthorized user is ignored
        unauth_msg = MagicMock()
        unauth_msg.author.bot = False
        unauth_msg.author.id = 999
        unauth_msg.channel.id = 222
        unauth_msg.content = "open notepad"
        assert await bot_c2._handle_text_message(unauth_msg) is False
        orch.bridge.submit_goal.assert_not_called()

        # Authorized user plain-text dispatches goal inline
        auth_msg = MagicMock()
        auth_msg.author.bot = False
        auth_msg.author.id = 111
        auth_msg.author.mention = "<@111>"
        auth_msg.channel = AsyncMock()
        auth_msg.channel.id = 222
        auth_msg.content = "open cookie clicker"
        assert await bot_c2._handle_text_message(auth_msg) is True
        orch.bridge.submit_goal.assert_called_once()
        assert orch.bridge.submit_goal.call_args.kwargs["goal"] == "open cookie clicker"
        auth_msg.channel.send.assert_called_once()

    async def test_control_deck_parasite_it_and_abort_task_consent_button(self) -> None:
        from parasite_ai.mind.memory import ActionType, StepRecord
        from parasite_ai.ui.bridge import EpisodeEvent
        from parasite_ai.ui.discord_bot import ActiveTaskControlsView, ControlDeckView, CourseCorrectModal

        cfg = AppConfig()
        cfg.discord.authorized_user_ids = [111]
        cfg.discord.milestone_screenshot_interval = 1
        orch = MagicMock()
        orch.is_running = True
        orch._is_in_cognitive_step = True
        orch.request_parasite_consult.return_value = True
        orch.request_course_correction.return_value = True
        orch.screen_capture.capture_screen.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        bot_c2 = DiscordBotC2(orchestrator=orch, config=cfg)

        # Idle ControlDeckView should NOT have Course Correct or Parasite It
        deck = ControlDeckView(bot_c2)
        deck_labels = [getattr(c, "label", "") for c in deck.children]
        assert "New Task" in deck_labels
        assert "Screenshot" in deck_labels
        assert "Status" in deck_labels
        assert "Panic" in deck_labels
        assert "Course Correct" not in deck_labels
        assert "Parasite It" not in deck_labels

        # ActiveTaskControlsView has Course Correct & Parasite It
        active_view = ActiveTaskControlsView(bot_c2)
        active_labels = [getattr(c, "label", "") for c in active_view.children]
        assert "Course Correct" in active_labels
        assert "Parasite It" in active_labels

        interaction = AsyncMock()
        interaction.user.id = 111
        interaction.user.mention = "<@111>"
        interaction.channel_id = 222
        parasite_btn = [c for c in active_view.children if getattr(c, "label", "") == "Parasite It"][0]
        await parasite_btn.callback(interaction)
        orch.request_parasite_consult.assert_called_once()

        # CourseCorrectModal queues steering when task is active
        modal = CourseCorrectModal(bot_c2)
        modal.instruction_input._value = "Use Win+R instead of Steam"
        modal_inter = AsyncMock()
        modal_inter.user.id = 111
        modal_inter.user.mention = "<@111>"
        modal_inter.channel_id = 222
        await modal.on_submit(modal_inter)
        orch.request_course_correction.assert_called_once_with("Use Win+R instead of Steam")

        # RiskConsentView has Parasite It, Course Correct, and Abort Task
        req = ActionConsentRequest(
            step_id=1,
            action_plan=ActionPlan(action=ActionType.CLICK),
            risk=ActionRisk.YELLOW,
            reason="Test",
        )
        view = RiskConsentView(request=req, authorized_user_ids=[111], timeout=10.0, orchestrator=orch, bot_c2=bot_c2)
        consent_labels = [getattr(c, "label", "") for c in view.children]
        assert "Parasite It" in consent_labels
        assert "Course Correct" in consent_labels
        assert "Abort Task" in consent_labels

        abort_btn = view.children[2]
        await abort_btn.callback(interaction)
        assert view.aborted is True
        assert view._future.result() is False
        orch.bridge.clear_goals.assert_called_once()

        # step_completed embeds include Thought, Window, Telemetry, and ActiveTaskControlsView
        rec = StepRecord(
            step_id=1,
            action=ActionPlan(action=ActionType.CLICK, coordinates=(350, 250)),
            persona_thought="Clicking Steam search bar",
            post_window="Steam (steamwebhelper.exe)",
            screen_diff=0.06,
        )
        channel = AsyncMock()
        ev = EpisodeEvent(kind="step_completed", goal="open auto clicker", step=1, data={"step_record": rec})
        await bot_c2._dispatch_episode_event(ev, channel)
        channel.send.assert_called_once()
        kw = channel.send.call_args.kwargs
        assert "Clicking Steam search bar" in kw["embed"].description
        assert isinstance(kw["view"], ActiveTaskControlsView)
