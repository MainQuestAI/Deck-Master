# Deck Master High-Density Builder Engineering Spec v1

日期：2026-08-05
状态：Superseded historical baseline
适用范围：Deck Master 高密度 Builder 独立 Skill 的合同、命令、运行时、证据链和首版工程包

> 本文件已被 `deck-master-high-density-builder-core-engineering-spec-v2.md` 替代。PR #15 只完成工程外壳，本文中的 P0/P1 完成口径和 First Engineering Acceptance 不再有效。后续实现、评审和验收统一以 v2 Spec 为准。

## 0. 结论

Deck Master 下一版高密度 Builder 采用独立 Skill 包：

```text
deck-builder-high-density
```

该 Skill 在仓库内独立实现和发布，不运行时调用 CyberPPT、`native-svg-redraw` 或 PPT Master Skill。三套参考能力只作为方法和验收基线，代码从零实现。Deck Master 工作流仍使用 `deck-builder` 阶段，`--profile high-density` 将该阶段路由到独立 Skill。

用户入口保持收敛：

```bash
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
deck-master build status --run-dir <run_dir> --profile high-density
```

首版工程目标：

```text
Page Package
-> content_lock.v1 with NBB enrichment
-> high-density blueprint
-> page_scene.v1
-> native SVG
-> native DrawingML PPTX
-> high_density_manifest.v1
-> canonical build/artifact/render handback
-> deck-quality independent gate
```

首版验收目标锁定 `production_pptx`。`client_delivery` 不进入首版高密度验收门，等现有 release readiness blocker 清掉后再接入。

## 1. Supersedes

本 Spec 替代以下旧口径：

- 高密度 Builder 仍处于 P01-P03 小样本 MVP。
- 独立 Skill 是否成立仍待裁决。
- 70+ 页链路仍属于下一轮外部验证。

当前前提更新为：

- 73 页级别的旁路 MVP 已完成，可作为产品路线实证。
- 73 页证据暂不直接进入公开 repo 原文档；后续只导入脱敏 evidence index。
- 真实工程仍从合同和运行时开始，避免生成链路先行后再补 manifest。

旧文档仍保留为需求历史：

- `docs/specs/high-density-ppt-builder-skill-requirements.md`
- `docs/specs/deck-master-high-density-builder-next-iteration-spec.md`

## 2. Non-Negotiables

1. 独立 `deck-builder-high-density` Skill 是产品方向。
2. 用户入口是 `deck-master build ... --profile high-density`。
3. CyberPPT 的内容增强和 ImageGen 蓝图能力必须迁移，不能退化成普通大纲生成。
4. 主质量路径是 `content/image blueprint -> native SVG -> native DrawingML PPTX`。
5. 最终 PPTX 的关键内容必须可编辑，禁止整页图片封装承载主要信息。
6. High-density 自审只能作为生产证据，最终质量放行归 `deck-quality`。
7. 首版只做单一高质量路径，不引入多后端、质量档位和风格市场。
8. NBB 内容增强、ImageGen 蓝图、SVG 重绘和 DrawingML 编译由独立 Skill 完整承接；首版不得依赖三套参考 Skill 的运行时串联。
9. Page Package 是事实和证据真相源；`content_lock.v1` 是其构建期冻结投影和受控扩展。

## 3. Current Repo Facts

### 3.1 已有基础

- `build-manifest.v2` schema 已存在。
- `scripts/build/manifest.py` 已有 `build_manifest_v2()`，能从 Page Package 生成 v2 manifest。
- Stage Contract 已要求 `deck-builder` 消费 `page_packages/`，并输出：
  - `build_manifest.json`
  - `artifact_manifest.json`
  - `render_result.json`
- `artifact-manifest.v1`、`render-result.v2` 已是后续 `deck-quality` 的主要 handback 入口。
- 生产后端和 render runtime 当前可用；`client_delivery_ready` 仍被依赖快照阻断。

### 3.2 当前冲突

| Area | Current State | Required for High-Density |
| --- | --- | --- |
| CLI | `build prepare/run/status` 无 `--profile` | 增加 `--profile high-density` |
| runtime build | `scripts/runtime/build.py` 仍写 `deck_build_manifest.v1` | 生产路径写 `deck_build_manifest.v2` |
| production input | runtime 仍读 `preview_manifest.json` | 生产路径消费 `page_packages/` |
| manifest profile | `build-manifest.v2` 顶层禁止额外字段 | 增加合法 `builder_profile` |
| capability | 只有 `deck_master.build.v1` | 增加 `deck_master.build.high_density.v1` |
| lineage | final artifact manifest 不承载内部过程件 | 新增 `high_density_manifest.v1` |
| recovery | `next-step` 未理解高密度页级状态 | 增加 stage/page 级恢复映射 |
| execution | standard production path 可返回 `awaiting_external_render` | high-density 使用 Agent-managed internal build path |
| skill registration | manifest 只登记 `deck-builder` | 独立登记 `deck-builder-high-density` 并绑定 high-density profile |

