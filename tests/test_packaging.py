"""Consistency checks between packaging metadata and CI configuration."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _classifier_versions() -> set[str]:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return set(re.findall(r'"Programming Language :: Python :: (\d+\.\d+)"', pyproject))


def _ci_matrix_versions() -> set[str]:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    match = re.search(r"python-version:\s*\[([^\]]+)\]", workflow)
    assert match is not None, "python-version matrix not found in ci.yml"
    return {item.strip().strip("\"'") for item in match.group(1).split(",")}


def test_ci_matrix_matches_declared_python_versions() -> None:
    """Every Python version advertised in pyproject must actually run in CI."""
    declared = _classifier_versions()
    tested = _ci_matrix_versions()
    assert declared == tested, (
        f"pyproject classifiers {sorted(declared)} differ from CI matrix {sorted(tested)}"
    )


def test_requires_python_matches_lowest_ci_version() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', pyproject)
    assert match is not None
    assert match.group(1) == min(_ci_matrix_versions())
