# Known Limitations

Deck Master is currently v0.9.14-preview.2 / Technical Preview (agent-operable).

Version mapping:

- GitHub release label: `v0.9.14-preview.2`
- Python package version: `0.9.14a2`
- Suite / Skill OS contract version: `1.1.0` (from `skills/stage-contracts.json`, tracked in `docs/releases/v1.1.0-release-notes.md`). This is a separate axis from the package version: it tracks the skill/handoff contract maturity, not the installable release. `docs/releases/v1.1.0-release-notes.md` documents that contract release, not a package 1.1.0.
- Production readiness: not claimed

## M1 Technical Preview

M1 guarantees a local fixture demo and Review Desk preview path. It does not guarantee a full production deck build unless production companion backends are configured and verified.

Current M1 boundaries:

1. Fixture demo is the default first-run path.
2. Production backend status must be checked through `setup-status`, `suite-status`, `agent-doctor`, or `backend status`.
3. If the `ppt-master` production backend is not configured and verified, production export commands should block instead of reporting ready. `ppt-deck-pro-max` is a page-production Skill in the suite, not a separately bound production backend.
4. Review Desk write operations use a local write token plus same-origin guard. Non-loopback preview hosts are disabled by default and require explicit `--allow-remote-preview`.
5. Browser smoke depends on local Playwright/browser availability.
6. The public demo uses synthetic retail transformation content.

## M2 RC Requirements

Before formal RC, Deck Master must also close:

1. Production external dependency handling.
2. Review Desk full design-system alignment.
3. Release tree install, verification, and rollback evidence.
4. Production deployment hardening beyond the local Review Desk write guard.