## 4. Ownership Matrix

| Owner | Owns | Produces | Cannot Own |
| --- | --- | --- | --- |
| `deck-producer` | facts, evidence, page claims, approved page content | Page Package, evidence bindings, density plan | PPTX build, final quality release |
| Deck Master Run OS | profile routing, capability discovery, run state, resume, invalidation, `next-step`, canonical handback | workflow state, next command, blocker state | page content authorship, final artifact self-approval |
| `deck-builder-high-density` | NBB enrichment and high-density production engine | `content_lock.v1`, blueprint, `page_scene.v1`, native SVG, PPTX candidate, self-review evidence, `high_density_manifest.v1` | unsupported factual claims, final delivery approval |
| `deck-quality` | independent quality and customer-visible safety gate | quality report, editability verdict, delivery/readiness blocker | generating or mutating page content |

## 5. Contract Version Matrix

| Contract | Role | Producer | Consumer | v1 Decision |
| --- | --- | --- | --- | --- |
| `deck_master.build.v1` | baseline build capability | Deck Master suite | Stage contract | keep |
| `deck_master.build.high_density.v1` | optional high-density build capability | `deck-builder-high-density` package | CLI, suite-status, stage contract | add |
| `deck_build_manifest.v2` | canonical builder manifest | build runtime | renderer, quality, next-step | extend with `builder_profile` and high-density refs |
| `deck_artifact_manifest.v1` | final artifact manifest | build runtime / renderer | quality, review | keep final artifacts only |
| `deck_render_result.v2` | renderer handback | high-density renderer | build status, quality | keep final PPTX and preview refs |
| `content_lock.v1` | build-scoped content projection | `deck-builder-high-density` | blueprint, scene, SVG/PPTX compiler | add |
| `high_density_manifest.v1` | internal lineage manifest | high-density engine | debug, retry, quality evidence import | add |
| `high_density_status.v1` | profile execution state | high-density engine | CLI status, Run OS, next-step | add |
| `blueprint_manifest.v1` | ImageGen blueprint lineage and approval | high-density engine / Agent | scene, SVG review, retry | add |
| `page_scene.v1` | semantic page IR | high-density engine | SVG/PPTX compiler and QA | add |

## 6. Profile Semantics

### 6.1 CLI

User-facing spelling:

```text
high-density
```

Internal enum:

```text
high_density
```

Allowed first-version profiles:

```text
standard
high_density
```

CLI rules:

- `--profile high-density` maps to `builder_profile=high_density`.
- `--profile high_density` is invalid CLI input.
- Unknown profile returns `BUILD_PROFILE_UNSUPPORTED`.
- Requested high-density with missing capability returns `HIGH_DENSITY_CAPABILITY_MISSING`.
- Existing manifest profile conflict returns `BUILDER_PROFILE_MISMATCH`.

### 6.2 Field Separation

| Field | Meaning | Example |
| --- | --- | --- |
| `run_mode` | execution environment | `production`, `fixture`, `dev`, `benchmark` |
| `builder_profile` | build route | `standard`, `high_density` |
| `output_profile` | delivery target | `production_pptx`, `client_delivery` |

First version default:

```json
{
  "builder_profile": "high_density",
  "output_profile": "production_pptx"
}
```

### 6.3 Skill Packaging and Discovery

Source layout:

```text
skills/deck-builder-high-density/SKILL.md
scripts/high_density/
docs/contracts/content-lock.v1.schema.json
docs/contracts/page-scene.v1.schema.json
docs/contracts/high-density-manifest.v1.schema.json
docs/contracts/high-density-status.v1.schema.json
```

Registration rules:

- `skills/manifest.json` contains a separate `deck-builder-high-density` entry with `stage_id=deck-builder`, `profile=high_density` and capability `deck_master.build.high_density.v1`.
- Skill manifest validation allows multiple profile implementations for one stage while requiring exactly one default implementation.
- `product-capability-manifest.json` lists the Skill as an optional public capability until the first engineering acceptance passes.
- The profile route is explicit: `deck-builder + high_density -> deck-builder-high-density`.
- The `deck-builder` stage keeps `deck_master.build.v1` and conditionally requires `deck_master.build.high_density.v1` when the selected profile is high-density.
- `suite-status --capability deck_master.build.high_density.v1` checks the Skill file, profile route, runtime package, contract schemas and required local dependencies.
- The standard `deck-builder` entry remains the default route and does not depend on the high-density capability.

