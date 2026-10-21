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

## v1.1 云端 WU00 核对（2026-10-20）

上文是原 v1.0 编制时的历史观察，不代表本云端环境或 PR127 最终状态。本环境 checkout 从干净的 main `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8` 建立独立 `codex/webui-post127-spec-review-20261020` 规格分支；未访问用户本机，未检出/写入 PR127 分支，未推送、合并、发布或开始产品实现。仓库 AGENTS、任务索引、恢复指引、DESIGN、当前 UI 语言已读取；云端 .agents/.codex 为空，无额外嵌套 AGENTS。

只读 ls-remote/fetch 首次观察 `02627c17`，末次观察推进至 `d1ee1c7d1f16db120fd4c91c2cc9e71ce31b915e`，main 未变。两观察 head 相差 8 文件；最新观察 head 相对 main 为 122 文件、5223 行新增、277 行删除，web.py/static 无改动。新修复把 blueprint 最终选择校验移到持久请求之前；移除 compose design/production/delivery 的错误 method-selection 默认；Review 方法读取固定 review phase/units；重派保留原冻结记录。新 WebUI 不能把这些基础能力重做一遍。

现有 collaboration-desk、launcher、固定版本 /api/content-plan、正文/来源、Review 及内容操作均需复用。六项源码裁决：

| 裁决 | 已读取源码锚点（main 09f0213d；PR127 修改另核对） | 规格落点 |
|---|---|---|
| R1 | collaboration.py:553；content_production.py:1646；eligibility.py decision.record/proposal.adopt | 独立决定/采用准入，原两个事务不变 |
| R2 | d1ee1c7d 的 service.py _continue_project、method_resources.py、resource_catalog.py select | 目录浏览独立于派发；不调用 continue 预览，不放宽 resolver |
| R3 | web.py:684；content_plan.py _projection_v2/show；content_production.py:485 | 固定 Plan 已有读取；候选 Plan 需要只读关联投影，零 Page 保留职责 |
| R4 | snapshots.py 合法快照；content_production.py 采用谓词 | 比较两真实 Narrative，current+candidate 合法；比较不产生写授权 |
| R5 | review.v1 schema（含最早提交 032de48f）；models.py:399；review.py finding 消费 | v1 已要求 finding_id/impact/resolution，无依据的缺 ID 兼容删除，固定 Ref/revision 深链 |
| R6 | content_plan.py 不可读投影；view.py Review 局部错误 | 明确判别 union 与 null，禁止编造业务值 |

本环境 `gh pr view 127` 被 Forbidden 拒绝，未重试或换渠道绕过。父线程另提供的证据：准确 head d1ee1c7d 的 CI 39398981973 仍运行，渲染通过、单元与浏览器待完成，静态复审未见新增阻断。此为转交观察，不是本环境独立验证或 CI 终态。最终 head/收口、required CI、包证据与最终基线适用性仍待父线程确认，G0 未通过。

原 Library 传输失败后未重试；父线程分 15 批提供原文。本环境核对 manifest 的全部 14 个内容文件，bytes/SHA 全匹配；另保留 manifest，共 15 文件。原文冻结于提交 `4f7f2a3b`，manifest 在 original-package-manifest.json，原 inputs/impact-report.md 不修改。其历史本机路径只保留为报告文本，未访问。验证脚本已阅读未执行；本轮检查为独立文档静态核对，不代表产品/浏览器/安装/Host/专业/人类验收。

## WU00 实施门槛确认（父线程授权续接）

实施基线为 3217a65630023244eac5a09b3e7570954cce9188。父线程确认精确 head CI 39401753812 在 2026-10-20 10:31 UTC completed/success（browser/installed UI、四组 unit、rendering、Group report）。本地 fetch/ls-remote 确认 PR127 分支该 SHA，main 仍 09f0213d，未包含修复；独立分支 codex/webui-content-methods-20261020 以精确 head 建立。PR127 仅为依赖，不自动合并；Draft PR 目标为其分支以展示净增量，后续再迁移到 main。

