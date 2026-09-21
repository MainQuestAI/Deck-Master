# Deck Master Agent Task Index

This index routes user intent to the rebuilt-core command path (spec 09).
Prefer these entries over guessing file locations or reading historical specs.
Legacy v0.9.x commands map onto this surface per spec 09.6; the full table is
`deck-master legacy-map` and the migration notes live in
[docs/migration-to-rebuilt-core.md](migration-to-rebuilt-core.md).

## Task Scope

Choose the request before loading a production playbook. Existing directions,
page selections, and authorization remain usable; only ask about a missing
decision that affects this task.

| Intent | Routing command | Detail to read |
| --- | --- | --- |
| New deck from material | `deck-master create --brief … --source … --out …` | `skills/deck-master/references/source-reading.md`、`content-methods.md`、`content-examples.md` |
| Complete draft at hand | `deck-master import-draft --project <dir> --input draft.json` (or `create --draft …`) | Page v2 shape; unknown fields raise, never drop |
| Continue / next Host batch | `deck-master continue --project <dir>` | Returns stable `pending_tasks`; exit 3 = awaiting host/tool, not failure |
| Submit Host results | `deck-master task accept --project … --task-id … --operation-id … --produced-against … --result result.json` | Envelope shape: `docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/README.md` |
| Read-only status | `deck-master view --project <dir>` or `deck-master next-step --project <dir>` | Same `deck_view.v1` projection everywhere |
| Delivery readiness | `deck-master final-readiness --project <dir>` | Readiness is a report, not an export |
| Review workbench | `deck-master view --open --project <dir>` | One loopback service per project; reuse is automatic |
| Edit copy | `deck-master edit --project … --page page.json --base-revision … --page-hash … --operation-id …` | Conflicts exit 5, current unchanged |
| Export | `deck-master export --project … --out … --purpose review\|delivery` | review ships unfinished decks with the real unresolved list; delivery requires passing current checks |
| Diagnose toolchain | `deck-master doctor --step compose\|blueprint\|compile\|render\|view\|export` | `needs_tool` carries the real reason |
| History / restore | `deck-master history list\|restore --project <dir>` | Restore creates a new revision; call facts are never rolled back |

## Old Runs And Old Commands

- A legacy run directory (`preview_manifest.json` / `run.json` markers, no
  `.deckmaster/current.json`) passed to any new write command is refused with
  `legacy_run_format` (exit 2). New commands never migrate or initialise an
  old run in place.
- Old command names (`next-step`, `agent-doctor`, `final-readiness`,
  `import-plan`, `build …`) either execute the new semantics or return a
  controlled guidance/retirement JSON. Nothing re-enters
  `scripts/deck_master.py`.
- For a human or Agent holding an old v0.9.x run: pin the old release for that
  run, or convert its full draft per the migration notes — never mix writers
  on one run.

## Project Skill Installation

After `python -m pip install -e ".[dev]"` the `deck-master` console command is
the only entry; no suite linking, skill symlink installation, or first-run
setup step is required. See `skills/deck-master/references/installation.md`
for release-candidate activation and rollback of installed trees.
