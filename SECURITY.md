# Security Policy

## Supported Versions

Only the latest release of `bakim-bloklari` receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

We take the security of vulnerable individuals and privacy-first home automation very seriously. If you discover a security vulnerability or safety flaw within `bakim-bloklari`, please do NOT open a public issue.

Instead, please report security concerns directly by contacting the project maintainer via:
- GitHub Security Advisory: Open a private advisory under the Security tab of the repository.

Please include:
1. Detailed description of the vulnerability.
2. Reproduction steps, simulated automation scenario, or configuration snippet.
3. Potential impact on resident safety or privacy.

You will receive an acknowledgment within 48 hours.

## Privacy & Safety Design Principles

1. **Zero External Telemetry:** All blueprints and simulation tools execute 100% locally on your Home Assistant instance. No sensor states, events, or resident data ever leave your local network.
2. **No Hardcoded Credentials:** Blueprints never request or store API tokens, account keys, or passwords. All notification targets use Home Assistant native notification services and entities.
3. **Fail-Safe Offline Handling:** Sensors marked as `unavailable` or `unknown` are explicitly caught by conditions to avoid triggering false emergency escalations when devices reboot or battery levels drop.
4. **Disclaimer:** `bakim-bloklari` is an open-source automation toolkit designed for ambient assistance. It is NOT a certified medical device or certified emergency response system.
