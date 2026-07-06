# Deck Master 当前实现与用户故事梳理

日期：2026-06-17
版本：复审后迭代版
范围：当前 `main`，仓库代码已进入 v0.9.13 Product Capability Suite 形态；本机安装仍存在旧 release 与 suite skill 冲突；同时保留复审证据文件 `deck-master-user-story-rereview-2026-06-17.md`。

## 1. 一页结论

Deck Master 当前最准确的产品定位是：客户方案 Deck 的生产运行时和审查中枢。它可以把客户材料、workspace、run、brief、claim map、主叙事、页面任务、历史页来源、生成任务、生成结果、渲染结果、质量门禁、Review Cockpit、export queue、feedback 和 benchmark 串到一个可追踪链路里。

相比上一版报告，当前代码已有三处明确改善：

1. **安装链路升级到 Product Capability Suite。** v0.9.13 新增 `setup --install-suite`，在干净环境中可以一次装齐 `deck-master`、`deck-planner`、`deck-review`、`ppt-master`、`ppt-library`、`ppt-deck-pro-max`、`ppt-quality-gate`。
2. **生成链路有最小内置能力。** `generation-session create` 会优先发现 bundled `ppt-deck-pro-max` capability，减少对 `~/.deck-master/tools.json` 的强依赖。
3. **渲染链路有最小回写能力。** `render --format html --fixture-safe` 可写入 canonical `render_results/render_result.json`。

同时，真实产品体验仍有关键风险：

- 本机实际 suite 仍是 `degraded_ready`，`full_suite_ready=false`。
- `deck-master start` 仍只显示 setup ready，没有把 suite 阻断和 task readiness 放到首屏。
- 主叙事仍被固定页型骨架牵引，材料驱动能力还不够。
- PPT Library `auto` 模式仍会 fallback fixture，用户容易误解候选来源。
- 生成结果导入后，session 状态进入 `quality_required`；即使 `quality-gate draft` / `draft_v2` 已 pass，`run-state` 仍卡在 `needs_draft_gate`。

因此，当前对外承诺建议收紧为：

> Deck Master 能把客户方案 Deck 的生产过程从材料、主叙事、页面来源、生成、质检、审查到导出放到一个可追踪 run 里。当前版本已经具备最小生成和渲染闭环；高质量最终 PPT 仍取决于真实素材库、生成工具、人工审查和状态闭环修复。

## 2. 当前真实能力地图

| 模块 | 当前状态 | 用户可感知结果 | 关键边界 |
|---|---|---|---|
| Skill / Suite 安装 | 代码已改善，本机仍降级 | 干净环境可通过 `setup --install-suite` 装齐 required suite | 本机存在旧 release、real dir conflict、foreign symlink |
| Setup | 可用 | 可登记 active workspace、runs dir、Review Cockpit URL | `start` 仍没有展示 suite/task readiness |
| Workspace | 可用 | 可创建标准 workspace 目录和占位质量文件 | 占位视觉系统、页型标准仍需维护 |
| Context Intake | 可用 | 可从本地文本创建 context manifest | 实时飞书、OpenViking、复杂 PDF 理解仍需外部流程 |
| Guided Conversation | 基础可用 | 生成固定问题清单和 locked decisions | 缺回答、跳过、锁定的真实交互闭环 |
| Brief / Claim Map | 可用 | 能产出 deck brief、claim map | 仍偏摘要、关键词和规则提取 |
| Narrative Planner | 可用但偏模板 | 能产出 12 页左右 narrative plan 和 page tasks | `BASE_BEATS` 仍包含固定零售页型 |
| PPT Library | 契约可用 | 可调用 `ppt-lib` 或使用 fixture 候选 | 本机 suite 判定 `library_sourcing=blocked`，fallback 标识不够显眼 |
| Sourcing | 可用 | 每页可判定 reuse / adapt / generate / manual_placeholder | 决策质量受候选页质量和 planner 准确性影响 |
| Generation Tasks | 可用 | 能创建 adapt / generate 任务包 | 任务包质量依赖页面计划和证据质量 |
| Generation Session | 已有最小闭环 | 可创建 session、执行 bundled placeholder generator、导入结果 | bundled 输出是 placeholder，真实成片仍依赖高质量外部工具 |
| Render | 已有最小闭环 | 可输出 fixture-safe HTML 和 canonical render result | 不能等同于最终客户 PPT |
| Quality Gate | 可用但状态衔接有缺口 | Draft / Evidence / Brand / Confidentiality / Render / Delivery 等 gate 可运行 | `quality_required` 与 gate pass 的状态推进存在死循环 |
| Review Cockpit | 可用且更完整 | 能看 run-state、readiness、suite、quality、export、feedback | UI 仍偏审查面板，缺完整用户向导 |
| Export Queue | 可用 | 只导出 approved 页面，并读取质量阻断 | final readiness 口径仍需统一 |
| Feedback / Metrics / Benchmark | 可用 | 能记录 run-local feedback、metrics、benchmark 报告 | 真实反馈写回外部库仍需显式策略 |

