# Scoped image events at one shared ledger

`image_event_controller.py` is a Host recorder and own-SDK adapter. It never
calls a model or imagegen, writes manuscript content, grants production rights,
adopts a candidate, or declares an experiment qualified. Root supplies the real
tool invocation and complete original observation. Engineering registrations and
observations remain `ENGINEERING_ONLY_NOT_ADMITTED`.

The original bf image controller stays byte-for-byte unchanged. Its global
key permits one call for each original whole-run/arm/Page pair, which cannot
represent two separately authorized Q4 events on the same Page. This controller
adds explicit instruction scopes under the **same** original wholeflow and
canonical ledger. It does not rename the Page, reset the whole run, or raise a
cap after seeing an output. It also supports one M02 project with two sequential
uses. Q4A and Q4B still require independent projects.

## Before the first affected call

Pin `rc3-image-event-registration.v1`: `status`, `controller_sha256`, exact sibling
`sdk_controller` (d0) and `bf_primitives` (bf) references, `protocol`, `policy`,
`admission_review`, `activation`, and own `installations[arm]` identities. The
actual installation interpreter, module origin, source/tree/wheel manifest and
complete package inventory are rechecked by d0. A new tool source commit does
not change a historical installed source SHA.

The separate `rc3-image-event-policy.v1` contains:

* One canonical `ledger_root`, fixed finite `total_call_cap`, `protocol`, and
  `Root_decision` references. Unused optional scope cannot be borrowed elsewhere.
* `parents`: unique `parent_id`, `matrix_slot`, original `case`, `whole_run_id`,
  `repetition`, `arm`, and `max_calls` for each wholeflow/arm.
* `scopes`: unique `scope_slot`, original `parent_id`, `checkpoint`, exact UTF-8
  `instruction` reference, `max_calls`, and finite `leaves`.
* Each leaf fixes `leaf_id`, stable `page_label`, actual `page_id` or null until
  its actual Page exists, and `max_calls=1`, `max_candidates=1`, `retries=0`.

Actual future SDK Requests, Attempts and grants are not fabricated at policy
registration. A null Page is bound to its actual ID by the later handoff, never
passed to a public SDK. Same-checkpoint semantic Page identity then stays fixed.
Both M02 uses register distinct stable Page IDs; their original parent and
actual project remain shared.

For M02's `scope-events-v1` profile, each leaf's stable `page_label` must equal
one of its own use's preregistered `page_ids`. All live/read labels are distinct.
Its `page_id` may remain null while the recorder is registered and initialized
before manuscript creation; a nonnull value must equal that leaf's planned ID.
This is a planning identity check, not a Page or a production grant. Begin and
preparation still require the actual current own-SDK Page, Task, frozen Request,
reserved allowance and then in-flight Attempt. Null cannot be dispatched.
M02's actual Page ID must equal that leaf's original planned label at begin,
preparation and the saved-preparation check before dispatch or settlement.
Actual rights to a different Page in the same live/read use do not satisfy this
identity check. An explicit handoff leaf must name the same slot. Other cases
retain their existing late-binding semantics.

`activation` is Root's operational `host_attested` decision: `observer_id=/root`,
the exact `policy_sha256`, `legacy_writer_route=HISTORICAL_READ_ONLY`, and
`evidence_kind=ROOT_ACTUAL_DECISION` (or engineering). No platform signature or
human approval is invented. After activation Root uses this entry for new calls;
the old bf entry remains historical. Any later old dispatch changes the captured
frontier and closes the new route rather than silently ignoring that charge.

For an existing root, `legacy_policy_refs` lists the actual original
`global-budget.json` and `budget-origin.json` in that order when present.
`legacy_mapping` maps **every** existing dispatch hash to its original scope,
leaf, actual project/Request/allowance and observed instruction/budget-root
identity. Unknown historical outcomes count. If these facts cannot be mapped,
activation refuses; neither old bytes nor historical evidence is rewritten.
An empty original root needs no invented dispatch. Initialization uses the same
bf lock and creates a separate new mode-600 observer key; it never reads an old
observer key. A second root, copied ledger or reinitialization is refused.

## Actual Host sequence

Use the selected own installation's absolute interpreter with `-I -B`; keep
project paths short. Controller registrations and ledger/key directories are
Host-only and never Writer material.

