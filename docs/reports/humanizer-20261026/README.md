# Humanizer integration candidate on PR209

Latest local base adaptation: [3618f3d checkpoint](integration-3618.md).
The 724/7285 results below remain historical and are not relabelled.

Date: 2026-10-26. Exact base: `7244477a240002ba5365e0283713e8096778c72f`.
Local branch: `codex/humanizer-on-pr209-20261026`.
The parent is coordinating PR189 → PR209 → Humanizer; PR209 is not treated as
merged or final. Push and PR creation wait for the parent's final-base decision.

## Scope and provenance

Reapplied only the unique Humanizer increment from
`c6a79ffa8d4d8f3e999555b82f486faa33cd7159`; the old branch is preserved.
Content and Review retain all current_work, co-creation, external-review record
and authorized repair instructions inherited from this base. Added only an
optional selector reference and its catalog entry, license attribution, tests
and evidence. No runtime, Q2 performance code, workflows, mandatory gates,
additional public Skill, M11, automatic correction or issue state changes.

Upstream remains blader/humanizer 3.1.0 at
`8c307f367c91bd974002f10f2be2965d642c13df`. Re-fetched the three pinned files
and verified their hashes against the canonical reference; the full upstream
MIT notice matches byte content (ignoring trailing whitespace only for the
embedding comparison). Source SHA-256 values themselves cover exact bytes.
No upstream installation or scripts were executed.

## Current candidate engineering checks

- 133 passed: test_expression_review_resource.py, test_rc5_resource_catalog.py,
  test_rc5_library_acceptance.py, test_rc5_host_selection.py, test_current_work.py.
- Added a project-backed read regression with work_context.v2 and explicit
  workbench_summary.v2: current_work is returned, selected resource is present,
  and the stored Document is unchanged.
- Existing coverage retains optional-only dispatch, visual/design rejection,
  old Task no-supplement, hash-drift detection, four Skills and ten method cards.
- Library checker PASS: 67 resources, 77 packaged files, 37 local links,
  no errors. Ruff and git diff --check passed.
- Real wheel and sdist built; all 77 inventory files match canonical source,
  wheel, sdist, isolated pip installation and managed-release extraction.
  Python -I outside the repository resolved the installed package and read the
  selected resource with current summary negotiation. Exact archive/resource
  hashes are in package-verification.json. This is not full render/activation.

## Actual non-customer sample application

sample-input.md is an explicitly synthetic two-page training-signup example
plus outline and visual-only scopes. sample-review.md records this session's
actual author application: located findings, proposed rewrites, protected
facts/qualifiers, retained structures, missing visual observations and a
fact-by-fact check. The original input is retained and its hash is recorded.

This is host_self, not an independent review receipt or paid/model subprocess
run. It shows the actual handling of this sample, not a preference score or
proof of general language improvement. Paired model comparison, independent
review and human-reader evaluation remain not_run. Parent coordinates the
independent review; old review approval is not reused as this candidate's gate.

## Historical failures and pending actions

The original 2026-10-23 report remains historical, not current test evidence.
It records 95 targeted passes and extended tests 46 passed / 2 failed: missing
rsvg-convert at activation and an empty-pending-tasks flow failure reproduced
on original 601. Those extended suites were not rerun in this integration.
Parent monitoring reported c6a79ff push run39929391288 failed at the 180-second
Q2 child (3902 passed / 1 failed / 2 skipped). Its log was not independently
retrieved: the Actions API returned Forbidden. Neither a Humanizer regression
nor a runner cause was established. This candidate does not claim to repair it
or inherit PR209 CI success. New-head CI is pending, not passed.

Prior denied actions: GraphQL open-PR listing and Actions run39929391288 lookup.
Neither was retried; no credentials, identity, app or alternate endpoint were
used to bypass denial. The parent now reports no Humanizer PR exists. Local
preparation is complete; publication still requires final PR209 base confirmation
and a usable authorized PR API path. No merge, release or issue closure performed.
