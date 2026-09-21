# Migration to the Rebuilt Core

The rebuilt core (spec pack v1.1) replaces the v0.9.x Run OS. This note is the
single place that explains what moved, what retired, and how to treat old
runs. Nothing here deletes files; retirement and cleanup follow task T24.

## One Command Surface

The only entry is the rebuilt CLI:

- Installed: `deck-master …` (console entry `deck_master.cli:main`).
- Source checkout: `python -m deck_master …`.
- `python3 scripts/deck_master.py` is legacy. New commands never import or
  exec it.

`deck-master legacy-map` prints the full mapping table. Summary (spec 09.6):

| Class | Old entries | Behaviour |
| --- | --- | --- |
| Alias (runs new semantics) | `agent-doctor`, `next-step`, `run-state`, `final-readiness`, `import-plan`, `product-capability-manifest`, `doctor`, `export` | Executes the rebuilt flow; read-only entries return the same `deck_view.v1` projection |
| Alias (legacy build subcommands) | `build prepare`, `build status` | Read-only status derived from the current ProjectView; `build run` points at `deck --project <dir>` |
| Guidance (exit 2, typed JSON) | `start-conversation`, `plan`, `build-brief`, `build-claim-map`, `autoplan`, `search-library`, `decide-sourcing`, `library-status`, `import-library-selection`, `record-library-feedback`, `uat-ppt-library`, `validate-ppt-library-result`, `suite-status`, `suite-install`, `suite-repair`, `setup`, `setup-status` | Points at the correct new command; never silently generates a rule-based draft or requires a slide library |
| Retired (exit 2, typed JSON) | `backend`, `rc-gate`, `preview-gate`, `release-*`, `suite-*`, `benchmark-*`, `uat-*`, `render`, `workflow`, `init-*`, `delivery`, `opportunity`, `connector`, generation/handoff/import-preview commands, `install-skill`/`uninstall-skill`, … | Refuses explicitly; not a prerequisite for any new task |

## What Is No Longer Required

- No PPT Master backend binding or SHA certification.
- No PPT Library installation or workspace/template bootstrap.
- No first-run `setup`; a plain material directory is enough:
  `deck-master create --brief … --source … --out …`.

Renderer and font gaps are reported per doctor step as `needs_tool` with the
real reason.

## Old Runs

A v0.9.x run directory keeps its bytes. New write commands recognise the old
shape (`preview_manifest.json` / `run.json` markers, no `.deckmaster`) and
refuse with `legacy_run_format`; they never migrate or initialise it in place.

Options for an old run that still matters:

1. **Pin the old release** for that run and keep operating it with the legacy
   toolchain. Do not mix the new CLI writers into the same run.
2. **Convert its full draft**: map the v1 page package to Page v2 per spec
   12.2 (customer_visible blocks, explicit page order, separated speaker
   notes), then `deck-master import-draft --project <new> --input draft.json`.
   Unknown fields must be mapped explicitly — they are rejected, never
   silently dropped. Old artifact bytes stay in the old run as history.

## Status Semantics

- Exit 0 / completed tasks are engineering facts, never professional approval.
- `export --purpose review` ships unfinished decks with the real unresolved
  list; `--purpose delivery` requires passing current checks (and, when the
  policy demands it, a non-failing professional/human review on the current
  output).
- PPTX output is editable shapes and text; tables/charts are not Office-native
  data objects.

## Document Map

- Routing: [docs/agent-task-index.md](agent-task-index.md)
- Blocked states: [docs/agent-recovery-playbook.md](agent-recovery-playbook.md)
- Contracts: [docs/contracts/](contracts/)
- Rebuild baseline: [docs/specs/deck-master-rebuild-v1/](specs/deck-master-rebuild-v1/)
- Historical spec packs under `docs/` are archived references, not current
  truth.
