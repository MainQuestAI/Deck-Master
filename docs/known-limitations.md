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

M1 guarantees a local fixture demo and Review Desk preview path. SC-1.1 adds a built-in native production route; actual task readiness and final delivery gates remain required.

Current M1 boundaries:

1. Fixture demo is the default first-run path.
2. Production backend status must be checked through `setup-status`, `suite-status`, `agent-doctor`, or `backend status`.
3. For an existing or explicitly selected legacy route, a missing `ppt-master` backend blocks that route. Native runs do not require that binding. `ppt-deck-pro-max` is a page-production Skill in the suite, not a separately bound production backend.
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

1. **Legacy standard backend smoke (superseded for the default by SC-1.1)** — the managed PPT Master install exists
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


## SC-1.1 Native Deck Core (2026-09-07)

Landed: the built-in native compile kernel (single implementation extracted
from the high-density builder), default native routing, library_mode=none as
a first-class mode, a real native runtime probe, the native engine adapter
(real two-page compile+readback through native_pptx), precise semantic-gate
matching, and atomic revision commits with failure-budget accounting.

Current engineering state remains `in_progress`:

- Real host ImageGen outputs, ten-page native compilation/render/readback,
  seven-class SVG/PPTX parity, explicit run migration and isolated installation
  have been exercised during PR31. Their evidence must be bound to the final
  candidate; earlier successful runs are not final-SHA acceptance.
- Human visual review and final-file approval remain pending. Auxiliary model
  scores do not replace that review. An exhausted page repair budget requires
  an explicit increase before further attempts.
- Desktop editing has been exercised, but its saved result still requires
  the final visual check. No cross-platform PowerPoint compatibility is inferred
  from LibreOffice results.
- Real customer paired outcomes are excluded from this engineering round and
  remain `outcome_pending`. No `accepted` claim is made.

The formal installed launcher protects newer run formats after software rollback.
Directly executing an old source checkout bypasses that launcher; it is not a
supported way to write newer run data.
