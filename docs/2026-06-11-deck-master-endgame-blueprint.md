# Deck Master 终局蓝图：专业方案叙事生产系统

日期：2026-06-11  
状态：终局蓝图 v0.1  
来源：Office Hour、CEO Review、Engineering Review、Design Review、终局思考评审、Run OS MVP 方案评审  
适用范围：Deck Master 长期产品方向、阶段路线和本轮 MVP 取舍依据

## 1. 文档定位

这份文档回答 Deck Master 的长期目标。

`Run OS MVP` 回答的是一次 Deck run 如何被创建、恢复、规划、检索、审查和导出。终局蓝图回答的是多次客户项目之后，Deck Master 会积累什么能力，以及它为什么能成为专业方案人员的长期生产系统。

后续文档关系：

| 文档 | 职责 |
|---|---|
| 本文档 | 定义终局产品方向、价值飞轮和阶段路线 |
| `docs/2026-06-10-run-os-mvp-confirmed-implementation-plan.md` | 定义下一轮可执行 MVP |
| `docs/2026-06-10-web-ui-design-spec.md` | 定义 localhost Web UI 审查面板 |
| `docs/2026-06-10-planning-review-log.md` | 记录评审过程和决策来源 |

## 2. 终局定位

Deck Master 的终局是专业 Solution Deck 的叙事生产系统。

它面向售前解决方案架构师、咨询顾问、行业方案团队和专业服务团队，把客户上下文、历史方案资产、专家判断、证据材料、页面生产工具、质量门禁和人工审查连接成一个可运行、可追踪、可复用、可持续学习的生产系统。

一句话定义：

> Deck Master 帮助专业方案人员把客户上下文、历史方案资产和专家判断转化为可证明、可审查、可交付、可复用的 Solution Deck，并让每一次交付持续沉淀为后续项目的方案资产。

终局关键词：

| 关键词 | 含义 |
|---|---|
| Solution Deck | 聚焦客户方案、售前方案、咨询汇报、投标方案和专业服务交付材料 |
| 专业叙事 | 强调论点、论证、论据、客户决策推进和证据链 |
| 生产系统 | 覆盖上下文、对话、规划、检索、生成、审查、质检、导出和反馈 |
| 资产复利 | 每次交付沉淀论点、页型、证据、历史页、质量规则和业务结果 |
| 人机协作 | AI 负责整理、规划、检索、生成和质检，用户负责关键业务判断和最终交付判断 |

## 3. North Star Outcome

终局成功状态：

> 用户可以从一次客户上下文出发，在一个可审查生产闭环内，生成证据充分、来源可追踪、视觉一致、质量可控、可继续打磨的客户 Solution Deck；同时，每一次交付都会沉淀为未来可复用的方案资产。

近期硬指标仍然保留：

- 从“方案思路基本确认”到“第一版可审查草案”，从约 12 小时压到约 2 小时。
- 第一场景聚焦会后客户 Solution Deck 草案。
- 第一用户聚焦售前解决方案架构师。
- 第一批真实样本来自当前用户自己的客户方案工作流。

长期指标应逐步增加：

| 指标 | 含义 |
|---|---|
| 草案产出时间 | 从上下文输入到可审查草案的耗时 |
| 页面通过率 | Draft Gate 和人工审查后可保留页面比例 |
| 历史页有效复用率 | reuse / adapt 页面进入最终交付的比例 |
| 证据缺口发现率 | 早期被发现并可处理的证据缺口数量 |
| 质量问题复发率 | 同类质量问题在后续 run 中是否减少 |
| 资产沉淀率 | 每次交付后新增可复用 claim、evidence、page archetype、historical slide 的数量 |
| 业务推进信号 | 客户认可、进入下一阶段、形成报价/SOW/合同等结果信号 |

## 4. 终局系统构成

Deck Master 终局由 8 个系统组成。

| 系统 | 职责 |
|---|---|
| Context Intelligence | 把会议转写、客户材料、产品资料、历史方案和用户判断变成结构化项目上下文 |
| Solution Narrative Engine | 构建 Deck 目标、核心主张、证明路径、章节策略、页面职责和客户决策推进逻辑 |
| Claim-Evidence Graph | 关联核心论点、支撑逻辑、证据、假设、风险、页面和来源 |
| Asset Intelligence | 管理历史页面、案例、页型、视觉模式、复用记录和交付结果 |
| Deck Run OS | 管理一次 run 的状态、事件、恢复、工具调用、审批点和中间产物 |
| Build Skill Runtime | 把页面任务交给页面生成、图表生成、架构图生成等生产能力，并回收产物 |
| Quality & Governance | 内建 Draft、Render、Delivery、Evidence、Brand、Confidentiality 等质量门禁 |
| Review & Decision Cockpit | 通过 localhost Web UI 支持页面预览、来源审查、质量风险和交付判断 |

## 5. 价值飞轮

Deck Master 的长期价值来自工作区级资产复利。

