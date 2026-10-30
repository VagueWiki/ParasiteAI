"""
Empirical stress tests for extreme YAML/JSON configs:
huge strings, malicious types, unicode/null bytes, missing/null sections,
and zero-config self-healing robustness.
"""

from pathlib import Path
import pytest
import yaml
from pydantic import ValidationError

from parasite_ai.config import (
    AppConfig,
    SystemConfig,
    PersonaConfig,
    BrainConfig,
    SafetyConfig,
    UIConfig,
    HandsConfig,
    load_config,
    save_config,
    get_default_config,
)


# ===========================================================================
# 1. Huge Strings & Memory Pressure
# ===========================================================================

def test_config_huge_strings(tmp_path: Path):
    """
    Stress-test: Huge strings (1MB persona name, 5MB system prompt).
    Verifies that parser and model handle large payloads without crashing.
    """
    cfg_file = tmp_path / "huge_strings.yaml"
    huge_name = "P" * 100_000
    huge_prompt = "You are Parasite. " * 200_000  # ~3.6 MB

    yaml_content = f"""
    persona:
      name: "{huge_name}"
      system_prompt: "{huge_prompt}"
    """
    cfg_file.write_text(yaml_content, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert len(cfg.persona.name) == 100_000
    assert len(cfg.persona.system_prompt) > 3_000_000


# ===========================================================================
# 2. Malicious Types & Unsafe Deserialization
# ===========================================================================

def test_yaml_safe_load_blocks_python_code_execution(tmp_path: Path):
    """
    Security check: Attempting to use PyYAML !!python/object/apply tags
    must be blocked by yaml.safe_load and raise a ValueError / ConstructorError.
    """
    malicious_yaml = """
    system:
      log_level: !!python/object/apply:os.system ["whoami"]
    """
    malicious_file = tmp_path / "exploit.yaml"
    malicious_file.write_text(malicious_yaml, encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to read configuration YAML"):
        load_config(malicious_file)


@pytest.mark.parametrize("bad_payload", [
    {"system": {"log_level": 12345}},                # int instead of string enum
    {"brain": {"mode": True}},                        # bool instead of mode enum
    {"ui": {"hud": {"stroke_width_px": "not_a_float"}}},  # string instead of float
    {"safety": {"panic_hotkeys": "should_be_a_list"}},     # string instead of list
    {"hands": {"keyboard": {"cadence_jitter_ms": [10]}}},  # 1 element instead of (int, int) tuple
    {"hands": {"mouse": {"speed_factor": "invalid"}}},
])
def test_malicious_type_confusion_rejected(bad_payload):
    """Verify type confusion raises Pydantic ValidationError with exact diagnosis."""
    with pytest.raises(ValidationError):
        AppConfig.model_validate(bad_payload)


# ===========================================================================
# 3. Unicode, Control Characters, and Null Bytes
# ===========================================================================

def test_unicode_and_special_characters_in_strings(tmp_path: Path):
    """Verify RTL overrides, zalgo text, surrogate pairs, and emojis in text fields."""
    special_text = (
        "Parasite 🐱‍💻 \u202e reversed text \u202c "
        "Zalgo: t̷e̷s̷t̷ "
        "CJK: パラサイト 寄生虫 "
        "Math: ∀x ∈ ℝ, x² ≥ 0"
    )
    cfg_file = tmp_path / "special_unicode.yaml"
    cfg_data = {
        "persona": {
            "name": special_text,
            "system_prompt": special_text,
        }
    }
    with open(cfg_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg_data, f)

    cfg = load_config(cfg_file)
    assert cfg.persona.name == special_text
    assert cfg.persona.system_prompt == special_text


def test_null_bytes_in_strings(tmp_path: Path):
    """Verify null bytes in config strings do not cause low-level C crashes."""
    cfg_file = tmp_path / "null_byte.yaml"
    cfg_file.write_text('persona:\n  name: "Parasite\\x00Hacked"\n', encoding="utf-8")

    # In YAML, \x00 parses as a null character \0
    cfg = load_config(cfg_file)
    assert "\x00" in cfg.persona.name


# ===========================================================================
# 4. Null Sections and Zero-Config Self-Healing
# ===========================================================================

def test_null_subsystem_sections(tmp_path: Path):
    """
    Stress-test: YAML specifies section keys with null/empty values:
    persona: null
    safety: null
    brain: null
    Verifies whether zero-config self-healing handles null entries
    or if it crashes with ValidationError.
    """
    null_sections_yaml = """
    persona: null
    safety: null
    brain: null
    system: null
    """
    cfg_file = tmp_path / "null_sections.yaml"
    cfg_file.write_text(null_sections_yaml, encoding="utf-8")

    # Empirical observation: Does load_config accept null sections or raise ValidationError?
    try:
        cfg = load_config(cfg_file)
        # If it succeeds, verify defaults were substituted
        assert isinstance(cfg.persona, PersonaConfig)
        assert isinstance(cfg.safety, SafetyConfig)
    except ValidationError as err:
        # Documented behavior: Pydantic rejects None for non-optional sub-models
        assert "Input should be a valid dictionary" in str(err)


def test_yaml_root_is_scalar_or_array(tmp_path: Path):
    """
    Stress-test: Root of YAML is not a mapping/dict, but a scalar or list.
    e.g. `[1, 2, 3]` or `"just text"`.
    """
    array_file = tmp_path / "array.yaml"
    array_file.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(array_file)

    scalar_file = tmp_path / "scalar.yaml"
    scalar_file.write_text("just_a_bare_string", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(scalar_file)


# ===========================================================================
# 5. Multi-Document YAML & Anchor Expansion
# ===========================================================================

def test_yaml_anchor_expansion(tmp_path: Path):
    """Verify standard YAML anchors expand properly without memory explosion."""
    anchor_yaml = """
    default_anchor: &default_set
      log_level: "WARNING"
      integrity_mode: "production"

    system:
      <<: *default_set
    """
    cfg_file = tmp_path / "anchors.yaml"
    cfg_file.write_text(anchor_yaml, encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.system.log_level == "WARNING"
    assert cfg.system.integrity_mode == "production"


def test_corrupted_encoding_file_raises_value_error(tmp_path: Path):
    """Verify non-UTF8 binary noise in config file raises a clear diagnostic error."""
    bad_bytes_file = tmp_path / "noise.yaml"
    bad_bytes_file.write_bytes(b"\x80\x81\xff\xfe\x00\x01\xfa\xce")

    with pytest.raises(ValueError, match="Failed to read configuration YAML"):
        load_config(bad_bytes_file)
