# Deck Master v1.0 Skill Suite Interaction Spec

日期：2026-06-22
状态：v1.0 前置产品 Spec，供 Skill Suite 重命名、路由、Workspace 初始化、Setup/Upgrade、连续 Workflow 迭代使用。
参考对象：GStack skill suite、Deck Master v0.9.12 Skill Suite Runtime Foundation、Deck Master Skill System Product Architecture、当前本机 v0.9.13 安装版。

## Summary

本轮目标是把 Deck Master 的 skill 体系从“能力包列表”升级为“用户输入驱动的专业 Deck 生产系统”。

当前 Deck Master 已具备核心生产链路：run state、planning、sourcing、generation session、render、quality gate、final readiness、Review Cockpit、export。问题集中在交互层和产品定位层：

- 用户给出原始材料、deep research 报告、已有 brief、历史 PPT、待审 PPTX、已有 run、安装/升级请求时，应该触发哪个 skill 还不够清楚。
- `deck-planner`、`ppt-library`、`ppt-deck-pro-max`、`ppt-quality-gate` 等能力存在重叠感，原因是 skill 名称和触发条件没有围绕用户输入重新设计。
- Workspace 初始化、项目目录、参考素材目录、项目禁词、run 绑定等动作尚未形成独立入口。
- Setup / Upgrade / Doctor 仍藏在 `deck-master` 大入口里，没有形成类似 GStack 的明确运维 skill。
- 连续工作流缺少一个类似 GStack `autoplan` 的快速编排入口，用户需要知道太多中间 skill。

v1.0 的设计方向：

- Skill 数量可以增加，前提是每个 skill 有清晰输入、清晰边界、清晰产物、清晰下一步。
- `ppt-*` 历史名称保留为兼容别名和底层能力名，对用户暴露的新入口统一改成 `deck-*` 产品语言。
- Deck Master 顶层入口负责路由和 run state，具体生产动作交给专门 skill。
- Workspace 初始化进入正式 skill 体系，命名为 `deck-init`。
- Setup、Upgrade、Doctor 进入正式 skill 体系，避免安装和生产流程混在一个入口。
- 增加 `deck-autopilot`，用于从材料到可审查产物的连续 workflow。

## GStack Reference Conclusions

本 Spec 参考 GStack 的结构方法，重点吸收以下模式。

| GStack 模式 | 对 Deck Master 的启发 | Deck Master v1.0 设计 |
|---|---|---|
| 多 skill 并存，但每个 skill 的 `Use when` 很具体 | 数量并非核心问题，定位模糊才会造成混乱 | 每个 Deck skill 必须声明输入类型、触发句、禁止触发、产物和下一步 |
| `autoplan` 作为连续审查入口 | 用户不应手动记住全部中间步骤 | 增加 `deck-autopilot`，把 init、brief、planner、sourcing、production、quality、review 串起来 |
| `setup-gbrain` / `gstack-upgrade` 独立存在 | 安装、升级、运行任务是不同心智模型 | 增加 `deck-setup`、`deck-upgrade`、`deck-doctor` |
| `qa` 与 `review` 分开 | 测试执行、问题修复、交付判断需要不同入口 | `deck-quality` 做文件级质量门禁，`deck-review` 做 run 级交付判断 |
| `ship` 有发布前门禁 | 最终交付需要唯一放行口径 | `deck-review` 读取 `final_readiness.json`，client export 必须通过 |
| `context-save` / `context-restore` 解决跨会话恢复 | Deck 生产也需要项目级和 run 级恢复 | `deck-master` 保持 run state owner，`deck-init` 写项目索引，`deck-review` 负责恢复交付状态 |
| skill 调工具，工具写结构化产物 | Agent 文字说明不能替代机器可读状态 | 每个 Deck skill 输出必须进入 run artifact、Workspace index 或 release manifest |
| Skill docs 加上前置检查和退出门槛 | 入口可用性需要自动判断 | 每个 Deck skill 需要 `First checks`、`Exit artifacts`、`Do not use when` |

## Product Target

Deck Master v1.0 的目标用户是非技术背景的解决方案架构师、售前负责人、方案顾问和使用 AI Coding / AI Agent 生产交付物的个人开发者。

v1.0 的目标场景：

