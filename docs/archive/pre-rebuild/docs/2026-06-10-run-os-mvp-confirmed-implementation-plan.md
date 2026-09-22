# Deck Master Run OS MVP 确认版实现方案

日期：2026-06-10
状态：确认版 v0.2
来源：Office Hour、CEO Review、DevEx Review、Engineering Review、Design Review、终局蓝图评审、Run OS MVP 方案评审
适用范围：Deck Master 下一轮产品化实现

## 1. 文档定位

这份文档是 Deck Master 下一轮实现的主方案。它只定义阶段 1 的 `Run OS Core` 落地范围。

Deck Master 的长期产品方向见：

- `docs/2026-06-11-deck-master-endgame-blueprint.md`

本文档与终局蓝图的关系：

- 终局蓝图定义长期 North Star、价值飞轮和五阶段路线。
- 本文档定义下一轮 MVP 的可执行范围、数据契约、实现顺序和验收标准。
- 本轮 MVP 目标是跑通可审查 Deck run，不承担 Asset Intelligence、团队协同和完整反馈学习。

它合并以下评审结论：

- `docs/2026-06-10-office-hour-run-os.md`
- `docs/2026-06-10-planning-review-log.md`
- `docs/2026-06-10-web-ui-design-spec.md`
- `docs/2026-06-10-guided-conversation-runtime.md`
- `docs/2026-06-10-built-in-quality-gate.md`
- `docs/deck-master-vnext-workspace-quality-gate-plan.md`
- `<local-strategy-note>`
- `<local-strategy-review>`

后续实现优先按本文档推进。旧文档保留为背景和决策记录。

## 2. 产品目标

Deck Master 的 Run OS MVP 目标：

> 服务售前解决方案架构师和专业顾问，把会议转写、客户材料、历史方案、个人判断和 AI 引导式对话，转成可审查、可追踪、带质量门禁的客户 Solution Deck 草案。

硬指标：

- 从“方案思路基本确认”到“第一版可审查草案”，目标从约 12 小时压到约 2 小时。
- 首版聚焦会后客户 Solution Deck 草案。
- 首版必须保留人工判断和最终交付前审查。

第一用户：

- 售前解决方案架构师。
- 专业顾问。
- 高质量 Solution Deck 创作者。

第一场景：

- 一场客户会议结束后，用户把会议转写、客户资料、历史方案摘要和口头判断交给 Agent。
- Deck Master 创建一次 run，生成 brief、claim map、page tasks、来源决策、可审查 preview 和 Draft Gate 报告。
- 用户在 localhost Web UI 里看页面、审来源、看证据缺口、处理质量风险、批准页面。

本轮 MVP North Star：

> 从本地资料或 brief 出发，稳定生成一个可恢复、可审查、带来源决策和 Draft Gate 的 Deck Run；用户可以在 Web UI 中完成页面审查，并导出通过质量门禁的 approved queue。

本轮优先级：

- 优先做硬 Runtime：typed events、`next_step`、坏 JSON 防覆盖、状态恢复。
- 优先做可解释页面任务：`deck_brief.json`、`claim_map.json`、分层 `page_tasks.json`、`sourcing_plan.json`。
- 优先做质量可控：Draft Gate 默认运行，Export 读取 P0/P1 阻断。
- Web UI 首版优先支持审查、审批和备注。
- Build Skill 首轮优先定义 task package、状态和 artifact handback contract；自动执行进入增强层。

## 3. 应用形态

Deck Master 的应用形态：

> 面向 Agent 的专业 Deck 生产运行时，通过 CLI 管理流程，通过 localhost Web UI 提供审查，通过 Deck Workspace 固化视觉、结构和质量标准。

四层关系：

