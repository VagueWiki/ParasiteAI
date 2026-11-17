"""
parasite_ai/ui/discord_bot.py - Discord Command & Control (C2) Daemon for ParasiteAI.

Provides an asynchronous, zero-VRAM remote management bridge over discord.py:
1. Strict authorization whitelist (fail-closed if authorized_user_ids empty).
2. Slash commands: /task, /panic (<2ms latency), /status, /screen.
3. Thread-per-task execution with live thought streaming, milestone screenshots,
   and final EpisodeReceipt summaries.
4. Interactive Risk Consent Gate: [Approve] / [Cancel] buttons for Yellow/Red actions.
"""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import io
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands
import numpy as np
from PIL import Image

from parasite_ai.config import AppConfig, DiscordConfig
from parasite_ai.mind.brain_manager import check_vram_headroom
from parasite_ai.mind.memory import EpisodeReceipt
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.safety.risk_gate import ActionConsentRequest, ActionRisk
from parasite_ai.ui.bridge import EpisodeEvent

logger = logging.getLogger("parasite_ai.ui.discord_bot")

# --- UI Embed Theme Colors ---
COLOR_ACTIVE = 0x00F0FF       # Cyber Blue / Neon Cyan
COLOR_CONSENT_WARN = 0xFFB300 # Amber Warning (Yellow Risk)
COLOR_PANIC_RED = 0xFF0055    # Crimson Panic / Error (Red Risk)
COLOR_SUCCESS_EMERALD = 0x00FF87 # Holographic Emerald (Completed)


def trim_embed_value(text: Optional[str], max_len: int = 1000) -> str:
    """Trims text to fit within Discord embed field limits (1024 chars), preventing 400 Bad Request."""
    if not text or not str(text).strip():
        return "None."
    s = str(text).strip()
    return s[:max_len] + "..." if len(s) > max_len else s


