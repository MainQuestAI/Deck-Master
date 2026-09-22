# Deck Master PPT Library Bridge & Runtime Closure Development Spec v1

状态：Development Spec
正式发布基线：Deck Master `main@cc5b112` / `v0.9.14-preview.2`
开发目标基线：`chore/1.0.0-rc-governance-ci-tier@ed2bc42`
本机验证基线：Deck Master 安装 `REVISION=5713ea6`，PPT Library CLI `2.0.0`
主责仓库：Deck Master
外部依赖：PPT Library
开发方式：Subagent Driven Development（SDD）

## 1. 目标

本轮把 Deck Master 与 PPT Library 的真实资产复用链路收成可安装、可降级、可追踪、可审查、可回滚的生产能力。

完成后必须满足：

1. 安装版 Deck Master 使用 release-local Python 3.12，不再依赖 `/usr/bin/python3` 或未校验的 PATH `python3`。
2. Deck Master 页面角色不再直接进入 PPT Library 的 8 角色校验器。
3. PPT Library 角色标注为 0 时，角色选页明确返回 gap，Deck Master 自动转入每页真实语义检索。
4. 语义检索仍无候选时，该页面明确进入 generate，不产生静默空结果。
5. 每个 beat 使用独立 query 和 trace，跨页面默认不重复选择同一历史页。
6. 原始绝对路径、客户源路径和私有目录不得进入客户可见产物或公开 RC 证据。
7. `deck_sourcing_plan.v2` 成为新的唯一写入格式；旧 `decisions[]` 只保留兼容读取和迁移。
8. `library-status`、`setup-status`、Review Desk 与 RC gate 读取同一份 PPT Library readiness 真相。

## 2. 已验证基线

### 2.1 Branch & Release Governance

- GitHub 默认分支、`origin/HEAD` 和正式发布口径仍指向 `main@cc5b112`。
- 开发目标分支以 `cc5b112` 为 merge base，相对 `main` 领先 11 个提交、落后 0 个提交，没有分叉。
- 目标分支已推送远端且 CI 通过；截至 2026-07-10 尚无 PR、正式 tag 或默认分支切换记录。
- 目标分支已经提供 `rc-gate --tier ci`、CI job、RC 证据分层与开源治理能力，本 Spec 直接复用这些能力。
- 本 Spec 的开发、review 和 UAT 基于 `ed2bc42`；正式发布声明仍需完成 PR、合并、tag 和 release gate。

### 2.2 Runtime

- 本机全局 launcher 调用 `/usr/bin/python3`，该解释器为 Python 3.9.6。
- 安装代码使用 `str | None` 等 Python 3.10+ 语法，导致 launcher 在模块导入阶段失败。
- `cc5b112` 的 release builder 生成 `exec python3`，仍未固定到受支持解释器。
- 当前 `pyproject.toml` 声明 `>=3.11,<3.14`；真实 PPT Library v2 集成按 Python 3.12 验收。

### 2.3 Bridge

- `run_library_selection()` 将原始 `narrative_plan.json` 直接传给 `ppt-lib select-slides`。
- PPT Library 只接受 `opener/problem/solution/architecture/case/roi/cta/appendix`。
- 现有真实 run 共使用 12 个唯一 role：`opener`、`executive_summary`、`business_context`、`problem`、`solution_overview`、`capability_matrix`、`architecture`、`capability_detail`、`process_flow`、`section_handoff`、`solution_detail`、`cta`。
- `split_selection_by_beat()` 先按 role 聚合，再把同一 role 的候选池复制给所有对应 beat。
- `deck_sourcing_plan.v2` 已存在，但 CLI、generation 和部分 Review Desk 读者仍消费旧 `decisions[]`。

### 2.4 PPT Library 数据状态

