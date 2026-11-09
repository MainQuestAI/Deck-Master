# Install and use Deck Master 1.1.2

Deck Master 1.1.2 provides the Rust CLI `deck`, a loopback Web UI (`deck serve`),
file tools (`deck-tools`), and the Codex Skill tree in `deck-skill/`. The
default install still links the compatibility entry `deck`. `--skills-root`
also links `deck-master`, `deck-content`, `deck-design`, and `deck-review`.
It does not bundle a model, Codex account, image-generation service, desktop office
application, renderer binaries or fonts. A plain material directory is enough
to start; no PPT Master backend or slide library is needed.

The previous Python workbench (`deck-master`) and its four Skills remain in the
tree for maintenance. Their managed-wheel install is in
[Legacy Python workbench (1.0.0)](#legacy-python-workbench-100) below.

## Requirements

- Rust 1.88 or later. Cargo enforces `rust-version` in `rust/Cargo.toml`.
- Python 3.12 for the `scripts/install.sh` deck-tools venv. `deck-tools`
  metadata allows 3.11–3.13 and excludes 3.14. CI uses 3.12.
- Node 22 to build the WebUI (`frontend/`). The install script runs
  `npm ci` and `npm run build`; the binary embeds that output.
- For content and image work, an external Host (first Host: Codex). Install
  and authenticate [Codex CLI](https://developers.openai.com/codex/cli)
  separately if using the linked Skill.
- Real previews/rendering require `rsvg-convert`, LibreOffice `soffice`,
  Poppler `pdftoppm`, Fontconfig `fc-match`, and the fonts selected by the
  design. `deck doctor` checks those four tools. `deck doctor --fonts "<family>"`
  also checks the named fonts. Without `--fonts`, the font line is only a
  warning and does not by itself make the status `needs_tool`.
  Compiling SVG to PPTX does not require an external PPT application.
  SVG handoff (`deck run result`) needs `soffice` for the preview. If it is
  missing, the error gives the install steps and says to stop rather than call
  `compile_job`.

CLI inspection needs no model call. Image generation uses the Host's account
and permissions.

## Install from source

```bash
./scripts/install.sh
```

The script builds the Web UI, installs the `deck` binary at `<prefix>/bin/deck`
(default prefix `~/.local`, so `~/.local/bin/deck`), and creates a Python 3.12
venv for `deck-tools` at `<prefix>/share/deck/venv`. The binary is not
`<prefix>/deck`. `--dry-run` prints the plan, including `deck-bin`, and checks
the selected skill paths without writing. A finished install prints that same
`deck` path and the `deck` currently resolved on `PATH`.

If `<prefix>/bin` is not on `PATH`, add it or call `<prefix>/bin/deck`. A
non-default `--prefix` means the skill and
[commands.md](../deck-skill/references/commands.md) must use that full path.

Skill flags during this migration:

- No skill flag: install or update the CLI, the tool environment, and the
  compatibility entry at `~/.codex/skills/deck`. The four role entries are not
  installed.
- `--skill-dir PATH`: install only that compatibility entry at `PATH`.
- `--skills-root DIR`: install `deck`, `deck-master`, `deck-content`,
  `deck-design`, and `deck-review` under `DIR`. `deck` links the whole
  `deck-skill/` tree. Each role directory's `SKILL.md` links the matching
  source file, and its `references` and `assets` link the shared directories.

`--skill-dir` and `--skills-root` cannot be used together. An entry that
already points at this source is left unchanged, including other files in a
role directory. Any other symlink or directory on the selected name exits 2
and prints the path and target. The script does not replace or delete it.
Remove only that symlink (`rm` the link, not the directory it points at) or
move the directory aside, then rerun. Or pass a different path. The old
installer treats these same-name entries as foreign; switching back requires
handling the links explicitly. The two installs do not stack on one path.

npm 12 blocks dependency install scripts unless `allowScripts` lists them, and
prints an `install-scripts` warning for the rest. `frontend/package.json`
allows the locked `esbuild` and `fsevents` versions so `npm ci` can install
esbuild's platform binary. npm 10 ignores that field and still runs the scripts.

A fresh install finds deck-tools in the prefix venv, so it does not need
`DECK_TOOLS_PYTHON`. deck-tools is an editable install of this checkout;
moving or deleting the checkout leaves that venv unable to import it.

After install:

```bash
deck new ./my-deck --title '方案标题'
deck --project ./my-deck doctor --fonts 'Source Han Sans SC'
deck serve ./my-deck
```

`deck serve` prints a loopback URL and binds `127.0.0.1` only. Host or Origin
that is not this process's loopback address is rejected. Keep the URL private.
One process serves one project.

Command examples: [README Quick Start](../README.md#quick-start) and
[deck-skill/references/commands.md](../deck-skill/references/commands.md).
Release scope: [1.1.2 notes](releases/1.1.2.md).

## Upgrade an old Python project

Do not create `.deck/` inside an old project directory.

```bash
deck-master legacy-export <project> <out>
deck import <out> <new>
```

`<out>` must sit outside `<project>`. The old directory is unchanged.
`visual_spec.intent` is copied into `purpose` only when that page has no
purpose of its own; otherwise the intent text is an `unmapped` item of kind
`visual_spec_intent`. Old revisions are not migrated: each
`.deckmaster/revisions/*.json` other than the current revision is an
`unmapped` item of kind `revision`. See
[1.1.0 notes](releases/1.1.0.md#upgrade-and-migration). v0.9.x run directories
still follow [migration-to-rebuilt-core.md](migration-to-rebuilt-core.md).

### Upgrade

Re-running `scripts/install.sh` upgrades an existing install. An existing
venv is reused and the `deck` binary is overwritten.

## Legacy Python workbench (1.0.0)

The 1.0.0 managed installer and `deck-master` CLI are the previous source
line. They are not the 1.1.0 authoring path. Python `1.0.0` mapped to tag
`v1.0.0`. Source version alone does not establish that a release or its
assets have been published.

Download the wheel and `release.json` from the same
[GitHub Release](https://github.com/MainQuestAI/Deck-Master/releases) if you
need that line. Keep them in one directory. No PyPI publication is assumed.

```bash
python3.12 -m venv ./deck-master-bootstrap
./deck-master-bootstrap/bin/python -m pip install ./deck_master-1.0.0-py3-none-any.whl
./deck-master-bootstrap/bin/python -m deck_master install candidate \
  --prefix "$HOME" --manifest ./release.json
```

`candidate` creates and checks an isolated managed release without activation.
Read its returned `release_id`. If its checks pass and you want to activate it:

```bash
./deck-master-bootstrap/bin/python -m deck_master install activate \
  --prefix "$HOME" --release-id <returned_release_id> --transaction-id <UUIDv4>
"$HOME/.deck-master/bin/deck-master" doctor --step compose
```

Substitute actual returned IDs. Activation registers the four managed Skills
under `$CODEX_HOME/skills` (default `~/.codex/skills`). See the
[installation and recovery reference](../skills/deck-master/references/installation.md).
Rolling back a managed 1.0.0 prefix does not install `deck`.

Workbench on that line: `"$HOME/.deck-master/bin/deck-master" view --open --project <dir>`.
Task routing: [agent-task-index.md](agent-task-index.md).

## Known limitations

- UNC paths (`\\server\share`) are not covered by local-path sanitization in
  `deck-tools`.
- `GET /api/export/md` does not run the credential check used on exported
  PPTX slide text.
- After `deck build`, `stale_pages` can still list pages whose SVG basis differs
  from the current content, image, or style (including `imported`). That does
  not mean the PPTX is out of date. `stale_images` on `deck show` is the
  same comparison for original images. `deck export pptx` sets `input_changed`
  only when the SVG files, notes, or build settings changed after that build.
- PPTX has been rechecked through LibreOffice (`soffice`) rendering in the
  tool tests. The 2026-11-04 maintainer check is in the
  [1.1.0 notes](releases/1.1.0.md#maintainer-acceptance-2026-11-04).
  Actual WPS editing was not verified on the PR125 1.0.0 observation
  because the Mac device locked.
- Native editable PPT output uses shapes and text. Tables/charts are composed
  shapes/text rather than Office-native spreadsheet-backed data objects.
- `doctor` finding a font family does not prove LibreOffice can render every
  glyph. In the maintainer's macOS 27.0.1 arm64 / LibreOffice 26.8.1.1 run,
  `fc-match` found Noto CJK but default PDF rendering substituted unrelated
  fonts and produced missing Chinese glyphs. Reusing an existing Homebrew
  Fontconfig configuration for the rendering process fixed that run.
- Only if these existing Homebrew paths are readable, the following optional
  command applies the same known configuration and a task-local cache to one
  pending render operation. Use the actual complete working configuration on
  your machine; do not blindly set nonexistent paths or replace it with a
  partial font list. For UI-triggered rendering, start `deck serve` with the
  same environment; an already-running server keeps its old environment.

```bash
if [ -r /opt/homebrew/etc/fonts/fonts.conf ] && [ -d /opt/homebrew/etc/fonts ]; then
  mkdir -p ./render-cache
  FONTCONFIG_FILE=/opt/homebrew/etc/fonts/fonts.conf \
  FONTCONFIG_PATH=/opt/homebrew/etc/fonts \
  XDG_CACHE_HOME="$PWD/render-cache" \
    deck --project ./my-deck build
fi
```

These are [Fontconfig's process environment overrides](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html).
Use the same environment for `deck doctor --fonts ...` and the command that
creates the actual renders. This changes no global configuration and installs
no fonts. Inspect the resulting real previews; existing cached previews are
not automatically replaced by setting environment variables.

The maintainer's actual installed PR125 task at `d7ec4530` (Python 1.0.0 line)
passed native review, trusted native-image observations on two pages, SVG/PPT,
real rendering and formal delivery, reporting `ready` and `handoff-check verified`
with no missing Task. This is one complete observed task, not broad OS or model
certification, and it is not a 1.1.0 `deck` install observation.
Professional human review and application-specific desktop editing remain
separate observations and are never inferred from CI or a generated PPTX.

The browser does not start image or SVG runs. Hosts use `deck run` on the CLI.
`codex app-server` ImageGen from the WebUI is not claimed.

Report reproducible issues with neutral material and actual version/diagnostic
results using the [contribution guide](../CONTRIBUTING.md). Keep credentials,
private sources and internal execution logs out of public reports.