### 6.4 Runtime Execution Boundary

Deck Master keeps its zero-built-in-LLM-provider policy. The independent Skill is the Agent-owned execution layer: it calls ImageGen through the active Agent environment and invokes repository-owned high-density scripts for scene, SVG, PPTX and validation work.

Execution rules:

- `build prepare --profile high-density` creates the v2 manifest and high-density state.
- `build run --profile high-density` starts or resumes the internal profile route.
- When Agent/ImageGen work is required, the command returns `awaiting_agent_build` with a machine-readable `next_command` or `next_action`; the same Skill invocation continues the work.
- A high-density run cannot emit `awaiting_external_render` and does not require `import-render-result` from PPT Master.
- Managed subprocesses are allowed, while manual external render handoff is outside the high-density path.
- Completion writes `high_density_manifest.v1` and the existing canonical handback contracts.
- The standard profile keeps the current external render handoff behavior.

## 7. Schema Changes

### 7.1 `deck_build_manifest.v2`

Add top-level field:

```json
{
  "builder_profile": "high_density"
}
```

Recommended schema:

```json
{
  "builder_profile": {
    "enum": ["standard", "high_density"],
    "default": "standard"
  }
}
```

Compatibility rules:

- Existing valid v2 manifests without `builder_profile` remain valid and are read as effective `builder_profile=standard`.
- New writers always emit `builder_profile`; `build_manifest_v2()` receives a keyword argument whose default is `standard`.
- `builder_profile` stays optional in the JSON Schema for v2 read compatibility. Runtime normalization supplies the effective default without rewriting the source file.
- `high_density_manifest` is allowed only for `builder_profile=high_density` and becomes required when a high-density build manifest reaches `status=completed`.
- Standard manifests reject `high_density_manifest`.
- Schema, generator, loader/normalizer, validator and compatibility tests land in one engineering package.
- This additive change keeps `deck_build_manifest.v2`; no in-place migration command is required in P0.

Add optional high-density refs:

```json
{
  "high_density_manifest": "high_density_build/high_density_manifest.json"
}
```

Do not hide profile inside `builder_backend` extras. Profile controls the build route and should be visible to Run OS, `next-step` and `deck-quality`.

### 7.2 `content_lock.v1`

Purpose: freeze the exact customer-visible content used by the high-density build while preserving Page Package lineage.

Required top-level fields:

```json
{
  "schema_version": "deck_content_lock.v1",
  "run_id": "run-id",
  "page_id": "P001",
  "page_package_ref": "page_packages/P001.json",
  "page_package_sha256": "<64hex>",
  "source_fingerprint": "<64hex>",
  "customer_visible": {},
  "evidence_bindings": [],
  "enrichment": {
    "framework": "nbb",
    "derived_claims": [],
    "structure_decisions": []
  },
  "created_at": "2026-08-05T00:00:00Z"
}
```

Truth and mutation rules:

- `customer_visible` starts from the Page Package and may be reorganized, compressed or expanded through NBB enrichment.
- Every added factual statement, number and caveat requires an existing evidence binding or an explicit new evidence reference accepted before blueprint generation.
- Unsupported ImageGen text never enters the lock.
- The lock records `page_package_sha256`, `source_fingerprint` and its own file hash in `high_density_manifest.v1`.
- A Page Package hash change invalidates the lock and every downstream artifact.
- Downstream repair may update layout or scene geometry. Content changes require regeneration of the lock and downstream invalidation.
- The lock never writes enriched content back into the Page Package automatically.

### 7.3 `high_density_manifest.v1`

Purpose: record internal lineage without overloading final artifact manifest.

Required top-level fields:

```json
{
  "schema_version": "deck_high_density_manifest.v1",
  "run_id": "run-id",
  "builder_profile": "high_density",
  "source_fingerprint": "<64hex>",
  "status": "completed",
  "pages": [],
  "created_at": "2026-08-04T00:00:00Z"
}
```

Page fields:

```json
{
  "page_id": "P001",
  "order": 1,
  "status": "completed",
  "content_lock": {"path": "...", "sha256": "..."},
  "blueprint": {"path": "...", "sha256": "..."},
  "page_scene": {"path": "...", "sha256": "..."},
  "svg": {"path": "...", "sha256": "..."},
  "preview": {"path": "...", "sha256": "..."},
  "visual_review": {"path": "...", "sha256": "..."},
  "pptx_trace": {"path": "...", "sha256": "..."},
  "readback_report": {"path": "...", "sha256": "..."},
  "blockers": []
}
```

Path rules:

- Repo/run artifacts use run-relative paths.
- External evidence uses explicit `external_ref` objects with path class and hash, not raw private material.
- Absolute local paths are not written into repo docs or customer-visible artifacts.

