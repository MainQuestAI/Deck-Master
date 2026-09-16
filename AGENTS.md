# AGENTS.md

Deck Master is an Agent-operable Solution Deck Run OS. This file is the
first entrypoint for Codex, Claude Code, OpenCode, and other local coding
agents working in this repository.

## Agent First Read Order

1. `AGENTS.md` for project rules, task routing, and safety boundaries.
2. `docs/agent-task-index.md` for user-intent to command routing.
3. `docs/agent-recovery-playbook.md` for blocked-state repair decisions.
4. `docs/contracts/` for runtime JSON contracts and schema truth.
5. For mainline rebuild work: `docs/specs/deck-master-rebuild-v1/task-cards/README.md`
   first, then `task-cards/<T-NN>.md` and `inventory/baseline-record.md`.

## Rebuild Baseline (v1.1)

The active implementation baseline for the mainline rebuild is
`docs/specs/deck-master-rebuild-v1/` (spec pack v1.1). Rules for this effort:

- New core code lives in `src/deck_master/` (src layout). It must never import
  the old namespaces `runtime`, `workflow`, `high_density`, `preview`, or
  `build` (the old scripts tree), and must not borrow implementations through
  `sys.path` inserts. Enforced by `tests/rebuild/test_package_boundary.py`.
- Execute work one task card at a time from `task-cards/` (25 cards, 90 ACs,
  exactly one final owner per AC). Early `min` slices may ship before a card
  closes, but never omit original-image comparison, immutable originals,
  atomic writes, or cancel/late-result protection.
- Extraction sources are fixed per file in `inventory/baseline-record.md`
  (B0 `2a866cf…`, K0 `2c5a4c50…`). Migrate function by function; never merge
  or cherry-pick PR31/K0 wholesale.
- T01 froze the per-path disposition baseline in `inventory/old-files.csv`.
  No old file is deleted before T24 verifies behavior migration and reference
  zeroing. Never delete user runs, source material, third-party skills, fonts,
  or historical artifacts. Do not reset the working tree or run
  `git clean -fdx`.

## Project Truth

- Runtime contracts: `docs/contracts/`.
- Public capability manifest: `product-capability-manifest.json`.
- Skill task schemas: `skills/deck-master/schemas/`.
- Source checkout CLI entrypoint: `python3 scripts/deck_master.py`.
- Editable install uses Python 3.12 by default. Python 3.11 and 3.12 are
  supported for preview commands; real PPT Library v2 integration requires
  Python 3.12+. After
  `python -m pip install -e ".[dev]"`, installed command is `deck-master`.
- Technical Preview demo: `scripts/demo.sh` plus `preview-gate`.
- Release verification: `release-build` plus `release-smoke`.

Do not infer state from prose when a JSON command exists. Prefer these
machine-readable commands:

```bash
python3 scripts/deck_master.py agent-doctor --mode preview --output json
python3 scripts/deck_master.py agent-doctor --mode production --output json
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py next-step --run-dir <run_dir>
python3 scripts/deck_master.py preview-gate --run-dir <run_dir> --expect-unconfigured-backend-ok
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

## Task Routing

- New fixture demo or public preview: run `bash scripts/demo.sh`, then
  `preview-gate`.
- Continue an existing run: run `next-step` first, then execute only the
  returned `next_command`.
- Diagnose readiness: run `agent-doctor`; use `preview` for public demo and
  `production` for production backend checks.
- Check client export: run `final-readiness`; do not export when it is blocked.
- Build release tree: run `release-build` to a fresh output path, then
  `release-smoke --release-root <that_path>`.
- Repair blocked state: read `docs/agent-recovery-playbook.md` and follow the
  matching blocked code or runtime stage.

## Forbidden Actions

- Do not report production backend readiness unless JSON status says ready.
- Do not use fixture fallback in production or benchmark mode.
- Do not write placeholder artifacts into production runs.
- Do not commit generated runs, private benchmark sources, local env files,
  tokens, caches, or raw customer material.
- Do not expose absolute local paths, private customer names, or internal
  execution commands in customer-visible artifacts.
- Do not overwrite user files unless a command explicitly supports `--force`
  and the user asked for replacement.

## Stop And Report

Stop and report when:

- `agent-doctor --mode production` returns `blocked`.
- `suite-status` reports a required skill or capability as missing.
- `next-step` requires an output that the current Agent cannot create with its
  available tools, or requires missing material or a user decision. When the
  current Agent is authorized and can write the declared `output_ref`, complete
  the handoff and resume the run.
- `final-readiness` returns blockers.
- A contract schema mismatch appears and no migration command is documented.
- A command would require private backend binding or customer material not
  present in the repository.

## UI And Design Work

For visual or UI changes, read `DESIGN.md` before editing. Keep the locked
direction: serious tool feel, Satoshi/Geist/IBM Plex Mono stack, cold ink
surface with amber-copper action accent, hairline solid panels, no glass
panels, restrained radius, and no decorative gradients. The Review Desk IA
source is `docs/2026-06-21-web-ui-ia-v1.md`; design QA should flag deviations.
