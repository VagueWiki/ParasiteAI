# ParasiteAI — Configuration Architecture & Schema Specification (M1)

**Component:** `parasite_ai/config.py` & `config.yaml`  
**Author:** `teamwork_explorer_m1_2`  
**Milestone:** M1 (Foundation & Zero-Config Setup)  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Objective

The ParasiteAI configuration subsystem establishes the **declarative contract** between the user, the operating system, and all internal subsystems (`safety`, `hands`, `ui`, `vision`, and `mind`).

### Key Design Pillars
1. **Zero-Config Self-Healing:** The application must boot instantly with zero manual configuration. If `config.yaml` is absent, the system automatically instantiates host-optimized defaults and generates a documented `config.yaml` without user intervention.
2. **Pydantic V2 Strict Validation:** Every parameter is typed, bounded, and validated using Pydantic V2 (`BaseModel`, `Field`, `field_validator`, `model_validator`, `ConfigDict`). Malformed values fail fast with clear human diagnostics rather than causing runtime crashes during physical execution.
3. **Host-Aware Defaults:** Defaults match verified system capabilities: NVIDIA RTX 4060 (8 GB VRAM -> 5500 MB budget ceiling), Windows 11 high-DPI scaling, installed browsers (Google Chrome and Opera GX), and dual-mode brain flexibility (Browser Offload default for instant zero-download startup).
4. **Resilient Aliasing:** Accepts either `brain:` or `mind:` top-level keys in YAML to guarantee backwards-compatibility with architectural surveys and future extensions.
5. **Environment Variable Overrides:** Supports runtime overrides via prefixed environment variables (e.g., `PARASITE_LOG_LEVEL=DEBUG`, `PARASITE_BRAIN_MODE=browser_offload`).

---

## 2. Pydantic V2 Configuration Architecture

### 2.1 Model Hierarchy Tree

```
AppConfig (Root)
├── system: SystemConfig
├── persona: PersonaConfig
├── brain: BrainConfig (Alias: mind)
│   ├── local_model: LocalModelConfig
│   └── offload: BrowserOffloadConfig
├── safety: SafetyConfig
├── ui: UIConfig
│   ├── dock: CompanionDockConfig
│   └── hud: GhostHUDConfig
├── vision: VisionConfig
└── hands: HandsConfig
    ├── mouse: MouseConfig
    └── keyboard: KeyboardConfig
```

---

## 3. Complete Source Specification: `parasite_ai/config.py`

Below is the exact production-ready specification for `parasite_ai/config.py`:

```python
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


class BrainConfig(BaseModel):
    """Unified brain coordination configuration (pluggable backends)."""
    model_config = ConfigDict(extra="ignore", validate_default=True, str_strip_whitespace=True)

    mode: Literal["local_llm", "browser_offload", "hybrid"] = Field(
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

    @model_validator(mode="before")
    @classmethod
    def handle_aliases_and_env(cls, data: Any) -> Any:
        """Alias 'mind' -> 'brain' and apply environment variable overrides."""
        if not isinstance(data, dict):
            return data

        # Backward compatibility alias: allow 'mind' to populate 'brain'
        if "mind" in data and "brain" not in data:
            data["brain"] = data.pop("mind")

        # Environment variable overrides
        env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
        if env_log_level:
            data.setdefault("system", {})["log_level"] = env_log_level.upper()

        env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
        if env_brain_mode:
            data.setdefault("brain", {})["mode"] = env_brain_mode.lower()

        env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
        if env_integrity:
            data.setdefault("system", {})["integrity_mode"] = env_integrity.lower()

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
```

---

## 4. Default `config.yaml` Reference Specification

When `config.yaml` is generated or placed in `g:\__Docs\ParasiteAI\config.yaml`, it contains:

```yaml
# ==============================================================================
# ParasiteAI - Unified System Configuration
# ==============================================================================

system:
  log_level: "INFO"
  integrity_mode: "development"
  data_dir: "data"
  models_dir: "models"

persona:
  name: "Parasite"
  avatar: "cyber_cat"
  voice_style: "witty_desktop_companion"
  verbosity: "normal"
  system_prompt: |
    You are Parasite, a desktop-native AI companion living on the user's screen.
    You have direct physical control of the mouse and keyboard when authorized.
    Speak naturally, expressively, and vividly in character.
    Always provide commentary on what you observe on screen before taking action.

brain:
  mode: "browser_offload"  # "local_llm", "browser_offload", or "hybrid"
  local_model:
    model_id: "Qwen/Qwen2.5-3B-Instruct-GGUF"
    filename: "qwen2.5-3b-instruct-q4_k_m.gguf"
    context_size: 4096
    gpu_layers: -1
    vram_budget_mb: 5500
    local_endpoint: "http://127.0.0.1:8080/v1"
    download_auto: false
  offload:
    preferred_browser: "chrome"  # "chrome" or "opera_gx"
    browser_paths:
      chrome: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
      opera_gx: "C:\\Users\\Suici\\AppData\\Local\\Programs\\Opera GX\\opera.exe"
    default_web_ai_url: "https://gemini.google.com"
    stream_stability_ms: 1500
    stream_timeout_sec: 45
    sentinel_token_prefix: "__PARASITE_SENTINEL__"

safety:
  interrupt_enabled: true
  interrupt_latency_budget_ms: 2.0
  override_pause_duration_sec: 10.0
  panic_hotkeys:
    - "ctrl+alt+backspace"
    - "ctrl+alt+p"
    - "esc"
  corner_panic_enabled: true
  corner_distance_px: 4
  sensitive_window_titles:
    - "Bitwarden"
    - "1Password"
    - "KeePass"
    - "Task Manager"
    - "Administrator:"
    - "Windows Security"
    - "User Account Control"
    - "Registry Editor"
  sensitive_process_names:
    - "bitwarden.exe"
    - "1password.exe"
    - "keepass.exe"
    - "keepassxc.exe"
    - "taskmgr.exe"
    - "regedit.exe"
    - "credentialui.exe"
    - "consent.exe"
    - "logonui.exe"
  mask_screen_on_sensitive: true

ui:
  dock:
    width: 340
    height: 540
    anchor: "bottom_right"
    margin_x: 24
    margin_y: 24
    opacity: 0.95
    always_on_top: true
    frameless: true
    show_thought_stream: true
    show_perception_preview: true
  hud:
    enabled: true
    fps_target: 60
    reticle_color: "#FF3366"
    reticle_duration_ms: 300
    som_box_color: "#00E5FF"
    som_glow_color: "#00FFCC"
    box_alpha: 0.25
    stroke_width_px: 1.5

vision:
  grounding_mode: "hybrid"  # "hybrid", "uia_only", or "ocr_only"
  max_som_elements: 60
  screen_diff_threshold: 0.02
  ocr_scoped_only: true
  capture_backend: "mss"
  settling_diff_threshold: 0.003
  settling_consecutive_polls: 3

hands:
  mouse:
    speed_factor: 1.0
    trajectory_type: "cubic_bezier"
    overshoot_radius_px: 12
    micro_jitter_amplitude_px: 1.5
    step_delay_ms: 8
    preview_reticle_ms: 300
  keyboard:
    typing_wpm: 85
    cadence_jitter_ms: [25, 75]
    micro_pause_probability: 0.04
    micro_pause_duration_ms: [200, 600]
    punctuation_pause_ms: [80, 150]
    multiline_shift_enter: true
```

---

## 5. Automated Unit Test Architecture: `tests/test_config.py`

To verify the configuration engine under `uv run pytest`, the test suite in `tests/test_config.py` must achieve 100% test coverage across all validation and serialization paths.