1. 用户给出客户原始材料、会议纪要、deep research 报告、历史方案、截图、参考 PPT。
2. Deck Master 初始化 Workspace，登记材料，建立项目边界和禁词。
3. Deck Master 生成 brief、claim map、叙事结构、页面任务和素材需求。
4. 系统判断每页该复用、改写、生成、补证据或人工处理。
5. 页面生产结果回写 run。
6. render 产出 HTML / PDF / PNG / PPTX 等交付物。
7. quality gate 扫最终文件和客户可见内容。
8. review 统一判断是否可交付，并生成返修队列。
9. export 只读取最终 readiness，避免绕过质量门禁。
10. 项目反馈沉淀到 Workspace 和素材库，提升下一次生产质量。

v1.0 成功标准：

- 用户无需理解底层 `ppt-*` 能力来源，也能知道该从哪个 `deck-*` 入口开始。
- 用户给出的输入越明确，系统路由越精确。
- 一条连续 workflow 能从原始材料走到可审查产物。
- 最终交付有硬门禁，内部策划语言、占位语、未完成标记不能进入客户 PPT。
- 安装、升级、修复、生产、质检、交付各有独立入口。

## Skill Naming Strategy

### Public Product Names

对用户暴露的 v1.0 主入口统一使用 `deck-*`：

| v1.0 Skill | 用户理解 | 主要问题 |
|---|---|---|
| `deck-master` | 总控台 | 当前项目 / run 卡在哪里，下一步做什么 |
| `deck-setup` | 本机安装和首次配置 | 本机 Deck Master 能不能正常运行 |
| `deck-upgrade` | 升级与回滚 | 当前安装版如何更新、失败如何恢复 |
| `deck-doctor` | 诊断修复 | 安装、suite、workspace、preview 服务哪里坏了 |
| `deck-init` | 项目 Workspace 初始化 | 这次客户项目的目录、参考资料、禁词、run 绑定如何建立 |
| `deck-brief` | 材料理解入口 | 原始材料如何变成可用 brief 和证据索引 |
| `deck-planner` | 方案结构规划 | 这套 Deck 怎么讲、分几章、每页做什么 |
| `deck-sourcing` | 素材决策 | 哪些页复用、改写、新做、补证据 |
| `deck-producer` | 页面生产 | 页面内容、视觉任务、generation result 如何产出 |
| `deck-renderer` | 构建渲染 | HTML / PDF / PNG / PPTX 等产物如何生成 |
| `deck-quality` | 文件级质量门禁 | 最终文件有没有客户可见风险、缺页、坏图、占位语 |
| `deck-review` | 交付审查 | 这个 run 是否可以交付、如何返修、能否 export |
| `deck-learn` | 反馈沉淀 | 本次项目经验如何沉淀给下一次使用 |
| `deck-autopilot` | 连续工作流 | 从材料到可审查产物的一键推进 |

### Compatibility Names

当前 `ppt-*` skill 不直接删除，先降级为兼容入口和底层能力别名。

| Current Skill | v1.0 Public Name | 兼容策略 |
|---|---|---|
| `ppt-library` | `deck-sourcing` | 保留 `ppt-library`，文档说明其为 asset retrieval capability；用户侧推荐 `deck-sourcing` |
| `ppt-deck-pro-max` | `deck-producer` | 保留 `ppt-deck-pro-max`，文档说明其为 production capability；用户侧推荐 `deck-producer` |
| `ppt-master` | `deck-renderer` | 保留 `ppt-master`，文档说明其为 render engine；用户侧推荐 `deck-renderer` |
| `ppt-quality-gate` | `deck-quality` | 保留 `ppt-quality-gate`，文档说明其为 quality engine；用户侧推荐 `deck-quality` |

兼容期规则：

- v1.0 安装时同时安装新名和旧名。
- 旧名 SKILL.md 可以变成薄 wrapper，指向新名定位和 Deck Master run import 规则。
- Suite status 同时展示 public skill 和 capability alias。
- v1.1 之后再评估是否把旧名从主导航中隐藏。

## Final Skill Table

