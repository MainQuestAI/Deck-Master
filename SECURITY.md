# Security Policy

## Supported Status

Security fixes target the current 1.x release line on a best-effort basis.
There is no promised response SLA or independent security certification.

## Reporting

Do not disclose exploit steps, payloads, credentials, customer material, or
sensitive logs in public Issues or pull requests. First check this repository's
Security tab for GitHub's **Report a vulnerability** action. Use it only if the
private reporting action is actually available.

Private vulnerability reporting has **not been verified** for this repository
as of 2026-10-20. This policy file does not enable it. There is no separately
verified private contact listed here. If the private action is unavailable,
withhold the report details. At most, open a public request saying only that a
private security contact is needed, without identifying the vulnerability,
affected target, reproduction, or sensitive evidence. Wait for a maintainer to
establish a verified private channel before sharing details.

Maintainers must verify the channel and update this policy before advertising
private reporting as available; see the [setup checklist](docs/issue-maintenance.md#上线检查).

## Current Threat Boundary

Deck Master is a local-first tool running with the user's filesystem permissions.
Its Workbench is a loopback service, not a hosted multi-tenant application.

Current boundaries:

1. No hosted multi-tenant service is included.
2. No production credentials should be committed or pasted into issues.
3. Workbench writes require a per-server token and same-origin checks; reads are available on loopback.
4. The server binds to `127.0.0.1`. Do not expose or reverse-proxy it as an internet service.
5. The local write token is not a remote-user or tenant authentication system.
6. External Hosts, model accounts and image tools have their own access and data-handling policies. Install them separately and share only material you are authorized to process.
7. Native independent review owns an ephemeral read-only Codex session and uses exact result/receipt bindings. It does not introduce a general JSON-signing endpoint or a new credential store.

## Do Not Report As Vulnerabilities

1. Missing cloud authentication for a service that is not shipped.
2. Lack of SaaS tenant isolation in this local-only tool.
3. Documented unavailable fonts, renderers or external Host capabilities, unless they expose a reproducible security flaw.