- 746 份演示稿、28129 页、24996 张截图。
- 语义 embedding 已覆盖当前 slides，真实文本查询可以返回候选。
- `annotated_count=0`，所以规范角色的 `select-slides` 均返回成功码和 gap。
- `deals_count=0`、`slide_usage_count=0`，business ranking 处于 cold start。
- 当前还有 33 个 failed jobs、34 个 orphan presentations；归 PPT Library 数据治理任务处理。

## 3. 范围

### 3.1 In Scope

- Release-local Python 3.12、launcher、install/upgrade/rollback 和 release smoke。
- Bridge request/selection 契约、角色策略、每页语义降级、trace 和证据产物。
- 候选身份、路径脱敏、预览退化状态、页内和跨页去重。
- `beat_id -> page_task_id` 身份穿线。
- `deck_sourcing_plan.v2` 唯一写入源和旧格式迁移。
- `library-status` 多维 readiness、setup/suite 摘要、Review Desk 状态提示。
- 真实 run 副本 UAT、contract tests、release install/rollback 验证。

### 3.2 Out of Scope

- 修改 PPT Library 代码、schema 或数据库。
- 执行批量 annotate/enrich、清理 orphan、重跑 failed jobs。
- 写入 deal/usage/outcome 反馈。
- 在 production/benchmark 中启用 fixture fallback。
- 修改真实用户 run；UAT 必须使用副本或临时 run。
- 借本轮重构无关 CLI、Review Desk 视觉或其他 companion bridges。

## 4. 产品状态模型

PPT Library readiness 必须拆成独立维度：

| 字段 | 含义 | 当前预期 |
|---|---|---|
| `runtime_ready` | Deck Master 与 `ppt-lib` CLI 可启动 | launcher 修复后 true |
| `contract_ready` | CLI/schema/输出形状可被 bridge 消费 | true 或兼容模式 |
| `semantic_search_ready` | 无角色文本检索可返回真实候选 | true |
| `role_selection_ready` | 8 个规范角色有可用标注和候选 | false |
| `fallback_ready` | 每页语义降级链路通过 | M2 完成后 true |
| `preview_ready` | 候选有可用缩略图 | 当前可能 degraded |
| `business_ranking_ready` | 有足够 deal/usage 反馈 | `cold_start` |
| `data_hygiene_status` | failed/orphan/source coverage 摘要 | degraded |

聚合状态：

- `ready`：runtime、contract、semantic、role selection 和 preview 均满足当前策略。
- `degraded_ready`：语义复用可用，角色筛选或预览存在退化，流程可继续。
- `blocked`：runtime、contract 或真实语义检索不可用，production/benchmark 不得伪装成功。

`search-library` 结果状态：

- `library_ready`：所有需要检索的页面均有角色化候选。
- `library_degraded`：使用 semantic fallback 或存在 preview degradation。
- `library_gap`：部分或全部页面需要 generate，流程仍可继续。
- `library_blocked`：真实依赖或契约失败，流程停止并给出 repair action。

## 5. Runtime Closure

### 5.1 运行时策略

安装版固定使用 release-local Python 3.12：

保留现有 staging、`current`、`previous` 和 `failed` 目录模型，只在每个 release tree 内增加本地 venv：

```text
~/.deck-master/
  staging/release-<release-id>/
    .venv/bin/python
    scripts/deck_master.py
  current/
    .venv/bin/python
    scripts/deck_master.py
  previous/
    .venv/bin/python
    scripts/deck_master.py
  failed/
  bin/deck-master
```

解释器优先级：

1. 已安装 launcher 固定使用 `current/.venv/bin/python`。
2. 安装或恢复阶段允许显式 `DECK_MASTER_PYTHON`，但必须校验为 Python 3.12。
3. 未提供 override 时探测 `python3.12`，校验通过后用它创建 stage venv。
4. 其余解释器不得直接启动 Deck Master 模块。

Stage venv 创建流程：

```text
<python-3.12> -m venv <staged-release>/.venv
<staged-release>/.venv/bin/python -m pip install <staged-release>
<staged-release>/.venv/bin/python <staged-release>/scripts/deck_master.py --help
```

