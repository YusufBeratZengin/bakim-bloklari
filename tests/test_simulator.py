"""Tests for Home Assistant simulator state machine and event runner."""

from datetime import datetime
from pathlib import Path
from typing import Any

from bakim_bloklari.models import BlueprintDefinition, InputRef
from bakim_bloklari.simulator import HomeAssistantSimulator


def make_dummy_blueprint(
    triggers: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    variables: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
) -> BlueprintDefinition:
    return BlueprintDefinition(
        path=Path("dummy.yaml"),
        name="Dummy Blueprint",
        description="A dummy blueprint for unit testing",
        domain="automation",
        inputs=inputs
        or {
            "input_one": {"name": "Input 1", "default": "default_val"},
            "optional_input": {"name": "Optional"},
        },
        variables=variables or {"my_var": InputRef("input_one")},
        mode="single",
        triggers=triggers or [{"platform": "time", "at": "10:00:00"}],
        conditions=conditions or [],
        actions=actions or [{"service": "notify.test", "data": {"message": "Test"}}],
        raw={},
    )


def test_simulator_time_and_state_management() -> None:
    bp = make_dummy_blueprint()
    sim = HomeAssistantSimulator(bp)
    start_time = datetime(2026, 11, 3, 8, 0, 0)
    sim.set_time(start_time)
    assert sim.current_time == start_time

    sim.advance_time(minutes=15, seconds=30)
    assert sim.current_time == datetime(2026, 11, 3, 8, 15, 30)

    # Add entity
    ent1 = sim.set_state("binary_sensor.test", "off")
    assert ent1.state == "off"
    assert ent1.last_changed == sim.current_time

    # Update entity to same state -> last_changed preserved
    sim.advance_time(minutes=5)
    ent2 = sim.set_state("binary_sensor.test", "off")
    assert ent2.last_changed == ent1.last_changed

    # Update entity to different state -> last_changed updated
    sim.advance_time(minutes=5)
    ent3 = sim.set_state("binary_sensor.test", "on")
    assert ent3.last_changed == sim.current_time


def test_simulator_condition_combinators() -> None:
    bp = make_dummy_blueprint()
    sim = HomeAssistantSimulator(bp)
    sim.set_state("sensor.a", "10")
    sim.set_state("sensor.b", "20")

    ctx = {"id": "test"}

    # State condition
    cond_state = {"condition": "state", "entity_id": "sensor.a", "state": "10"}
    assert sim.evaluate_condition_item(cond_state, ctx) is True
    cond_state_false = {"condition": "state", "entity_id": "sensor.a", "state": "99"}
    assert sim.evaluate_condition_item(cond_state_false, ctx) is False

    # And condition
    cond_and = {
        "condition": "and",
        "conditions": [
            {"condition": "state", "entity_id": "sensor.a", "state": "10"},
            {"condition": "state", "entity_id": "sensor.b", "state": "20"},
        ],
    }
    assert sim.evaluate_condition_item(cond_and, ctx) is True

    # Or condition
    cond_or = {
        "condition": "or",
        "conditions": [
            {"condition": "state", "entity_id": "sensor.a", "state": "wrong"},
            {"condition": "state", "entity_id": "sensor.b", "state": "20"},
        ],
    }
    assert sim.evaluate_condition_item(cond_or, ctx) is True

    # Not condition
    cond_not = {
        "condition": "not",
        "conditions": [{"condition": "state", "entity_id": "sensor.a", "state": "wrong"}],
    }
    assert sim.evaluate_condition_item(cond_not, ctx) is True

    # Unknown / unhandled condition type defaults to True
    assert sim.evaluate_condition_item({"condition": "sun"}, ctx) is True


def test_simulator_template_condition_error_handling() -> None:
    bp = make_dummy_blueprint()
    sim = HomeAssistantSimulator(bp)
    bad_template_cond = {
        "condition": "template",
        "value_template": "{{ non_existent_function_xyz() }}",
    }
    assert sim.evaluate_condition_item(bad_template_cond, {}) is False


def test_simulator_actions_and_choose() -> None:
    actions: list[dict[str, Any]] = [
        {
            "choose": [
                {
                    "conditions": [
                        {"condition": "state", "entity_id": "input_boolean.mode", "state": "vip"}
                    ],
                    "sequence": [{"service": "notify.vip_alert"}],
                }
            ],
            "default": [{"service": "notify.standard_alert"}],
        },
        {"wait_for_trigger": [{"platform": "state"}], "timeout": {"minutes": 10}},
    ]
    bp = make_dummy_blueprint(actions=actions)
    sim = HomeAssistantSimulator(bp)
    sim.set_state("input_boolean.mode", "standard")

    sim.trigger_time_check()
    assert len(sim.action_history) == 1
    assert sim.action_history[0].action_type == "notify.standard_alert"

    # Now change state to vip
    sim.set_state("input_boolean.mode", "vip")
    sim.trigger_time_check()
    assert len(sim.action_history) == 2
    assert sim.action_history[1].action_type == "notify.vip_alert"


def test_simulator_event_trigger() -> None:
    bp = make_dummy_blueprint()
    sim = HomeAssistantSimulator(bp)
    triggered = sim.trigger_event("button_press", {"entity_id": "event.button", "state": "single"})
    assert triggered is True
    assert len(sim.action_history) == 1


def test_simulator_substitute_inputs() -> None:
    bp = make_dummy_blueprint()
    sim = HomeAssistantSimulator(
        bp,
        inputs={
            "input_one": "resolved_string",
            "list_input": ["a", "b"],
            "bool_true": True,
            "bool_false": False,
            "none_input": None,
        },
    )
    tmpl = (
        "{{ input_one }} / {{ list_input }} / {{ bool_true }} / {{ bool_false }} / {{ none_input }}"
    )
    subbed = sim._substitute_inputs(tmpl)
    assert "resolved_string" in subbed
    assert "['a', 'b']" in subbed
    assert "true" in subbed
    assert "false" in subbed
    assert "''" in subbed


