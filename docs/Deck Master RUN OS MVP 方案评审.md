
这份方案的核心价值判断是正确的：它没有把 Deck Master 定位成单纯“生成 PPT 的工具”，而是定位成面向售前/咨询方案生产的 **Run OS / Deck Production Runtime**，围绕 brief、claim map、page tasks、sourcing decision、quality gate、preview review、approved export 建立可审查、可追踪、可恢复的生产链路，这个方向和你要做的专业方案资产化、顾问工作流提效是匹配的。上传的确认版也明确将目标限定在“会后客户 Solution Deck 草案”，并保留人工判断和最终交付前审查，这是非常正确的边界控制。

## 1. 总体评估：合理，但建议把 MVP 再切薄一层

我会给当前规划一个判断：**产品方向 8.5/10，工程落地节奏 7/10，MVP 范围控制 6.5/10。**

它合理的地方在于，方案已经抓住了 Deck Master 的真正壁垒：不是“让 AI 生成几页 PPT”，而是让 AI 进入专业顾问 Deck 的生产控制流。专业 Solution Deck 的难点并不只是页面美观，而是：

第一，客户事实、业务目标、会议转写、历史方案和个人判断之间要有结构化承接；
第二，每页需要明确“页面职责”和“核心论点”，不能只是泛泛的行业大字报；
第三，历史页复用要可解释，不能黑盒拷贝；
第四，证据缺口、案例缺口、截图缺口、业务风险要显性化；
第五，最后必须允许顾问在 Web UI 中审查、批准、拒绝、备注和导出。

这几个关键点，在当前确认版里基本都覆盖到了。尤其是 `deck_brief.json`、`claim_map.json`、分层 `page_tasks.json`、`sourcing_plan.json`、`preview_manifest.json`、`quality_reports/`、`approved_queue.json` 这一组状态产物，已经比较接近一个专业生产运行时的骨架。

但问题也很明显：**当前方案把“下一轮产品化实现”写得过完整。** 它同时包含 Workspace Foundation、Shared Runtime Pipeline、Context/Brief/Claim Map、Workspace-aware Planner、Retrieval + Sourcing、Build Skill Handoff、Quality Gate、Web UI Review Panel、Export + Feedback、Docs + Tests + Regression 10 个包。作为完整路线图是合理的，但作为下一轮 MVP，工程面太宽，容易出现每块都做了但每块都不够硬的情况。

我的建议是：**不要砍掉架构，只调整节奏。** 把它分成“Run OS MVP 必须闭环”和“产品化增强”两层。

Run OS MVP 必须先证明一件事：用户给本地资料和 brief 后，系统能够稳定生成一个可审查的 deck run，并且每一页都有明确任务、来源决策、质量发现和人工审批状态。只要这个闭环跑稳，后面的 Build Skill 自动化、Web UI 高级操作、反馈学习、Render/Delivery Gate 都可以逐步增强。

---

## 2. 目前已有代码基础：不是从零开始，方案有现实支撑

从仓库代码看，Deck Master 当前已经有一个初步可运行的 CLI 链路。`scripts/deck_master.py` 已经包含 `plan`、`start-conversation`、`build-brief`、`build-claim-map`、`autoplan`、`search-library`、`decide-sourcing`、`create-generation-tasks`、`build-preview`、`export`、`quality-gate` 等命令入口，这说明确认版方案不是空中楼阁，而是在已有 baseline 上做硬化和产品化。

当前 `autoplan` 已经能够按顺序执行：补计划、检索 PPT Library、做 sourcing decision、创建 generation tasks、构建 preview manifest，最终返回 `autoplan_preview_ready`。这与确认版提出的 “auto-through preview” 基本一致，说明主链路已有可迁移基础。

本地资料到对话/brief/claim map 的链路也已经存在。`start-conversation` 会基于 context file 生成 context manifest、request 和 conversation session；`build-brief` 会基于 request、context manifest、conversation session 编译 deck brief；`build-claim-map` 会基于 deck brief 和 context manifest 生成 claim map。这个设计方向和确认版中“Context 与 Guided Conversation 首版只接本地或已导出资料”的边界一致。

