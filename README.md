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

**Version:** `1.1.0` (Rust CLI `deck`, Python packages `deck-master` and
`deck-tools`, WebUI). Source version, built artifacts, an active install and a
published GitHub Release are separate facts. Start with the
[installation and first-run guide](docs/getting-started.md). See
[1.1.0 release notes](docs/releases/1.1.0.md) for migration, the 2026-11-04
maintainer check, and known limits. **License:** Apache-2.0.

The 1.1.0 authoring path is the Rust core in `rust/`, file tools in
`deck-tools/`, the WebUI in `frontend/` served by `deck serve`, and the Codex
Skill in `deck-skill/`. A plain material directory is enough to start; no PPT
Master backend or slide library is required. The previous Python workbench
(`deck-master` in `src/deck_master/`, four Skills under `skills/`) remains for
maintenance only.

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

The script builds the Web UI, installs `deck` into `~/.local/bin`, creates a
Python 3.12 venv for `deck-tools` at `~/.local/share/deck/venv`, and links
`deck-skill/` to `~/.codex/skills/deck`. It does not activate or roll back a
managed Python release.

Options: `--prefix DIR`, `--skill-dir PATH`, `--dry-run`. If `~/.local/bin` is
not on `PATH`, add it or call that `deck` by its full path. The skill path must
be new, or already a link to this checkout's `deck-skill/`. The script leaves
a different file or link unchanged and exits 2. A symlink that points
elsewhere prints `已存在且指向其他位置`; remove it and run the script again, or
pass another `--skill-dir`. See the [first-run guide](docs/getting-started.md#upgrade).

After install, `deck new ./my-deck --title '方案标题'` creates a work
directory. The linked skill describes the first-run commands.

A fresh install finds deck-tools in the prefix venv, so it does not need
`DECK_TOOLS_PYTHON`. `cargo install --force` replaces a `deck` binary already
present in `PREFIX/bin`. deck-tools is an editable install of this checkout;
moving or deleting the checkout leaves that venv unable to import it.

Development in a worktree (do not reuse another checkout's venv):

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e "./deck-tools[dev]"
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
(cd frontend && npm ci && npm test && npm run build)
(cd rust && cargo test)
```

The legacy Python workbench still installs with `pip install -e ".[dev]"` and
the command `deck-master`. That line is maintenance-only; see
[AGENTS.md](AGENTS.md) section 12.

## Migrate an old project

Move an old Python project into a new directory. The old directory stays as it is:

```bash
deck-master legacy-export <project> <out>
deck import <out> <new>
```

`<out>` has to sit outside `<project>`. Imported images and SVG are stored with
`basis` `imported`, so the overview shows those pages as stale. `deck export pptx`
reports `input_changed`.

The most recent PPTX is cleaned before becoming downloadable, preserving its own
slide order and speaker notes. If that cleanup fails or its tool is unavailable,
the editable content still imports; `last_export:false` and `unmapped` identify
the unavailable PPTX and explain the next step. The uncleaned file stays in the
old project and archive.

v0.9.x run directories follow
[docs/migration-to-rebuilt-core.md](docs/migration-to-rebuilt-core.md).

## Quick Start

Use your own complete material and brief. Substitute paths and IDs returned by
the commands; do not paste the placeholders as values. Examples assume `deck`
is on `PATH` after `scripts/install.sh`.

```bash
# 1. Create a work directory and add author-specified source files only.
deck new ./my-deck --title '方案标题'
deck --project ./my-deck material add ./materials/brief.pdf
deck --project ./my-deck material text m1

# 2. Read, edit, and save. put compares against --base and writes only
#    changed units. Conflicts exit 5 and leave the current version unchanged.
deck --project ./my-deck get > ./my-deck/current.json
deck --project ./my-deck put --base <version> ./my-deck/patch.json
deck --project ./my-deck show
deck --project ./my-deck export md > ./my-deck/manuscript.md

# 3. Check local tools and selected fonts before image / SVG / PPTX work.
deck --project ./my-deck doctor --fonts 'Source Han Sans SC'

# 4. Image then SVG, then build PPTX. Hosts register each ImageGen call.
deck --project ./my-deck run start image --pages p1,p2
deck --project ./my-deck run call <run> p1
deck --project ./my-deck run result <run> p1 ./page.png
deck --project ./my-deck run start svg --pages p1,p2
deck --project ./my-deck run result <run> p1 ./page.svg
deck --project ./my-deck build
deck --project ./my-deck export pptx

# 5. Open the local UI. It binds 127.0.0.1 only.
deck serve ./my-deck
```

The Skill in `deck-skill/` describes judgment and which command to run. Worked
command examples are in
[deck-skill/references/commands.md](deck-skill/references/commands.md).
Page reviews: `deck review add` / `list` / `resolve`. Restore a historical
version with `deck restore <version>` (it writes a new version; files, runs and
builds are not deleted).

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

1. Produced PPTX contains editable shapes and text. Tables and charts are
   shape/text compositions, not Office-native spreadsheet-backed data objects.
2. Incomplete work can be saved, exported as Markdown, and built. Missing or
   stale SVG pages are listed next to download; export is not blocked.
3. Cancelled runs and results whose page basis has changed are stored and not
   adopted automatically. A later result for the same run page is an explicit
   candidate.
4. Renderer and font gaps surface as exit code 3 (`needs_tool`) with the
   actual reason.
5. Reviews are stored on the version at add time. The UI writes human reviews;
   CLI `self_check` is the current Host's own check.

The 2026-11-04 macOS check is in the
[1.1.0 release notes](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04).
It is not a full acceptance. Professional content review, WPS, and PowerPoint
desktop editing were not part of it. See
[known limitations](docs/getting-started.md#known-limitations).
Follow-ups: [#274](https://github.com/MainQuestAI/Deck-Master/issues/274).

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
- [1.1.0 release notes](docs/releases/1.1.0.md)
- [Rust rebuild plan (current architecture)](docs/specs/rust-rebuild/README.md)
- [Product Philosophy (Chinese)](docs/product-philosophy.md)
- [Next iteration: business expression plan (Chinese)](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent entry](AGENTS.md)
- [New Skill](deck-skill/SKILL.md)
- [Legacy Python task index](docs/agent-task-index.md)
- [Legacy recovery playbook](docs/agent-recovery-playbook.md)
- [v0.9 migration to the previous rebuilt core](docs/migration-to-rebuilt-core.md)
- [Support and Feedback](SUPPORT.md)
- [Issue Maintenance](docs/issue-maintenance.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
