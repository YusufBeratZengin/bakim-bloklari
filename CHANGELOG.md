# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-04

### Fixed
- **Button/event acknowledgements were ignored (`escalation_pipeline.yaml`)**: `ack_entity`
  advertised `event` entities, but the pipeline only accepted a switch turning `on`. Pressing a
  button changes the event state (`idle` -> `single_press`) and never yields `on`, so the
  resident was marked unresponsive and the caregiver alarm fired anyway. The wait now also
  listens for any state change other than `off`/`unavailable`/`unknown`/empty and gates the
  later stages on Home Assistant's `wait.completed`, so one press stops the pipeline.
- **Morning check-in input narrowed (`morning_inactivity.yaml`)**: a momentary button press
  cannot be observed at 10:00, so the input no longer offers `event` entities. It is documented
  as a boolean check-in flag set by the "I Am OK" button blueprint.

### Changed
- **Simulator fidelity (`simulator.py`)**: state triggers now ignore writes that do not change
  the state (Home Assistant only triggers on transitions) and accept `entity_id` lists.
  `wait_for_trigger` publishes Home Assistant's `wait.completed`, and every state trigger inside
  a wait only matches a transition observed during that wait - a value that was already there
  when the wait started (for example an acknowledgement left `on`) is not a fresh answer.
- Scenario 12 now starts the button event entity at `idle` and performs a real transition.

### Tests
- 80 tests. New regressions: an event-domain press stops escalation (red before the fix), a
  no-change write does not fire a state trigger, and `entity_id` lists are matched.

## [0.1.1] - 2026-11-04

### Fixed
- **Morning inactivity false alarms (`morning_inactivity.yaml`)**: the check now treats any
  sensor activity between `morning_start_time` and `check_time` as activity, using each
  sensor's `last_changed`. Previously only the instantaneous state at check time counted, so a
  resident who moved at 07:00 and sat still was reported as inactive at 10:00.
- **Escalation order (`escalation_pipeline.yaml`)**: the pipeline now matches its description:
  speaker prompt → wait for acknowledgement → resident phone notification → wait again →
  caregiver critical alarm. Acknowledgement at either window stops the remaining stages; the
  caregiver alarm can no longer fire before the resident notification.
- **Duplicate night alert (`door_left_open.yaml`)**: the daytime "left open" trigger now stays
  silent inside the night window when night wandering alerts are enabled, so one night exit
  produces one immediate alert instead of a second one after the daytime timeout.
- **`install` overwrite safety (`cli.py`)**: existing files are never overwritten silently.
  Identical files are reported unchanged; differing files are skipped and exit non-zero unless
  `--force` is passed, and `--backup` writes a timestamped `.bak` copy before replacing.

### Changed
- **Validator honesty (`schema.py`, README, CHANGELOG)**: claims narrowed to what the tool does.
  It is a structural validator (metadata, declared inputs, trigger platforms, action shapes,
  Jinja syntax, unknown automation mode, undeclared `!input` references), not the official
  Home Assistant core validator.
- **Offline-sensor guard detection**: the safety warning now inspects `condition:` templates
  only. Mentioning "unavailable"/"unknown" in a description no longer silences the warning.
- **Simulator executes blueprint triggers** instead of scenarios invoking actions directly:
  time triggers are matched against the clock, `for:` durations are armed/cancelled, and
  `wait_for_trigger` polls template/state triggers each simulated minute. All 12 scenarios now
  drive the real trigger path.
- **CI matrix** now includes Python 3.14 to match the classifiers, with a packaging test that
  fails if the two drift apart.
- **Blueprint descriptions** carry a Turkish (`TR:`) summary; `docs/blueprints.tr.md` adds a
  field-by-field Turkish reference. Home Assistant itself does not localise blueprint UI fields
  and the docs say so.
- **Package/repo blueprint copies**: a test now fails if `src/bakim_bloklari/blueprints/`
  diverges from `blueprints/automation/bakim_bloklari/`.

### Tests
- 76 tests (up from 52); regression tests cover earlier-morning motion, escalation ordering and
  acknowledgement stops, trigger `for:` durations, validator structural errors, and CLI install
  conflict/force/backup paths. Overall coverage 96% (threshold 85%).

## [0.1.0] - 2026-11-03

### Added
- **Core Elderly Care Blueprints (`blueprints/automation/bakim_bloklari/`)**:
  - `morning_inactivity.yaml`: Camera-free morning inactivity monitor with window timing, `unavailable`/`unknown` sensor suppression, and staged escalation.
  - `prolonged_bathroom.yaml`: Bathroom and wet room safety net alert for immobility or prolonged occupancy beyond configurable thresholds.
  - `door_left_open.yaml`: Daytime door left open alert and immediate nighttime wandering detection.
  - `escalation_pipeline.yaml`: Reusable multi-stage notification escalation pipeline (speaker prompt -> phone ping -> caregiver alarm).
  - `ok_button.yaml`: Wireless button handler for "I Am OK" acknowledgment (single click) and immediate SOS dispatch (double/long press).
- **Home Assistant Blueprint Validation Engine (`bakim_bloklari.schema`)**:
  - Structural validator for blueprint metadata, inputs, triggers, actions and `!input` tags.
  - Offline-sensor guard check for `unavailable`/`unknown` handling in `condition:` templates
    (a heuristic warning, not a full Home Assistant schema validator).
- **Home Assistant Virtual Environment & Template Engine (`bakim_bloklari.jinja_env`)**:
  - Mock Home Assistant Jinja2 environment providing `states()`, `is_state()`, `state_attr()`, `is_state_attr()`, `has_value()`, `now()`, `utcnow()`, `as_datetime()`, `as_timestamp()`, and `iif()`.
- **Deterministic State Engine Simulator (`bakim_bloklari.simulator`)**:
  - Virtual time-driven Home Assistant execution simulator for deterministic automation dry-runs.
- **12 Acceptance Test Scenarios (`bakim_bloklari.scenarios`)**:
  - Deterministic test suite covering motion detection, morning inactivity alert, away mode suppression, vacation mode suppression, sensor unavailable safe fallback, sensor unknown safe fallback, normal shower clearance, prolonged bathroom alarm, bathroom offline fallback, daytime door open timeout, nighttime wandering alert, and "I Am OK" acknowledgment button reset.
- **CLI (`bakim-bloklari`)**:
  - `validate`: Validate local blueprint YAML files for schema compliance and safety rules.
  - `simulate`: Run the 12 acceptance test scenarios with terminal report.
  - `list`: Inspect available blueprints in directory.
  - `inspect`: Detailed view of blueprint inputs, default values, and selectors.
  - `install`: Copy blueprints to local Home Assistant config directory.
- **Test Suite**:
  - 52 unit and integration tests with 100% statement coverage (99.23% overall) via `pytest-cov`.
- **CI / Quality Automation**:
  - GitHub Actions matrix workflow (Ubuntu + Windows).
  - Cross-platform check script `scripts/check.sh`.