## 3. PM 视角的标准用户故事

### 3.1 第一次安装与 Setup

用户目标：让 Deck Master 知道当前客户项目在哪里、产物放在哪里、需要哪些 Agent 能力、Review Cockpit 在哪里。

当前推荐路径：

1. 选择当前客户项目 workspace。
2. 执行 `setup --workspace <path> --repair-workspace --target codex --target claude-code --install-suite`。
3. 执行 `setup-status --include-suite --output json`。
4. 执行 `suite-status --output json`。
5. 打开 Review Cockpit，确认 active workspace、runs、suite readiness 和 task readiness。

当前本机事实：

- 基础 setup ready。
- active workspace 指向 `<local-private-workspace>`。
- Review Cockpit 可读取该 workspace 的 runs。
- suite status 是 `degraded_ready`。
- `full_suite_ready=false`。
- `deck-master start` 没有把 suite degraded 展示给用户。

产品风险：

- 用户看到 setup ready 后，会误判完整生产链路可用。
- 真实检索、生成、独立质检、渲染和 delivery readiness 会在后续步骤才暴露阻断。

### 3.2 创建一个客户方案 Run

用户目标：从会议转写、客户材料或 brief 开始一轮客户方案 Deck。

当前路径：

1. `start-conversation --workspace <workspace> --context-file <file> --industry <industry> --run-id <run_id>`
2. `build-brief --run-id <run_id>`
3. `build-claim-map --run-id <run_id>`
4. `autoplan --run-id <run_id> --planning-mode narrative_v2 --library-mode auto`

临时环境复审结果：

- 能从样例上下文生成 12 页 preview。
- 能生成 request、context_manifest、conversation_session、deck_brief、claim_map、narrative_plan、page_tasks、sourcing_plan、generation_tasks、preview_manifest。
- 8 个页面进入 generation task 队列。
- 12 页初始状态为待审。

用户风险：

- 这一步输出的是可审查 run / preview，仍需生成、渲染、质量门禁、人工审查和导出放行。
- `library-mode auto` 失败后会使用 fixture candidate，必须显式标记候选来源。

### 3.3 主叙事与页面规划

用户目标：让系统从客户上下文中提炼真正的方案主线，并决定哪些页面需要复用、改写或新生成。

当前实现：

- 可生成 `consulting_judgments.json`。
- 可生成 `claim_evidence_graph.json`。
- `narrative_v2` 会结合 claim map、judgments、workspace archetypes。
- production 模式下如果没有 claim map，planner 会阻断。

主要问题：

- `page_budget.py` 仍保留固定 `BASE_BEATS`。
- 固定页型包含“全渠道场景、库存可视化、最后一公里配送”等零售页。
- `narrative_planner.py` 只对少数受限样本过滤不合适页型。
- Guided Conversation 仍是固定问题清单，缺回答闭环。

产品判断：

- 当前主叙事层是“模板骨架 + 证据字段 + claim 绑定”的 MVP。
- 真正按客户材料动态生成方案主线，还需要继续强化。

### 3.4 历史页检索与 Sourcing

用户目标：判断哪些页面可复用、哪些页面需改写、哪些页面需新生成。

当前实现：

- `search-library` 可调用 PPT Library 的 `select-slides`。
- `import-library-selection` 可导入外部 PPT Library selection。
- `decide-sourcing` 会生成 sourcing plan。
- `record-library-feedback` 默认写 run-local queue，降低污染外部库的风险。

本机现状：

- `ppt-lib` CLI 存在。
- Codex 下 `ppt-library` skill 是 real dir conflict。
- suite 判定 `library_sourcing=blocked`。

