# Contributing

Contributions to Deck Master 1.x are welcome when they keep the local-first
workflow reliable, verifiable, and clear for outside users. The project is
licensed under [Apache-2.0](LICENSE); commits require the DCO sign-off below.
Use the [support guide](SUPPORT.md) and structured Issue forms for bugs, content
quality, feature proposals and documentation feedback. Follow the
[maintenance guide](docs/issue-maintenance.md) for triage, version selection and
Issue → PR → release tracking, and the
[security policy](SECURITY.md) for sensitive reports.

## Development

[AGENTS.md](AGENTS.md) is the single source of development rules: setup, test
commands, branch and PR scope, verification, data safety and when to ask first.
It applies to human contributors and coding agents alike.

The repository is mid-rewrite. The new core and backend live in `rust/`, the
production tools in the standalone Python package `deck-tools/`, and the new
Skill in `deck-skill/`; see the [Rust rebuild plan](docs/specs/rust-rebuild/README.md).
The existing Python implementation (`src/deck_master/`, `skills/`, `tests/rebuild/`)
accepts only fixes for data loss, duplicate external consumption, failure to
open or export, and real security issues, each with a regression test.

The [Rebuilt Core Gate](.github/workflows/rebuild.yml) remains the CI source of
truth for the existing Python line. The workflow for `rust/` and `deck-tools/`
is added with the first Rust slice.

Pull requests and main pushes run the legacy tests only when a changed path
is outside `rust/`, `deck-tools/`, `deck-skill/`, `docs/specs/rust-rebuild/`,
and the new-line workflow `.github/workflows/rust.yml`.
Legacy changes run one unit configuration (Python 3.12 / Node 22), plus the
rendering, browser and installed-package checks. The full Python/Node matrix
runs weekly and through `workflow_dispatch`. Feature-branch pushes use the PR
checks instead of starting a duplicate legacy run. Group report still runs for
every PR and fails if change detection or any applicable check fails.

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

The dev extra includes `setuptools>=77` and `wheel` for the release builder,
which runs without build isolation (matching CI). After installing development dependencies, `make smoke` inspects the actual
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
