# AGENTS.md

Deck Master is an Agent-operable Solution Deck Run OS. This file is the
first entrypoint for Codex, Claude Code, OpenCode, and other local coding
agents working in this repository.

## Agent First Read Order

1. `AGENTS.md` for project rules, task routing, and safety boundaries.
2. `docs/agent-task-index.md` for user-intent to command routing.
3. `docs/agent-recovery-playbook.md` for blocked-state repair decisions.
4. `docs/contracts/` for runtime JSON contracts and schema truth.

## Project Truth

- Runtime contracts: `docs/contracts/`.
- Public capability manifest: `product-capability-manifest.json`.
- Skill task schemas: `skills/deck-master/schemas/`.
- Source checkout CLI entrypoint: `python3 scripts/deck_master.py`.
- Editable install uses Python 3.11 or 3.12 in a venv; after
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
- `next-step` points to an external Agent handoff waiting state.
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
