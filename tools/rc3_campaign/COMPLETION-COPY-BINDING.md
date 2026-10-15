# S04: an explicit original/frozen completion-copy binding

The four actual unseen A/B first-original manifests reference their original
Root completion files. Their unchanged original snapshots instead reference
the exclusive `raw-root-completion.json` copies frozen by `observe`. Each
pair has exactly the same raw bytes, SHA256 and length, but different paths.
Frozen `unseen_native_only.py` requires whole-Ref equality in two comparisons
and therefore refused the first actual slot. The failure and all original
files remain; no original manuscript, first-complete instant or author is
replaced by this correction.

`completion_copy_binding.py` is a separate, narrow companion. It verifies and
imports unchanged sibling unseen SHA
`c6e64132703e1b1eed77abdb2e3c52c4794435c7db091a82a5b59c0f4c032af3`,
which verifies d0 SHA
`d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261`.
It never imports the SDK, uses a model/image, changes a registration, rewrites
an old function, makes a synthetic old-format actual record, normalizes a
completion body or exposes a private-opening entrypoint.

## Exact scope and checks

The companion supports only the four original A/B slots in the existing six
unseen slots. C keeps the old recorder's exact original route, earliest
native prefix and raw/FINAL equality. No Q1 alias, new case, budget or pool
is created.

One exact original completion ↔ frozen copy pair is discovered from the
existing original snapshot and its native-complete manifest. It must name
exactly one selected stage, different canonical regular-file paths, equal
actual bytes and correct declared hashes/lengths. Its unchanged stage receipt
must reference that frozen copy. The pair's actual invocation, method read,
Task and project are bound explicitly. No third same-hash path or later
stage gains an implicit alias.

The A/B branch reproduces the frozen binding validator, preserving:

- Exact proof fields, case/input/method identities and original-complete
  snapshot/manifest, selected raw-stage order and every raw/completion carrier.
- Actual evidence class, host-attested full nonempty UTF-8 FINAL, completed
  sender/list-agents observation, exact raw hash and complete method-read hash.
- Original known chronology, exact earliest snapshot hash, existing author
  identities, unchanged invocation/read/completion receipts for every stage,
  actual Task/project, known invocation lineage and stable actual turn IDs.
- Excluded-author checks and uniqueness within/between slots. Same-byte output
  does not waive independence or make one actual turn eligible twice.
- The existing freshness requirements for proof/lineage observations. An old
  observation is not refreshed by this tool; Root must supply any future
  mechanical observation through an explicit separate file, preserving old
  files and the original first-complete snapshot.

Only two Ref relations differ: original manifest completion membership, and
the completeness-stage receipt matching the lineage summary. They may match
the one exact prospective pair instead of whole-Ref path equality. All stage
receipt → original frozen completion equality stays exact; the lineage's
completion must still be the original manifest's exact Ref. Full bytes,
identity and authorization are checked, not just SHA labels.

## Prospective Root amendment

Read-only diagnosis needs no admission and appends no ledger event. Binding
needs a separately supplied immutable amendment and exact SHA256. It is
operational Host authorization of this exact copy relation, not native
evidence or an additional platform-signature requirement. The companion never
creates an amendment or upgrades an engineering campaign.

| Field | Required binding |
| --- | --- |
| `format` | `rc3-completion-copy-admission.v1` |
| `action` | `bind_original_same_bytes_completion_copy_only` |
| `status` | Exact original campaign status |
| `observer_id`, `assurance` | `/root`, `host_attested` for ADMITTED |
| `evidence_kind` | `ROOT_ACTUAL_PROSPECTIVE_COMPLETION_COPY_AMENDMENT` for ADMITTED |
| `tool`, `recorder`, `common` | Exact new deployed tool and unchanged sibling helper Refs |
| `campaign`, `registration`, `slot`, `proof` | Original canonical campaign and exact original slot/proof/registration |
| `original_snapshot`, `native_complete_manifest`, `lineage` | Exact existing earliest-original files |
| `copy_pair` | Exact object described below |

`copy_pair` has exactly the observed values: `ordinal`, `task_id`,
`project_id`, `invocation`, `method_read`, `original_completion`,
`frozen_completion`, `sha256`, `bytes`. Newly generated Refs record canonical
absolute `{path,sha256,bytes}`; neither an unavailable path nor a caller's claimed
digest is proof. The two completion Refs must be the actual manifest and
selected snapshot/receipt Refs. Tool and helper locations are explicit;
placing a new file does not relabel an older source or installed candidate.

An engineering campaign requires `/engineering/rc3-s04`,
`synthetic_engineering`, `SYNTHETIC_ENGINEERING_ONLY`. Such an amendment never
authorizes an ADMITTED campaign. Fixtures stay labeled synthetic and do not
fabricate a Root observation or real native author.

## Transaction and existing private gate

