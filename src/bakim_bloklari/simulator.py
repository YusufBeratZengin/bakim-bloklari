"""Home Assistant automation scenario runner and state engine simulator."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any

from bakim_bloklari.jinja_env import HomeAssistantJinjaEnvironment
from bakim_bloklari.models import (
    AutomationActionCall,
    BlueprintDefinition,
    EntityState,
    InputRef,
)


class HomeAssistantSimulator:
    """Simulates the Home Assistant automation engine for deterministic dry-runs."""

    def __init__(
        self, blueprint: BlueprintDefinition, inputs: dict[str, Any] | None = None
    ) -> None:
        self.blueprint = blueprint
        self.inputs: dict[str, Any] = self._resolve_inputs(inputs or {})
        self.resolved_variables: dict[str, Any] = self._resolve_variables()
        self.states: dict[str, EntityState] = {}
        self.jinja = HomeAssistantJinjaEnvironment(self.states)
        self.current_time = datetime(2026, 11, 3, 7, 0, 0)
        self.action_history: list[AutomationActionCall] = []
        self.logs: list[str] = []

    def _resolve_variables(self) -> dict[str, Any]:
        """Resolve blueprint variable mappings against resolved inputs."""
        vars_map: dict[str, Any] = {}
        for var_name, var_val in self.blueprint.variables.items():
            if isinstance(var_val, InputRef):
                vars_map[var_name] = self.inputs.get(var_val.key)
            else:
                vars_map[var_name] = var_val
        return vars_map

    def _resolve_inputs(self, user_inputs: dict[str, Any]) -> dict[str, Any]:
        """Combine user inputs with blueprint default inputs."""
        resolved: dict[str, Any] = {}
        for key, defn in self.blueprint.inputs.items():
            if isinstance(defn, dict) and "default" in defn:
                resolved[key] = defn["default"]
            else:
                resolved[key] = None
        resolved.update(user_inputs)
        return resolved

    def log(self, msg: str) -> None:
        time_str = self.current_time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{time_str}] {msg}"
        self.logs.append(entry)

    def set_time(self, dt: datetime) -> None:
        """Advance simulator clock."""
        self.current_time = dt
        self.jinja.set_time(dt)

    def advance_time(self, seconds: int = 0, minutes: int = 0, hours: int = 0) -> None:
        """Advance time by relative offset."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        self.set_time(self.current_time + delta)

    def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> EntityState:
        """Set or update state of an entity in the simulator."""
        ts = timestamp or self.current_time
        old_entity = self.states.get(entity_id)
        last_changed = (
            ts if old_entity is None or old_entity.state != state else old_entity.last_changed
        )

        attrs = (
            copy.deepcopy(attributes)
            if attributes is not None
            else (old_entity.attributes.copy() if old_entity else {})
        )
        ent = EntityState(
            entity_id=entity_id,
            state=state,
            attributes=attrs,
            last_changed=last_changed,
            last_updated=ts,
        )
        self.states[entity_id] = ent
        self.jinja.update_states(self.states)
        self.log(f"Entity '{entity_id}' state -> '{state}'")
        return ent

    def evaluate_condition_item(self, cond: dict[str, Any], trigger_ctx: dict[str, Any]) -> bool:
        """Evaluate a single condition node."""
        cond_type = cond.get("condition")

        if cond_type == "template":
            tmpl = cond.get("value_template", "")
            if not tmpl:
                return True
            resolved_tmpl = self._substitute_inputs(tmpl)
            try:
                context: dict[str, Any] = {"trigger": trigger_ctx}
                context.update(self.inputs)
                context.update(self.resolved_variables)
                res = self.jinja.evaluate_condition_template(resolved_tmpl, extra_vars=context)
                self.log(f"Evaluated template condition: {res}")
                return res
            except Exception as exc:
                self.log(f"Error evaluating template condition: {exc}")
                return False

        if cond_type == "state":
            ent_id = self._resolve_val(cond.get("entity_id", ""))
            expected = cond.get("state")
            current = self.jinja.get_state_val(ent_id)
            res = str(current).lower() == str(expected).lower()
            self.log(
                f"Evaluated state condition on '{ent_id}' (curr='{current}', exp='{expected}'): {res}"
            )
            return res

        if cond_type == "and":
            subs = cond.get("conditions", [])
            return all(self.evaluate_condition_item(c, trigger_ctx) for c in subs)

        if cond_type == "or":
            subs = cond.get("conditions", [])
            return any(self.evaluate_condition_item(c, trigger_ctx) for c in subs)

        if cond_type == "not":
            subs = cond.get("conditions", [])
            return not any(self.evaluate_condition_item(c, trigger_ctx) for c in subs)

        return True

    def evaluate_all_conditions(self, trigger_ctx: dict[str, Any]) -> bool:
        """Evaluate all top-level conditions for the blueprint."""
        for cond in self.blueprint.conditions:
            if not self.evaluate_condition_item(cond, trigger_ctx):
                self.log("Condition check failed; automation execution halted.")
                return False
        self.log("All conditions passed.")
        return True

    def trigger_time_check(self, time_str: str | None = None) -> bool:
        """Simulate a time trigger at specified or configured check time."""
        check_time = time_str or str(self.inputs.get("check_time", "10:00:00"))
        self.log(f"Triggering time event at {check_time}")
        trigger_ctx = {
            "platform": "time",
            "now": self.current_time.isoformat(),
            "id": "time_trigger",
        }
        if self.evaluate_all_conditions(trigger_ctx):
            self._execute_actions(self.blueprint.actions, trigger_ctx)
            return True
        return False

    def trigger_state_change(
        self, entity_id: str, to_state: str, trigger_id: str = "state_change"
    ) -> bool:
        """Simulate a state change event triggering automation."""
        from_state = self.jinja.get_state_val(entity_id)
        self.set_state(entity_id, to_state)
        self.log(f"Triggering state event for '{entity_id}' -> '{to_state}' (id={trigger_id})")

        trigger_ctx = {
            "platform": "state",
            "entity_id": entity_id,
            "id": trigger_id,
            "from_state": {"state": from_state},
            "to_state": {"state": to_state},
        }

        if self.evaluate_all_conditions(trigger_ctx):
            self._execute_actions(self.blueprint.actions, trigger_ctx)
            return True
        return False

    def trigger_event(self, event_type: str, event_data: dict[str, Any]) -> bool:
        """Simulate an event-based trigger (e.g. button click)."""
        self.log(f"Triggering event '{event_type}' with data {event_data}")
        trigger_ctx = {
            "platform": "event",
            "event_type": event_type,
            "event_data": event_data,
            "to_state": {"state": event_data.get("state", event_data.get("event", ""))},
        }
        if self.evaluate_all_conditions(trigger_ctx):
            self._execute_actions(self.blueprint.actions, trigger_ctx)
            return True
        return False

    def _execute_actions(
        self, action_list: list[dict[str, Any]], trigger_ctx: dict[str, Any]
    ) -> None:
        """Execute action nodes and log invocations."""
        for act in action_list:
            if "choose" in act:
                choices = act.get("choose", [])
                executed_choice = False
                for choice in choices:
                    conds = choice.get("conditions", [])
                    if all(self.evaluate_condition_item(c, trigger_ctx) for c in conds):
                        seq = choice.get("sequence", [])
                        if isinstance(seq, InputRef):
                            seq = self.inputs.get(seq.key, [])
                        if isinstance(seq, list):
                            self._execute_actions(seq, trigger_ctx)
                        executed_choice = True
                        break
                if not executed_choice:
                    default_action = act.get("default", [])
                    if isinstance(default_action, InputRef):
                        default_action = self.inputs.get(default_action.key, [])
                    if isinstance(default_action, list):
                        self._execute_actions(default_action, trigger_ctx)
                    elif isinstance(default_action, dict):
                        self._record_action(default_action)
            elif "wait_for_trigger" in act:
                timeout_mins = 5
                timeout_spec = act.get("timeout", {})
                if isinstance(timeout_spec, dict):
                    mins_val = timeout_spec.get("minutes", 5)
                    if isinstance(mins_val, InputRef):
                        mins_val = self.inputs.get(mins_val.key, 5)
                    try:
                        timeout_mins = int(mins_val)
                    except (ValueError, TypeError):
                        timeout_mins = 5

                self.log(f"Action wait_for_trigger reached (timeout={timeout_mins}m)")
                # advance time by wait duration
                self.advance_time(minutes=timeout_mins)
            else:
                self._record_action(act)

    def _record_action(self, act: dict[str, Any]) -> None:
        action_name = act.get("action") or act.get("service") or "notify"
        target = str(act.get("target", ""))
        data = act.get("data", {})
        call = AutomationActionCall(
            action_type=str(action_name),
            target=target,
            data=data if isinstance(data, dict) else {},
            timestamp=self.current_time,
        )
        self.action_history.append(call)
        self.log(f"Action executed: {call.action_type} (target={call.target})")

    def _resolve_val(self, val: Any) -> Any:
        if isinstance(val, InputRef):
            return self.inputs.get(val.key)
        return val

    def _substitute_inputs(self, template_str: str) -> str:
        """Substitute input variables in templates."""
        result = template_str
        for key, val in self.inputs.items():
            pattern1 = f"{{{{ {key} }}}}"
            pattern2 = f"{{{{{key}}}}}"
            if isinstance(val, list):
                repr_val = str(val)
            elif isinstance(val, bool):
                repr_val = "true" if val else "false"
            elif val is None:
                repr_val = "''"
            else:
                repr_val = str(val)
            result = result.replace(pattern1, repr_val).replace(pattern2, repr_val)
        return result
