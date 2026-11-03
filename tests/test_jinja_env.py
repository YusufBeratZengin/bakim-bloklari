"""Tests for Home Assistant Jinja2 execution environment."""

from datetime import datetime

from bakim_bloklari.jinja_env import HomeAssistantJinjaEnvironment
from bakim_bloklari.models import EntityState


def test_jinja_env_state_access() -> None:
    now_dt = datetime(2026, 11, 3, 10, 0, 0)
    states = {
        "binary_sensor.front_door": EntityState(
            entity_id="binary_sensor.front_door",
            state="on",
            attributes={"device_class": "door", "battery": 95},
            last_changed=now_dt,
            last_updated=now_dt,
        ),
        "person.elder": EntityState(
            entity_id="person.elder",
            state="home",
            attributes={"latitude": 41.0, "longitude": 29.0},
        ),
    }
    env = HomeAssistantJinjaEnvironment(states)
    env.set_time(now_dt)

    # Basic states function
    assert env.get_state_val("binary_sensor.front_door") == "on"
    assert env.get_state_val("nonexistent.entity") == "unknown"
    assert env.get_state_val("") == "unknown"
    assert env.get_state_val(None) == "unknown"  # type: ignore[arg-type]

    # is_state function
    assert env.is_state("binary_sensor.front_door", "on") is True
    assert env.is_state("binary_sensor.front_door", "off") is False
    assert env.is_state("nonexistent.entity", "on") is False
    assert env.is_state("", "on") is False
    assert env.is_state(None, "on") is False  # type: ignore[arg-type]

    # Attributes
    assert env.get_attr_val("binary_sensor.front_door", "device_class") == "door"
    assert env.get_attr_val("binary_sensor.front_door", "missing") is None
    assert env.get_attr_val("nonexistent", "device_class") is None
    assert env.is_state_attr("binary_sensor.front_door", "battery", 95) is True
    assert env.is_state_attr("binary_sensor.front_door", "battery", 50) is False

    # has_value
    assert env.has_value("binary_sensor.front_door") is True
    assert env.has_value("nonexistent.entity") is False

    # Rendering templates
    res = env.render_template("State: {{ states('person.elder') }}")
    assert res == "State: home"

    res_cond = env.evaluate_condition_template("{{ is_state('person.elder', 'home') }}")
    assert res_cond is True

    res_cond_false = env.evaluate_condition_template("{{ is_state('person.elder', 'away') }}")
    assert res_cond_false is False


def test_jinja_env_time_and_filters() -> None:
    now_dt = datetime(2026, 11, 3, 10, 30, 0)
    env = HomeAssistantJinjaEnvironment()
    env.set_time(now_dt)

    # now and utcnow
    res_now = env.render_template("{{ now().strftime('%H:%M') }}")
    assert res_now == "10:30"

    res_utc = env.render_template("{{ utcnow().tzinfo is not none }}")
    assert res_utc.lower() == "true"

    # as_datetime and as_timestamp
    iso_str = "2026-11-03T10:30:00"
    dt = env._as_datetime(iso_str)
    assert dt == now_dt
    assert env._as_datetime(now_dt) == now_dt
    assert env._as_datetime("invalid-date") is None
    assert env._as_datetime(12345) is None

    ts = env._as_timestamp(iso_str)
    assert ts == now_dt.timestamp()
    assert env._as_timestamp("invalid-date") is None

    # iif filter
    res_iif = env.render_template("{{ true | iif('yes', 'no') }}")
    assert res_iif == "yes"
    res_iif_false = env.render_template("{{ false | iif('yes', 'no') }}")
    assert res_iif_false == "no"


def test_jinja_env_update_states() -> None:
    env = HomeAssistantJinjaEnvironment()
    assert env.is_state("sensor.temp", "21") is False

    env.update_states({"sensor.temp": EntityState("sensor.temp", "21")})
    assert env.is_state("sensor.temp", "21") is True
