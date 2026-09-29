# Deck Master Agent Recovery Playbook

Use this playbook when a rebuilt-core command returns a non-zero exit, a
`blocked`/`fail` status, or an unexpected state. Do not repair by editing
project objects by hand; every fix goes through the CLI/service layer.

Exit codes (spec 09.3): 0 action done (read `status` for deck state), 2 invalid
input, 3 awaiting host/tool, 4 execution failure, 5 conflict/late result with
current unchanged.

## Legacy Run Format

- Detect by: exit 2 with `error.code == "legacy_run_format"`.
- Meaning: the path is an old v0.9.x run (preview/run markers, no new
  Document pointer).
- Auto action: none in place. Read
  [docs/migration-to-rebuilt-core.md](migration-to-rebuilt-core.md); convert a
  full draft and `import-draft`, or pin the old release for that run.
- Stop when: the user has not chosen conversion vs pinning.

## Renderer Or Font Missing

- Detect by: `doctor --step render|compile` returns `status == "needs_tool"`,
  or `continue` returns `status == "needs_tool"`.
- Auto action: install the named tool (`soffice`, `pdftoppm`, `rsvg-convert`,
  `fc-match`) or point `DECK_MASTER_<TOOL>` at it, then re-run the same step.
- Never fall back to fixtures outside demo material.

## Conflict / Late Result

- Detect by: exit 5 or `error.code == "conflict"`.
- Auto action: re-read the current project (`view` / `continue`), rebase the
  payload (fresh `page_hash` / `produced_against`), retry with a new
  `operation_id` for changed content. The late payload never overwrites.
- Cancel-first wins: a result after `task cancel` is settled for call facts
  and refused for content (`late result after cancellation`).

## Task Accept Response Lost

Retry the exact same task_id, operation_id, produced_against and result envelope.
For new successful adoptions, the request digest and stable result are stored
in the same Document commit as the completed Task and result_refs. A missing
or damaged operations cache is rebuilt from committed history; orphan revision
files never count as applied operations.

`already_applied.revision_id` names the original adoption, while
`current_revision_id` names the current project version. These may differ after
later work. `operation_result` is the original core result. Replay does not
restore the old version or dispatch historical pending tasks.

If `journal_warning.code == receipt_cache_unavailable`, adoption is committed
but the derived cache could not be saved. Keep the same payload and operation
ID when retrying after storage is writable. Changed payloads or dependency
bindings conflict. Old completed tasks without a receipt and without their
journal remain unresolved; do not invent a digest or edit storage by hand.

## Generation Protocol

New `generation.v1` blueprint tasks require explicit Host protocol/capability
declarations, an immutable request and a begun attempt. These are enabled only
for new projects created with `--project-format workbench.v3`; no old project
is migrated in place. New projects use `deckmaster-current.v2` so old writers
refuse them before changing current. Use the matching core to read or continue;
an older UI may be used with that core, but do not downgrade the writer.

- `host_protocol_unsupported` (CLI 2 / HTTP 422): read the current public Skill
  and declare the required capabilities. A Host name alone is not support.
- `generation_request_required` / `generation_attempt_required` (2 / 422):
  use the IDs returned by requests freeze and the same call begin.
- `generation_binding_conflict` / `generation_input_mismatch` (5 / 409):
  inspect frozen and actual input. New input needs a new request; the same
  allowance cannot be resent or relabeled. Consumed facts are retained.
- `generation_evidence_incomplete` / `tool_observation_unavailable` (2 / 422):
  inspect the real tool completion and its exposed fields. The current Codex
  adapter verifies native prompt/PNG/transparent-background fields. Its narrow
  direct literal-call profile also proves reference arguments were omitted.
  Nonempty references require a direct literal referenced_image_paths call,
  same-project immutable object files unchanged since call start, and the
  same-call PNG return. Other wrappers, semantic roles besides reference,
  model/seed and unrecorded parameters remain unverified. Never fill them from defaults or a self-reported observer label.
- `generation_object_not_found` (2 / 404): select a request/attempt referenced
  by the task in the chosen committed revision; orphan objects are not history.
- `operation_payload_conflict` (5 / 409): reuse the original freeze payload
  or use a new operation ID for genuinely different input.

