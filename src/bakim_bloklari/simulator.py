"""Home Assistant automation scenario runner and state engine simulator."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from bakim_bloklari.jinja_env import HomeAssistantJinjaEnvironment
from bakim_bloklari.models import (
    AutomationActionCall,
    BlueprintDefinition,
    EntityState,
    InputRef,
)


@dataclass
class _ScheduledState:
    """External state change queued to happen at a future simulator time."""

    when: datetime
    entity_id: str
    state: str


@dataclass
class _PendingTrigger:
    """A state trigger whose ``for:`` duration has not elapsed yet."""

    when: datetime
    entity_id: str
    expected_state: str
    trigger_id: str


class HomeAssistantSimulator:
    """Simulates the Home Assistant automation engine for deterministic dry-runs.

    Supported behaviour:
      * time triggers (``platform: time``), matched against the simulator clock,
      * state triggers including ``for:`` durations, evaluated on a virtual clock,
      * ``choose`` / ``delay`` / ``wait_for_trigger`` actions, with waits that poll
        template and state triggers minute by minute,
      * Jinja conditions rendered through :class:`HomeAssistantJinjaEnvironment`.

    Not simulated: real device latency, metered-time templates, ``repeat``/``parallel``
    blocks, and MQTT/webhook events. Scenarios rely only on the supported subset.
    """

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
        self._scheduled_states: list[_ScheduledState] = []
        self._pending_triggers: list[_PendingTrigger] = []

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
        """Set the simulator clock."""
        self.current_time = dt
        self.jinja.set_time(dt)

    def advance_time(self, seconds: int = 0, minutes: int = 0, hours: int = 0) -> None:
        """Advance the virtual clock, applying queued events and due triggers in order."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        self._advance_to(self.current_time + delta)

    def schedule_state(
        self,
        entity_id: str,
        state: str,
        after_minutes: float = 0,
        after_seconds: float = 0,
    ) -> None:
        """Queue an external entity change (e.g. the resident presses the button)."""
        when = self.current_time + timedelta(minutes=after_minutes, seconds=after_seconds)
        self._scheduled_states.append(_ScheduledState(when, entity_id, state))
        self._scheduled_states.sort(key=lambda item: item.when)

    def _advance_to(self, target: datetime) -> None:
        """Advance to ``target`` in chronological order of scheduled work."""
        if target < self.current_time:
            raise ValueError("Simulator time cannot move backwards in advance_time()")

        while True:
            candidates = [item.when for item in self._scheduled_states if item.when <= target] + [
                item.when for item in self._pending_triggers if item.when <= target
            ]
            if not candidates:
                break

            next_moment = min(candidates)
            if next_moment > self.current_time:
                self.set_time(next_moment)

            due_states = [s for s in self._scheduled_states if s.when <= self.current_time]
            for scheduled in due_states:
                self._scheduled_states.remove(scheduled)
                self.log(f"Scheduled state change: '{scheduled.entity_id}' -> '{scheduled.state}'")
                self.set_state(scheduled.entity_id, scheduled.state)

            due_triggers = [t for t in self._pending_triggers if t.when <= self.current_time]
            for pending in due_triggers:
                self._pending_triggers.remove(pending)
                self._fire_pending_trigger(pending)

        if target > self.current_time:
            self.set_time(target)

    def _fire_pending_trigger(self, pending: _PendingTrigger) -> None:
        current = self.jinja.get_state_val(pending.entity_id)
        if str(current).lower() != pending.expected_state.lower():
            self.log(
                f"Pending trigger '{pending.trigger_id}' cancelled: "
                f"'{pending.entity_id}' is now '{current}'"
            )
            return
        trigger_ctx = {
            "platform": "state",
            "entity_id": pending.entity_id,
            "id": pending.trigger_id,
            "to_state": {"state": pending.expected_state},
        }
        self.log(f"Trigger '{pending.trigger_id}' for-duration elapsed")
        self._run_automation(trigger_ctx)

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

    def process_state_change(self, entity_id: str, new_state: str) -> bool:
        """Apply a state change and fire the blueprint's matching state triggers.

        This is the realistic entry point: unlike :meth:`trigger_state_change` it
        honours ``entity_id``, ``to`` and ``for`` trigger filters.
        """
        from_state = self.jinja.get_state_val(entity_id)
        ent = self.set_state(entity_id, new_state)
        fired = False

        for trig in self.blueprint.triggers:
            if not isinstance(trig, dict) or trig.get("platform") != "state":
                continue
            trigger_entity = self._resolve_val(trig.get("entity_id"))
            if trigger_entity != entity_id:
                continue
            expected = trig.get("to")
            if expected is not None and str(expected).lower() != str(new_state).lower():
                continue

            trigger_id = str(trig.get("id") or f"state_{entity_id}")
            for_spec = trig.get("for")
            if for_spec is not None:
                duration = self._duration_to_timedelta(for_spec, default_minutes=0)
                if duration is None:
                    duration = timedelta(0)
                self._pending_triggers.append(
                    _PendingTrigger(
                        when=self.current_time + duration,
                        entity_id=entity_id,
                        expected_state=str(new_state),
                        trigger_id=trigger_id,
                    )
                )
                self._pending_triggers.sort(key=lambda item: item.when)
                self.log(
                    f"State trigger '{trigger_id}' armed for "
                    f"{duration.total_seconds() / 60:.0f} minute(s)"
                )
                continue

            trigger_ctx = {
                "platform": "state",
                "entity_id": entity_id,
                "id": trigger_id,
                "from_state": {"state": from_state},
                "to_state": {"state": ent.state},
            }
            self.log(f"Trigger '{trigger_id}' fired for '{entity_id}' -> '{new_state}'")
            fired = self._run_automation(trigger_ctx) or fired

        return fired

    def process_time_trigger(self, time_str: str | None = None) -> bool:
        """Fire the blueprint's time triggers that match the simulator clock."""
        now_str = self._normalize_time(time_str or self.current_time.strftime("%H:%M:%S"))
        fired = False
        for trig in self.blueprint.triggers:
            if not isinstance(trig, dict) or trig.get("platform") != "time":
                continue
            at = self._resolve_val(trig.get("at"))
            if at is None or self._normalize_time(at) != now_str:
                continue
            trigger_ctx = {
                "platform": "time",
                "now": self.current_time.isoformat(),
                "id": str(trig.get("id") or "time_trigger"),
            }
            self.log(f"Trigger 'time' fired at {now_str}")
            fired = self._run_automation(trigger_ctx) or fired
        return fired

    def evaluate_condition_item(self, cond: dict[str, Any], trigger_ctx: dict[str, Any]) -> bool:
        """Evaluate a single condition node."""
        cond_type = cond.get("condition")

        if cond_type == "template":
            tmpl = cond.get("value_template", "")
            if not tmpl:
                return True
            resolved_tmpl = self._substitute_inputs(tmpl)
            try:
                res = self.jinja.evaluate_condition_template(
                    resolved_tmpl, extra_vars=self._template_context(trigger_ctx)
                )
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

    def _run_automation(self, trigger_ctx: dict[str, Any]) -> bool:
        if not self.evaluate_all_conditions(trigger_ctx):
            return False
        self._execute_actions(self.blueprint.actions, trigger_ctx)
        return True

    def trigger_time_check(self, time_str: str | None = None) -> bool:
        """Force a time-trigger dispatch, bypassing trigger matching.

        Kept for focused condition tests; scenarios use :meth:`process_time_trigger`.
        """
        check_time = time_str or str(self.inputs.get("check_time", "10:00:00"))
        self.log(f"Triggering time event at {check_time}")
        trigger_ctx = {
            "platform": "time",
            "now": self.current_time.isoformat(),
            "id": "time_trigger",
        }
        return self._run_automation(trigger_ctx)

    def trigger_state_change(
        self, entity_id: str, to_state: str, trigger_id: str = "state_change"
    ) -> bool:
        """Force a state-trigger dispatch, bypassing trigger matching (tests only)."""
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
        return self._run_automation(trigger_ctx)

    def trigger_event(self, event_type: str, event_data: dict[str, Any]) -> bool:
        """Simulate an event-based trigger (e.g. button click)."""
        self.log(f"Triggering event '{event_type}' with data {event_data}")
        trigger_ctx = {
            "platform": "event",
            "event_type": event_type,
            "event_data": event_data,
            "to_state": {"state": event_data.get("state", event_data.get("event", ""))},
        }
        return self._run_automation(trigger_ctx)

    def _execute_actions(
        self, action_list: list[dict[str, Any]], trigger_ctx: dict[str, Any]
    ) -> None:
        """Execute action nodes and log invocations."""
        for act in action_list:
            if "choose" in act:
                choices = act.get("choose") or []
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
                self._execute_wait_for_trigger(act, trigger_ctx)
            elif "delay" in act:
                duration = self._duration_to_timedelta(act.get("delay"), default_minutes=5)
                if duration is None:
                    duration = timedelta(minutes=5)
                self.log(f"Action delay reached (duration={duration.total_seconds() / 60:.0f}m)")
                self._advance_to(self.current_time + duration)
            else:
                self._record_action(act)

    def _execute_wait_for_trigger(self, act: dict[str, Any], trigger_ctx: dict[str, Any]) -> None:
        """Wait for a trigger, polling once per simulated minute until the timeout."""
        specs = act.get("wait_for_trigger") or []
        timeout = self._duration_to_timedelta(act.get("timeout"), default_minutes=5)
        if timeout is None:
            timeout = timedelta(minutes=5)
        start = self.current_time
        deadline = start + timeout

        matched = self._evaluate_wait_triggers(specs, trigger_ctx)
        while not matched and self.current_time < deadline:
            step = min(timedelta(minutes=1), deadline - self.current_time)
            self._advance_to(self.current_time + step)
            matched = self._evaluate_wait_triggers(specs, trigger_ctx)

        elapsed = (self.current_time - start).total_seconds() / 60
        self.log(f"wait_for_trigger finished (matched={matched}, elapsed={elapsed:.0f}m)")

    def _evaluate_wait_triggers(self, specs: Any, trigger_ctx: dict[str, Any]) -> bool:
        """Return True when any trigger specification currently holds."""
        if isinstance(specs, dict):
            specs = [specs]
        if not isinstance(specs, list):
            return False

        for spec in specs:
            if not isinstance(spec, dict):
                continue
            platform = spec.get("platform")
            if platform == "template":
                tmpl = spec.get("value_template", "")
                if not tmpl:
                    continue
                try:
                    if self.jinja.evaluate_condition_template(
                        self._substitute_inputs(tmpl),
                        extra_vars=self._template_context(trigger_ctx),
                    ):
                        return True
                except Exception as exc:
                    self.log(f"Error evaluating wait template: {exc}")
                continue
            if platform == "state":
                ent_id = self._resolve_val(spec.get("entity_id"))
                expected = spec.get("to")
                current = self.jinja.get_state_val(str(ent_id))
                if current in ("unknown", "unavailable"):
                    continue
                if expected is None or str(current).lower() == str(expected).lower():
                    return True
        return False

    def _template_context(self, trigger_ctx: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {"trigger": trigger_ctx}
        context.update(self.inputs)
        context.update(self.resolved_variables)
        return context

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

    @staticmethod
    def _normalize_time(value: Any) -> str:
        text = str(value).strip()
        return text if len(text) == 8 else f"{text}:00"

    def _duration_to_timedelta(self, spec: Any, default_minutes: int = 5) -> timedelta | None:
        """Convert a blueprint delay/timeout spec into a timedelta."""
        if spec is None:
            return timedelta(minutes=default_minutes)
        if isinstance(spec, (int, float)):
            return timedelta(minutes=float(spec))
        if isinstance(spec, str):
            parts = spec.split(":")
            try:
                nums = [int(p) for p in parts]
            except ValueError:
                return timedelta(minutes=default_minutes)
            if len(nums) == 3:
                return timedelta(hours=nums[0], minutes=nums[1], seconds=nums[2])
            if len(nums) == 2:
                return timedelta(minutes=nums[0], seconds=nums[1])
            return timedelta(minutes=default_minutes)
        if isinstance(spec, dict):
            total = timedelta()
            for key, factor in (("hours", 3600), ("minutes", 60), ("seconds", 1)):
                if key not in spec:
                    continue
                raw = self._resolve_val(spec[key])
                try:
                    total += timedelta(seconds=float(raw) * factor)
                except (TypeError, ValueError):
                    return timedelta(minutes=default_minutes)
            return total
        return timedelta(minutes=default_minutes)

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
