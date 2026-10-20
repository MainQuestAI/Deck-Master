# Installation

The rebuilt Python package exposes one CLI: `deck-master` or `python -m deck_master`.
For development, use Python 3.11 or 3.12 and `python -m pip install -e '.[dev]'`.
A release used from Codex also needs its managed Skill registration.
For release downloads, external Host requirements, first use and upgrade, see
the repository's `docs/getting-started.md`. Published assets are listed at
https://github.com/MainQuestAI/Deck-Master/releases; a package version alone
does not mean an installation has been activated.

## Candidate, activation and rollback

Build and check the candidate first. `install candidate` creates an isolated
virtual environment, extracts the four `skill/<name>/` entries and shared methods from the wheel, and runs
compile/render/compose/view checks. It does not activate or register the Skill.

```bash
python tools/build_release.py --out /path/to/new-release
python -m deck_master install candidate \
  --prefix /path/to/prefix --manifest /path/to/new-release/release.json
python -m deck_master install activate \
  --prefix /path/to/prefix --release-id <release_id> --transaction-id <UUIDv4>
/path/to/prefix/.deck-master/bin/deck-master doctor --step compose
/path/to/prefix/.deck-master/bin/deck-master install rollback \
  --prefix /path/to/prefix --transaction-id <another_UUIDv4>
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

## Durable transaction recovery

Both activate and rollback accept an optional canonical, lowercase UUIDv4
`--transaction-id`. Keep the exact ID for retries. It binds the verb, prefix,
activation release, Host root and registration option; rollback freezes its
actual old/new targets before switching. The durable journal lives under
`<prefix>/.deck-master/transactions/activation/<id>.json`, with
`activation-pending.json` in that installation root. These are installation
facts, not a project Document or production authorization.

`preparing` durably freezes the request, old managed state and each preparation
intent before creating `.after` or `.witness` items. Retry the original ID and
request after interruption. An item whose ownership was not durably established
is preserved; that same transaction can prepare again in a separate recorded
namespace without claiming or deleting the residual item.

A matching unfinished request resumes even when the ID is omitted. A different
request reports `installation_transaction_pending` with the original ID;
same-ID/different-binding reports `installation_transaction_conflict`. Reuse
the original request. Recovery rechecks real pointers, launcher, four links,
preparations and backups rather than trusting a recorded completed step.
It holds the prefix lock, then the shared Host lock, and rechecks after waiting.
The retained Host lock coordinates managed installers across prefixes.
Directory symlinks for the Host Skill root retain their existing compatibility:
the transaction locks and plans against the verified real directory, checks the
original access chain, and keeps the logical `skill_link` paths in CLI results.

An explicit completed ID only returns its original receipt. Original
`cli_active` and `host_skill` describe that completed transaction;
`observed_current_release_id` / `current_install_state` independently describe
the installation observed now. A later switch may make these differ. A
completed rollback called again without its ID is a new toggle using current
`previous`; it can switch back and must not be taught as an exact retry.

Ctrl-C returns exit 130 with the observed transaction state. `compensating`
continues reverse recovery; a terminal `rolled_back` ID replays its original
failure, so a genuinely new attempt needs a new ID after the cause is resolved.
`installation_recovery_conflict` preserves external content and the retained
`.before`/`.after`/`.witness` or legacy backups for diagnosis; do not overwrite
these or claim full restoration. Unverifiable records report unknown; a failure
with a durable preparation record can report `preparing` and resume the original
request. Preserve the journal and inspect the named paths.

`--no-host-registration` never resolves, locks, scans, reads or writes Host
paths, including interrupted legacy migration recovery. It changes only the
selected prefix. A request that used this option must retain it on exact retry.

Rollback follows `previous` and keeps method and CLI releases aligned. If the
previous release predates the Skill, managed links missing from that release are removed and the result
reports `host_skill_unregistered`. Project data and recorded calls are not rolled back. RC3-04 projects use the
forward writer floor `rc3-entry.v1`; new RC4 method/policy facts atomically
require `rc4-content.v1`. A real older writer must refuse these projects after
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

## Generation workbench v3

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

## Candidate resource identity

The development source version is PEP 440 `1.0.0rc5` (RC5 is incomplete); read the actual CLI,
package metadata and capabilities rather than assuming the active installation
has been upgraded. `tools/build_release.py` builds both wheel and
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
