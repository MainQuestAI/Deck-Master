# Deck Master 链路诊断报告

日期：2026-06-15

## 1. 结论

当前 Deck Master 的问题比单点命令缺失更深。代码已经具备 Run、Artifact、Quality Gate、Review Cockpit、Handoff 等对象，但产品链路没有形成强主控。

核心断点有六个：

1. Setup 把“安装可用”误判成“用户已完成工作区设置”。
2. Workspace 只影响 runs dir，未稳定进入 request、planner、page task 和质量标准读取。
3. 自动规划仍是通用模板，包含硬编码零售/履约页型，会污染真实客户方案。
4. Deck Master 和 PPT Deck Pro Max 的关系停留在文件契约，缺少真实 runner / skill bridge / generation session。
5. `orchestration-check` 放行条件过松，未把 Review Cockpit 页面审阅状态纳入生产放行。
6. Skill 约束依赖 Agent 自觉执行，没有代码级的“用户点名 Deck Master 后先进入 Deck Master 链路”的外部工具阻断机制。

因此当前体验会像“Agent 在外部思考和手写文件，Deck Master 事后登记结果”。这解释了为什么真实会话里先调用 Canva、后面手工写 plan/sourcing，再导回 run。

## 2. 验证摘要

### 2.1 临时 HOME 黑盒验证

用临时 HOME 验证安装、Setup 和真实 plan：

```text
after_install_setup_status=blocked deck-master setup --workspace <path> --target codex
after_setup_no_workspace_status=ready active_workspace=''
plan_without_workspace=planned <tmp>/.deck-master/runs/no-workspace-smoke
```

结论：

- `install-skill` 后确实没有自动 Setup。
- 执行 `setup --runs-dir` 且不传 workspace 后，系统会进入 ready。
- ready 后真实 run 命令可继续执行。

### 2.2 active workspace 黑盒验证

用临时 HOME 设置 active workspace 后执行 `plan`：

```text
run_dir=<tmp>/workspace/runs/workspace-aware-smoke
request.workspace=None
first_beat_workspace_refs=None
workspace_exists=True
```

结论：

- active workspace 会决定 run 放到哪里。
- `request.json` 没写入 workspace。
- Planner 没拿到 workspace refs。

### 2.3 本机真实配置

`/Users/dingcheng/.deck-master/config.json` 当前：

```json
{
  "active_workspace": "",
  "default_runs_dir": "/Users/dingcheng/.deck-master/runs"
}
```

结论：

- 本机当前是全局 runs 模式。
- 云南白药 run 没有绑定 `/Users/dingcheng/Workspace/云南白药/云南白药DAM`。

### 2.4 云南白药真实 run 状态

两个相关 run：

```text
20260615022309-云南白药二轮方案-企业级-ai-知识与内容底座及九条业务流程拆解-v2
request.workspace=None
context_manifest.json missing

yunnan-baiyao-ai-foundation-deck-v1
request.workspace=None
context_manifest.workspace=''
conversation.answers=0
preview decisions: needs_review=22
source_decision: adapt=12, generate=10
generation_results: empty
```

`next-step` 输出：

```text
status=needs_page_review
pending_pages=22
```

`orchestration-check` 输出：

```text
status=ready_for_external_production
allow_external_production=true
```

结论：

- 当前 run 仍有 22 页待审。
- `orchestration-check` 仍放行外部生产。
- 10 页 generate 没有真实 generation result。

## 3. 问题到代码的映射

### P0-1：Setup ready 语义过宽

现象：

用户安装后没有真实工作区引导。当前 setup 可以在没有 workspace 的情况下 ready。

代码位置：

- `scripts/runtime/setup_status.py:74-107`
- `scripts/runtime/setup_status.py:110-192`
- `scripts/runtime/setup_status.py:201-209`

关键代码行为：

