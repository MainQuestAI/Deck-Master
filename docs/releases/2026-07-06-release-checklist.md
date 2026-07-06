# 2026-07-06 Open Source Readiness Release Checklist

Status: M1 validated locally
Target: M1 public Technical Preview

## Decisions

| ID | Decision | Status |
|---|---|---|
| D0 | M1 is public Technical Preview | Accepted |
| D1 | License is Apache-2.0 | Accepted |
| D2 | Current Deck Master repository is open-source as a whole | Accepted |
| D2.1 | M1 proves independent first-run value through Review Desk and fixture demo | Accepted |
| D3 | M1 requires minimum DESIGN.md Review Desk compliance | Accepted |
| D4 | External entry docs are English-first | Accepted |
| D5 | `pyproject.toml` is package version source; skill manifest carries suite version | Accepted |
| D6 | M1 support is best-effort Technical Preview | Accepted |
| D7 | Contributions use DCO sign-off | Accepted |

## M1 Go Conditions

- [x] `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `THIRD_PARTY_NOTICES.md`, and `CHANGELOG.md` exist.
- [x] `python -m pip install -e ".[dev]"` succeeds in a clean environment.
- [x] README and Quick Start explain Technical Preview, fixture demo, Review Desk, License, and Known Limitations.
- [x] Fixture demo produces at least 10 preview pages.
- [x] `preview-gate` passes without a configured production backend.
- [x] Unconfigured production backend does not report `bound_verified`.
- [x] Review Desk M1 design scan passes.
- [x] Git does not track `.gstack/qa-reports`.
- [x] Release tree includes README, LICENSE, and Known Limitations.

## M2 RC Conditions

- [ ] M1 all green.
- [ ] Production external dependency handling is closed.
- [ ] `rc-gate --skip-browser-smoke` passes.
- [ ] `rc-gate --require-browser-smoke` passes.
- [ ] Localhost write operations have token or origin checks.
- [ ] GitHub issue/PR templates, CODEOWNERS, ROADMAP, and dependabot are present.
