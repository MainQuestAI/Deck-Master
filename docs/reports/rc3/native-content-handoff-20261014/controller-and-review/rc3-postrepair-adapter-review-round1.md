# RC3 postrepair verification adapter — independent engineering review

Reviewer: `/root/rc3_postrepair_adapter_review`. Scope is the controller adapter only. This reviewer did not execute the adapter against an actual project, write product code, author a manuscript, fabricate Native completion evidence, or assess actual manuscript quality.

## Current result

**CHANGES_REQUESTED**, pending the author's corrected version and an independent rereview. Initially inspected adapter SHA256: `5b1de61d5a5086cbdf98990c9237fa59b68365199baab23156da50e849fc894a` (754 lines).

The frozen driver and protocol were read and their current hashes match the original admitted values:

- `driver.py`: `f70a5d63a0da54e941e0e754af62988a37de87e58bad1ff651e9a7fc37947c23`
- `protocol.json`: `4fa26f301f817bb274586e8a18359d5ea598b670b28cf785bb46d785e3e14f67`

## Findings sent to the author

1. **PRV-01 — Fresh verifier completion was permitted to be unknown.** `native_completion()` allowed the restart-limited `unknown` marker for both historical exact-result consumption and a new independent verifier. Root expressly requires actual `completed` status observed through `collaboration.list_agents` before accepting a new verification. Historical retained FINAL evidence can carry its original narrower assurance; a new verifier must not inherit that exception.
2. **PRV-02 — A stale original blocker could escape the owner freeze.** `freeze_owner()` checked the new envelope and `preproduction_status()` only. The SDK's `_applicable_reviews()` omits stale reviews after manuscript changes. Thus a fresh pass with `replaces=null` could satisfy the gate while an original open `must_fix`/`needs_judgment` lacked an explicit closure. The freeze must check every prior blocker, including its stale original owner, through the existing central replacement/closure semantics. A model chooses its actual observations, evidence and resolution; the controller must not supply them.
3. **PRV-03 — Interpreter admission was not explicit.** The adapter checked module path inside `sys.prefix`, source and wheel metadata, but did not bind the admitted exact interpreter path. Root's new A/B installation record must include the precise interpreter used for every command and reviewer instruction.
4. **PRV-04 — The original-preservation snapshot omitted repair stages.** `originals()` captured only `0*-*` stages although `accept-existing-speech` also supports `repair-speech`. Its original result/refusal/observer must enter the unchanged-evidence snapshot before recording `original_refusal_preserved=true`. Writer-provenance observations should also validate the full canonical spawn/FINAL/claim/method/completion binding rather than only sender/hash fields.

The author acknowledged PRV-01/02/03 and is implementing corrections. No PASS is asserted for the inspected version.

## Positive checks in the initially inspected version

- New source/wheel/module admission is separate from the frozen arm registration, with an explicit hashed transition and `not_original_frozen_E1` classification.
- New verification writes are confined to a separate `verification/` tree with exclusive file creation; no fallback manuscript is manufactured.
- A fresh formal Review Task is dispatched through the installed SDK. The verifier receives full current objects, prior Review records and hashed actual scope evidence; instructions keep actual human use tests as `NOT_RUN` and distinguish estimated feasibility (AC-M03) from actual timed delivery (AC-U03).
- Root's registered protected-transport provider is bound through `ProviderRuntime`; receipt contexts are opaque. Only independent-model receipts are exposed, while verified-user and human capabilities remain false.
- Ordinary JSON contexts, changed results, foreign Task replay, and every actual author identity have explicit negative-control paths.
- Exact old speech consumption retains its old refusal, does not create a new Native output/claim, and separately labels the new SDK's acceptance. This does not change the original frozen effect result.
- The actual current SDK gate is a necessary owner-freeze condition. Open advisory/F3 suggestions can be retained without a fabricated repair.

## Review limits

This is an engineering review of evidence transport and formal gating. It cannot establish actual content quality, frozen A/B effect success, human Owner acceptance, timed delivery, editable PowerPoint behavior, or RC3 release completion. New admitted A/B installations and actual Native verifier execution remain Root's separate work.