- `run_setup()` 的 `workspace` 是可选参数。
- 未传 workspace 时，`active_workspace` 写成空字符串。
- 未传 workspace 时，`default_runs_dir` 使用 `~/.deck-master/runs`。
- `setup_status()` 只有在存在 `workspace_path` 时才验证 workspace。
- `require_setup_ready()` 只看 `status == "ready"`。

影响：

- 首次使用可以绕开 workspace 初始化。
- 系统无法保证真实项目有 visual-system、structure-assets、quality、assets、runs、exports。
- 用户体验上会变成“装了就能跑”，但跑出来的 run 没有项目生产环境。

建议修复方向：

- 将 setup 拆成 `install_ready` 和 `workspace_ready` 两层。
- 真实 deck run 必须要求 active workspace。
- 无 workspace 时 `setup-status` 应返回 `blocked` 或 `needs_workspace`。

### P0-2：安装链路没有 onboarding 状态机

现象：

真实用户安装后，系统没有自动引导 Setup。

代码位置：

- `scripts/skills/installer.py:104-186`
- `scripts/deck_master.py:1309-1321`
- `skills/deck-master/agents/openai.yaml:1-4`

关键代码行为：

- `install_skill()` 只创建 Agent skill 软链接并写 install log。
- `install-skill` 不写 `config.json`。
- `install-skill` 不返回下一步 setup 命令。
- `openai.yaml` 只有展示信息，没有 first-run hook。

影响：

- 安装完成和 Setup 完成是两个割裂动作。
- Codex 看到 Skill 后不会被代码层强制带入 Setup。
- 用户会以为安装完成后可以直接开始正式项目，但工作区没有建立。

建议修复方向：

- `install-skill` 返回 `next_command`。
- 增加 `deck-master doctor` 或 `deck-master onboarding`。
- Skill First Checks 之外，CLI 和 Review Cockpit 都要暴露 setup banner / blocked state。

### P0-3：active workspace 没有进入 request 和 planner

现象：

即便配置了 active workspace，`plan` 生成的 `request.json` 里也没有 workspace。

代码位置：

- `scripts/deck_master.py:322-339`
- `scripts/deck_master.py:1067-1079`
- `scripts/deck_master.py:454-475`
- `scripts/deck_master.py:189-220`

关键代码行为：

- `add_brief_args()` 没有 `--workspace`。
- `command_plan()` 调 `build_request()` 时不传 workspace。
- `command_autoplan()` 复用 `command_plan()`，也没有 workspace。
- `_load_workspace_archetypes()` 只读 `request["workspace"]`。

影响：

- active workspace 只影响 run 写入目录。
- Planner 不读取工作区页型和标准。
- Page tasks 不携带稳定 workspace refs。
- 质量门禁无法默认读取项目级质量规则。

建议修复方向：

- `plan/autoplan` 增加 `--workspace`，默认读取 setup active workspace。
- `request.json` 必须写入 `workspace`。
- `write_plan_artifacts()` 必须在 workspace 缺失时阻断真实 run。

### P0-4：Workspace 校验与真实 run 门禁没有闭环

现象：

云南白药工作区校验结果是 `pending_manual_review`，但真实 run 已经在全局 runs 下继续推进。

代码位置：

- `scripts/workspace/foundation.py:142-204`
- `scripts/runtime/setup_status.py:155-170`
- `scripts/deck_master.py:175-186`
- `scripts/deck_master.py:1507-1511`

关键代码行为：

- `validate_workspace()` 能发现缺失项。
- `setup_status()` 只有拿到 workspace_path 才调用校验。
- `_workspace_for_setup_guard()` 对 `plan` 无法给出 workspace，因为 `plan` 没有 workspace 参数。

影响：

- workspace 校验能力存在，但真实 run 经常碰不到它。
- 代码满足了“有 validate-workspace 命令”，没有满足“真实 run 必须在有效 workspace 内启动”。

建议修复方向：

- setup active workspace 为空时阻断真实 run。
- plan/start/autoplan 默认使用 active workspace。
- Review Cockpit Studio 创建 run 也必须先检查 workspace。

