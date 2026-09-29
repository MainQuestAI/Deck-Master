# Migration to the Rebuilt Core

The rebuilt core (spec pack v1.1) replaces the v0.9.x Run OS. This note is the
single place that explains what moved, what retired, and how to treat old
runs. Nothing here deletes files; retirement and cleanup follow task T24.

## One Command Surface

The only entry is the rebuilt CLI:

- Installed: `deck-master …` (console entry `deck_master.cli:main`).
- Source checkout: `python -m deck_master …`.
- `python3 scripts/deck_master.py` is legacy. New commands never import or
  exec it.

`deck-master legacy-map` prints the full mapping table. Summary (spec 09.6):

| Class | Old entries | Behaviour |
| --- | --- | --- |
| Alias (runs new semantics) | `agent-doctor`, `next-step`, `run-state`, `final-readiness`, `import-plan`, `product-capability-manifest`, `doctor`, `export` | Executes the rebuilt flow; read-only entries return the same `deck_view.v1` projection |
| Alias (legacy build subcommands) | `build prepare`, `build status` | Read-only status derived from the current ProjectView; `build run` points at `deck --project <dir>` |
| Guidance (exit 2, typed JSON) | `start-conversation`, `plan`, `build-brief`, `build-claim-map`, `autoplan`, `search-library`, `decide-sourcing`, `library-status`, `import-library-selection`, `record-library-feedback`, `uat-ppt-library`, `validate-ppt-library-result`, `suite-status`, `suite-install`, `suite-repair`, `setup`, `setup-status` | Points at the correct new command; never silently generates a rule-based draft or requires a slide library |
| Retired (exit 2, typed JSON) | `backend`, `rc-gate`, `preview-gate`, `release-*`, `suite-*`, `benchmark-*`, `uat-*`, `render`, `workflow`, `init-*`, `delivery`, `opportunity`, `connector`, generation/handoff/import-preview commands, `install-skill`/`uninstall-skill`, … | Refuses explicitly; not a prerequisite for any new task |

## What Is No Longer Required

- No PPT Master backend binding or SHA certification.
- No PPT Library installation or workspace/template bootstrap.
- No first-run `setup`; a plain material directory is enough:
  `deck-master create --brief … --source … --out …`.

Renderer and font gaps are reported per doctor step as `needs_tool` with the
real reason.

## Old Runs

A v0.9.x run directory keeps its bytes. New write commands recognise the old
shape (`preview_manifest.json` / `run.json` markers, no `.deckmaster`) and
refuse with `legacy_run_format`; they never migrate or initialise it in place.

Options for an old run that still matters:

1. **Pin the old release** for that run and keep operating it with the legacy
   toolchain. Do not mix the new CLI writers into the same run.
2. **Import read-only into a new project copy**:

```bash
# dry-run first: pages, media, unknown fields, source-hash plan
deck-master import legacy --input <old-run> --out <new-project> --inspect

# real import: copies allowed media into new objects with real byte hashes,
# maps v1 visible copy/relations to Page v2, keeps speaker notes,
# records old completed/pass strings as history only
deck-master import legacy --input <old-run> --out <new-project>
```

Known inputs: a `deck_page_package.v1` page pack (single file or a directory
of `*.v1.json` pages) and an HD run directory (`preview_manifest.json` +
`narrative_plan.json` + `page_tasks.json` with SVG/PPT media). Anything else
is refused with the concrete fields found — nothing is guessed from
substrings, and unknown body-block shapes stop the import with a pointer
(e.g. `pages[p09]/customer_visible/body_blocks/1`) until you map them.

Import semantics:

- The source run is strictly read-only: every file's sha256 is snapshotted
  before and after; any change refuses the copy. No `.deckmaster` is created
  inside the source, and no legacy script is executed.
- Media bytes land in the new objects with their real sha256 and a
  `legacy_import` provenance note; the original URI is recorded. A missing
  original keeps `original_sha256: null` — never a fabricated value, and an
  all-zero fingerprint is rejected outright.
