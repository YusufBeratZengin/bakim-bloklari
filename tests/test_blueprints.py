"""Tests verifying all production blueprint files in the repository."""

from pathlib import Path

from bakim_bloklari.schema import BlueprintValidator


def test_production_blueprints_all_valid() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    blueprints_dir = repo_root / "blueprints" / "automation" / "bakim_bloklari"
    assert blueprints_dir.is_dir(), f"Directory not found: {blueprints_dir}"

    yaml_files = sorted(list(blueprints_dir.glob("*.yaml")) + list(blueprints_dir.glob("*.yml")))
    assert len(yaml_files) >= 3, f"Expected at least 3 v0.1 blueprints, found {len(yaml_files)}"

    expected_blueprints = {
        "morning_inactivity.yaml",
        "prolonged_bathroom.yaml",
        "door_left_open.yaml",
    }
    found_names = {f.name for f in yaml_files}
    for expected in expected_blueprints:
        assert expected in found_names, f"Missing required blueprint: {expected}"

    validator = BlueprintValidator()
    for bp_file in yaml_files:
        res = validator.validate_file(bp_file)
        assert res.valid is True, (
            f"Blueprint {bp_file.name} failed validation: {[e.message for e in res.errors]}"
        )
        assert len(res.errors) == 0, f"Blueprint {bp_file.name} has errors: {res.errors}"
        assert len(res.warnings) == 0, (
            f"Blueprint {bp_file.name} has unexpected warnings: {res.warnings}"
        )

        parsed = validator.parse_blueprint(bp_file)
        assert parsed is not None
        assert parsed.domain == "automation"
        assert len(parsed.inputs) > 0
        assert len(parsed.triggers) > 0
        assert len(parsed.actions) > 0
        # Home Assistant does not localise blueprint UI strings, so every
        # description carries a Turkish summary for Turkish-speaking users.
        assert "TR:" in parsed.description, f"{bp_file.name} lacks a Turkish summary"


def test_packaged_blueprints_match_repository_copies() -> None:
    """The wheel copy under src/ must not drift from the repo blueprints."""
    repo_root = Path(__file__).resolve().parent.parent
    source_dir = repo_root / "blueprints" / "automation" / "bakim_bloklari"
    packaged_dir = repo_root / "src" / "bakim_bloklari" / "blueprints"

    source_files = {p.name: p.read_bytes() for p in source_dir.glob("*.yaml")}
    packaged_files = {p.name: p.read_bytes() for p in packaged_dir.glob("*.yaml")}

    assert source_files, "No repository blueprints found"
    assert source_files == packaged_files, (
        "Packaged blueprints are out of sync; copy "
        "blueprints/automation/bakim_bloklari/*.yaml to src/bakim_bloklari/blueprints/"
    )
