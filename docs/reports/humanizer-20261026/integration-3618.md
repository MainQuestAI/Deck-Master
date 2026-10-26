# Humanizer candidate on 3618f3d

Exact base: `3618f3d77d87e52042ccef50e70efcdc0d95b1fd`.
Preparation branch: `codex/humanizer-on-3618-20261026`.
Reapplied only Humanizer commit `7285bbff8c76a301189541e2a8cd79178445ab44`
onto the updated PR209 candidate. Both old branches (7285 and c6) are preserved.
No push, PR creation, merge, release or issue closure in this preparation.

The base's #140/#204 review/context fixes and #162 editable-output boundary
remain unchanged. In particular, deck-design/SKILL.md, content-to-visual.md,
production.py, content_review.py, review_import.py and static/v2/project.js
are byte-identical to 3618f3d. Humanizer does not modify the production prompt,
compiler scope or editable-vs-bitmap policy. New resource/Content/Review bytes
are unchanged from 7285; the optional selector, read-only and no-old-task-graft
boundaries remain. No upstream re-research or unrelated performance changes.

Verification: the same resource/current_work suites plus
`test_design_editability_prompt.py` and `test_perf_review_import_public.py`.
Final result: **142 passed in 46.54s**. Library checker, Ruff and whitespace checks passed.
Built fresh wheel/sdist and installed the new wheel in the owned isolated venv.
All 77 resource-inventory files match canonical source, wheel, sdist, installed
site-packages and managed-release extraction. Isolated reader outside checkout
returned the optional method with summary negotiation. Exact hashes are recorded
in package-verification-3618.json; earlier package-verification.json belongs to
724/7285 and is retained as historical evidence.

The earlier synthetic author sample and its limitations remain in sample-review.md;
it was not relabelled as a new independent review or repeated model experiment.
No new-head CI executed. Historical c6 CI failure and previous API denials remain
unresolved by this local preparation; no denied endpoint was retried. Publication
waits for the parent's final PR209 baseline confirmation. Parent coordinates the
independent review and any later merge sequence.
