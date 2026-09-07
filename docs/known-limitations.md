# Known Limitations

Deck Master is currently v0.9.14-preview.4 / Technical Preview (agent-operable).

Version mapping:

- GitHub release label: `v0.9.14-preview.4`
- Python package version: `0.9.14a4`
- Suite / Skill OS contract version: `1.1.0` (from `skills/stage-contracts.json`, tracked in `docs/releases/v1.1.0-release-notes.md`). This is a separate axis from the package version: it tracks the skill/handoff contract maturity, not the installable release. `docs/releases/v1.1.0-release-notes.md` documents that contract release, not a package 1.1.0.
- Production readiness: not claimed

The high-density builder is included as an installable preview capability. Its
fresh provider smoke and six-page external icon evidence remain release gates;
the repository keeps those gates fail-closed when private artifacts are not
available.

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

## SC-1 Solution Core Iteration (2026-09-07)

The SC-1 iteration landed the managed capability lock, hosted backend/library
resolution, full material reading, gap-driven research, the solution model and
public narrative, Page Package production and standard-build consumption,
diagram views, semantic review v2 (six-dimension rubric) as a required
production gate, action envelopes, and the acceptance-rate metric fix. It did
NOT close:

1. **Real standard backend smoke** — the managed PPT Master install exists
   (`backend install-managed`), but until a real backend is bound and verified,
   real two-page PPTX build/render acceptance (A-03/P-01) stays blocked. No
   fixture substitution is performed.
2. **Real paired UAT** — the three-sample × two-run paired comparison (E-02 to
   E-06) requires real customer samples, which are not stored in the repo.
   Pairing metadata and manual-effort records are accepted by the harness, but
   no outcome claim is made.
3. **Host capability wording** — only codex / claude-code / hermes / custom
   targets are supported; unknown hosts are rejected rather than claimed.
4. **Typed question triggers** — the stage-contracts forcing-question table
   still uses string triggers; typed trigger/answer_schema refactor is
   registered as an open deviation.

Engineering state and evidence: `docs/specs/sc1-solution-core-independence/implementation/`.
