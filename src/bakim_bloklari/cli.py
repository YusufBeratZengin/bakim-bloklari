"""Command line interface for bakim-bloklari."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from bakim_bloklari import __version__
from bakim_bloklari.scenarios import ScenarioSuite
from bakim_bloklari.schema import BlueprintValidator


def get_default_blueprints_dir() -> Path:
    """Find default blueprints directory relative to cwd, repo root, or installed package."""
    cwd = Path.cwd()
    candidate = cwd / "blueprints" / "automation" / "bakim_bloklari"
    if candidate.is_dir():
        return candidate
    # Fallback to repo root if running from repository clone
    repo_candidate = (
        Path(__file__).resolve().parent.parent.parent
        / "blueprints"
        / "automation"
        / "bakim_bloklari"
    )
    if repo_candidate.is_dir():
        return repo_candidate
    # Fallback to bundled blueprints inside installed package
    pkg_candidate = Path(__file__).resolve().parent / "blueprints"
    if pkg_candidate.is_dir():
        return pkg_candidate
    return candidate


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate one or more blueprint files."""
    target_path = Path(args.path) if args.path else get_default_blueprints_dir()
    validator = BlueprintValidator()

    if target_path.is_file():
        files = [target_path]
    elif target_path.is_dir():
        files = sorted(list(target_path.glob("*.yaml")) + list(target_path.glob("*.yml")))
    else:
        print(f"Error: Path '{target_path}' does not exist.", file=sys.stderr)
        return 1

    if not files:
        print(f"No YAML blueprint files found in '{target_path}'.", file=sys.stderr)
        return 1

    print(f"\n[bakim-bloklari v{__version__}] Validating {len(files)} blueprint(s)...\n")
    all_valid = True

    for file in files:
        res = validator.validate_file(file)
        status_tag = "[PASS]" if res.valid else "[FAIL]"
        err_count = len(res.errors)
        warn_count = len(res.warnings)
        print(
            f"{status_tag} {file.name} - {res.blueprint_name} (Errors: {err_count}, Warnings: {warn_count})"
        )

        for err in res.errors:
            loc = f" at [{err.location}]" if err.location else ""
            print(f"       ERROR{loc}: {err.message}")
        for warn in res.warnings:
            loc = f" at [{warn.location}]" if warn.location else ""
            print(f"       WARNING{loc}: {warn.message}")

        if not res.valid:
            all_valid = False

    print("\n" + ("=" * 60))
    if all_valid:
        print(f"Validation SUCCESS: All {len(files)} blueprint(s) passed schema checks.")
        return 0
    else:
        print("Validation FAILED: One or more blueprints have schema errors.", file=sys.stderr)
        return 1