用户风险：

- CLI 和 suite readiness 口径不一致。
- fixture candidate 在 preview 中可能显示成普通 `library_slide`。
- 如果真实 PPT Library 索引质量不足，Deck Master 仍能产出可追踪决策，但决策质量会受影响。

### 3.5 新页生成与渲染

用户目标：把 generate / adapt 页面交给生产能力，得到 preview、PPTX、HTML 或其他 artifact，并回写 Deck Master run。

当前实现：

- `create-generation-tasks` 会创建 adapt / generate 任务包。
- `generation-session create/status/validate/import-results` 已实现。
- `run-generation` 会优先发现 bundled `ppt-deck-pro-max` capability。
- `generation-session import-results` 会校验 run_id、session_id、artifact path、preview path，并刷新 preview。
- `render --format html --fixture-safe` 可写 canonical render result。

临时环境复审结果：

- `generation-session create` 自动使用 bundled `ppt-deck-pro-max`。
- `run-generation` 成功产出 8 个 generation result。
- `generation-session import-results` 后 preview 能刷新生成页。
- `render` 成功写入 `render_results/render_result.json`。

用户风险：

- bundled generator 当前产出 placeholder 文件，不能代表真实成片质量。
- 本机 suite 冲突仍会阻断 production readiness。
- 生成结果导入后的状态推进存在死循环，详见 P0-5。

### 3.6 质量门禁、审查和导出

用户目标：最终输出前确认页面质量、证据、品牌、敏感词、渲染和交付 readiness。

当前实现：

- 内建 gate：`draft`、`draft_v2`、`evidence`、`context-conflict`、`confidentiality`、`brand`、`render`、`delivery`。
- Review Cockpit 展示 run-state、external-results、runtime-readiness、quality-governance、export-queue、run-metrics。
- `export` 会读取 approved 页面和质量阻断。

临时环境复审结果：

- `quality-gate draft_v2` pass。
- `quality-gate draft` pass。
- `run-state` 仍显示 `needs_draft_gate`，原因是 session status 留在 `quality_required`。

产品判断：

- 单个 gate pass 不能代表最终可交付。
- final readiness 需要统一收口：setup、suite、workspace、generation、render、quality、review、export 都要进入同一个用户可理解状态。

## 4. 当前关键问题

### P0-1：`start` 让用户误判完整可用

现象：

- `setup-status --include-suite` 显示 suite degraded。
- `deck-master start` 只显示 setup ready。
- `start` 的 next action 指向 `deck-master setup-status`，没有指向 suite repair。

影响：

- 用户会认为 Deck Master 已经可用于完整生产。
- blocked capability 会在后续真实任务中才暴露。

建议：

- `start` 默认包含 suite 摘要。
- `full_suite_ready=false` 时首屏展示 blocked task readiness。
- first action 指向 `suite-repair` 或 migration plan。

### P0-2：本机安装与仓库代码存在状态差

现象：

- 仓库 skill 已推荐 `setup --install-suite`。
- 本机 `deck-master` skill 仍指向旧 release。
- `ppt-master` 是 foreign symlink。
- `ppt-library`、`ppt-deck-pro-max` 是 real dir conflict。
- `deck-planner`、`deck-review`、`ppt-quality-gate` 缺 skill link。

影响：

- 新代码能力已经提升，但用户本机仍会以 degraded suite 运行。
- Agent 按 installed skill 读取时可能拿到旧流程。

建议：

- 提供 suite migration dry-run。
- 对 real dir conflict 给出保留、迁移、替换三种路径。
- 迁移完成后强制复查 `suite-status`。

### P0-3：主叙事仍偏模板化

现象：

- 固定 `BASE_BEATS` 仍存在。
- 零售页型仍会进入通用规划。
- judgment、claim、workspace refs 只是增强字段。

影响：

- 真实客户方案可能出现行业不匹配页面。
- 用户会感觉系统在套模板。

建议：

- production path 中固定模板降级为 fallback。
- 页面计划优先来自 claim graph、conversation decisions、narrative advice、workspace archetypes。
- 增加 `answer-question`、`skip-question`、`lock-decision` 或 UI 等价能力。

### P0-4：PPT Library fixture fallback 标识不足

现象：