| Skill | 当前现状 | v1.0 定位 | 典型输入 | 触发条件 | 禁止触发 | 主要产物 | 下一步 |
|---|---|---|---|---|---|---|---|
| `deck-master` | 已存在，承担总控、setup、run、review、export 等大量职责 | 只做总控、路由、run state、next step、Review Cockpit | “继续这个 Deck Master run”“现在卡在哪里”“帮我用 Deck Master 做完整流程” | 用户点名 Deck Master；需要恢复 run；需要判断下一步 | 用户只要求安装修复时交给 `deck-setup` / `deck-doctor`；只给 standalone PPTX 质检时交给 `deck-quality` | `run-state`、`next-step`、route decision、Review Cockpit state | 按状态转给 init / brief / planner / sourcing / producer / renderer / quality / review |
| `deck-setup` | setup 命令藏在 `deck-master` skill | 本机首次安装、skill 链接、workspace 全局配置、preview 服务启动 | “安装 Deck Master”“本机能不能用”“setup 一下” | 无可用安装；suite 未 ready；首次使用 | 项目材料规划；页面生产；质量审查 | setup status、suite status、active workspace、preview health | `deck-init` 或 `deck-master start` |
| `deck-upgrade` | 当前通过 release/install 命令处理，未形成 skill | 版本升级、release tree 切换、回滚、迁移 | “升级 Deck Master”“部署当前版本到本机”“回滚上一版” | 用户要求升级/部署/回滚；当前 release 落后 | 普通项目生产；单 run 修复 | release manifest、capability lock、SHA256SUMS、rollback marker | `deck-doctor` 验证，再回到 `deck-master` |
| `deck-doctor` | doctor 命令存在，入口不独立 | 诊断安装、suite、workspace、run、preview 服务 | “为什么打不开”“skill 失效”“suite 不 ready” | 出现运行异常；preview 失败；link 错误；workspace 丢失 | 用户给出新项目材料；用户要审 PPT 内容 | diagnosis report、repair plan、repair evidence | `deck-setup` / `deck-upgrade` / 对应 run skill |
| `deck-init` | 当前缺失独立入口 | 项目 Workspace 初始化和材料目录建立 | 原始材料文件夹、客户项目目录、deep research 包、参考素材 | 用户给一堆材料准备做 PPT；新客户项目启动；需要建立参考目录 | 已有 run 且只需继续执行；单文件质量审查 | `deck_project.json`、材料清单、目录结构、项目禁词、run binding | `deck-brief` |
| `deck-brief` | `deck-planner` 内含 brief 生成 | 原始材料理解、brief、claim、证据索引 | 会议纪要、客户资料、研究报告、访谈记录、现有 Word/PDF/Markdown | 用户给材料并问“做 PPT 前先理解一下” | 用户已给结构化 brief 且只需规划页面 | `deck_brief.json`、`claim_map.json`、evidence inventory | `deck-planner` |
| `deck-planner` | 已存在，负责 brief、claim map、narrative、page tasks | 叙事结构、章节、页面任务、讲标逻辑 | 已有 brief、deep research 摘要、项目目标、受众 | 用户要求“规划这套 Deck”“出页级结构”“主叙事怎么讲” | 用户只要检索历史页；只要质检现有 PPTX | `narrative_plan.json`、`page_tasks.json`、sourcing intent | `deck-sourcing` |
| `deck-sourcing` | 当前为 `ppt-library` + `decide-sourcing` 的组合 | 决定每页复用、改写、新做、补证据、阻断 | page tasks、历史页库、参考 PPT、证据缺口 | 用户问“哪些页复用”“找类似页面”“这页要新做吗” | 没有 page task 时先回到 planner；只做最终交付审查时交给 review | `library_candidates.json`、`sourcing_plan.json`、reuse/adapt/generate decisions | `deck-producer` 或人工补证据 |
| `deck-producer` | 当前为 `ppt-deck-pro-max` | 页面生产和 generation result 回写 | generation dispatch package、页面任务、视觉要求、素材决策 | 用户要求“生成页面”“把 brief 做成页面”“执行 generation session” | 未完成 sourcing；缺 run/session binding；生产模式没有真实 executor | `deck_generation_result.v2`、page content、speaker notes、visual tasks | `deck-renderer` |
| `deck-renderer` | 当前为 `ppt-master` | build / render 产物生成与登记 | generation result、page assets、render request | 用户要求“导出 HTML/PDF/PPTX/PNG”“生成预览” | 内容未生产完成；production 下缺安全产物 | `build_manifest.json`、HTML/PDF/PNG/PPTX、artifact manifest | `deck-quality` |
| `deck-quality` | 当前为 `ppt-quality-gate` | 文件级门禁和客户可见安全扫描 | PPTX、PDF、HTML、render artifact、quality policy | 用户要求“质量检查”“PPT 能不能给客户看”“扫禁词/占位语” | 用户要 run 级 export 决策时由 `deck-review` 汇总 | quality reports、customer-visible safety report、artifact validation | `deck-review` |
| `deck-review` | 已存在，负责审查与交付 | run 级 readiness、返修队列、client/internal export 判断 | 完整 Deck Master run、quality reports、render artifacts | 用户问“能不能交付”“导出给客户”“列返修清单” | 只给原始材料时先 init/brief；只查安装问题时 doctor | `final_readiness.json`、repair queue、export queue | export 或 repair loop |
| `deck-learn` | 架构文档提到，尚未实现 | 项目反馈、素材复利、benchmark metadata | 成交反馈、客户反馈、页面效果、返修记录 | 用户说“沉淀经验”“记录这页好用”“形成 benchmark” | 当前 run 仍未完成交付；敏感原文未脱敏 | learning pack、library feedback events、benchmark metadata | 下一次 `deck-sourcing` / `deck-brief` |
| `deck-autopilot` | 当前只有 `autoplan` 命令，偏单步 pipeline | 连续 workflow 总入口 | 原始材料 + 目标输出；已有 run + “继续推进” | 用户要求“从这些材料一路做出来”“连续推进不要每步确认” | 关键业务方向不清；缺 workspace 权限；生产 executor 不可用 | workflow plan、phase evidence、checkpoint commits 或 run artifacts | 根据阻断点转给对应 skill |