### P0-5：自动规划引擎仍是硬编码模板

现象：

白药自动 plan 里出现“库存可视化”“最后一公里配送”等不适配页名。

代码位置：

- `scripts/planning/page_budget.py:4-17`
- `scripts/planning/page_budget.py:41-55`
- `scripts/planning/narrative_planner.py:135-233`
- `scripts/planning/brief_intake.py:8-15`

关键代码行为：

- `BASE_BEATS` 写死了全渠道、库存、配送等页型。
- `beat_templates()` 超页数时循环通用 extra_roles。
- `detect_topics()` 只有少量关键词。
- `plan_narrative()` 基于模板生成页面，不会从客户材料中抽出真实场景结构。

影响：

- 自动规划在真实行业方案上会跑偏。
- Agent 必须人工重写 plan。
- Deck Master 的“主叙事引擎”体验会弱。

建议修复方向：

- 把默认模板降级为 fallback。
- 强制走 context -> brief -> claim -> narrative advice -> page plan。
- 引入客户需求结构抽取：场景、角色、监管、业务线、证据包、部署边界。

### P0-6：Guided Conversation 只是静态问题清单

现象：

当前 run 的 `conversation.answers=0`，但后续流程仍继续。

代码位置：

- `scripts/conversation/session_builder.py:6-32`
- `scripts/conversation/session_builder.py:35-60`
- `scripts/deck_master.py:342-366`

关键代码行为：

- `GUIDED_QUESTIONS` 是固定问题列表。
- `build_conversation_session()` 创建 questions 和 locked_decisions。
- 没有收集用户答案的 CLI / UI 强制步骤。
- build-brief 不要求 conversation answers。

影响：

- “问询式主叙事校准”没有实际发生。
- 用户以为 Deck Master 会先问关键问题，实际可以直接继续跑。

建议修复方向：

- 增加 `answer-question` / `lock-decision` 命令。
- `build-brief` 前检查关键问题是否已回答或被显式跳过。
- Review Cockpit Studio 首屏应展示 setup + guided questions。

### P0-7：PPT Deck Pro Max 关系停在文件合约

现象：

Deck Master 没有正确呼起 PPT Deck Pro Max。

代码位置：

- `scripts/generation/task_builder.py:10-50`
- `scripts/generation/handback.py:47-173`
- `scripts/tools/deck_pro_max_client.py:10-56`
- `skills/deck-master/playbooks/ppt-deck-pro-max-handoff.md:24-61`
- `scripts/deck_master.py:1385-1398`

关键代码行为：

- `create_generation_tasks()` 只生成 JSON 文件。
- `prepare_generation_handoff()` 只增强 task 字段。
- `import_generation_result()` 只导入外部结果。
- `deck_pro_max_client.py` 有硬编码 pipeline init helper，但没有接入主 CLI。
- Playbook 写的是让 Agent 自己跑 `ppt-deck-pro-max generate`。

影响：

- Deck Master 无法保证 PPT Deck Pro Max 被调用。
- Agent 如果没有主动触发 `ppt-deck-pro-max` Skill，生成链路会停在任务文件。
- 用户会看到 Deck Master 有 generation tasks，但没有真实成页。

建议修复方向：

- 决策点需要明确：继续外部工具模式，还是内化生成 runtime。
- 短期可做 `run-generation --tool ppt-deck-pro-max`，让 Deck Master 至少能创建 generation session、调用命令、导入结果。
- 中期可把 PPT Deck Pro Max 的项目 skeleton 和 page generation runner 合并进 Deck Master 的 generation subsystem。

### P0-8：Generation tasks 把 adapt 和 generate 混在一起

现象：

云南白药 run 有 12 页 adapt、10 页 generate，但 generation_tasks 生成了 22 个任务。

代码位置：