```bash
"$OWN_PY" -I -B "$EVENT_TOOL" inspect-plan --registration event-registration.json
"$OWN_PY" -I -B "$EVENT_TOOL" admit-epoch --registration event-registration.json --root "$FORMAL_IG"
```

`admit-epoch` registers an already independently reviewed scope; the command
name does not prove admission. All referenced actual gates remain Root's
responsibility. The old root/policies stay visible and unchanged.

For each actually triggered scope, Root records an immutable occurrence with
`assurance=host_attested`, `observer_id=/root`, `evidence_kind=ROOT_ACTUAL_NATIVE`
(or engineering), `scope_slot`, exact `instruction_sha256`,
`actual_trigger_satisfied=true`, and actual `source_observations` references.
Use the own public SDK to create the real instruction evidence/current Request,
effective bounded grant, claimed single-Page Task and frozen generation Request.
The actual frozen parameters must equal `{"transparent_background":false}`;
the product independently permits other parameters, which this campaign rejects.

An `rc3-image-scope-handoff.v1` binds these actual fields:

```json
{
  "format":"rc3-image-scope-handoff.v1",
  "matrix_slot":"ORIGINAL_SLOT", "case":"ORIGINAL_CASE",
  "whole_run_id":"ORIGINAL_WHOLEFLOW", "repetition":1, "arm":"B",
  "checkpoint":"ORIGINAL_CHECKPOINT", "scope_slot":"REGISTERED_SCOPE",
  "project":"/canonical/actual/project", "stage":"ACTUAL_STAGE",
  "instruction_occurrence_ref":{"path":"/actual/occurrence.json","sha256":"ACTUAL"},
  "actual_request_id":"RETURNED_COLLABORATION_REQUEST_ID",
  "task_id":"RETURNED_TASK_ID", "allowance_id":"RETURNED_ALLOWANCE_ID",
  "attempt_id":"RETURNED_ATTEMPT_ID",
  "packet_audit_ref":{"path":"/actual/audit.json","sha256":"ACTUAL"}
}
```

This is an explanatory template, not dispatchable JSON. Before an actual begin,
`guard_call_begin(config,binding,page_id,arguments)` accepts a missing/null
`attempt_id`, checks the real reserved allowance, exact frozen Request/current
claim and campaign space, and **does not begin or invent an Attempt**. Host then
calls its own `tasks.call_begin` and adds the returned Attempt ID. The
supplementary recorder can pass this as its explicit Host callback; a JSON
`trusted_context` is not accepted. Its query chain consists of d0 installation
verification, Store reads, `tasks.task_inputs_current` and `eligibility.guard`;
it performs no generation/show/freeze/begin call itself.

The packet audit records `status=PASS`, the exact `scope_slot`, `task_id`,
`project`, `stage`, `required_read_closure_checked=true`,
`raw_workorder_preserved=true`, and three immutable refs: `original_raw_ref`,
`author_view_ref`, `read_closure_manifest_ref`. A bounded P5 view can differ from
the quarantined complete raw response. Its mapping and actual required-read
receipt must say exactly what was read; full methods remain unchanged. Merely
seeing an opaque full-artifact identity is not equivalent to reading that file.
This adapter checks the pinned audit/binding, not the semantic safety of a view;
the independent packet audit supplies that fact. It never claims the Writer read
the quarantined original.

```bash
"$OWN_PY" -I -B "$EVENT_TOOL" prepare-page-call --root "$FORMAL_IG" --leaf-id ACTUAL_LEAF --binding handoff.json --attempt-id ACTUAL_ATTEMPT
"$OWN_PY" -I -B "$EVENT_TOOL" mark-dispatch --root "$FORMAL_IG" --leaf-id ACTUAL_LEAF --bootstrap actual-root-bootstrap.json
```

`prepare-page-call` reads the actual own-SDK in-flight right, parent chain,
current claim/inputs and exact literal arguments/references. A shared real
two-Page parent can have zero *unreserved* remaining space while its two already
reserved child calls remain legitimate. A new instruction scope requires an
actually different current collaboration Request, occurrence and grant; a new
label, operation ID or batch is insufficient. Child grants in one scope must
retain the same actual budget-root identity.

