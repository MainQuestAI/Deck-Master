# RC3 supplementary recorder

`supplementary_recorder.py` is a Host recorder for explicitly scoped, finite
experiments. It does not generate prose, create a substitute Task, issue image
rights, or declare a model/human result. Run it with the **registered own
installation's absolute Python `-I -B`**. The frozen d0 helper is imported by
exact SHA; its `prepare` function is never called.

## Registration and resource units

The registration format is `rc3-supplementary-registration.v1`. It pins this
recorder SHA, sibling `common`, `protocol`, `policy_epoch`, `admission_review`,
`exposure_registry`, `grammar`, actual `installations`, a canonical `ledger_root`
and finite `scopes`. A scope key is consumed once. Copying a run/campaign or
initializing the same registration at another ledger root is refused. A later
registration is a new experiment; this program cannot attest that an operator
has not created an undisclosed experiment elsewhere.

Each scope contains `profile`, `case`, `checkpoint`, `matrix_slot`,
`whole_run_id`, `repetition`, `arm`, `scope_slot`, canonical `project`,
`project_mode: new|existing`, actual `checkpoint_ref` for an existing project,
`instruction`, `materials`, `technical_supplements`, stable `page_ids`, and:

```json
{
  "limits": {"writer": 48, "review": 32, "sdk": 1200, "render": 64},
  "native_limits": {
    "initial_writer": 12, "repair_writer": 3, "feedback": 1,
    "verification": 1, "production": 24, "production_review": 16
  }
}
```

The example illustrates **ceilings**, not a Root resource decision. Individual
role ceilings are constrained by the aggregate ceilings as well; they do not
add another pool. Scopes may preregister smaller finite ceilings.

| Profile | Actual case/checkpoint | Shared upper ceiling: writer / review / SDK / compile-render |
| --- | --- | --- |
| `q3q4` | Q3/Q3 or Q4/Q4A,Q4B | 48 / 32 / 1200 / 64, **one pool per arm across Q3 and Q4** |
| `q1-p5` | Q1/Q1P5 | 5 / 3 / 128 / 8 per original whole run, repetition and arm |
| `q2-300` | Q2/Q2_300 | 6 / 2 / 128 / 0; initial writer ≤3, necessary repair writer ≤3 |
| `e2` | E2/E2 | 5 / 3 / 128 / 8 per preregistered risk run and arm |
| `e3` | E3/E3 | 0 / 1 / 0 / 0; separate selected-file audit operation |
| `m02-tools` | M02/M02 | 0 / 0 / 1024 / 64; wraps **only tools**, M02 native roles remain in its own recorder |

An SDK unit is **one explicit public entry/query attempted**, including a
refusal. Preparing methods is a real `read_task_methods` entry; the A0 fallback
is one actual `task_summary` adapter returning its own full installed files.
Claiming performs and charges `task_start` and a new full-method entry. Read-only
installation metadata/package hashing and ordinary Store reads are separately
observations, not invented SDK operations. Inner implementation calls of a
public SDK function do not constitute additional Host entries.

`resource_session(run, render_reserve=N)` yields a `MeteredJournal, state,
config`. An existing Host helper must actually use that journal for each
`sdk_intent`; an unwrapped helper is **not** claimed to be metered. In particular,
Root can wrap M02 **public operations** with this context and pass the yielded
journal to M02's existing operation function. Do not wrap M02's native begin in
the `m02-tools` profile: its native roles have their own independent limits.

Reserve a known finite maximum before a call that might compile or render.
The read-only call profiler observes the own installed function entries:

- `compiler/api.py::compile_deck`: one native compilation attempt.
- `pipeline.py::render_deck`: one outer PPT renderer round; its `pdftoppm` page
  loop does not add renderer units.
- `pipeline.py::preview_svg_page`: one page SVG preview attempt.

An entered function still costs a unit when validation, a renderer, or a later
CAS commit fails. A completed local trace reconciles proven unused reservation;
it never refunds an entered attempt. An interrupted process leaves its original
reservation pending. Lost/changed profiling leaves unknown and blocks another
session. Exceeding the reserved maximum retains the outcome, charges actual
attempts and refuses to consume it as admitted work. No renderer fallback or
automatic retry exists. An unresolved SDK intent permits only explicitly
allowlisted read-only queries; `reconcile` uses actual `operations.show` facts.
Historical/unavailable/unknown remains unresolved, with the old payload retained.

## Native Task chain and safe P5 view

The callable/CLI order is:

1. `freeze`, `init`, `instruction-event`: exact preregistered instruction bytes
   require an actual Root trigger observation and source observation refs.
2. `public-operation`: own actual closed public SDK entries, no caller Store,
   project switch or trusted adapter/receipt selector.
3. `prepare-task`: actual current Task, role/kind/phase match, full own methods;
   raw response and Task remain in `preflight/quarantine`.
4. `audit-packet`: independent non-author audit pins raw, named author view and
   transitive closure. No author has permission to the raw quarantine directory.
5. Root spawns a fresh author that initially waits; `begin-native` records the
   actual invocation and consumption even on an actual budget overrun.
6. `claim-read`: real own `task_start`, then real new full methods/workorder;
   response stays quarantined. `release-safe-packet` requires a second actual
   independent audit before releasing the listed author files.
