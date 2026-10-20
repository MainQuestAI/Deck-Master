# 基线、差异与启动门槛

## 已核对的来源

| 来源 | 本轮核对结果 |
|---|---|
| 原影响报告 | 固定 PR127 `12bffbd72631ad60ada6d456b99e95c3e6b2bd0e`，只读分析 |
| 本次 PR127 | `02627c17d5046428609e6806569ad3cd790e7d26`，OPEN / Draft；base `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8` |
| 当前主工作区 | `92e9f567eaf506f004cac1ef68f44f314739631a`，存在用户未提交文件；仅新增本规格包和本事项接续说明 |
| 当前设计 | `DESIGN.md`、`docs/design/webui-opendesign-20261001/`，不恢复旧 Review Desk |
| 资源输入 | 原 v1.1 包 00/02/03/05/06/09 与核心方法指南；现在以 PR127 内化资源为运行依据 |

本轮通过 gh 核对 PR 状态，通过 `git show 02627c17:<path>` 读取确定版本；不以并行开发工作树的未提交文件作为事实。

## 相对原报告必须更新的结论

1. 资源包缺失已经解除。当前 catalog 有 66 项，即 14 个既有 reference 加 52 个采用资源；统一映射报告为 76 个发布文件。
2. `create`、`continue`、`inputs update` 及独立 methods 读取已增加 `selected_resource_ids`。`collaboration_api._FIELDS['continue']` 已允许该字段，并传递到 service。不得重复开发这一基础。
3. 已持久化 Task 不允许补充资源；scope/phase 校验与最终冻结继续由 Runtime 负责。
4. 三类成对稿和四类范围文字探针已有回执；不是全部未运行。回执明确它们不证明 Runtime 写入 E2E、生产验收或人类认可。
5. 干净安装证据绑定 `5d5db8cf`；后续 HEAD 的 CI、构建内容差异应重新读回，不能把旧包描述成新 HEAD 构建。
6. 在已核对源码中，资源目录没有人类展示标题；Narrative 已有结构、Review v2 已有定位/证据/解决状态、content_requirements 已有语义说明。UI 应复用这些事实。

## 当前代码锚点

以下都是 `02627c17` 中的路径，行号只作定位辅助；实施时按最终基线重查。

| 路径 | 已有能力/本轮切入点 |
|---|---|
| `src/deck_master/service.py` | 真实派发、工作单方法依据、create/continue/inputs_update |
| `method_resources.py`、`resource_catalog.py` | 冻结资源、读取、角色/阶段/范围与依赖选择 |
| `run_desk.py` | task_row/detail 投影，尚无专用方法依据区 |
| `content_production.py` | 内容阶段、完成态、Narrative/Plan proposal 采用 |
| `collaboration_api.py` | 既有决定、proposal-adoptions、continue 的共享适配 |
| `content_ops.py` | source/lineage、正文局改 plan/commit |
| `resources/contracts/narrative.v1.schema.json` | communication_job、nodes/edges、issues、alternatives |
| `resources/contracts/page.v2.schema.json` | visible_links、固定 narrative_ref、source_links |
| `resources/contracts/review.v2.schema.json` | finding_id、page_id、element_refs、evidence、resolution |
| `resources/contracts/content-requirements.v1.schema.json` | page_role、required_qualifications、structure_refs、visual_intent |
| `resources/static/v2/{content-sources,page-workbench,run-desk,views,collaboration-desk,launcher-ui,routes}.js` | 现有 Studio 复用的前端模块 |
| `web.py`、`snapshots.py`、`capabilities.py` | HTTP 路由、固定版本读取、能力描述 |

## PR127 完成后的 G0 门槛（WU00）

现在只完成 Spec。实施前建立 `execution-ledger.json`，填写：

```json
{
  "pr127_final_head": null,
  "integration_base": null,
  "merge_commit": null,
  "baseline_disposition": "NOT_CHECKED",
  "required_checks": [],
  "package_evidence_ref": null,
  "spec_drift_review": "NOT_RUN",
  "implementation_status": "NOT_STARTED"
}
```

G0 的判定条件：

1. PR127 的负责会话已给出收口记录；资源、Host 接口及其兼容性没有仍在修改的未结阻断。
2. 当前最终 head 的 required CI 结果已核对；失败或待定不记通过。历史 macOS 渲染差异和不同 SHA 的包证据按原记录保留，并核对是否影响本轮路径。
3. 若 PR127 已合并，实施从包含该 merge 的最新适用 main 开始，核对后续差异；若已完成但未合并，可从核实完成的最终 head 创建独立接续分支，明确记录它仍依赖 PR127。用户本次已指定“基于 PR127”，无需再为这一常规基线选择增加审批。不得自行合并 PR127 来“满足门槛”。
4. 与本 Spec 的接口/合同作差异复核。已有同等实现则复用；字段/权限/写边界改变时先更新相应规格和 AC。
5. 用隔离开发分支承载实现，保留当前主工作区与 PR127 的工作。创建分支默认使用 `codex/` 前缀。

G0 不要求把专业认可或真实 HOME 激活改成 PASS；它们仍是独立验收层。G0 未满足时可继续评审本规格，不能把产品实现标为已启动。

## 固定证据链接

- [PR127](https://github.com/MainQuestAI/Deck-Master/pull/127)
- [RC5 工程回执](https://github.com/MainQuestAI/Deck-Master/blob/02627c17d5046428609e6806569ad3cd790e7d26/docs/reports/rc5/engineering-acceptance.md)
- [成对稿回执](https://github.com/MainQuestAI/Deck-Master/blob/02627c17d5046428609e6806569ad3cd790e7d26/docs/reports/rc5/paired-manuscript-review.md)
- [范围探针回执](https://github.com/MainQuestAI/Deck-Master/blob/02627c17d5046428609e6806569ad3cd790e7d26/docs/reports/rc5/scope-probe-review.md)
