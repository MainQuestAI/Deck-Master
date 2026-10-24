# RP-24 bounded settled native-image reuse

Refs #184, #185, #134, #135. Implementation baseline remains
`55adc97c5bb5f16ae7fcff7c33c43969fae9ce97`. Independent prior review baseline:
`fdb8fca959a40d54e8cc2e4881533473a1838657`. New implementation commit:
`9b7a22f6f263f217a66c520c8c6ea4a5c08841c1`.

Explicit user authorization received 2026-10-23 02:29 UTC permits implementation,
tests and push to the existing PR185. It permits reuse while retaining both
execution identities and actual consumption, not a single-call transfer.

## Contract and boundaries

`generation_result.reuse_from` selects an existing same-project source Task,
Request and Attempt. Both distinct non-trial blueprint executions must already
be consumed; project-wide unknown/in-flight calls block adoption. Source B must
have persisted protected native-controller observation, original receipt/event,
and exact original bytes. Arbitrary paths, externally supplied receipts or
caller-created association provenance cannot authorize reuse.

Frozen inputs match except independently validated basis. Both Tasks retain
current input, scope and original authority checks. Destination A explicitly
negotiates `settled_image_reuse_v1`; existing A may add this optional capability
under its original execution without rewriting its frozen required contract.
Explicit current `generation.reuse` authority and within-scope adoption are
required. Current ancestor usage cannot exceed its ceiling; zero new calls may
reuse at an exhausted but not exceeded budget. Neither original consumed call
is refunded, relabelled or counted as the other.

The existing result transaction stores `generation_reuse.v1` and promotes the
writer floor to `settled-image-reuse.v1` only on successful commit. Original
Requests, Attempts, receipt and call ledgers stay intact. Artifact provenance
keeps B as generator and the immutable association names A as result owner.
Historical reading validates that association, without renewing authority.
V1 rejects later accepted Attempt-version substitution rather than silently
changing evidence. Replays use the existing operation contract and CAS.

Single-call handoff, unregistered external B, missing native source evidence,
trial reuse and unresolved A remain unsupported. No send-fence or A-to-B
transport proof is manufactured. Real Host/model/visual acceptance is NOT_RUN;
all image fixtures below are synthetic protocol evidence.

## Validation

- New `test_settled_image_reuse.py`: 28 cases, including positive identity and
  two-call preservation, missing proof, inputs/output mismatch, unknown/in-flight,
  cancellation/late result, superseded source, missing capability, revoked or
  paused authority, lowered budget, replay/conflict, CAS and lost-response recovery,
  old writer boundary and explicit existing-execution capability negotiation.
- Matched generation/native/recovery suite: **117 passed in 53.02s**.
- Independent integrated consumers: **135 passed in 54.87s** using
  `test_rc3_adopted_design_handoff.py`, `test_rp20_original_review.py`,
  `test_page_detail.py`, `test_package_boundary.py`,
  `test_install_preparation_compatibility.py`, `test_rc3_resource_inventory.py`,
  with `-m 'not render and not browser'`.
- Exact implementation-commit archive wheel built and installed without network:
  **280 package files matched**, canonical Skill inventory verified; wheel SHA256
  `0ae63572132d6cfb775cbd41aae99c1c853be699fcdf5f5fcdb5d247c805f9ef`.
- Actual installed package: `test_settled_image_reuse.py` plus
  `test_generation_protocol.py`: **43 passed in 17.12s**; all **63** loaded
  `deck_master` modules audited under the isolated installation.
- Cross-runtime synthetic public-path checks created B, then both A/B under
  `fdb8fca9`; upgraded reader rejects absent reuse capability, permits explicit
  original-execution negotiation, preserves old frozen identity/input/call fields
  and B Task, and adopts without a new call.
- `ruff check src/deck_master tests/rebuild`: PASS. Existing installed CI regression
  list now includes all new reuse tests; no checks, assertions or limits removed.

Local evidence: `/tmp/rp24-matched-regression.log`,
`/tmp/rp24-integration-consumers.log`, `/tmp/deck-followup-9b7a22f6/provenance.json`,
`/tmp/rp24-upgrade-both/old.json`. Exact final-head CI will be recorded in PR185;
prior fdb8 push/PR success is not substituted for new-head validation.

No paid model, customer production, real HOME/Host registration, credential or
security changes. Local librsvg installation remains blocked independently;
remote renderer success does not imply local installation. RP24 still requires
real Host scenario acceptance, and no claim closes all 51 issues.
