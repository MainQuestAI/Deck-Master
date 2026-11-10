# Changelog

## Unreleased

- 新增 native 逐页还原文件工具、Tabler outline 图标库与 pptxgenjs 生成器；本阶段成品为 `<作品>/native/deck.pptx`，`deck export pptx` 尚不包含它。
- 默认安装 `deck-master`、`deck-content`、`deck-design`、`deck-review` 四个职责入口到 `~/.codex/skills`，不再安装 `deck` 入口；`--skills-root` 可更换目录，`--skill-dir` 已取消。
- 每个入口改为整个职责目录的软链接，目录内保留真实 `SKILL.md`，让 Codex 能发现这些技能。
- 再次运行安装脚本会只移除指向本源的旧 `deck` 软链接，并将仅含三条托管链接的旧职责包装目录升级为整目录软链接；含用户文件的目录会保留并报冲突。
- 若同名旧 Python 线入口仍占用安装位置，脚本在写入前退出并打印路径和目标；请先移走该软链接（只删链接，不删目标目录）再安装。
- 旧 Python 工作台（`src/deck_master/`、`skills/deck-*`、旧线测试与 `rebuild.yml`）已移出仓库。
- 删除 `deck-master` 命令及其 `legacy-export`，旧项目不再提供官方导出。
- Rust `deck import` 仍可导入已经存在的 `legacy-export.v1` 档案。
- 项目格式 4 → 5：升级会提升 user_version，保留旧版本、文件和历史依据；旧程序遇到高版本格式会拒绝打开；不提供原地降级，回退需要使用升级前保留的完整项目副本。(#310)
- 新增 `GET /api/builds/{id}`，按需持久读取构建详情；workspace 仍只返回构建摘要。(#310)
- 安装布局：`scripts/install.sh` 在 `<prefix>/share/deck/installations/` 下准备完整目录（CLI 与内嵌 WebUI、非 editable 的 deck-tools venv、四个职责 Skill 及共享资源），验证后切换 `<prefix>/share/deck/current` 指针；职责入口链接经由 current；升级保留旧目录。首次多入口迁移中断时，`entry-migrations` 保存已确认入口的迁移凭据，供同参数重试，成功后删除。(#310)
- 嵌套 labels/footnotes/callouts 的子项进入文字回读；材料保留不可变原件副本，`deck material text` 返回该副本路径，原件缺失时为 null。(#310)
- 新 SVG 依据为 svg-v2，纳入 purpose/layout；历史依据保持兼容，原图过期单独显示。(#310)
- 三类编辑共用同一套 draft dirty 判断。(#310)
- 新增 `frontend/browser-smoke.mjs` 浏览器冒烟脚本；CI 新增独立 render job，安装 rsvg/LibreOffice/poppler/CJK 字体后运行 `pytest -m render`。(#310)
- **行为变更**：`deck review add` 的 `--method` 改为必填，不再默认 `human`；漏写时报错并列出 `self_check`、`other_model`、`human`。依赖旧默认值的脚本需显式传入 `--method human`。

## 1.1.2 — 2026-11-09

See [1.1.2 release notes](docs/releases/1.1.2.md) for the changes merged after
`v1.1.1` (`542e1bce`) through `main` after #306 (`32c66bad`). Python
`deck-master`, Rust `deck`, `deck-tools` and WebUI source versions are `1.1.2`.
The release PR prepares these notes; tag `v1.1.2` and the GitHub Release follow
separately after merge. Published status is recorded on
[GitHub Releases](https://github.com/MainQuestAI/Deck-Master/releases), with no
PyPI publication implied.

- Authoring UI: edit task/framing, move/delete pages, edit blocks/bullets/tables,
  read historical versions and compare with current; retain drafts on 409
  without automatic replay (#279–#288).
- Skills: four role entries share one method source; page logic, composition,
  visual systems, reconstruction choices, page-scoped assets and SVG relation
  checks guide production (#289–#293, #295–#296, #298–#299).
- Delivery and revision: fix native-table borders, table letter spacing and
  backtracking curves; add three-layer QA, scoped repair, same-page original /
  compiled-preview comparison and reconstruction object preservation; tighten
  lookup-table success to genuine row-by-row reading tasks whose layout names
  the table as the main visual (#297, #300–#304).
- Follow-ups: refine method guidance and comparison/asset behavior; reject empty
  `--page`, scope tests to the relevant behavior, and avoid new orphan files
  when a page is deleted during conversion (#305–#306).
- D13 has not started; T07 visual human judgment remains open. `visual_review`
  and `desktop_editing` do not auto-pass. Desktop WPS/PowerPoint, officecli,
  full real-install acceptance, the 22-page sample, real Host/ImageGen, browser
  adopt and MA02/MA03 are not claimed verified. LibreOffice cannot replace WPS.
  PPTX-to-deck import remains unimplemented.

## 1.1.1 — 2026-11-05

See [1.1.1 release notes](docs/releases/1.1.1.md).

Follow-ups from the 2026-11-04 maintainer acceptance
([#274](https://github.com/MainQuestAI/Deck-Master/issues/274)).

- `scripts/install.sh` still exits 2 with `已存在且指向其他位置` when the skill
  symlink points elsewhere, and the message now says to remove only that symlink.
  A finished install always prints `<prefix>/bin/deck`; if `deck` is on `PATH`
  it also prints that path, otherwise it says there is no `deck` on `PATH`.
- `deck doctor` now checks `rsvg-convert`. Without `--fonts`, the font line is
  only a warning and does not by itself turn `ready` into `needs_tool`.
- `legacy-export` now lists in `unmapped` any `visual_spec.intent` that differs
  from the page purpose, and every old revision except the current one.
- `stale_pages` and `stale_images` mean the SVG or original-image basis differs
  from the current page. A successful build does not clear them.
- `frontend/package.json` `allowScripts` now lists the locked esbuild and fsevents
  versions, so npm 12 no longer blocks their install scripts.
- When `soffice` is missing, the error gives the install step and says not to
  bypass `deck build` / `deck export pptx` by calling `compile_job`.

- Record the 2026-11-04 maintainer acceptance in the
  [1.1.0 release notes](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04).
  Follow-ups: #274.

## 1.1.0 — 2026-11-04

Source versions: Python package `deck-master` `1.1.0`, Rust crate `deck` `1.1.0`,
file-tools package `deck-tools` `1.1.0`, WebUI package `1.1.0`. Tag `v1.1.0`
is `292fb60a`. Basis is `main` after PR #272 (`abb785eb`), which that tag
contains.

The authoring path is the Rust CLI `deck`, the standalone `deck-tools` Python
package, `deck serve` with the embedded WebUI in `frontend/`, and the Codex
Skill in `deck-skill/`. The previous Python workbench (`src/deck_master/`,
`skills/`) stays in the tree for maintenance only.

See [1.1.0 release notes](docs/releases/1.1.0.md), including the
[2026-11-04 maintainer acceptance](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04).

### Rust rebuild

- **S1 core** (PR #252): `deck new`, `material add` / `material text`, `show`,
  `get`, `put --base`, `restore`, and `export md`. Works live in
  `<project>/.deck/` (SQLite + content-addressed files). Partial `put` merges
  by unit; conflicts exit 5 and leave the current version unchanged.
- **S2 content skill** (PR #256): `deck-skill/` content workflow for brief,
  framing and page copy, calling the S1 commands.
- **S3 tools and delivery** (PR #258): `deck-tools` compile / render / readback
  / sanitize / doctor; `deck run` (image and svg), `deck build`,
  `deck export pptx`, `deck doctor`, `deck asset add`. Late results after
  cancel, and results whose page basis has changed, are stored and not adopted
  automatically. Author spacing is applied on save and delivery (Humanizer);
  semantic wording stays with the Host.
- **S4 serve, API and WebUI** (PR #259, #250, #257, #260): `deck serve <project>`
  binds `127.0.0.1` only and rejects non-local Host / Origin. HTTP covers deck
  read/write, runs, build, file download, Markdown/PPTX export, restore, and
  static assets. The #250 React 18 + Vite WebUI in `frontend/` is embedded by
  `rust/build.rs` and shipped with the binary. Overview, gallery, copy/notes
  editing, run status and cancel, build/download, and version restore are
  wired to live project state. Browser storage failure does not block cancel.
- **S5 page reviews and manual adoption** (PR #261): `deck review add` / `list`
  / `resolve`; HTTP `GET|POST /api/reviews` and resolve. The WebUI lists open
  reviews on the overview and on the page, saves human reviews, and marks them
  resolved. Same-page image or SVG candidate comparison and `run adopt` are
  available from the UI; adoption re-reads the candidate inside the write
  transaction.
- **S6 migration and install** (PR #262): `deck-master legacy-export` writes a
  `legacy-export.v1` archive outside the old project; `deck import` creates a
  new `.deck` project. The old directory is not modified. `scripts/install.sh`
  builds the WebUI, installs `deck`, creates a dedicated deck-tools venv, and
  links `deck-skill/` for Codex. It does not activate or roll back a managed
  Python release.

Slice design remains in the [Rust rebuild plan](docs/specs/rust-rebuild/README.md).

### Fixes

- **#263**: new pages no longer reuse deleted page ids.
- **#264**: a second result for the same run page is kept as an explicit
  candidate instead of replacing the first.
- **#265**: export sanitizer treats ordinary public URL paths (for example
  `/home/products`) as public instead of local paths.
- **#266**: native-table readback checks cell visibility and non-empty titles
  against declared content.
- **#267**: build input digest includes compiler settings, so a settings-only
  change is reported as `input_changed`.
- **#268**: run listing reuses per-page basis digests within one poll instead
  of recomputing them for every historical run.
- **#269**: WebUI connects reviews and fixed left/right candidate comparison
  (current work on the left, selected candidate on the right). Polling does
  not replace an open comparison.
- **#272** (R1–R6):
  - candidate comparison shows compiled previews instead of raw SVG;
  - candidate comparison prompts a reopen when that page's production basis
    changes (image: content/layout/purpose/style; svg: content/image/style);
  - export sanitizer rejects credential-bearing URLs, including credentials
    split across styled runs, and single-slash `file:` / forward-slash drive
    URLs embedded in public links;
  - native tables that leave the slide are reported on readback;
  - presentation mode ends when its page is gone, and Space stays with the
    focused presentation controls.

### CI and cleanup

- **#251**: `AGENTS.md` is the single development standard; rust-rebuild plan
  v1.2 is in-tree.
- **#253**: routine legacy CI is scoped and the default matrix is reduced.
- **#254**: automatic legacy checks run after `main` updates, not on every
  feature-branch push.
- **#255**: `rust.yml` checks the new line on pull requests.
- **#249**: remove byte-identical spec schema mirrors (overdefense P0).

Two workflows: [`rust.yml`](.github/workflows/rust.yml) covers `rust/` and
`deck-tools/` on pull requests and `main`; [`rebuild.yml`](.github/workflows/rebuild.yml)
covers the Python line on `main` only. Render tests that need
rsvg-convert/soffice stay local (`-m "not render"` in CI).

### Also on this source line (after v1.0.0, Python workbench)

These landed on `main` after `v1.0.0` and remain in the maintenance Python
line; they are not the 1.1.0 authoring path.

- PR #189 integration closeout; PR #209 performance v1.2; PR #211 optional
  Humanizer review; PR #197 verified Pillow 13.
- PR #212 content-completion handoff; PR #213 reap owned runtime; PR #214
  content delivery guidance; PR #215 main iteration 2026-10-27; PR #216
  business-expression suite v0.2.

### Known limitations

- UNC paths (`\\server\share`) are not covered by local-path sanitization.
- `GET /api/export/md` does not run the export credential check used on PPTX
  slide text.
- PPTX has been rechecked through LibreOffice rendering in the tool tests.
  `scripts/install.sh` runs on Linux CI (`ubuntu-latest`). The 2026-11-04
  maintainer check is in the
  [1.1.0 release notes](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04).
- The legacy test
  `test_small_json_cache_detects_corruption_and_returns_independent_objects`
  can fail on Linux: the cache signature includes ctime and the test rewrites
  the file within one clock tick. It is a test-timing issue in the old line and
  was not changed here.
- Native editable PPT still uses shapes and text. Tables and charts are
  composed shapes/text, not Office-native spreadsheet-backed objects.
- `doctor` finding a font family does not prove LibreOffice can render every
  glyph. Fontconfig/LibreOffice Chinese glyph substitution remains as
  documented in the [first-run guide](docs/getting-started.md#known-limitations).

## 1.0.0 — release preparation, 2026-10-21

Python package `1.0.0`; intended tag `v1.0.0`. Publication and final candidate
validation remain separate from this source preparation.

- Integrate the RC5 content-method catalog, bounded Host resource selection,
  dependency expansion and frozen Task methods from PR127.
- Add structured support/feedback and contribution guidance from PR128.
- Clarify current documentation and preserve dated evidence through the
  documentation and archive indexes from PR129.
- Replace retired Make/script entry points with the rebuilt CLI and current
  checks; retire the unvalidated legacy Docker/Dev Container entry and document
  the supported local Python installation instead.

- Integrate PR130's fixed-revision content/method reading, narrative comparison,
  direction adoption recovery, source evidence and bounded review handoffs.
- Preserve image request ownership when aborting, replacing or removing queued
  image work; release active leases synchronously on cancellation.

Exact-source validation and release assets are tracked in the
[release preparation record](docs/releases/1.0.0-preparation.md). Historical observations
below retain their original version and scope. Font rendering, professional
human review and desktop editing limitations remain in the first-run guide.

## 1.0.0rc4 — candidate, 2026-10-20

Release candidate of the rebuilt, local-first Deck Master core. Python
package version `1.0.0rc4`; proposed prerelease tag `v1.0.0-rc4`. The earlier
1.0.0 source preparation was not published; its formal release is cancelled.
This candidate supersedes the historical
v0.9 preview architecture; old project formats require the documented migration.

- One `deck-master` CLI and loopback Workbench for source-backed content,
  scoped design, editable SVG/PPT production, review, recovery and delivery.
- Four managed Codex Skills share one canonical method source; new Tasks
  freeze their exact ordered methods and applicable content policy.
- Recoverable input receipts and installation transactions preserve exact
  retries, interrupted work, cancellation and current authorization.
- Negotiated `work_context.v2` supports full context and bounded deduplication;
  history queries preserve committed ancestry and unknown outcomes.
- Normal installed native independent review uses an actual fresh Codex
  session and the existing authenticated receipt path. Literal MCP server names,
  including dots, quotes and Unicode, remain disabled in that session.
- Release installation, external Host requirements, first use, upgrade,
  font configuration limits and contribution guidance are documented.

The functional baseline PR125 (`d7ec4530`) passed both 7-job CI runs. The
maintainer's actual installed Host task completed native review, native-image
observations on two pages, real SVG/PPT rendering and formal delivery with
`handoff-check verified`. Chinese LibreOffice rendering required an existing
process-scoped Fontconfig configuration. Actual WPS editing was not verified
because the device locked. These observations are not a general desktop,
professional-review or operating-system certification.

See [first run and known limitations](docs/getting-started.md). Publishing a
tag/Release and activating a user's installation are separate operations.

## Pre-rebuild unreleased notes (historical)

These entries belong to the retired preview architecture and are retained as
history; its RC Gate and companion setup are not current release requirements.

- Enforce final artifact approval at every client export entry.
- Return a failing process status when RC Gate is blocked or failed.
- Preserve fixture run mode across state and routing commands.
- Package Skill OS registries and expand isolated release smoke coverage.
- Require delivery-grade evidence before benchmark reports qualify for RC.

## v0.9.14-preview.4

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.4` maps to Python
package version `0.9.14a4`. Skill Suite contract version remains `1.1.0`.
This patch preview supersedes `v0.9.14-preview.3` without changing the
high-density content or rendering behavior.

This patch fixes release-runtime packaging and capability discovery:

- Installed releases discover v2 high-density contracts from the canonical
  release `contracts/` directory as well as the source `docs/contracts/`
  directory.
- Python entrypoints inside the moved release virtual environment are
  repaired to point at the active release path instead of the staging path.
- Added regression coverage for installed contract discovery and moved
  virtual-environment launchers.

Validation includes the full release-runtime and high-density regression set:
`110 passed`, `4 subtests passed`, Ruff, compile checks, and `git diff --check`.

## v0.9.14-preview.3

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.3` maps to Python
package version `0.9.14a3`. Skill Suite contract version remains `1.1.0`.
This preview does not claim production readiness.

This preview adds the independently installable High-Density Builder route:

- MBB content enrichment with storyline selection, evidence binding, SCR, and
  page-level content planning.
- Content-safe ImageGen blueprint generation with page-number and internal-label
  prohibitions.
- Native SVG reconstruction with controlled icon, curve, table, text, and
  visual-registration gates.
- SVG-authoritative DrawingML PPTX compilation, readback, trace, and visual
  parity checks.
- Fail-closed migration handling for retired content-planning artifacts and
  release evidence that accurately reports unavailable private benchmarks.

Validation for this preview includes `1399 passed` and `105 subtests passed`,
Python 3.11/3.12 compile checks, Ruff, JSON contract validation, release smoke,
and local installation verification.

The fresh provider smoke, six-page external icon acceptance, and 73-page
external benchmark remain release gates and are not represented as completed
in this preview.

## v0.9.14-preview.2

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.2` maps to Python
package version `0.9.14a2`. This preview does not claim production readiness.

This preview carries the final release hygiene patch after
`v0.9.14-preview.1`, including Python 3.12 CI coverage, release checklist
closure, PPT Library handback wording cleanup, and refreshed Agent QA routing.

## v0.9.14-preview.1

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.1` maps to Python
package version `0.9.14a1`. This preview does not claim production readiness.

This preview focuses on open-source readiness:

1. Apache-2.0 project license.
2. Standard editable install through `pyproject.toml`.
3. Public first-run fixture demo and Review Desk path.
4. Backend readiness transparency when production companions are not configured.
5. M1 `preview-gate` separated from M2 `rc-gate`.
6. Review Desk local write protection with token and same-origin guard.
7. Source checkout verification commands that do not assume `deck-master` is already on PATH.

This preview does not carry formal GA support guarantees.
