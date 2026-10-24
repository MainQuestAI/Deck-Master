# Reproduce the fixed integration

Use the final review commit from sources.json and Python 3.12 (observed 3.12.14). Do not edit source while a suite or its child interpreters run. The original workspace's editable environment points at a different checkout and must not be reused.

Observed environments:

- Source: `/workspace/deck-integration-venv`, editable `/workspace/Deck-Master-integrated`, distribution 1.0.0.
- Wheel: `/workspace/deck-wheel-venv`, actual module `/workspace/deck-wheel-venv/lib/python3.12/site-packages/deck_master/__init__.py`, distribution 1.0.0.
- Actual wheel: `/tmp/deck-integration-stability/wheels-browser-fixed/deck_master-1.0.0-py3-none-any.whl`; SHA256 `fbe010395aa53f5c1e69bb86b55ed47c40fa2cd92541eb5195ab2b9e20b4b2dd`.
- Existing Chromium: `/usr/bin/chromium`. The denied browser download was not retried via another channel.
- Dependency cache: `/tmp/deck-integration-evidence/wheelhouse`. Loopback-safe fixtures remove ambient proxies; cached actual dependencies allow nested wheel/sdist installation tests to execute without bypassing those fixtures.

Run from the integration checkout. On a fresh machine, create separate source and wheel virtual environments and install the declared dev dependencies first. The commands below use the observed environment paths, not the original user workspace environment.

```bash
/workspace/deck-integration-venv/bin/python -m ruff check src/deck_master tests/rebuild
node examples/workbench/w10_poll_lifecycle.mjs
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/deck-integration-evidence/wheelhouse \
  /workspace/deck-integration-venv/bin/python -m pytest -q tests/rebuild \
  -m 'not browser and not render' --maxfail=15 \
  --junitxml=/tmp/source-full.xml
```

Build and install an actual wheel; no editable runtime is allowed in the wheel environment:

```bash
/workspace/deck-integration-venv/bin/python -m pip wheel \
  --no-deps --no-build-isolation -w /tmp/review-wheel .
/workspace/deck-wheel-venv/bin/python -m pip install --no-deps --force-reinstall \
  /tmp/review-wheel/deck_master-1.0.0-py3-none-any.whl
```

A rebuilt ZIP can have a different whole-wheel digest; record it and verify every packaged file and every tracked Git runtime blob. The checked-in runner does that before testing, preloads the installed parent before conftest inserts source, protects spawned children, audits imported submodules and static resources, and records package fingerprints after testing. It does not replace runtime implementations.

```bash
DECK_VERIFY_OUTPUT=/tmp/installed-unit \
DECK_VERIFY_WHEEL=/tmp/review-wheel/deck_master-1.0.0-py3-none-any.whl \
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/deck-integration-evidence/wheelhouse \
  /workspace/deck-wheel-venv/bin/python -I \
  docs/reports/unified-20261024/verify-installed.py \
  -q tests/rebuild -m 'not browser and not render' --maxfail=15 \
  --junitxml=/tmp/installed-unit.xml

DECK_VERIFY_OUTPUT=/tmp/installed-browser \
DECK_VERIFY_WHEEL=/tmp/review-wheel/deck_master-1.0.0-py3-none-any.whl \
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/deck-integration-evidence/wheelhouse \
  /workspace/deck-wheel-venv/bin/python -I \
  docs/reports/unified-20261024/verify-installed.py \
  -q tests/rebuild -m 'browser and not render' --maxfail=15 \
  --require-browser --browser-executable=/usr/bin/chromium \
  --junitxml=/tmp/installed-browser.xml
```

The latter selection deliberately records two actual-render browser cases as NOT_RUN locally, because rsvg-convert is absent. CI's fully provisioned browser job selects **all** browser tests, including those two, with skips failing the browser gate. Unit/pure-render/browser CI collection covers 4913 cases exactly once. Local exclusions are not CI omissions or passing evidence.

Available real PPT rendering (synthetic vector/text fixture, no model calls):

```bash
DECK_VERIFY_OUTPUT=/tmp/installed-ppt \
DECK_VERIFY_WHEEL=/tmp/review-wheel/deck_master-1.0.0-py3-none-any.whl \
  /workspace/deck-wheel-venv/bin/python -I \
  docs/reports/unified-20261024/verify-installed.py -q \
  tests/rebuild/test_render.py::test_ppt_renders_with_soffice_pdftoppm_chain \
  --junitxml=/tmp/installed-ppt.xml
```

Q2 is part of the complete unit suite. Its focused reproduction is:

```bash
/workspace/deck-integration-venv/bin/python -m pytest -q \
  tests/rebuild/test_rc3_q2_later_300.py tests/rebuild/test_q2_installation_v3.py
```

