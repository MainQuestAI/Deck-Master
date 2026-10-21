# Contributing

Contributions to Deck Master 1.x are welcome when they keep the local-first
workflow reliable, verifiable, and clear for outside users. The project is
licensed under [Apache-2.0](LICENSE); commits require the DCO sign-off below.
Use the [support guide](SUPPORT.md) and structured Issue forms for bugs, content
quality, feature proposals and documentation feedback. Follow the
[maintenance guide](docs/issue-maintenance.md) for triage, version selection and
Issue → PR → release tracking, and the
[security policy](SECURITY.md) for sensitive reports.

## Development Setup

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Before Opening A Pull Request

Choose collected tests that exercise the changed behavior. For an active
entrypoint or method-routing change, this is a focused starting point:

```bash
python -m pytest --collect-only -q tests/rebuild/test_package_boundary.py tests/rebuild/test_entry_capabilities.py tests/rebuild/test_rc3_early_methods.py tests/rebuild/test_rc3_content_methods.py
python -m pytest -q tests/rebuild/test_package_boundary.py tests/rebuild/test_entry_capabilities.py tests/rebuild/test_rc3_early_methods.py tests/rebuild/test_rc3_content_methods.py
python -m ruff check src/deck_master tests/rebuild
```

Add the relevant installation, schema, HTTP or business regression tests for
your change. `python -m pytest -q` and `python -m pytest -q tests/rebuild` are
whole suites, not focused checks. Record the exact command, candidate SHA or
dirty-tree scope, result, deselections and unavailable prerequisites.

The [Rebuilt Core Gate](.github/workflows/rebuild.yml) is the CI source of truth:

- Unit tests and Ruff: Python 3.11/3.12 × Node 22/24; unit selection excludes
  `render` and `browser` because they have separate required jobs.
- Real rendering: renderer-marked tests with librsvg, LibreOffice, Poppler
  and declared fonts.
- Required browser tests: Chromium with `--require-browser` so missing browser
  coverage fails. The same job builds and installs a wheel, then runs offline
  installed UI/download and recovery checks without editable resource borrowing.
- Group report: succeeds only when unit, rendering and browser jobs succeed.

For local readiness and migration diagnostics, use actual CLI entrypoints:

```bash
deck-master legacy-map   # confirms retired commands map or refuse explicitly
deck-master doctor --step render
deck-master capabilities
```

Missing tools, isolated installed-wheel checks, actual Host application and
professional acceptance are distinct evidence. A local focused pass does not
replace final CI on the published candidate, activate user HOME, or publish a
Release. Follow the [current increment](docs/specs/deck-master-next-iteration-20261019/README.md)
and its single execution ledger for candidate closure.

## DCO

This project uses Developer Certificate of Origin sign-off. Add a sign-off to each commit:

```bash
git commit -s -m "type: concise summary"
```

The sign-off means you have the right to submit the contribution under the project license.

## Pull Request Expectations

Every PR should include:

1. What changed.
2. Why it matters to the user.
3. Verification commands and results.
4. Known limitations or follow-up work.

Do not include private customer data, local absolute paths, credentials, logs, build outputs, or internal agent scratch files.

For a bug report, include the package version, relevant `doctor` result,
operating system and external Host/tool versions, plus a small neutral example.
Distinguish an unavailable Host, model account, renderer or font from a core
regression. Keep exact retries and project originals intact while investigating.


## Issue-linked changes

Link the actual Issue when one exists; a small documentation fix does not need
a placeholder Issue. Explain the root cause (or why still unknown), scope,
non-goals, verification, compatibility and documentation effects. Partial work
uses `Refs #<issue>`; use `Fixes #<issue>` only for a complete resolution targeting
the default branch. A merged PR is not a published release. Record the actual
release tag and associated Issue/PR links when the change ships.

For content quality, preserve authorized, sanitized input and before/after
outputs with version/Host/model settings and professional review reasons.
Automated checks are supporting evidence, not user acceptance. Reuse existing
[benchmark guidance](benchmarks/README.md) when promoting a representative case;
do not commit customer originals.

## Convenience entry points

After installing development dependencies, `make smoke` inspects the actual
CLI and runs package/entry checks. `make test` runs core unit tests; the
renderer, required-browser and installed/offline gates remain in the workflow.
`make preview REGISTRY=./deck-master-projects.json` starts the loopback launcher.
`make package OUT=<new-directory>` creates wheel/sdist/provenance; it does
not publish them. Legacy release and RC targets now stop with a retirement message.

## Retired container entry point

The legacy Dockerfile and Dev Container configuration are removed for 1.0.0.
Their [last mainline versions](https://github.com/MainQuestAI/Deck-Master/tree/44e9dd8bd96b9e52ac0acc4174b87f677d3c9bf6) remain in Git history.
They referenced the retired preview server and did not install the rebuilt
src-layout package correctly. A replacement image has not passed an actual
build and runtime check, so container support is not part of this release.
Use the Python virtual-environment instructions in [README](README.md#install)
and the [first-run guide](docs/getting-started.md) for the supported local CLI
and loopback Workbench. CI provisions its own renderer and browser dependencies.
A future container entry must validate installation, CLI startup and its stated
renderer/browser scope before it is offered as a supported path.