```text
客户上下文输入
→ 创建 Deck Run
→ 形成 Brief / Claim / Evidence / Page Tasks
→ 检索历史资产或生成新页面
→ 人工审查和质量门禁
→ 最终交付
→ 记录 approved / rejected / replaced / delivered
→ 更新历史页面、页型、论点、证据和质量规则
→ 下一次 run 更快、更准、更接近专家判断
```

这个飞轮决定 Deck Master 的壁垒：

- 单次 run 让用户更快产出草案。
- 多次 run 让工作区积累可复用方案资产。
- 团队级 run 让专家经验成为可治理、可复用、可传承的生产能力。

## 6. 核心数据资产

### 6.1 Deck Workspace

Workspace 是客户、行业、品牌或团队的方案资产容器。

终局里，Workspace 是方案资产容器。它保存：

- 视觉规范。
- 页型资产。
- 历史页面。
- 论点资产。
- 证据资产。
- 质量规则。
- 历史 run。
- 导出物。
- 审查记录。
- 反馈结果。

本轮实现仍采用文件系统优先形态，便于本地运行、Agent 调用和真实项目验证。

### 6.2 Claim-Evidence Graph

`claim_map.json` 是起点，终局应升级为 Claim-Evidence Graph。

核心对象：

| 对象 | 说明 |
|---|---|
| `claims` | 本 Deck 要证明的核心主张 |
| `evidence` | 客户原话、截图、数据、案例、产品能力、历史方案、外部资料 |
| `assumptions` | 当前暂时成立但需要确认的判断 |
| `risks` | 证据不足、客户语境冲突、交付风险、合规风险 |
| `page_claim_links` | 页面和 claim 的对应关系 |
| `evidence_page_links` | 证据和页面的对应关系 |
| `source_refs` | 每条证据和判断的来源指针 |

每页都应能回答：

- 本页证明哪个 claim。
- 本页用了哪些 evidence。
- 哪些 evidence 缺失。
- 哪些内容来自客户资料。
- 哪些内容来自历史方案。
- 哪些内容来自 AI 推断。
- 哪些内容需要客户确认。

### 6.3 Consulting Judgment Layer

专业 Deck 的价值来自业务判断。Deck Master 需要把关键判断结构化，避免关键依据只停留在 brief 文本里。

建议对象：

```json
{
  "consulting_judgments": [
    {
      "judgment": "客户当前的核心问题是跨渠道运营闭环薄弱。",
      "why_it_matters": "这决定方案主线应从运营模式升级切入。",
      "supporting_evidence": ["meeting_quote_003", "current_process_map_001"],
      "deck_implication": "前 5 页优先建立业务闭环，而非直接讲工具能力。"
    }
  ]
}
```

### 6.4 可学习页型

Page Archetype 应从静态模板升级为可学习生产模式。

终局字段：

- `archetype_id`
- `best_for`
- `required_modules`
- `evidence_pattern`
- `visual_pattern`
- `common_failures`
- `approval_rate`
- `reuse_count`
- `delivery_outcome`

这样系统会逐渐知道哪些页型适合高管汇报，哪些适合技术评审，哪些适合投标应答，哪些经常缺证据。

### 6.5 Delivery Outcome

`approved / rejected` 只能说明页面审查结果，不能完整反映业务结果。终局需要 `delivery_outcome.json`。

建议记录：

- 是否进入最终交付。
- 哪些页面进入最终版。
- 哪些页面被客户重点关注。
- 哪些页面被内部重写。
- 是否推进到下一阶段。
- 是否形成报价、SOW 或合同。
- 哪些 claim 被认可。
- 哪些 claim 被质疑。
- 哪些证据后续被补齐。

## 7. 五阶段路线

### 阶段 1：Run OS Core

目标：

> 把一次客户方案 Deck 生产从不可控手工过程，变成可运行、可追踪、可审查的 run。

核心能力：

- Workspace。
- Run。
- Context Manifest。
- Conversation Session。
- Deck Brief。
- Claim Map。
- Narrative Plan。
- Page Tasks。
- Sourcing Plan。
- Preview Manifest。
- Draft Gate。
- Approved Queue。

阶段价值：

- 用户不再从空白 PPT 开始。
- 每页有任务、有来源、有风险、有审批状态。
- 从约 12 小时压到约 2 小时的第一版可审查草案。
- AI 输出不再是黑盒生成。

当前 `Run OS MVP` 属于这个阶段。

### 阶段 2：Solution Narrative Engine

目标：

> 让 Deck Master 帮助用户形成专业方案主线。

核心能力：

- Consulting Judgment Layer。
- Claim-Evidence Graph。
- Argument Chain。
- Decision Intent。
- Section Strategy。
- Audience Strategy。
- Objection Handling。
- Evidence Policy。
- Customer Specificity Level。

阶段价值：

- 输出更像专业顾问写的方案。
- 用户从改页面转向审主线。
- 每页围绕客户决策推进承担明确职责。

### 阶段 3：Asset Intelligence

目标：

> 让历史方案资产产生复利。

