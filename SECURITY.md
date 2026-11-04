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

1. **No Telemetry From This Project:** The blueprints, validator and simulator contain no analytics and make no outbound network calls of their own. Sensor evaluation and scenario simulation run on your own Home Assistant instance.
2. **Outbound Data Depends on Your Actions:** The blueprints deliberately accept free-form Home Assistant actions (`speaker_action`, `resident_notify_action`, `caregiver_notify_action`, `notify_action`). If you point those at a mobile-app push, Nabu Casa Cloud, Telegram, e-mail or a webhook, the message content leaves your network and that integration's privacy policy applies. Motion history is stored in your Home Assistant recorder database; protecting it, its backups and any remote access is the operator's responsibility.
3. **No Hardcoded Credentials:** Blueprints never request or store API tokens, account keys, or passwords. All notification targets use Home Assistant native notification services and entities.
4. **Fail-Safe Offline Handling:** Sensors marked as `unavailable` or `unknown` are explicitly caught by conditions to avoid triggering false emergency escalations when devices reboot or battery levels drop.
5. **Disclaimer:** `bakim-bloklari` is an open-source automation toolkit designed for ambient assistance. It is NOT a certified medical device or certified emergency response system.