Preview UI 也已有基础服务。当前 server 已经支持获取 deck、run 列表、单页 payload、创建 run、更新页面 decision、加载质量报告等 API，这说明 Web UI 不需要从零开始，但需要重做信息架构和语言系统。

质量门禁也已有雏形。当前 `evaluate_draft_gate` 已经检查业务目标、claim 风险、页面主论点、页面 gaps，并输出 findings、repair plan 和 blocks_delivery；Render/Delivery Gate 也已经围绕 PPTX audit 做了页数、稀疏页、整页截图、禁用词、媒体资源等检查。

所以总体判断是：**规划方向和当前代码基础是对得上的，值得继续推进。** 需要改进的是工程分层、状态模型一致性、MVP 验收边界和若干数据契约。

---

## 3. 主要优点：这份规划抓住了 Deck Master 的产品内核

### 3.1 以 run 为核心，而不是以单次生成任务为核心

当前规划要求每次 Deck 任务形成一个 run，并沉淀 `request.json`、`events.jsonl`、`context_manifest.json`、`deck_brief.json`、`claim_map.json`、`narrative_plan.json`、`page_tasks.json`、`sourcing_plan.json`、`preview_manifest.json`、`quality_reports/`、`approved_queue.json`。这个设计非常关键。

原因是，专业 Deck 生产天然不是单步生成，而是一个可恢复、可审查、可解释的多阶段工作流。尤其对售前解决方案架构师来说，经常会出现：客户补材料、老板改判断、历史页复用需要替换、证据不足需要占位、某页要锁定、某页要重生成。这些都要求系统有稳定状态，而不是一次性 prompt 输出。

当前代码的 `create_run` 已经会创建 run 目录、写入 `request.json`，并追加事件；`ensure_run_dirs` 也会创建 `library_results/by_beat`、`generation_tasks`、`links`、`notes`、`placeholders`、`quality_reports` 等目录。这个基础方向是正确的。

### 3.2 分层 page tasks 是非常正确的设计

确认版明确要求 `page_tasks.json` 采用 `planning / retrieval / sourcing / generation` 分层结构，避免多个阶段反复写同一批平铺字段。

这个设计很重要。因为 Deck Master 后续必然会接入多个工具：Planner、PPT Library、Build Skill、Quality Gate、Web UI、Export。如果 page task 是平铺字段，后续会出现字段 ownership 混乱：Planner 写了 sourcing 字段，Sourcing 又覆盖 generation 字段，Web UI 备注又污染 planner 字段。分层结构可以明确每个阶段的写入边界。

当前 `build_page_tasks` 已经按照 `planning`、`retrieval`、`sourcing`、`generation` 输出任务结构，说明代码层面已经初步对齐。

### 3.3 Sourcing Decision 的四类决策合理

`reuse / adapt / generate / manual_placeholder` 这四类决策非常适合作为 MVP 的 sourcing taxonomy。

这四类实际上对应顾问制 Deck 生产中的四种真实工作方式：

`reuse`：历史页足够匹配，直接进入审查。
`adapt`：历史页结构有价值，但需要换客户语境、标题、论据或视觉。
`generate`：历史库没有合适页面，需要新生成。
`manual_placeholder`：缺客户事实、截图、案例、数据，AI 不应该瞎编，需要人工补证据。

当前代码也已经有这四类决策，并有基础评分逻辑。`candidate_score` 当前使用 confidence、win_rate、reuse_count、screenshot_bonus；`decide_for_beat` 会根据候选分数、截图和证据需求决定 reuse/adapt/generate/manual_placeholder。

虽然当前评分还没有达到确认版里更完整的多维权重，但抽象方向是对的。

### 3.4 Quality Gate 做成内建子系统是正确选择

