"""Deterministic 12 acceptance test scenarios with fixed fake data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from bakim_bloklari.models import BlueprintDefinition, ScenarioResult
from bakim_bloklari.schema import BlueprintValidator
from bakim_bloklari.simulator import HomeAssistantSimulator


class ScenarioSuite:
    """Suite of 12 acceptance test scenarios verifying blueprints under all conditions."""

    def __init__(self, blueprints_dir: Path | None = None) -> None:
        self.validator = BlueprintValidator()
        self.blueprints_dir = (
            blueprints_dir
            or Path(__file__).resolve().parent.parent.parent
            / "blueprints"
            / "automation"
            / "bakim_bloklari"
        )
        self._cache: dict[str, BlueprintDefinition] = {}

    def get_blueprint(self, filename: str) -> BlueprintDefinition:
        if filename not in self._cache:
            bp_path = self.blueprints_dir / filename
            parsed = self.validator.parse_blueprint(bp_path)
            if not parsed:
                raise ValueError(f"Failed to parse blueprint at {bp_path}")
            self._cache[filename] = parsed
        return self._cache[filename]

    def run_all(self) -> list[ScenarioResult]:
        """Execute all 12 acceptance scenarios and return results."""
        scenarios: list[Callable[[], ScenarioResult]] = [
            self.scenario_01_morning_motion_detected_no_alert,
            self.scenario_02_morning_inactivity_alert_triggered,
            self.scenario_03_morning_inactivity_away_suppression,
            self.scenario_04_morning_inactivity_vacation_mode_suppressed,
            self.scenario_05_morning_sensor_unavailable_safe,
            self.scenario_06_morning_sensor_unknown_safe,
            self.scenario_07_bathroom_normal_shower_cleared,
            self.scenario_08_bathroom_prolonged_occupancy_alert,
            self.scenario_09_bathroom_sensor_unavailable_safe,
            self.scenario_10_door_left_open_daytime_alert,
            self.scenario_11_door_opened_night_wandering_alert,
            self.scenario_12_ok_button_press_cancels_alert,
        ]
        return [fn() for fn in scenarios]

    def scenario_01_morning_motion_detected_no_alert(self) -> ScenarioResult:
        """Scenario 1: Normal morning motion detected -> No alarm triggered."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Inactivity"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("input_boolean.vacation_mode", "off")
        sim.set_state("binary_sensor.living_room_motion", "on")  # active motion

        triggered = sim.trigger_time_check("10:00:00")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-01",
            name="Normal Morning Motion Detected -> No Alarm",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected no alert when motion is detected",
        )

    def scenario_02_morning_inactivity_alert_triggered(self) -> ScenarioResult:
        """Scenario 2: Zero morning motion detected -> Staged escalation alarm fired."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {
                        "service": "notify.notify_family",
                        "data": {"message": "Morning inactivity detected"},
                    }
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("input_boolean.vacation_mode", "off")
        sim.set_state("binary_sensor.living_room_motion", "off")  # zero motion

        triggered = sim.trigger_time_check("10:00:00")
        passed = triggered and (len(sim.action_history) == 1)
        return ScenarioResult(
            scenario_id="SCENARIO-02",
            name="Zero Morning Motion -> Escalation Alarm Fired",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected alert when no motion is detected",
        )

    def scenario_03_morning_inactivity_away_suppression(self) -> ScenarioResult:
        """Scenario 3: Resident is away (not_home) -> Morning alarm suppressed."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Inactivity"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "not_home")  # away
        sim.set_state("input_boolean.vacation_mode", "off")
        sim.set_state("binary_sensor.living_room_motion", "off")

        triggered = sim.trigger_time_check("10:00:00")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-03",
            name="Resident Away (not_home) -> Alarm Suppressed",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None
            if passed
            else "Expected alarm suppression when resident is not_home",
        )

    def scenario_04_morning_inactivity_vacation_mode_suppressed(self) -> ScenarioResult:
        """Scenario 4: Vacation mode is active -> Morning alarm suppressed."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Inactivity"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("input_boolean.vacation_mode", "on")  # vacation mode ON
        sim.set_state("binary_sensor.living_room_motion", "off")

        triggered = sim.trigger_time_check("10:00:00")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-04",
            name="Vacation Mode Active -> Alarm Suppressed",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected alarm suppression when vacation mode is on",
        )

    def scenario_05_morning_sensor_unavailable_safe(self) -> ScenarioResult:
        """Scenario 5: Motion sensor is 'unavailable' -> Safe fallback, zero false emergency alarms."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Inactivity"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("input_boolean.vacation_mode", "off")
        sim.set_state("binary_sensor.living_room_motion", "unavailable")  # sensor offline

        triggered = sim.trigger_time_check("10:00:00")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-05",
            name="Motion Sensor Unavailable -> Safe Fallback (No False Alarm)",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected no false alarm when sensor is unavailable",
        )

    def scenario_06_morning_sensor_unknown_safe(self) -> ScenarioResult:
        """Scenario 6: Motion sensor is 'unknown' -> Safe fallback, zero false alarms."""
        bp = self.get_blueprint("morning_inactivity.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "motion_sensors": ["binary_sensor.living_room_motion"],
                "check_time": "10:00:00",
                "person_entity": "person.elder_person",
                "vacation_mode": "input_boolean.vacation_mode",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Inactivity"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 10, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("input_boolean.vacation_mode", "off")
        sim.set_state("binary_sensor.living_room_motion", "unknown")  # sensor state unknown

        triggered = sim.trigger_time_check("10:00:00")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-06",
            name="Motion Sensor Unknown -> Safe Fallback (No False Alarm)",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected no false alarm when sensor is unknown",
        )

    def scenario_07_bathroom_normal_shower_cleared(self) -> ScenarioResult:
        """Scenario 7: Bathroom normal shower (15 mins) clears without triggering alarm."""
        bp = self.get_blueprint("prolonged_bathroom.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "bathroom_sensor": "binary_sensor.bathroom_radar",
                "max_duration_minutes": 30,
                "person_entity": "person.elder_person",
                "notify_action": [
                    {"service": "notify.notify_family", "data": {"message": "Prolonged bathroom"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 8, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("binary_sensor.bathroom_radar", "on")
        # normal shower: person leaves after 15 minutes
        sim.advance_time(minutes=15)
        sim.set_state("binary_sensor.bathroom_radar", "off")

        passed = len(sim.action_history) == 0
        return ScenarioResult(
            scenario_id="SCENARIO-07",
            name="Bathroom Normal 15-Min Shower -> Cleared Normally",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected no alarm for normal duration shower",
        )

    def scenario_08_bathroom_prolonged_occupancy_alert(self) -> ScenarioResult:
        """Scenario 8: Bathroom occupancy exceeds safe duration (30 mins) -> Prolonged alert fires."""
        bp = self.get_blueprint("prolonged_bathroom.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "bathroom_sensor": "binary_sensor.bathroom_radar",
                "max_duration_minutes": 30,
                "person_entity": "person.elder_person",
                "notify_action": [
                    {
                        "service": "notify.notify_caregiver",
                        "data": {"message": "Prolonged bathroom occupancy detected"},
                    }
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 8, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("binary_sensor.bathroom_radar", "on")
        sim.advance_time(minutes=31)

        # Trigger timer expiration
        triggered = sim.trigger_state_change(
            "binary_sensor.bathroom_radar", "on", trigger_id="prolonged"
        )
        passed = triggered and (len(sim.action_history) == 1)
        return ScenarioResult(
            scenario_id="SCENARIO-08",
            name="Bathroom Prolonged Occupancy (>30m) -> Emergency Alert Fired",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected prolonged bathroom alarm to fire",
        )

    def scenario_09_bathroom_sensor_unavailable_safe(self) -> ScenarioResult:
        """Scenario 9: Bathroom sensor goes 'unavailable' -> No false prolonged alarm."""
        bp = self.get_blueprint("prolonged_bathroom.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "bathroom_sensor": "binary_sensor.bathroom_radar",
                "max_duration_minutes": 30,
                "person_entity": "person.elder_person",
                "notify_action": [
                    {
                        "service": "notify.notify_caregiver",
                        "data": {"message": "Prolonged bathroom"},
                    }
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 8, 0, 0))
        sim.set_state("person.elder_person", "home")
        sim.set_state("binary_sensor.bathroom_radar", "unavailable")

        triggered = sim.trigger_state_change("binary_sensor.bathroom_radar", "unavailable")
        passed = (not triggered) and (len(sim.action_history) == 0)
        return ScenarioResult(
            scenario_id="SCENARIO-09",
            name="Bathroom Sensor Unavailable -> Safe Fallback (No False Alarm)",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None
            if passed
            else "Expected no false alarm when bathroom sensor is unavailable",
        )

    def scenario_10_door_left_open_daytime_alert(self) -> ScenarioResult:
        """Scenario 10: Entrance door left open for 5+ minutes in daytime -> Door open alarm fires."""
        bp = self.get_blueprint("door_left_open.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "door_sensor": "binary_sensor.front_door",
                "day_open_timeout_minutes": 5,
                "night_wandering_alert": True,
                "night_start_time": "23:00:00",
                "night_end_time": "06:00:00",
                "notify_action": [
                    {"service": "notify.door_open", "data": {"message": "Front door left open"}}
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 14, 0, 0))  # 14:00 daytime
        sim.set_state("binary_sensor.front_door", "on")
        sim.advance_time(minutes=5)

        triggered = sim.trigger_state_change(
            "binary_sensor.front_door", "on", trigger_id="daytime_open"
        )
        passed = triggered and (len(sim.action_history) == 1)
        return ScenarioResult(
            scenario_id="SCENARIO-10",
            name="Front Door Left Open Daytime (>5m) -> Alert Fired",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected daytime door alert to fire",
        )

    def scenario_11_door_opened_night_wandering_alert(self) -> ScenarioResult:
        """Scenario 11: Door opened at 02:30 AM -> Night wandering alarm triggers immediately."""
        bp = self.get_blueprint("door_left_open.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "door_sensor": "binary_sensor.front_door",
                "day_open_timeout_minutes": 5,
                "night_wandering_alert": True,
                "night_start_time": "23:00:00",
                "night_end_time": "06:00:00",
                "notify_action": [
                    {
                        "service": "notify.night_wandering",
                        "data": {"message": "Night exit detected"},
                    }
                ],
            },
        )
        sim.set_time(datetime(2026, 11, 3, 2, 30, 0))  # 02:30 AM night hours
        sim.set_state("binary_sensor.front_door", "off")

        # Door opens at 02:30 AM
        triggered = sim.trigger_state_change(
            "binary_sensor.front_door", "on", trigger_id="night_open"
        )
        passed = triggered and (len(sim.action_history) == 1)
        return ScenarioResult(
            scenario_id="SCENARIO-11",
            name="Night Wandering Door Open (02:30 AM) -> Urgent Alert Fired",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected night wandering alert at 02:30 AM",
        )

    def scenario_12_ok_button_press_cancels_alert(self) -> ScenarioResult:
        """Scenario 12: Elder presses 'I Am OK' smart button -> Alert acknowledged and reset."""
        bp = self.get_blueprint("ok_button.yaml")
        sim = HomeAssistantSimulator(
            blueprint=bp,
            inputs={
                "button_entity": "event.bedside_button",
                "single_press_action": [
                    {"service": "input_boolean.turn_off", "target": "input_boolean.elder_alert"}
                ],
                "emergency_press_action": [
                    {"service": "notify.emergency", "data": {"message": "SOS Button Pressed"}}
                ],
                "emergency_event_types": "double_press, long_press, hold, emergency",
            },
        )
        sim.set_time(datetime(2026, 11, 3, 9, 30, 0))
        sim.set_state("input_boolean.elder_alert", "on")
        sim.set_state("event.bedside_button", "single_press")

        # Single press event triggered
        sim.trigger_state_change("event.bedside_button", "single_press")
        passed = (len(sim.action_history) == 1) and (
            sim.action_history[0].action_type == "input_boolean.turn_off"
        )
        return ScenarioResult(
            scenario_id="SCENARIO-12",
            name="'I Am OK' Button Single Press -> Alert Acknowledged & Cleared",
            passed=passed,
            logs=sim.logs,
            action_calls=sim.action_history,
            error_message=None if passed else "Expected single press to clear alert",
        )