## Input-Driven Routing

### Routing Matrix

| 用户输入类型 | 首选入口 | 系统动作 | 退出条件 |
|---|---|---|---|
| 一堆客户原始资料、会议纪要、PDF、Word、截图、deep research 报告 | `deck-init` | 建项目 Workspace、登记材料、创建参考目录、初始化禁词和 run binding | 项目目录和材料清单 ready |
| 已有整理好的 brief 或项目背景 | `deck-planner` | 生成叙事结构、章节、页面任务、证据需求 | page tasks ready |
| 用户问“哪些内容复用历史方案，哪些新做” | `deck-sourcing` | 调 PPT Library / 候选页检索 / reuse-adapt-generate 决策 | sourcing plan ready |
| 用户给历史 PPT，希望找相似页面或可复用资产 | `deck-sourcing` | 检索素材库，必要时提示先建立 library index | candidates ready 或 blocked |
| 用户给 generation session / dispatch package | `deck-producer` | 执行页面生产，生成 canonical generation result | generation result imported |
| 用户给已有页面内容，要生成文件 | `deck-renderer` | build / render，登记 artifact | artifact manifest ready |
| 用户给 standalone PPTX / PDF / HTML，问能不能交付 | `deck-quality` | 文件级质量门禁，扫最终可见内容 | quality report ready |
| 用户给 Deck Master run，问能否交付 | `deck-review` | 汇总 render、quality、safety、lineage、readiness | final readiness ready 或 blocked |
| 用户说安装、配置、本机不能用 | `deck-setup` / `deck-doctor` | 检查和修复安装、suite、preview 服务 | setup ready 或 repair blocked |
| 用户说升级、部署当前版本、回滚 | `deck-upgrade` | stage -> verify -> activate，失败恢复 previous | release active |
| 用户说从材料直接推进到可审查版本 | `deck-autopilot` | 自动串联 init、brief、planner、sourcing、producer、renderer、quality、review | ready、awaiting agent、blocked 三选一 |

### Routing Priority

路由优先级从高到低：

1. 安全和安装类请求优先：setup、upgrade、doctor。
2. 已有 run 请求优先走 `deck-master` 解析状态，再转具体 skill。
3. 新项目材料优先走 `deck-init`，避免直接进入 planner。
4. 已有 brief / research summary 可跳过 init，直接进 `deck-planner`。
5. 单独文件质量检查优先走 `deck-quality`。
6. 最终交付判断优先走 `deck-review`。
7. 用户要求连续推进时走 `deck-autopilot`，但每个阶段仍写结构化证据。

## Workspace Model

`deck-init` 是 v1.0 必须新增的关键入口。它解决用户提到的“Workspace 中创建初始目录和参考目录”的问题。

### Standard Project Tree

`deck-init` 默认在用户指定项目目录中创建：

