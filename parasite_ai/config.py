"""
ParasiteAI - Unified System Configuration Engine (Pydantic V2).
Provides declarative, typed, and validated configuration for all subsystems.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Helpers & Validators
# ---------------------------------------------------------------------------

HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def validate_hex_color(v: str) -> str:
    """Ensure string is a valid hex color code (#RGB, #RRGGBB, #RRGGBBAA)."""
    if not isinstance(v, str) or not HEX_COLOR_PATTERN.match(v):
        raise ValueError(f"Invalid hex color format: '{v}'. Expected #RGB, #RRGGBB, or #RRGGBBAA")
    return v


# ---------------------------------------------------------------------------
# Subsystem Configurations
# ---------------------------------------------------------------------------

class SystemConfig(BaseModel):
    """Core operating environment and filesystem directories."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging verbosity level."
    )
    integrity_mode: Literal["development", "production", "testing"] = Field(
        default="development",
        description="System integrity and assertion mode."
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Path to store persistent telemetry, screenshots, and logs."
    )
    models_dir: Path = Field(
        default=Path("models"),
        description="Directory for local GGUF weights."
    )

    @field_validator("data_dir", "models_dir", mode="before")
    @classmethod
    def parse_path(cls, v: Any) -> Path:
        return Path(v) if not isinstance(v, Path) else v


class PersonaConfig(BaseModel):
    """Character identity, speech styling, and system prompt."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    name: str = Field(default="Parasite", description="Assistant persona name.")
    avatar: str = Field(default="cyber_cat", description="Visual avatar asset identifier.")
    voice_style: str = Field(
        default="witty_desktop_companion",
        description="Stylistic prompt descriptor for monologue generation."
    )
    verbosity: Literal["concise", "normal", "verbose"] = Field(
        default="normal",
        description="Dialogue length preference."
    )
    system_prompt: str = Field(
        default=(
            "You are Parasite, a desktop-native AI companion living on the user's screen.\n"
            "You have direct physical control of the mouse and keyboard when authorized.\n"
            "Speak naturally, expressively, and vividly in character.\n"
            "Always provide commentary on what you observe on screen before taking action."
        ),
        description="Pass 1 Persona monologue system instruction."
    )


class LocalModelConfig(BaseModel):
    """GGUF runtime configuration for local GPU execution."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    model_id: str = Field(
        default="Qwen/Qwen2.5-3B-Instruct-GGUF",
        description="HuggingFace model repository ID."
    )
    filename: str = Field(
        default="qwen2.5-3b-instruct-q4_k_m.gguf",
        description="Quantized GGUF filename within the repository."
    )
    context_size: int = Field(
        default=4096,
        ge=512,
        le=32768,
        description="Inference context window length in tokens."
    )
    gpu_layers: int = Field(
        default=-1,
        description="Number of layers offloaded to GPU (-1 = all available)."
    )
    vram_budget_mb: int = Field(
        default=5500,
        ge=1024,
        le=32768,
        description="Safe maximum VRAM allocation ceiling in megabytes."
    )
    local_endpoint: str = Field(
        default="http://127.0.0.1:8080/v1",
        description="HTTP base endpoint for external llama-server or Ollama."
    )
    download_auto: bool = Field(
        default=False,
        description="Automatically trigger GGUF download if missing on startup."
    )


class BrowserOffloadConfig(BaseModel):
    """Configuration for physical desktop browser offloading."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    preferred_browser: Literal["chrome", "opera_gx"] = Field(
        default="chrome",
        description="Primary browser targeted for visible physical offloading."
    )
    browser_paths: Dict[str, Path] = Field(
        default_factory=lambda: {
            "chrome": Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            "opera_gx": Path(r"C:\Users\Suici\AppData\Local\Programs\Opera GX\opera.exe"),
        },
        description="Absolute filesystem paths to installed web browsers."
    )
    default_web_ai_url: str = Field(
        default="https://gemini.google.com",
        description="Default frontier AI web interface for reasoning offload."
    )
    stream_stability_ms: int = Field(
        default=1500,
        ge=500,
        le=10000,
        description="Duration screen diff must remain settled before harvesting text."
    )
    stream_timeout_sec: int = Field(
        default=45,
        ge=10,
        le=300,
        description="Maximum seconds to wait for web AI streaming completion."
    )
    sentinel_token_prefix: str = Field(
        default="__PARASITE_SENTINEL__",
        description="Unique clipboard boundary token for verification."
    )

    @field_validator("browser_paths", mode="before")
    @classmethod
    def parse_browser_paths(cls, v: Any) -> Dict[str, Path]:
        if isinstance(v, dict):
            return {k: Path(p) if not isinstance(p, Path) else p for k, p in v.items()}
        return v


