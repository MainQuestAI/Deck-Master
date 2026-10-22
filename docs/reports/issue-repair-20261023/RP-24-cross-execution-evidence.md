# RP-24: cross-execution completed-image association — read-only diagnosis

Inspected source SHA: `dd424554284f881a1ce76c0f3323cbcbcc37bace`.
No product code, schema, or Skill changed. This report and four deterministic
regression tests retain the read-only investigation. No real sessions/HOME, secrets,
customer project, model or remote writes accessed. Synthetic tests write only
pytest temporary projects and explicit synthetic runtime directories.

## Conclusion

The existing stored facts can authenticate B's actual output and exact input,
and detect an already registered invocation within the current project. They
cannot generally prove that A did not also send, or that B did not already incur
a distinct/unknown consumption elsewhere. Therefore blindly associating B with
A's single consumed allowance is not a safe implementation using those facts
alone. This is a concrete missing send/ownership/accounting proof, not a generic
"needs real Host" or a visual-acceptance blocker. Correct-execution late native
proof enrichment is already implemented and is a different operation.

## What the code actually guarantees

- `generation.py:220-245` / `tasks.py:1746-1822`: call_begin commits a frozen
  request, A execution identity, allowance and started time; initial observations
  and output_refs are empty. It does not dispatch a transport or record an
  exclusive send token/negative send attestation. Identical in_flight state is
  possible before any transport and after an unobserved send.
- `observations.py:129-176,177-274`: owned Codex rollout proves selected
  thread/turn/item, successful PNG bytes, matching generated file and timestamps;
  restricted executed literal call + same-call return can prove prompt,
  transparent_background and ordered immutable references. It scans for a
  selected completion, not an exhaustive/fenced absence of A calls. Matching
  pixels/prompt do not establish that B belongs to A's authorization/allowance.
- `generation.py:313-316`: codex_session requires exact
  `attempt.execution_ref == codex:thread:turn` before collecting. B's real
  selector rejects for A; changing it to A loses genuine provenance.
- `native_image_evidence.py:85-135,154-258`: protected controller completion
  must bind exact project/request/task/attempt/begun ref/allowance/execution,
  exact input hash, prompt/references/parameters, current controls and actual
  installation identity. Output bytes and time are checked. B completion whose
  actual binding is B cannot be re-signed or relabeled into an A completion.
- `native_image_evidence.py:282-295` rechecks current binding when consuming the
  typed Runtime context. No public JSON can mint it. Settlement may preserve
  rejected evidence as host_reported; that cannot satisfy adoption.
- `generation.py:392-423` requires this Task's own request/attempt, consumed
  allowance, output SHA and tool-observed input match. Existing path does not
  represent “artifact from B reused under A while billing remains B”.
- `tasks.py:1840-1884`: terminal settlement cannot be overwritten; the stable
  invocation is checked against every allowance of every Task in the current
  project document. This is durable across registry/process restarts. Native
  bridge uses actual invocation if known, otherwise
  `native-host:<provider_id>:<event_id>`; Codex collector uses native item_id.
  This protects same-project duplicate registration under a stable identity.
- `native_image_evidence.py:138-143,244-248`: `_seen` event→claims/raw digest map
  is registry memory only. Restart does not compare newly verified claims to
  previously issued (but unconsumed) receipts. This is NOT proof that duplicate
  consumption succeeds: the project invocation guard remains active.

## Exact missing facts for the proposed A→B case

1. A send disposition: empty observations, unknown, in_flight, or a success in B
   do not prove “A never sent”. Even an absent A completion is insufficient.
   Current not_sent settlement is a Host declaration; it is not a controller
   fence guaranteeing no later A send. Need actual controller send journal plus
   a terminal/fenced A disposition, or retain A's unknown/consumed cost separately.
2. B ownership: need B's original event and original execution, plus a reliable
   link to the logical authorized job. A current matching prompt/asset sequence
   alone is not that link. A native B completion may have been for another Task.
3. Single consumption: current project ledger detects already registered stable
   invocation, including after registry restart. It cannot rule out B pending or
   consumed under host_reported evidence lacking invocation, provider aliases,
   another project/registry boundary or an unrecorded controller call. No global
   durable canonical physical-event ownership ledger is present in this code.
4. Current authorization: valid old input does not override current stop,
   cancellation, scope replacement, revoked authority or changed target. Existing
   guards must run again for any new association/adoption operation; a historical
   completion receipt is not authority to perform that new action.