```text
<project>/
  00-客户原始需求/
  01-会议与沟通/
  02-AI协作过程/
    有价值/
    临时过程/
  03-参考素材/
    历史方案/
    客户素材/
    竞品与行业/
    截图与证据/
  04-方案与交付物/
    deck-master/
    exports/
    review/
  .deck-master/
    deck_project.json
    material_inventory.json
    workspace_policy.json
    run_bindings.json
  quality/
    forbidden_terms.md
```

说明：

- `00-客户原始需求` 保存客户原始输入，默认只读使用。
- `01-会议与沟通` 保存纪要、访谈、澄清问题。
- `02-AI协作过程/有价值` 保存可复用的 AI 过程产物。
- `02-AI协作过程/临时过程` 保存临时推理和草稿，默认不进入客户交付。
- `03-参考素材` 是 `deck-sourcing` 的首选项目级参考区。
- `04-方案与交付物/deck-master` 保存 Deck Master run 产物。
- `.deck-master` 保存项目机器可读状态。
- `quality/forbidden_terms.md` 保存项目级客户可见禁词。

### Project Metadata

`deck-init` 输出：

```json
{
  "schema_version": "deck_master_project.v1",
  "project_id": "stable-project-id",
  "project_name": "客户项目名",
  "workspace_root": "/absolute/path",
  "created_at": "2026-06-22T00:00:00Z",
  "material_roots": [
    "00-客户原始需求",
    "01-会议与沟通",
    "03-参考素材"
  ],
  "delivery_root": "04-方案与交付物",
  "quality_policy": "quality/forbidden_terms.md",
  "run_bindings": []
}
```

### Deck Init Exit Criteria

`deck-init` 完成条件：

- 标准目录存在。
- 原始材料清单生成。
- 参考素材目录存在。
- 项目禁词文件存在。
- Deck Master run 目录策略明确。
- 如果用户要求立即开工，创建或绑定一个 Deck Master run。

## Planning And Sourcing Rules

### Page Decision Types

`deck-sourcing` 必须对每页给出一个明确决策：

| Decision | 含义 | 使用条件 |
|---|---|---|
| `reuse` | 直接复用历史页结构或页面 | 内容高度匹配、来源允许、视觉和客户语境可接受 |
| `adapt` | 改写历史页 | 结构适合但行业、客户、品牌、数据需要更新 |
| `generate` | 新建页面 | 新观点、新客户上下文、历史库无合格候选 |
| `evidence_required` | 先补证据 | 关键论断缺数据、截图、案例、客户事实 |
| `manual_required` | 人工处理 | 需要人工确认商业口径、敏感边界、客户授权 |
| `blocked` | 阻断 | 来源不安全、资料冲突、缺关键输入、生产模式能力不可用 |

### Reuse / Adapt / Generate Trigger Rules

| 条件 | 推荐决策 |
|---|---|
| 历史页主题、受众、页面目的、证据类型均匹配 | `reuse` |
| 历史页结构好，但客户名、行业、数据、截图、视觉需替换 | `adapt` |
| 历史页只匹配视觉风格，内容逻辑不匹配 | `generate` |
| deep research 里有新结论，历史库无对应表达 | `generate` |
| 需要真实客户截图、系统界面、合同条款、报价等敏感证据 | `evidence_required` 或 `manual_required` |
| 候选页来源含未授权客户材料 | `blocked` |
| 页面任务仍含内部策划语言 | 退回 `deck-planner` 修正字段边界 |

### Sourcing Output

`deck-sourcing` 输出：

```json
{
  "schema_version": "deck_master_sourcing_plan.v2",
  "run_id": "run-id",
  "decisions": [
    {
      "page_task_id": "page_03",
      "decision": "adapt",
      "reason": "历史方案结构匹配，但客户证据和业务语境需替换",
      "library_candidate_ids": ["cand_001"],
      "required_inputs": ["客户系统截图", "项目目标 KPI"],
      "next_skill": "deck-producer"
    }
  ]
}
```

## Continuous Workflow

`deck-autopilot` 是 v1.0 需要新增的连续工作流入口。它参考 GStack `autoplan` 的做法，帮助用户用一句话启动完整链路，同时保留清晰的阶段证据。

### Modes

| Mode | 场景 | 行为 |
|---|---|---|
| `quick` | 用户要快速形成可审阅方向 | 使用项目材料，生成 brief / plan / sourcing，不进入生产 export |
| `production` | 用户要真实推进交付 | 严格走 setup、workspace、run、sourcing、generation、render、quality、review |
| `repair` | 用户已有阻断报告 | 读取 findings，生成返修任务，回到 producer / renderer / quality |
| `review-only` | 用户已有文件或 run | 只跑 quality / review / readiness |

