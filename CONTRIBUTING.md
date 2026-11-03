# Contributing to bakim-bloklari

Thank you for your interest in contributing to `bakim-bloklari`! We welcome contributions that improve elderly safety, reduce caregiver alert fatigue, and protect resident privacy without intrusive cameras.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yusufberatzengin/bakim-bloklari.git
   cd bakim-bloklari
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies in editable mode:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run the quality check script:**
   ```bash
   bash scripts/check.sh
   ```

## Blueprint Contribution Guidelines

If you are contributing a new Home Assistant blueprint:
1. Place the YAML file in `blueprints/automation/bakim_bloklari/<name>.yaml`.
2. Follow standard Home Assistant blueprint specifications (`blueprint:`, `domain: automation`, `input:`, `trigger:`, `action:`).
3. **Safety Requirement:** All elderly care blueprints **must** explicitly handle `unavailable` and `unknown` sensor states in their conditions to prevent false alarms when Zigbee/Z-Wave devices drop off or reboot.
4. Provide both English and Turkish explanations in descriptions or comments.
5. Add corresponding deterministic acceptance scenarios to `src/bakim_bloklari/scenarios.py`.
6. Run `bakim-bloklari validate` and `bakim-bloklari simulate` to verify before submitting a PR.

## Code Style & Testing

- **Linting & Formatting:** We use `ruff`.
  ```bash
  ruff check src tests
  ruff format --check src tests
  ```
- **Type Checking:** Strict `mypy` is required.
  ```bash
  mypy src tests
  ```
- **Test Suite & Coverage:** We require pytest test coverage >= 85%.
  ```bash
  pytest --cov=bakim_bloklari --cov-fail-under=85
  ```

## Pull Request Process

1. Fork the repository and create a feature branch (`git checkout -b feature/new-kitchen-inactivity-blueprint`).
2. Commit your changes with concise, descriptive commit messages.
3. Ensure `bash scripts/check.sh` passes with exit code 0.
4. Open a Pull Request referencing any relevant issues.