Keep the original 70 inner cases, 180-second deadline, zero failures/errors/skips and real `-I -B` identities. Preserve invocation, stdout/stderr, JUnit, execution-summary and all 61 runtime observations. Original v1/v2 campaign bytes remain frozen; active v3 tools have distinct hashes and do not inherit old controls' execution authority.

Both complete-source and complete-wheel sweeps at 2040ca6d proved that the original service startup failures disappear when parent and child load one frozen runtime. The independent BUILD_ID reproducer alters only a temporary copy, observes the mismatch at the unchanged health deadline, restores it and verifies recovery. Do not mutate the real checkout as a diagnostic during active tests.

The original autosave and upload-continuation failures, unsuccessful first corrections, collection/setup errors and interrupted broad starts are retained in the stability archive. Do not present an interrupted run or a narrow rerun as a full-suite pass.

The dependency-audited extended selection is reproducible with the same installed runner and these arguments:

```bash
-q tests/rebuild/test_native_notes_view.py tests/rebuild/test_native_table_geometry.py \
 tests/rebuild/test_native_table_path_evidence.py tests/rebuild/test_rc3_table_text_slack.py \
 tests/rebuild/test_rc3_design_native.py \
 tests/rebuild/test_export.py::test_cli_needs_tool_maps_to_exit_3 \
 tests/rebuild/test_install.py::test_doctor_step_isolation_and_host_truth \
 tests/rebuild/test_install.py::test_candidate_install_activate_and_run_doctor \
 -m render -k 'not test_actual_mixed_alignment_and_same_text_swap_renders_are_retained and not test_actual_svg_and_native_renders_retain_the_sample_and_hashes and not test_negative_source_and_native_renders_are_retained_with_located_readback' --maxfail=15
```

This actual attempt produced 74 passes and one blocked failure: the temporary candidate-install action indirectly requires the full renderer doctor and refused before activation because rsvg-convert is missing. Do not rerun or bypass that blocked action in this environment; provide the complete toolchain in an authorized validation environment first. The other selected checks and their actual native/PPT/notes artifacts remain valid bounded evidence. The five directly rsvg-dependent cases were identified before the selection, not removed after failing.

## #183 scope and measurement limits

[receipt-consumers.json](receipt-consumers.json) inventories 35 explicit owned SDK calls, four public compatibility boundaries and 16 historically frozen campaign calls. The active v3 carrier uses compact mutation receipts; Host instructions still require the full frozen context. Browser cancellation negotiates the capability and verifies task identity/terminal status through recovery reads.

Historical response-construction measurements at 1ea3ad22 used six synthetic sources (~16 KiB each), warm-up and three samples. For 1/13/30 pending tasks, legacy bytes were 230759/2993372/6907112 versus 1226 compact bytes; CPU medians were 2.463/36.436/81.110ms versus 0.037/0.044/0.064ms. These are response-construction measurements, not end-to-end Host latency, device temperature or final CPU acceptance. No actual Host, customer production, paid model, release or credential activity was performed.


Final installed-wheel measurements at test candidate 7947b25a (runtime b66cec18) passed 3/3 in 1.74s. Six synthetic sources each contain 17754 characters; one warm-up and three raw samples per protocol are retained. For 1/13/30 pending tasks, legacy responses were 230759/2993372/6907112 bytes and compact responses were 1226 bytes; JSON object reads were 9/105/241 versus zero. Legacy CPU medians were 3.738627/36.811266/75.847958ms versus 0.056237/0.048177/0.190684ms. All raw samples, including the 1.121228ms compact30 outlier, remain in installed-receipt-measurements.log and final-receipt-measurements/. This measures response construction only, not end-to-end Host latency, temperature or final CPU acceptance.

Additional installed-runner selections (use the same DECK_VERIFY_OUTPUT and DECK_VERIFY_WHEEL environment and isolated Python command above, giving each run a distinct output prefix):

```bash
-q tests/rebuild/test_pipeline_preview_reuse.py::test_assembly_reuses_current_preview_but_really_renders_ppt tests/rebuild/test_paused_exact_replay.py::test_real_assembly_then_pause_replays_without_compiling_or_writing
-q tests/rebuild/test_page_visual_gate.py::test_missing_preview_renderer_blocks_next_page_with_tool_reason
-q -s tests/rebuild/test_task_compact_receipts.py::test_receipt_scaling_same_workload
```

These selections returned 3, 1 and 3 passes respectively. The missing-renderer test asserts refusal; it is not a successful render. From an external working directory, `/workspace/deck-wheel-venv/bin/python -I -m deck_master capabilities` returned exit0 and installed resource readiness; context_ready remains false for compact receipts and the independent-review/human-review/verified-user-event flags remain false. Browser/render versions observed were Chromium151.0.7922.173, LibreOfficeDev26.8.0.0.alpha0 and Poppler26.05.0. Exact output and installation paths are retained in the evidence archive.