Deck Master 的差异化不应只靠“生成速度”，而应靠“可交付质量控制”。确认版把 Quality Gate 设为内建子系统，并拆成 Draft Gate、Render Gate、Delivery Gate，非常合理。

其中 Draft Gate 作为硬链路尤其重要。原因是，很多 Deck 的失败并不是出在视觉渲染，而是出在早期叙事结构：没有目标受众、没有业务目标、页面没有主张、证据链不清、案例缺失、章节推进不自然。Draft Gate 越早介入，越能减少后续页面生产浪费。

当前代码里 Draft Gate 已经在检查 `business_goal`、claim risk、page core claim、planning gaps，这个实现方向非常对。

---

## 4. 关键问题：当前实现规划存在 8 个主要改进点

## 问题 1：MVP 范围仍然偏大，建议重新定义 P0/P1/P2

现在的实现包从 Package 0 到 Package 10，基本覆盖了一套完整产品化系统。问题不是这些能力不需要，而是 **不应该在同一轮里都作为强验收项**。

我建议把当前包重新切成三层：

**P0：Run OS 可用闭环，必须本轮完成**

包括：

1. Workspace Foundation 的最小版本：创建/注册 workspace、写 manifest、提供默认 visual/structure/quality 文件。

2. Shared Runtime Pipeline：统一 CLI 和 Web UI 的 runtime 入口，补 `next_step`。

3. Context / Brief / Claim Map：本地资料到结构化输入。

4. Workspace-aware Planner：读取 page archetypes，输出分层 page_tasks。

5. Retrieval + Sourcing：PPT Library 或 fixture 结果，稳定输出四类 sourcing decision。

6. Draft Gate：默认硬链路，阻断 P0/P1。

7. Preview UI 最小审查：看页面、看来源、看风险、approve/reject/note。

8. Approved-only Export：只导出 approved 页面。


**P1：产品化增强，建议本轮可做但不阻塞**

包括：

1. 替换来源。

2. 转生成页。

3. 锁定历史页。

4. Build Skill 状态化执行，但先只做 task package 和 handback，不强制自动跑生成。

5. I18n 完整语言包。

6. Render/Delivery Gate 的 fixture 检查。

7. 真实样本回归。


**P2：后续版本**

包括：

1. 多 Build Skill registry。

2. Web UI 完整专业咨询审查台。

3. 反馈学习系统。

4. slide win-rate 写回 PPT Library。

5. reference PPT 视觉自动抽取。

6. 并行生成、复杂重试。

7. 长期知识库和外部系统连接。


这样切完之后，MVP 就不会被 UI 高级操作、Build Skill 执行状态、Render/Delivery Gate 等功能拖住。

---

## 问题 2：确认版事件模型与当前代码事件模型不一致，需要优先统一

确认版要求事件最小字段包括 `timestamp`、`event_type`、`run_id`、`step`、`message`、`refs`、`severity`。

但当前 `append_event` 实际写入的是 `timestamp`、`actor`、`action`、`target`、`status`、`payload_ref`、`error`、`data`。

这不是小问题。因为事件日志会承担四个职责：审计、恢复、Agent 解释、Web UI 风险展示。如果 schema 不统一，后面会出现：

第一，`next_step` 无法稳定判断失败状态；
第二，Web UI 很难按 step/status/severity 聚合；
第三，Agent 无法基于事件解释“为什么卡住”；
第四，人工操作和工具失败混在 action 字符串里，不利于后续统计。

建议不要立刻把旧事件全部废掉，而是做一个兼容升级：

```json
{
  "timestamp": "2026-06-10T00:00:00Z",
  "event_type": "step_completed",
  "run_id": "retail-conversation",
  "step": "sourcing",
  "message": "Sourcing decision completed for 14 pages.",
  "refs": ["sourcing_plan.json", "library_results/selection.json"],
  "severity": "info",
  "actor": "deck_master",
  "action": "sourcing.plan.created",
  "status": "ok",
  "payload_ref": "sourcing_plan.json",
  "data": {}
}
```

