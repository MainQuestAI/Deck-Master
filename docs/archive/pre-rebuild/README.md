# Pre-Rebuild Archive

History of the v0.9.x Run OS and its retirement. Nothing here is current
implementation truth. Start with the [current documentation index](../../README.md);
the [rebuild specification](../../specs/deck-master-rebuild-v1/) is an inherited
engineering baseline, not a claim that later increments are absent.
Current entry point and old-command mapping:
[docs/migration-to-rebuilt-core.md](../../migration-to-rebuilt-core.md);
`deck-master legacy-map` prints the mapping table.

## Index

- `contracts/` — the 58 legacy JSON contracts (active schema source is now
  `src/deck_master/resources/contracts/`).
- `docs/` — old-OS living docs and dated records (quick start, user guide,
  release notes, QA/planning/integration/UAT archives, archived spec packs
  with their ARCHIVED.md markers).
- `specs-legacy/` — pre-rebuild spec directories moved from `docs/specs/`.
- `skill-playbooks/` — the old-OS deck-master playbooks and agent instructions
  (current roles are listed in [the four-Skill resolver](../../../skills/RESOLVER.md)).
- `test-fixtures/fixtures/` — fixtures of the retired test suite.
- `ci-legacy.yml` — the retired GitHub workflow (superseded by
  `.github/workflows/rebuild.yml`).
- `product-capability-manifest.v09.json` — the v0.9.x capability manifest.

## Running an Old Run

Old runs are not migrated in place. Use a pinned v0.9.x release for a run
that still matters, or convert its full draft via
`deck-master import legacy` (read-only). See the migration note for details.

## Retirement Record

- Old source tree (`scripts/`, 177 files): deleted per
  `docs/specs/deck-master-rebuild-v1/inventory/old-files.csv`; per-path
  reference evidence in [reference scan](../../specs/deck-master-rebuild-v1/inventory/reference-scan.md).
- Old tests (`tests/*.py`, 123 entries (122 test files + tests/__init__.py) + fixtures): disposition rationale in
  [test disposition](../../specs/deck-master-rebuild-v1/inventory/old-tests-disposition.md) (AC-L06).
