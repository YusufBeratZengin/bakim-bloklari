# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-03

### Added
- **Core Elderly Care Blueprints (`blueprints/automation/bakim_bloklari/`)**:
  - `morning_inactivity.yaml`: Camera-free morning inactivity monitor with window timing, `unavailable`/`unknown` sensor suppression, and staged escalation.
  - `prolonged_bathroom.yaml`: Bathroom and wet room safety net alert for immobility or prolonged occupancy beyond configurable thresholds.
  - `door_left_open.yaml`: Daytime door left open alert and immediate nighttime wandering detection.
  - `escalation_pipeline.yaml`: Reusable multi-stage notification escalation pipeline (speaker prompt -> phone ping -> caregiver alarm).
  - `ok_button.yaml`: Wireless button handler for "I Am OK" acknowledgment (single click) and immediate SOS dispatch (double/long press).
- **Home Assistant Blueprint Validation Engine (`bakim_bloklari.schema`)**:
  - Full schema validator for Home Assistant blueprint standards, selectors, and tags (`!input`).
  - Strict safety filter enforcing offline (`unavailable`/`unknown`) sensor handling to prevent false emergency alerts.
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