Release tree 必须包含可安装的 `pyproject.toml` 和 runtime 源码。依赖安装失败时 stage 保留诊断，`current` 不切换。

Python 3.12 缺失时输出固定错误：

```text
Deck Master installed releases require Python 3.12. Set DECK_MASTER_PYTHON
to a Python 3.12 executable or install python3.12. No release was activated.
```

### 5.2 安装与回滚

- Stage release tree。
- 校验 manifest、SHA256、required files 和 Python 版本。
- 在 stage 内创建 `.venv` 并安装 runtime dependencies。
- 使用 stage launcher 运行 smoke。
- 原子切换 `current`，保留 `previous`。
- 失败时保留当前工作版本，不写坏 launcher。
- rollback 切回 previous，并再次运行 release smoke。
- runs、workspace binding、用户配置和 PPT Library 数据不得随 release rollback 回滚。

### 5.3 Runtime 验收

- 即使 shell 默认 `python3` 指向 3.9 或 3.14，全局 launcher 仍使用 release-local 3.12。
- `setup-status --include-suite --output json` 可运行。
- clean HOME install、upgrade、rollback 均通过。
- 删除或移动源码 checkout 后，安装版仍可运行。
- release manifest 记录受支持 Python 范围和实际 runtime 版本，不记录源码绝对路径。

## 6. Bridge Contract

### 6.1 Outbound：`deck_master_ppt_library_bridge_plan.v1`

Bridge 不修改 `narrative_plan.json`，在 run 内生成独立 request artifact：

```text
external/ppt_library/private/bridge_plan.v1.json
```

每个 request 必须包含：

```json
{
  "beat_id": "beat-001",
  "page_task_id": "page-task-001",
  "section_id": "section-01",
  "order": 1,
  "role_original": "solution_detail",
  "role_strategy": "mapped",
  "role_mapped": "solution",
  "query": "...",
  "query_trace_id": "...",
  "reuse_policy": "reuse_or_adapt"
}
```

强约束：

- `beat_id` 是选片阶段主身份，必须存在且在一个 request 中唯一。
- `build_page_tasks()` 必须新增稳定字段：`page_task_id = explicit page_task_id || task_id || page_id || beat_id`。
- Bridge 从 `page_tasks.json` 按 `beat_id` 解析 `page_task_id`。旧 run 缺该字段时使用 `page_task_id=beat_id`，记录 `LEGACY_PAGE_TASK_ID_DERIVED`。
- `page_task_id` 一经生成不得在 Bridge、Selection v2、Sourcing v2、generation、preview 或 readiness 阶段重新铸造。
- `query_trace_id = sha256(canonical_json([run_id, beat_id, normalized_query]))`，由 bridge 铸造并稳定复现；canonical JSON 固定 UTF-8、无多余空格和稳定分隔符。
- `query` 优先使用 `reuse_query`，其次组合 `page_title` 和 `content_goal`。
- `section_handoff` 使用相邻 beat 的 `page_title` 构造过渡 query。

### 6.2 Inbound：`deck_master_ppt_library_selection.v2`

规范化结果写入：

```text
external/ppt_library/library_results.v2.json
library_results/selection.json
library_results/by_beat/<beat_id>.json
```

每个 selection 必须包含：

- `beat_id`
- `page_task_id`
- `query_trace_id`
- `role_original`
- `role_strategy`
- `role_mapped`
- `retrieval_method`: `role_selection | semantic_fallback | none`
- `fallback_reason`
- `preview_status`: `ready | missing | invalid`
- `candidates[]`

每个 candidate 必须包含：

- `candidate_id`
- `slide_id`（可空但需要 fallback identity）
- `asset_key`
- `title`
- `text_summary`
- `page_number`
- `score`
- `confidence`
- `source_asset_id`
- `source_display_name`
- `screenshot_ref`
- `candidate_origin=ppt_library`
- `reuse_policy`

`ppt-library-selection.v1` 保留兼容读取；新的真实 bridge 只写 v2。