### Production Workflow

```text
deck-autopilot production
  -> deck-setup readiness check
  -> deck-init project readiness
  -> deck-brief material understanding
  -> deck-planner narrative and page tasks
  -> deck-sourcing reuse/adapt/generate decisions
  -> deck-producer generation session
  -> deck-renderer artifact build
  -> deck-quality file and customer-visible gates
  -> deck-review final readiness and export queue
```

### Autopilot Stop Conditions

`deck-autopilot` 只在以下情况下停下请用户决策：

- 客户项目目录或资料范围不明确。
- 生产模式需要外部 Agent，但 generation session 进入 `awaiting_agent_execution`。
- 发现客户可见内容 P0 安全问题。
- 发现敏感材料来源无授权。
- 关键业务方向存在多种互斥选择。
- 安装、升级、文件权限、preview 服务连续修复失败。

其他情况下，`deck-autopilot` 继续推进并记录阶段证据。

## Setup, Upgrade, Doctor

### `deck-setup`

职责：

- 检查 `~/.deck-master/current`。
- 检查 CLI、skills、suite manifest。
- 检查 Codex / Claude Code skill links。
- 检查 active workspace。
- 检查 Review Cockpit 服务。
- 修复安全可自动修复的问题。

退出产物：

- `setup_status.json`
- `suite_status.json`
- `setup_evidence.md`

### `deck-upgrade`

职责：

- 准备 release tree。
- 校验 release manifest、capability lock、checksums。
- stage -> verify -> activate。
- 失败时恢复 previous release。
- 输出升级摘要和回滚路径。

退出产物：

- `release_manifest.json`
- `capability_lock.json`
- `SHA256SUMS`
- `upgrade_evidence.md`

### `deck-doctor`

职责：

- 只读诊断优先。
- 区分 install、suite、workspace、run、preview、artifact、quality。
- 给出可执行 repair plan。
- 修复后重新验证。

退出产物：

- `doctor_report.json`
- `repair_plan.md`
- `repair_evidence.md`

## Skill Manifest Changes

v1.0 的 `skills/manifest.json` 需要增加 role、public name、compat aliases、trigger type。

示例：

```json
{
  "name": "deck-sourcing",
  "path": "deck-sourcing/SKILL.md",
  "role": "product_workflow",
  "public": true,
  "compat_aliases": ["ppt-library"],
  "capabilities": [
    "deck_master.sourcing_decision.v2",
    "ppt_library.search.v1",
    "ppt_library.feedback_event.v1"
  ],
  "input_types": [
    "page_tasks",
    "historical_slide_library",
    "reference_deck"
  ],
  "exit_artifacts": [
    "library_candidates.json",
    "sourcing_plan.json"
  ]
}
```

Skill roles：

| Role | 含义 | 示例 |
|---|---|---|
| `ops` | 安装、升级、修复 | `deck-setup`、`deck-upgrade`、`deck-doctor` |
| `orchestrator` | 总控、路由、状态 | `deck-master`、`deck-autopilot` |
| `project` | Workspace 和项目初始化 | `deck-init` |
| `planning` | 材料理解和方案规划 | `deck-brief`、`deck-planner` |
| `production` | sourcing、generation、render | `deck-sourcing`、`deck-producer`、`deck-renderer` |
| `governance` | quality、review、export | `deck-quality`、`deck-review` |
| `learning` | 反馈、benchmark、经验沉淀 | `deck-learn` |
| `compat` | 历史名称兼容 | `ppt-library`、`ppt-master` 等 |

## Skill Document Contract

每个 SKILL.md 必须包含以下结构：

```text
---
name: deck-skill-name
description: 明确 Use when，必须包含输入类型和任务意图
triggers:
  - 用户自然语言触发句
do_not_use_when:
  - 应转给其他 skill 的场景
---

# Skill Name

## Use When
## Do Not Use When
## First Checks
## Runtime Ownership
## Allowed Commands
## Exit Artifacts
## Next Skill
## Safety Rules
```

新增要求：

- `Use When` 写用户输入，不写内部命令。
- `Do Not Use When` 必须指出常见误触发。
- `Exit Artifacts` 必须是机器可读文件或明确的 run state。
- `Next Skill` 必须告诉 Agent 下一步。
- `Safety Rules` 必须覆盖客户可见内容、敏感资料、fixture / production 边界。

