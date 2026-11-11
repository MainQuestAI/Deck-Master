# Install and use Deck Master 1.1.2

Deck Master 1.1.2 provides the Rust CLI `deck`, a loopback Web UI (`deck serve`),
file tools (`deck-tools`), and the Codex Skill tree in `deck-skill/`. The
default install links the complete `deck-master`, `deck-content`, `deck-design`,
and `deck-review` directories into `~/.codex/skills`. `--skills-root` changes
that directory; the compatibility entry `deck` is no longer installed.
It does not bundle a model, Codex account, image-generation service, desktop office
application, renderer binaries or fonts. A plain material directory is enough
to start; no PPT Master backend or slide library is needed.

The previous Python workbench and its official exporter have been removed.
Historical notes are in the published [1.1.0 release page](releases/1.1.0.md#upgrade-and-migration).

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

The script prepares the CLI, embedded frontend, non-editable Python package and
four role resource directories together in `<prefix>/share/deck/installations/`.
A single `<prefix>/share/deck/current` link selects the completed directory.
`<prefix>/bin/deck` is the fixed entry and resolves the physical installation
before executing it. The venv is created in its final position. Failed
preparation leaves the old installation selected; old directories are retained
for existing processes. `--dry-run` prints the plan without writing.

If `<prefix>/bin` is not on `PATH`, add it or call `<prefix>/bin/deck`. A
non-default `--prefix` means the skill and
[commands.md](../deck-skill/references/commands.md) must use that full path.

Skill installation:

- With no skill flag, install the four role entries `deck-master`,
  `deck-content`, `deck-design`, and `deck-review` into `~/.codex/skills`.
- `--skills-root DIR` installs the same four entries into `DIR` instead.
- Each entry is a symlink through `current/deck-skill/<role>` to the installed copy.
  Its `SKILL.md` is a regular file; relative `references` and `assets` links
  resolve to the shared method source. Codex can discover these directories.
- The compatibility entry `deck` is no longer installed. `--skill-dir` has
  been removed; use `--skills-root` to choose a skill directory.

For users with only `deck`, rerun the script: it removes that symlink only
if it points at this source's `deck-skill/`, and installs the four roles.
For users with `deck` plus old role wrappers, rerunning also upgrades wrappers
that contain only the three managed `SKILL.md`, `references`, and `assets`
symlinks. It replaces each wrapper with a whole-directory symlink. Existing
links to this source migrate to current; current links are kept.

Any extra file in a wrapper, or another entry occupying a role name, causes
exit 2 before any writes; the script prints the path and target. This includes
same-name links from the old Python installer. Move those links away first
(remove the symlink only, never its target directory), or move a regular
directory aside, then rerun. An unmanaged `deck` entry is preserved with a
warning that it may compete with the four roles for triggering; it does not
block installation.

npm 12 blocks dependency install scripts unless `allowScripts` lists them, and
prints an `install-scripts` warning for the rest. `frontend/package.json`
allows the locked `esbuild` and `fsevents` versions so `npm ci` can install
esbuild's platform binary. npm 10 ignores that field and still runs the scripts.

Standard installs do not need `DECK_TOOLS_PYTHON` and survive moving the source
checkout. Use `scripts/install.sh` for upgrades. Unknown CLI entries are retained
and reported; supported Cargo installations migrate using their installation
records. Old venvs and source directories are not moved or removed.

For development, use an independent prefix and this worktree's Python:

```bash
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
cargo install --path rust --root "$PWD/.dev-prefix"
export PATH="$PWD/.dev-prefix/bin:$PATH"
```

After install:

```bash
deck new ./my-deck --title '方案标题'
deck --project ./my-deck doctor --fonts 'Source Han Sans SC'
deck serve ./my-deck
```

These three commands check that the installed CLI starts. The first draft uses the synthetic sample: open Codex in this checkout and type the one sentence in the [README Quick Start](../README.md#quick-start). It points at `examples/first-run/`.

`deck serve` prints a loopback URL and binds `127.0.0.1` only. Host or Origin
that is not this process's loopback address is rejected. Keep the URL private.
One process serves one project.
The old `/studio/` and `/v2/` addresses no longer work; use the address printed by `deck serve`.

Command examples: [README Quick Start](../README.md#quick-start) and
[deck-skill/references/commands.md](../deck-skill/references/commands.md).
Release scope: [1.1.2 notes](releases/1.1.2.md).

## Import an existing archive

The `deck-master` command and its `legacy-export` exporter have been deleted;
old projects no longer have an official exporter. `deck import <archive> <new>`
still imports an existing `legacy-export.v1` archive into a new directory.

## Upgrade

Re-running `scripts/install.sh` prepares a new complete directory and switches
`current` after validation. It creates a new venv; existing processes retain their
old tools. A supported legacy Cargo binary is migrated only when its installation
record and associated built artifact agree. Unknown entries are preserved.

If the legacy checkout was rebuilt after installation, its current
`rust/target/release/deck` may differ from the installed binary. Exit 2 then
means ownership could not be confirmed; the installer does not replace it.
Keep the old source and venv. Verify the Cargo record, checkout and reported
entries before making a manual change. If the original built artifact is still
available, restore that verified artifact in the original checkout and retry
there. Otherwise, back up the confirmed old CLI and each reported legacy role
entry individually to a new directory outside `bin` and the skills root,
preserving symlinks themselves and any user-added files, then rerun installation.
Stop the legacy Deck and tool processes before this manual backup procedure.
Never delete a symlink's target. Moving only `bin/deck` away and starting from a
different checkout loses the evidence used to identify the old role links;
it is not a complete cross-checkout migration procedure.

## Remove one confirmed historical installation

The installer never cleans up historical groups. Stop all Deck and tool
processes and prevent them from restarting during manual cleanup. Choose one
confirmed obsolete directory and preserve any files you added there first.
The following example rejects `current`, symlinks, paths outside the installation
root, an observed running process, and incomplete process checks. It needs
`lsof`; missing tools or inspection errors stop cleanup. The checks are a
snapshot, so keep processes stopped until the command finishes. Do not replace
the single directory name with `installations/*`.

```bash
prefix="$HOME/.local"
old_name='<confirmed-old-directory>'
"$prefix/share/deck/current/share/deck/venv/bin/python" - "$prefix" "$old_name" <<'PY'
import shutil
import subprocess
import sys
from pathlib import Path

prefix = Path(sys.argv[1]).resolve(strict=True)
root = (prefix / 'share/deck/installations').resolve(strict=True)
name = sys.argv[2]
if name in ('', '.', '..') or Path(name).name != name:
    raise SystemExit('请指定 installations 下一个已确认的旧目录名；未删除。')
old = root / name
current = (prefix / 'share/deck/current').resolve(strict=True)
if old.is_symlink() or not old.is_dir() or old.resolve().parent != root:
    raise SystemExit('目标不是 installations 下的普通目录；未删除。')
if current.parent != root or old.resolve() == current:
    raise SystemExit('不能清理 current，或无法确认 current；未删除。')
if shutil.which('lsof') is None:
    raise SystemExit('需要 lsof 检查运行进程；未删除。')
opened = subprocess.run(['lsof', '-nP', '+D', str(old)], capture_output=True, text=True, check=False)
if opened.returncode != 1 or opened.stdout.strip() or opened.stderr.strip():
    raise SystemExit('目录仍被进程使用，或检查不完整；未删除。')
processes = subprocess.run(['ps', '-axww', '-o', 'command='], capture_output=True, text=True, check=False)
if processes.returncode != 0 or processes.stderr.strip() or str(old) in processes.stdout:
    raise SystemExit('仍有进程引用该目录，或无法核对进程；未删除。')
if (prefix / 'share/deck/current').resolve(strict=True) == old.resolve():
    raise SystemExit('current 已切到该目录；未删除。')
shutil.rmtree(old)
print('已清理单个确认的历史安装目录：', old)
PY
```

## Known limitations

- UNC paths (`\\server\share`) are not covered by local-path sanitization in
  `deck-tools`.
- `GET /api/export/md` does not run the credential check used on exported
  PPTX slide text.
- After `deck build`, `stale_pages` can still list pages whose SVG or native
  basis differs from the current content, purpose, layout, image file, or style
  (including `imported`). That does not mean the PPTX is out of date.
  `stale_images` is the same comparison for original images. `deck get`,
  `deck show`, `deck build`, and `deck export pptx` all include it. Build and
  PPTX export also list those page ids in `warnings` (`code` `stale_image`,
  `level` `warning`). They are not folded into `stale_pages` and do not change
  the exit code or the readback status. `deck export pptx` sets `input_changed`
  only when the page files, notes, or build settings changed after that build.
- PPTX has been rechecked through LibreOffice (`soffice`) rendering in the
  tool tests. The 2026-11-04 maintainer check is in the
  [1.1.0 notes](releases/1.1.0.md#maintainer-acceptance-2026-11-04).
  Actual WPS editing was not verified on the PR125 1.0.0 observation
  because the Mac device locked.
- Native output uses editable shapes and text. Supported tables marked
  `data-native-table="true"` with complete grid and ownership bindings become
  native PPT tables; ordinary drawn tables remain shapes/text. Charts are not
  Office-native spreadsheet-backed data charts.
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