## 7. 角色策略

### 7.1 原值透传

```text
opener, problem, solution, architecture, case, roi, cta, appendix
```

### 7.2 安全映射

| Deck Master role | PPT Library role |
|---|---|
| `business_context` | `problem` |
| `solution_overview` | `solution` |
| `capability_matrix` | `solution` |
| `capability_detail` | `solution` |
| `solution_detail` | `solution` |
| `process_flow` | `architecture` |

### 7.3 无角色语义检索

| Deck Master role | 策略 |
|---|---|
| `executive_summary` | semantic-only，默认 `adapt` |
| `section_handoff` | semantic-only，`adapt_only` |

未知 role：

- preview/interactive：semantic-only，记录 `UNKNOWN_ROLE_SEMANTIC_FALLBACK`。
- production/benchmark：`library_blocked`，要求先更新显式策略。

## 8. Retrieval Ladder

每个 beat 独立执行：

1. 运行 preflight，读取 CLI、schema、status 和能力快照。
2. 对原值透传或安全映射角色调用 role selection。兼容路径按 beat 单独调用；只有已验证的 contract 输出能回传 `beat_id` 时才允许 batch。
3. role selection 返回 gap 时，调用 `ppt-lib search <query> --output json`。
4. semantic-only 角色直接调用 search。
5. 规范化 candidate，补 `score -> confidence`。
6. 处理 preview、路径和 identity。
7. 页内去重后进入跨页分配。
8. 无候选时写 `retrieval_method=none`，Sourcing v2 进入 generate/evidence/manual。

禁止行为：

- 角色 gap 不得记录为 `library_ready`。
- semantic fallback 不得触发 fixture。
- Deck Master 不直接打开 PPT Library SQLite 数据库补字段。
- bridge 不把一个 role 候选池复制给多个 beat。

## 9. Preview 与路径治理

### 9.1 Screenshot

- `screenshot_path` 存在且文件可读时，复制或受控链接到 run-local `preview_assets/`，规范化结果只保存 run-relative ref。
- `screenshot_path` 缺失时，设置 `preview_status=missing` 和 `preview_degraded=true`。
- Review Desk 显示稳定占位状态，不伪造缩略图。
- 截图缺失不阻断语义候选进入 `adapt`；自动 `reuse` 需要后续预览确认。

### 9.2 Source Path

原始 CLI 输出保存到 internal-only artifact：

```text
external/ppt_library/private/selection.raw.json
```

该目录不得进入 client export、public benchmark evidence 或 release artifact。

规范化候选：

- `source_asset_id = sha256(normalized_source_path)`。
- `source_display_name` 使用经过脱敏策略处理的标签。
- 不保存 `/Users/...`、`/private/...` 或其他绝对路径。
- customer-visible safety gate 扫描绝对路径、客户目录名和 raw artifact 引用。

## 10. Candidate Identity 与全局分配

`asset_key` 优先级：

1. `canonical:<canonical_slide_id>`，字段存在且非空时使用。
2. `source-page:<sha256(normalized_source_path)>:<page_number>`。
3. `slide:<slide_id>`。
4. 全部缺失时拒绝候选并记录 `CANDIDATE_IDENTITY_MISSING`。

页内去重按 `asset_key` 保留最高分候选。

跨页分配采用稳定全局 greedy：

1. 汇总所有 `(beat, candidate)` 边。
2. 按 score 降序、beat order 升序、candidate rank 升序排序。
3. 每个 beat 默认最多分配一个首选候选。
4. 每个 `asset_key` 默认只能成为一个 beat 的首选。
5. 未分配 beat 再从未占用候选中选择次优项。
6. `allow_repeat_source=true` 只允许显式设置，并进入 review warning。

Bridge 负责生成 `asset_key`、页内去重和每页候选池。跨页分配实现在 `scripts/sourcing/plan.py`，属于 Sourcing v2 决策职责。