也就是说，**保留 action/status 兼容旧逻辑，但新增 event_type/run_id/step/message/refs/severity 作为 canonical 字段。**

这是我建议优先于 Web UI 重构做的事情。因为事件模型一旦不稳定，后续所有恢复、失败解释、审查面板都会反复返工。

---

## 问题 3：`next_step` 是 Run OS 的中枢，但当前代码还没有 canonical resolver

确认版明确要求 Runtime 必须有 canonical `next_step` 解析器，并列出了 request、brief、claim map、narrative plan、library results、sourcing plan、generation tasks、preview、quality reports、approval/export 的恢复规则。

当前代码已有 `run_status`，但它只根据 `preview_manifest.json`、`sourcing_plan.json`、`narrative_plan.json`、`request.json` 判断粗状态。

这个粒度不够。因为确认版链路里新增了 context、conversation、deck_brief、claim_map、page_tasks、library_results、generation_tasks、quality_reports、approved_queue 等多个关键产物。只靠 `run_status` 无法回答：

- 当前 run 应该下一步 build brief 还是 build claim map？

- library selection 是否失败但可回退？

- Draft Gate 是否阻断？

- preview 存在但是否有待审页面？

- 有 approved 页面但是否允许 export？

- 某个 JSON 坏了是否应该停止而非覆盖？


建议新增 `runtime/next_step.py`，输出结构化诊断：

```json
{
  "run_id": "retail-conversation",
  "status": "quality_blocked",
  "next_step": "review_draft_gate_findings",
  "can_continue": true,
  "blocking_reasons": [
    {
      "severity": "P1",
      "message": "3 pages missing core claim",
      "refs": ["quality_reports/draft_gate.json"]
    }
  ],
  "available_actions": [
    "open_web_ui",
    "repair_page_tasks",
    "rerun_draft_gate"
  ]
}
```

并把 CLI 和 Web UI 都统一依赖它，而不是各自判断状态。

---

## 问题 4：Workspace Foundation 合理，但当前计划应避免“文件结构完整、实际标准空心化”

确认版要求本期做完整 Workspace Foundation，包括 `workspace_manifest.json`、`AGENTS.md`、`visual-system/`、`structure-assets/`、`quality/`、`sources/`、`projects/`、`runs/`、`exports/`、`reference-analysis/`。

这个方向正确，但要注意一个风险：**只创建目录和 starter markdown，没有让 Planner / Quality Gate 真正读取，就会变成“工作区壳子”。**

我建议 Workspace Foundation 验收不要只验“目录存在”，而要验三件事：

1. Planner 确实读取 `structure-assets/page_archetypes.md`，并把 `workspace_refs` 写入 page task。

2. Planner 确实读取 `visual-system/spec_lock.md` 或 `design_spec.md`，并生成 `style_constraints`。

3. Draft Gate 确实读取 `quality/scoring_rubric.md` 或 `failure_modes.md`，至少能够把 workspace 的质量标准映射成 finding 规则或 quality requirement。


当前 page task 里 `workspace_refs` 还是空数组，说明这块还没有真正接入 Workspace 标准。

建议把 Package 1 和 Package 4 之间加一个非常明确的验收口径：

```text
同一个 brief，在没有 workspace 时使用默认 page archetype；
在有 workspace 时，每页必须带 preferred_archetype、workspace_refs、style_constraints、quality_requirements；
Draft Gate 报告里必须能显示至少一条来自 workspace quality policy 的规则。
```

这样 Workspace 才不是形式化资产。

---

## 问题 5：Planner 当前仍偏模板化，需要补“论点-论证-论据”的业务智能

确认版要求 Planner 把页面设计成“论点、论证、论据”的承载单元，避免泛泛生成大字报式页面。

但当前 `plan_narrative` 主要基于 page_count 和 beat_templates 生成页面，并根据 role 写 `evidence_need`、`visual_need`、`generation_brief`。它的 gap 识别目前也比较浅，只判断 industry、must_cover_topics、是否提到案例。