### 7.4 `page_scene.v1`

Purpose: stable semantic page model between locked content, SVG and PPTX.

Required top-level fields:

```json
{
  "schema_version": "deck_page_scene.v1",
  "run_id": "run-id",
  "page_id": "P001",
  "canvas": {"width": 1672, "height": 941, "unit": "px"},
  "content_lock_sha256": "<64hex>",
  "elements": [],
  "created_at": "2026-08-04T00:00:00Z"
}
```

Element fields:

```json
{
  "element_id": "title.main",
  "role": "title",
  "priority": "P0",
  "bbox": {"x": 80, "y": 64, "w": 900, "h": 72},
  "text_ref": "content_lock.customer_visible.title",
  "evidence_refs": ["E001"],
  "text_fit": {"preferred_size_px": 36, "min_size_px": 28, "max_lines": 2},
  "overflow_policy": "block",
  "editability_target": "native_text",
  "asset_policy": "none",
  "pptx_expectation": {"object_type": "text", "must_readback": true}
}
```

Element priority:

- `P0`: title, key claim, key numbers, SO WHAT, sources, core table text.
- `P1`: major cards, connectors, chart labels, explanatory text.
- `P2`: decorative texture, minor icons, background accents.

Registered image assets:

- `kind=image` requires `asset_policy=registered`, `editability_target=registered_asset`, `asset_ref` and `asset_sha256`.
- `asset_ref` is the approved `asset_id` from the source Page Package `asset_bindings`, never an arbitrary filesystem path.
- The binding must be approved, run-relative, limited to PNG/JPEG in the first implementation, and hash-identical to both the Page Package and the scene.
- The compiler embeds registered assets only in their declared local bbox. A full-canvas image wrapper, external URL, unregistered asset, or stale asset hash blocks the page with `HD_ASSET_POLICY_BLOCKED`.

### 7.5 `high_density_status.v1`

Purpose: expose profile-specific progress and Agent continuation without adding unsupported values to canonical build or render status enums.

```json
{
  "schema_version": "deck_high_density_status.v1",
  "run_id": "run-id",
  "builder_profile": "high_density",
  "status": "awaiting_agent_build",
  "current_page_id": "P001",
  "current_stage": "blueprint",
  "next_action": {
    "kind": "agent_imagegen",
    "page_id": "P001",
    "stage": "blueprint",
    "input_ref": "high_density_build/content_locks/P001.json",
    "output_ref": "high_density_build/blueprints/P001.png",
    "resume_command": "deck-master build run --run-dir <run_dir> --profile high-density"
  },
  "updated_at": "2026-08-05T00:00:00Z"
}
```

State projection rules:

- `high_density_status.v1` owns `prepared`, `building`, `awaiting_agent_build`, `completed`, `blocked`, `failed` and `stale`.
- While high-density status is `awaiting_agent_build`, `deck_build_manifest.v2.status` remains `building`.
- Canonical `render_result.v2` is written only after an internal rendering attempt reaches `completed`, `partial` or `failed`.
- Run-state and `next-step` read the profile status and expose its exact `next_action`.
- `build status --watch` returns immediately on `awaiting_agent_build`, `completed`, `blocked` or `failed`; actionable waiting returns the continuation payload.

## 8. Directory Layout

Inside a run:

```text
high_density_build/
  status.json
  high_density_manifest.json
  content_locks/
  blueprints/
  page_scenes/
  svg/
  previews/
  reviews/
  pptx/
  readback/
  traces/
```

Canonical handback remains:

```text
build/build_manifest.json
build/artifact_manifest.json
render_results/render_result.json
```

`deck-quality` should read canonical handback first. It may follow `high_density_manifest` for detailed evidence.

## 9. Stage Pipeline

### Stage A: Content Lock

Owner: `deck-builder-high-density`

Inputs:

- Page Package.
- evidence table.
- density plan.
- SCR / storyline plan.
- NBB enrichment rules migrated from the CyberPPT reference workflow.

Outputs:

- `content_lock.<page_id>.json`
- stable hash.
- enrichment lineage and evidence bindings.

Hard gates:

- every key claim, number and caveat binds evidence.
- ImageGen cannot be fact source.
- low-density page content is blocked before blueprinting.
- internal-only notes cannot leak into customer-visible fields.
- Page Package hash and source fingerprint match the lock lineage.
- NBB enrichment expands structure and explanatory depth without creating unsupported facts.

### Stage B: Blueprint

Owner: `deck-builder-high-density`

Inputs:

- content lock.
- density plan.
- style lock.

Outputs:

- blueprint image.
- `blueprint_manifest.<page_id>.json`.

Hard gates:

