# #138 / RP11 cross-PR follow-up

Baseline: PR187 5a245de64e82a5c1031cdcb69c3aa63ef011359b. Original ownership was PR185/RP11; this repair belongs to PR187 and does not modify PR185's branch or historical evidence.

Ordinary manuscript source findings now include source association/version/locator semantics. Speech source findings retain both source and actual notes/segment semantics. Other content findings do not close merely because source metadata changed. Fixed source findings require current manuscript evidence; owner, finding identity, replaces, current dependencies and same-page checks remain. The existing accepted-variance contract is unchanged.

Regression: test_source_finding_repair.py covers page_copy/speech/whole manuscript, locator-only and notes-only changes, no change, another page, metadata, old evidence/dependencies and wrong identities; positive cases also use the real review receiver. These are synthetic Store/receiver tests, not a native model review.

Independent read-only review identified a speech regression during development; the final candidate includes the source+speech union and preserves that failure as development evidence outside the repository. Full fixed-HEAD build/install and the combined follow-up regressions are reported separately. No claim that all original issues or actual model/visual quality are accepted.
