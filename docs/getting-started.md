# Install and use Deck Master 1.0.0

Deck Master provides the local CLI, Workbench, project history and four Codex
Skills. It does not bundle a model, Codex account, image-generation service,
desktop office application, renderer binaries or fonts. A plain material
directory is enough to start; no PPT Master backend or slide library is needed.

## Requirements

- Python 3.11 or 3.12, the versions exercised in CI. Metadata allows 3.13;
  that version is outside the tested matrix. Python 3.14 is excluded.
- For actual content/design work, an external Host able to read the frozen
  Task methods, execute the requested scope and return its actual results.
  Install and authenticate [Codex CLI](https://developers.openai.com/codex/cli)
  separately if using the managed Codex Skills.
- The normal native independent reviewer requires `codex` on PATH, an existing
  ChatGPT-authenticated CLI session, and a working `codex app-server` protocol.
  Inspect `codex --version` and `codex login status`. An API-key-only login is
  not a substitute for this runner; no provider credential is added by Deck Master.
  The maintainer's complete local validation used Codex CLI 0.163.0; other
  versions are not a promised compatibility matrix.
- Blueprint/image tasks need the actual image-generation and observation
  capabilities declared by the Host. Installing the Python wheel does not
  supply them or authorize their calls.
- Real previews/rendering require `rsvg-convert`, LibreOffice `soffice`,
  Poppler `pdftoppm`, Fontconfig `fc-match`, and the fonts selected by the
  design. Use the installed launcher's
  `doctor --step render --font "<actual font family>"` command.
  The normal Python PPT compiler does not require an external PPT backend.

CLI inspection and the bundled read-only sample need no model call. Genuine
model/image work uses the external Host's account and permissions; follow the
actual request's authorization and call allowance.

## Install a release

Python `1.0.0` maps to tag `v1.0.0`. Source version alone does not establish
that the release or its assets have been published.

Download the wheel and `release.json` from the same
[GitHub Release](https://github.com/MainQuestAI/Deck-Master/releases).
Keep them in one directory. The source archive is optional for ordinary use.
Check the published SHA256 sums; the managed installer also verifies the wheel
against its manifest. No PyPI publication is assumed by these instructions.

Bootstrap the CLI in a separate environment, using the downloaded wheel:

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
"$HOME/.deck-master/bin/deck-master" capabilities
```

Substitute actual returned IDs; do not paste placeholders.
Generate a transaction UUIDv4 with `python -c 'import uuid; print(uuid.uuid4())'`.
Activation changes the selected prefix and registers all four managed Skills under
`$CODEX_HOME/skills` (default `~/.codex/skills`). Existing foreign files/links
are preserved and reported as conflicts. Use another prefix for an isolated
installation, and `--no-host-registration` if you explicitly want CLI-only
activation. The remaining examples use the default prefix's absolute launcher,
`"$HOME/.deck-master/bin/deck-master"`; substitute your chosen prefix's launcher
if different. Adding `.deck-master/bin` to PATH is optional for these examples.
Start a new Codex session or reload its
Skills, then use the Python belonging to the actual loaded Skill release.
See the [installation and recovery reference](../skills/deck-master/references/installation.md).

## First run

Open the local launcher with a registry you choose:

```bash
"$HOME/.deck-master/bin/deck-master" workbench --registry ./deck-master-projects.json --no-open
```

Open the returned loopback URL. **打开只读示例** displays a bundled synthetic
example without generating or approving real work. **新建项目** and **选择项目文件夹**
operate on your own material and projects. The UI is local; keep its returned
URL/token private and preserve the registry and project directories.

For a real task, give the external Host your brief, full material location and
requested output. Use `deck-master` for coordination, `deck-content` for
content alone, `deck-design` for scoped design, or `deck-review` for read-only
review. A copied handoff does not start a model. Follow the returned scope,
decisions and Tasks; the [CLI quick start](../README.md#quick-start) shows the
manual claim/accept sequence.

When a current authorized full-deck/edit request needs independent content
review, use **独立审阅当前内容** in the Workbench or:

```bash
"$HOME/.deck-master/bin/deck-master" review native --project ./my-deck --json
"$HOME/.deck-master/bin/deck-master" continue --project ./my-deck --no-open
```

The runner performs an actual independent native session; it accepts no
handwritten receipt JSON. A failed/unavailable session remains a named gap.
Inspect its Task before retrying an uncertain or running call.

Before formal delivery, complete the current image/page/final reviews, run
`final-readiness`, export `--purpose delivery`, and check the actual file with
an explicit delivery purpose:

```bash
"$HOME/.deck-master/bin/deck-master" handoff-check --project ./my-deck \
  --file /path/to/actual-exported.pptx --purpose delivery --json
```

Replace the file path with the actual PPTX returned by your delivery export.
Always pass `--purpose delivery` for this check; the CLI defaults to `review`.
`--purpose review` can produce an unfinished
reading copy with its real unresolved list. Content-only completion does not
start design or PPT production. See the [task index](agent-task-index.md).

## Upgrade and rollback

Download the new release's matching wheel and manifest, install that wheel into
the bootstrap environment, then repeat `install candidate` and `install activate`
using the new returned release ID and a new transaction ID. Reload the Host's
Skill entry after switching. Keep each transaction's original ID and arguments
for exact recovery after interruption; a timeout is not proof of failure.

`"$HOME/.deck-master/bin/deck-master" install rollback --prefix "$HOME" --transaction-id <new_UUIDv4>`
switches to the recorded previous managed release. It does not roll back project
data, recorded calls or writer floors. An older runtime may refuse a project
that has acquired newer protocol facts. Follow the
[transaction recovery reference](../skills/deck-master/references/installation.md#durable-transaction-recovery).
For v0.9 runs, use the [migration guide](migration-to-rebuilt-core.md); never
initialize a new-format project in the old run directory.

## Known limitations

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
  partial font list. For UI-triggered rendering, start the Workbench process
  with the same environment; an already-running server keeps its old environment.

```bash
if [ -r /opt/homebrew/etc/fonts/fonts.conf ] && [ -d /opt/homebrew/etc/fonts ]; then
  mkdir -p ./render-cache
  FONTCONFIG_FILE=/opt/homebrew/etc/fonts/fonts.conf \
  FONTCONFIG_PATH=/opt/homebrew/etc/fonts \
  XDG_CACHE_HOME="$PWD/render-cache" \
    "$HOME/.deck-master/bin/deck-master" continue --project ./my-deck --no-open
fi
```

These are [Fontconfig's process environment overrides](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html).
Use the same environment for `doctor --step render --font ...` and the command
that creates the actual renders. This changes no global configuration and
installs no fonts. Inspect the resulting real previews; existing cached
previews are not automatically replaced by setting environment variables.

The maintainer's actual installed PR125 task at `d7ec4530` passed native review,
trusted native-image observations on two pages, SVG/PPT, real rendering and
formal delivery, reporting `ready` and `handoff-check verified` with no missing
Task. This is one complete observed task, not broad OS or model certification.
Actual editing in WPS was not verified because the Mac device locked.
Professional human review and application-specific desktop editing remain
separate observations and are never inferred from CI or a generated PPTX.

Report reproducible issues with neutral material and actual version/diagnostic
results using the [contribution guide](../CONTRIBUTING.md). Keep credentials,
private sources and internal execution logs out of public reports.