An attempt's call state comes from Task.call_allowances. Unknown blocks new
calls; it is not not_sent. Native receipts may enrich a consumed Host report
without creating a second allowance or erasing the earlier observation.

## Review Blocked

- Detect by: `final-readiness` reports `review_status != "pass"`, or
  `export --purpose delivery` refuses with the unresolved dimensions list.
- A `continue` result with `next_action == "repair_page_visual"` addresses only
  the current page. Rebuild that Page/SVG, regenerate its preview, and submit a
  new page review with evidence closing the original finding. If it returns
  `repair_no_progress`, inspect the unchanged Page/SVG and the named finding
  before retrying. An unreviewed current page cannot dispatch the next page.
- Auto action: fix the named Page/SVG layer, then re-run the affected checks.
  Read findings from `deck-master view --project <dir> --revision <id>` (findings carry
  page/element addressing).
- A failing professional review blocks delivery even when all engineering
  checks pass; stopping a no-progress repair loop is not a pass.

## Schema Or Envelope Mismatch

- Detect by: exit 2 with a field path in `error.message`.
- Auto action: fix the named field; unknown envelope fields are rejected, not
  ignored. Page v2 normalization raises the exact pointer needing a decision.
- Stop when: a contract mismatch has no documented migration.

## Workbench Unavailable

- Detect by: `view_status == "unavailable"` or `review_url == null`.
- Auto action: the payload `findings` carry the real reason (no Document,
  service start failure, no browser). The local URL is still printed when a
  service is running; no browser does not lose the address.

## Launcher And Personal Draft Recovery

`deck-master workbench` checks role, instance, project/registry identity and
loaded code version before service reuse. `port_conflict` never takes over
another listener: choose `--port 0` or explicitly stop the matching service.
`--stop` affects only the selected launcher/project and keeps business data.
`core_ready_ui_unavailable` means the core runs but the v2 UI is not installed;
use the explicit project `--ui legacy` until the frontend is available.

A `local_state_conflict` is a personal draft ETag/target conflict. Retain the
local buffer, read the saved draft, and keep an independent draft when needed.
Only a project ACK promises automatic recovery on a new port. A recovery file
is validated data and never a command to adopt or replay a pending operation.
Do not delete the journal to resolve a business conflict; it does not change
Document revision, content identity, or call facts.

## History And Restore

- Restore always creates a NEW revision; task call facts (consumed/unknown/
  cancelled) and the user stop state are never rolled back. Use
  `deck-master history list --project <dir>` to pick a revision, then
  `history restore` with the current base revision.

## Workbench Snapshot Reads

`view --content-plan` and `GET /api/content-plan` follow the same fixed revision
rules. `recorded` means the plan was saved, not that its claims passed review;
`derived` is a Page-title outline and is never persisted as a historical plan.
`basis_changed` retains the original Page/source links for comparison.
`content_plan_invalid` rejects compose adoption for missing goals, invalid
source versions/locators or missing basis. Re-read the work order's source
contract and use explicit unresolved facts where material is missing.
`content_plan_unreadable` is local to that detail; other pages remain readable.

New workbench projects require the `content-plan.v1` writer boundary and
`compose.v1` Host capabilities. Existing old-protocol tasks remain compatible;
never make an old project new-format by editing its pointer. History restore
restores the selected plan reference while keeping the current writer boundary.

`view --summary` and `view --page-id <id> --lineage` read current by default.
Add `--revision <id>` to pin the Document, page slots, tasks and stored prompts.
Get valid IDs with `deck-master history list --project <dir>`. Reads never
restore a revision, start Host work or save project changes. Read options
cannot combine with `--open`; `--lineage` requires `--page-id`.

- `invalid_revision` (HTTP 400 / CLI 2): provide one valid identifier, not a
  path. Empty or repeated HTTP revision arguments are rejected.
- `revision_not_found` / `revision_unavailable` (HTTP 404 / CLI 2): the
  snapshot must be readable, belong to this project and be reachable through
  the committed parent chain. Copied files, orphans and symlinks do not count.
  Read the project's available history. Never silently fall back to current.
- `page_not_found` (HTTP 404 / CLI 2): choose a page present in that snapshot.
- `project_unavailable` (HTTP 404 or 422 / CLI 2): check the selected project
  and restore missing/corrupt storage from a verified copy; do not rewrite
  current.json or content-addressed objects by hand.
