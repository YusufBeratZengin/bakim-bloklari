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
    code = main(["inspect", "morning_inactivity.yaml"])
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
