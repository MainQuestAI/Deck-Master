# Reproduction and evidence boundaries

Use Python 3.12 (observed 3.12.14), an isolated virtual environment, and the fixed integration commit. Never reuse the original workspace's editable environment: its isolated child imports a different source checkout and reports distribution `1.0.0.dev2` rather than this candidate's `1.0.0`.

```bash
python -m venv /workspace/deck-integration-venv
/workspace/deck-integration-venv/bin/pip install -e '.[dev]'
/workspace/deck-integration-venv/bin/python -m ruff check src/deck_master tests/rebuild
node examples/workbench/w10_poll_lifecycle.mjs
```

The ordinary test fixture removes ambient HTTP proxy variables for correct loopback behavior. In this cloud environment, nested pip then cannot resolve its package host. First run failures were retained; the retry uses an actual downloaded dependency wheel cache, with no skipped installation assertions:

```bash
/workspace/deck-integration-venv/bin/pip download --dest /tmp/deck-integration-evidence/wheelhouse '/tmp/deck-integration-evidence/wheels/deck_master-1.0.0-py3-none-any.whl[dev]'
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/deck-integration-evidence/wheelhouse /workspace/deck-integration-venv/bin/python -m pytest -q tests/rebuild -m 'not render and not browser' --maxfail=15 --junitxml=/tmp/deck-integration-evidence/full-unit-final.xml
```

Q2 retains its original inner 70 cases, the 180-second subprocess limit, no skip/error/failure acceptance, real `-I -B` interpreter identity and every production/control assertion. Historical v1/v2 executables retain their exact source SHA256; the migrated active carrier uses explicitly versioned v3:

```bash
/workspace/deck-integration-venv/bin/python -m pytest tests/rebuild/test_rc3_q2_later_300.py tests/rebuild/test_q2_installation_v3.py -q
```

The browser download failed with `403 Domain forbidden`. Do not retry that denied download through another channel. The supported local test option uses the already-installed real Chromium and preserves the CI default:

```bash
/workspace/deck-integration-venv/bin/python -m pytest tests/rebuild/test_method_preparation_browser.py tests/rebuild/test_rp10_content_browser.py tests/rebuild/test_studio_style_browser.py -k 'speech_clipboard or pending_current or plan_editor or imported_mapping or empty_pages' --require-browser --browser-executable=/usr/bin/chromium -q
```

Build an actual wheel, install it in `/workspace/deck-wheel-venv` with no editable runtime, preload `deck_master` before pytest's source conftest, then audit every imported `deck_master.*` path and the static resource directory against that installed package. The exact scripts, wheel hashes, package version, all imported module paths and JUnit results are in `/tmp/deck-integration-evidence/installed_probe_*.py` and `installed-identity-*.json`. Preloading is not a test implementation replacement: it selects the real installed package and asserts that no submodule was borrowed from `src`.

```bash
/workspace/deck-integration-venv/bin/python -m pip wheel --no-deps --no-build-isolation -w /tmp/deck-integration-evidence/wheels-75551e7d .
/workspace/deck-wheel-venv/bin/pip install --no-deps --force-reinstall /tmp/deck-integration-evidence/wheels-75551e7d/deck_master-1.0.0-py3-none-any.whl
/workspace/deck-wheel-venv/bin/python -I /tmp/deck-integration-evidence/installed_probe_75551e7d.py
```

`deck-master doctor --step render` returns `needs_tool` for missing `rsvg-convert`. Rendering and final visual/PPT meaning are not marked passing. No actual Host, paid model, private customer, release, credential or production activity is part of these synthetic validations.

## Compact response measurements (historical integration snapshot)

The first installed run at `1ea3ad22` measured the same six synthetic sources (about 16 KiB each), warm-up plus three samples, response construction only. These values do not prove end-to-end Host latency or device temperature changes. Final installed measurements are retained separately.

| Pending tasks | Legacy bytes | Compact bytes | Legacy median CPU ms | Compact median CPU ms | JSON reads legacy / compact |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 230759 | 1226 | 2.463390 | 0.037270 | 9 / 0 |
| 13 | 2993372 | 1226 | 36.436418 | 0.044109 | 105 / 0 |
| 30 | 6907112 | 1226 | 81.110472 | 0.064127 | 241 / 0 |

The native consumer regression forbids `_pending_host_tasks` during actual claim/checkpoint/accept orchestration; the browser cancellation regression checks sent protocol, returned schema/task identity and terminal status while retaining late-result rejection. The [consumer inventory](receipt-consumers.json) distinguishes 35 explicit owned SDK calls, four public compatibility boundaries, and 16 historically pinned campaign calls that were not rewritten. Current Q2 uses the migrated v3 copies; old controls do not grant new execution permission.
