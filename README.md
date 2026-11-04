# bakim-bloklari

> **Privacy-first, camera-free Home Assistant blueprint package and simulation engine for ambient elderly care and aging-in-place.**

[![CI](https://github.com/yusufberatzengin/bakim-bloklari/actions/workflows/ci.yml/badge.svg)](https://github.com/yusufberatzengin/bakim-bloklari/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Coverage: 96%](https://img.shields.io/badge/coverage-96%25-brightgreen.svg)](scripts/check.sh)

`bakim-bloklari` delivers non-intrusive ambient awareness automations for seniors living independently. Without deploying privacy-invasive cameras or listening microphones, it monitors passive ambient sensors (PIR motion detectors, mmWave presence radar, and magnetic door contacts) to detect morning immobility, prolonged bathroom occupancy, or nighttime exit wandering, escalating notifications to family members only when necessary.

It includes a Python test and dry-run engine that validates blueprint structure (metadata, declared inputs, triggers, actions, Jinja syntax) and simulates 12 deterministic real-world scenarios to ensure **offline or unavailable sensors never trigger false emergency alarms**.

> The validator checks the blueprint contract this project relies on. It is **not** the official Home Assistant core validator, and passing it does not guarantee that HA will load a blueprint; review the [limitations](#simulator-scope--limitations) before relying on it.

---

## 30-Second Quickstart

### 1. Import Directly into Home Assistant
In Home Assistant, navigate to **Settings > Automations & Scenes > Blueprints > Import Blueprint**, and paste the URL of any blueprint:

```text
https://github.com/yusufberatzengin/bakim-bloklari/blob/main/blueprints/automation/bakim_bloklari/morning_inactivity.yaml
```

Or install the full package locally via the CLI tool:

```bash
pip install bakim-bloklari
bakim-bloklari install --target ~/.homeassistant
```

`install` never overwrites your local edits silently: identical files are reported as
unchanged, differing files are skipped. Use `--force` to overwrite or `--backup` to keep a
timestamped `.bak` copy first.

### 2. Validate & Dry-Run with CLI
Validate blueprints and execute deterministic scenario simulations without touching live hardware:

```bash
# Validate Home Assistant YAML blueprint schema & offline safety rules
bakim-bloklari validate

# Run all 12 deterministic test scenarios in the state engine simulator
bakim-bloklari simulate
```

### Real Terminal Output

```text
$ bakim-bloklari validate
[bakim-bloklari v0.1.1] Validating 5 blueprint(s)...

[PASS] door_left_open.yaml - Elderly Care - Exterior Door Left Open & Night Wandering (Errors: 0, Warnings: 0)
[PASS] escalation_pipeline.yaml - Elderly Care - Multi-Stage Escalation Pipeline (Errors: 0, Warnings: 0)
[PASS] morning_inactivity.yaml - Elderly Care - Morning Inactivity Monitor (Errors: 0, Warnings: 0)
[PASS] ok_button.yaml - Elderly Care - 'I Am OK' & Emergency Button Handler (Errors: 0, Warnings: 0)
[PASS] prolonged_bathroom.yaml - Elderly Care - Prolonged Bathroom Occupancy Alert (Errors: 0, Warnings: 0)

============================================================
Validation SUCCESS: All 5 blueprint(s) passed schema checks.

$ bakim-bloklari simulate
[bakim-bloklari v0.1.1] Running 12 Acceptance Scenarios against: bakim_bloklari

[PASS] SCENARIO-01: Morning Motion Detected Earlier in Window -> No Alarm
[PASS] SCENARIO-02: Zero Morning Motion -> Escalation Alarm Fired
[PASS] SCENARIO-03: Resident Away (not_home) -> Alarm Suppressed
[PASS] SCENARIO-04: Vacation Mode Active -> Alarm Suppressed
[PASS] SCENARIO-05: Motion Sensor Unavailable -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-06: Motion Sensor Unknown -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-07: Bathroom Normal 15-Min Shower -> Cleared Normally
[PASS] SCENARIO-08: Bathroom Prolonged Occupancy (>30m) -> Emergency Alert Fired
[PASS] SCENARIO-09: Bathroom Sensor Unavailable -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-10: Front Door Left Open Daytime (>5m) -> Alert Fired
[PASS] SCENARIO-11: Night Wandering Door Open (02:30 AM) -> Urgent Alert Fired
[PASS] SCENARIO-12: 'I Am OK' Button Single Press -> Alert Acknowledged & Cleared

============================================================
Simulation Summary: 12/12 scenarios passed.
All elderly care scenarios verified successfully.
```

---

## Included Blueprints (v0.1)

| Blueprint | Description | Supported Hardware |
| --------- | ----------- | ------------------ |
| [`morning_inactivity.yaml`](blueprints/automation/bakim_bloklari/morning_inactivity.yaml) | Evaluates motion across the morning window (e.g. 06:30 - 10:00). Any motion in that window — not just the exact check instant — counts as activity. If none is seen while the resident is home, initiates a staged escalation. | PIR motion sensors, mmWave presence radar, Zigbee contact sensors. |
| [`prolonged_bathroom.yaml`](blueprints/automation/bakim_bloklari/prolonged_bathroom.yaml) | Monitors bathroom presence to protect against unobserved falls or medical crises behind closed doors. Triggers an alert when occupancy exceeds threshold (e.g. 30 min). | mmWave radar (Aqara FP2, LD2410), PIR sensors, door contacts. |
| [`door_left_open.yaml`](blueprints/automation/bakim_bloklari/door_left_open.yaml) | Alerts if external entrance doors remain open during the day (>5 min), or triggers immediate family alerts if opened during nighttime sleep hours (23:00 - 06:00) for wandering/sleepwalking prevention. | Magnetic door contact sensors (Zigbee / Z-Wave / Matter). |
| [`escalation_pipeline.yaml`](blueprints/automation/bakim_bloklari/escalation_pipeline.yaml) | Multi-stage alert pipeline that minimizes caregiver alert fatigue: plays a local speaker inquiry first ("Are you okay?"), waits for acknowledgement, then sends a soft phone notification and waits again; only an unanswered second window escalates to the caregiver alarm. | Media player / smart speaker, companion mobile app. |
| [`ok_button.yaml`](blueprints/automation/bakim_bloklari/ok_button.yaml) | Wireless bedside check-in button handler. Single press acknowledges check-in and resets active alert booleans; double press or hold triggers an instant SOS distress alert. | Zigbee / Matter wireless buttons, smart switches. |

---

## Safety & False Alarm Prevention Architecture

A major pitfall of smart home automations in elderly care is **alert fatigue**: if a caregiver receives repeated false alarms whenever a sensor reboots, changes batteries, or drops off a wireless mesh, the system loses trust and becomes dangerous.

`bakim-bloklari` blueprints enforce strict safety rules directly in Home Assistant Jinja conditions:

```yaml
# Example: Sensor health validation in morning_inactivity.yaml
condition:
  - condition: template
    value_template: >-
      {% set sensors = motion_sensors_var %}
      {% set sensor_list = sensors if sensors is iterable and sensors is not string else [sensors] %}
      {% set valid_sensors = sensor_list | reject('is_state', 'unavailable') | reject('is_state', 'unknown') | list %}
      {{ valid_sensors | length > 0 }}
```

1. **Offline Sensor Filtering:** Sensors in `unavailable` or `unknown` states are isolated. If all sensors are temporarily offline (e.g. Zigbee coordinator restart), emergency alarms are suppressed to avoid false distress calls.
2. **Away Mode & Vacation Suppression:** If the resident's `person` entity is `not_home` or `vacation_mode` is active, inactivity alarms are automatically suspended.
3. **Multi-Stage Graduated Escalation:** Local chimes and polite resident phone prompts precede family critical notifications, giving seniors time to dismiss accidental triggers.

---

## CLI Commands

The `bakim-bloklari` Python CLI tool provides complete tooling to validate, simulate, inspect, and deploy blueprints:

```bash
# List all blueprints with descriptions and input counts
bakim-bloklari list

# Inspect detailed inputs, selectors, and defaults of a blueprint
bakim-bloklari inspect morning_inactivity

# Validate blueprint structure, declared inputs and Jinja syntax
bakim-bloklari validate [optional_path]

# Run deterministic 12-scenario test simulation
bakim-bloklari simulate [-v]

# Copy blueprints into Home Assistant configuration directory
bakim-bloklari install --target /path/to/homeassistant [--force | --backup]
```

---

## Simulator Scope & Limitations

The simulator is an approval aid, not a Home Assistant runtime. It executes a virtual clock
and a deliberately small subset of the automation engine:

**Modelled**
- time triggers matched against the simulated clock,
- state triggers including `for:` durations (with cancellation when the entity leaves the state),
- `choose`, `delay` and `wait_for_trigger` (polled minute by minute, so an acknowledgement
  during a wait stops the stage),
- Home Assistant Jinja helpers this project uses: `states[...]` with `last_changed`,
  `is_state`, `state_attr`, `now`, `today_at`, `as_timestamp`, `as_datetime`, `iif`.

**Not modelled**
- real device latency, Zigbee/Z-Wave mesh behaviour, MQTT/webhook/event payloads,
- `repeat`, `parallel`, `if/then`, `wait_template`, template triggers in the main `trigger:` block,
- templates that depend on attributes this simulator does not populate.

Scenarios therefore prove *logic* (state gating, offline safety, escalation order, timing
thresholds), not that a specific Home Assistant release will load the YAML. Before relying on
a blueprint in production, validate it in **Developer Tools → YAML → Check configuration** on
your own Home Assistant instance.

---

## Localisation

Home Assistant blueprint schemas do not support per-field translation: the names and
descriptions in the blueprint UI are whatever the YAML declares. Every blueprint in this
package therefore carries an English description followed by a Turkish (`TR:`) summary, and
[`docs/blueprints.tr.md`](docs/blueprints.tr.md) provides a field-by-field Turkish reference
including example entity mappings. Turkish-speaking users can follow the guide while the UI
labels stay in English, which is what Home Assistant supports today.

---

## Runtime Dependencies & Rationale

`bakim-bloklari` maintains a minimal dependency footprint:

- `pyyaml`: Required for parsing and serializing Home Assistant blueprint YAML definitions with custom YAML tags (`!input`).
- `jinja2`: Required for rendering, testing, and verifying embedded Home Assistant Jinja2 automation expressions, filters, and state evaluations.

All other functionality relies exclusively on the Python standard library.

---

## Target Audience & Limitations

- **Target Audience:** Families supporting aging parents, independent elderly individuals (`NEEDS_SOURCE` for global demographic market size), caregivers, and Home Assistant smart home enthusiasts.
- **Privacy Notice:** 100% of automation logic and sensor processing runs entirely locally on your Home Assistant server. No movement logs, presence timestamps, or personal data leave your premises.
- **Non-Medical Disclaimer:**

> [!IMPORTANT]
> **NOT A CERTIFIED MEDICAL OR LIFE-SAVING EMERGENCY DEVICE:**  
> `bakim-bloklari` is an open-source ambient home automation assistant. It does not provide medical diagnoses, active biometric vitals monitoring, or direct connection to emergency dispatch services (911/112). It is designed as an auxiliary comfort and early-warning tool and must never replace certified personal emergency response systems (PERS), fall pendants, or professional caregiving services.

---

## Development & Testing

```bash
# Clone and setup
git clone https://github.com/yusufberatzengin/bakim-bloklari.git
cd bakim-bloklari
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run full quality check (lint + typecheck + tests + coverage + simulate)
bash scripts/check.sh
```

---

## License

This project is licensed under the [MIT License](LICENSE) - Copyright (c) 2026 Yusuf Berat Zengin.