| 层级 | 形态 | 职责 |
|---|---|---|
| Agent 入口 | Codex / Claude Code / OpenCode 等对话环境 | 需求澄清、方案讨论、run 调度、错误解释、下一步建议 |
| CLI / Runtime | `scripts/deck_master.py` 与共享运行时 | 创建 workspace、创建 run、续跑、状态恢复、工具调用、质量门禁、导出 |
| localhost Web UI | 任务唤起式 Run 审查面板 | 页面预览、来源审查、质量风险查看、页面操作、审批和备注 |
| Deck Workspace | 用户指定文件夹 | 视觉规范、页型资产、质量标准、来源指针、历史 run、导出物 |

首版不做：

- 本地桌面应用。
- 完整 Web 工作台。
- 长期知识管理系统。
- 实时飞书拉取。
- OpenViking 在线强依赖。
- 移动端主路径。
- 多 Build Skill 并行调度平台。

## 4. 当前基线与处理策略

当前 `main` 上已有一批可运行能力：

- brief 到 preview 的 autoplan 链路。
- 本地 context manifest。
- 引导式 conversation session。
- deck brief。
- claim map。
- 分层 `page_tasks.json`。
- PPT Library fixture / fake 回退。
- sourcing decision。
- generation task package。
- preview manifest。
- Web UI 预览和审批回写。
- approved queue 导出。
- slide win-rate 本地反馈 MVP。
- Draft / Render / Delivery Quality Gate MVP。

处理策略：

- 与确认版架构一致的能力保留并硬化。
- 与确认版架构冲突的能力重构到共享 runtime pipeline。
- 临时 UI 只作为 spike 参考，后续按《Web UI Design Spec》重做信息架构和语言系统。
- 旧接口尽量保留兼容入口，但内部调用统一 runtime。

## 5. 运行时状态模型

每次 Deck 任务形成一个 run。

推荐目录：

```text
runs/<run_id>/
  request.json
  events.jsonl
  context_manifest.json
  conversation_session.json
  deck_brief.json
  claim_map.json
  narrative_plan.json
  page_tasks.json
  library_results/
  sourcing_plan.json
  generation_tasks/
  preview_manifest.json
  quality_reports/
  approved_queue.json
```

核心产物职责：

| 文件 | 职责 |
|---|---|
| `request.json` | 记录用户需求、行业、受众、页数、边界和风格偏好 |
| `events.jsonl` | 记录 typed events，支持审计、恢复和 Agent 解释 |
| `context_manifest.json` | 记录本次引用的本地资料、摘要、hash 和来源路径 |
| `conversation_session.json` | 记录关键追问、用户确认点、已锁定判断和待补缺口 |
| `deck_brief.json` | 稳定描述 Deck 目标、受众、业务目标、核心观点和边界 |
| `claim_map.json` | 记录要证明的核心论点、支撑逻辑、证据需求和风险 |
| `page_tasks.json` | 记录页面任务，采用 `planning / retrieval / sourcing / generation` 分层 |
| `library_results/` | 保存 PPT Library 结果和每页候选 |
| `sourcing_plan.json` | 保存每页 reuse / adapt / generate / manual_placeholder 决策 |
| `generation_tasks/` | 保存 Build Skill 或生成工具的页面任务包 |
| `preview_manifest.json` | Web UI 使用的页面、来源、质量、审批和备注状态 |
| `quality_reports/` | 保存 Draft / Render / Delivery Gate 结果 |
| `approved_queue.json` | 只保存批准进入后续组装或导出的页面 |

`page_tasks.json` 必须保持分层，避免多个阶段重复写同一批平铺字段。

推荐页面任务结构：