核心能力：

- slide-level asset graph。
- canonical slide id。
- page archetype tagging。
- claim / evidence tagging。
- visual pattern tagging。
- approval / rejection feedback。
- reuse / adapt / generate 决策学习。
- historical case matching。
- workspace asset health report。

阶段价值：

- 优秀页面可沉淀。
- 低质量页面可识别。
- 历史交付变成未来生产能力。

### 阶段 4：Quality & Delivery Governance

目标：

> 让 Deck Master 具备交付级质量控制能力。

核心能力：

- Draft Gate 强化。
- Evidence Gate。
- Render Gate。
- Delivery Gate。
- Confidentiality Gate。
- Brand Gate。
- Client Context Conflict Gate。
- Override Governance。
- Delivery Package Validation。
- Final Version Lineage。

阶段价值：

- 控制 AI 输出风险。
- 降低客户交付风险。
- 形成团队统一交付标准。

### 阶段 5：Team / Enterprise Solution Deck Factory

目标：

> 从专家个人本地工作流扩展到团队级方案生产系统。

核心能力：

- 多用户。
- 角色权限。
- 审批流。
- workspace sharing。
- asset ownership。
- team quality dashboard。
- opportunity-level deck history。
- CRM / 文档库 / 会议系统集成。
- business outcome feedback。
- team benchmark。
- reusable solution package。

阶段价值：

- 新人可以复用专家经验。
- 团队交付质量更一致。
- 售前材料生产效率提升。
- 方案团队形成可持续生产能力。

## 8. 产品形态

### 8.1 Expert Local Mode

当前阶段优先形态。

适合：

- 当前用户本人。
- 独立顾问。
- AI 解决方案架构师。
- 小型咨询团队。
- 高隐私客户材料。
- 本地文件资产多的场景。

形态：

- Agent 入口。
- CLI。
- local workspace。
- localhost Web UI。
- 本地 PPT Library。
- 本地质量报告。
- 本地导出。

### 8.2 Team Workspace Mode

中期形态。

适合：

- 售前团队。
- 咨询团队。
- 解决方案团队。
- Agent 交付团队。
- 行业方案团队。

能力：

- 共享 workspace。
- 团队历史资产。
- 审批和备注。
- team-level archetype。
- 质量看板。
- 页面复用统计。
- 输出版本管理。

### 8.3 Enterprise Proposal Intelligence Mode

远期形态。

适合：

- 大型软件公司。
- 咨询公司。
- SI。
- Martech / AI / CRM / CDP 服务商。
- 多行业售前组织。

能力：

- CRM / 飞书 / Google Drive / SharePoint / Notion / 知识库集成。
- 商机级项目空间。
- 方案资产权限。
- 合规审查。
- 品牌规范。
- 投标材料。
- 成交反馈。
- 多团队共享。

本阶段不进入近期实现。

## 9. 产品边界

Deck Master 专注专业客户方案 Deck 的论点、证据、历史资产复用、质量门禁和交付审查。

不追求成为：

- 通用 AI Presentation 生成器。
- 通用 PPT 编辑器。
- 模板市场。
- CRM。
- 通用知识库。
- 长期笔记系统。
- 全功能项目管理系统。
- 单纯 Agent 编排平台。

近期边界：

- 不做本地桌面 App。
- 不做完整 Web 工作台。
- 不做实时飞书拉取。
- 不做 OpenViking 在线强依赖。
- 不做 reference PPT 自动视觉提取。
- 不做多 Build Skill 调度平台。

## 10. 对 Run OS MVP 的约束

终局蓝图对下一轮 MVP 的约束：

1. `Run OS MVP` 是阶段 1 的可用闭环，不承担阶段 2 到阶段 5 的全部能力。
2. 本轮优先证明从本地资料到可审查 Deck run 的稳定性。
3. Runtime、typed events、`next_step`、坏 JSON 防覆盖要先于复杂 UI 和 Build Skill 自动执行。
4. Workspace Foundation 要被 Planner 和 Draft Gate 真实读取，不能只创建目录。
5. Planner 要开始引入 `decision_intent`、`argument_chain`、`evidence_policy` 和 `customer_specificity_level`。
6. Sourcing 决策要输出可解释 `score_breakdown`，即使部分字段首版使用规则推断。
7. Web UI 首轮以审查和审批为主，复杂操作放到增强层。
8. Export 必须读取 Quality Gate，不能只按人工批准过滤。
9. Feedback 首轮只记录 approved / rejected / delivered 基础信号，学习闭环后续增强。

## 11. 下一步

后续执行顺序：

1. 用本文档作为顶层产品蓝图。
2. 修订 `Run OS MVP` 实施方案，压缩为 P0 可审查闭环。
3. 将 `Claim-Evidence Graph`、`Consulting Judgment Layer`、`Delivery Outcome` 标为阶段 2/3/4 的核心演进对象。
4. 从 Package 0 开始做迁移清单，先统一 Runtime、Events、`next_step` 和状态契约。