## UI And Review Workspace

Review Cockpit / Workspace UI 需要按 v1.0 skill 体系展示状态：

| UI 区块 | 展示内容 | 来源 |
|---|---|---|
| Project Setup | Workspace、材料清单、禁词、run binding | `deck-init` |
| Plan | brief、claim map、narrative、page tasks | `deck-brief` / `deck-planner` |
| Sourcing | reuse/adapt/generate、候选页、缺证据 | `deck-sourcing` |
| Production | generation session、awaiting agent、import status | `deck-producer` |
| Render | artifact manifest、文件签名、stale 状态 | `deck-renderer` |
| Quality | artifact validator、customer-visible safety、P0 blockers | `deck-quality` |
| Review | final readiness、repair queue、export queue | `deck-review` |

用户可见文案原则：

- 主文案使用业务语言，例如“最终文件包含内部制作语言，需要返修”。
- 技术路径和 XML 包路径只放在详情区。
- 阻断原因需要指向负责 skill 和下一步动作。

## Implementation Plan

### Phase 0: Spec Freeze

目标：

- 落本文档。
- 更新 `docs/specs/README.md`。
- 把 v1.0 skill suite 作为后续迭代入口。

验收：

- Spec 明确最终 skill 名称、兼容策略、路由规则、Workspace、Workflow、Setup/Upgrade、测试计划。

### Phase 1: Manifest And Skill Skeletons

目标：

- 扩展 `skills/manifest.json`。
- 新增 `deck-setup`、`deck-upgrade`、`deck-doctor`、`deck-init`、`deck-brief`、`deck-sourcing`、`deck-producer`、`deck-renderer`、`deck-quality`、`deck-learn`、`deck-autopilot` 的 SKILL.md skeleton。
- 当前 `ppt-*` skill 改为兼容 wrapper。

验收：

- `suite-status` 能展示 public skills、compat aliases、capability readiness。
- Codex skill 列表中能看到新名。
- 旧名仍可触发，不破坏已安装用户。

### Phase 2: Deck Init

目标：

- 新增 `deck-master init-project` 或等价命令。
- 创建标准 Workspace tree。
- 生成 `deck_project.json`、`material_inventory.json`、`workspace_policy.json`、`quality/forbidden_terms.md`。
- 支持绑定现有 run。

验收：

- 空项目目录可初始化。
- 已有目录可幂等补齐。
- 不覆盖用户已有材料。
- 初始化后 `deck-brief` 可读取材料清单。

### Phase 3: Routing Resolver

目标：

- 新增 input-driven route resolver。
- `deck-master start` 返回 recommended skill route。
- `next-step` 返回 skill-level next action。
- Review Cockpit 展示当前 skill 阶段。

验收：

- 原始材料 -> `deck-init`。
- existing brief -> `deck-planner`。
- standalone PPTX -> `deck-quality`。
- existing run delivery -> `deck-review`。
- setup problem -> `deck-setup` / `deck-doctor`。

### Phase 4: Sourcing Boundary

目标：

- 将 `ppt-library` + `decide-sourcing` 对用户收敛为 `deck-sourcing`。
- 输出统一 `sourcing_plan.v2`。
- 每页必须有 reuse/adapt/generate/evidence/manual/blocked 决策。

验收：

- 候选页检索结果可追踪。
- reuse/adapt/generate 规则可测试。
- 无 page task 时不会误触发 library search。

### Phase 5: Producer / Renderer / Quality Public Renaming

目标：

- `deck-producer` 包装 generation session。
- `deck-renderer` 包装 render/build manifest。
- `deck-quality` 包装 artifact validator 和 customer-visible safety gate。
- 保留旧 `ppt-*` 入口。

验收：

- 新旧入口都能跑。
- 文档推荐新入口。
- Run state 仍只认 canonical artifacts。

### Phase 6: Deck Autopilot

目标：

- 新增连续 workflow。
- 支持 `quick`、`production`、`repair`、`review-only`。
- 阶段之间写 evidence，不以用户确认作为默认门。

验收：

- 从材料启动 quick workflow，能到 page tasks / sourcing。
- production workflow 在无 executor 时停在 `awaiting_agent_execution`。
- repair workflow 能从 quality findings 生成返修任务。