- blueprint prompt hash recorded.
- blueprint image hash recorded.
- source canvas and approved 16:9 `slide_frame` are recorded in the blueprint manifest.
- mapping from `slide_frame` to the canonical canvas uses one uniform affine transform; silent non-uniform stretch is forbidden.
- page number, generation annotations and internal labels are absent from the approved slide frame.
- generated text is treated as layout/OCR hint only.
- final text remains from content lock.

### Stage C: Page Scene

Owner: `deck-builder-high-density`

Inputs:

- content lock.
- blueprint manifest.
- visual element inventory.

Outputs:

- `page_scene.<page_id>.json`.

Hard gates:

- P0/P1 elements have bbox and role.
- text targets reference content lock.
- asset policy is explicit.
- editability targets are defined.

### Stage D: Native SVG

Owner: `deck-builder-high-density`

Inputs:

- blueprint image.
- page scene.
- style lock.

Outputs:

- native SVG.
- preview PNG.
- subagent self-review JSON.
- main review JSON.

Hard gates:

- no `foreignObject`, `script`, `iframe`, external dependency or whole-page image.
- P0/P1 text overflow blocks.
- container overflow blocks.
- icon and complex-region comparison is recorded.
- root canvas and key groups carry stable ids and PPTX-oriented bounds.

### Stage D.1: Fidelity and Overflow Policy

Canonical geometry:

- `page_scene.v1` uses one 16:9 canonical canvas for SVG and PPTX.
- The blueprint manifest records source image dimensions, `slide_frame` and the exact source-to-scene transform.
- Provider output with a different aspect ratio is mapped through the approved `slide_frame`; full-image stretching is forbidden.
- Coordinates remain floating point through scene and compiler stages, with rounding only during SVG or DrawingML serialization.

Text reconstruction:

- OCR and generated text provide region hints only; visible text is rebuilt from `content_lock.v1`.
- Each text element declares preferred font size, minimum font size, maximum lines and overflow policy.
- Fit order is line reflow, spacing adjustment within policy, font reduction down to the declared minimum, then bounded container repair.
- Remaining overflow blocks the page and returns to scene repair or content-lock regeneration. Clipping, hidden overflow and font reduction below the declared minimum cannot pass.

Visual comparison:

- Comparison uses text-masked structure similarity for layout, key-region color difference, element-level bbox deltas and Agent visual review.
- Default structure gate is `text_masked_ssim >= 0.92`; the threshold lives in a versioned quality policy and may only change with fixture evidence.
- P0/P1 SVG geometry may deviate from `page_scene.v1` by at most 2 px per bbox edge.
- PPTX readback geometry may deviate from the scene-to-slide transform by at most 0.75 pt per P0/P1 bbox edge.
- P0 text content requires normalized exact match on readback; P1 text requires full presence with no truncation.
- Global similarity cannot override a failed P0/P1 element, overflow finding or manual high-complexity review.

### Stage E: Native DrawingML PPTX

Owner: `deck-builder-high-density`

Inputs:

- native SVG.
- page scene.
- notes.

Outputs:

- PPTX candidate.
- PPTX trace JSON.

First whitelist:

- `text`
- `tspan`
- `rect`
- `line`
- basic `path`
- arrow `polygon`
- table gridlines
- registered image assets

Hard gates:

- title, body, key numbers, table core text, SO WHAT and sources are editable.
- whole-page image wrapper blocks.
- major text as image blocks.
- unregistered images block.
- SVG-to-DrawingML uses one documented px-to-slide-unit transform derived from the canonical canvas.
- P0/P1 geometry and text readback satisfy Stage D.1 tolerances.

### Stage F: Readback and Handback

Owner: `deck-builder-high-density`, then `deck-quality`

Outputs:

- readback report.
- `high_density_manifest.v1`.
- canonical `build_manifest.json`.
- canonical `artifact_manifest.json`.
- canonical `render_result.json`.

Hard gates:

- slide count matches expected count.
- speaker notes count matches expected count.
- major text is readable.
- image relationships obey asset policy.
- canonical handback validates before stage transition.

## 10. State Model

Run status values for `high_density_status.v1`:

```text
prepared
building
awaiting_agent_build
completed
blocked
failed
stale
```

`awaiting_agent_build` means the active Skill must perform an Agent/ImageGen or Agent-authored redraw action and then resume through the recorded action. Canonical build status stays `building` during this state. `awaiting_external_render` remains reserved for the standard profile and is invalid for high-density.

Page status values:

```text
pending
content_ready
blueprint_ready
page_scene_ready
svg_ready
visual_review_passed
pptx_ready
readback_passed
completed
blocked
stale
failed
```

Blocked reasons:

```text
HD_CONTENT_LOCK_INVALID
HD_BLUEPRINT_REGEN_REQUIRED
HD_PAGE_SCENE_INVALID
HD_SVG_REVIEW_FAILED
HD_PPTX_EDITABILITY_FAILED
HD_ASSET_POLICY_BLOCKED
HD_CONTRACT_HANDBACK_FAILED
```

Invalidation:

| Changed Input | Invalidates |
| --- | --- |
| Page Package | content lock, blueprint, page scene, SVG, PPTX, reviews |
| content lock | blueprint, page scene, SVG, PPTX, reviews |
| style lock | blueprint, page scene, SVG, PPTX, visual review |
| blueprint | page scene, SVG, PPTX, visual review |
| page scene | SVG, PPTX, readback |
| SVG | preview, visual review, PPTX, readback |
| PPTX | readback, render result, artifact manifest |

`next-step` must return exact recovery commands, for example:

```bash
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P037 --stage svg
```

## 11. CLI and Errors

### 11.1 Golden Path

```bash
deck-master suite-status --capability deck_master.build.high_density.v1 --output json
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
deck-master build status --run-dir <run_dir> --profile high-density --watch
deck-master next-step --run-dir <run_dir>
deck-master build retry --run-dir <run_dir> --profile high-density --page-id <page_id>
```

### 11.2 Error Contract

Each high-density error returns:

```json
{
  "code": "HD_SVG_REVIEW_FAILED",
  "message": "SVG visual review failed on page P037.",
  "cause": "P0 text overflow in title.main",
  "fix": "Repair the SVG layout or return to content lock if text cannot fit.",
  "next_command": "deck-master build retry --run-dir <run_dir> --profile high-density --page-id P037 --stage svg",
  "docs": "docs/agent-recovery-playbook.md#high-density-builder",
  "stage": "svg",
  "page_id": "P037",
  "artifacts": ["high_density_build/reviews/P037.main_review.json"]
}
```

Error codes:

| Code | Meaning |
| --- | --- |
| `BUILD_PROFILE_UNSUPPORTED` | unsupported profile spelling or value |
| `HIGH_DENSITY_CAPABILITY_MISSING` | high-density capability unavailable |
| `BUILDER_PROFILE_MISMATCH` | CLI profile conflicts with existing run/build state |
| `HD_CONTENT_LOCK_INVALID` | missing or invalid content lock |
| `HD_BLUEPRINT_REGEN_REQUIRED` | blueprint stale or invalid |
| `HD_PAGE_SCENE_INVALID` | page scene schema or geometry invalid |
| `HD_SVG_REVIEW_FAILED` | SVG structure or visual review failed |
| `HD_PPTX_EDITABILITY_FAILED` | PPTX readback/editability gate failed |
| `HD_ASSET_POLICY_BLOCKED` | unregistered or invalid image asset |
| `HD_CONTRACT_HANDBACK_FAILED` | canonical JSON handback invalid |
| `HD_STAGE_UNSUPPORTED` | retry requested an unsupported high-density stage |

## 12. Evidence Policy

The 73-page MVP is accepted as route evidence. Repo implementation should not copy private source material or final deck pages into public docs.

Required evidence index:

- 3 high-complexity pages.
- 3 normal high-density pages.
- 1 repaired or failed page.

Each evidence row records:

- evidence id.
- page class.
- source artifact type.
- path class, not absolute local path.
- sha256 or stable hash.
- quality result.
- repair notes.
- accepted/rejected status.

Example:

```json
{
  "evidence_id": "HD-MVP-001",
  "page_class": "complex_framework",
  "artifact_set": ["blueprint", "svg", "preview", "pptx_trace", "readback_report"],
  "path_class": "external_local_private",
  "sha256": "<64hex>",
  "quality_summary": {
    "slides": 73,
    "speaker_notes": 73,
    "skipped": 0,
    "media_files": 0,
    "image_relationships": 0,
    "native_object_route": true
  }
}
```

## 13. Implementation Packages

Priority semantics:

- P0 is the required contract and runtime foundation.
- P1 is the required first usable engine implementation.
- First engineering acceptance requires every P0 and P1 package below.
- P2 starts after the first engineering release.

### HD-P0-001: Supersede old high-density spec statements

Goal: update repo docs so old MVP status cannot mislead later agents.

Acceptance:

- older P01-P03-only language is marked superseded.
- 73-page external MVP is recorded as accepted evidence.
- no private customer raw content is copied into repo.

### HD-P0-002: Define builder profile and contract matrix

Goal: lock `builder_profile`, `output_profile` and `run_mode` semantics.

Acceptance:

- CLI `high-density` maps to internal `high_density`.
- `production_pptx` is first release target.
- unknown profile rejects with `BUILD_PROFILE_UNSUPPORTED`.
- legacy v2 manifests without `builder_profile` resolve to `standard`.