```json
{
  "beat_id": "beat_004",
  "order": 4,
  "planning": {
    "page_title": "库存可视化目标架构",
    "role": "architecture",
    "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
    "decision_intent": "让客户认可库存可视化直接服务履约效率，避免被理解为普通报表项目。",
    "argument_chain": {
      "why_now": "全渠道履约复杂度上升，库存状态延迟会直接影响订单承诺。",
      "business_tension": "前台渠道承诺越来越实时，后台库存和配送状态仍分散。",
      "solution_logic": "通过统一库存状态、履约状态和配送节点，让运营团队能按异常优先级调度。",
      "proof_needed": "需要客户现有库存可视化缺口、履约指标或最后一公里配送案例。"
    },
    "content_goal": "说明目标架构和关键数据流。",
    "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
    "evidence_policy": {
      "required": true,
      "evidence_types": ["customer_current_state", "product_screenshot", "case_metric"],
      "allow_ai_generated_without_evidence": false
    },
    "customer_specificity_level": "evidence_locked",
    "visual_need": "分层架构图",
    "density": "high",
    "preferred_archetype": "architecture",
    "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
    "quality_requirements": ["必须有主观点", "必须说明数据如何服务决策"],
    "gaps": []
  },
  "retrieval": {
    "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
    "constraints": ["avoid generic platform overview"]
  },
  "sourcing": {
    "decision": null,
    "selected_candidate": null,
    "alternatives": [],
    "risk_flags": [],
    "confidence": null
  },
  "generation": {
    "generation_brief": "生成一页库存可视化目标架构页，强调全渠道库存、履约状态和最后一公里配送。",
    "reference_slide": null,
    "task_path": null,
    "status": "pending"
  }
}
```

## 6. 状态恢复与事件模型

Runtime 必须有 canonical `next_step` 解析器。

基本恢复规则：

| 当前状态 | 下一步 |
|---|---|
| `request.json` 缺失 | 创建或恢复 request |
| `deck_brief.json` 缺失 | 编译 brief |
| `claim_map.json` 缺失 | 编译 claim map |
| `narrative_plan.json` 缺失 | 运行 planner |
| `library_results/selection.json` 缺失 | 检索 PPT Library 或 fixture |
| `sourcing_plan.json` 缺失 | 运行 sourcing decision |
| `generation_tasks/index.json` 缺失 | 创建生成任务 |
| `preview_manifest.json` 缺失 | 构建 preview |
| `quality_reports/draft_gate.json` 缺失 | 运行 Draft Gate |
| 存在 P0/P1 或 `rework_required` | 标记 quality blocked |
| 存在待审页面 | 打开 Web UI 审查 |
| 有批准页 | 可以导出 approved queue |

坏 JSON、缺文件、人工审批冲突、工具失败都必须写入事件，不能静默覆盖。

事件类型：

| 类型 | 用途 |
|---|---|
| `run_created` | 创建 run |
| `step_started` | 步骤开始 |
| `step_completed` | 步骤完成 |
| `tool_call` | 外部工具调用 |
| `tool_result` | 外部工具返回 |
| `decision` | planner、sourcing、quality、export 决策 |
| `manual_action` | 用户审批、拒绝、备注、锁定、转生成 |
| `warning` | 可恢复问题 |
| `error` | 阻断问题 |

事件最小字段：

- `timestamp`
- `event_type`
- `run_id`
- `step`
- `message`
- `refs`
- `severity`

## 7. Deck Workspace Foundation

本期做完整 Workspace Foundation。

标准目录：

```text
deck-workspace/
  workspace_manifest.json
  AGENTS.md
  visual-system/
    design_spec.md
    spec_lock.md
    layout_blueprint.md
    template/
      page_archetypes.md
  structure-assets/
    page_archetypes.md
  quality/
    quality_policy.md
    scoring_rubric.md
    failure_modes.md
    repair_playbooks.md
  sources/
  projects/
  runs/
  exports/
  reference-analysis/
```

首版命令：

```bash
python3 scripts/deck_master.py init-workspace \
  --workspace /path/to/deck-workspace \
  --name "MarketingForce PPT Workshop"
```

支持注册已有工作坊：

```bash
python3 scripts/deck_master.py register-workspace \
  --workspace /path/to/existing-workshop \
  --name "MarketingForce PPT Workshop"
```

reference PPT 规则：

