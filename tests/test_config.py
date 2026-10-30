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
    validate_hex_color,
)


def test_default_config_instantiation():
    """Verify default AppConfig creates all valid sub-models with expected defaults."""
    cfg = get_default_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.system.log_level == "INFO"
    assert cfg.system.integrity_mode == "development"
    assert cfg.persona.name == "Parasite"
    assert cfg.brain.mode == "browser_offload"
    assert cfg.mind.mode == "browser_offload"  # mind alias property
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
    """Verify serializing to YAML and deserializing restores exact configuration."""
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
    assert cfg.mind.mode == "local_llm"
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


def test_hex_color_validation():
    """Verify validate_hex_color handles 3, 6, 8 hex digits and rejects invalid formats."""
    assert validate_hex_color("#FFF") == "#FFF"
    assert validate_hex_color("#00E5FF") == "#00E5FF"
    assert validate_hex_color("#00E5FFAA") == "#00E5FFAA"

    for invalid in ["00E5FF", "#GGG", "#12", "#12345", "blue"]:
        with pytest.raises(ValueError):
            validate_hex_color(invalid)


def test_corrupt_yaml_file_raises_error(tmp_path: Path):
    """Verify malformed YAML raises ValueError with clear diagnosis."""
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("system:\n  log_level: [unclosed", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to read configuration YAML"):
        load_config(bad_file)


def test_load_root_config_yaml():
    """Verify the actual repository config.yaml loads and validates successfully."""
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.persona.name == "Parasite"
    assert cfg.brain.mode in ("browser_offload", "local_llm", "hybrid")
    assert cfg.safety.interrupt_enabled is True
    assert cfg.ui.dock.width > 0
    assert cfg.ui.hud.reticle_duration_ms == 300


def test_empty_yaml_returns_default_config(tmp_path: Path):
    """Verify an empty YAML file gracefully falls back to default AppConfig values."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("# only comments\n", encoding="utf-8")

    cfg = load_config(empty_file)
    assert isinstance(cfg, AppConfig)
    assert cfg.persona.name == "Parasite"
    assert cfg.brain.mode == "browser_offload"

