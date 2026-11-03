"""Jinja2 environment mirroring Home Assistant template extensions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import jinja2

from bakim_bloklari.models import EntityState


class HomeAssistantJinjaEnvironment:
    """Provides a Jinja2 execution environment compatible with Home Assistant."""

    def __init__(self, state_store: dict[str, EntityState] | None = None) -> None:
        self.state_store: dict[str, EntityState] = state_store if state_store is not None else {}
        self.current_time: datetime = datetime.now()
        self.env: jinja2.Environment = self._build_jinja_env()

    def update_states(self, state_store: dict[str, EntityState]) -> None:
        self.state_store = state_store

    def set_time(self, dt: datetime) -> None:
        self.current_time = dt

    def get_state_val(self, entity_id: str) -> str:
        if not entity_id or not isinstance(entity_id, str):
            return "unknown"
        clean_id = entity_id.strip("'\"")
        entity = self.state_store.get(clean_id)
        if entity is None:
            return "unknown"
        return str(entity.state)

    def is_state(self, entity_id: str, state: str) -> bool:
        if not entity_id or not isinstance(entity_id, str):
            return False
        clean_id = entity_id.strip("'\"")
        entity = self.state_store.get(clean_id)
        if entity is None:
            return False
        return str(entity.state).lower() == str(state).lower()

    def get_attr_val(self, entity_id: str, attribute: str) -> Any:
        clean_id = entity_id.strip("'\"")
        entity = self.state_store.get(clean_id)
        if entity is None:
            return None
        return entity.attributes.get(attribute)

    def is_state_attr(self, entity_id: str, attribute: str, value: Any) -> bool:
        attr = self.get_attr_val(entity_id, attribute)
        return bool(attr == value)

    def has_value(self, entity_id: str) -> bool:
        val = self.get_state_val(entity_id)
        return val not in ("unknown", "unavailable", "")

    def _build_jinja_env(self) -> jinja2.Environment:
        env = jinja2.Environment(
            undefined=jinja2.Undefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # HA global functions
        env.globals["states"] = self.get_state_val
        env.globals["is_state"] = self.is_state
        env.globals["state_attr"] = self.get_attr_val
        env.globals["is_state_attr"] = self.is_state_attr
        env.globals["has_value"] = self.has_value
        env.globals["now"] = lambda: self.current_time
        env.globals["utcnow"] = lambda: self.current_time.astimezone(timezone.utc)

        # HA filters
        env.filters["is_state"] = lambda entity_id, state: self.is_state(entity_id, state)
        env.filters["as_datetime"] = self._as_datetime
        env.filters["as_timestamp"] = self._as_timestamp
        env.filters["iif"] = lambda condition, if_true=True, if_false=False: (
            if_true if condition else if_false
        )

        # HA tests (for reject / select filters)
        env.tests["is_state"] = lambda entity_id, state: self.is_state(entity_id, state)

        return env

    def _as_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _as_timestamp(self, value: Any) -> float | None:
        dt = self._as_datetime(value)
        if dt:
            return dt.timestamp()
        return None

    def render_template(self, template_str: str, extra_vars: dict[str, Any] | None = None) -> str:
        """Render a Jinja2 template string."""
        context: dict[str, Any] = {}
        if extra_vars:
            context.update(extra_vars)
        template = self.env.from_string(template_str)
        return template.render(**context)

    def evaluate_condition_template(
        self, template_str: str, extra_vars: dict[str, Any] | None = None
    ) -> bool:
        """Evaluate a Jinja template string as a boolean condition."""
        rendered = self.render_template(template_str, extra_vars).strip()
        return rendered.lower() in ("true", "1", "yes", "on")