def test_simulator_literal_variables_and_empty_template() -> None:
    bp = make_dummy_blueprint(
        variables={"literal_var": "static_value"},
        conditions=[{"condition": "template", "value_template": ""}],
    )
    sim = HomeAssistantSimulator(bp)
    assert sim.resolved_variables["literal_var"] == "static_value"
    # Empty template condition returns True
    assert sim.evaluate_condition_item({"condition": "template", "value_template": ""}, {}) is True


def test_simulator_trigger_event_failing_conditions() -> None:
    bp = make_dummy_blueprint(
        conditions=[{"condition": "state", "entity_id": "input_boolean.gate", "state": "open"}]
    )
    sim = HomeAssistantSimulator(bp)
    sim.set_state("input_boolean.gate", "closed")
    triggered = sim.trigger_event("button_press", {"entity_id": "event.button"})
    assert triggered is False
    assert len(sim.action_history) == 0


def test_simulator_actions_advanced_branches() -> None:
    bp = make_dummy_blueprint(
        inputs={
            "seq_input": {"name": "Seq", "default": [{"service": "notify.via_input_ref"}]},
            "timeout_ref": {"name": "Timeout", "default": 8},
            "ent_ref": {"name": "Ent", "default": "sensor.target"},
        },
        actions=[
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "state",
                                "entity_id": InputRef("ent_ref"),
                                "state": "ready",
                            }
                        ],
                        "sequence": InputRef("seq_input"),
                    }
                ],
                "default": {"service": "notify.single_dict_default"},
            },
            {"wait_for_trigger": [], "timeout": {"minutes": InputRef("timeout_ref")}},
            {"wait_for_trigger": [], "timeout": {"minutes": "invalid_number"}},
            {"delay": {"minutes": InputRef("timeout_ref")}},
            {"delay": {"minutes": "invalid"}},
            {"delay": 3},
        ],
    )
    sim = HomeAssistantSimulator(bp, inputs={"timeout_ref": 8, "ent_ref": "sensor.target"})
    sim.set_state("sensor.target", "ready")
    sim.trigger_time_check()
    assert len(sim.action_history) == 1
    assert sim.action_history[0].action_type == "notify.via_input_ref"

    # Now test single dict default execution
    sim.set_state("sensor.target", "busy")
    sim.trigger_time_check()
    assert len(sim.action_history) == 2
    assert sim.action_history[1].action_type == "notify.single_dict_default"


def test_morning_inactivity_ok_button_suppression() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    bp_path = repo_root / "blueprints" / "automation" / "bakim_bloklari" / "morning_inactivity.yaml"
    from bakim_bloklari.schema import BlueprintValidator

    validator = BlueprintValidator()
    bp = validator.parse_blueprint(bp_path)
    assert bp is not None

    sim = HomeAssistantSimulator(
        bp,
        inputs={
            "motion_sensors": ["binary_sensor.hallway_motion"],
            "check_time": "10:00:00",
            "morning_start_time": "06:30:00",
            "person_entity": "person.elder",
            "ok_button": "input_boolean.morning_ok",
            "notify_action": [{"service": "notify.family"}],
        },
    )
    sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
    sim.set_state("person.elder", "home")
    sim.set_state("binary_sensor.hallway_motion", "off")
    # Resident already pressed check-in button (morning_ok is on)
    sim.set_state("input_boolean.morning_ok", "on")

    triggered = sim.trigger_time_check("10:00:00")
    assert triggered is False
    assert len(sim.action_history) == 0


def test_morning_inactivity_before_start_time() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    bp_path = repo_root / "blueprints" / "automation" / "bakim_bloklari" / "morning_inactivity.yaml"
    from bakim_bloklari.schema import BlueprintValidator

    validator = BlueprintValidator()
    bp = validator.parse_blueprint(bp_path)
    assert bp is not None

    sim = HomeAssistantSimulator(
        bp,
        inputs={
            "motion_sensors": ["binary_sensor.hallway_motion"],
            "check_time": "06:00:00",
            "morning_start_time": "06:30:00",
            "notify_action": [{"service": "notify.family"}],
        },
    )
    # Check triggered at 05:00:00 before morning window starts
    sim.set_time(datetime(2026, 11, 3, 5, 0, 0))
    sim.set_state("binary_sensor.hallway_motion", "off")

    triggered = sim.trigger_time_check("05:00:00")
    assert triggered is False
    assert len(sim.action_history) == 0


def test_prolonged_bathroom_door_unknown_suppressed() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    bp_path = repo_root / "blueprints" / "automation" / "bakim_bloklari" / "prolonged_bathroom.yaml"
    from bakim_bloklari.schema import BlueprintValidator

    validator = BlueprintValidator()
    bp = validator.parse_blueprint(bp_path)
    assert bp is not None

    sim = HomeAssistantSimulator(
        bp,
        inputs={
            "bathroom_sensor": "binary_sensor.bath_presence",
            "door_sensor": "binary_sensor.bath_door",
            "max_duration_minutes": 30,
            "notify_action": [{"service": "notify.alert"}],
        },
    )
    sim.set_state("binary_sensor.bath_presence", "on")
    # Door sensor is in unknown state
    sim.set_state("binary_sensor.bath_door", "unknown")

    triggered = sim.trigger_state_change("binary_sensor.bath_presence", "on")
    assert triggered is False
    assert len(sim.action_history) == 0
