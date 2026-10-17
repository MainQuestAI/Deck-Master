# Scoped terminal reconciliation companion (S05)

This separate tool exposes the frozen common reconciliation event contract for
one exact scoped key. It never retries, grants authority, plans a new change,
commits business data, starts a Task, calls an image/model, adopts or exports.
The original registration, ledger, errors, raw returns and caps remain in place.
Independent review and Root's prospective admission are required for formal use.

Run the reviewed, hash-pinned tool using the original own managed installation:

```text
OWN_ABSOLUTE_PYTHON -I -B scoped_terminal_reconciliation.py
  --run ORIGINAL_SCOPED_RUN
  --admission ROOT_ONE_KEY_ADMISSION --admission-sha256 EXACT_SHA256
  --out NEW_PUBLIC_EVIDENCE_DIRECTORY
```

The command supports only `q3q4` runs and original `changes.commit` failures or
their failed `operations.show` queries. It accepts no caller-selected API,
callback, observation result, retry or state override. Other unresolved writes
block it. Failed same-ID `operations.show` keys can remain while the original
business key is reconciled; each old query key then needs its own admission.
There is no clear-all. A previously settled key cannot be reconciled again.

The admission JSON has `format: rc3-scoped-terminal-admission.v1` and
`action: observe_one_scoped_terminal_intent_no_retry`. It binds:

- Original `status`, `root`, `slot`, `project`, `arm`, `scope_slot`, `whole_run_id`.
- Exact ordinary FileRefs for `tool`, `scoped_recorder`, `common`, `registration`,
  `run_manifest`, original `intent` and `failure`. FileRefs contain canonical
  absolute `path`, `sha256`, and optional nonnegative integer `bytes`; the
  admission dependency fields themselves must equal the tool's full FileRefs.
- Original `installation` fields `python`, `module_file`, `source_sha`,
  `source_tree`, `manifest`, `wheel_sha256`; the unchanged recorder additionally
  verifies the entire original installed package inventory and managed identity.
- Exact `operation_key`, `operation_id`, original `arguments`,
  `arguments_sha256` (SHA256 of frozen common `encoded(arguments)`),
  `project_id` and `expected_revision`.
- For `changes.commit`, `plan_outcome` is the exact old public plan outcome Ref,
  and `request_digest` is the own Runtime's canonical digest of that original
  project/operation/base/plan. The tool independently derives it from the old
  outcome and validates the plan's canonical content hash. For a failed
  `operations.show`, `request_digest` must be null; it cannot claim a commit.
- Actual fresh timezone-aware `observed_at_utc` after the original failure.
  An ADMITTED run requires `observer_id: /root`, `assurance: host_attested`, and
  `evidence_kind: ROOT_ACTUAL_PROSPECTIVE_SCOPE_AMENDMENT`. ENGINEERING requires
  `/engineering/rc3-s05` and `synthetic_engineering`, and cannot authorize an
  ADMITTED run. These records are Host bookkeeping, never platform signatures.

Within the existing controller/resource/Runtime locks, the command makes fixed
own-public queries: `view.project_view`, `collaboration.describe`, all pages of
`run_desk.listing` at the admitted revision, then same-ID `operations.show`.
The first two use the existing public-operation readers; `run_desk.listing` is
the existing public Run Desk reader, explicitly exposed only here as a fixed
same-project read. Every actual call uses unchanged
`s.resource_session`/`s.perform(query=True)` and charges the original arm pool
once, including failures. SDK cap refusal before dispatch creates no call.
There is no retroactive fee for a past call that did not occur.

`not_found` requires an actual own `OperationError` with exact ID, code
`operation_not_found`, `operation_state=not_found` and HTTP 404, plus matching
live project/revision and readable Task call facts. For a business key, the old
error must be the supported `EligibilityBlocked` at `eligibility/change.commit`
and current must still equal the original base, establishing this precommit
refusal. Bare 404, timeout, unavailable/unknown, a changed base, unreadable state,
reserved/in-flight/unknown calls, running Tasks or other unresolved mutations
preserve UNKNOWN. Completed spent calls remain spent. A verified own committed
receipt is accepted only with the exact original ID/request digest and matching
current revision; caller-supplied committed JSON is never consumed.

Full query arguments, returns or typed failures, own identity, argv and real UTC
are saved exclusively. New failed reads receive individual reconciliation
records: supported typed not_found queries are readonly terminals without any
business commit assertion; other failed reads remain UNKNOWN. The original key
gets a separate frozen-common record. Exact admissions/dependencies are reloaded
and all evidence is checked before append. A later refusal retains all raw query
evidence and unresolved keys; use original `status` to inspect each key.

Exit 0 means `recorded_no_retry`; exit 3 means `still_unresolved`; exit 2 means
refused/uncertain input or execution. None is content, professional, native or
human PASS. Only after all necessary keys are settled may Root separately record
a real authorization, reread current state, plan again and use a new commit ID.
Fidelity/preproduction gates and the original one-candidate/one-call/zero-retry
P5 limits remain ordinary Runtime decisions. This command does not implement
the other Runtime gaps or orphan-review recovery.

Source tests use explicit neutral ENGINEERING fixtures; installation admission
is the sole source-suite seam. Public grants/fidelity/call-begin setup and the
transport-lost response fixture are labeled L1 engineering, never native or
image execution. The separate managed CLI trace uses the real original package,
complete installation admission and `-I -B` with no installation seam.

The standard pytest entry `tests/rebuild/test_rc3_scoped_terminal_reconciliation.py`
now runs the unchanged 45 substantive cases in an actual `-I -B` child process.
The carrier `tests/rebuild/rc3_scoped_terminal_reconciliation_cases.py` is excluded
from automatic filename collection and can also be run explicitly with isolated
pytest. The ordinary outer suite has three checks: the complete 45-case child
run plus two actual CLI flag refusals. Child JUnit must contain all 45 successful
unique cases and no skips/errors/failures. Actual argv, UTC, stdout, stderr,
exit and Runtime flag observations remain in the pytest temporary directory.
This harness change preserves the production guard and does not relabel CI508.