- 只登记路径、文件名、大小、修改时间和备注。
- 可以引用已有 `reference-analysis/` 产物。
- 本期不自动抽取新 reference PPT 的颜色、字体、布局和母版。

Workspace 注册性能边界：

- 只注册标准文件、来源指针和 include / exclude 规则。
- SVG、PPTX、PNG、review grids、历史 exports 作为 examples 或 artifacts 引用。
- 不深度摄取所有生成物。

## 8. Context 与 Guided Conversation

首版只接本地或已导出资料。

支持输入：

- `--context-file`
- 本地会议转写。
- 客户材料摘要。
- 历史方案说明。
- 用户口头判断转写。

核心命令：

```bash
python3 scripts/deck_master.py start-conversation \
  --workspace /path/to/deck-workspace \
  --context-file examples/context/retail_meeting_transcript.txt \
  --industry retail \
  --run-id retail-conversation

python3 scripts/deck_master.py build-brief --run-id retail-conversation

python3 scripts/deck_master.py build-claim-map --run-id retail-conversation
```

首版不做：

- 实时飞书拉取。
- 长期思考库。
- OpenViking 在线强依赖。
- 自动写回外部知识库。

## 9. Planner 与页面任务

Planner 必须读取 Workspace 标准。

输入：

- `deck_brief.json`
- `claim_map.json`
- Workspace visual standards。
- Workspace page archetypes。
- Workspace density standards。
- 用户页数目标。
- 受众、行业、来源限制。

输出：

- `narrative_plan.json`
- `page_tasks.json`

页数策略：

| 页数目标 | 策略 |
|---|---|
| `auto` | 默认 12 到 18 页 |
| `15` | 偏高管摘要和紧凑方案 |
| `30` | 完整 Solution Deck |
| `60+` | 拆章节，强化 section handoff |

缺客户事实、业务目标、现状痛点、产品范围、案例证据时，必须写入 `gaps[]`。

Planner 要把页面设计成“论点、论证、论据”的承载单元，避免泛泛生成大字报式页面。

本轮新增四个规划字段：

| 字段 | 用途 |
|---|---|
| `decision_intent` | 描述这页要推动客户形成什么判断 |
| `argument_chain` | 描述为什么现在要讲、业务矛盾是什么、方案如何证明、还缺什么证据 |
| `evidence_policy` | 明确是否必须有客户证据、产品截图、案例指标或外部依据 |
| `customer_specificity_level` | 区分通用方法论、行业化页面、客户事实页和必须锁定证据页 |

`customer_specificity_level` 推荐值：

| 值 | 含义 |
|---|---|
| `generic_method` | 通用方法论页，可复用历史框架 |
| `industry_contextualized` | 行业化页面，需要行业语境 |
| `customer_specific` | 客户事实页，需要客户上下文 |
| `evidence_locked` | 必须引用明确证据，缺证据时进入 `manual_placeholder` |

## 10. PPT Library 与 Sourcing Decision

Deck Master 作为调用者和决策者。PPT Library 专注搜索、选择和返回候选页。

主调用形态：

```bash
ppt-lib select-slides \
  --plan <run>/narrative_plan.json \
  --brief <run>/request.json \
  --ranking business \
  --max-per-role 5 \
  --output <run>/library_results/selection.json
```

备用调用：

```bash
ppt-lib search "<reuse_query>" \
  --top-k 8 \
  --ranking business \
  --output json
```

解析字段：

- `slide_id`
- `canonical_slide_id`
- `title`
- `text_summary`
- `source_file`
- `page_number`
- `screenshot_path`
- `confidence`
- `win_rate`
- `reuse_count`

失败策略：

| 情况 | 行为 |
|---|---|
| 无结果 | 写空结果并继续 |
| CLI 缺失 | 写 tool unavailable，走 fixture 或 generate fallback |
| JSON 错误 | 写 parse error，继续生成可审查草案 |
| 截图缺失 | 保留候选，增加 risk flag |
| embedding 不可用 | 写 dependency failure，继续 |

