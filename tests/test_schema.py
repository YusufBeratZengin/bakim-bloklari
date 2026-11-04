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


def test_safety_guard_must_be_in_conditions_not_description(tmp_path: Path) -> None:
    """Regression: mentioning unavailable/unknown in prose must not count as a guard."""
    validator = BlueprintValidator()
    bp_file = tmp_path / "prose_guard.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Prose Guard Only"
  description: "Ignores unavailable and unknown sensor states, allegedly."
  domain: automation
  input:
    sensor:
      name: "Sensor"
      selector:
        entity:
          domain: binary_sensor
trigger:
  - platform: state
    entity_id: !input sensor
condition:
  - condition: state
    entity_id: !input sensor
    state: "off"
action:
  - service: notify.notify
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    assert any("offline-sensor guard" in i.message for i in result.warnings)


def test_undeclared_input_reference_is_an_error(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "undeclared.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Undeclared Input"
  description: "References a missing input declaration."
  domain: automation
  input:
    sensor:
      name: "Sensor"
      selector:
        entity: {}
trigger:
  - platform: state
    entity_id: !input missing_sensor
condition:
  - condition: template
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - service: notify.notify
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    assert not result.valid
    assert any("undeclared input 'missing_sensor'" in i.message for i in result.errors)


def test_unknown_trigger_platform_and_mode_are_errors(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "bad_trigger.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Bad Trigger"
  description: "Uses an unsupported trigger platform and automation mode."
  domain: automation
  input:
    sensor:
      name: "Sensor"
      selector:
        entity: {}
mode: sometimes
trigger:
  - platform: teleport
    entity_id: !input sensor
condition:
  - condition: template
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - service: notify.notify
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    assert not result.valid
    messages = [i.message for i in result.errors]
    assert any("Unknown trigger platform 'teleport'" in m for m in messages)
    assert any("Unknown automation mode 'sometimes'" in m for m in messages)


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


def test_action_sequence_structural_errors(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "bad_actions.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Bad Actions"
  description: "Exercises structural action validation branches."
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
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - choose:
      - conditions: []
        sequence: []
      - conditions:
          - condition: template
            value_template: "{{ true }}"
    default:
      - service: notify.notify
  - delay: [bad, list]
  - totally_unknown_key: true
  - 42
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    messages = [i.message for i in result.errors]
    assert any("non-empty 'conditions'" in m for m in messages)
    assert any("requires a 'sequence'" in m for m in messages)
    assert any("'delay' must be a number" in m for m in messages)
    assert any("no recognized key" in m for m in messages)
    assert any("non-empty mapping" in m for m in messages)


def test_action_sequence_unrecognized_key_is_warning(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "extra_key.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Extra Action Key"
  description: "Known action plus an unknown sibling key."
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
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - service: notify.notify
    mystery_key: 1
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    assert any("Unrecognized action keys" in i.message for i in result.warnings)


def test_non_mapping_trigger_and_choose_shape(tmp_path: Path) -> None:
    validator = BlueprintValidator()
    bp_file = tmp_path / "shape.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Bad Shapes"
  description: "Non-mapping trigger and invalid choose container."
  domain: automation
  input:
    sensor:
      name: "Sensor"
      selector:
        entity: {}
trigger:
  - "just a string"
condition:
  - condition: template
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - choose: not-a-list
""",
        encoding="utf-8",
    )
    result = validator.validate_file(bp_file)
    messages = [i.message for i in result.errors]
    assert any("Trigger must be a mapping" in m for m in messages)
    assert any("'choose' must be a list" in m for m in messages)