class BrainConfig(BaseModel):
    """Unified brain coordination configuration (pluggable backends)."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
        default="browser_offload",
        description="Cognitive execution mode (browser_offload provides instant zero-VRAM startup)."
    )
    local_model: LocalModelConfig = Field(
        default_factory=LocalModelConfig,
        description="GGUF local model execution settings."
    )
    offload: BrowserOffloadConfig = Field(
        default_factory=BrowserOffloadConfig,
        description="Desktop browser offloader settings."
    )


class SafetyConfig(BaseModel):
    """Win32 low-level hardware hooks, panic triggers, and window guard."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    interrupt_enabled: bool = Field(
        default=True,
        description="Enable Win32 low-level hooks for instant physical touch abort."
    )
    interrupt_latency_budget_ms: float = Field(
        default=2.0,
        ge=0.1,
        le=50.0,
        description="Target maximum abort latency budget on physical touch."
    )
    override_pause_duration_sec: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        description="Seconds to yield control to human user after a physical touch event."
    )
    panic_hotkeys: List[str] = Field(
        default_factory=lambda: ["ctrl+alt+backspace", "ctrl+alt+p", "esc"],
        description="Global hotkeys triggering instant emergency abort."
    )
    corner_panic_enabled: bool = Field(
        default=True,
        description="Enable cursor slam into screen corners as an emergency abort trigger."
    )
    corner_distance_px: int = Field(
        default=4,
        ge=1,
        le=50,
        description="Pixel distance from display boundary triggering corner panic."
    )
    sensitive_window_titles: List[str] = Field(
        default_factory=lambda: [
            "Bitwarden",
            "1Password",
            "KeePass",
            "Task Manager",
            "Administrator:",
            "Windows Security",
            "User Account Control",
            "Registry Editor",
        ],
        description="Window title substrings triggering immediate privacy blackout and action halt."
    )
    sensitive_process_names: List[str] = Field(
        default_factory=lambda: [
            "bitwarden.exe",
            "1password.exe",
            "keepass.exe",
            "keepassxc.exe",
            "taskmgr.exe",
            "regedit.exe",
            "credentialui.exe",
            "consent.exe",
            "logonui.exe",
        ],
        description="Executable filenames triggering privacy pause."
    )
    mask_screen_on_sensitive: bool = Field(
        default=True,
        description="Replace perception screenshots with a blank frame when sensitive windows are active."
    )