def cmd_simulate(args: argparse.Namespace) -> int:
    """Run all 12 acceptance test scenarios."""
    bp_dir = Path(args.blueprints_dir) if args.blueprints_dir else get_default_blueprints_dir()
    if not bp_dir.is_dir():
        print(f"Error: Blueprints directory not found: '{bp_dir}'", file=sys.stderr)
        return 1

    print(
        f"\n[bakim-bloklari v{__version__}] Running 12 Acceptance Scenarios against: {bp_dir.name}\n"
    )
    suite = ScenarioSuite(blueprints_dir=bp_dir)
    results = suite.run_all()

    all_passed = True
    for res in results:
        status_tag = "[PASS]" if res.passed else "[FAIL]"
        print(f"{status_tag} {res.scenario_id}: {res.name}")
        if not res.passed:
            all_passed = False
            if res.error_message:
                print(f"       ERROR: {res.error_message}")
            if args.verbose:
                print("       LOGS:")
                for log_line in res.logs[-5:]:
                    print(f"         {log_line}")

    print("\n" + ("=" * 60))
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    print(f"Simulation Summary: {passed_count}/{total_count} scenarios passed.")

    if all_passed:
        print("All elderly care scenarios verified successfully.")
        return 0
    else:
        print("One or more scenarios failed.", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List available blueprints and their basic information."""
    bp_dir = Path(args.blueprints_dir) if args.blueprints_dir else get_default_blueprints_dir()
    if not bp_dir.is_dir():
        print(f"Error: Blueprints directory not found: '{bp_dir}'", file=sys.stderr)
        return 1

    validator = BlueprintValidator()
    files = sorted(list(bp_dir.glob("*.yaml")) + list(bp_dir.glob("*.yml")))
    print(f"\n[bakim-bloklari v{__version__}] Available Blueprints ({len(files)}):\n")

    for idx, file in enumerate(files, start=1):
        parsed = validator.parse_blueprint(file)
        if parsed:
            desc = parsed.description.strip().replace("\n", " ")
            desc_short = (desc[:75] + "...") if len(desc) > 75 else desc
            print(f"{idx}. {file.name}")
            print(f"   Name   : {parsed.name}")
            print(f"   Inputs : {len(parsed.inputs)} inputs configured")
            print(f"   Summary: {desc_short}\n")
        else:
            print(f"{idx}. {file.name} (Unparsed/Invalid schema)\n")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect the structure and inputs of a specific blueprint."""
    bp_dir = Path(args.blueprints_dir) if args.blueprints_dir else get_default_blueprints_dir()
    file_or_name = args.blueprint_name
    candidate = bp_dir / file_or_name
    if not candidate.is_file() and not file_or_name.endswith(".yaml"):
        candidate = bp_dir / f"{file_or_name}.yaml"

    if not candidate.is_file():
        print(f"Error: Blueprint file '{candidate}' not found.", file=sys.stderr)
        return 1

    validator = BlueprintValidator()
    parsed = validator.parse_blueprint(candidate)
    if not parsed:
        print(f"Error: Could not parse blueprint '{candidate.name}'.", file=sys.stderr)
        return 1

    print(f"\nBlueprint: {candidate.name}")
    print("=" * len(f"Blueprint: {candidate.name}"))
    print(f"Name       : {parsed.name}")
    print(f"Domain     : {parsed.domain}")
    print(f"Mode       : {parsed.mode}")
    print(f"Description:\n  {parsed.description.strip()}\n")
    print("Inputs:")
    for in_key, in_val in parsed.inputs.items():
        if isinstance(in_val, dict):
            in_name = in_val.get("name", in_key)
            in_def = in_val.get("default", "<None>")
            selector = list(in_val.get("selector", {}).keys())
            sel_str = selector[0] if selector else "general"
            print(f"  - {in_key} ({sel_str}):")
            print(f"      Label  : {in_name}")
            print(f"      Default: {in_def}")
            if "description" in in_val:
                print(f"      Help   : {in_val['description'].strip()}")
        else:
            print(f"  - {in_key}: {in_val}")
    print()
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Copy blueprints into a Home Assistant configuration directory.

    Existing files are never clobbered silently: identical files are reported as
    unchanged, differing files are skipped unless ``--force`` is given, and
    ``--backup`` keeps a timestamped copy before overwriting.
    """
    src_dir = Path(args.blueprints_dir) if args.blueprints_dir else get_default_blueprints_dir()
    if not src_dir.is_dir():
        print(f"Error: Source blueprints directory not found: '{src_dir}'", file=sys.stderr)
        return 1

    target_dir = Path(args.target).expanduser()
    dest_dir = target_dir / "blueprints" / "automation" / "bakim_bloklari"
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    files = sorted(list(src_dir.glob("*.yaml")) + list(src_dir.glob("*.yml")))
    installed = 0
    unchanged = 0
    conflicts = 0

    for f in files:
        dest = dest_dir / f.name
        if dest.is_file():
            if dest.read_bytes() == f.read_bytes():
                print(f"Unchanged: {f.name} (identical file already installed)")
                unchanged += 1
                continue
            if args.backup:
                backup_path = dest.with_name(f"{dest.name}.{stamp}.bak")
                shutil.copy2(dest, backup_path)
                print(f"Backed up: {dest.name} -> {backup_path.name}")
            elif not args.force:
                print(
                    f"Skipped: {dest} already exists and differs "
                    f"(use --force to overwrite or --backup to keep a copy)",
                    file=sys.stderr,
                )
                conflicts += 1
                continue
        shutil.copy2(f, dest)
        print(f"Installed: {f.name} -> {dest}")
        installed += 1

    print(f"\nInstalled {installed}, unchanged {unchanged}, skipped {conflicts} in '{dest_dir}'.")
    if conflicts:
        print(
            "Some blueprints were not installed because local versions differ.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bakim-bloklari",
        description="Home Assistant elderly care blueprint package and simulation tool.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # validate
    p_val = subparsers.add_parser(
        "validate", help="Validate blueprint YAML schema and safety rules"
    )
    p_val.add_argument("path", nargs="?", default=None, help="Path to blueprint file or directory")

    # simulate
    p_sim = subparsers.add_parser("simulate", help="Run deterministic 12-scenario test suite")
    p_sim.add_argument("--blueprints-dir", default=None, help="Directory containing blueprints")
    p_sim.add_argument(
        "-v", "--verbose", action="store_true", help="Print recent scenario logs on failure"
    )

    # list
    p_list = subparsers.add_parser("list", help="List available blueprints")
    p_list.add_argument("--blueprints-dir", default=None, help="Directory containing blueprints")

    # inspect
    p_ins = subparsers.add_parser("inspect", help="Inspect blueprint details and input parameters")
    p_ins.add_argument("blueprint_name", help="Name or filename of the blueprint")
    p_ins.add_argument("--blueprints-dir", default=None, help="Directory containing blueprints")

    # install
    p_inst = subparsers.add_parser(
        "install", help="Copy blueprints to Home Assistant config folder"
    )
    p_inst.add_argument(
        "--target",
        required=True,
        help="Home Assistant configuration directory (e.g. ~/.homeassistant or /config)",
    )
    p_inst.add_argument(
        "--blueprints-dir", default=None, help="Directory containing source blueprints"
    )
    p_inst.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing blueprints that differ from the packaged version",
    )
    p_inst.add_argument(
        "--backup",
        action="store_true",
        help="Keep a timestamped .bak copy before overwriting an existing blueprint",
    )

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "simulate":
        return cmd_simulate(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "inspect":
        return cmd_inspect(args)
    if args.command == "install":
        return cmd_install(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
