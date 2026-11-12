# Deck Master

[English](README.md) | [简体中文](README.zh-CN.md)

Deck Master is an AI-native workbench for developing and presenting business
solutions. It helps solution architects, proposal authors and presenters turn
complex material into clear, coherent decks grounded in real requirements and
product capabilities.

## Philosophy

A strong deck starts with business judgment: what needs to be said, why it
matters for this task, and how the parts fit together. Our aim is to help authors
understand the problem, find an organizing idea, and develop it into an
explanation that makes complex ideas clear and abstract ideas concrete.

Three principles guide the product:

- **Purpose shapes the story.** The author's task determines the central message,
  emphasis and content choices; the audience's knowledge guides how to explain them.
- **Understanding gives content its structure.** A useful business framework
  connects requirements, capabilities and scenarios, and carries through the
  whole deck and its spoken delivery.
- **Visuals do explanatory work.** Words, diagrams and examples make
  relationships, processes and tradeoffs visible. Formats and production tools
  serve that purpose.

These principles guide product development. The current workbench connects
content planning, editable SVG/PPT production, review and revision through the
`deck` CLI and a local Web UI. See the [capability boundaries](#capability-boundaries)
for current implementation limits.

**Version:** `1.1.3` (Rust CLI `deck`, Python file tools `deck-tools`, WebUI).
Source version, built artifacts, an active install and a published GitHub
Release are separate facts. Start with the
[installation and first-run guide](docs/getting-started.md). See
[1.1.3 release notes](docs/releases/1.1.3.md) for changes and known limits. **License:** Apache-2.0.

The current authoring path is the Rust core in `rust/`, file tools in
`deck-tools/`, the WebUI in `frontend/` served by `deck serve`, and the Codex
Skill in `deck-skill/`. A plain material directory is enough to start; no PPT
Master backend or slide library is required. The previous Python workbench
and its official exporter have been removed from the repository.

## Who It Is For

Deck Master is built for people who explain business solutions: solution
architects, consultants, proposal authors, bidders and presenters. It supports
their work from understanding source material and shaping the narrative to
producing, reviewing and revising the deck.

## Install

Rust 1.88 or later is required; Cargo checks the declared minimum. File tools
use Python 3.11 or 3.12 (3.12 in CI and in `scripts/install.sh`). Package
metadata for `deck-tools` allows 3.13 and excludes 3.14.

From a source checkout:

```bash
./scripts/install.sh
```

The script prepares a complete directory under `<prefix>/share/deck/installations/`:
the CLI with embedded WebUI, a non-editable deck-tools venv, and copies of all
four role Skills and shared resources. `<prefix>/share/deck/current` selects
that directory; `<prefix>/bin/deck` resolves it once and executes its real binary.
Preparation failures leave the current installation selected. Upgrades retain
old directories, so existing processes keep their tools. The venv is created
in its final location and never moved. This installation is independent of the
source checkout; Python itself, fonts, renderers and the external Host remain
system prerequisites.

By default the script links `deck-master`, `deck-content`, `deck-design`, and
`deck-review` into `~/.codex/skills`. Each link points to a complete role
directory in `current/deck-skill/`, with a regular `SKILL.md` and links to shared
`references` / `assets`, so Codex can discover it. `--skills-root DIR` changes
the skill directory. `--prefix DIR` sets the CLI install root; `--dry-run`
prints the plan without writing. The compatibility entry `deck` is no longer
installed, and `--skill-dir` has been removed.

Rerunning removes only a leftover `deck` symlink pointing at this source's
`deck-skill/`. Old role wrappers containing exactly the three managed links
are upgraded to links through current; existing current links are kept.
Wrappers with extra files and other same-name entries cause exit 2 before
any writes, with the path and target printed. If old Python-line links occupy
these names, move those links away first (remove only the links, never their
target directories), then rerun. An unmanaged `deck` is preserved with a
warning that it may compete with the four role entries for triggering.
A new shell keeps its own PATH. If `command -v deck` is not `<prefix>/bin/deck`, call `<prefix>/bin/deck` or put `<prefix>/bin` ahead of the other entry. A non-default prefix writes that absolute path into the installed commands.md.
Steps are in the [install guide](docs/getting-started.md#install-from-source).

After install, follow the [Quick Start](#quick-start) to make your first deck.

Standard installation and upgrades use `scripts/install.sh`, without
`DECK_TOOLS_PYTHON`. Unknown CLI entries are preserved and reported as conflicts;
Cargo records plus the associated built artifact identify supported old installs
without executing unknown binaries.
Old venvs and source links are retained for old processes during migration.

Development in a worktree (do not reuse another checkout's venv):

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e "./deck-tools[dev]"
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
cargo install --path rust --root "$PWD/.dev-prefix"
export PATH="$PWD/.dev-prefix/bin:$PATH"
(cd frontend && npm ci && npm test && npm run build)
(cd rust && cargo test)
```

## Import an existing archive

The old Python workbench, the `deck-master` command and its `legacy-export`
exporter have been removed. There is no longer an official exporter for old
projects. Historical instructions are in the published
[1.1.0 release notes](docs/releases/1.1.0.md#upgrade-and-migration).

`deck import <archive> <new>` still imports an existing `legacy-export.v1`
archive into a new directory. The archive is read without modification.

## Quick Start

1. From this checkout, install with `bash scripts/install.sh`; see [Install](#install)
   and the [install guide](docs/getting-started.md#install-from-source). Ensure `deck` is on `PATH`.
2. Open Codex in this checkout and type:

   > Make a 6-page deck from examples/first-run/en/material.md following examples/first-run/en/brief.md, in ./first-deck.

   The [sample](examples/first-run/README.md) is fully synthetic. The four Skills run the commands.
3. View the draft with `deck serve ./first-deck`. It binds `127.0.0.1` and prints the URL to open.

`deck-master`, `deck-content`, `deck-design`, and `deck-review` share
`references/` and `assets/` and call `deck`. Further commands are in
[deck-skill/references/commands.md](deck-skill/references/commands.md).

## Workbench

`deck serve <project>` starts the local UI for that one project, prints a
loopback URL, and serves the embedded WebUI. Host or Origin that is not this
process's loopback address is rejected. There is no login or session token.

The UI shows the overview and gallery (originals, compiled previews, stale
marks), copy and speaker-notes editing, open reviews, run status and cancel,
candidate comparison and manual adopt, build and Markdown/PPTX download, and
version restore. The browser does not start image or SVG runs; the Host uses
`deck run` on the CLI. The UI does not list every project: one `deck serve`
process serves one project.

Keep the printed URL private. The server binds `127.0.0.1` only.

## Capability Boundaries

1. Produced PPTX contains editable shapes and text. Supported tables explicitly
   marked `data-native-table="true"` with complete grid and ownership bindings
   become native PPT tables; ordinary drawn tables remain shapes/text. Charts
   are not Office-native spreadsheet-backed data charts.
2. Incomplete work can be saved, exported as Markdown, and built. Missing or
   stale SVG pages are listed next to download; export is not blocked.
3. Cancelled runs and results whose page basis has changed are stored and not
   adopted automatically. A later result for the same run page is an explicit
   candidate.
4. Renderer and font gaps surface as exit code 3 (`needs_tool`) with the
   actual reason.
5. Reviews are stored on the version at add time. The UI writes human reviews;
   CLI `self_check` is the current Host's own check.

The 2026-11-04 maintainer check is in the
[1.1.0 release notes](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04).

## Diagnostics

```bash
deck doctor --fonts 'Source Han Sans SC'
```

Checks the deck-tools interpreter, `soffice`, `pdftoppm`, `fc-match`, and the
named fonts. Missing tools keep the real reason; nothing falls back to a
fixture.

## Project Docs

Start with the [documentation index](docs/README.md). Historical reports do not
certify the current source line; see the [archive index](docs/archive/README.md).

- [Installation, first run, Host requirements and known limitations](docs/getting-started.md)
- [1.1.3 release notes](docs/releases/1.1.3.md)
- [Rust rebuild plan (current architecture)](docs/specs/rust-rebuild/README.md)
- [Product Philosophy (Chinese)](docs/product-philosophy.md)
- [下一轮拟实施：商业表达与专家共创改稿闭环（版本号未定）](docs/specs/README.md#当前架构与下一轮拟实施主题)
- [2026-10-29 商业表达历史规划与产品目的](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent entry](AGENTS.md)
- [deck-master](deck-skill/deck-master/SKILL.md), [deck-content](deck-skill/deck-content/SKILL.md), [deck-design](deck-skill/deck-design/SKILL.md), [deck-review](deck-skill/deck-review/SKILL.md)
- [Support and Feedback](SUPPORT.md)
- [Issue Maintenance](docs/issue-maintenance.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