Sourcing Plan v2 必须消费全部候选池并完成唯一分配，不能对每个页面再次独立挑选重复 top-1。Bridge 与 Sourcing allocation 必须在同一个 M2 放行包中完成。

## 11. Sourcing Plan v2 收口

- `command_decide_sourcing` 改为调用 `build_sourcing_plan_v2()`。
- `sourcing_plan.json` 新写入必须带 `schema_version=deck_sourcing_plan.v2` 和 `pages[]`。
- 旧 v1 文件通过 `migrate_v1()` 读取；不得继续产生新的 `decisions[]`。
- generation task builder、preview builder、quality/readiness、benchmark 和 Review Desk 逐一迁移到 `pages[]`。
- 临时兼容 reader 可同时接受 v1/v2；兼容期结束条件由 RC 报告记录。
- Producer 只消费 Sourcing v2，不自行重新选择 library candidate。

### 11.1 Canonical Reader

新增或复用一个共享 reader，把 v1/v2 统一为 Sourcing v2 page shape。generation、preview、quality、readiness、benchmark 和 Review Desk 必须调用该 reader，禁止各自维护字段映射。

### 11.2 下游字段映射

| Sourcing v2 | 兼容消费者语义 |
|---|---|
| `pages[].page_id` | `beat_id` / `page_id` |
| `pages[].page_task_id` | generation `task_id` 的稳定来源字段 |
| `pages[].decision` | `source_decision` |
| `pages[].reason` | `decision_reason` |
| `pages[].selected_sources[0]` | `selected_candidate` / `reference_slide` |
| `pages[].selected_sources[1:]` | `alternatives` |
| `pages[].claim_ids` | generation claim binding |
| `pages[].evidence_need` | generation/quality evidence requirement |
| selected source `query_trace_id` | generation/preview trace |
| selected source `asset_key` | duplicate and lineage identity |
| `permission_status` | reuse/adapt blocking gate |

迁移约束：

- v2 writer 只写 `pages[]`。
- 兼容 reader 可把旧 `decisions[]` 迁移为 page shape，但不得写回第二份 v1 artifact。
- `preview_builder` 当前输出的 `source_pptx` 不再读取原始 `source_file`；改用 `source_asset_id` 或安全 `source_display_name`。
- generation task builder 必须保留 `page_task_id`、`beat_id`、`query_trace_id` 和 `asset_key`。
- readiness 和 benchmark 统计按 v2 page 数量、decision、gap 和 selected identity 计算。

## 12. Readiness 与用户可见状态

`library-status` 升级为 `deck_master_library_status.v2`，至少输出：

```json
{
  "status": "degraded_ready",
  "runtime_ready": true,
  "contract_ready": true,
  "semantic_search_ready": true,
  "role_selection_ready": false,
  "fallback_ready": true,
  "preview_ready": false,
  "business_ranking_ready": "cold_start",
  "data_hygiene_status": "degraded",
  "blocking_summary": [],
  "warnings": []
}
```

要求：

- `library-status` 保持只读，不创建 run、不改数据库、不修复 skill。
- `setup-status` 和 `suite-status` 只透传同一份摘要，不各自重算。
- Review Desk 展示 role selection、semantic fallback、preview degradation 和 generate gap。
- `search-library` 不再仅凭 CLI return code 输出 `library_ready`。
- production/benchmark 的 fixture guard 保持现有阻断语义。

## 13. 允许修改路径

核心实现：

- `scripts/skills/installer.py`
- `scripts/tools/ppt_library_client.py`
- `scripts/deck_master.py`
- `scripts/sourcing/plan.py`
- `scripts/planning/sourcing_decider.py`
- `scripts/planning/page_tasks.py`
- `scripts/generation/task_builder.py`
- `scripts/orchestrate/preview_builder.py`
- `scripts/preview/server.py`
- `scripts/runtime/import_log.py`
- 与 setup/suite readiness 共用真相直接相关的现有模块

契约与文档：

