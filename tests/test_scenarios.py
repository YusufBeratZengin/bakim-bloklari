"""Tests for the 12 acceptance test scenarios suite."""

from pathlib import Path

import pytest

from bakim_bloklari import scenarios
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


def test_scenario_suite_dir_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_scenarios_file = tmp_path / "pkg" / "src" / "scenarios.py"
    pkg_bp = tmp_path / "pkg" / "src" / "blueprints"
    pkg_bp.mkdir(parents=True)

    monkeypatch.setattr(scenarios, "__file__", str(fake_scenarios_file))
    suite = ScenarioSuite()
    assert suite.blueprints_dir == pkg_bp

    pkg_bp.rmdir()
    suite_default = ScenarioSuite()
    assert suite_default.blueprints_dir == tmp_path / "blueprints" / "automation" / "bakim_bloklari"
