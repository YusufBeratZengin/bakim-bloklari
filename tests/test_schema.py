"""Tests for Home Assistant blueprint schema validator."""

from pathlib import Path

from bakim_bloklari.models import InputRef
from bakim_bloklari.schema import BlueprintValidator


def test_input_ref_repr_and_eq() -> None:
    ref1 = InputRef("test_sensor")
    ref2 = InputRef("test_sensor")
    ref3 = InputRef("other_sensor")
    assert repr(ref1) == "!input test_sensor"
    assert str(ref1) == "!input test_sensor"
    assert ref1 == ref2
    assert ref1 != ref3
    assert ref1 != "not an InputRef"


def test_validator_nonexistent_file(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    result = validator.validate_file(tmp_path / "does_not_exist.yaml")
    assert not result.valid
    assert any("Failed to read file" in i.message for i in result.errors)


def test_validator_invalid_yaml(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("blueprint: [unclosed list", encoding="utf-8")
    result = validator.validate_file(bad_yaml)
    assert not result.valid
    assert any("YAML parsing error" in i.message for i in result.errors)


def test_validator_non_mapping_yaml(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "scalar.yaml"
    bad_yaml.write_text("just a string", encoding="utf-8")
    result = validator.validate_file(bad_yaml)
    assert not result.valid
    assert any("must be a YAML mapping" in i.message for i in result.errors)


def test_validator_missing_blueprint_block(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "no_bp.yaml"
    bad_yaml.write_text("trigger:\n  - platform: time\n    at: '10:00:00'\n", encoding="utf-8")
    result = validator.validate_file(bad_yaml)
    assert not result.valid
    assert any("Missing 'blueprint:'" in i.message for i in result.errors)


def test_validator_invalid_metadata(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "bad_meta.yaml"
    bad_yaml.write_text(
        """blueprint:
  name: "a"
  description: "short"
  domain: "script"
  input: "not a dict"
trigger: []
action: []
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bad_yaml)
    assert not result.valid
    error_messages = [i.message for i in result.errors]
    assert any("Blueprint name must be a non-empty string" in msg for msg in error_messages)
    assert any("Blueprint description must be informative" in msg for msg in error_messages)
    assert any("domain must be 'automation'" in msg for msg in error_messages)
    assert any("Blueprint inputs must be a mapping" in msg for msg in error_messages)
    assert any("must define at least one valid 'trigger'" in msg for msg in error_messages)
    assert any("must define at least one valid 'action'" in msg for msg in error_messages)


def test_validator_input_selector_validation(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "bad_inputs.yaml"
    bad_yaml.write_text(
        """blueprint:
  name: "Valid Blueprint Name"
  description: "Detailed description of the automation for testing."
  domain: automation
  input:
    invalid_input_structure: "not a dict"
    bad_selector_type:
      name: "Bad"
      selector: "should be dict"
    unknown_selector:
      name: "Custom"
      selector:
        exotic_selector: {}
trigger:
  - platform: time
    at: "10:00:00"
action:
  - service: notify.notify
condition:
  - condition: template
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bad_yaml)
    assert any("must be a dictionary" in i.message for i in result.errors)
    assert any("selector must be a dictionary" in i.message for i in result.errors)
    assert any(
        "Selector type 'exotic_selector' in 'unknown_selector' is not standard" in i.message
        for i in result.warnings
    )


def test_validator_template_syntax_error(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bad_yaml = tmp_path / "bad_template.yaml"
    bad_yaml.write_text(
        """blueprint:
  name: "Syntax Error Test"
  description: "Valid blueprint with broken template expression."
  domain: automation
  input:
    sensor:
      name: "Sensor"
      selector:
        entity: {}
trigger:
  - platform: state
    entity_id: !input sensor
condition:
  - condition: template
    value_template: "{{ is_state('a', 'b' }}"
action:
  - service: notify.notify
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bad_yaml)
    assert not result.valid
    assert any("Jinja template syntax error" in i.message for i in result.errors)
    assert any(
        "Safety Notice: Blueprint does not explicitly check for 'unavailable'" in i.message
        for i in result.warnings
    )


def test_parse_blueprint_returns_none_on_invalid(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("invalid: yaml: content", encoding="utf-8")
    parsed = validator.parse_blueprint(invalid_file)
    assert parsed is None


def test_parse_blueprint_single_dict_blocks(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "single_blocks.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Single Blocks Blueprint"
  description: "Testing single dict triggers conditions and actions."
  domain: automation
  input:
    test_sensor:
      name: "Test"
      selector:
        entity: {}
variables: "not-a-dict"
trigger:
  platform: time
  at: "08:00:00"
condition:
  condition: template
  value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  service: notify.notify
""",
        encoding="utf-8",
    )
    parsed = validator.parse_blueprint(bp_file)
    assert parsed is not None
    assert isinstance(parsed.triggers, list)
    assert len(parsed.triggers) == 1
    assert isinstance(parsed.conditions, list)
    assert len(parsed.conditions) == 1
    assert isinstance(parsed.actions, list)
    assert len(parsed.actions) == 1
    assert parsed.variables == {}


def test_input_constructor_non_scalar(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    yaml_file = tmp_path / "non_scalar.yaml"
    yaml_file.write_text("item: !input [a, b]", encoding="utf-8")
    data, issues = validator.load_yaml(yaml_file)
    assert data is not None
    assert data["item"] == InputRef("")