### HD-P0-003: Add high-density contracts

Goal: create formal content lock, IR and lineage contracts.

Acceptance:

- `content_lock.v1`, `page_scene.v1`, `high_density_manifest.v1` and `high_density_status.v1` schemas exist.
- validators exist.
- fixtures cover invalid paths and missing lineage.
- content lock lineage and invalidation rules are tested.

### HD-P0-004: Package and expose the independent Skill

Goal: install the clean implementation and make `deck_master.build.high_density.v1` discoverable.

Acceptance:

- `skills/deck-builder-high-density/SKILL.md` and `scripts/high_density/` exist.
- skill and product capability manifests contain the explicit profile route.
- manifest validation accepts one default and one high-density implementation for the `deck-builder` stage.
- `suite-status --capability` can report the capability and dependency-level blockers.
- missing capability blocks.
- standard Builder remains usable.
- runtime code has no import or shell dependency on the three reference Skill directories.

### HD-P0-005: Add CLI profile routing and retry

Goal: make the promised command line executable.

Acceptance:

- `build prepare/run/status --profile high-density` parse.
- `build prepare --output-profile production_pptx` parse.
- `build status --watch` parse.
- `build retry --page-id [--stage]` parse.
- `suite-status --capability` parse and filters one capability.
- profile mismatch blocks with exit 2.

### HD-P0-006: Migrate runtime build to v2

Goal: align runtime with Stage Contract.

Acceptance:

- production build prepare consumes Page Packages.
- production direct preview input blocks.
- `build_manifest.json` is `deck_build_manifest.v2`.
- old v2 manifests without `builder_profile` remain readable as standard.
- new schema, generator, normalizer and validators agree on profile semantics.
- completed high-density manifests require a valid `high_density_manifest` ref.

### HD-P0-007: Add the Agent-managed high-density execution adapter

Goal: define and implement the execution boundary without requiring PPT Master render handoff.

Acceptance:

- high-density `build run` routes to `deck-builder-high-density`.
- Agent-owned work returns `awaiting_agent_build` with exact machine-readable continuation.
- high-density never returns `awaiting_external_render`.
- standard external handoff tests remain unchanged.
- a fake high-density adapter validates prepared, awaiting, resumed, blocked and completed contract transitions.

### HD-P0-008: Implement status, invalidation and `next-step`

Goal: make page-level progress recoverable.

Acceptance:

- `high_density_build/status.json` exists.
- status mirrors to run-state.
- `next-step` returns exact retry command.
- `status --watch` returns on completed, blocked, failed or `awaiting_agent_build` and preserves the continuation payload.

### HD-P0-009: Add canonical handback

Goal: let `deck-quality` consume high-density output through standard handback.

Acceptance:

- standard build/artifact/render JSON validates.
- internal lineage is referenced through `high_density_manifest.v1`.
- final artifacts and previews are run-relative.

### HD-P0-010: Add the sanitized engineering fixture

Goal: make first-release acceptance reproducible without private materials or a live image provider in hermetic CI.

Acceptance:

- a source-controlled 7-page synthetic fixture covers framework, process, table, comparison, architecture, data story and dense narrative page classes.
- fixture content, blueprint images and expected readback contain no customer source material.
- frozen blueprint inputs and expected assertions are ready for deterministic Stage C-F CI tests.
- a provider-enabled Stage B smoke scenario and evidence contract are defined.
- fixture inputs and expected artifacts pass schema and confidentiality checks before engine work starts.

### HD-P1-011: Reimplement NBB content enrichment

Goal: carry the proven CyberPPT content-density method into the independent Skill.

Acceptance:

- Page Packages produce deterministic `content_lock.v1` artifacts.
- every enriched factual statement retains evidence lineage.
- page numbers, internal labels and unsupported generated claims are excluded.
- content-lock hash changes invalidate all downstream artifacts.

### HD-P1-012: Implement blueprint generation

Goal: generate high-density visual blueprints through the active Agent ImageGen capability.

Acceptance:

- prompts are built from content lock, density plan, style lock and visual element inventory.
- prompt hash, image hash, source canvas and approved `slide_frame` are recorded.
- generated text remains a region hint and cannot override locked content.
- one provider-enabled page passes the release smoke scenario.

### HD-P1-013: Implement page-scene reconstruction

Goal: convert the blueprint and locked content into deterministic semantic geometry.

Acceptance:

- P0/P1 regions map to stable roles, bboxes, text refs and editability targets.
- source-to-scene transform preserves ratio and records all crop or frame decisions.
- text-fit and overflow policies exist for every text region.
- scene validation rejects missing locked content and out-of-canvas regions.

### HD-P1-014: Reimplement native SVG redraw and visual QA

Goal: rebuild the visual composition as native SVG with measurable fidelity.