- `docs/contracts/ppt-library-bridge-plan.v1.schema.json`
- `docs/contracts/ppt-library-selection.v2.schema.json`
- `docs/contracts/library-status.v2.schema.json`
- `docs/contracts/setup-status.v2.schema.json`
- `docs/integration/ppt-library-v2.md`
- 本 Spec 和 release notes

测试：

- `tests/test_ppt_library_client.py`
- `tests/test_sourcing_plan_v2.py`
- `tests/test_page_tasks.py`
- `tests/test_skill_installation.py`
- `tests/test_setup_enforcement.py`
- `tests/test_agent_ready_contract.py`
- `tests/test_preview_server.py`
- `tests/test_review_cockpit.py`
- 新增 contract、sanitization、allocation 和 real CLI UAT tests

超出路径前必须在 spec deviation log 记录原因、兼容影响和验证方法。

## 14. 测试矩阵

### 14.1 Runtime

- Python 3.9 PATH + release-local 3.12。
- PATH python 3.14 + release-local 3.12。
- `DECK_MASTER_PYTHON` 合法/非法版本。
- clean install、upgrade failure、rollback、moved source checkout。

### 14.2 Contract 与身份

- 原始 `narrative_plan.json` checksum 不变。
- 所有当前 Deck Master roles 都进入已定义策略。
- `beat_id` 唯一；`beat_id -> page_task_id` 映射完整。
- `query_trace_id` 稳定且 query 变化后更新。
- v1 selection 仍可导入，v2 缺 required fields 被拒绝且不覆盖旧结果。

### 14.3 Retrieval

- invalid role 不再直接传给 PPT Library。
- 零标注库：role selection 返回 gap，随后 semantic fallback。
- semantic search 有候选：状态为 `library_degraded`，候选进入 Sourcing v2。
- semantic search 无候选：状态为 `library_gap`，页面进入 generate。
- production/benchmark 仍禁止 fixture。
- `section_handoff` 使用相邻标题 query 且候选为 `adapt_only`。

### 14.4 Preview 与隐私

- screenshot 存在：规范化为 run-relative ref。
- screenshot 缺失：`preview_degraded=true`，Review Desk 有占位状态。
- normalized selection、preview manifest、final artifact、benchmark evidence 不含 `/Users/`、`/private/` 和 raw source path。
- `preview_builder` 的 `source_pptx` 不得回填原始 `source_file`。
- private raw artifact 不进入 export package。

### 14.5 去重与 Sourcing

- 11 个映射到 solution 的 beat 使用独立 query。
- 同一 candidate 出现在多个 pool 时，默认只成为一个页面的首选。
- `canonical_slide_id=None` 时使用 hashed source-page identity。
- Sourcing v2 不重新制造重复 top-1。
- v1 migration 后 generation/preview/quality/readiness 行为保持兼容。

### 14.6 真实 UAT

使用 `yunnan-baiyao-ai-foundation-deck-v1` 的临时副本：

- 原始 run 不变。
- 不再出现 invalid narrative role error。
- role gap 被记录。
- 真实 semantic fallback 返回候选。
- 候选不存在绝对路径泄漏。
- 重复首选数量为 0。
- 未命中页面明确进入 generate。
- `library-status` 与 run 产物状态一致。

## 15. 验收门

### Gate A：Runtime

- clean HOME install/upgrade/rollback 全通过。
- 全局 launcher 使用 release-local 3.12。
- release smoke 验证实际 runtime binding。

### Gate B：Bridge

- 当前真实 run 的 12 个唯一 role 均按显式策略处理。
- 零标注库可通过 semantic fallback 产生真实候选。
- gap、fallback、preview degradation 和 query trace 可审计。
- normalized/customer-visible 产物无绝对路径泄漏。

### Gate C：Sourcing

- 所有新 run 只写 Sourcing v2。
- 每个 page task 有且仅有一个 decision。
- 默认无重复 selected `asset_key`。
- 旧 run 可迁移读取。

### Gate D：Readiness

