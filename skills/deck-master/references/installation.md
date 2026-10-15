# Installation

The rebuilt Python package exposes one CLI: `deck-master` or `python -m deck_master`.
For development, use Python 3.11 or 3.12 and `python -m pip install -e '.[dev]'`.
A release used from Codex also needs its managed Skill registration.

## Candidate, activation and rollback

Build and check the candidate first. `install candidate` creates an isolated
virtual environment, extracts the four `skill/<name>/` entries and shared methods from the wheel, and runs
compile/render/compose/view checks. It does not activate or register the Skill.

```bash
python tools/build_release.py --out /path/to/new-release
python -m deck_master install candidate \
  --prefix /path/to/prefix --manifest /path/to/new-release/release.json
python -m deck_master install activate \
  --prefix /path/to/prefix --release-id <release_id>
/path/to/prefix/.deck-master/bin/deck-master doctor --step compose
/path/to/prefix/.deck-master/bin/deck-master install rollback --prefix /path/to/prefix
```

For the normal personal installation, `--prefix "$HOME"` produces
`~/.deck-master/bin/deck-master`. Use the chosen prefix's launcher when using
another prefix. When operating through the Host Skill, resolve its loaded entry
path to `releases/<id>/skill/deck-master/SKILL.md` and invoke that same release's
`venv/bin/python -I -m deck_master`, as shown in SKILL.md. Do not substitute a
HOME or PATH installation. Reload the Skill entry and resolve again after
activation or rollback. Skill bytes are not rewritten during installation.
Activation manages all four links under `$CODEX_HOME/skills` (default `~/.codex/skills`):
`deck-master`, `deck-content`, `deck-design`, and `deck-review`, each pointing to
`<prefix>/.deck-master/current/skill/<name>`. All four entries are preflighted
before switching current. An error compensates pointers, launcher and each
managed link; external changes are reported without overwriting them.
A real directory/file or a foreign link at that path is a `host_skill_conflict`
(exit 5); resolve the named conflict before retrying. `--no-host-registration`
on both `activate` and `rollback` leaves every Host entry untouched, including legacy cleanup and retiring a
managed link when the target release has no Skill. CLI and Host status are
reported separately; a preserved link can remain unreadable.
No config.toml changes, other Host registrations or third-party Skill changes occur.

Rollback follows `previous` and keeps method and CLI releases aligned. If the
previous release predates the Skill, managed links missing from that release are removed and the result
reports `host_skill_unregistered`. Project data and recorded calls are not rolled back. RC3-04 projects use the
forward writer floor `rc3-entry.v1`; a real older writer must refuse them after
rollback, while the matching current Runtime can continue to read and settle
existing call facts. The label `rc3.v1` alone is insufficient because historical
RC3 binaries already recognized it.

## Legacy companion layout

Activation recognizes a real `current/` containing only
`companion-manifest.json` with schema `deck_master_companion_manifest.v3` and
`bundled_symlink_only` on its Deck Skill rows. The policy is nested in `skills[]`;
it is not a top-level manifest field. Other directory contents are refused.
The old directory moves to `legacy-companion-<timestamp>` and remains available.
Only `deck-*` symlinks targeting the exact old `current/skills/` subtree are
removed, with each move, removal and skipped entry reported. Launcher and path
conflicts are checked before moving the directory or deleting links.
With `--no-host-registration`, the directory is backed up and the CLI activated,
but all Host links remain unchanged. A later activation without that flag uses
the validated preserved manifest to finish legacy link cleanup and registration.
Retry is idempotent.

Run migration tests with an isolated HOME and CODEX_HOME. Actual installation
migration and the seven-step new Codex session are user-run acceptance checks;
passing package tests is not evidence that either was completed.

## Tools and old runs

```bash
deck-master doctor --step compose
deck-master doctor --step render
deck-master legacy-map
```

Missing renderers/fonts report `needs_tool`. Old run directories report
`legacy_run_format`; use `deck-master import legacy --input <old-run> --out <new>`
or pin a compatible old release. Never initialize or migrate an old run in place.

## Generation workbench v3 (available in this candidate)

After installing this wheel in a supported Python 3.11/3.12 environment, run
`deck-master workbench --registry /path/to/isolated/projects.json --no-open`.
Open the returned URL and choose **打开只读示例**. This bundled synthetic sample
requires no model account and does not authorize generation. Use **新建项目**
or **选择项目文件夹** for your own material. `--project /path/to/project` opens
one explicit project; the workbench is the sole UI; the retired review interface is no longer packaged.
`deck-master view --project … --open --ui v2` opens the same project service at
the explicit new workbench entry; `view --open` without `--ui` keeps the default
entry.
Stop the selected service using `workbench --registry … --stop` (launcher) or
`workbench --project … --stop` (project). Stopping a service preserves its data;
it does not prevent an independent CLI writer from being invoked.

The five work areas are 制作总览, 内容与来源, 整稿画廊, 逐页查看 and 任务与交付.
The UI saves personal drafts separately from formal operations. Copying a Host
handoff does not start a model. New output remains a candidate until explicitly
adopted; an unknown response must be verified using its original operation ID.
The bundled CSS uses system font stacks and inline SVG icons, with no CDN or
webfont download. PPT rendering separately requires the actual declared fonts
and the renderer toolchain checked by `doctor --step render`.

In 任务与交付, **版本与文件** freezes the selected revision. The CLI equivalent is
`export --project … --revision … --purpose review|delivery|engineering --out …`,
with a new output directory; `--export-id export-<UUIDv4>` supports exact retries.
Review works without a PPT and excludes internal source objects and prompts.
Delivery checks the selected snapshot and refuses unresolved dimensions.
Engineering retains source material, full prompts and recoverable history and
is for internal use. Sanitized copies do not modify immutable original bytes.
`history plan-restore --project … --revision … --base-revision …` previews
restoration; `history commit-restore --project … --plan-id … --base-revision …
--operation-id …` creates a new revision while retaining execution and stop facts.

The executable source-side verification drivers are indexed in
`examples/workbench/README.md`; `w12_installed_acceptance.py` builds a fixed Git
candidate and then checks it using its installed interpreter. A synthetic
browser/CLI pass is not 30-page real Host, professional or customer acceptance.

## RC3 resource identity

The version is PEP 440 `1.0.0rc3`. `tools/build_release.py` builds both wheel and
sdist. The wheel contains a generated `resources/method-inventory.json` with an
exhaustive mapping from every Skill/method resource to canonical source and
SHA256. Unknown/missing/symlink canonical files or extra wheel Skill members
fail comparison; a fixed legacy file count is not evidence. The only generated
method exception is that inventory itself. Four entries share one editable
`skills/deck-master/references` tree, packaged at `resources/skill/references`;
other entries contain no copied references.

Candidate installation validates wheel inventory, extracted Host bytes, actual
installed resource bytes and module origin using the candidate interpreter.
`release.json` records each canonical/wheel/Host/installed-package path and hash.
It never borrows source methods through the working directory. Build metadata,
CLI version, workorder dispatch/current method basis and actual Host application
must be recorded separately. `runtime_returned_bytes` is not model application.
Use a temporary prefix, registry and CODEX_HOME for diagnostics; do not alter
real HOME or third-party Skill/config to prove candidate readiness. Real human
professional/desktop acceptance remains separately recorded.