- `object_unreadable` within a successful response: other pages/layers remain
  usable. Select an earlier readable snapshot or recover the affected object
  from a verified copy. An unreadable quality record cannot make the view pass.

The summary's `quality.status=detail_required` is not a quality verdict. Use
`final-readiness` for the current delivery gate. Artifact metadata is hash
checked on read; large image/PPT bytes are checked when `/api/file` serves
them. Historical applicability means relative to the selected snapshot.

## Workbench Operations

New `annotations save` and `changes commit` operations require a client-generated
canonical UUIDv4 saved with the complete request before transmission. Saving
opinions changes only their history; it does not dispatch tasks or invalidate
production outputs. `changes plan` stores an immutable derived preview without
changing the business revision. Commit requires that exact plan and base.

- `conflict` (CLI 5 / HTTP 409): read current state and preview a new plan. Do not
  silently widen its page/layer scope or reuse a stale target slot.
- `operation_payload_conflict` (5 / 409): an ID already names a different
  committed request. Recover the original request or use a new ID for genuinely
  new input. Whitespace and Unicode are not normalized.
- A missing response is unknown, not a failed save. Keep the original payload
  separate from later draft edits. Run `deck-master operations show --project
  <dir> --operation-id <UUID>` before another business submission.
- `operation_not_found` (2 / 404): no matching committed fact was found. Replay
  only the exact original payload and ID. A query timeout is not `not_found`;
  keep the pending operation and verify again without creating a new ID.
- `receipt_cache_unavailable`: business state is committed. The operations
  directory is a derived index and is rebuilt from committed parent history.
  Do not delete or rewrite immutable objects/current.json to repair it.
- `operation_unavailable` (4 / 503): storage or verification could not complete.
  Preserve the pending request and inspect the project before retrying.

Read `changes handoff --change-id <id>` to obtain the core-generated plan,
tasks, required protocols and safely quoted CLI entry. Copying does not start
work. Only an actual `task start` with an execution reference records a claim.
A task older than 30 minutes needs verification; the service never automatically
repeats its call. Confirm cancellation before creating a replacement handoff.
Late results keep call facts but cannot overwrite the cancelled task's targets.
New `changes.v1` records require the matching writer; older cores refuse that
boundary. Existing projects are not migrated in place.

## Run Desk Recovery

`deck-master task list --project <dir> --limit 30 --offset 0 --revision <id>`
and `GET /api/tasks?limit=30&offset=0&revision=<id>` share a bounded projection.
Pin the returned revision for later pages. Optional status/change_id/attention
filters never start work. Existing `/api/tasks` without paging filters retains
its old response. `task status --details --revision <id>` and
`GET /api/tasks/<task_id>?revision=<id>` share detail, call facts and links to the
existing requests/attempts queries. Normal awaiting_host is HTTP 200 / CLI 0;
`continue` still uses exit 3 when it is waiting for a Host.

- `invalid_run_query`: CLI 2 / HTTP 400. Use limit 1–100, a nonnegative offset,
  one filter value and a committed revision. Do not fall back to a new snapshot.
- `task_not_found` / `change_not_found`: CLI 2 / HTTP 404. Read IDs from the
  selected project's committed run list; do not substitute another task.
- `run_object_unreadable`: local row/detail error. Other rows remain readable;
  use available history or restore that object from a verified project copy.
- `run_unavailable`: CLI 2 / HTTP 503. Preserve the current UI and saved operation;
  retry the same read. It is not permission to dispatch a replacement call.

New real claims on workbench.v3 record `execution_started_at` in the same Task
commit as execution_ref/status, and advance the pointer to `run-desk.v1`.
Use the matching core; older cores refuse the new writer before changing the
project. No existing HOME, installation or project is migrated by a read.
Legacy claims without this field remain "not recorded". Fixed-revision reads
do not acquire a live timeout merely because wall-clock time passes. Their last task update
may establish at least 30 minutes of waiting, but is never labeled claim time.

A 30-minute waiting warning only requests verification. Inspect the original
Task, request, Attempt and call allowance. Unknown is not not_sent; never
allocate or replay an external call automatically. After confirmed cancellation,
return to the affected page and explicitly preview a new scoped plan. Preserve
successful results and calls, and exclude those pages from the replacement.
The normal late-result protection remains in force after cancellation.