- `library-mode auto` 真实调用失败后会使用 fixture。
- selection 有 `source=fixture`，但 preview 主视图容易显示为普通 `library_slide`。

影响：

- 用户可能把占位候选当成真实历史资产检索结果。

建议：

- preview 页面增加 `真实库 / fixture / imported` badge。
- production run 下 `auto -> fixture` 需要用户确认。
- Review Cockpit page detail 显示 fallback warning 和 candidate source。

### P0-5：生成后质量状态无法自然推进

现象：

- `generation-session import-results` 后 session status 变成 `quality_required`。
- `quality-gate draft_v2` pass。
- `quality-gate draft` pass。
- `run-state` 仍显示 `needs_draft_gate`。

影响：

- 用户按系统提示跑完质量门禁后，系统仍要求重复跑 gate。
- run 无法自然进入 review 阶段。

建议：

- `quality-gate draft/draft_v2` pass 后更新 generation session status。
- 或者 `run_state_resolver` 在看到 `quality_required` 时检查 draft gate；如果 gate 已存在且不阻断，就推进到 review。

### P1-1：final readiness 口径分散

现象：

- `run-state` 已展示 render readiness。
- stage 判定进入 export 前没有强制 render present。
- Review readiness 的 export ready 主要看 evidence、quality、approved pages。

影响：

- 用户会看到多个状态，难以判断最终是否能交付。

建议：

- 建立统一 final readiness：setup、suite、workspace、generation、render、quality、review、export 一次性给出结论。

### P1-2：Playbook 与 CLI 漂移

发现：

- `codex-run-solution-deck.md` 仍使用 `--context-dir`。
- `ppt-deck-pro-max-handoff.md` 仍写 one entry per generate page。
- 当前实际 generation task 覆盖 adapt 和 generate。

影响：

- Agent 按文档执行会出错或误解任务边界。

建议：

- 先修 playbook，成本低、收益高。
- 将真实生产路径统一为一条最短命令序列。

## 5. 复审后的用户故事

建议把 PM 视角用户故事收敛为 7 步：

1. 用户选择当前客户 workspace，并执行 `setup --install-suite`。
2. 系统显示三层 readiness：基础 setup、当前任务能力、完整生产 suite。
3. 用户导入客户材料，系统创建 run、brief、claim map。
4. 系统生成 narrative plan 和 page tasks，同时标出证据缺口。
5. 系统做 sourcing：真实历史页、fixture、generate、adapt 都有清晰标识。
6. 系统执行 bundled 或外部 generation/render，并把结果回写 run。
7. 系统通过统一 final readiness 判断是否允许 export。

## 6. 最小修复优先级

时间有限时，建议按下面顺序收敛：

1. 修 `run_state_resolver` 的 `quality_required` 死循环，让 gate pass 后推进到 review。
2. 修 `start`，默认展示 suite readiness 和 blocked task readiness。
3. 修 playbook：`--context-file`、adapt/generate、v0.9.13 setup flow。
4. 在 preview 和 Review Cockpit 显示 fixture badge。
5. production run 创建前确认 workspace。
6. 将固定 `BASE_BEATS` 降级成 fallback，优先使用 claim/advice 驱动 page plan。

## 7. 验证记录

本轮复审执行过：

- 当前本机 `setup-status --include-suite`：setup ready，suite degraded，full_suite_ready=false。
- 当前本机 `start`：只显示 setup ready，没有 suite 摘要。
- 临时 HOME `setup --install-suite --target codex --target claude-code`：full_suite_ready=true。
- 临时 run：`start-conversation -> build-brief -> build-claim-map -> autoplan` 成功，生成 12 页 preview。
- 临时 run：`generation-session create` 成功，自动使用 bundled `ppt-deck-pro-max`。
- 临时 run：`run-generation` 成功，产出 8 个 generation result。
- 临时 run：`render --format html --fixture-safe` 成功，写入 canonical render result。
- 临时 run：`quality-gate draft_v2` 和 `quality-gate draft` 均 pass。
- 临时 run：质量 gate pass 后 `run-state` 仍卡 `needs_draft_gate`。
- 相关测试：`python3 -m unittest tests.test_skill_installation tests.test_generation_session_bridge tests.test_render_runtime tests.test_run_state_resolver`，61 tests passed。
- 文档格式检查：`git diff --check` 通过。

