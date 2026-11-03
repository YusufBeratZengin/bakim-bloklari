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
) -> BlueprintDefinition:
    return BlueprintDefinition(
        path=Path("dummy.yaml"),
        name="Dummy Blueprint",
        description="A dummy blueprint for unit testing",
        domain="automation",
        inputs={
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