`mark-dispatch` rechecks current rights and charges global/original-parent/scope/
leaf counters under the same lock **before** Root performs the external call.
It appends a global hash-linked reservation before its local mark. A crash
between those writes retains the charge. Unknown, rejected, unusable, late or
partially settled calls never free it, and no command resends it.

Every preparation/dispatch/seal/settlement/reconciliation write loads and
validates the current legacy frontier **after acquiring the same original bf
lock**. Accounting inspection and the begin guard's campaign-budget snapshot
use that lock as well. A successful check made before waiting for the lock is
insufficient: an old writer could append while the new caller waits. Such a
change now refuses before a typed charge or dispatch marker is published.
Initial epoch registration already captures legacy files inside this same lock.

Root now calls the real image tool once with the saved
`literal-tool-arguments.json` **unchanged**, then records the complete original
tool response and original PNG bytes using the bf callback shape:
`observer_kind`, `observer_id`, `tool_name`, `actual_arguments`,
`controller_observed_completed_at_ms`, `completion_status`, `native_response`,
and for completed output `original_png`; optional actual
`platform_invocation_ref` remains optional. Root's actual bootstrap uses the
unchanged bf bootstrap contract. No image call happens inside these commands.

```bash
"$OWN_PY" -I -B "$EVENT_TOOL" seal-observation --root "$FORMAL_IG" --leaf-id ACTUAL_LEAF --callback actual-callback.json --bootstrap actual-root-bootstrap.json
"$OWN_PY" -I -B "$EVENT_TOOL" settle --root "$FORMAL_IG" --leaf-id ACTUAL_LEAF
"$OWN_PY" -I -B "$EVENT_TOOL" inspect-accounting --root "$FORMAL_IG"
```

The first callback and readable original response/PNG are frozen before
validation. Literal argument/time/raw-response validation and unchanged image
reference checking reuse the **unchanged pinned bf functions**. New code owns
the scope accounting, its separate protected seal/provider, same-global-charge
binding and own-SDK context/settlement path. Those changes require independent
engineering review; an old GIMG pass does not silently cover the new provider.
Exact unchanged extraction/validation primitives may reuse their original real
tool evidence with an explicit dependency/scope bridge rather than automatically
spending another image call. Ordinary JSON, output substitution, changed hashes,
copied ledger paths or a context from another event are refused.

A completed call is charged as consumed even if its output/context is unusable;
error/uncertainty is charged unknown. Real Runtime settlement errors retain their
facts and unconfirmed record. `reconcile-settlement --root ... --leaf-id ...
--runtime-observations QUERY_REFS.json` reads actual own `generation.show`; it
neither reruns a tool nor refunds campaign space. Actual SDK acceptance/adoption
and central production/file gates remain separate operations.

## A0 capability boundary and M02 profile

The A0 path uses only its own installed Store/generation/public protocol. It
does not import B's native evidence module. Its current old observation
capability is reported `BLOCKED_MISSING_OWN_NATIVE_OBSERVATION`; preparation
normally stops there. An explicitly preregistered
`allow_A0_host_observed_only=true` scope may record and charge Root's real call
using A0's own host-reported settlement. This remains blocked for native
observation/adoption and cannot be called a native or professional pass.

M02 omits `image_ledger_profile` or chooses `legacy-bf-v1` to retain the existing
bf validation/guard. Explicit `scope-events-v1` instead pins
`image_event_controller`, `image_event_registration`, `global_image_policy` and
the same protocol/own B installation. It must omit `global_image_budget`, bind
exactly one original M02 parent, distinct exact live/read Page sets, their exact
instructions, per-use ceilings and one candidate per permitted call. Unknown or
mixed profiles refuse. Only the old budget validation and image-ledger begin
check dispatch to the new helper; Narrative/version/current/notes/review/native
business logic is unchanged. The M02 source hash changes and needs a new
registration; historical 3c84 evidence remains exact historical evidence.

## Engineering evidence limits

Focused tests cover real public SDK Request/grant/claim/freeze/begin/settlement
and acceptance with explicit synthetic observation/packet seams, shared parent
children, same-Page new events, same-project M02 four-leaf accounting, Q4 project
separation, historical/unknown charges, crash publication and invalid bindings.
These tests call no model or image tool, do not establish full M02 variants or
Q3/Q4 visual quality, and do not replace Root's actual effect records or the
deferred human acceptance.
