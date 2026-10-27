# Deck Master Agent Task Index

This index routes user intent to the rebuilt-core command path (spec 09).
Prefer these entries over guessing file locations or reading historical specs.
Legacy v0.9.x commands map onto this surface per spec 09.6; the full table is
`deck-master legacy-map` and the migration notes live in
[docs/migration-to-rebuilt-core.md](migration-to-rebuilt-core.md).

The content-method entry is the [RC5 increment](specs/content-methods-rc5/README.md).
For inherited work, use the
[RC4 increment](specs/deck-master-next-iteration-20261019/README.md), inherited
contracts then the assigned N1–N6 card. Its
[single candidate ledger](../tests/rebuild/fixtures/history/rc4/iteration-20261019/execution-ledger.json)
records that RC4 candidate's dated verification. RC3, Web UI v4 and rebuild reports preserve their
own date/SHA; read those only for the contract needed by this task.

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
| Submit Host results | `deck-master task accept --project … --task-id … --operation-id … --produced-against … --result result.json` | Use the actual Task protocol/variant and `src/deck_master/resources/contracts/compose-result.v2.schema.json`; old roundtrips remain protocol-specific examples |
| Read exact Task methods | `deck-master methods --project … --task-id … --read` | Frozen ordered manifest and actual bytes/hash; `basis_changed` needs formal reissue, not extra role methods |
| Claim actual Host execution | `deck-master task start --project … --task-id … --execution-ref … --supported-protocol … --capability …` | Repeat each required capability; copy/handoff is not execution, declare only actual support |
| Read negotiated full context | `deck-master capabilities`, then `methods … --read --read-protocol work_context.v2 --body-mode full` | Only methods/create/continue expose these CLI read options; no options means v1; transport is not application evidence |
| Resolve a proposed direction | `deck-master collaboration decision --project … --input decision.json`, then `collaboration adopt-proposal --input adoption.json` | Actual covering decision, exact proposal and current CAS; `collaboration grant` requires actual authorization |
| Retry a settled external call | `deck-master task call allocate --project … --task-id … --count 1` | Allocates a new allowance under the project policy; retain the earlier call outcome and evidence |
| Start a new v3 protocol project | `deck-master create --project-format workbench.v3 --brief … --source … --out …` | Default for new projects; existing projects require explicit migration before formal writes; older cores refuse the forward writer floor |
| Freeze a new-protocol generation input | `deck-master requests freeze --project … --task-id … --input request.json --base-revision … --operation-id …` | First claim with required capabilities; input comes from the task's generation_input |
| Inspect a generation request or attempt | `deck-master requests show --project … --request-id …` / `attempts show --project … --attempt-id …` | Optional --revision; attempt reads its original call allowance and actual observed fields |
| Read the content plan | `deck-master view --project … --content-plan --revision …` | Stored chapters/goals/source versions; absent plans show a labeled derived outline without writing |
| Save version-bound opinions | `deck-master annotations save --project … --input notes.json --base-revision … --operation-id <UUIDv4>` | Saves opinions only; no task dispatch or output invalidation |
| Preview and dispatch a bounded change | `deck-master changes plan --project … --input changes.json`, then `changes commit --plan-id … --base-revision … --operation-id <UUIDv4>` | Exact plan, page/layer targets and call bound; changing the basis requires a new plan |
| Recover an uncertain operation | `deck-master operations show --project … --operation-id …` | Committed ancestry is authoritative; preserve original payload/base/ID/path context; unknown is not absence; [input recovery](../skills/deck-master/references/input-update.md) |
| Trial one page without replacing current | `changes plan/commit` with `mode=trial` and explicit target/stage | [Candidate/Host protocol](../skills/deck-master/references/candidates-and-stages.md); candidate_result capability required |
| Inspect and adopt selected candidates | `candidates list/show/plan/adopt --project …` | Length-one and batch selections share all-or-none CAS; no image call during adoption |
| Plan initial design or restyle selected pages | `styles propose/confirm/plan`, then existing `changes commit/handoff` | [Style recipe protocol](../skills/deck-master/references/style-calibration.md); v3 permits an explicitly authorized first one-or-two-page candidate batch |
| Refine selected icon objects and reuse an adopted sample | `icons inspect/catalog/propose/confirm/plan`, then existing zero-call `changes commit/handoff` | [Icon quality protocol](../skills/deck-master/references/icon-quality.md); faithful redraw first, fixed object scope, icon_repair Host capability |
| Check actual candidate PPT before icon adoption | `candidate-preview request/status --project … --candidate-id …` | Isolated single-page compile/render/readback; engineering check and human visual approval are separate |
| Review original-image expression before SVG | `deck-master review original --project … --page-id … [--candidate-id …]`; `review original-status --project … --page-id … --use expand` | Fixed image/requirements, authenticated independent receipt and explicit graph checks; view/compare/repair_reference are separate from expansion permission |
| Explicitly assemble reviewed current SVGs | `stages assemble --project … --base-revision … --operation-id <UUIDv4>` | Same normal pipeline, all current page visual gates required; final review still required |
| Read a change handoff | `deck-master changes handoff --project … --change-id …` | Core plan and task identities; copy does not claim execution |
| Independent project launcher | `deck-master workbench --registry <file> --no-open` | Separate launcher; optional `--project <absolute-dir>`, `--port 0`, `--stop`; core-only installs report missing v2 UI honestly |
| Workbench service status | `deck-master view --project <dir>` | Existing service status; does not launch a browser |
| Read paged run facts | `deck-master task list --project <dir> --limit 30 --offset 0 --revision <id>` | Optional `--change-id`, `--status`, `--attention`; next page stays on the returned revision; no execution |
| Inspect run recovery links | `deck-master task status --project <dir> --task-id <id> --details --revision <id>` | Core claim time, call facts and existing request/Attempt links; [run recovery](agent-recovery-playbook.md#run-desk-recovery) |
| Read ordered stages | `deck-master view --project <dir> --summary --json` | Lightweight Document projection; add `--revision <id>` to pin history |
| Read one page's lineage | `deck-master view --project <dir> --page-id <id> --lineage --revision <id> --json` | Stored prompts and references only; missing history stays unknown |
| Read full fixed snapshot | `deck-master view --project <dir> --revision <id> --json` | Same `deck_view.v1` as HTTP; obtain IDs with `history list` |
| Delivery readiness | `deck-master final-readiness --project <dir>` | Readiness is a report, not an export |
| Review workbench | `deck-master view --open --project <dir>` | One loopback service per project; reuse is automatic |
| Edit copy | `deck-master edit --project … --page page.json --base-revision … --page-hash … --operation-id …` | Conflicts exit 5, current unchanged |
| Export | `deck-master export --project … --out … --purpose review\|delivery\|engineering --revision <id>` | review is a public reading copy (PPT optional); delivery checks the selected snapshot; engineering is internal recovery |
| Check a proposed PPTX handoff | `deck-master handoff-check --project … --file … --purpose review\|delivery` | Read-only match to current outputs plus page/render/task completeness; exit 3 means blocked |
| Diagnose toolchain | `deck-master doctor --step compose\|blueprint\|compile\|render\|view\|export` | `needs_tool` carries the real reason |
| History / restore | `deck-master history list\|restore --project <dir>` | Restore creates a new revision; call facts are never rolled back. Workbench: `history plan-restore` then `history commit-restore` with a UUIDv4 operation ID |

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
all four managed Skills (`deck-master`, `deck-content`, `deck-design`, `deck-review`) under `$CODEX_HOME/skills` (default
`~/.codex/skills`), following `current/skill/<name>`. All four links are checked before activation;
a conflict keeps the previous release and links unchanged. Registration does
not modify config.toml or other Host skill roots. See
`skills/deck-master/references/installation.md` for candidate installation,
legacy companion migration and rollback.

Both `install activate` and `install rollback` accept
`--transaction-id <canonical-UUIDv4>` for exact recovery. A matching pending
request resumes automatically; a different request reports the pending ID.
Completed explicit replay reports its historical result and independent
current observations. A new rollback without an ID can switch again using
current `previous`; it is not an exact retry. Never lower a project's writer
floor or overwrite an external path to make rollback appear successful.

Inspect an interrupted installation with `install transaction status --prefix …`
(optionally `--transaction-id …`). Resolve that ID with `install transaction
recover --prefix … --transaction-id … --action resume|rollback|abandon`.
`abandon` requires `--reason …`, preserves managed paths, backups and the journal,
and clears only its own verified pending pointer. It leaves current health marked
as conflict; a corrupt journal has no force-unlock path. See the
[installation recovery controls](../skills/deck-master/references/installation.md#inspect-or-resolve-an-interrupted-transaction).

## Workbench content operations

For `content_ops.v1`, use `deck-master content plan --project <dir> --input <json>` then `content commit --plan-id … --base-revision … --operation-id <UUIDv4>`. Direct body/outline edits, reorder/remove, and bounded Host rewrite/merge/split share this transaction. Use `content inputs --input <patch.json>` for the recoverable workbench form of existing input updates, `content source --source-id … --revision …` for exact material versions, and `content lineage --page-id … --revision …` for derived-page provenance. Method: `skills/deck-master/references/input-update.md`.

## Inherited Web UI increment (2026-09-30)

For the inherited UI integration and capability contracts, read
[Web UI v4 baseline](specs/deck-master-webui-v4-20260930/README.md).
A now means UI implementation; B means capability completion. Historical
Flow Quality and W01-W12 records keep their original names and evidence.

## RC3 responsibility and completion

Route explicit planning/writing/speech/content packages to `deck-content`,
visual plans and bounded sample pages to `deck-design`, strict read-only
project/external-file review to `deck-review`, and full-deck coordination or
cross-role continuation to `deck-master`. See `skills/RESOLVER.md` and the
single shared `references/collaboration-routing.md` method.

Named, natural-language, Master handoff and recovery paths use the same Runtime
and current request/scope. `method_resources.read_skill_methods` reads actual
installed bytes, task methods and current completion without dispatching work.
Returned method bytes and actual Host application are separate evidence.

New Tasks freeze their ordered `method_manifest`; the N3 resolver is the sole
method list. Old Tasks use their provable frozen RC3 selector/digest without
grafting new Review defaults. A changed/missing basis stays explicit and an
active Task needs formal Runtime retirement/reissue after outstanding calls
are settled. New method/policy writes atomically require `rc4-content.v1`;
historical reads and exact accepted-result replay do not upgrade old facts.

For v2, full is the default and permits explicit re-fetch. Manifest has
`context_ready=false`. Delta omits only exact bytes retrievable in an actually
observed Host session/context generation; the CLI has no such observation and
therefore stays cold/full. Preserve all sources, Page/notes, limitations,
original image refs/dimensions and physical constraints. Transmission or cache
offers do not establish reading, application, review independence or approval.

`content_only` + `plan_only|write_only|speech_only|content_full` each finish with
their requested artifacts. Use `completion.state/outputs/checks/missing` instead
of project-wide `work_complete`; completed content does not start design or PPT.
Design returns a scheme or bounded candidate; Review returns a strict read-only
report outside the source, with gaps explicit. Only a separate explicit import
writes that report through current CAS. A Skill name never upgrades identity.

The default create is `workbench.v3`/rc3 with a real instruction source and no
production grant. Imported confirmed drafts preserve their actual source and
mapping; old formats need migration describe/apply before formal writes.
Selected historical exports are judged against their actual file/notes and
current control, including current pause/revoke/review facts.

## RC5 method selection

New dispatch through `create`, `continue` and `inputs update` accepts repeated
`--selected-resource-id <catalog-id>`. The matching Python service input is
`selected_resource_ids`; collaboration API `continue` accepts the same bounded
list. IDs must be registered and applicable to the final role, phase and scope.
For example, an argument-phase dispatch can select `content-m04` and
`case-e04-walkthrough`; dependencies include the example's input and after text.
This does not authorize producing a new page, changing a confirmed direction,
or using synthetic example values as project evidence.

Independent reads use `methods --kind compose --phase argument --read
--selected-resource-id content-m04`. Existing Task reads must omit selection:
their ordered manifest is immutable. Finish or formally retire/reissue pending
work before selecting resources for a new dispatch. See the
[RC5 implementation specification](specs/content-methods-rc5/README.md).
