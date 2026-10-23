# Optional Chinese PPT expression review

Base: `601f5ec68ae994fb42d933f672f0f495eb6d557b` (remote
`codex/issue-repair-20261023-ci-followup`, PR185 base branch, not main).
Branch: `codex/humanizer-zh-review-20261023`.
No unpublished `258fc33a3b63504b5652b846c686457024cd42dd` changes or old-thread
drafts were copied. Future integration may need a small Content SKILL text merge.

## Adaptation

Fixed source: blader/humanizer commit
`8c307f367c91bd974002f10f2be2965d642c13df`, SKILL 3.1.0, MIT.
SKILL.md, README.md and LICENSE were read in full; hashes and complete license
are retained in the canonical reference. No upstream scripts were executed or
third-party Skill installed. README preference experiments are not evidence of
Chinese PPT human-reader outcomes.

Select `expression-review-humanizer` through the existing selected_resource_ids
interface for a new content/review dispatch or independent read. Example:

```python
from deck_master.method_resources import read_skill_methods
report_context = read_skill_methods(
    'deck-review', review_units=['page_copy'],
    selected_resource_ids=['expression-review-humanizer'])
```

This only reads methods. Actual Review returns located findings and preserves
the source; Content needs existing write authorization and checks facts after
editing. Existing Task reads cannot add selection. No defaults, state machine,
new Skill, M11, mandatory gate, or author-detection score were added.

The reference includes seven fixed, explicitly fictional calibration cases:
32/80 is missing-model share rather than labor savings; preserve forecast,
scope, unverified status and no automatic writeback; preserve meaningful
contrast, three real options, bold, process arrows and Chinese quotes; remove
empty closers without removing necessary conclusions; never invent examples,
sources, attitudes or actors. These are authored expected boundaries, not
actual model outputs. Pure visual scope is rejected; outline work stays outline.

## Evidence

- Targeted suites: 95 passed (`test_expression_review_resource`,
  `test_rc5_resource_catalog`, `test_rc5_library_acceptance`,
  `test_rc5_host_selection`). New resource tests: 21.
- Library checker: PASS, 67 resources, four public Skills, 77 packaged files,
  37 local links, zero errors. Ruff and git diff whitespace check passed.
- Real wheel and sdist built. Canonical resource, wheel, sdist, isolated pip
  installation and managed-release extraction bytes matched SHA-256
  `45023e7cd2999904254c6dc50f12d32b6c6c6ea6fa1a7fd092c2ac1ca1c8247e`.
  Isolated `python -I` ran outside the checkout and resolved the installed
  resource from its own site-packages.
- Independent read-only sub-agent review: independently ran 21 tests and
  checked upstream hashes/license. Found an inaccurate first-party-only claim
  in THIRD_PARTY_NOTICES.md; corrected, then independently confirmed closed.
- Extended install/role/handoff suites: first run 41 passed, 3 failed,
  4 setup errors when nested pip could not resolve the package index. With a
  local wheelhouse and `PIP_NO_INDEX=1`, rerun reached 46 passed, 2 failed.
  Candidate activation stops at render doctor (`needs_tool`: rsvg-convert
  unavailable); full-chain test encounters an empty pending_tasks list at
  test_install.py:607. The same full-chain failure was reproduced on a
  separate unchanged 601f5ec worktree (1 failed, identical IndexError).
  Neither is counted as passing. Resource installation
  and byte checks above passed independently; full render/activation is not
  claimed complete.
- Actual model paired comparison: `not_run`; no model-effectiveness or human
  preference claim. Engineering checks are separate from semantic quality.

## Publication status at preparation

`git ls-remote` verified base SHA and that the new head name was absent.
The open-PR duplicate check (`gh pr list --repo MainQuestAI/Deck-Master
--state open --json number,title,headRefName,baseRefName,url`) was denied:
`Post "https://api.github.com/graphql": Forbidden`.
No alternate credential, identity or API was used to bypass that denial.
Draft PR creation and head CI require restoring the authorized GitHub API path;
the failed query is not evidence that no other Humanizer PR exists.