这意味着当前 Planner 能生成结构，但还不足以生成真正的咨询方案主线。建议对 Planner 做三项增强：

第一，新增 `argument_chain`。
每个 beat 不只要有 `core_claim`，还应有：

```json
"argument_chain": {
  "why_now": "客户为什么现在需要做这件事",
  "business_tension": "业务矛盾是什么",
  "solution_logic": "方案如何解决矛盾",
  "proof_needed": "需要什么证据证明"
}
```

第二，新增 `customer_specificity_level`。
页面应区分：

- `generic_method`：通用方法论页；

- `industry_contextualized`：行业化页；

- `customer_specific`：客户事实页；

- `evidence_locked`：必须引用客户证据页。


这样可以决定哪些页允许 generate，哪些页必须 manual_placeholder。

第三，新增 `decision_intent`。
专业 Deck 不是信息堆叠，而是推动客户决策。每页应该标记：

```json
"decision_intent": "让客户认可库存可视化不是报表项目，而是履约效率项目"
```

这会显著提升页面质量，也会让 Draft Gate 更好判断页面有没有主张。

---

## 问题 6：Sourcing Decision 的权重设计合理，但当前实现与确认版存在差距

确认版的 Sourcing 初始权重比较完整，包括语义匹配、叙事角色匹配、页型匹配、截图可用、来源可信度、胜率、复用次数、客户语境冲突、视觉连续性、证据充分性。

当前代码实际 scoring 还比较简化，只使用 confidence、win_rate、reuse_count、screenshot_bonus，并且阈值是 `reuse >= 0.74`、`adapt >= 0.45`，和确认版的 `reuse >= 0.78`、`adapt >= 0.58` 不一致。

建议这里不要一步到位做复杂模型，但要把 scoring 拆成可解释字段：

```json
"score_breakdown": {
  "semantic_match": 0.72,
  "narrative_role_match": 0.80,
  "archetype_match": 0.65,
  "screenshot_available": 1.0,
  "source_credibility": 0.6,
  "win_rate": 0.67,
  "reuse_count": 0.6,
  "customer_context_conflict": 0.2,
  "visual_continuity": 0.5,
  "evidence_sufficiency": 0.4
}
```

即使部分字段先用 heuristic，也要先把结构打出来。这样后续 PPT Library、Feedback、Quality Gate 都能逐步接入。

同时，建议把 `manual_placeholder` 的判断从现在的关键词规则升级成“证据需求等级”规则。当前 `page_needs_manual_evidence` 主要看“客户案例、案例、收益指标、成本优化”等关键词。 这容易误判。更合理的是在 Planner 阶段就给每页写：

```json
"evidence_policy": {
  "required": true,
  "evidence_types": ["customer_quote", "case_metric", "product_screenshot"],
  "allow_ai_generated_without_evidence": false
}
```

然后 Sourcing 再根据 evidence_policy 决定是否 `manual_placeholder`。

---

## 问题 7：Web UI 的确认版目标偏重，建议首版先做“审查台”而不是“操作台”

确认版 Web UI 要实现中文/英文语言包、显式语言切换、顶部状态条、左侧页面列表、中央预览、右侧审查面板、底部状态抽屉、Draft Gate 阻断、Build Skill 状态、审批备注、替换来源、转生成页、锁定历史页等。

从产品上看，这些都对。但从 MVP 落地看，建议先分两步：

**第一步：Review-only UI**

必须有：

- Run 状态；

- 页面列表；

- 页面预览；

- source decision；

- selected candidate；

- alternatives 只读展示；

- risk flags；

- Draft Gate finding；

- generation task 状态只读展示；

- approve / reject / note；

- approved-only export。


**第二步：Action UI**

再做：

- 替换来源；

- 转生成页；

- 锁定历史页；

- 触发 Build Skill；

- rerun 单页；

- override P0/P1；

- 多语言完整切换。