- If the original file is restored later, it is **not** retroactively claimed
  as the verified original; only hashes actually measured at import count.
- The new project starts with zero reviews: `review_status` is
  `not_evaluated` and human/professional evidence stays unverified until real
  checks run. `deck-master import-draft` remains the path for drafts that are
  already Page v2.

## Status Semantics

- Exit 0 / completed tasks are engineering facts, never professional approval.
- `export --purpose review` ships unfinished decks with the real unresolved
  list; `--purpose delivery` requires passing current checks (and, when the
  policy demands it, a non-failing professional/human review on the current
  output).
- PPTX output is editable shapes and text; tables/charts are not Office-native
  data objects.

## Third-Party Skills

仓库中旧的多 Skill 入口已退役，统一使用 `skills/deck-master/SKILL.md`。
旧入口到新命令的对照见 [Flow Quality 迁移说明](specs/deck-master-flow-quality-v1.1/MIGRATION.md)。
本机第三方 Skill 保持原样；安装器只迁移已识别的旧 companion 目录和属于该目录的失效链接。

## Document Map

- Routing: [docs/agent-task-index.md](agent-task-index.md)
- Blocked states: [docs/agent-recovery-playbook.md](agent-recovery-playbook.md)
- Contracts: [src/deck_master/resources/contracts/](contracts/)
- Rebuild baseline: [docs/specs/deck-master-rebuild-v1/](specs/deck-master-rebuild-v1/)
- Historical spec packs under `docs/` are archived references, not current
  truth.

## Fixed-revision exports (Workbench W11)

`export --revision <committed-id> --purpose review|delivery|engineering --out <new-directory>`
freezes one snapshot before reading artifacts. Omit `--revision` to capture current
at start; background commits cannot change the package. Retry a download using
its returned export ID. A CLI retry also supplies the same revision and purpose.

The old `review` package included a portable project. **That behavior is retired:**
`review` now contains readable page text, available images/SVG/PPTX, missing-stage
information and a hash manifest. It works before a PPT exists. `working` remains
an alias. Use `engineering` explicitly for internal recovery: it includes original
materials, complete prompts, immutable objects and the selected snapshot's
committed ancestry. Treat this package as internal. Runtime authentication,
service state, locks, caches and personal UI drafts are excluded.

Public packages clean copies of PNG/JPEG metadata, SVG metadata/comments and
PPTX properties/notes/comments/non-visible shape descriptions/printer settings.
Pixels, visible text and ordinary hyperlinks are retained; unsupported embedded
files, external SVG assets, macros, unnormalized EXIF orientation or private values in retained content refuse
export with `export_privacy_blocked`. Immutable originals are unchanged. Public
PPTX hashes can therefore differ from the original; `handoff-check` recognizes a
deterministically cleaned copy by recomputing it from the current original.
This cleanup is not a replacement for reviewing visible customer content.

`delivery` still requires the selected snapshot's effective engineering checks,
input alignment and applicable professional-review policy. Failure returns exit
3 / HTTP 409 with `revision_id`, page/layer `gaps` and an offline recovery link.
It does not borrow a pass from current when exporting history. Counts of text
runs/shapes, editability declarations, professional review and desktop editing
remain separate facts; missing evidence is not a pass.

Browser clients use same-origin `POST /api/exports` with the normal session token
and only `purpose`, `revision`, `export_id`; returned download URLs select a
project-local export ID and whitelisted file. CLI/Host clients use the CLI.
No new Origin-bypass token exists. Files are checked against their frozen hashes
on every download. Existing output directories are never overwritten.

`history plan-restore` records a read-only impact plan; `history commit-restore`
requires that plan, the unchanged base revision and a UUIDv4 operation ID.
Confirmation creates a new revision, preserving current task facts, call history,
policy and `user_stop`; in-flight tasks become superseded. A lost receipt can be
recovered through `operations show` or replaying the exact same request. The old
`history restore` command remains available with its existing semantics. Restored
engineering projects retain their writer floor; older writers must still refuse
unsupported formats. This change does not migrate HOME or switch the default UI.