Acceptance:

- implementation is repository-owned and has no runtime dependency on `native-svg-redraw`.
- SVG passes structural, overflow, text and asset-policy checks.
- text-masked structure similarity and P0/P1 bbox tolerances satisfy Stage D.1.
- high-complexity pages include both subagent self-review and main Agent visual review evidence.

### HD-P1-015: Implement SVG-to-DrawingML compiler MVP

Goal: produce editable PPTX objects from the approved native SVG and page scene.

Acceptance:

- first-version whitelist maps to native DrawingML or registered image assets.
- P0/P1 text and geometry pass editability and readback tolerances.
- every PPTX object maps back to a scene element through trace JSON.
- unsupported elements block with an explicit page/stage recovery command.

### HD-P1-016: Implement readback, handback and recovery integration

Goal: close the production loop through canonical Deck Master contracts.

Acceptance:

- OfficeCLI or equivalent OOXML readback validates slide count, notes, text, geometry and image relationships.
- canonical build, artifact and render handback validates.
- status, retry and `next-step` resume a failed page without rebuilding unaffected pages.
- `deck-quality` can consume the completed result without a profile-specific bypass.

### HD-P1-017: Complete release docs and regression acceptance

Goal: make the first engine release reproducible and operable by another Agent.

Acceptance:

- quick start, user guide and recovery playbook cover normal, blocked and retry paths.
- the P0 seven-page fixture passes deterministic Stage C-F CI.
- provider-enabled one-page release smoke passes Stage B-F.
- additional regression fixtures cover overflow, ratio drift, stale hashes and unsupported SVG elements.

### HD-P2-018

After P1 baseline:

- compare SVG route, object-first route, page archetype route and hybrid asset route by page type.

## 14. Test Plan

### Schema

- `builder_profile=standard/high_density` accepted.
- legacy v2 manifest without `builder_profile` resolves to standard.
- unknown profile rejected.
- standard manifest carrying `high_density_manifest` rejected.
- completed high-density manifest missing `high_density_manifest` rejected.
- `content_lock.v1` Page Package lineage and evidence binding checked.
- `page_scene.v1` required elements checked.
- `high_density_manifest.v1` lineage paths checked.
- `high_density_status.v1` rejects unsupported states and missing continuation payloads.

### CLI

- `--profile high-density` parses.
- `--profile high_density` rejects.
- missing capability blocks.
- profile mismatch returns blocked / exit 2.
- `suite-status --capability` filters capability readiness.
- `build prepare --output-profile`, `build status --watch` and `build retry --stage` parse.

### Runtime

- production build consumes Page Package.
- production build blocks direct `preview_manifest.json`.
- fixture/dev legacy adapter remains explicit.
- canonical handback validates.
- high-density uses `awaiting_agent_build` for Agent-owned work.
- canonical build status remains `building` during `awaiting_agent_build`.
- high-density rejects `awaiting_external_render`.
- standard external render handoff remains covered.

### PPTX

- slide count matches expected count.
- speaker notes count matches expected count.
- key text readback passes.
- whole-page image wrapper blocks.
- image relationships follow asset policy.

### Recovery

- content lock hash change invalidates downstream artifacts.
- failed page returns exact retry command.
- partial artifacts remain visible.

### Evidence

- 7-page sanitized synthetic fixture and evidence index validate in hermetic CI.
- one-page provider-enabled blueprint smoke validates Stage B during release acceptance.
- 73-page external baseline is referenced without private raw assets.

## 15. First Engineering Acceptance

The first engineering release is accepted when:

1. `deck-master suite-status --capability deck_master.build.high_density.v1 --output json` reports the capability or a clear blocker.
2. `deck-master build prepare --profile high-density --output-profile production_pptx` writes a valid v2 build manifest, while legacy v2 manifests still resolve to standard.
3. One `deck-builder-high-density` invocation can continue through `awaiting_agent_build` states and produce native SVG, native DrawingML PPTX, `high_density_manifest.v1` and canonical handback without manual PPT Master render import.
4. `deck-master build status --profile high-density --watch` shows page/stage progress and terminates on a stable end state.
5. `deck-master next-step` and `build retry` can recover a failed page or stage.
6. `deck-quality` can evaluate final PPTX through canonical handback.
7. The sanitized 7-page synthetic fixture passes schema, SVG, PPTX and readback gates in hermetic CI.
8. A provider-enabled one-page release smoke generates a fresh blueprint and records reproducible prompt/image lineage.

## 16. Explicitly Deferred

- multi-backend PPTX compiler.
- `fast / standard / max-quality` modes.
- full visual style marketplace.
- complex chart data engine.
- browser UI for high-density progress.
- `client_delivery` acceptance for high-density mode.