原因是，当前 preview manifest 的审批状态还没有和确认版完全一致。确认版要求 `needs_review / approved / rejected`，但当前 manifest 允许的是 `needs_review / keep / replace / approved`。

这会直接影响 Web UI、Export、Feedback、Quality Gate 的状态语义。建议先统一审批状态：

```text
review_status:
- needs_review
- approved
- rejected

action_intent:
- none
- replace_source
- convert_to_generate
- lock_history
```

不要把“审批结果”和“后续动作”混成一个字段。当前的 `keep`、`replace` 更像 action intent，不是审批状态。

---

## 问题 8：Export 需要纳入质量阻断，不应只按 approved 过滤

当前 export queue 逻辑只按 manifest page decision 过滤，默认导出 `approved` 页面。

确认版要求 P0/P1 页面不能进入最终 handback，除非有显式 override；`manual_placeholder` 不能作为最终交付页。

所以当前 export 需要补三类判断：

第一，读取 `quality_reports/draft_gate.json`、`render_gate.json`、`delivery_gate.json`，检查 page-level P0/P1。
第二，检查页面 `source_decision == manual_placeholder` 时不能进入 client-facing export。
第三，支持 override，但 override 必须写事件：

```json
{
  "event_type": "manual_action",
  "step": "export",
  "message": "User overrode P1 finding for beat_004",
  "severity": "warning",
  "refs": ["quality_reports/draft_gate.json", "approved_queue.json"]
}
```

否则 approved-only export 只是“人工审批过滤”，还不是“质量门禁后的导出”。

---

## 5. 我建议调整后的实现顺序

我建议把确认版 10 个包改成下面 7 个更稳的包。这个顺序更利于快速形成稳定闭环。

|优先级|实现包|核心目标|验收重点|
|--:|---|---|---|
|P0-1|Runtime Contract Hardening|统一 run state、typed events、next_step、坏 JSON 处理|CLI 和 Web UI 都基于同一个 `next_step`|
|P0-2|Workspace Foundation Lite|创建/注册 workspace，读取 visual/structure/quality 标准|page_tasks 真的写入 workspace_refs|
|P0-3|Context → Brief → Claim Map|本地材料结构化，形成可复用 deck brief 和 claim map|同一输入可重复生成稳定结果|
|P0-4|Workspace-aware Planner|生成 narrative_plan 和分层 page_tasks|每页有 core_claim、evidence_need、gaps、decision_intent|
|P0-5|Library + Sourcing v1|每页稳定输出 reuse/adapt/generate/manual_placeholder|有 score_breakdown、decision_reason、risk_flags|
|P0-6|Draft Gate + Review UI|Web UI 展示页面、来源、风险、质量 finding，支持 approve/reject/note|Draft Gate P0/P1 能阻断 export|
|P0-7|Export + Regression|approved-only + quality-aware export，跑零售和达能样本|真实样本能到可审查草案|

Build Skill 建议在 P0-5 之后只做 **task package 生成和 handback contract**，不要把“自动执行一个默认 Build Skill”作为 P0 阻断项。因为 Build Skill 一旦纳入自动执行，就会引入失败重试、耗时任务、局部失败、并发、产物回写、artifact freshness 等问题，会显著拉高复杂度。

---

## 6. 需要补充的关键数据契约

为了避免后续代码返工，我建议尽快补 6 个 schema，并作为测试基准。

### 6.1 `run_status.json` 或 `next_step.json`

虽然可以动态算，但建议每次 pipeline 后输出一个状态快照，便于 UI 和 Agent 读取。

```json
{
  "run_id": "retail-conversation",
  "status": "draft_gate_blocked",
  "current_step": "draft_gate",
  "next_step": "repair_page_tasks",
  "blocking": true,
  "blocking_reasons": [],
  "available_actions": []
}
```

### 6.2 `page_task` schema

当前已有结构，但建议补足：

```json
{
  "planning": {
    "core_claim": "",
    "decision_intent": "",
    "argument_chain": {},
    "evidence_policy": {},
    "customer_specificity_level": ""
  }
}
```