- `scripts/generation/task_builder.py:10`
- `tests/test_generation_tasks.py:21-33`
- `skills/deck-master/playbooks/ppt-deck-pro-max-handoff.md:11`

关键代码行为：

- `TASK_DECISIONS = {"generate", "adapt"}`。
- 测试也确认 adapt 会生成任务。
- Playbook 文案却说 “one entry per generate page”。

影响：

- adapt 页到底是历史页改写、PPT Deck Pro Max 重新生成、还是 PPT Master 渲染处理，边界不清。
- PPT Deck Pro Max 任务量被扩大。
- Review Cockpit 看到的 `generated` / `library_slide` 与 generation_tasks 的语义不一致。

建议修复方向：

- 拆成 `adapt_tasks` 和 `generation_tasks`。
- adapt 页要记录 reference slide、改写说明、是否需要重新渲染。
- generate 页才进入新页生成队列。

### P0-9：orchestration-check 放行条件不足

现象：

`next-step` 显示 22 页待审，`orchestration-check` 仍允许进入外部生产。

代码位置：

- `scripts/runtime/orchestration.py:49-84`
- `scripts/runtime/next_step.py:108-159`
- `tests/test_orchestration_enforcement.py:69-90`

关键代码行为：

- `orchestration_check()` 只检查必备 artifact 和是否存在 quality report。
- 不读取 quality report 的 `blocks_delivery`。
- 不读取 preview pages 的 decision 状态。
- 测试只断言有一个 `draft_gate.json` 就可以放行。

影响：

- 人工审阅还没完成时，系统可能提示外部生产可继续。
- Deck Master 的 gate 信号和 next-step 信号冲突。

建议修复方向：

- `allow_external_production` 必须同时满足：
  - 必备 artifact 完整。
  - 必要 quality gates 通过且不阻断。
  - generate/adapt 任务状态明确。
  - Review Cockpit 页面审阅达到要求。
- `orchestration-check` 和 `next-step` 使用同一个状态机。

### P0-10：Review Cockpit Studio 绕过 Setup Guard

现象：

Web Studio 能直接创建 run，但没有 setup guard。

代码位置：

- `scripts/preview/server.py:295-333`
- `scripts/preview/server.py:873-893`

关键代码行为：

- `api_create_run()` 直接 build_request、create_run、plan、search、sourcing、preview。
- server main 只读取 configured runs dir。
- 没有调用 `setup_status()` 或 `require_setup_ready()`。

影响：

- CLI 保护和 Web 入口保护不一致。
- 用户从 Review Cockpit 创建 run 时可以绕开 workspace setup。

建议修复方向：

- Studio 启动时检查 setup status。
- 未 ready 时只展示 setup repair 引导。
- `api_create_run` 必须阻断未绑定 workspace 的真实 run。

### P1-1：Skill 约束没有 host-level enforcement

现象：

真实会话里用户点名 Deck Master，但 Agent 第一反应调用 Canva。

代码位置：

- `skills/deck-master/SKILL.md:35-50`
- `skills/deck-master/SKILL.md:122-132`
- `skills/deck-master/references/agent-instructions.md:14-21`
- `skills/deck-master/agents/openai.yaml:1-4`

关键代码行为：

- Skill 写了 First Checks 和 Rules。
- 这些规则依赖 Agent 读取并遵守。
- 没有 runtime-level 阻止 Agent 先调 Canva 或纯手写规划。

影响：

- 触发稳定性取决于 Agent 行为。
- 用户点名 Deck Master 时仍可能走其他插件。

建议修复方向：

- Skill 开头加入更硬的执行序列。
- 提供单命令入口：`deck-master start --workspace ... --brief-file ...`。
- 减少 Agent 自己选择多个命令组合的空间。

## 4. 设计层判断：是否要内化 PPT Deck Pro Max

当前文档边界写得很清楚：

- Deck Master owns planning、tool orchestration、source decisions、preview、quality、export。
- PPT Deck Pro Max owns rich content generation、page-level generation workflow、project skeletons、generated assets。