class CompanionDockConfig(BaseModel):
    """PyQt6 desktop companion dock widget geometry and styling."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    width: int = Field(default=340, ge=240, le=800, description="Dock window width in pixels.")
    height: int = Field(default=540, ge=300, le=1200, description="Dock window height in pixels.")
    anchor: Literal["bottom_right", "bottom_left", "top_right", "top_left", "custom"] = Field(
        default="bottom_right",
        description="Screen corner anchor position."
    )
    margin_x: int = Field(default=24, ge=0, le=200, description="Horizontal margin from display border.")
    margin_y: int = Field(default=24, ge=0, le=200, description="Vertical margin from display border.")
    opacity: float = Field(default=0.95, ge=0.2, le=1.0, description="Window transparency opacity.")
    always_on_top: bool = Field(default=True, description="Enforce topmost z-order flag.")
    frameless: bool = Field(default=True, description="Remove operating system window chrome.")
    show_thought_stream: bool = Field(default=True, description="Render live internal thought text area.")
    show_perception_preview: bool = Field(default=True, description="Render downscaled perception thumbnail.")


class GhostHUDConfig(BaseModel):
    """Transparent click-through Win32 layered overlay (Set-of-Mark)."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    enabled: bool = Field(default=True, description="Render visual Set-of-Mark overlay on desktop.")
    fps_target: int = Field(default=60, ge=15, le=144, description="Target animation frame rate.")
    reticle_color: str = Field(default="#FF3366", description="Pre-click reticle hex color.")
    reticle_duration_ms: int = Field(
        default=300,
        ge=100,
        le=2000,
        description="Pre-click visual targeting preview duration before physical mouse motion."
    )
    som_box_color: str = Field(default="#00E5FF", description="Default bounding box stroke color.")
    som_glow_color: str = Field(default="#00FFCC", description="Grounded element highlight accent color.")
    box_alpha: float = Field(default=0.25, ge=0.0, le=1.0, description="Fill opacity for bounding boxes.")
    stroke_width_px: float = Field(default=1.5, ge=0.5, le=5.0, description="Bounding box stroke width.")

    @field_validator("reticle_color", "som_box_color", "som_glow_color")
    @classmethod
    def check_colors(cls, v: str) -> str:
        return validate_hex_color(v)


class UIConfig(BaseModel):
    """Top-level GUI settings."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    dock: CompanionDockConfig = Field(default_factory=CompanionDockConfig)
    hud: GhostHUDConfig = Field(default_factory=GhostHUDConfig)


class VisionConfig(BaseModel):
    """Screen capture and hybrid grounding engine parameters."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    grounding_mode: Literal["hybrid", "uia_only", "ocr_only"] = Field(
        default="hybrid",
        description="Element grounding backend (hybrid = Win32 UIA + Scoped RapidOCR)."
    )
    max_som_elements: int = Field(
        default=60,
        ge=5,
        le=200,
        description="Maximum interactive elements tagged in a single frame."
    )
    screen_diff_threshold: float = Field(
        default=0.02,
        ge=0.001,
        le=0.5,
        description="Visual difference ratio required to confirm action success."
    )
    ocr_scoped_only: bool = Field(
        default=True,
        description="Scope RapidOCR strictly to active window rectangle to maximize speed."
    )
    capture_backend: Literal["mss", "pillow", "win32"] = Field(
        default="mss",
        description="Fast screen buffer capture provider."
    )
    settling_diff_threshold: float = Field(
        default=0.003,
        ge=0.0001,
        le=0.05,
        description="Frame difference threshold below which screen is considered settled."
    )
    settling_consecutive_polls: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Consecutive settled frames required to confirm render stabilization."
    )


class MouseConfig(BaseModel):
    """Kinematic mouse trajectory generator parameters."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    speed_factor: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Movement duration multiplier (lower = faster, higher = slower)."
    )
    trajectory_type: Literal["cubic_bezier", "min_jerk", "linear"] = Field(
        default="cubic_bezier",
        description="Kinematic trajectory curve algorithm."
    )
    overshoot_radius_px: int = Field(
        default=12,
        ge=0,
        le=100,
        description="Maximum pixel overshoot before final corrective landing."
    )
    micro_jitter_amplitude_px: float = Field(
        default=1.5,
        ge=0.0,
        le=10.0,
        description="Amplitude of simulated physiological motor tremor."
    )
    step_delay_ms: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Sleep delay between successive cursor trajectory points."
    )
    preview_reticle_ms: int = Field(
        default=300,
        ge=0,
        le=2000,
        description="Targeting preview delay before physical mouse moves."
    )


class KeyboardConfig(BaseModel):
    """Physical Unicode typing engine parameters."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    typing_wpm: int = Field(
        default=85,
        ge=10,
        le=300,
        description="Nominal typing speed in words per minute."
    )
    cadence_jitter_ms: Tuple[int, int] = Field(
        default=(25, 75),
        description="Random interval bounds added between keystrokes."
    )
    micro_pause_probability: float = Field(
        default=0.04,
        ge=0.0,
        le=0.5,
        description="Probability of human-like micro-pause between words."
    )
    micro_pause_duration_ms: Tuple[int, int] = Field(
        default=(200, 600),
        description="Duration bounds for micro-pauses."
    )
    punctuation_pause_ms: Tuple[int, int] = Field(
        default=(80, 150),
        description="Extra pause after punctuation marks."
    )
    multiline_shift_enter: bool = Field(
        default=True,
        description="Emit Shift+Enter for interior newlines to prevent premature chat form submission."
    )