7. `observe` freezes raw native output/completion/sidecars first, then checks
   d0's actual full-FINAL/completed/Task/method binding **and** the actual author
   view/closure hashes and complete-file read observation. It does not claim the
   author read the complete original raw SDK workorder.
8. Exact existing d0 `input_revision` materialization or own public acceptance;
   preproduction reviews use their own opaque bridge, ordinary production
   reviews use normal acceptance. `snapshot` records actual current readiness.

`q4-p5` is an **explicit bounded workorder view**, not a redacted raw response.
Raw responses are preserved unchanged. Its manifest maps every actual required
file to an exact byte copy and separately lists opaque identity-only bindings.
It includes the complete current target Page/notes, complete registered P5
source projection, required target visual/design objects and **all full method
bytes**. Original-source `text`, immutable original and extract/locator fields
must agree structurally. A full historical Source containing other Pages cannot
become safe because the Task's `scope_pages` happens to say P5. This is checked
by parsed Page/object/ref identity and transitive hashes, not a sentinel search.
Unknown workorder fields and unclassified required URIs refuse dispatch.

The public local Task constructor includes whole-file outputs in `inputs` as
well as `outputs`. For the supported page-local repair/reconstruct/blueprint or
page-visual review protocols these exact output Refs remain **opaque binding
metadata**, with no whole-file read permission. Expanded output content is
refused. A required full Plan/Narrative, other Page/notes, foreign path, path
alias/symlink or extra required source refuses the packet. Final whole-file
review cannot be relabeled a P5 task. Project paths and opaque refs are metadata,
not a directory access grant; this is a Host boundary, **not an OS sandbox**.

The bounded semantic-object guard uses the actual public schema families
`narrative.v1` and `content_plan.v2`. It rejects complete objects inline, nested
inside JSON, or reached through required-read Refs, including JSON stored with
another suffix. JSON is checked before an author copy is written, so a rejected
wrapper cannot already contain the whole Narrative/Plan in the author files.
Opaque `narrative_ref`/`page_manifest_ref` identities stay unexpanded. This guard
applies only to the bounded view; full/nonblind Q1/E2/public source profiles keep
their existing permissions. It does not change any Runtime Task or Page contract.

The real neutral route diagnosis is separate evidence: public legacy import
then replacing a full Source with a P5 Source succeeds as an input operation but
creates a global input-revision Task; a P5-only Request cannot claim it. This
recorder does not repair other Pages or bypass that barrier. A project created
with the full historical draft and **only the complete P5 Source from the
outset** can dispatch/claim a real P5 repair task. Whether that route meets an
individual formal checkpoint's fidelity requirements remains an actual Root
registration/preflight decision, not an inferred Runtime PASS.

`q3-full` and `nonblind-file-engineering` are explicitly full/nonblind packet
profiles. They must not be used to release a full historical Q4 file to a P5
author or to claim an unseen/blind result. Q4 P5 notes may already specify the
public modification goal; reading them is not independent discovery.
The `q3-full` name also serves the explicit Q1-P5/E2 own-public-material
production checkpoint: those original materials need not be a P5 JSON Page.
Actual Task Page scope is still bounded to the registered target. Q4's stricter
historical-source quarantine is not silently imposed on unrelated profiles.

## Repair, image and selected-file boundaries

`deliver-feedback` permits one accepted, actually observed feedback per original
case. `repair-begin` validates actual feedback findings and necessary semantic
layers, once per original case. `svg-repair-begin` needs an actual adopted
page-visual review finding and existing Page/SVG; its single allowance keys the
stable Page ID across Tasks/events/checkpoints. A real page-visual repair Task
cannot start production without that declaration.

`tasks.call_begin` requires a Host guard callback. CLI callers supply
`--image-guard` pointing to exact `event_registration_ref`, `binding_ref` and
`page_id`; the registration must pin the sibling `image_event_helper` bytes.
The companion `guard_call_begin` checks own actual claimed Task/current
Request/reserved allowance/frozen false-parameter request and the same global
ledger policy. Its current implementation performs installed-identity and
Store/eligibility observations, **zero extra public generation queries**.
Changing the helper requires a new exact dependency review. Only after the
guard does this recorder call/charge the real own SDK `call_begin`. The actual
returned Attempt then binds `image-handoff`; generation IDs are never invented.
The image companion alone observes/settles actual Root tool results. This
recorder has no image tool, key or settlement entrypoint. A0 missing its own
collector/opaque bridge remains blocked without borrowing B.

E3 has `prepare-file-audit`, `begin-file-audit`, `observe-file-audit`: an actual
current selected native PPTX and transitive current outputs, own complete file
review methods, one independent fresh read-only native auditor and exact raw
completion. It is explicitly **not a DM Task** and produces no fake review
receipt, SDK acceptance or professional gate. Its zero SDK/render budget stays
zero. Missing actual native PPTX refuses preparation.

All model/image operations, final-head installation/control admission, formal
scope execution, independent code review and the deferred human/desktop checks
remain separate from synthetic mechanical unit tests and installed engineering
traces. Optional events are not triggered by merely registering their profiles.