Both commands acquire the original campaign Journal lock. Under it, they
reload the original registration, proof, manifest, snapshots, method and
completion Refs. Every dependency is pinned before validation and checked
again immediately before append, including the raw copy pair. Binding also
rebinds the exact admission: even semantically identical JSON with different
bytes is identity drift. Any refusal leaves the original binding/barrier
unchanged; no ledger compensation or extra allowance is invented.

The companion guards canonical public regular-file paths before each body
open, including nested Ref paths in every JSON object it reads. At bootstrap,
direct copy diagnosis and locked reload it reads the registration through this
guard, preflights its nested Refs and the exposure/C-method JSON consumed by
the frozen validator, and passes that same parsed registration to unchanged
`u.validate`. It also preflights existing Journal metadata and invocation Refs
before the old uniqueness reader. It never delegates an unchecked registration
to `u.campaign` or `u.read`. An alias or forbidden path is rejected before the
old reader can attempt to open it; opaque strings are not followed as files.

Ref shape is checked before any delegated body open, even if a `path` object
has no digest. Every file-Ref position consumed by the frozen registration
validator and prior Journal invocation reader is checked explicitly, so a
missing `path` or wrong shape cannot bypass the guard either. The old Ref
contract remains compatible: `path` and a valid lowercase SHA256 are required;
`bytes` is optional and, when present, is checked for type/range and actual
length. Legal extra metadata fields are retained. Non-file relationship
metadata such as `copy_pair` digest/length is not mistaken for a file Ref,
and opaque strings do not cause file IO. The full original bytes and complete
Ref identities still govern the admitted copy relation.

`bind-original-slot` emits the established `original_bound` event only after
all checks. It retains the old event fields and adds the exact amendment,
pair and new tool identity. All old and new dependency Refs are retained in
`validated_refs`, so the old barrier still rechecks them. This is an audited
tool transaction, not a controller manually appending a substitute event.

The original `inspect-initial-barrier` and `open-private-evaluation` remain
unchanged. Six complete originals and a fresh independent nonauthor native
audit with exact fullFINAL/completed/raw evidence are still required before
Root opens the private stage through the original gate. An external audit
is separately counted; no Writer/feedback budget is reset. The companion
does not dispatch an auditor, open/read/hash/discover oracle files, or infer
quality from a barrier/SDK acceptance.

## Public commands

Run the reviewed immutable tool with an absolute Python and `-I -B`. Preserve
actual argv/UTC/stdout/stderr/exit, including failures. Placeholder names below
are descriptions, not executable registrations.

```text
PYTHON -I -B completion_copy_binding.py diagnose-copy
  --campaign ORIGINAL_UC --slot EXACT_A_OR_B_SLOT
  --proof ORIGINAL_PUBLIC_PROOF --proof-sha256 EXACT_SHA

PYTHON -I -B completion_copy_binding.py bind-original-slot
  --campaign ORIGINAL_UC --slot EXACT_A_OR_B_SLOT
  --proof ORIGINAL_PUBLIC_PROOF --proof-sha256 EXACT_SHA
  --admission ROOT_EXACT_AMENDMENT --admission-sha256 EXACT_SHA
```

Diagnosis returns `DIAGNOSIS_ONLY_NO_ADMISSION_NO_BINDING`. A binding returns
`ORIGINAL_BOUND_NO_PRIVATE_RELEASE`. Neither is content/professional/human
PASS. This tool performs no SDK/native/image calls and charges no experiment
writer turn. Its real controller and later audit overhead must still be
reported; historic failures and resumption costs remain.

## Engineering evidence

Focused tests use the existing recorder's explicitly tiny synthetic method
fixture seam only inside pytest. They reproduce the old exact-Ref refusal,
prove authorized same-body binding and unchanged originals, retain all
identity/chronology/receipt/uniqueness refusals, reject authorization/digest/
length/byte drift, and check final locked revalidation and the original six
slot barrier with unchanged C. Isolated import checks that no SDK is loaded.
Separate actual-public-data diagnostics read the preserved four original
A/B proofs without any admission, bind/private event or SDK/model/image call.
Independent review and Root's exact prospective amendment remain required
before use to bind the formal slots.

The first independent review found an unchecked transitive registration Ref
route before the original guard. Its original failure remains frozen. The
follow-up tests retain a permanent external Python open audit hook and cover
protocol/source/role/method/exposure Refs, nested JSON and aliases, direct
copy diagnosis, existing Journal invocation Refs and final locked reload.
Sentinel data is newly generated synthetic public test data; its digest comes
from known in-memory bytes. No sentinel body is read or hashed. The original
independent negative is replayed with only exact source/output fixture
bindings changed, preserving its audit hook and assertion.

Independent R2 found the path-plus-bytes/no-digest variant skipped by the
first fix. Its actual failed open-attempt test is preserved and separately
replayed before/after the second fix with the same permanent hook. Added
checks cover incomplete/invalid file Refs at original registration positions,
nested JSON, prior invocation entries and final locked reload, plus successful
two-field/extra-metadata compatibility through actual unchanged old validation
and a complete synthetic binding. No missing digest is repaired by the tool.
