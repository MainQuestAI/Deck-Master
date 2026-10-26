# Second-review confirmed fixes (local only)

Independent review remains fixed at
`fdb8fca959a40d54e8cc2e4881533473a1838657`. This increment implements the supplied
confirmed findings; it does not repeat that review or infer 51-issue completion.
The existing RP24 commits `9b7a22f6` and `2e1c5ce4` are retained. No push or PR
update was retried after the earlier execution approval denial.

## Finding to implementation

| Finding | Integrated commit | Result and evidence |
|---|---|---|
| X1 / RP03 | `08f0ee9e6bf72f3e0ad80991eaa72208f8e78209` | Public plan/commit reproduces pass→not_evaluated and verified→blocked. Only a committed, matching zero-call SVG candidate-only plan can exempt a pending Task. Dispatch/start/candidate-ready/adoption covered; current writes, call facts and open findings still block. 16 new cases; matched 119 passed, 2 existing renderer skips. |
| X2 / RP06, RP18 | `1f630f81b68fdca2924d340a517ed944bc4d5629` | 16 failures reproduced before action/topic/negation repair. Both reader protocols permit legitimate Master coordination without granting write authority. 123 matched tests and 4 real clipboard→reader browser checks pass. See RP-06-X2.md. |
| X3 / RP08, RP22 | `7d6836520f954eda108c3c869b10c7c4e66dfe72` | Existing request completion projection governs plan actions in summary and both UI surfaces; missing images remain factual. Completed/incomplete plan, actual sample request and full_deck tested. 4 new API + 8 browser cases; 58 existing API + 3 browser checks pass. |
| X4 / RP01 | `b56cef23c963cf301057740660e298c1a63b9fed` | Pre-Task startup failures get fixed-category local diagnostics, phase/observed exit code/recovery hint; discovery keeps history distinct from current prerequisites and real execution. No raw stderr, fake Task or receipt. 14 new diagnostics tests, 72 matched tests pass; see RP-01-startup-diagnostics.md. |
| Isolated child provenance | `092bb984`, `2f6072cc` | Mixed installed parent/editable child deterministically rejected. Matching wheel parent/child roots and installed version checked without overriding -I. See R2-native-subprocess-provenance.md. |
| RP05, RP25 | `46b062c1adcd0a66171e762215a9ba06f8b91c63` | Real missing/stale preview rebuild tests added, NOT_RUN locally without rsvg. Matching 2e1c5ce4 source/wheel 30-page real browser workload completed; formal target Host/site remains unverified. See RP-05-RP-25-followup.md. |
| RP26 and RP00/27/29 mapping | `2c1ac56c087bb89e47e117f2d5eef27a78cfbec4` | 216 repeated cold/warm samples across three exact source snapshots and identical input versions; historical before/after full result equality retained. Later protocol-field differences disclosed. Historical test SHAs not rewritten as current results. See execution/RP-26.md and updated card reports. |

X3's first root browser invocation failed all eight new cases before page load:
the default Playwright cache lacked its expected binary. Existing RP18 cases
passed with the repository's installed Chromium selection. `0a789325` aligns
X3 with that same supported launcher, preserving assertions. It changes tests
only, not product behavior. Source and installed rerun results below supersede
that invocation, not its recorded failure. Logs remain in `/tmp/r2-integrated-browser.log`.

## Integrated validation

Product source snapshot: `b56cef23c963cf301057740660e298c1a63b9fed`.
Subsequent launcher/installed-gate edits are test-only; product/Skill bytes match.

- Source cross-regression: **139 passed, 8 browser deselected, 29.85s**.
  Files: native_review, native_review_startup, native_review_transport,
  review_channel_discovery, x3_design_plan_actions, rp06_design_completion,
  rp03_svg_trial_isolation, settled_image_reuse; pytest with
  `-q -p no:cacheprovider -m 'not render and not browser'`.
- Matching archive wheel: **281 package files byte-identical**, canonical Skill
  inventory verified; SHA256
  `917ab9e5aceb01886055bce897fbaec815fffedb6bb3a367dbfcd0d66e6bc49b`.
- Actual wheel installed in a temporary venv, invoked with `python -I`:
  same selection excluding the X3 browser file, **135 passed in 29.82s**;
  all **78** loaded runtime modules audited under that installation.
- Source X3 + RP18 Chromium: **12 passed, 4 non-browser deselected, 43.89s**.
- Matching installed wheel Chromium: **12 passed, 4 non-browser deselected, 42.58s**;
  all **64** loaded runtime modules audited under that wheel. Both invocations
  use `--require-browser`; no selected browser test was skipped.
- Ruff for source/tests/measurement/installed-gate scripts and diff check: PASS.
- Existing installed gate retains the new startup, SVG isolation and design-plan
  UI regressions (`8f1c75c1`), plus prior reuse and native provenance checks.

Local logs: `/tmp/r2-final-integration.log`, `/tmp/r2-final-installed.log`,
`/tmp/r2-final-installed-modules.json`, `/tmp/r2-final-source-browser.log`,
`/tmp/r2-final-installed-browser.log`. Wheel provenance:
`/tmp/deck-followup-b56cef23/provenance.json`. X3 screenshots:
`/tmp/x3-browser-proof/` (both routes, overview and current-work dialog).

## Remaining boundaries

No new remote CI exists: PR185 remains fdb8fca9. Its previous green runs are not
validation of this local increment. Earlier push denial remains in force and
this turn did not retry push/PR update or switch tools to bypass it.

Real rsvg rebuild/assembly positives are added but locally NOT_RUN because the
executable is absent; no substitute renderer or security change was used.
Formal target Host installation/site workload, RP24 real receiving Host, actual
image/independent visual acceptance and other card-specific specialist checks
remain separate. Local CJK blank-output diagnosis has not justified compiler or
font changes. No paid model/image batch, customer production, merge, release,
issue closure, credential modification or HOME/Host registration was performed.
