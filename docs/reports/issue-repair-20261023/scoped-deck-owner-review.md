# Scoped preproduction owner follow-up

Reviewed runtime head `9aacfc08` against `59f4`, focusing on native forced
re-review `c9cc33a2`, scoped admission `9d08f79e`, semantic policy identity
`19e043b9`, and read-only reassociation explanation `ddeb5722`. Completed
2026-10-22 19:11 UTC. No real model, paid call or external project was used.

## Confirmed finding and repair

`preproduction_status(page_ids=['p1'])` retains an open deck-level finding
(`page_id=None`) from a historical review whose page dependencies only cover p2.
However, `_review_scope_owners(..., pages=['p1'])` discarded that owner because
its page dependencies did not intersect p1. Thus the dispatched repair packet
omitted the exact historical finding owner despite reporting the finding as a
blocker. A deterministic isolated historical-record fixture failed at the
missing-owner assertion before the change (`/tmp/runtime-review-probe.log`:
**1 failed, 26 passed in 6.53s**; the 26 existing checks cover the four reviewed
features). Parent authorized the narrow correction after this hypothesis.

Owner selection now includes an otherwise out-of-scope owner only if its required
unit has an unresolved deck-level finding and the requested scope contains a
current page. It uses the existing closure interpretation and exact immutable
review Ref, retaining review ID, finding ID, subjects and dependencies. Unrelated
units, other-page local findings and empty scope remain excluded. Closure checks
for unrelated local findings are not added.

This does **not** grant broader page authority or permit a partial manuscript
review to close a deck-level finding. Full current manuscript subjects/dependencies
and existing closure evidence remain required. A scoped task can now see and
preserve the relevant owner; any actual deck-wide closure still requires the
appropriately authorized complete re-review. No finding is automatically closed.

## Verification

New tests use clearly synthetic historical defect records and real scoped task
dispatch; they do not claim professional review acceptance. They cover both
must-fix and needs-judgment owner inclusion, exact frozen replacement enforcement,
unchanged immutable owner bytes, local/unrelated-unit/empty-scope exclusion,
partial closure rejection, and removal after a valid full-current-manuscript
accepted-variance closure interpretation.

```sh
PYTHONPATH=src:tests/rebuild /workspace/Deck-Master/.venv/bin/python -m pytest -q \
 tests/rebuild/test_scoped_deck_finding_owner.py \
 tests/rebuild/test_native_review.py tests/rebuild/test_native_review_recovery.py \
 tests/rebuild/test_selective_content_review.py \
 tests/rebuild/test_scoped_preproduction_eligibility.py \
 tests/rebuild/test_content_preproduction_review.py \
 tests/rebuild/test_review_policy_semantic_identity.py \
 tests/rebuild/test_rp24_readonly_diagnostic.py tests/rebuild/test_review.py
# Final code: 115 passed in 14.71s; /tmp/deck-owner-final.log
```

The other reviewed changes yielded no confirmed new safety bypass in this review:
forced native selection retains matching unit set/full page scope/current inputs;
actual native result acceptance retains authenticated execution and owner IDs;
semantic policy comparison strips only Ref/replaces/created_at while retaining
current applicability, evidence and other decision identity; reassociation
explanation remains read-only, unsupported, and explicitly checks no current
authority. This bounded review and synthetic regressions do not replace full CI,
live native execution or independent external review.