代码落地没有达到这个边界。特别是 tool orchestration 没有真实 runner，只有 task/result 文件。

是否内化 PPT Deck Pro Max，本质是两个路线：

### 路线 A：保持 Companion Tool，补真实 runner

Deck Master 保持 Run OS 定位，但新增：

- `generation_session.json`
- `run-generation --tool ppt-deck-pro-max`
- tool availability check
- command invocation log
- result import automation
- generation task status machine

优点：

- 改动小。
- 保留 PPT Deck Pro Max 的独立能力。
- 能快速解决“Deck Master 没有呼起生成工具”的问题。

风险：

- 仍依赖外部工具质量。
- 多 Skill 调用仍可能受 Agent 行为影响。

### 路线 B：内化 PPT Deck Pro Max 的生产 runtime

Deck Master 接管：

- 项目 skeleton。
- 页面生成工作流。
- SVG/HTML/PPTX 中间产物。
- 生成后的视觉 QA 和修复循环。

优点：

- 用户链路更顺。
- Run、Plan、Generate、Review、Quality 都在一个系统内。
- 更符合“Deck Master 是专业 Deck 生产运行时”的产品直觉。

风险：

- 边界明显扩大。
- 会把 Deck Master 从 Run OS 推向完整生产引擎。
- 需要重新整理 PPT Deck Pro Max 的代码质量、依赖、资源路径和测试矩阵。

当前诊断建议：

先不要直接整包吞并 PPT Deck Pro Max。更稳的下一步是做“受控内化”：把生成 session、runner、状态机、导入和质量门禁放进 Deck Master；页面生成算法和渲染细节先保留为可替换 backend。这样能先解决链路断裂，同时避免一次性合并两个系统带来的不稳定。

## 5. 建议的下一轮修复范围

建议版本：`v0.9.11 Orchestration Runtime Realignment`

P0 范围：

1. Setup 状态拆分：`install_ready`、`workspace_ready`、`run_ready`。
2. 真实 run 必须绑定 workspace。
3. `plan/autoplan/start-conversation/Studio create-run` 默认使用 active workspace。
4. `request.json` 必须写入 workspace。
5. `run-status` 作为统一状态机，替代分散的 `next-step` / `orchestration-check` 判断。
6. `orchestration-check` 读取 page review、quality blocking、generation task 状态。
7. 增加 `import-sourcing`，禁止手工 sourcing 只落外部文件。
8. 增加 `generation-session` 和 `run-generation`，至少能真实呼起 PPT Deck Pro Max 或返回明确阻断。
9. 将通用 page template 从默认主路径降级为 fallback。
10. Review Cockpit Studio 增加 setup / workspace banner 和 blocked state。

P1 范围：

1. Guided questions 变成真实可回答、可锁定、可跳过的运行步骤。
2. Workspace learning pack 自动注入 planner。
3. adapt 与 generate 分开建模。
4. Skill playbook 改成单入口优先，降低 Agent 自行编排空间。

## 6. 给二次代码审查的问题清单

建议让 ChatGPT 重点核验这些问题：

1. `setup_status()` 是否会在 active workspace 为空时错误返回 ready。
2. `plan/autoplan` 是否能在没有 workspace 的情况下启动真实 run。
3. active workspace 是否实际进入 `request.json`。
4. Planner 是否读取 workspace 标准。
5. `BASE_BEATS` 是否导致行业页型污染。
6. `orchestration-check` 是否忽略 pending review pages。
7. `orchestration-check` 是否忽略 quality gate blocking 字段。
8. generation handoff 是否真的调用 PPT Deck Pro Max。
9. `deck_pro_max_client.py` 是否没有接入 CLI 主链路。
10. Web Studio 是否绕过 setup guard。
11. `generation_tasks` 是否混淆 adapt 和 generate。
12. Skill 约束是否只停留在提示词层。