class HandsConfig(BaseModel):
    """Physical hardware input execution layer."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    mouse: MouseConfig = Field(default_factory=MouseConfig)
    keyboard: KeyboardConfig = Field(default_factory=KeyboardConfig)


# ---------------------------------------------------------------------------
# Master Application Configuration
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    """Master configuration root container for ParasiteAI."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    system: SystemConfig = Field(default_factory=SystemConfig)
    persona: PersonaConfig = Field(default_factory=PersonaConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    hands: HandsConfig = Field(default_factory=HandsConfig)

    @property
    def mind(self) -> BrainConfig:
        """Alias property to ensure access via cfg.mind matches cfg.brain."""
        return self.brain

    @model_validator(mode="before")
    @classmethod
    def handle_aliases_and_env(cls, data: Any) -> Any:
        """Alias 'mind' -> 'brain' and apply environment variable overrides."""
        if not isinstance(data, dict):
            return data

        # Backward compatibility alias: allow 'mind' to populate 'brain'
        if "mind" in data and "brain" not in data:
            data["brain"] = data.pop("mind")

        def _get_section_dict(key: str) -> Dict[str, Any]:
            val = data.get(key)
            if isinstance(val, BaseModel):
                d = val.model_dump()
            elif isinstance(val, dict):
                d = val
            else:
                d = {}
            data[key] = d
            return d

        # Environment variable overrides
        env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
        if env_log_level:
            _get_section_dict("system")["log_level"] = env_log_level.upper()

        env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
        if env_brain_mode:
            _get_section_dict("brain")["mode"] = env_brain_mode.lower()

        env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
        if env_integrity:
            _get_section_dict("system")["integrity_mode"] = env_integrity.lower()

        return data


# ---------------------------------------------------------------------------
# YAML Loading, Saving & Self-Healing Utilities
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_FILENAME = "config.yaml"


def _path_representer(dumper: yaml.SafeDumper, data: Path) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.SafeDumper.add_representer(Path, _path_representer)


def get_default_config() -> AppConfig:
    """Instantiate a fully-populated AppConfig with host-verified default values."""
    return AppConfig()


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """
    Load and validate configuration from YAML file.
    If the file does not exist, automatically generates a documented default config.yaml
    and returns a valid default AppConfig (Zero-Config Principle).
    """
    path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_FILENAME)

    if not path.is_file():
        default_cfg = get_default_config()
        try:
            save_config(default_cfg, path)
        except OSError:
            # Gracefully continue if working directory is write-protected
            pass
        return default_cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as exc:
        raise ValueError(f"Failed to read configuration YAML at {path}: {exc}") from exc

    if raw_data is None:
        raw_data = {}

    return AppConfig.model_validate(raw_data)


def save_config(config: AppConfig, config_path: Path | str | None = None) -> None:
    """Serialize AppConfig into formatted YAML file."""
    path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)

    raw_dict = config.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw_dict, f, default_flow_style=False, sort_keys=False, indent=2)
