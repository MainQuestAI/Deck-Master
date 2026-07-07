# Security Policy

## Supported Status

Deck Master is a public Technical Preview. Security fixes are handled on a best-effort basis until the first formal release candidate.

## Reporting

Please report security concerns through a private GitHub security advisory when available. If that is not available, open a GitHub issue with a high-level description and avoid posting exploit details or sensitive data.

## Current Threat Boundary

Deck Master is a local-first developer tool. The M1 Technical Preview focuses on local fixture demo, Review Desk preview, packaging, and capability transparency.

Current boundaries:

1. No hosted multi-tenant service is included.
2. No production credentials should be committed or pasted into issues.
3. Review Desk write operations use a per-server local write token plus same-origin guard.
4. Review Desk binds to loopback hosts by default. Non-loopback preview requires explicit `--allow-remote-preview` and is only for trusted local-network demos.
5. The Review Desk write token is not a network authentication boundary because any browser that can load the page can read it.
6. Production backend readiness depends on configured local or open-source companion capabilities.

## Do Not Report As Vulnerabilities

1. Missing cloud authentication for a service that is not shipped.
2. Lack of SaaS tenant isolation in the local-only preview.
3. Fixture demo limitations already documented in Known Limitations.