包报告实际绑定 d1ee1c7d，不冒称为 3217a656 构建；git diff 核对两者 src/skills/pyproject/setup/MANIFEST/tools 均无变化，仅报告与一处测试校正，包对应的运行源码和资源适用。此前局部 shared-lock 单测失败仍为未查明的环境验证限制，不因 CI 全绿杜撰根因。产品实现按已授权范围开始，最终本轮包仍需绑定新实现 SHA。

基于新授权证据只重试一次 PR127 只读 GraphQL，仍 Forbidden；不再重试或绕过。规格原始提交与修订提交保留在原分支，新分支仅 cherry-pick 文档，不改 PR127/PR128/PR129。
## 本回合只读复核补记

2026-10-20，`git ls-remote` 再次成功：PR127 分支为 `3217a65630023244eac5a09b3e7570954cce9188`，main 为 `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`。这是远端引用观察，不把 head 自动认定为已收口。PR 元信息读取此前 Forbidden，本回合没有重试或绕过；最终基线确认和 required Checks 仍等待本任务明确接续证据。

相对原观察 `02627c17`，共 12 文件、351 行新增、15 行删除；涉及方法阶段默认、blueprint 写前校验、旧任务重派、案例/算术脚本及回归和报告。相对 main 的 `web.py` 与静态 UI 无差异，未发现本规格六类新增阅读接口已被 PR127 实现。包报告绑定 `d1ee1c7d`；该 SHA 到 `3217a656` 仅变更四份报告和一份测试，运行源码/资源未变化。因此可说明包证据的源码适用性，不能称为从 `3217a656` 构建或本任务执行安装验证。已读取报告中共享锁测试在原基线亦失败的限制，不以其他通过记录抹除该限制。

本回合开始时 `/workspace/Deck-Master` 已在另一实现分支并带有产品源码未提交改动。没有修改、执行或提交这些文件；为本回合限定的文档工作另挂载 `/workspace/Deck-Master-spec-review`，分支 `codex/webui-post127-spec-review-20261020`。本回合没有启动产品实现、推送、创建 PR、合并或发布。后续实现状态不能由此文档检查推导。

重新用 `git show 4f7f2a3b:<path>` 核对原 manifest：14/14 bytes 与 SHA256 匹配；另有 manifest 本身，共 15 文件。独立静态断言确认 9 卡、50 AC、唯一 owner、ACCEPTANCE 与 traceability 的逐项 pass_condition 一致。直接读 `3217a656` 的 Review v1/v2 schema，二者 finding 均要求 finding_id/impact/resolution。附件脚本未执行；产品、浏览器、安装、实际 Host、专业阅读、人类认可均未在本回合验证。

## 开发接续：父线程确认与隔离检查点（取代上文 pending）

父线程明确确认 PR127 最终可用 head `3217a65630023244eac5a09b3e7570954cce9188`，CI run `39401753812` completed/success、全部 jobs 通过。此为外部提供证据，不重试 Forbidden 的 PR 元信息读取。main 尚为 09f0213d 时，采用未合并依赖分支，不合并 PR127。包报告绑定 d1ee1c7d，运行代码/资源与最终 head 无差异，原证据适用但不冒称精确 head 构建。G0 已满足，产品实施获明确授权。

现有六文件草稿与本任务前段实现记录一致（两个核心纯检查抽取、读取服务/路由及测试），未发现无关用户改动。按 SHA256 保存至 `/workspace/webui-spec-input/implementation-resume/` 并保留原工作区。开发接续在新工作树 `/workspace/Deck-Master-webui`、分支 `codex/webui-content-methods-impl-20261020`，由 4c6102ba（包含最终基线）建立，带入最新规格 a5c40511（本分支对应 39c8256f）。原工作树与 PR127 未修改。

无副作用回归曾捕获决定预检通过 resolve_evidence 写入指令文本，已将该持久化步骤留在正式事务入口，纯检查只接收已存在的证据 Ref。当前验证必须按最终实现 SHA 重新绑定；此前通过记录不自动关闭全部 AC。
