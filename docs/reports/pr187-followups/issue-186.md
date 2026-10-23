# #186: original external findings survive repair handoff

Scope: the six acceptance requirements of issue #186, read in full. This increment reuses external_review_report.v1, explicit source bindings/import, existing authorization/CAS and the owner/replaces closure predicate. No second approval or repair state machine is introduced.

- AC1: `review record` packages actual caller judgments and complete finding context. Canonical report SHA + original review ID + finding ID distinguish two reports both called R01. Optional original_report_path retains original UTF-8 bytes and their separate SHA. Only newly marked imports receive deterministic namespaced IDs; historical imports/replay remain unchanged.
- AC2: `review repair-handoff` derives the complete original set and current explicit replacement closures. A synthetic six-finding test closes five while leaving F1 unresolved despite a generic pass. Final response guidance requires listing that unresolved impact.
- AC3: current manuscript and final observation stages remain distinct. Missing observations or a content-stage pass cannot close final visual findings. This is a contract regression, not actual rendered-PPT validation.
- AC4: recording/listing do not write projects; output must be outside source directories. Unavailable source/project still permits the fixed report's list; import retains actual source verification and authorization. Malformed finding context is rejected before evidence writes.
- AC5: engineering provenance, caller reviewer identity, existing independent proof, render and desktop observations remain separate. No model call is made. An unbound external finding is not automatically closed; existing observations remain in the report for subsequent binding/review.
- AC6: complete original expectations, unknowns, acceptance conditions, use impact and F severity travel to Master/Review. Guidance prohibits inventing capability, benefit or budget to close a finding. Deterministic preservation tests do not establish professional judgment quality.

New content packets include existing imported report findings as fixed, page-scoped context. Final findings remain final; old frozen Tasks are not silently expanded. No customer report, new model run, desktop session or external independent installation was used.

Independent read-only review found and verified repairs for missing finding_context at import and rejected-report evidence writes. Its final targeted result was 100 passed (including #138 and legacy imports). Fixed-HEAD package/install and combined follow-up verification are reported separately; neither this document nor two fixes certify the full 52-issue matrix.