### 6.3 `sourcing_decision` schema

建议统一字段名。当前代码里叫 `source_decision`，确认版里叫 `decision`。建议对外统一：

```json
{
  "decision": "adapt",
  "decision_reason": "",
  "score": 0.66,
  "score_breakdown": {},
  "selected_candidate": {},
  "alternatives": [],
  "risk_flags": [],
  "confidence": 0.66
}
```

内部兼容 `source_decision`，但 canonical 用 `decision`。

### 6.4 `review_status` schema

建议拆开审批状态和动作意图：

```json
{
  "review_status": "needs_review",
  "review_note": "",
  "action_intent": "none",
  "locked": false
}
```

### 6.5 `quality_finding` schema

建议补 `blocking_scope`：

```json
{
  "severity": "P1",
  "blocking_scope": "page",
  "page_id": "beat_004",
  "dimension": "evidence_and_specificity",
  "message": "",
  "repair_instruction": "",
  "refs": []
}
```

### 6.6 `override` schema

后续交付必须有 override 机制，但不能静默：

```json
{
  "override_id": "override_001",
  "target": "beat_004",
  "finding_id": "beat_004_gaps",
  "reason": "客户口头确认，下一版补截图",
  "actor": "user",
  "created_at": ""
}
```

---

## 7. 对当前确认版中各模块的具体判断

|模块|合理性|当前判断|建议|
|---|--:|---|---|
|产品目标|高|目标明确，聚焦会后 Solution Deck 草案，符合真实顾问场景|保持不变|
|应用形态|高|Agent + CLI/Runtime + localhost UI + Workspace 分层合理|保持，但强调 Runtime 是唯一状态源|
|Run 状态模型|高|产物设计完整|补 schema version、next_step、artifact freshness|
|事件模型|中高|方向正确，但与现有代码不一致|优先做兼容升级|
|Workspace|高|是产品资产化关键|不要只建目录，必须让 Planner/Gate 真实读取|
|Context / Guided Conversation|高|首版只接本地资料非常务实|增加 source hash、摘要边界、敏感信息标记|
|Planner|中高|分层 page task 方向正确|增强论点链、证据策略、客户特异性|
|PPT Library|高|Deck Master 做决策、Library 做检索，边界清楚|补 score_breakdown 和候选字段校验|
|Sourcing|中高|四类决策正确|统一阈值，实现与文档对齐|
|Build Skill|中|方向对，但放入本期强验收偏重|P0 只做 task package，不强制自动执行|
|Quality Gate|高|是产品核心护城河|Draft Gate 硬链路优先，Render/Delivery 后移|
|Web UI|中高|审查台定位正确|首版先做 review-only，action UI 后移|
|Export|中|approved-only 有基础|必须接入 P0/P1 和 manual_placeholder 阻断|
|Feedback|中|方向对|首版只记 outcome，不做学习闭环|

---

## 8. 最关键的 5 个改进建议

### 建议 1：把本轮目标从“全链路产品化”改成“Run OS 可审查闭环”

当前确认版容易让工程团队误以为每个模块都要做到产品完成态。建议明确本轮 North Star：

> 从本地资料/brief 出发，稳定生成一个可恢复、可审查、带来源决策和 Draft Gate 的 Deck Run；用户可以在 Web UI 中完成页面审查，并导出通过质量门禁的 approved queue。

这句话比“完成 10 个 Package”更适合作为 MVP 验收目标。

### 建议 2：Runtime、Events、Next Step 必须先于 UI 和 Build Skill

这是底座。没有统一 runtime，就会出现 CLI 一套状态、Web UI 一套状态、Agent 又一套解释逻辑。当前代码已有 run_state 和 events，但还没有完全对齐确认版 typed events 和 canonical next_step。

### 建议 3：Web UI 首版不要过早做复杂操作