Sourcing 决策类型：

- `reuse`
- `adapt`
- `generate`
- `manual_placeholder`

初始评分权重：

| 维度 | 权重 |
|---|---:|
| 语义匹配 | 0.30 |
| 叙事角色匹配 | 0.18 |
| 页型匹配 | 0.10 |
| 截图可用 | 0.10 |
| 来源可信度 | 0.08 |
| 胜率 | 0.10 |
| 复用次数 | 0.04 |
| 客户语境冲突 | -0.12 |
| 视觉连续性 | 0.06 |
| 证据充分性 | 0.06 |

初始阈值：

| 决策 | 条件 |
|---|---|
| `reuse` | score >= 0.78，截图可用，无高客户语境冲突 |
| `adapt` | score >= 0.58，且页型匹配或叙事角色匹配 >= 0.70 |
| `generate` | score < 0.58，且没有必需证据缺口 |
| `manual_placeholder` | 缺必需客户事实、截图、数据或案例证据 |

决策输出必须包含：

- `beat_id`
- `decision`
- `decision_reason`
- `score`
- `score_breakdown`
- `selected_candidate`
- `alternatives`
- `risk_flags`
- `confidence`
- `tool_refs`

`score_breakdown` 首版允许部分字段使用规则推断，但字段结构必须稳定：

