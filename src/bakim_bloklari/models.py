"""Data models for bakim-bloklari blueprint validation and simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


class InputRef:
    """Wrapper for !input YAML tags in Home Assistant blueprints."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __repr__(self) -> str:
        return f"!input {self.key}"

    def __str__(self) -> str:
        return f"!input {self.key}"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, InputRef):
            return self.key == other.key
        return False


@dataclass
class ValidationIssue:
    """Represents a validation error or warning."""

    severity: Literal["error", "warning"]
    message: str
    location: str = ""


@dataclass
class ValidationResult:
    """Result of blueprint schema and rule validation."""

    file_path: str
    blueprint_name: str
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


@dataclass
class BlueprintDefinition:
    """Parsed Home Assistant automation blueprint."""

    path: Path
    name: str
    description: str
    domain: str
    inputs: dict[str, Any]
    variables: dict[str, Any]
    mode: str
    triggers: list[dict[str, Any]]
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    raw: dict[str, Any]


@dataclass
class EntityState:
    """Home Assistant entity state representation."""

    entity_id: str
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class AutomationActionCall:
    """Recorded action invocation during automation simulation."""

    action_type: str
    target: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ScenarioResult:
    """Result of running a test scenario through the simulator."""

    scenario_id: str
    name: str
    passed: bool
    logs: list[str] = field(default_factory=list)
    action_calls: list[AutomationActionCall] = field(default_factory=list)
    error_message: str | None = None
