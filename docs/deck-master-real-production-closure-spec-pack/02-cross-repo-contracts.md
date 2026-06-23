# Cross-Repository Contracts

## 1. 总原则

1. Deck Master 是 contract owner 和 state owner。
2. PPT Deck Pro Max 是页面生产 orchestrator。
3. PPT Library 是历史资产检索 owner。
4. PPT Master 是 deterministic build / render owner。
5. 所有外部能力在 active Run 内产生的结果必须回写 Deck Master。
6. 所有路径必须为 Run-relative；禁止把本地绝对路径作为 canonical artifact path。
7. Production 不接受只写状态、不写真实 artifact 的成功结果。

---

## 2. Deck Master → PPT Deck Pro Max

### 输入：Generation Handoff Package

建议路径：

```text
<run>/handoffs/ppt_deck_pro_max/<session_id>/
  handoff_manifest.json
  request.json
  deck_brief.json
  claim_map.json
  narrative_plan.json
  page_tasks.json
  sourcing_plan.json
  visual_system/
  evidence/
```

`handoff_manifest.json` 至少包含：

- schema_version
- run_id
- session_id
- production_profile
- page task ids
- expected result schema
- output directory
- source fingerprint
- workspace references
- quality policy
- prohibited fixture flags

### PPT Deck Pro Max Bridge CLI

目标命令：

```bash
python scripts/run_deck_pipeline.py deck-master-import \
  --handoff <handoff_manifest.json> \
  --project-dir <session_project_dir>

python scripts/run_deck_pipeline.py deck-master-export \
  --project-dir <session_project_dir> \
  --run-id <run_id> \
  --session-id <session_id> \
  --output-dir <generation_results_dir>
```

Bridge 必须：

- 保留 run_id、session_id、task_id、page_id；
- 不修改 Deck Master 原始 artifact；
- 输出真实 artifact；
- 写 checksum；
- 标记 producer version / source SHA；
- 对未完成页输出 failed / partial，而不是假 completed。

---

## 3. PPT Deck Pro Max → Deck Master

输出使用 `deck_generation_result.v2`。

每页至少需要：

- 一个真实页面源：
  - HTML fragment；
  - page HTML；
  - SVG；
  - PNG；
  - native PPTX page；
  - 其他被 PPT Master 支持的 source。
- 一个真实 preview；
- artifact metadata；
- source fingerprint；
- producer provenance。

不允许：

- 文本文件改后缀；
- 0 字节文件；
- placeholder token；
- Run 外路径；
- run_id / session_id 不匹配；
- created_at 早于 handoff；
- 缺 checksum。

---

## 4. Deck Master → PPT Master

输入：`deck_build_manifest.v1`

建议路径：

```text
<run>/build/
  build_manifest.json
  source_snapshot.json
  theme/
  page_sources/
```

Build manifest 冻结：

- page order；
- page source artifact；
- profile；
- expected page count；
- visual system；
- fonts；
- output targets；
- source fingerprint；
- editability requirement。

PPT Master 不得自行改变 page order 或替换内容。

---

## 5. PPT Master → Deck Master

输出：

```text
<run>/render_results/render_result.json
<run>/artifacts/artifact_manifest.json
<run>/rendered/deck.html
<run>/rendered/deck.pdf
<run>/rendered/deck.pptx
<run>/rendered/pages/page_001.png
...
```

使用：

- `deck_render_result.v2`
- `deck_artifact_manifest.v1`

---

## 6. Deck Master ↔ PPT Library

PPT Library 继续通过真实 CLI 或 imported selection 工作。

Production 要求：

- `library_source` 只能是 `ppt_library` 或 `imported`；
- `fixture` 必须阻断，除非 run profile 明确为 fixture；
- selection 必须有 run_id；
- candidate 必须保留：
  - canonical_slide_id；
  - source file ref；
  - page number；
  - screenshot path；
  - confidence / score；
  - source mode；
  - query trace id；
  - index version（如果可用）。

Deck Master 不接管 PPT Library 的数据库和索引生命周期，但 Final Readiness 必须展示该 Run 是否使用真实检索、导入结果或 fixture。

---

## 7. Artifact Kind

Canonical kind：

```text
page_html
html_fragment
page_svg
page_png
page_jpeg
page_pptx
deck_html
deck_pdf
deck_pptx
asset_bundle
quality_report
source_snapshot
```

Canonical editability：

```text
native
hybrid
flat_image
not_applicable
unknown
```

Canonical validation：

```text
validated
invalid
unvalidated
stale
missing
```

---

## 8. Source Fingerprint

每个 build / render 必须计算：

```text
SHA256(
  ordered page_id
  + selected generation result sha256
  + selected library source sha256/ref
  + visual system hash
  + theme hash
  + build profile
)
```

任何输入变化后，旧 build / render 自动标记 stale。

---

## 9. Typed Events

新增或统一事件：

```text
generation.handoff.prepared
generation.awaiting_agent_execution
generation.result.rejected
generation.results.validated
build.manifest.created
build.started
build.completed
render.completed
artifact.validation.failed
artifact.stale.detected
final_readiness.updated
release.activated
release.rolled_back
benchmark.real_case.completed
```

事件必须包含：

- run_id；
- session/build id；
- refs；
- severity；
- message；
- source fingerprint（适用时）。

---

## 10. 错误分级

| 场景 | Severity |
|---|---|
| 文件扩展名与实际格式不符 | P0 |
| Production 使用 fixture / placeholder | P0 |
| run/session mismatch | P0 |
| 最终页数不一致 | P0 |
| artifact stale | P0 |
| required format missing | P0 |
| parse failure | P0 |
| PPTX flat-image 但客户要求 native | P1 |
| 非关键页面预览缺失 | P1 |
| 部分 metadata 缺失但可补算 | P1 |
| 视觉优化建议 | P2 |