### Phase 7: UI And Docs

目标：

- Review Cockpit 按 skill 阶段展示。
- README、Quick Start、Agent Guide、Troubleshooting、Release Notes 改成新命名。
- 文档明确旧名兼容关系。

验收：

- 用户能从 UI 判断当前处于 init、brief、planner、sourcing、producer、renderer、quality、review 哪一段。
- 文档不会继续把 `ppt-*` 当主入口推荐给普通用户。

## Test Plan

静态验证：

```bash
git diff --check
python3 -m json.tool skills/manifest.json
```

Skill 文档验证：

- 每个 public skill 必须有 `Use When`。
- 每个 public skill 必须有 `Do Not Use When`。
- 每个 public skill 必须有 `Exit Artifacts`。
- 每个 public skill 必须有 `Next Skill`。
- 每个 compat skill 必须指向 public replacement。

Routing 测试：

- 原始材料目录 -> `deck-init`。
- deep research Markdown -> `deck-init` 或 `deck-brief`，取决于是否已有项目。
- brief JSON -> `deck-planner`。
- page tasks -> `deck-sourcing`。
- generation dispatch package -> `deck-producer`。
- render request -> `deck-renderer`。
- standalone PPTX -> `deck-quality`。
- Deck Master run export request -> `deck-review`。
- install problem -> `deck-setup`。
- broken preview service -> `deck-doctor`。
- upgrade request -> `deck-upgrade`。

Workspace 测试：

- 空目录初始化成功。
- 已有项目目录幂等补齐。
- 已有用户文件不覆盖。
- 项目禁词文件生效。
- run binding 可读写。

Workflow 测试：

- `deck-autopilot quick` 能从材料推进到 plan / sourcing。
- `deck-autopilot production` 在缺 executor 时进入等待 Agent 状态。
- `deck-autopilot repair` 能读取 quality findings 生成返修队列。
- `deck-review` 只读取 final readiness 做 client export 判断。

回归测试：

```bash
python3 -m compileall scripts tests
python3 -m unittest discover -s tests
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
```

## Acceptance Criteria

v1.0 Skill Suite 完成标准：

- 用户看到的主入口统一为 `deck-*`。
- `ppt-*` 旧入口可用，但在产品文档中降级为 capability alias。
- `deck-init` 能创建项目 Workspace 和参考素材目录。
- `deck-master start` 能给出 skill-level next action。
- `deck-autopilot` 能连续推进一个项目，不要求用户每步确认。
- setup、upgrade、doctor 与生产流程分离。
- Review Cockpit 能显示当前阶段和业务化阻断原因。
- 客户可见内容安全门禁接入 `deck-quality` 和 `deck-review`。
- client export 只受 `final_readiness.json` 放行。

## Open Decisions

| Decision | Default | 说明 |
|---|---|---|
| 是否一次性安装所有新 skill | 是 | 用户无需理解能力包来源，Suite 完整安装更符合产品心智 |
| 是否立即删除旧 `ppt-*` | 否 | 保留兼容，降低迁移风险 |
| `deck-brief` 是否独立于 `deck-planner` | 是 | 原始材料理解和页面结构规划是两类输入，分开后路由更清晰 |
| `deck-init` 是否创建标准中文目录 | 是 | 匹配当前用户 Workspace 工作方式，同时允许配置英文模板 |
| `deck-autopilot` 是否默认 production | 否 | 默认 quick，用户明确要求真实交付时进入 production |
| `deck-learn` 是否进入 v1.0 必做 | 可 skeleton 先行 | 反馈沉淀重要，但不阻塞 v1.0 主交付链 |

## Next Iteration Entry

建议下一轮实施顺序：

1. Phase 1：manifest + skill skeleton + compat wrapper。
2. Phase 2：`deck-init` Workspace 初始化。
3. Phase 3：routing resolver 和 `next-step` skill-level 输出。
4. Phase 4：`deck-sourcing` 合并 library + sourcing decision。
5. Phase 5：producer / renderer / quality 新名入口。
6. Phase 6：`deck-autopilot` 连续 workflow。
7. Phase 7：UI 和文档收口。

这条路径先解决用户认知和 workflow 连续性，再逐步替换底层能力入口。它保持 v0.9.13 已完成的生产闭环不倒退，同时为 v1.0 建立一套接近 GStack 成熟度的 Deck 生产 skill suite。
