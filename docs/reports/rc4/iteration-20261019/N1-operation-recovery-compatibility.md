# N1 operation recovery compatibility

This report describes the RC4 working implementation on the fixed RC3 base
`a08bc68c1cbbbc806205104c2bb01f3f096305f0`. Evidence is synthetic engineering,
not a production-project or professional-content approval. The integration
owner records the final candidate commit and the sole AC status ledger.

## Request and response contracts

| Surface | Request ID | Digest | Success |
|---|---|---|---|
| CLI `inputs update`, Python `service.inputs_update`, old HTTP `/api/inputs/update` | Existing Store safe syntax `[A-Za-z0-9][A-Za-z0-9_.-]*`; no UUID or 128-character restriction | New `inputs-update-request.v1` domain, raw parsed patch, project, original base, lexical absolute patch directory when relative source paths occur | Existing flat `updated` or `unchanged` response |
| `content inputs`, `content_ops.inputs`, `/api/content/inputs` | Existing canonical UUIDv4 | Existing `changes.v1` / `content.inputs` digest is unchanged | Existing `committed` / `operation_result` wrapper |
| `operations show` | Safe existing ID | Reads original stored digest | Atomic `committed`, or explicit old `legacy_recorded` projection |

New ordinary requests bind the **original base**, original parsed JSON and
relative-path context. JSON object key ordering is insignificant; array order,
Unicode, string whitespace, omitted fields and explicit defaults remain
significant. Path context uses `expanduser`/`abspath`, without resolving source
paths or consulting upload records. Keep the original patch file, original
base and original operation ID when retrying. Relative source paths require
the same patch directory context; absolute source paths can be replayed across
CLI, Python and old HTTP without an additional HTTP parameter.

Both input families check canonical operation history and old-log occupancy
before source normalization, upload lookup, upload byte verification or source
reading. They repeat the same check while holding the project lock, before CAS
and business effects. An ID owned by the other family is a conflict even when
the visible inputs appear identical.

Ordinary updates atomically store `change.operation_receipt.v1` together with
the business Document. Their core response's `revision_id` always denotes the
original commit. Replay adds `replayed=true` and the separately observed
`current_revision_id`; it does not dispatch or claim tasks. Any `pending_tasks`
in the saved result are historical records: run `continue` to obtain current
executable tasks. Workbench URLs and session ports are attached by the existing
CLI presentation layer and are not stored in the receipt.

Actual input changes, display-name-only changes and business no-ops all create
recoverable receipts. A new ordinary no-op still reports `unchanged` and may
advance the revision solely to record the receipt. It leaves Page refs, content
basis, input digest, tasks, reviews, outputs and call facts unchanged. Existing
higher writer floors are preserved; N1's own minimum feature is `content-ops.v1`.
An input update that also produces an N3 Task naturally retains N3's higher
floor.

Objects and unpointed revision files are not commits. Before the current pointer
changes, an interrupted request can execute again under CAS. After the pointer
changes, exact retry recovers its original result. An index-write failure after
commit returns success with `journal_warning.code=receipt_cache_unavailable`.
The operations JSON index is optional and does not establish business truth.

## Historical ordinary journals

No historical digest, Document or journal is migrated or rewritten. Old ordinary
journals retain `request_sha256`, `kind=input_update` and the original flat
result. The adapter reads only the safe ID's one journal and verifies its ID,
format and reachable result revision. Historical changed results also have to
name the matching operation commit; old unchanged journal-only results may point
to their then-current ancestor. Pure legacy task/reason/default/metadata/remove
normalization reproduces the old digest without adding a base binding that was
never stored.

An old source add/replace or upload binding cannot be recreated from today's
filesystem without changing the evidence. Such replay returns
`operation_unverified`, without reopening files or upload staging.

| Historical evidence | Pure resolver | Ordinary adapter / neutral query |
|---|---|---|
| Reachable old input change, no atomic receipt, complete matching log | `unknown`, `legacy_receipt_only` | Exact pure old normalization can replay; show returns `legacy_recorded` |
| Same old change, missing/corrupt/unverifiable log | `unknown` | `operation_unverified`; retain original payload/base/ID |
| Old log-only no-op, complete valid log | `not_found` in canonical ancestry | Log still occupies ID; exact old replay is allowed; show returns `legacy_recorded` |
| Old log-only no-op, surviving corrupt log | `not_found` in canonical ancestry | `operation_unverified`; preserve corrupt log |
| Old log-only no-op, sole log completely lost and no history ID | Indistinguishable from a never-used ID | Do not invent the old result; show reports not found; new admission follows current base/CAS |

`legacy_recorded` declares `receipt_source=legacy_log` and
`request_binding_verification=legacy_only`; it is not atomic `committed` and
has no fabricated `result_ref`. Index publication preserves old input journals.
A legacy or corrupt surviving log cannot be bypassed by switching input family.
The final static comparison against the fixed base confirms byte-identical
function source for old ordinary `_normalize_input_patch`, content
`operations.request_digest`, and Store's `_validate_operation_id`. The evidence
JSON records their hashes alongside the runtime compatibility cases.