## Safe bounded implementation shape (requires explicit proof contract)

Do not mutate Attempt A or rewrite B's receipt. Introduce an immutable
association record with two independent identities: intended logical request A
and actual execution/event B. Keep original raw receipt, output and frozen input
refs. A read-only preparation endpoint can already enumerate deficiencies and
conflicts without claiming readiness; it must not manufacture missing proofs.

For an automatic single-call association transaction, require ALL:

1. Authenticate B's original event and original executor; compare exact original
   prompt, ordered references and parameters against A's frozen input. Validate
   original timing, target, project and authorization scope, not just output SHA.
2. Authenticate an actual dispatch/handoff correlation from the trusted
   controller that ties B to A's logical job, plus a fenced terminal A not-sent
   disposition. Do not create this claim from caller JSON or retrospective guess.
3. Use a durable canonical physical-event key (not provider alias/output hash)
   and an ownership record across the controller's relevant project namespace.
   Existing B Task/allowance consumption must be reconciled explicitly. If B
   already belongs to another allowance, retain that owner; reject transferring
   it as a fresh A consumption. If disposition is uncertain, return a precise
   conflict and keep both call facts, not release one to fit the budget.
4. Within the project CAS/transaction, recheck current authority and exact target,
   record the association and canonical event reservation once, settle the
   actual single physical call exactly once, preserve the old immutable A
   execution and all prior evidence. Replays return the same association;
   contradictory mappings or newly changed basis reject. Any cross-store event
   ledger needs crash-safe reservation/commit reconciliation, not two unrelated
   writes whose race can double-consume.
5. Adoption references the association record and original B evidence explicitly;
   it never presents B as A's execution. Current review gates still apply.

This is materially different from today's late-proof enrichment of the same
Attempt/execution. It needs a versioned association/accounting contract and
trusted controller capability; existing receipt schema cannot silently acquire
these meanings.

## Smallest product decision, if that proof is absent

Choose whether to support **reuse of B's already-produced artifact while keeping
B's original accounting owner**, rather than attributing B's call to A. In that
mode A remains released only with actual not-sent evidence, otherwise unknown or
consumed; B remains separately accounted, even if this reveals two calls or an
unallocated past call. Current stop/budget/authority blockers remain visible and
cannot be erased by approval of the image itself. The operation must say
“associate/reuse external completed output”, not “A executed successfully”.

The necessary product choices are the permitted ownership/accounting boundary
(project-only vs controller-wide), treatment of already-produced unallocated B
calls, and whether new adoption may proceed while A's send disposition remains
unknown. Current conservative policy blocks new calls on unknown; it must not
be quietly changed. None of those decisions is a reason to fabricate a native
receipt, retroactively approve an unauthorized call or count two calls as one.

## Executed synthetic evidence

```sh
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -m pytest -q tests/rebuild/test_rp24_cross_execution_evidence.py
```

**4 passed in 1.07s**, `/tmp/rp24-readonly-analysis-tests.log`:
(1) begun with no send has in_flight/empty observation state;
(2) B selector rejects before collector under A;
(3) changed authenticated event claims reject within one registry but a new
registry has no persistent issued-event digest cache;
(4) separately, actual settled invocation remains protected against another
allowance by persistent project scan. Test 3 uses an explicitly synthetic
trusted adapter and does NOT assert a real provider changes its claims or that
second consumption succeeds. No production security configuration changed.

### Contract precision

`native-image-receipt.v1.schema.json` validates the outer receipt but leaves
`claims` as an object. Supplemental keys could therefore be serialized; that
is not supported handoff authentication. The actual trusted consumer requires
`claims.binding == image_binding(A)` and recognizes no separate B execution,
A send-disposition/fence, original dispatch-correlation, globally reserved
physical-event identity or explicit association transaction. The existing
strict generation Attempt preserves its one execution/allowance/request chain.
A new proof contract must define and validate those meanings rather than merely
allow extra JSON keys or sign retrospective claims from the caller.

Repository regression rerun: **4 passed in 1.21s**,
`/tmp/rp24-committed-evidence-tests.log`; Ruff and diff checks PASS. The duplicate
invocation check invokes the shared settlement validator against a genuinely
settled synthetic project; it is a precise validator-level test, not a claim
that a nonexistent second allowance was publicly allocated or consumed.
