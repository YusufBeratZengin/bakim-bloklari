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

    def _validate_templates_and_safety(
        self, data: dict[str, Any], issues: list[ValidationIssue]
    ) -> None:
        """Recursively checks Jinja syntax and scans for unavailable/unknown safety checks."""
        # Check safety rule across conditions/triggers/variables
        dumped_str = str(data)
        if "unavailable" not in dumped_str or "unknown" not in dumped_str:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=(
                        "Safety Notice: Blueprint does not explicitly check for 'unavailable' "
                        "and 'unknown' sensor states. Ensure offline sensors do not trigger false alarms."
                    ),
                    location="condition",
                )
            )

        # Recursively find all template strings
        template_strings: list[tuple[str, str]] = []

        def collect_templates(node: Any, current_path: str) -> None:
            if isinstance(node, str):
                if "{{" in node or "{%" in node:
                    template_strings.append((current_path, node))
            elif isinstance(node, dict):
                for k, v in node.items():
                    collect_templates(v, f"{current_path}.{k}" if current_path else str(k))
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    collect_templates(item, f"{current_path}[{idx}]")

        collect_templates(data, "")

        for path_str, tmpl_str in template_strings:
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