```json
{
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

`manual_placeholder` 判断优先读取 `planning.evidence_policy`。当 `allow_ai_generated_without_evidence` 为 `false` 且缺少必需证据时，不能自动走 `generate`。

## 11. Build Skill 交接

本轮 P0 先定义 Build Skill 任务包、状态和 artifact handback contract。

自动执行一个默认 Build Skill 进入 P1 增强，不作为 P0 阻断项。

Build Skill 来源：

- Workspace 默认配置。
- run 可覆盖。

P0 边界：

- 定义 Build Skill registry。
- 定义 artifact handback contract。
- 为 `generate` 和 `adapt` 页面创建 generation task package。
- 支持 fake executor 或手动 handback fixture。
- 任务状态写回 run。
- 失败写 typed events，并在 Web UI 可见。
- 不做多工具调度平台。
- 不把自动执行作为 P0 必须通过项。
- 不做并行页面生成。
- 不做复杂重试系统。

Generation task package：

```text
generation_tasks/<beat_id>.json
```

任务字段：

- `beat_id`
- `task_id`
- `page_title`
- `role`
- `core_claim`
- `generation_brief`
- `reference_slide`
- `preferred_archetype`
- `visual_need`
- `evidence_need`
- `style_constraints`
- `workspace_refs`
- `quality_requirements`

Artifact handback 最小字段：

- `task_id`
- `beat_id`
- `artifact_type`
- `artifact_path`
- `preview_path`
- `source_decision`
- `build_tool`
- `status`
- `created_at`
- `errors`

P1 自动执行策略：

- `autoplan --auto-through preview` 可以顺序跑到 preview。
- 长步骤需要状态输出和 no-wait 选项。
- Web UI 可以启动任务并轮询状态。
- 每一步写 typed events。

## 12. Built-in Quality Gate

Quality Gate 是 Deck Master 内建子系统。

三段门禁：

| Gate | 触发点 | 本期策略 |
|---|---|---|
| Draft Gate | `narrative_plan.json` 和 `page_tasks.json` 存在后 | 默认硬链路 |
| Render Gate | HTML / SVG / PPTX 预览资产存在后 | 显式 artifact check |
| Delivery Gate | export queue 或最终 PPTX 存在后 | 显式 artifact check |

Draft Gate 检查：

- Deck 是否有清晰受众和业务目标。
- 每页是否有明确页面职责。
- 每页是否有核心主张。
- 页面顺序是否有叙事推进。
- 证据需求是否明确。
- 缺失事实是否标记为 gaps。
- 长 Deck 是否有章节交接。
- 页面密度是否匹配页面角色。

Scorecard：

- Narrative Integrity。
- Page Job Clarity。
- Information Density。
- Evidence And Specificity。
- Screenshot And Asset Integration。
- Layout Variety。
- Consulting-Style Expression。
- Visual Readiness。
- Delivery Readiness。

状态值：

- `pass`
- `conditional_pass`
- `rework_required`

阻断规则：

- 任意 P0/P1 finding 阻断交付。
- `rework_required` 阻断交付。
- Web UI 必须显示 run 级质量状态和页面级 findings。

## 13. Web UI 实现边界

Web UI 以 `docs/2026-06-10-web-ui-design-spec.md` 为唯一设计依据。

首版定位：

- 任务唤起式 Run 审查面板。
- 桌面浏览器优先。
- 默认进入第一页。
- 页面列表按 Deck 页码排序。
- 视觉方向为专业咨询审查台。

P0 必须实现：

- 中文 / 英文完整语言包。
- 跟随浏览器语言。
- 显式语言切换。
- 用户语言偏好本地保存。
- 顶部 run 状态条。
- 左侧页面列表和筛选。
- 中央页面预览。
- 右侧页面审查面板。
- 底部状态抽屉。
- Draft Gate 阻断显示。
- Build Skill 状态显示。
- 页面级审批和备注。
- 候选来源只读展示。
- approved-only export 状态展示。

P1 增强操作：

- 替换来源。
- 转生成页。
- 锁定历史页。
- 触发单页生成任务。
- 显式 override P0/P1 findings。

首版审批状态：

- `needs_review`
- `approved`
- `rejected`

页面操作规则：

- 替换来源只能从已有候选中选择。
- 转生成页会更新 sourcing decision，并刷新 generation task。
- 锁定历史页会阻止后续自动决策覆盖该页来源。
- 所有操作写入事件日志。
- 页面操作不能绕过 Draft Gate 阻断。

移动端：

- 不进入本期验收。
- CSS 避免明显破版即可。

## 14. Export 与 Feedback

导出规则：

- 默认只导出 `approved` 页面。
- P0/P1 页面不能进入最终 handback，除非存在显式 override 记录。
- `manual_placeholder` 可以作为任务提醒进入内部队列，不能作为最终交付页。

反馈首版：

- 记录 approved / rejected outcomes。
- 保留现有 slide win-rate 本地反馈 MVP。
- 本期不做全量反馈学习系统。
- 后续等 PPT Library 稳定 canonical slide id 后，再考虑写回 metadata。

## 15. 实现包与顺序

本轮从“全链路产品化”收敛为“Run OS 可审查闭环”。

### 15.1 P0 必须闭环

| 优先级 | 实现包 | 目标 | 依赖 | 验收 |
|---:|---|---|---|---|
| P0-0 | Spike 对齐与迁移保护 | 标记现有能力保留、重构、延后 | 无 | 形成迁移清单，不误删可用能力 |
| P0-1 | Runtime Contract Hardening | 统一 run state、typed events、`next_step`、坏 JSON 处理 | P0-0 | CLI 和 Web UI 都基于同一个 `next_step` |
| P0-2 | Workspace Foundation | 创建和注册完整 Deck Workspace，并让 Planner / Gate 真实读取 | P0-1 | `page_tasks.json` 写入 `workspace_refs`、`style_constraints`、`quality_requirements` |
| P0-3 | Context / Brief / Claim Map | 本地材料结构化，形成稳定 deck brief 和 claim map | P0-1 | 同一输入可重复生成稳定结果 |
| P0-4 | Workspace-aware Planner | 生成 narrative plan 和分层 page tasks | P0-2、P0-3 | 每页有 `core_claim`、`decision_intent`、`argument_chain`、`evidence_policy`、`gaps` |
| P0-5 | Library + Sourcing v1 | 每页稳定输出 reuse / adapt / generate / manual_placeholder | P0-4 | 有 `score_breakdown`、`decision_reason`、`risk_flags`、`selected_candidate` |
| P0-6 | Draft Gate + Review UI | Web UI 展示页面、来源、风险、质量 findings，支持 approve / reject / note | P0-1、P0-5 | Draft Gate P0/P1 能阻断 export |
| P0-7 | Export + Regression | approved-only + quality-aware export，跑零售和达能样本 | P0-6 | 真实样本能到可审查草案 |

### 15.2 P1 产品化增强

| 能力 | 说明 |
|---|---|
| Build Skill 自动执行 | 在 P0 task package 和 handback contract 稳定后，执行一个默认 Build Skill |
| Web UI Action UI | 替换来源、转生成页、锁定历史页、触发单页生成 |
| Render / Delivery Gate fixture | 在有明确 artifact 后运行显式检查 |
| 完整 I18n 验收 | 检查中文 / 英文语言包完整性和同屏一致性 |
| override 机制 | P0/P1 finding 需要人工 override 时写入事件和原因 |
| 真实样本回归扩充 | 达能、ECCO KOS、零售数字化、企业级 AIGC 等样本 |

### 15.3 P2 后续能力

| 能力 | 说明 |
|---|---|
| 多 Build Skill registry | 支持不同页面生产能力和工具选择 |
| Asset Intelligence | 历史页 claim / evidence / archetype / outcome 标注 |
| Feedback Learning | 从 approved / rejected / delivered 升级到决策学习 |
| reference PPT 视觉抽取 | 从 reference deck 自动提取视觉系统 |
| 团队工作区 | 共享 workspace、权限、审批流和团队质量看板 |

## 16. 测试矩阵

必须新增或补齐以下测试：

| 测试类别 | 核心用例 |
|---|---|
| Workspace | 新建 workspace、注册已有工作坊、manifest 校验、include / exclude |
| Runtime | 创建 run、恢复 run、坏 JSON 阻断、`next_step` 解析 |
| Events | typed events schema、追加事件、错误事件、人工操作事件 |
| Conversation | context manifest、conversation session、deck brief、claim map |
| Planner | workspace archetype 读取、fallback 默认模板、页数策略、gaps |
| PPT Library Client | 正常 JSON、空结果、坏 JSON、截图缺失、CLI 不可用 |
| Sourcing | reuse、adapt、generate、manual_placeholder、胜率 tie-break |
| Build Skill | task package、registry、fake executor、artifact handback、失败状态 |
| Quality Gate | Draft Gate hard path、Render artifact-only、Delivery artifact-only |
| Preview Manifest | 旧 manifest 兼容、扩展字段、审批状态、页面操作 |
| Web UI API | deck API、review action、notes、quality findings、候选展示；candidate replacement / generation conversion / lock 作为 P1 |
| I18n | 中文 / 英文语言包完整性、语言切换、无同屏混排 |
| Export | approved-only、P0/P1 阻断、manual placeholder 内部任务化 |
| End-to-end | retail fixture 从 context 到 preview 和 Draft Gate |
| Real regression | 达能 AI 消费者样本跑到可审查草案 |

基础验证命令：

```bash
uvx pytest
```

## 17. 验收场景

### 17.1 零售数字化 fixture

输入：

- 全渠道。
- 库存可视化。
- 最后一公里配送。

期望：

- 生成 deck brief。
- 生成 claim map。
- 生成 10 页以上 page tasks。
- 包含架构、案例、价值、路线图等页面。
- sourcing 有 reuse / adapt / generate / manual_placeholder 决策。
- Draft Gate 输出质量报告。
- Web UI 能审查来源、风险和审批状态。

### 17.2 达能 AI 消费者真实回归

输入：

- 会议转写。
- 客户材料。
- 历史方案摘要。
- 用户口头判断。

期望：

- 2 小时内产出可审查草案。
- 页面主线可用。
- 证据缺口明确。
- 历史页复用可解释。
- Draft Gate 能指出内容和证据风险。
- 用户可以继续人工打磨。

### 17.3 外部工具失败

输入：

- PPT Library 不可用或 embedding 服务失败。

期望：

- run 不中断到不可恢复状态。
- 事件日志记录失败。
- sourcing 回退 generate 或 manual_placeholder。
- Web UI 显示风险和下一步。

### 17.4 Generation task handback 失败

输入：

- 某页 generation task 缺少 handback artifact，或 fake executor 返回失败。

期望：

- 对应页显示 failed 状态。
- 其他页面仍可 preview。
- 事件日志记录失败。
- Agent 可以解释下一步。

### 17.5 审批导出

输入：

- 用户批准部分页面，拒绝部分页面。

期望：

- `approved_queue.json` 只包含 approved 页面。
- P0/P1 页面不能静默进入导出队列。
- rejected 页面保留审查记录和备注。

## 18. 风险与控制

| 风险 | 控制 |
|---|---|
| Run OS 过早平台化 | 本期只围绕会后 Solution Deck 草案，不做多项目后台 |
| Web UI 变重 | 只做任务唤起式审查面板，不做完整工作台 |
| Workspace 范围过大 | 完整文件结构先落地，reference PPT 自动分析延后 |
| Quality Gate 空壳化 | Draft Gate 先进入硬链路，Render / Delivery 只在有 artifact 时运行 |
| Build Skill 黑盒 | P0 先固定 task package 和 artifact handback，自动执行进入 P1 |
| Sourcing 不稳定 | 初始权重和阈值固定，测试覆盖四类决策 |
| 文案混乱 | 中文 / 英文语言包完整覆盖，用户可见文案禁止硬编码 |
| Agent 和 Web UI 边界模糊 | Agent 负责讨论和调度，Web UI 负责可视化审查 |

## 19. 非目标

本期不做：

- 本地桌面应用。
- 完整 Web 工作台。
- 长期思考库。
- 实时飞书拉取。
- OpenViking 在线检索强依赖。
- 从新 reference PPT 自动提取完整视觉系统。
- 深度摄取 workspace 内全部历史产物。
- 把 Build Skill 自动执行作为 P0 阻断项。
- 多 Build Skill 调度平台。
- 并行页面生成。
- 复杂重试系统。
- 移动端主路径。
- 高保真视觉稿。
- 全量反馈学习系统。

## 20. 最终交付标准

本期完成后，Deck Master 应达到：

- 用户可以创建或注册完整 Deck Workspace。
- 用户可以从本地资料和引导式对话启动一次 run。
- Deck Master 可以生成 deck brief、claim map、narrative plan 和分层 page tasks。
- Planner 可以读取 workspace 页型、密度和质量标准。
- Deck Master 可以调用 PPT Library 或 fixture 获得历史候选。
- Deck Master 可以给每页做稳定的 reuse / adapt / generate / manual_placeholder 决策。
- Deck Master 可以为生成页创建 generation task package，并定义 artifact handback contract。
- Draft Gate 默认进入硬链路。
- Render / Delivery Gate 可以对显式 artifact 运行，作为 P1 增强验收。
- Web UI 可以按 P0 Design Spec 审查页面、来源、质量和审批。
- 用户可以 approve、reject、add note。
- 导出队列只包含 approved 页面。
- 错误提示能说明问题、可能原因和下一步动作。
- 完整测试矩阵通过。
- 零售 fixture 和达能 AI 消费者样本可跑通。

## 21. 下一步

建议下一步执行顺序：

1. 把 `docs/2026-06-11-deck-master-endgame-blueprint.md` 作为顶层蓝图。
2. 把本文档作为 P0 实现主方案。
3. 按 P0-0 做现有代码迁移清单。
4. 从 P0-1 到 P0-3 开始实现，先保证 Runtime、Workspace、Conversation 的稳定底座。
5. 每个 Package 完成后运行测试并更新文档。