替换来源、转生成页、锁定历史页都很有价值，但它们会改变 sourcing_plan、generation_tasks、preview_manifest 和 events。首版先把只读审查和 approve/reject/note 做稳，后续再加操作能力。

### 建议 4：Build Skill 先定义 contract，不要急着自动执行

确认版说本期支持一个默认 Build Skill 的状态化执行。这个可以做，但我建议不要作为首轮闭环必须项。先把 `generation_tasks/<beat_id>.json`、`artifact handback contract`、`status`、`errors` 设计好即可。自动执行留到下一阶段，否则会把 MVP 拉入复杂的异步任务和失败恢复问题。

### 建议 5：质量门禁要接入导出，而不是只做报告

当前 Quality Gate 已经能生成报告，但最终价值在于阻断不合格页面。导出逻辑必须读取 quality finding，否则 Quality Gate 会变成旁路报告。当前 export queue 只按 decision 过滤，还需要补 P0/P1、manual_placeholder、override 规则。

---

## 9. 建议的最终 MVP 验收口径

我建议把下一轮验收标准写成下面这样，更清楚、更可测。

**MVP 通过标准：**

1. 可以创建或注册一个 Deck Workspace。

2. 可以输入本地会议转写/客户材料/历史方案摘要/口头判断，创建一个 run。

3. run 目录下能稳定生成 `request.json`、`context_manifest.json`、`conversation_session.json`、`deck_brief.json`、`claim_map.json`、`narrative_plan.json`、`page_tasks.json`。

4. `page_tasks.json` 必须采用 `planning / retrieval / sourcing / generation` 分层结构。

5. Planner 必须读取 workspace page archetypes，并在 page task 中写入 `preferred_archetype` 和 `workspace_refs`。

6. PPT Library 可用时调用真实检索，不可用时使用 fixture，run 不进入不可恢复状态。

7. 每页必须有唯一 sourcing decision：`reuse / adapt / generate / manual_placeholder`。

8. 每个 sourcing decision 必须有 `decision_reason`、`risk_flags`、`confidence`、`selected_candidate/alternatives`。

9. Draft Gate 默认运行，并对缺业务目标、缺主论点、缺证据、缺 gaps 标记输出 finding。

10. Web UI 能展示 run 状态、页面预览、来源决策、候选来源、风险、Draft Gate findings。

11. 用户可以对页面执行 `approved / rejected / needs_review` 和备注。

12. Export 只输出 approved 页面，且 P0/P1 或 manual_placeholder 页面默认不能进入最终导出。

13. 所有关键步骤、工具失败、人工操作都写入 typed events。

14. 零售 fixture 和达能 AI 消费者样本至少能跑到可审查草案。

15. 坏 JSON、PPT Library 不可用、Build task 缺失、preview asset 缺失都不能静默覆盖已有数据。


这个验收口径比当前确认版更偏“工程可落地”，也更能防止产品范围膨胀。

---

## 10. 总结判断

**这个项目值得继续推进，且当前实现规划的大方向是正确的。** 它已经从普通 PPT 生成器，上升到了面向专业顾问的 Deck 生产运行时：有 Workspace、有 Run、有状态、有来源、有质量门禁、有审查、有导出，这个架构方向具备产品壁垒。

但如果按确认版原样推进，最大的风险是 **MVP 过宽、事件/状态契约不先行、Web UI 和 Build Skill 抢占底座建设资源**。我建议下一步不要急着重做完整 UI，也不要急着自动执行 Build Skill，而是先把以下四件事做硬：

1. **Runtime Contract**：typed events、next_step、状态恢复、坏 JSON 防覆盖。

2. **Workspace-aware Planner**：真正读取 workspace 标准，输出高质量分层 page tasks。

3. **Sourcing + Draft Gate**：每页有可解释来源决策，每页有质量判断。

4. **Review UI + Quality-aware Export**：用户能审、能批、能拒，且导出不绕过质量门禁。


这样做完后，Deck Master 就已经不是 demo，而是一个真正可用的 **Solution Deck Run OS MVP**。