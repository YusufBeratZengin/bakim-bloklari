## Description
Briefly describe the purpose of this PR and what changes were made.

## Blueprint / Code Changes
- [ ] Added or updated blueprint in `blueprints/automation/bakim_bloklari/`
- [ ] Added or updated simulator scenarios in `src/bakim_bloklari/scenarios.py`
- [ ] Added or updated unit tests in `tests/`
- [ ] Updated documentation (README.md, README.tr.md, CHANGELOG.md)

## Safety & Offline Sensor Handling
- [ ] Verified that sensors in `unavailable` or `unknown` state do not trigger false alarms
- [ ] No hardcoded tokens, passwords, or personal data

## Quality Checks
- [ ] `bash scripts/check.sh` passes with exit code 0
- [ ] `ruff check src tests` passes
- [ ] `ruff format --check src tests` passes
- [ ] `mypy src tests` passes without issues
- [ ] `pytest --cov=bakim_bloklari` achieves >= 85% coverage