## Error adapters

| Condition | Old HTTP | Ordinary CLI |
|---|---|---|
| Pause, scope, missing decision | 409 with actual primary eligibility code, reasons, responsible role, next action, decision projection and artifact/control revisions | Existing exit 4, same business code |
| Stale base or changed raw request/binding | 409 `input_revision_conflict`; `cause=stale_base` or `operation_payload_conflict` | Exit 5 |
| ID owned by other input family | 409 `input_revision_conflict`, `cause=operation_type_conflict` | Exit 5 |
| Old operation evidence unverifiable | 409 `operation_unverified`, unknown, retryable false | Exit 4; inspect original operation |
| Canonical history/object IO unavailable | 503 `operation_unavailable`, unknown | Exit 4 |
| Malformed JSON, ordinary patch/field errors, missing call fields, unsafe ordinary ID | Structured 400 `invalid_input`, preserving the old endpoint mapping | Exit 2 |
| Typed transport-body validation (for example a non-object top-level body) | Structured 422 `invalid_input`, preserving the old endpoint mapping | Exit 2 |
| Unreadable source material | Structured 422 `source_unreadable`, with a safe field/message | Exit 2 with a safe field/message |

The adapter is limited to the old inputs endpoint. It does not replace every
HTTP error handler. The covered source-parser, history and snapshot failures
publish safe fields/messages without local paths or parser tracebacks. Unknown
recovery points to original-operation inspection and retains
the original payload, base and ID rather than recommending a fresh execution.

## Shared internal query and eligibility boundaries

`operations.resolve_operation(store, operation_id, *, head_revision=None)`
returns `OperationLookup` with state, actual head, receipt format, stored kind,
committed revision, verified record/result and an internal reason. It performs
no source/model/task execution, revision creation or disk-index publication.
`_decode_committed_operation` is the canonical receipt decoder;
`committed_record`, `recover`, `show` and `Store.operation_receipt` consume the
same semantics. A complete verified chain is required to establish not found;
missing, corrupt, foreign or cyclic history is unknown. N4 may accelerate this
query and retry a concurrently moving current once according to N4's explicit
matrix; it must declare the actual final fixed head. An explicitly selected
historical head stays selected and must be reachable from captured control.

`snapshots.load_artifact_control` captures a safe control Document once and
selects only a same-project ancestor as artifact. Python eligibility and the
HTTP eligibility action both use this pair. Empty revision is invalid; it does
not select current. A later pause does not become part of an already captured
pair, and a subsequent query observes that pause. Both surfaces report the
actual artifact/control revisions and reject invalid, orphan, copied, foreign,
symlinked and corrupt snapshots without initializing or repairing the project.
The final review also checks the full Document schema on captured control and
each traversed ancestor before eligibility evaluation. Valid JSON with a broken
`collaboration` shape is rejected as `revision_unavailable` on SDK, the HTTP
adapter and the actual HTTP route; it cannot escape as an internal AttributeError
or establish operation absence.

N4's cache is disposable. `DECK_MASTER_OPERATION_CACHE=0` or resolver
`use_cache=False` selects canonical control behavior. The N1 focused suite is
used with cache on and off to check semantic equivalence. The N4 owner maintains
separate decoding/read-count evidence.

## Verification scope

The pre-review final affected regression completed with **321 passed, 4
deselected** in 54.20s. Its focused cache-disabled counterpart completed with
**65 passed** in 15.00s. These are actual log results from the implementation
handoff, before the final review's schema-boundary addition.

The reviewed focused collection now contains **68 cases** (51 input-recovery,
17 eligibility-boundary). After the schema fix, the 17-case boundary set passed
with the cache enabled (3.17s) and disabled (3.31s). The three added cases cover
malformed current, selected historical and intermediate ancestor Documents;
they assert matching errors, unchanged bytes, path redaction and unknown
operation state. After the final N4 shared-source changes, the six-file
N1/N4B group passed **166 cases** (49.58s), and its four-file N1 shared-interface
counterpart passed **101 cases with the cache disabled** (22.19s). Both include
all 68 current N1 focused cases. The exact commands/results are also retained
in `N4-validation-resumed.txt`. The integration owner attaches the final
candidate SHA/tree and repository-wide gate results.
Four existing `generation.freeze` cases also passed (11 unrelated cases
deselected), covering the unchanged encoding vector, exact replay after later
progress, CLI/HTTP equivalence, and refusal before creating missing/legacy
projects. This supplements the task/content receipt cases in the 321-case group.

The four deselected cases are render-marked `test_flow_quality` cases;
`rsvg-convert` is unavailable locally. They are neither passing nor skipped
renderer evidence. Repository-wide, renderer, required-browser and installed
candidate gates remain integration responsibilities. No customer project,
actual HOME activation, external model call, commit or publication is evidenced
by this N1 report.
