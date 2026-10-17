# S03: one explicit Q3 precommit-absence reconciliation

`precommit_recovery.py` is a separate companion to the unchanged scoped
recorder and d0 helper. It resolves only the original Q3 initial
`service.create` failure with `presentation_mode=read`, after source ingestion
and before a Document existed. It does not retry, initialize, cancel, adopt,
write a Document, edit an original argument file, or release a later event.

The actual failure, its SDK charge, every source/extract orphan and the
original registration/run remain. `read` → `read_alone` is an explicit
transport-enum mapping, preserving the task text and other arguments. Any
later create is a separate explicit public call on the same registered
project and budget, after an independently reviewed prospective amendment.
It is not a first-attempt success or a new sample.

## Fixed dependencies and supported boundary

The tool verifies the exact repaired sibling supplementary SHA recorded in
`precommit_recovery.py` (`SCOPED_SHA`)
before import; that file verifies sibling d0 SHA
`d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261`.
The original helper/registration/run bytes are not amended. Its own
`resource_session` verifies the exact managed Python, module, manifest,
source/tree/wheel and complete package inventory. A0 uses only its own
original package API; it does not import B's capabilities or review modules.

Only profile `q3q4`, case/checkpoint `Q3`, project mode `new`, scope
`flow-{matrix_slot}--original-missing-template` is supported. There must be
exactly one unresolved original create, one saved ModelError at the
presentation-mode field, and its actual charged SDK intent. The original
arguments must contain exactly the registered brief, explicit `.txt`
materials, `read` and six-page limit, with no public operation ID. No native
or prepared/accepted Task history is accepted. Other failures require their
own recovery route; the companion fails closed.

## Prospective admission

The Host supplies an immutable JSON file and its exact SHA256. This is an
operational Host attestation of the permitted diagnostic scope, not proof
that a Runtime operation was absent and not a platform signature. No caller
JSON is accepted as an absence observation. Required fields are:

| Field | Exact value or binding |
| --- | --- |
| `format` | `rc3-precommit-absence-admission.v1` |
| `action` | `reconcile_service_create_precommit_absence_only` |
| `status` | The original registration status; no status upgrade |
| `observer_id`, `assurance` | `/root`, `host_attested` for an ADMITTED run |
| `evidence_kind` | `ROOT_ACTUAL_PROSPECTIVE_SCOPE_AMENDMENT` for ADMITTED |
| `tool`, `scoped_recorder`, `common` | Exact current new tool and unchanged sibling file Refs |
| `registration`, `run_manifest` | Exact original frozen JSON Refs |
| `root`, `slot`, `project`, `arm`, `scope_slot`, `whole_run_id` | Exact original run identities |
| `installation` | Original spec's `python`, `module_file`, `source_sha`, `source_tree`, `manifest`, `wheel_sha256` |
| `operation_key` | Actual unresolved journal key, not an invented public operation ID |
| `intent`, `failure` | Exact immutable original journal event Refs |
| `create_arguments_sha256` | d0 `digest(encoded(actual_intent.arguments))` |
| `enum_mapping` | `{ "field": "presentation_mode", "original": "read", "public": "read_alone" }` |

All Refs use the existing `{path,sha256,bytes}` format. An ENGINEERING
registration instead requires `observer_id=/engineering/rc3-s03` and
`assurance=synthetic_engineering`; it cannot authorize an ADMITTED run or
claim a real Root/native/human observation. No new admission is created by
this tool.

## Actual read and locking

The same controller-journal lock, original shared resource lock, and own
Runtime `write.lock`/`flock` are held. No second Runtime lock is invented.
The ordinary zero-byte `write.lock` may be created if original validation
failed before its first use. This is the only project metadata file the
companion may create; it is retained. Symlinks, aliases and a swapped lock
inode are refused.

Own pure source reading/canonicalization identifies exactly the registered
original text blobs and SourceExtract JSON objects. No Store object is put.
The entire actual project must consist of those objects, the normal empty
layout (including Store's empty `staging/anonymous`) and the held lock.
Current pointers, revisions, receipts, unknown objects/directories and any
Task ambiguity are refused. The tool does not infer absence from filenames
alone or ignore an orphan merely because it is not reachable from current.

After the first bounded probe, the companion charges **one actual SDK read**
to the original pool/scope and calls its own public `service.inputs_show`.
Only the actual own `StoreError` with path `(document)` and detail
`no current revision` qualifies. A returned result, different exception or
unknown state does not. Exact stdout/exception metadata, UTC and local
traceback are preserved. There is no operations query with a fabricated ID.
The original no-ID failure is not reissued to discover an ID.

The full file/dir identities and hashes are checked after the query and
again after rebinding the unchanged admission/scope/pending intent, before
settlement. Any drift refuses reconciliation. Actual cooperative Runtime
commits use the held Runtime lock; arbitrary external filesystem changes
observed during the probes are refused. The Host must retain exclusive
operational control of the admitted files; these local locks do not claim
protection against a privileged process replacing the program itself.

## Public commands

Use the **original registered managed Python** with `-I -B`, the reviewed
immutable S03 source and an exclusive new output directory outside the
original project/run/campaign. Do not execute the examples with placeholder
paths. The caller preserves actual argv, UTC, stdout, stderr and exit code,
including rejection before an output directory can be created.

```text
OWN_PYTHON -I -B precommit_recovery.py diagnose
  --run ORIGINAL_RUN --admission ROOT_AMENDMENT.json
  --admission-sha256 EXACT_SHA --out NEW_DIAGNOSIS_DIR

OWN_PYTHON -I -B precommit_recovery.py reconcile
  --run ORIGINAL_RUN --admission ROOT_AMENDMENT.json
  --admission-sha256 EXACT_SHA --out DIFFERENT_NEW_RECONCILIATION_DIR
```

`diagnose` leaves the original intent pending. `reconcile` repeats the real
read/probes; it never consumes stale diagnosis JSON. After actual absence,
it calls unchanged d0 `reconcile` with its generated Runtime observations,
appending ordinary `sdk_reconciliation` for the exact original key with
`observed_state=not_found` and `automatic_retry=false`. An already settled
intent refuses. Every invocation that actually reaches the query adds one
SDK charge, even if a later probe rejects; no charge is refunded. Exhausted
budgets prevent the query. Pure file/Store reads are not reported as public
SDK calls. A0 has no extra capabilities API query; other actual installation
queries remain separately observable through the original verifier.

Only after successful independent admission and actual reconciliation may
the Host issue **one separately recorded** scoped `service.create` with the
original arguments plus only the documented enum correction. The returned
mapped argument JSON is a proposal for that separate call, never executed
by the companion. Later template events, native limits, review gates and
original shared resource totals remain unchanged.

## Verification scope

Portable tests explicitly label their source-environment legacy-order
fixture and installation-admission seam. They use the real source reader,
Store writes, model validator and public query; they do not claim the
current atomic B create leaves orphans. Separate engineering evidence uses
actual A0 `-I -B` create/inputs_show and full installed-byte verification,
without an installation seam. Neither is a model/content/human acceptance
result. Formal Q3 recovery and retry remain Root actions after independent
review and a prospective exact scoped amendment.