```python
"""
Tests for parasite_ai.config module.
Verifies Pydantic V2 schema validation, YAML loading/saving, and host defaults.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError
from parasite_ai.config import (
    AppConfig,
    SystemConfig,
    PersonaConfig,
    BrainConfig,
    SafetyConfig,
    UIConfig,
    VisionConfig,
    HandsConfig,
    load_config,
    save_config,
    get_default_config,
)


def test_default_config_instantiation():
    """Verify default AppConfig creates all valid sub-models with expected defaults."""
    cfg = get_default_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.system.log_level == "INFO"
    assert cfg.system.integrity_mode == "development"
    assert cfg.persona.name == "Parasite"
    assert cfg.brain.mode == "browser_offload"
    assert cfg.brain.local_model.vram_budget_mb == 5500
    assert cfg.safety.interrupt_enabled is True
    assert cfg.safety.interrupt_latency_budget_ms == 2.0
    assert "Bitwarden" in cfg.safety.sensitive_window_titles
    assert "bitwarden.exe" in cfg.safety.sensitive_process_names
    assert cfg.ui.dock.width == 340
    assert cfg.ui.hud.reticle_duration_ms == 300
    assert cfg.vision.grounding_mode == "hybrid"
    assert cfg.hands.mouse.trajectory_type == "cubic_bezier"
    assert cfg.hands.keyboard.multiline_shift_enter is True


def test_yaml_roundtrip(tmp_path: Path):
    """Verify serialize to YAML and deserializing restores exact configuration."""
    cfg_original = get_default_config()
    cfg_original.persona.name = "TestParasite"
    cfg_original.hands.mouse.speed_factor = 2.5
    cfg_original.ui.hud.reticle_color = "#112233"

    cfg_file = tmp_path / "test_config.yaml"
    save_config(cfg_original, cfg_file)
    assert cfg_file.exists()

    cfg_loaded = load_config(cfg_file)
    assert cfg_loaded.persona.name == "TestParasite"
    assert cfg_loaded.hands.mouse.speed_factor == 2.5
    assert cfg_loaded.ui.hud.reticle_color == "#112233"
    assert cfg_loaded.brain.mode == cfg_original.brain.mode


def test_partial_yaml_loading(tmp_path: Path):
    """Verify partial YAML overrides specific values while preserving defaults for rest."""
    partial_yaml = """
    persona:
      name: "CustomBot"
    hands:
      mouse:
        speed_factor: 1.8
    """
    cfg_file = tmp_path / "partial.yaml"
    cfg_file.write_text(partial_yaml, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.persona.name == "CustomBot"
    assert cfg.hands.mouse.speed_factor == 1.8
    # Unspecified fields must hold default values
    assert cfg.system.log_level == "INFO"
    assert cfg.brain.mode == "browser_offload"
    assert cfg.safety.interrupt_enabled is True


def test_mind_alias_compatibility(tmp_path: Path):
    """Verify YAML using legacy 'mind:' key seamlessly populates 'brain' model."""
    mind_yaml = """
    mind:
      mode: "local_llm"
      local_model:
        context_size: 2048
    """
    cfg_file = tmp_path / "mind_alias.yaml"
    cfg_file.write_text(mind_yaml, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.brain.mode == "local_llm"
    assert cfg.brain.local_model.context_size == 2048


def test_environment_variable_overrides(tmp_path: Path, monkeypatch):
    """Verify environment variables take precedence over config file values."""
    monkeypatch.setenv("PARASITE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PARASITE_BRAIN_MODE", "hybrid")
    monkeypatch.setenv("PARASITE_INTEGRITY_MODE", "production")

    cfg_file = tmp_path / "env_override.yaml"
    cfg_file.write_text("system:\n  log_level: 'INFO'\n", encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.system.log_level == "DEBUG"
    assert cfg.brain.mode == "hybrid"
    assert cfg.system.integrity_mode == "production"


def test_missing_config_auto_generates_file(tmp_path: Path):
    """Verify loading a non-existent file automatically generates default config.yaml."""
    target_file = tmp_path / "auto_generated.yaml"
    assert not target_file.exists()

    cfg = load_config(target_file)
    assert isinstance(cfg, AppConfig)
    assert target_file.exists()
    assert "browser_offload" in target_file.read_text(encoding="utf-8")


def test_validation_bounds():
    """Verify out-of-bound numerical and string inputs raise Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        # speed_factor cannot be negative
        HandsConfig(mouse={"speed_factor": -1.0})

    with pytest.raises(ValidationError):
        # Invalid hex color string
        UIConfig(hud={"reticle_color": "not_a_color"})

    with pytest.raises(ValidationError):
        # Invalid log level literal
        SystemConfig(log_level="SUPER_VERBOSE")

    with pytest.raises(ValidationError):
        # VRAM budget below minimum 1024 MB
        BrainConfig(local_model={"vram_budget_mb": 500})
```

---

## 6. Implementation Checklist for Worker Agent

When the builder/worker agent executes Milestone M1:
- [ ] Create `parasite_ai/config.py` using the exact Pydantic V2 code provided in Section 3.
- [ ] Create `config.yaml` at project root (`g:\__Docs\ParasiteAI\config.yaml`) with the documented structure in Section 4.
- [ ] Create `tests/test_config.py` using the test suite in Section 5.
- [ ] Execute `uv run pytest tests/test_config.py` and confirm all 7 test cases pass cleanly.
