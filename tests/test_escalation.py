"""Behaviour tests for the multi-stage escalation pipeline blueprint.

These exercise real trigger dispatch and ``wait_for_trigger`` polling in the
simulator, not direct action invocation, so the stage order and the
"acknowledgement stops escalation" contract are both verified.
"""

from datetime import datetime
from pathlib import Path

from bakim_bloklari.models import BlueprintDefinition
from bakim_bloklari.schema import BlueprintValidator
from bakim_bloklari.simulator import HomeAssistantSimulator

BLUEPRINT = (
    Path(__file__).resolve().parent.parent
    / "blueprints"
    / "automation"
    / "bakim_bloklari"
    / "escalation_pipeline.yaml"
)


def _pipeline() -> BlueprintDefinition:
    bp = BlueprintValidator().parse_blueprint(BLUEPRINT)
    assert bp is not None
    return bp


def _sim(ack_entity: str) -> HomeAssistantSimulator:
    sim = HomeAssistantSimulator(
        _pipeline(),
        inputs={
            "trigger_boolean": "input_boolean.care_alert",
            "ack_entity": ack_entity,
            "wait_resident_minutes": 5,
            "speaker_action": [{"service": "media_player.play_media", "data": {"media": "chime"}}],
            "resident_notify_action": [{"service": "notify.resident_phone"}],
            "caregiver_notify_action": [{"service": "notify.caregiver_critical"}],
        },
    )
    sim.set_time(datetime(2026, 11, 3, 9, 0, 0))
    sim.set_state("input_boolean.care_alert", "off")
    sim.set_state("input_boolean.resident_ack", "off")
    return sim


def _services(sim: HomeAssistantSimulator) -> list[str]:
    return [call.action_type for call in sim.action_history]


def test_escalation_runs_all_stages_in_documented_order() -> None:
    sim = _sim("input_boolean.resident_ack")
    sim.process_state_change("input_boolean.care_alert", "on")

    assert _services(sim) == [
        "media_player.play_media",
        "notify.resident_phone",
        "notify.caregiver_critical",
    ]
    speaker, resident, caregiver = sim.action_history
    assert speaker.timestamp == datetime(2026, 11, 3, 9, 0, 0)
    assert resident.timestamp == datetime(2026, 11, 3, 9, 5, 0)
    assert caregiver.timestamp == datetime(2026, 11, 3, 9, 10, 0)


def test_acknowledgement_during_first_window_stops_escalation() -> None:
    sim = _sim("input_boolean.resident_ack")
    sim.schedule_state("input_boolean.resident_ack", "on", after_minutes=2)

    sim.process_state_change("input_boolean.care_alert", "on")

    assert _services(sim) == ["media_player.play_media"]
    assert sim.current_time == datetime(2026, 11, 3, 9, 2, 0)


def test_acknowledgement_during_second_window_stops_caregiver_alarm() -> None:
    sim = _sim("input_boolean.resident_ack")
    sim.schedule_state("input_boolean.resident_ack", "on", after_minutes=7)

    sim.process_state_change("input_boolean.care_alert", "on")

    assert _services(sim) == ["media_player.play_media", "notify.resident_phone"]
    assert sim.current_time == datetime(2026, 11, 3, 9, 7, 0)


def test_pipeline_without_ack_entity_uses_two_timed_windows() -> None:
    sim = _sim("")
    sim.process_state_change("input_boolean.care_alert", "on")

    assert _services(sim) == [
        "media_player.play_media",
        "notify.resident_phone",
        "notify.caregiver_critical",
    ]
    assert sim.action_history[-1].timestamp == datetime(2026, 11, 3, 9, 10, 0)
