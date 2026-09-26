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
| Change audience, decisions, purpose or materials | `deck-master inputs show --project <dir>` then `inputs update --project … --patch … --base-revision … --operation-id …` | `skills/deck-master/references/input-update.md`; only changed pages go in `content_update` |
| Submit Host results | `deck-master task accept --project … --task-id … --operation-id … --produced-against … --result result.json` | Envelope shape: `docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/README.md` |
| Retry a settled external call | `deck-master task call allocate --project … --task-id … --count 1` | Allocates a new allowance under the project policy; retain the earlier call outcome and evidence |
| Start a new v3 protocol project | `deck-master create --project-format workbench.v3 --brief … --source … --out …` | Explicit opt-in; old projects and the default UI do not change; older cores refuse its pointer format |
| Freeze a new-protocol generation input | `deck-master requests freeze --project … --task-id … --input request.json --base-revision … --operation-id …` | First claim with required capabilities; input comes from the task's generation_input |
| Inspect a generation request or attempt | `deck-master requests show --project … --request-id …` / `attempts show --project … --attempt-id …` | Optional --revision; attempt reads its original call allowance and actual observed fields |
| Workbench service status | `deck-master view --project <dir>` | Existing service status; does not launch a browser |
| Read ordered stages | `deck-master view --project <dir> --summary --json` | Lightweight Document projection; add `--revision <id>` to pin history |
| Read one page's lineage | `deck-master view --project <dir> --page-id <id> --lineage --revision <id> --json` | Stored prompts and references only; missing history stays unknown |
| Read full fixed snapshot | `deck-master view --project <dir> --revision <id> --json` | Same `deck_view.v1` as HTTP; obtain IDs with `history list` |
| Delivery readiness | `deck-master final-readiness --project <dir>` | Readiness is a report, not an export |
| Review workbench | `deck-master view --open --project <dir>` | One loopback service per project; reuse is automatic |
| Edit copy | `deck-master edit --project … --page page.json --base-revision … --page-hash … --operation-id …` | Conflicts exit 5, current unchanged |
| Export | `deck-master export --project … --out … --purpose review\|delivery` | review ships unfinished decks with the real unresolved list; delivery requires passing current checks |
| Check a proposed PPTX handoff | `deck-master handoff-check --project … --file … --purpose review\|delivery` | Read-only match to current outputs plus page/render/task completeness; exit 3 means blocked |
| Diagnose toolchain | `deck-master doctor --step compose\|blueprint\|compile\|render\|view\|export` | `needs_tool` carries the real reason |
| History / restore | `deck-master history list\|restore --project <dir>` | Restore creates a new revision; call facts are never rolled back |

`continue` now completes the current page's SVG compiler check, preview, and
`review_stage=page_visual` review before dispatching the next page. The page
review covers `blueprint_content`, `blueprint_fidelity`, and `readability`.
After all pages pass, `continue` compiles the full PPT and dispatches the
six-dimension `review_stage=final` review. Old reviews without this field are
final reviews.

## Old Runs And Old Commands

- A legacy run directory (`preview_manifest.json` / `run.json` markers, no
  `.deckmaster/current.json`) passed to any new write command is refused with
  `legacy_run_format` (exit 2). New commands never migrate or initialise an
  old run in place.
- Old command names (`next-step`, `agent-doctor`, `final-readiness`,
  `import-plan`, `build …`) either execute the new semantics or return a
  controlled guidance/retirement JSON. Nothing re-enters
  the retired legacy CLI entry.
- For a human or Agent holding an old v0.9.x run: pin the old release for that
  run, or convert its full draft per the migration notes — never mix writers
  on one run.

## Project Skill Installation

After `python -m pip install -e ".[dev]"` the `deck-master` console command is
the only CLI entry. For a release used from Codex, `install activate` registers
one managed `deck-master` Skill under `$CODEX_HOME/skills` (default
`~/.codex/skills`), following `current/skill/deck-master`. Registration does
not modify config.toml or other Host skill roots. See
`skills/deck-master/references/installation.md` for candidate installation,
legacy companion migration and rollback.
