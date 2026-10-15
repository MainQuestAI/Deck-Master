# RC3-03 private pilot entry delta review — round 3

**Verdict: LIMITED PASS for the one-field private-helper fix.** Actual positive init → feasibility → begin integration of this revision remains **NOT_RUN by this reviewer** and must be observed in Root's fresh run-02. No product, image, candidate, quality, human or desktop acceptance is granted here.

Reviewed script SHA-256: `4f51363e867cdc367416a4b665a7537db5f2d1fa1c343b73cab848187790e782`.

Reviewed readme SHA-256: `935973a34eff3af29e2fe626b6cd99a62a320a96f3b427260283ef1d3aa942ff`.

This review used the actual installed candidate interpreter `/workspace/work/rc3/candidate-03-8057905/prefix/.deck-master/releases/8057905162f2-dacfcf0ca168/venv/bin/python -I -B`. Actual imported SDK module path matched that candidate's manifest. Source identity: `8057905162f20926cfc1a0a96252bc6745f4e700`; wheel SHA-256: `dacfcf0ca16801d16c2dc082a2cde8e1041b6dc4054e4b2c3bfaac130a1a05a3`. This identifies the validators used and does not repeat or borrow Root's wheel admission outcome.

## Observed failure and the fix

Run-01 reached a genuinely accepted Request and then failed before grant commitment because `collaboration_authorization.stop_conditions[]` requires the identifier pattern `^[a-z][a-z0-9_.-]*$`; the private helper supplied a natural-language sentence. R2 checked API signatures and the style-input schema but missed this grant-record field. That was a limit of my earlier review, not a new product failure. Its original LIMITED PASS and the actual subsequent integration failure remain recorded without being relabeled.

I independently verified all **13** frozen original failure files against manifest `e4b6eff520568cdf2b7e220ddf37f412cf2c83fbea3d2f3c2c37d4fb416438f9`. Readonly inspection of the actual run-01 Store found that its current revision is still the exact recorded grant input's base revision and the successful Request response revision. Its authorization Ref list and Task Ref list equal the init Document's lists. This supports the specific observation that Request succeeded and the failed grant did not commit; it does not invent a passing image/counter result.

The script delta is exactly one literal replacement: the former prose `stop_conditions` list becomes `[]`. I independently compared the previous script bytes with that single replacement and obtained byte-for-byte equality with this revision. No other executable byte changed. The readme now documents that an empty code list avoids both schema misuse and invented automatic enforcement codes, while scope, actions, budgets, candidate-only policy, missing adoption permission, source note and fail-without-retry controls stay in their actual existing fields.

## Independent validation

My own `schema-probes.py` produced **9 passing assertions** in its final run. It did not use the preparer's schema probe results as evidence.

The probe evaluates only the reviewed method's pure AST expressions to obtain the exact scope/action/request/grant input shapes for feasibility and begin. It does **not** execute `request_and_grant`, replace an SDK function, run a writer or issue a request/grant. For shape validation it constructs explicitly labeled L1 prospective records and calls the actual installed SDK's pure `validate_collaboration_region` and `validate_authorization_semantics`. Prospective records are never stored in a project and confer no authority; current dependency-basis calculation, authorization effectiveness and transaction behavior are intentionally not claimed.

Observed results:

- Both prospective Request regions and grant records satisfy the installed schema and structural semantic validators. Explicit replacement names the original current open Request.
- All supplied actions exist in the actual installed eligibility action registry. Feasibility retains exactly `design.feasibility` and `design.propose`, design-only p04 scope and zero call/candidate ceilings. Begin retains its original exact seven actions, p04 design/blueprint scope and single call/candidate ceilings.
- Both scopes retain `page_manifest_ref=None`, no membership/order changes and exploratory purpose. Grant policy remains `candidate_only`, with no `candidate.adopt` action. The only stop-condition codes supplied are the empty list; no Runtime execution promise is invented.
- Reinstating the actual run-01 prose in the prospective record reproduces the actual installed validator's rejection at `collaboration_authorization/stop_conditions/0` with the same pattern constraint. This is a pure negative schema observation, not a second SDK grant attempt.
- Both actual-source pure style-input constructors validate against the actual installed `style_input.v3` schema with p04-only targets and zero references.
- The installed pure evidence resolver computes `host_attested` from the actual declared `host_attested_instruction`. No client assurance, verified-user receipt, presentation receipt or human assertion appears. Readonly source-note bytes in the actual run-01 Store match the fixed authorization note.
- The previous 107-file pure input and reviewed helper retained their hashes. No writer or tool was called.

## Evidence limits and probe correction

Public SDK writers: **0**. Tool/model calls: **0**. Actual helper entry executed: **false**. Positive Runtime integration for the fixed revision: **NOT_RUN**. Authority effectiveness: **NOT_EVALUATED**. The earlier full helper review's source-object check and API sequence are unchanged by exact byte comparison; this delta review does not retrospectively broaden their old evidence.

My first delta probe had seven passes and one harness failure: it looked for the note object in the pure input, although the note was actually added to run-01 by the accepted Request step. Its original `results-original-harness-error.json` and `probe.log` are retained. I changed only the probe's readonly note lookup to the actual run-01 Store; the corrected eight-case run passed. I then added the explicit readonly original-run-state check and reran the complete nine-case set; `probe-final.log` and `results.json` contain that final result. The harness lookup error is not attributed to the helper or product.

Root should preserve run-01 and use the fixed script only for a fresh run-02. Schema and static compatibility do not prove that the ensuing grant is effective, sample Task dispatch succeeds, input freezes correctly or the image tool runs; those remain actual integration observations to collect separately.
