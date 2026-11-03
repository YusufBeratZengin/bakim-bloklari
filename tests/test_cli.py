"""Tests for bakim-bloklari command line interface."""

from pathlib import Path

import pytest

from bakim_bloklari.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "Home Assistant elderly care blueprint package" in captured.out


def test_cli_validate_success(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Validation SUCCESS" in captured.out


def test_cli_validate_single_file(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "blueprints/automation/bakim_bloklari/morning_inactivity.yaml"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Validation SUCCESS" in captured.out


def test_cli_validate_invalid_path(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "nonexistent/path/xyz"])
    assert code == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_cli_validate_empty_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", str(tmp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "No YAML blueprint files found" in captured.err


def test_cli_validate_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_yaml = tmp_path / "broken.yaml"
    bad_yaml.write_text("blueprint: invalid", encoding="utf-8")
    code = main(["validate", str(bad_yaml)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Validation FAILED" in captured.err


def test_cli_simulate(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["simulate", "-v"])
    assert code == 0
    captured = capsys.readouterr()
    assert "12/12 scenarios passed" in captured.out


def test_cli_simulate_invalid_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["simulate", "--blueprints-dir", str(tmp_path / "missing")])
    assert code == 1
    captured = capsys.readouterr()
    assert "Blueprints directory not found" in captured.err


def test_cli_list(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["list"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Available Blueprints" in captured.out
    assert "morning_inactivity.yaml" in captured.out


def test_cli_list_invalid_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["list", "--blueprints-dir", str(tmp_path / "missing")])
    assert code == 1
    captured = capsys.readouterr()
    assert "Blueprints directory not found" in captured.err


def test_cli_list_with_invalid_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid: [broken", encoding="utf-8")
    code = main(["list", "--blueprints-dir", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "Unparsed/Invalid schema" in captured.out


def test_cli_inspect_success(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["inspect", "morning_inactivity"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Blueprint: morning_inactivity.yaml" in captured.out
    assert "Morning Check Time" in captured.out


def test_cli_inspect_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["inspect", "does_not_exist.yaml"])
    assert code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_cli_inspect_unparseable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_yaml = tmp_path / "unparseable.yaml"
    bad_yaml.write_text("blueprint: broken", encoding="utf-8")
    code = main(["inspect", "unparseable.yaml", "--blueprints-dir", str(tmp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Could not parse blueprint" in captured.err


def test_cli_install(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ha_config = tmp_path / "homeassistant"
    code = main(["install", "--target", str(ha_config)])
    assert code == 0
    captured = capsys.readouterr()
    assert "Successfully installed" in captured.out

    dest = ha_config / "blueprints" / "automation" / "bakim_bloklari"
    assert (dest / "morning_inactivity.yaml").is_file()
    assert (dest / "prolonged_bathroom.yaml").is_file()
    assert (dest / "door_left_open.yaml").is_file()


def test_cli_install_invalid_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["install", "--target", str(tmp_path), "--blueprints-dir", str(tmp_path / "missing")]
    )
    assert code == 1
    captured = capsys.readouterr()
    assert "Source blueprints directory not found" in captured.err


def test_cli_validate_warning_prints_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bp_file = tmp_path / "custom.yaml"
    bp_file.write_text(
        """blueprint:
  name: "Custom Selector Warning Test"
  description: "Testing blueprint validation printing of warnings."
  domain: automation
  input:
    custom_in:
      name: "Custom In"
      selector:
        unknown_selector_kind: {}
trigger:
  - platform: time
    at: "10:00:00"
condition:
  - condition: template
    value_template: "{{ not is_state('s', 'unavailable') and not is_state('s', 'unknown') }}"
action:
  - service: notify.notify
""",
        encoding="utf-8",
    )
    code = main(["validate", str(bp_file)])
    assert code == 0
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "unknown_selector_kind" in captured.out


def test_cli_simulate_failure_reporting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bakim_bloklari.models import ScenarioResult
    from bakim_bloklari.scenarios import ScenarioSuite

    def mock_run_all(self: ScenarioSuite) -> list[ScenarioResult]:
        return [
            ScenarioResult(
                scenario_id="SCENARIO-FAIL",
                name="Failing Scenario",
                passed=False,
                logs=["log line 1"],
                error_message="Simulated error reason",
            )
        ]

    monkeypatch.setattr(ScenarioSuite, "run_all", mock_run_all)
    code = main(["simulate", "-v"])
    assert code == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "ERROR: Simulated error reason" in captured.out
    assert "log line 1" in captured.out
    assert "One or more scenarios failed." in captured.err


def test_cli_inspect_empty_desc_and_no_selector(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from bakim_bloklari.models import BlueprintDefinition
    from bakim_bloklari.schema import BlueprintValidator

    fake_file = tmp_path / "fake.yaml"
    fake_file.write_text("blueprint:\n  name: Fake\n", encoding="utf-8")

    fake_bp = BlueprintDefinition(
        path=fake_file,
        name="Fake Blueprint",
        description="",
        domain="automation",
        inputs={"non_dict_input": "scalar_value"},
        variables={},
        mode="single",
        triggers=[],
        conditions=[],
        actions=[],
        raw={},
    )
    monkeypatch.setattr(BlueprintValidator, "parse_blueprint", lambda self, p: fake_bp)
    code = main(["inspect", "fake.yaml", "--blueprints-dir", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "Blueprint: fake.yaml" in captured.out
    assert "non_dict_input: scalar_value" in captured.out


def test_cli_get_default_blueprints_dir_fallbacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from bakim_bloklari import cli

    # Change cwd to tmp_path where blueprints dir does not exist
    monkeypatch.chdir(tmp_path)
    # Result should resolve to package-relative candidate
    found = cli.get_default_blueprints_dir()
    assert found.is_dir()

    # When both don't exist, returns candidate
    fake_cli_file = tmp_path / "pkg" / "src" / "cli.py"
    monkeypatch.setattr(cli, "__file__", str(fake_cli_file))
    fallback = cli.get_default_blueprints_dir()
    assert fallback == tmp_path / "blueprints" / "automation" / "bakim_bloklari"