- 当前本机状态应表现为：semantic ready、role selection false、fallback true、business cold start、data hygiene degraded。
- CLI、setup/suite、Review Desk、RC gate 口径一致。

### Gate E：Regression

- Targeted tests 通过。
- 全量 tests、compile、format/diff check 通过。
- fresh clone 与 PR CI 中的 `rc-gate --tier ci` 通过。
- 具备真实后端和本地 benchmark 证据的发布环境中，full-tier RC gate 通过。
- `release-build`、`release-smoke`、fixture preview 和真实 run UAT 通过。

## 16. SDD 实施拆分

### D0：Spec 与 Fixture Freeze

- 主线程冻结 schema、角色策略、状态机、测试 fixture 和真实 UAT 副本。
- 不改产品代码。

### D1：Runtime Worker

Ownership：installer、release launcher、runtime tests。
必须同时覆盖 `~/.deck-master/bin/deck-master` 全局 launcher 和 release tree 内 `bin/deck-master`，禁止只修其中一个入口。
独立 reviewer：重点检查干净环境、失败激活、rollback 和源码路径泄漏。
Main acceptance：真实构建 release tree 并完成 install/rollback smoke。

### D2：Bridge Worker

Ownership：`ppt_library_client.py`、bridge schemas、contract tests。
必须实现：per-beat query、role policy、semantic fallback、identity、sanitization、preview state 和页内去重。
独立 reviewer：重点攻击全 gap、重复候选、空 canonical id、绝对路径、invalid role 和 fixture leak。

### D3：Sourcing & Readiness Worker

Ownership：page task identity、Sourcing v2 全局唯一分配、legacy readers、library/setup/suite readiness、Review Desk data feed。
独立 reviewer：重点检查双真相源、状态误报和旧 run 回归。
Main acceptance：真实 run 副本从 selection 进入 Sourcing v2 和 preview。

### D4：Release & UAT Worker

Ownership：UAT fixture、现有 two-tier RC gate 集成、RC evidence、release docs。
必须沿用目标分支已有的 `rc-gate --tier ci` 和 full-tier 边界，禁止新增第二套 RC 判断入口。
独立 reviewer：对抗式检查客户路径、私有原文、fixture、未验证 ready 声明。
Main acceptance：全量验证和第一性复核后决定是否进入 RC。

实现 worker 优先使用 `gpt-5.3-codex-spark`；reviewer 使用 `gpt-5.5`、`reasoning_effort=high`。每批 worker 完成后必须先 review，再由主线程验收。D2 与 D3 不并行写重叠文件。

## 17. 回滚

- Runtime 通过 `previous` release 原子回滚。
- Bridge v2 为新增 artifact；回滚后保留 v1 reader，不需要修改 PPT Library 数据。
- Sourcing v2 回滚只恢复 reader/writer 版本，原始 narrative/page tasks/library raw evidence 不删除。
- 所有数据迁移先生成备份和迁移报告；禁止原地破坏旧 run。
- 发生 contract mismatch、路径泄漏或错误 ready 声明时，停止 RC 并回滚到上一 release。

## 18. 外部依赖与后续任务

Deck Master 本轮可在 PPT Library 零角色标注状态下交付 semantic reuse。以下能力由 PPT Library 独立任务验证后再排期：

- `search` 为何未返回已有 screenshot path。
- `select-slides` role coverage 和 annotation readiness 定义。
- 33 个 failed jobs 和 34 个 orphan presentations 的分类与治理。
- annotate pipeline 的本地模型、断点续跑、批次提交、审计和回滚。
- deal/usage feedback cold-start 解除条件。
- `deck-master.v1` contract commit 的远端发布与后续 v2 contract 边界。

PPT Library 任务在收到本 Spec 摘要后先做只读验证和解法报告，不直接修改代码或数据。

硬约束：该任务禁止 annotate、enrich、record-deal、record-usage、prune、reindex、数据库写入、文件清理、升级、提交、推送和远端发布。若验证需要输出文件，只能写入临时目录。
