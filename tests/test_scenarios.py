"""Tests for the 12 acceptance test scenarios suite."""

import pytest

from bakim_bloklari.scenarios import ScenarioSuite


def test_scenario_suite_runs_all_12_passed() -> None:
    suite = ScenarioSuite()
    results = suite.run_all()
    assert len(results) == 12
    for r in results:
        assert r.passed is True, f"Scenario failed: {r.scenario_id} - {r.name}: {r.error_message}"


def test_scenario_suite_invalid_blueprint() -> None:
    suite = ScenarioSuite()
    with pytest.raises(ValueError, match="Failed to parse blueprint"):
        suite.get_blueprint("nonexistent_blueprint_file.yaml")
