"""Schema validator for Home Assistant automation blueprints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2
import yaml

from bakim_bloklari.models import (
    BlueprintDefinition,
    InputRef,
    ValidationIssue,
    ValidationResult,
)


def get_yaml_loader() -> type[yaml.SafeLoader]:
    """Return a SafeLoader subclass configured to parse !input tags."""

    class BlueprintYamlLoader(yaml.SafeLoader):
        pass

    def input_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> InputRef:
        if isinstance(node, yaml.ScalarNode):
            val = loader.construct_scalar(node)
            return InputRef(str(val))
        return InputRef("")

    BlueprintYamlLoader.add_constructor("!input", input_constructor)
    return BlueprintYamlLoader


class BlueprintValidator:
    """Validates Home Assistant blueprint YAML files against specifications and safety criteria."""

    VALID_SELECTORS = {
        "entity",
        "target",
        "time",
        "duration",
        "number",
        "boolean",
        "text",
        "action",
        "device",
        "object",
        "select",
        "addon",
    }

    VALID_TRIGGER_PLATFORMS = {
        "state",
        "time",
        "template",
        "event",
        "numeric_state",
        "sun",
        "zone",
        "device",
        "webhook",
        "mqtt",
        "calendar",
        "homeassistant",
        "tag",
        "geo_location",
        "persistent_notification",
        "conversation",
        "sentence",
    }

    VALID_MODES = {"single", "restart", "queued", "parallel"}

    #: Keys that may legally appear in an automation action step.
    ACTION_KEYS = {
        "action",
        "service",
        "target",
        "data",
        "data_template",
        "choose",
        "default",
        "if",
        "then",
        "else",
        "sequence",
        "delay",
        "wait_template",
        "wait_for_trigger",
        "timeout",
        "continue_on_timeout",
        "repeat",
        "parallel",
        "variables",
        "condition",
        "event",
        "stop",
        "enabled",
        "alias",
    }

    def __init__(self) -> None:
        self._jinja_env = jinja2.Environment()

    def load_yaml(self, path: Path) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
        """Load and parse a YAML file handling !input tags."""
        issues: list[ValidationIssue] = []
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            issues.append(ValidationIssue(severity="error", message=f"Failed to read file: {exc}"))
            return None, issues

        try:
            loader = get_yaml_loader()
            data = yaml.load(content, Loader=loader)
            if not isinstance(data, dict):
                issues.append(
                    ValidationIssue(severity="error", message="Blueprint must be a YAML mapping")
                )
                return None, issues
            return data, issues
        except yaml.YAMLError as exc:
            issues.append(ValidationIssue(severity="error", message=f"YAML parsing error: {exc}"))
            return None, issues

    def validate_file(self, path: Path) -> ValidationResult:
        """Validate a single blueprint file."""
        data, issues = self.load_yaml(path)
        blueprint_name = path.stem

        if data is None:
            return ValidationResult(
                file_path=str(path),
                blueprint_name=blueprint_name,
                valid=False,
                issues=issues,
            )

        # Validate blueprint section
        bp_meta = data.get("blueprint")
        if not isinstance(bp_meta, dict):
            issues.append(
                ValidationIssue(
                    severity="error", message="Missing 'blueprint:' configuration block"
                )
            )
            return ValidationResult(
                file_path=str(path),
                blueprint_name=blueprint_name,
                valid=False,
                issues=issues,
            )

        name = bp_meta.get("name")
        if not name or not isinstance(name, str) or len(name.strip()) < 3:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Blueprint name must be a non-empty string (>= 3 chars)",
                    location="blueprint.name",
                )
            )
        else:
            blueprint_name = name

        desc = bp_meta.get("description")
        if not desc or not isinstance(desc, str) or len(desc.strip()) < 10:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Blueprint description must be informative (>= 10 chars)",
                    location="blueprint.description",
                )
            )

        domain = bp_meta.get("domain")
        if domain != "automation":
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Blueprint domain must be 'automation', found: '{domain}'",
                    location="blueprint.domain",
                )
            )

        # Validate inputs
        inputs = bp_meta.get("input", {})
        if not isinstance(inputs, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Blueprint inputs must be a mapping",
                    location="blueprint.input",
                )
            )
        else:
            for input_key, input_def in inputs.items():
                self._validate_input_definition(input_key, input_def, issues)

        # Validate trigger
        trigger = data.get("trigger")
        if not trigger or not isinstance(trigger, (list, dict)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Blueprint must define at least one valid 'trigger'",
                    location="trigger",
                )
            )
        else:
            self._validate_trigger_list(trigger, issues)

        # Validate action
        action = data.get("action")
        if not action or not isinstance(action, (list, dict)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Blueprint must define at least one valid 'action'",
                    location="action",
                )
            )
        else:
            self._validate_action_sequence(action, "action", issues)

        # Validate execution mode
        mode = data.get("mode", "single")
        if mode not in self.VALID_MODES:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Unknown automation mode '{mode}' (expected one of {sorted(self.VALID_MODES)})",
                    location="mode",
                )
            )

        # Every !input reference must be declared in blueprint.input
        declared_inputs = set(inputs) if isinstance(inputs, dict) else set()
        for ref_path, ref_key in self._collect_input_refs(data):
            if ref_key not in declared_inputs:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"References undeclared input '{ref_key}' (add it under blueprint.input)",
                        location=ref_path,
                    )
                )

        # Validate Jinja syntax and safety rules across the document
        self._validate_templates_and_safety(data, issues)

        is_valid = not any(i.severity == "error" for i in issues)
        return ValidationResult(
            file_path=str(path),
            blueprint_name=blueprint_name,
            valid=is_valid,
            issues=issues,
        )

    def _validate_input_definition(
        self, key: str, defn: Any, issues: list[ValidationIssue]
    ) -> None:
        loc = f"blueprint.input.{key}"
        if not isinstance(defn, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Input definition for '{key}' must be a dictionary",
                    location=loc,
                )
            )
            return

        selector = defn.get("selector")
        if selector is not None and not isinstance(selector, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Input '{key}' selector must be a dictionary",
                    location=f"{loc}.selector",
                )
            )
        elif isinstance(selector, dict):
            for sel_type in selector:
                if sel_type not in self.VALID_SELECTORS:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            message=f"Selector type '{sel_type}' in '{key}' is not standard",
                            location=f"{loc}.selector.{sel_type}",
                        )
                    )

    def _validate_trigger_list(
        self, trigger: Any, issues: list[ValidationIssue], location: str = "trigger"
    ) -> None:
        items = [trigger] if isinstance(trigger, dict) else trigger
        if not isinstance(items, list):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Triggers must be a list or a single mapping",
                    location=location,
                )
            )
            return

        for idx, item in enumerate(items):
            loc = f"{location}[{idx}]"
            if isinstance(item, InputRef):
                continue
            if not isinstance(item, dict):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Trigger must be a mapping",
                        location=loc,
                    )
                )
                continue
            platform = item.get("platform")
            if not platform:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Trigger is missing the required 'platform' key",
                        location=loc,
                    )
                )
            elif platform not in self.VALID_TRIGGER_PLATFORMS:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Unknown trigger platform '{platform}'",
                        location=f"{loc}.platform",
                    )
                )

    def _collect_input_refs(self, node: Any, path: str = "") -> list[tuple[str, str]]:
        """Collect every ``!input`` reference with its YAML path."""
        refs: list[tuple[str, str]] = []
        if isinstance(node, InputRef):
            refs.append((path or "blueprint", node.key))
        elif isinstance(node, dict):
            for key, value in node.items():
                if not path and key == "input":
                    continue  # input declarations are not references
                child = f"{path}.{key}" if path else str(key)
                refs.extend(self._collect_input_refs(value, child))
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                refs.extend(self._collect_input_refs(item, f"{path}[{idx}]"))
        return refs

    def _validate_action_sequence(
        self, sequence: Any, location: str, issues: list[ValidationIssue]
    ) -> None:
        """Validate action steps, ``choose`` options and nested sequences."""
        if isinstance(sequence, InputRef):
            return
        items = [sequence] if isinstance(sequence, dict) else sequence
        if not isinstance(items, list):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Action sequence must be a list of action mappings",
                    location=location,
                )
            )
            return

        for idx, item in enumerate(items):
            loc = f"{location}[{idx}]"
            if isinstance(item, InputRef):
                continue
            if not isinstance(item, dict) or not item:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Action step must be a non-empty mapping",
                        location=loc,
                    )
                )
                continue

            keys = set(item)
            if not keys & self.ACTION_KEYS:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Action step has no recognized key (found: {sorted(keys)})",
                        location=loc,
                    )
                )
                continue
            unknown = keys - self.ACTION_KEYS
            if unknown:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Unrecognized action keys {sorted(unknown)}",
                        location=loc,
                    )
                )

            if "choose" in item:
                choices = item.get("choose")
                if not isinstance(choices, list):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            message="'choose' must be a list of options",
                            location=f"{loc}.choose",
                        )
                    )
                else:
                    for c_idx, choice in enumerate(choices):
                        c_loc = f"{loc}.choose[{c_idx}]"
                        if not isinstance(choice, dict):
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    message="Each choose option must be a mapping",
                                    location=c_loc,
                                )
                            )
                            continue
                        conds = choice.get("conditions")
                        if not isinstance(conds, list) or not conds:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    message="Choose option requires a non-empty 'conditions' list",
                                    location=c_loc,
                                )
                            )
                        if "sequence" not in choice:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    message="Choose option requires a 'sequence'",
                                    location=c_loc,
                                )
                            )
                        else:
                            self._validate_action_sequence(
                                choice["sequence"], f"{c_loc}.sequence", issues
                            )
                if "default" in item:
                    self._validate_action_sequence(item["default"], f"{loc}.default", issues)

            if "wait_for_trigger" in item:
                self._validate_trigger_list(
                    item["wait_for_trigger"], issues, f"{loc}.wait_for_trigger"
                )

            for nested_key in ("sequence", "then", "else"):
                nested = item.get(nested_key)
                if isinstance(nested, list):
                    self._validate_action_sequence(nested, f"{loc}.{nested_key}", issues)

            if "delay" in item and not isinstance(item["delay"], (int, float, str, dict)):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="'delay' must be a number, duration mapping or template string",
                        location=f"{loc}.delay",
                    )
                )

    def _collect_templates(self, node: Any, path: str = "") -> list[tuple[str, str]]:
        """Recursively collect Jinja template strings with their YAML paths."""
        templates: list[tuple[str, str]] = []
        if isinstance(node, str):
            if "{{" in node or "{%" in node:
                templates.append((path, node))
        elif isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                templates.extend(self._collect_templates(value, child))
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                templates.extend(self._collect_templates(item, f"{path}[{idx}]"))
        return templates

    def _validate_templates_and_safety(
        self, data: dict[str, Any], issues: list[ValidationIssue]
    ) -> None:
        """Check Jinja syntax and require an offline-sensor guard in conditions.

        The guard is only looked for inside ``condition:`` blocks: a blueprint
        that merely mentions the words "unavailable"/"unknown" in its
        description is not considered safe.
        """
        for path_str, tmpl_str in self._collect_templates(data):
            try:
                self._jinja_env.parse(tmpl_str)
            except jinja2.TemplateSyntaxError as exc:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Jinja template syntax error: {exc}",
                        location=f"{path_str} (line {exc.lineno})",
                    )
                )

        inputs = data.get("blueprint", {}).get("input", {})
        uses_entities = isinstance(inputs, dict) and any(
            isinstance(defn, dict)
            and isinstance(defn.get("selector"), dict)
            and "entity" in defn["selector"]
            for defn in inputs.values()
        )
        if not uses_entities:
            return

        condition_templates = [tmpl for _, tmpl in self._collect_templates(data.get("condition"))]
        has_guard = any("unavailable" in tmpl and "unknown" in tmpl for tmpl in condition_templates)
        if not has_guard:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=(
                        "No offline-sensor guard found in 'condition': add an explicit "
                        "'unavailable'/'unknown' check so a dead sensor cannot raise a "
                        "false emergency alert."
                    ),
                    location="condition",
                )
            )

    def parse_blueprint(self, path: Path) -> BlueprintDefinition | None:
        """Parse blueprint and return typed BlueprintDefinition if valid."""
        result = self.validate_file(path)
        if not result.valid:
            return None

        data, _ = self.load_yaml(path)
        assert data is not None
        bp = data["blueprint"]

        triggers = data.get("trigger", [])
        if isinstance(triggers, dict):
            triggers = [triggers]

        conditions = data.get("condition", [])
        if isinstance(conditions, dict):
            conditions = [conditions]

        actions = data.get("action", [])
        if isinstance(actions, dict):
            actions = [actions]

        variables = data.get("variables", {})
        if not isinstance(variables, dict):
            variables = {}

        return BlueprintDefinition(
            path=path,
            name=bp.get("name", path.stem),
            description=bp.get("description", ""),
            domain=bp.get("domain", "automation"),
            inputs=bp.get("input", {}),
            variables=variables,
            mode=data.get("mode", "single"),
            triggers=triggers,
            conditions=conditions,
            actions=actions,
            raw=data,
        )