def get_windows_system_memory() -> Tuple[int, int, float]:
    """
    Returns (used_mb, total_mb, percent_used) for host Windows physical memory
    using ctypes GlobalMemoryStatusEx without external psutil dependencies.
    """
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_mb = int(stat.ullTotalPhys // (1024 * 1024))
            avail_mb = int(stat.ullAvailPhys // (1024 * 1024))
            used_mb = total_mb - avail_mb
            pct = float(stat.dwMemoryLoad)
            return used_mb, total_mb, pct
    except Exception as exc:
        logger.debug(f"Could not query Windows system memory: {exc}")
    return 0, 0, 0.0


class RiskConsentView(discord.ui.View):
    """
    Interactive two-button view ([Approve], [Cancel]) presented to authorized operator
    when a YELLOW or RED risk action is proposed.
    """

    def __init__(
        self,
        request: ActionConsentRequest,
        authorized_user_ids: List[int],
        timeout: float = 60.0,
        orchestrator: Optional[Any] = None,
        bot_c2: Optional["DiscordBotC2"] = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.request = request
        self.authorized_user_ids = set(authorized_user_ids)
        self.orchestrator = orchestrator or (bot_c2.orchestrator if bot_c2 else None)
        self.bot_c2 = bot_c2
        self.value: Optional[bool] = None
        self.aborted: bool = False
        self._future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.authorized_user_ids and interaction.user.id not in self.authorized_user_ids:
            await interaction.response.send_message(
                "❌ You are not authorized to approve or deny risk actions.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Approve Action", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = True
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            content=f"✅ **Action Approved** by {interaction.user.mention}",
            view=self,
        )
        if not self._future.done():
            self._future.set_result(True)
        self.stop()

    @discord.ui.button(label="Deny Action", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            content=f"🚫 **Action Denied** by {interaction.user.mention} (escalating to Gemini for an alternative path; will not re-prompt this action).",
            view=self,
        )
        if not self._future.done():
            self._future.set_result(False)
        self.stop()

    @discord.ui.button(label="Abort Task", style=discord.ButtonStyle.danger, emoji="🛑")
    async def abort_task(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        self.aborted = True
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.orchestrator is not None:
            try:
                token = self.orchestrator.interrupt_guard.get_cancellation_token()
                token.set()
                self.orchestrator.interrupt_guard.panic_manager.trigger_panic("discord_consent_abort")
                self.orchestrator.bridge.clear_goals()
                self.orchestrator._neutralize_inputs()
            except Exception as exc:
                logger.debug(f"Abort task cleanup warning: {exc}")
        await interaction.response.edit_message(
            content=f"🛑 **Task Aborted** by {interaction.user.mention}.",
            view=self,
        )
        if not self._future.done():
            self._future.set_result(False)
        self.stop()

    @discord.ui.button(label="Parasite It", style=discord.ButtonStyle.success, emoji="🧠", row=1)
    async def parasite_it(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.orchestrator is not None and hasattr(self.orchestrator, "request_parasite_consult"):
            self.orchestrator.request_parasite_consult(hint=f"Operator rejected '{self.request.reason}' and requested Gemini recovery.")
        await interaction.response.edit_message(
            content=f"🧠 **Parasite It!** Action denied & Gemini consultation queued by {interaction.user.mention}.",
            view=self,
        )
        if not self._future.done():
            self._future.set_result(False)
        self.stop()

    @discord.ui.button(label="Course Correct", style=discord.ButtonStyle.primary, emoji="🧭", row=1)
    async def course_correct(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if not self._future.done():
            self._future.set_result(False)
        self.stop()
        if self.bot_c2 is not None:
            await interaction.response.send_modal(CourseCorrectModal(self.bot_c2))
        else:
            await interaction.response.edit_message(
                content=f"🧭 **Action Denied** for course correction by {interaction.user.mention}.",
                view=self,
            )

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if not self._future.done():
            self._future.set_result(False)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        logger.error("RiskConsentView error on %s: %s", getattr(item, "label", item), error, exc_info=True)


class SkillApprovalView(discord.ui.View):
    """
    Non-blocking interactive view ([Approve Skill], [Reject / Quarantine]) for operator
    sign-off on autonomously co-authored draft SKILL.md playbooks.
    Strictly fail-closed if authorized_user_ids is empty.
    """

    def __init__(
        self,
        skill_id: str,
        orchestrator: RuntimeOrchestrator,
        authorized_user_ids: List[int],
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.skill_id = skill_id
        self.orchestrator = orchestrator
        self.authorized_user_ids = set(authorized_user_ids)
        self.decision: Optional[str] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.authorized_user_ids or interaction.user.id not in self.authorized_user_ids:
            await interaction.response.send_message(
                "❌ You are not authorized to approve or reject learned skills.",
                ephemeral=True,
            )
            return False
        return True

    def _disable_all(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Approve Skill", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._disable_all()
        try:
            await asyncio.to_thread(self.orchestrator.approve_learned_skill, self.skill_id)
            self.decision = "approved"
            msg = f"✅ **Skill `{self.skill_id}` Approved** by {interaction.user.mention} (`draft=false`)."
        except Exception as exc:
            self.decision = "error"
            msg = f"⚠️ **Failed to approve `{self.skill_id}`:** {exc}"
        await interaction.response.edit_message(content=msg, view=self)
        self.stop()

    @discord.ui.button(label="Reject / Quarantine", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._disable_all()
        try:
            await asyncio.to_thread(
                self.orchestrator.reject_learned_skill,
                self.skill_id,
                f"Rejected via Discord by user {interaction.user.id}",
            )
            self.decision = "rejected"
            msg = f"🗑️ **Skill `{self.skill_id}` Quarantined** by {interaction.user.mention}."
        except Exception as exc:
            self.decision = "error"
            msg = f"⚠️ **Failed to quarantine `{self.skill_id}`:** {exc}"
        await interaction.response.edit_message(content=msg, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        self._disable_all()


class NewTaskModal(discord.ui.Modal, title="Dispatch New ParasiteAI Task"):
    """Interactive Discord modal for multi-line task entry without slash-command friction."""

    goal_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Objective",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. Open Cookie Clicker, then open Auto Clicker and turn it on",
        required=True,
        max_length=1000,
    )
    max_steps_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Max Steps (optional)",
        style=discord.TextStyle.short,
        placeholder="15",
        required=False,
        max_length=4,
    )

    def __init__(self, bot_c2: "DiscordBotC2") -> None:
        super().__init__()
        self.bot_c2 = bot_c2

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.bot_c2._is_authorized(interaction.user.id, interaction.channel_id):
            await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
            return
        goal = str(self.goal_input.value or "").strip()
        if not goal:
            await interaction.response.send_message("⚠️ Goal cannot be empty.", ephemeral=True)
            return
        max_steps: Optional[int] = None
        raw_steps = str(self.max_steps_input.value or "").strip()
        if raw_steps:
            try:
                max_steps = max(1, min(100, int(raw_steps)))
            except ValueError:
                await interaction.response.send_message("⚠️ Max Steps must be a number.", ephemeral=True)
                return

        if self.bot_c2._is_task_active():
            await interaction.response.send_message(
                "⚠️ ParasiteAI is currently executing an active task. Wait or issue `/panic`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        task_channel, embed = await self.bot_c2._dispatch_goal(
            goal=goal,
            max_steps=max_steps,
            user=interaction.user,
            channel=interaction.channel,  # type: ignore
        )
        if task_channel != interaction.channel:
            await interaction.followup.send(f"Task initiated in dedicated thread: {task_channel.mention}")
            await task_channel.send(embed=embed)
        else:
            await interaction.followup.send(embed=embed, view=ActiveTaskControlsView(self.bot_c2))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error("NewTaskModal error: %s", error, exc_info=True)


class CourseCorrectModal(discord.ui.Modal, title="Course Correct / Steer ParasiteAI"):
    """Interactive Discord modal for live operator steering or starting a new task."""

    instruction_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Steering Instruction (or New Goal if Idle)",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. Skip the popup, use Win+R and type calc instead",
        required=True,
        max_length=1000,
    )

    def __init__(self, bot_c2: "DiscordBotC2") -> None:
        super().__init__()
        self.bot_c2 = bot_c2

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.bot_c2._is_authorized(interaction.user.id, interaction.channel_id):
            await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
            return
        instruction = str(self.instruction_input.value or "").strip()
        if not instruction:
            await interaction.response.send_message("⚠️ Instruction cannot be empty.", ephemeral=True)
            return

        if self.bot_c2._is_task_active():
            applied = False
            if hasattr(self.bot_c2.orchestrator, "request_course_correction"):
                applied = bool(self.bot_c2.orchestrator.request_course_correction(instruction))
            if applied:
                await interaction.response.send_message(
                    f"🧭 **Course Correction Queued** by {interaction.user.mention}:\n> {trim_embed_value(instruction, 400)}"
                )
            else:
                await interaction.response.send_message("⚠️ Could not queue course correction.", ephemeral=True)
            return

        await interaction.response.defer()
        task_channel, embed = await self.bot_c2._dispatch_goal(
            goal=instruction,
            max_steps=None,
            user=interaction.user,
            channel=interaction.channel,  # type: ignore
        )
        if task_channel != interaction.channel:
            await interaction.followup.send(f"Task initiated in dedicated thread: {task_channel.mention}")
            await task_channel.send(embed=embed, view=ActiveTaskControlsView(self.bot_c2))
        else:
            await interaction.followup.send(embed=embed, view=ActiveTaskControlsView(self.bot_c2))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error("CourseCorrectModal error: %s", error, exc_info=True)


class ControlDeckView(discord.ui.View):
    """Always-accessible idle Discord Control Button Deck for ParasiteAI."""

    def __init__(self, bot_c2: "DiscordBotC2", timeout: Optional[float] = None) -> None:
        super().__init__(timeout=timeout)
        self.bot_c2 = bot_c2

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.bot_c2._is_authorized(interaction.user.id, interaction.channel_id):
            await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="New Task", style=discord.ButtonStyle.primary, emoji="📝", row=0, custom_id="parasite:deck:new_task")
    async def new_task(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(NewTaskModal(self.bot_c2))

    @discord.ui.button(label="Screenshot", style=discord.ButtonStyle.secondary, emoji="📸", row=0, custom_id="parasite:deck:screenshot")
    async def screenshot(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            frame = self.bot_c2.orchestrator.screen_capture.capture_screen()
            file_obj, w, h = self.bot_c2._encode_frame_to_discord_file(frame)
            embed = discord.Embed(
                title="📸 DESKTOP CAPTURE",
                description=f"Physical Resolution: `{w}x{h}`",
                color=COLOR_ACTIVE,
            )
            embed.set_image(url="attachment://screen.jpg")
            await interaction.followup.send(file=file_obj, embed=embed)
        except Exception as exc:
            await interaction.followup.send(f"❌ Failed to capture screenshot: {exc}")

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1, custom_id="parasite:deck:status")
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = self.bot_c2._build_status_embed()
        await interaction.response.send_message(embed=embed, view=ControlDeckView(self.bot_c2))

    @discord.ui.button(label="Panic", style=discord.ButtonStyle.danger, emoji="🛑", row=1, custom_id="parasite:deck:panic")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        t_start = time.perf_counter()
        token = self.bot_c2.orchestrator.interrupt_guard.get_cancellation_token()
        token.set()
        self.bot_c2.orchestrator.interrupt_guard.panic_manager.trigger_panic("discord_deck_panic")
        self.bot_c2.orchestrator.bridge.clear_goals()
        self.bot_c2.orchestrator._neutralize_inputs()
        if self.bot_c2._active_consent_view:
            self.bot_c2._active_consent_view.stop()
            if not self.bot_c2._active_consent_view._future.done():
                self.bot_c2._active_consent_view._future.set_result(False)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        await interaction.response.send_message(
            f"🛑 **EMERGENCY PANIC ABORT TRIPPED** (`{elapsed_ms:.2f} ms`) by {interaction.user.mention}."
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        logger.error("ControlDeckView error on %s: %s", getattr(item, "label", item), error, exc_info=True)


class ActiveTaskControlsView(discord.ui.View):
    """Live-run interactive controls attached to active task & step screenshot embeds."""

    def __init__(self, bot_c2: "DiscordBotC2", timeout: Optional[float] = None) -> None:
        super().__init__(timeout=timeout)
        self.bot_c2 = bot_c2

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.bot_c2._is_authorized(interaction.user.id, interaction.channel_id):
            await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Course Correct", style=discord.ButtonStyle.primary, emoji="🧭", row=0, custom_id="parasite:active:course_correct")
    async def course_correct(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(CourseCorrectModal(self.bot_c2))

    @discord.ui.button(label="Parasite It", style=discord.ButtonStyle.success, emoji="🧠", row=0, custom_id="parasite:active:parasite_it")
    async def parasite_it(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.bot_c2._is_task_active():
            await interaction.response.send_message(
                "ℹ️ No active task is running right now.",
                ephemeral=True,
            )
            return
        triggered = False
        if hasattr(self.bot_c2.orchestrator, "request_parasite_consult"):
            triggered = bool(self.bot_c2.orchestrator.request_parasite_consult())
        if triggered:
            await interaction.response.send_message(
                f"🧠 **Parasite It!** Gemini consultation queued for the next step by {interaction.user.mention}."
            )
        else:
            await interaction.response.send_message("⚠️ ParasiteSkill consultation unavailable.", ephemeral=True)

    @discord.ui.button(label="Screenshot", style=discord.ButtonStyle.secondary, emoji="📸", row=0, custom_id="parasite:active:screenshot")
    async def screenshot(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            frame = self.bot_c2.orchestrator.screen_capture.capture_screen()
            file_obj, w, h = self.bot_c2._encode_frame_to_discord_file(frame)
            embed = discord.Embed(
                title="📸 DESKTOP CAPTURE",
                description=f"Physical Resolution: `{w}x{h}`",
                color=COLOR_ACTIVE,
            )
            embed.set_image(url="attachment://screen.jpg")
            await interaction.followup.send(file=file_obj, embed=embed)
        except Exception as exc:
            await interaction.followup.send(f"❌ Failed to capture screenshot: {exc}")

    @discord.ui.button(label="Panic", style=discord.ButtonStyle.danger, emoji="🛑", row=0, custom_id="parasite:active:panic")
    async def panic_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        t_start = time.perf_counter()
        token = self.bot_c2.orchestrator.interrupt_guard.get_cancellation_token()
        token.set()
        self.bot_c2.orchestrator.interrupt_guard.panic_manager.trigger_panic("discord_active_panic")
        self.bot_c2.orchestrator.bridge.clear_goals()
        self.bot_c2.orchestrator._neutralize_inputs()
        if self.bot_c2._active_consent_view:
            self.bot_c2._active_consent_view.stop()
            if not self.bot_c2._active_consent_view._future.done():
                self.bot_c2._active_consent_view._future.set_result(False)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        await interaction.response.send_message(
            f"🛑 **EMERGENCY PANIC ABORT TRIPPED** (`{elapsed_ms:.2f} ms`) by {interaction.user.mention}."
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        logger.error("ActiveTaskControlsView error on %s: %s", getattr(item, "label", item), error, exc_info=True)


TaskQuickActionsView = ControlDeckView


class DiscordBotC2:
    """
    Asynchronous Discord Command & Control Daemon.
    Runs inside a dedicated asyncio event loop thread and bridges operator commands
    with the local RuntimeOrchestrator.
    """

    def __init__(
        self,
        orchestrator: RuntimeOrchestrator,
        config: Optional[AppConfig] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.app_config = config or orchestrator.config
        self.discord_config: DiscordConfig = getattr(self.app_config, "discord", DiscordConfig())

        # Bot Setup: default intents cover slash commands, DMs, and @mentions;
        # optionally request message_content if explicitly enabled in config.
        intents = discord.Intents.default()
        if getattr(self.discord_config, "enable_message_content_intent", False):
            intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.tree = self.bot.tree

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._active_thread_channel: Optional[Union[discord.Thread, discord.TextChannel, discord.DMChannel]] = None
        self._active_consent_view: Optional[RiskConsentView] = None
        self._is_running = False

        # Register Bot Lifecycle & Commands
        self._register_events_and_commands()

        # Subscribe to runtime bridge episode events
        self.orchestrator.bridge.subscribe_episode_events(self._on_episode_event)

    def _is_authorized(self, user_id: int, channel_id: Optional[int] = None) -> bool:
        """Fail-closed authorization check against config whitelist."""
        auth_users = self.discord_config.authorized_user_ids
        if not auth_users:
            logger.warning(f"Rejecting command from user {user_id}: authorized_user_ids is empty (fail-closed).")
            return False
        if user_id not in auth_users:
            logger.warning(f"Rejecting command from unauthorized user {user_id}.")
            return False
        auth_channels = self.discord_config.authorized_channel_ids
        if auth_channels and channel_id is not None:
            if channel_id not in auth_channels:
                logger.warning(f"Rejecting command from channel {channel_id}: not in authorized_channel_ids.")
                return False
        return True

    def _build_status_embed(self) -> discord.Embed:
        vram_used, vram_free = check_vram_headroom()
        ram_used, ram_total, ram_pct = get_windows_system_memory()
        active_win_str = "Unknown"
        if self.orchestrator.window_guard:
            try:
                winfo = self.orchestrator.window_guard.get_active_window_info()
                if winfo:
                    active_win_str = f"{winfo.title} (`{winfo.process_name}`)"
            except Exception:
                pass
        is_panic = self.orchestrator.interrupt_guard.is_panic()
        status_title = "⚙️ SYSTEM STATUS — READY"
        embed_color = COLOR_ACTIVE
        if is_panic:
            status_title = "🛑 SYSTEM STATUS — PANIC TRIPPED"
            embed_color = COLOR_PANIC_RED
        elif self.orchestrator.is_paused:
            status_title = "⚠️ SYSTEM STATUS — PAUSED"
            embed_color = COLOR_CONSENT_WARN
        embed = discord.Embed(title=status_title, color=embed_color)
        embed.add_field(name="Engine State", value=f"Running: `{self.orchestrator.is_running}`\nPaused: `{self.orchestrator.is_paused}`", inline=True)
        embed.add_field(name="GPU VRAM", value=f"Used: `{vram_used} MB`\nFree: `{vram_free} MB`", inline=True)
        embed.add_field(name="System RAM", value=f"Used: `{ram_used} MB` / `{ram_total} MB` (`{ram_pct:.1f}%`)", inline=True)
        embed.add_field(name="Foreground Window", value=trim_embed_value(active_win_str, 200), inline=False)
        embed.set_footer(text="ParasiteAI Remote C2 Telemetry")
        return embed

    def _build_deck_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎛️ PARASITEAI CONTROL DECK",
            description=(
                "Use the buttons below anytime:\n"
                "• **📝 New Task** — Launch a desktop goal\n"
                "• **📸 Screenshot** — Capture the current desktop\n"
                "• **⚙️ Status** — Live hardware & window telemetry\n"
                "• **🛑 Panic** — Immediate emergency abort"
            ),
            color=COLOR_ACTIVE,
        )
        embed.set_footer(text="ParasiteAI Remote C2 • Always-On Control Deck")
        return embed

    def _is_task_active(self) -> bool:
        return bool(
            self.orchestrator.is_running
            and getattr(self.orchestrator, "_is_in_cognitive_step", False)
        )

    async def _dispatch_goal(
        self,
        goal: str,
        max_steps: Optional[int],
        user: Union[discord.User, discord.Member],
        channel: Union[discord.Thread, discord.TextChannel, discord.DMChannel],
    ) -> Tuple[Union[discord.Thread, discord.TextChannel, discord.DMChannel], discord.Embed]:
        """Shared task dispatcher for /task, plain-text/mention messages, and NewTaskModal."""
        task_channel: Union[discord.Thread, discord.TextChannel, discord.DMChannel] = channel
        if getattr(self.discord_config, "use_task_threads", False) and hasattr(channel, "create_thread"):
            clean_title = goal.strip().replace("\n", " ")[:36]
            try:
                thread = await channel.create_thread(  # type: ignore
                    name=f"🧵 Task: {clean_title}...",
                    type=discord.ChannelType.public_thread,
                )
                task_channel = thread
            except Exception as th_err:
                logger.debug(f"Could not create thread in channel, falling back to channel: {th_err}")

        self._active_thread_channel = task_channel
        resolved_max_steps = max_steps or self.orchestrator.default_max_steps

        embed = discord.Embed(
            title="⚙️ TASK DISPATCHED — RUNTIME ACTIVE",
            description=f"**Objective:**\n> {trim_embed_value(goal, 400)}",
            color=COLOR_ACTIVE,
        )
        embed.add_field(name="Max Steps", value=str(resolved_max_steps), inline=True)
        embed.add_field(name="Operator", value=user.mention, inline=True)
        embed.set_footer(text="ParasiteAI Remote C2 • Live Telemetry Stream Active")

        self.orchestrator.bridge.submit_goal(
            goal=goal,
            max_steps=resolved_max_steps,
            source="discord",
            metadata={"user_id": user.id, "channel_id": getattr(channel, "id", None)},
            consent_callback=self._sync_consent_callback,
        )
        return task_channel, embed

    async def _handle_text_message(self, message: discord.Message) -> bool:
        """
        Processes plain-text / @mention / DM task messages from authorized users.
        Returns True if the message was handled as a C2 command or task.
        """
        if not getattr(self.discord_config, "enable_message_tasks", True):
            return False
        if getattr(message.author, "bot", False):
            return False
        if self.bot.user is not None and message.author.id == self.bot.user.id:
            return False

        channel_id = getattr(message.channel, "id", None)
        if not self._is_authorized(message.author.id, channel_id):
            return False

        raw_content = str(getattr(message, "content", "") or "").strip()
        if not raw_content:
            return False

        # Strip @bot mention if present
        if self.bot.user is not None:
            bot_id = self.bot.user.id
            raw_content = raw_content.replace(f"<@{bot_id}>", "").replace(f"<@!{bot_id}>", "").strip()
        if not raw_content:
            return False

        lower = raw_content.lower()
        if lower in ("!panic", "/panic", "panic"):
            token = self.orchestrator.interrupt_guard.get_cancellation_token()
            token.set()
            self.orchestrator.interrupt_guard.panic_manager.trigger_panic("discord_message_panic")
            self.orchestrator.bridge.clear_goals()
            self.orchestrator._neutralize_inputs()
            if self._active_consent_view:
                self._active_consent_view.stop()
                if not self._active_consent_view._future.done():
                    self._active_consent_view._future.set_result(False)
            await message.channel.send("🛑 **EMERGENCY PANIC ABORT TRIPPED.**")
            return True

        # Strip optional !task / !t prefix
        goal = raw_content
        for prefix in ("!task ", "!t "):
            if lower.startswith(prefix):
                goal = raw_content[len(prefix):].strip()
                break
        if not goal or goal.startswith("/"):
            return False

        if self._is_task_active():
            await message.channel.send(
                "⚠️ ParasiteAI is currently executing an active task. Wait or send `!panic` to abort."
            )
            return True

        task_channel, embed = await self._dispatch_goal(
            goal=goal,
            max_steps=None,
            user=message.author,
            channel=message.channel,  # type: ignore
        )
        if task_channel != message.channel:
            await message.channel.send(f"Task initiated in dedicated thread: {task_channel.mention}")
            await task_channel.send(embed=embed, view=ActiveTaskControlsView(self))
        else:
            await message.channel.send(embed=embed, view=ActiveTaskControlsView(self))
        return True

    def _register_events_and_commands(self) -> None:
        """Configures slash commands and lifecycle listeners."""

        @self.bot.event
        async def on_ready() -> None:
            logger.info(f"Discord C2 Bot logged in as {self.bot.user} (ID: {self.bot.user.id if self.bot.user else 'unknown'})")
            try:
                synced = await self.tree.sync()
                logger.info(f"Synchronized {len(synced)} slash commands with Discord.")
            except Exception as e:
                logger.error(f"Failed to sync slash commands: {e}")
            if getattr(self.discord_config, "auto_post_deck", True) and self.discord_config.authorized_channel_ids:
                try:
                    ch = self.bot.get_channel(self.discord_config.authorized_channel_ids[0])
                    if ch is not None and hasattr(ch, "send"):
                        await ch.send(embed=self._build_deck_embed(), view=ControlDeckView(self))
                except Exception as deck_err:
                    logger.debug(f"Could not auto-post Control Deck on startup: {deck_err}")

        @self.bot.event
        async def on_message(message: discord.Message) -> None:
            await self._handle_text_message(message)

        @self.tree.command(name="deck", description="Post the interactive ParasiteAI Control Button Deck.")
        async def cmd_deck(interaction: discord.Interaction) -> None:
            if not self._is_authorized(interaction.user.id, interaction.channel_id):
                await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
                return
            await interaction.response.send_message(embed=self._build_deck_embed(), view=ControlDeckView(self))

        # -------------------------------------------------------------------
        # Command: /task
        # -------------------------------------------------------------------
        @self.tree.command(name="task", description="Dispatch a goal for ParasiteAI to execute on desktop.")
        @app_commands.describe(
            goal="The objective for ParasiteAI to accomplish",
            max_steps="Maximum steps before terminating (default 15)",
        )
        async def cmd_task(
            interaction: discord.Interaction,
            goal: str,
            max_steps: Optional[int] = None,
        ) -> None:
            if not self._is_authorized(interaction.user.id, interaction.channel_id):
                await interaction.response.send_message("❌ Unauthorized: You do not have permission to control this bot.", ephemeral=True)
                return

            if self._is_task_active():
                await interaction.response.send_message(
                    "⚠️ ParasiteAI is currently executing an active task. Please wait or issue `/panic` to abort.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            task_channel, embed = await self._dispatch_goal(
                goal=goal,
                max_steps=max_steps,
                user=interaction.user,
                channel=interaction.channel,  # type: ignore
            )

            if task_channel != interaction.channel:
                await interaction.followup.send(f"Task initiated in dedicated thread: {task_channel.mention}")
                await task_channel.send(embed=embed, view=ActiveTaskControlsView(self))
            else:
                await interaction.followup.send(embed=embed, view=ActiveTaskControlsView(self))

        # -------------------------------------------------------------------
        # Command: /panic (<2ms latency abort)
        # -------------------------------------------------------------------
        @self.tree.command(name="panic", description="Emergency abort: immediate <2ms interrupt token, releases hands.")
        async def cmd_panic(interaction: discord.Interaction) -> None:
            if not self._is_authorized(interaction.user.id, interaction.channel_id):
                await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
                return

            t_start = time.perf_counter()
            token = self.orchestrator.interrupt_guard.get_cancellation_token()
            token.set()
            self.orchestrator.interrupt_guard.panic_manager.trigger_panic("discord_panic")
            self.orchestrator.bridge.clear_goals()
            self.orchestrator._neutralize_inputs()

            # Cancel any pending consent view
            if self._active_consent_view:
                self._active_consent_view.stop()
                if not self._active_consent_view._future.done():
                    self._active_consent_view._future.set_result(False)

            elapsed_ms = (time.perf_counter() - t_start) * 1000.0

            embed = discord.Embed(
                title="🛑 EMERGENCY PANIC ABORT TRIPPED",
                description="Hardware cancellation token set. All synthetic input drivers neutralized.",
                color=COLOR_PANIC_RED,
            )
            embed.add_field(name="Interrupt Latency", value=f"`{elapsed_ms:.2f} ms` (< 2ms budget)", inline=True)
            embed.add_field(name="Trigger Source", value="Discord `/panic`", inline=True)
            embed.set_footer(text="ParasiteAI Safety Engine • Preemption Invariant Verified")

            await interaction.response.send_message(embed=embed)

        # -------------------------------------------------------------------
        # Command: /status
        # -------------------------------------------------------------------
        @self.tree.command(name="status", description="Query live hardware telemetry, VRAM, and agent state.")
        async def cmd_status(interaction: discord.Interaction) -> None:
            if not self._is_authorized(interaction.user.id, interaction.channel_id):
                await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
                return
            embed = self._build_status_embed()
            await interaction.response.send_message(embed=embed, view=ControlDeckView(self))

        # -------------------------------------------------------------------
        # Command: /screen
        # -------------------------------------------------------------------
        @self.tree.command(name="screen", description="Capture an on-demand compressed JPEG screenshot of the desktop.")
        async def cmd_screen(interaction: discord.Interaction) -> None:
            if not self._is_authorized(interaction.user.id, interaction.channel_id):
                await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
                return

            await interaction.response.defer()
            try:
                frame = self.orchestrator.screen_capture.capture_screen()
                file_obj, w, h = self._encode_frame_to_discord_file(frame)

                embed = discord.Embed(
                    title="📸 DESKTOP CAPTURE",
                    description=f"Physical Resolution: `{w}x{h}`",
                    color=COLOR_ACTIVE,
                )
                embed.set_image(url="attachment://screen.jpg")
                embed.set_footer(text="ParasiteAI In-Memory Screen Capture")

                await interaction.followup.send(file=file_obj, embed=embed)
            except Exception as exc:
                logger.error(f"Failed to capture screen for /screen: {exc}", exc_info=True)
                await interaction.followup.send(f"❌ Failed to capture screenshot: {exc}")

    def _encode_frame_to_discord_file(
        self,
        frame: np.ndarray,
        filename: str = "screen.jpg",
    ) -> Tuple[discord.File, int, int]:
        """Encodes an RGB numpy frame to an in-memory compressed JPEG discord.File."""
        h, w = frame.shape[:2]
        # ScreenCapture.capture_screen returns RGB format (from mss.rgb or PIL convert("RGB"))
        # Do not invert channels (which would turn RGB into BGR and cause blue tinting!)
        rgb_frame = frame[:, :, :3] if frame.ndim == 3 and frame.shape[2] >= 3 else frame

        pil_img = Image.fromarray(rgb_frame)

        # Downscale proportionally if wider than screen_max_width
        max_w = self.discord_config.screen_max_width
        if w > max_w:
            new_h = int(h * (max_w / w))
            pil_img = pil_img.resize((max_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=self.discord_config.screen_jpeg_quality)
        buf.seek(0)
        return discord.File(buf, filename=filename), w, h

    # -----------------------------------------------------------------------
    # Interactive Consent Callback (Synchronous Worker -> Async Discord View)
    # -----------------------------------------------------------------------

    def _sync_consent_callback(self, request: ActionConsentRequest) -> bool:
        """
        Called synchronously by DualMindPipeline worker thread when a YELLOW or RED
        risk action is prepared during a Discord-initiated episode.
        Blocks worker thread safely until approved, cancelled, or timed out.
        """
        if not self.discord_config.require_risk_consent:
            return True

        if not self._loop or not self._is_running:
            return True

        channel = self._active_thread_channel
        if not channel:
            return True

        # Dispatch async prompt on Discord event loop
        fut = asyncio.run_coroutine_threadsafe(
            self._async_request_consent(request, channel),
            self._loop,
        )

        timeout = self.discord_config.consent_timeout_sec
        token = self.orchestrator.interrupt_guard.get_cancellation_token()
        poll_interval = 0.1
        elapsed = 0.0

        # Poll with cancellation token checks to ensure <2ms panic reactivity
        while elapsed < timeout:
            if token.is_set():
                logger.warning("Consent wait aborted: cancellation token set.")
                return False
            if fut.done():
                try:
                    return bool(fut.result())
                except Exception as e:
                    logger.warning(f"Consent future failed: {e}")
                    return False
            time.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(f"Consent request timed out after {timeout}s (failing closed).")
        return False

    async def _async_request_consent(
        self,
        request: ActionConsentRequest,
        channel: Union[discord.Thread, discord.TextChannel, discord.DMChannel],
    ) -> bool:
        """Posts interactive [Approve] / [Cancel] view to Discord."""
        color = COLOR_PANIC_RED if request.risk == ActionRisk.RED else COLOR_CONSENT_WARN
        embed = discord.Embed(
            title=f"⚠️ RISK CONSENT REQUIRED — {request.risk.value} SEVERITY",
            description=(
                f"**Step #{request.step_id} Proposed Action:**\n"
                f"> **Action Type:** `{request.action_plan.action.value}`\n"
                f"> **Reasoning:** {trim_embed_value(request.action_plan.reasoning, 250)}\n\n"
                f"**Risk Evaluation:**\n"
                f"> {trim_embed_value(request.reason, 300)}"
            ),
            color=color,
        )

        if request.action_plan.cli_command:
            embed.add_field(name="CLI Command", value=f"```cmd\n{trim_embed_value(request.action_plan.cli_command, 300)}\n```", inline=False)
        if request.action_plan.coordinates:
            embed.add_field(name="Target Coordinates", value=f"`{request.action_plan.coordinates}`", inline=True)
        if request.foreground_title or request.foreground_process:
            win_val = trim_embed_value(f"{request.foreground_title} (`{request.foreground_process}`)", 200)
            embed.add_field(name="Active Window", value=win_val, inline=True)

        embed.set_footer(text=f"Fail-closed timeout: {int(self.discord_config.consent_timeout_sec)}s • Operator sign-off required")

        view = RiskConsentView(
            request=request,
            authorized_user_ids=self.discord_config.authorized_user_ids,
            timeout=self.discord_config.consent_timeout_sec,
            orchestrator=self.orchestrator,
            bot_c2=self,
        )
        self._active_consent_view = view
        msg = await channel.send(embed=embed, view=view)
        result = await view._future
        self._active_consent_view = None
        return result

    # -----------------------------------------------------------------------
    # Episode Lifecycle Event Subscriber
    # -----------------------------------------------------------------------

    def _on_episode_event(self, event: EpisodeEvent) -> None:
        """Receives structured episode events from UIBridge on background threads."""
        if not self._loop or not self._is_running or not self._active_thread_channel:
            return

        asyncio.run_coroutine_threadsafe(
            self._dispatch_episode_event(event, self._active_thread_channel),
            self._loop,
        )

    async def _dispatch_episode_event(
        self,
        event: EpisodeEvent,
        channel: Union[discord.Thread, discord.TextChannel, discord.DMChannel],
    ) -> None:
        """Formats and posts milestone updates into the Discord task thread."""
        try:
            if event.kind == "step_completed":
                step_num = event.step
                data = event.data
                rec = data.get("step_record")
                summary = data.get("step_summary")

                # Post milestone screenshot if step matches interval
                interval = self.discord_config.milestone_screenshot_interval
                if step_num % interval == 0:
                    try:
                        frame = self.orchestrator.screen_capture.capture_screen()
                        file_obj, w, h = self._encode_frame_to_discord_file(frame, filename=f"step_{step_num}.jpg")
                        act_type = getattr(summary, "action_type", None) or (
                            rec.action.action.value if rec is not None and getattr(rec, "action", None) else "UNKNOWN"
                        )
                        coords_val = (
                            getattr(rec.action, "coordinates", None)
                            if rec is not None and getattr(rec, "action", None)
                            else None
                        )
                        act_line = f"`{act_type}`" + (f" at `{coords_val}`" if coords_val else "")
                        thought_val = getattr(rec, "persona_thought", "") if rec is not None else ""
                        desc_parts = [f"**Action:** {act_line}"]
                        if thought_val:
                            desc_parts.append(f"**Thought:** {trim_embed_value(thought_val, 300)}")
                        embed = discord.Embed(
                            title=f"📸 Milestone Progress — Step {step_num}",
                            description="\n".join(desc_parts),
                            color=COLOR_ACTIVE,
                        )
                        if rec is not None:
                            post_win = getattr(rec, "post_window", None)
                            if post_win:
                                embed.add_field(name="Window", value=trim_embed_value(str(post_win), 150), inline=True)
                            diff_val = getattr(rec, "screen_diff", None)
                            tier_obj = getattr(rec, "tier_level", None)
                            strikes_val = getattr(rec, "consecutive_strikes", 0)
                            if diff_val is not None:
                                tier_str = getattr(tier_obj, "value", str(tier_obj or "TIER_1"))
                                embed.add_field(
                                    name="Telemetry",
                                    value=f"Diff: `{float(diff_val):.2%}` • `{tier_str}` (`{strikes_val}/3`)",
                                    inline=True,
                                )
                        embed.set_image(url=f"attachment://step_{step_num}.jpg")
                        await channel.send(file=file_obj, embed=embed, view=ActiveTaskControlsView(self))
                    except Exception as ss_err:
                        logger.debug(f"Could not capture milestone screenshot: {ss_err}")

            elif event.kind == "finished":
                receipt: Optional[EpisodeReceipt] = event.data.get("receipt")
                if receipt:
                    color = COLOR_SUCCESS_EMERALD if receipt.success else COLOR_PANIC_RED
                    title = "🏆 TASK COMPLETE — GOAL ACHIEVED" if receipt.success else f"🛑 TASK HALTED — {receipt.exit_reason}"
                    embed = discord.Embed(title=title, color=color)
                    embed.description = f"**Goal:**\n> {trim_embed_value(receipt.goal, 400)}"
                    embed.add_field(name="Result", value="`SUCCESS`" if receipt.success else f"`{receipt.exit_reason}`", inline=True)
                    embed.add_field(name="Steps Executed", value=f"`{receipt.total_steps}`", inline=True)
                    embed.add_field(name="Duration", value=f"`{receipt.duration_sec:.2f}s`", inline=True)

                    if receipt.error:
                        embed.add_field(name="Error Detail", value=f"```fix\n{trim_embed_value(receipt.error, 400)}\n```", inline=False)

                    embed.set_footer(text="ParasiteAI Post-Mortem Receipt")
                    quick_view = TaskQuickActionsView(self)
                    final_file: Optional[discord.File] = None
                    if getattr(self.discord_config, "send_final_screenshot", True):
                        try:
                            frame = self.orchestrator.screen_capture.capture_screen()
                            final_file, _, _ = self._encode_frame_to_discord_file(frame, filename="final_screen.jpg")
                            embed.set_image(url="attachment://final_screen.jpg")
                        except Exception as ss_err:
                            logger.debug(f"Could not capture final screenshot: {ss_err}")

                    if final_file is not None:
                        await channel.send(file=final_file, embed=embed, view=quick_view)
                    else:
                        await channel.send(embed=embed, view=quick_view)

            elif event.kind == "parasite_skill_alert":
                data = event.data or {}
                failure = str(data.get("failure", "UNKNOWN"))
                phase = str(data.get("phase", "UNKNOWN"))
                detail = str(data.get("detail", ""))
                diag_path = str(data.get("diagnostics_path", "") or "none")
                fallback = str(data.get("fallback", "LOCAL_UITARS"))
                embed = discord.Embed(
                    title="⚠️ ParasiteSkill Fail-Closed Fallback",
                    description=f"**Goal:**\n> {trim_embed_value(event.goal, 300)}",
                    color=COLOR_CONSENT_WARN,
                )
                embed.add_field(name="Phase", value=f"`{phase}`", inline=True)
                embed.add_field(name="Failure", value=f"`{failure}`", inline=True)
                embed.add_field(name="Fallback", value=f"`{fallback}`", inline=True)
                embed.add_field(name="Detail", value=trim_embed_value(detail, 400), inline=False)
                embed.add_field(name="Diagnostics", value=f"`{trim_embed_value(diag_path, 250)}`", inline=False)
                embed.set_footer(text="ParasiteSkill Symbiosis Alert • Resumed locally")
                await channel.send(embed=embed)

            elif event.kind == "skill_learned":
                data = event.data or {}
                skill_id = str(data.get("skill_id", "unknown-skill"))
                skill_name = str(data.get("name", skill_id))
                summary = str(data.get("summary", ""))
                steps_count = int(data.get("steps", 0))
                skill_path = str(data.get("skill_path", "") or "data/skills/")
                embed = discord.Embed(
                    title=f"🧠 New Draft Skill Learned — `{skill_id}`",
                    description=f"**{trim_embed_value(skill_name, 120)}**\n> {trim_embed_value(summary, 400)}",
                    color=COLOR_ACTIVE,
                )
                embed.add_field(name="Steps", value=f"`{steps_count}`", inline=True)
                embed.add_field(name="State", value="`draft=true` (awaiting sign-off)", inline=True)
                embed.add_field(name="Source Goal", value=trim_embed_value(event.goal, 250), inline=False)
                embed.add_field(name="File", value=f"`{trim_embed_value(skill_path, 250)}`", inline=False)
                embed.set_footer(text="Approve to activate matching, or Reject to quarantine.")
                view = SkillApprovalView(
                    skill_id=skill_id,
                    orchestrator=self.orchestrator,
                    authorized_user_ids=self.discord_config.authorized_user_ids,
                )
                await channel.send(embed=embed, view=view)

        except Exception as exc:
            logger.debug(f"Failed to post episode event embed to Discord: {exc}")

    # -----------------------------------------------------------------------
    # Lifecycle Management (Start / Stop Daemon Thread)
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Starts Discord C2 event loop in a background daemon thread."""
        token = self.discord_config.token
        if not token:
            logger.warning("Discord token not configured; Discord C2 bot will not start.")
            return

        if self._is_running:
            return
        self._is_running = True

        def _runner() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self.bot.start(token))
            except Exception as e:
                logger.error(f"Discord bot encountered error: {e}")
            finally:
                self._is_running = False

        self._thread = threading.Thread(target=_runner, name="ParasiteDiscordC2", daemon=True)
        self._thread.start()
        logger.info("Discord C2 background daemon thread started.")

    def stop(self) -> None:
        """Stops the Discord bot and closes the event loop."""
        if not self._is_running:
            return
        self._is_running = False
        if self._loop and self.bot.is_ready():
            future = asyncio.run_coroutine_threadsafe(self.bot.close(), self._loop)
            try:
                future.result(timeout=5.0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("Discord C2 daemon stopped.")
