# Deck Master 1.0 RC Readiness 下一轮迭代 Spec

- 日期：2026-07-15
- 状态：Reviewed Spec（交叉评审修订版）
- 产品阶段：Technical Preview → 1.0 RC Readiness
- 起始提交：`main@266e752`
- 待固化修复输入：当前本机 repair diff；Phase 0 生成文件清单、patch SHA256 和测试证据后冻结
- 关联文档：
  - `docs/releases/2026-07-09-1.0.0-iteration-plan.md`
  - `docs/releases/v1.0.0-rc.1.md`
  - `docs/agent-recovery-playbook.md`

## 1. 结论

下一轮只解决阻止 Deck Master 进入 1.0 RC 的发布真相问题：诊断结论必须可信，当前修复必须进入正式代码基线，PPT Library 必须恢复生产就绪，真实 UAT 必须无警告，三组案例必须满足严格 `rc_eligible`，生产依赖必须可按公开版本与提交复现。

本轮继续维持 Technical Preview 标识。只有全部 RC 准入条件通过后，才进入单独的版本升级和发布决策。

## 2. 背景与实时基线

2026-07-15 的实时验证结果：

| 项目 | 当前结果 | 结论 |
| --- | --- | --- |
| 全量测试 | 1265 passed，105 subtests passed | 基础实现稳定 |
| Ruff | pass | 静态检查稳定 |
| Fixture Demo | 在已安装依赖的 Python 3.12 环境下通过，12 页 | Preview 主流程可用 |
| 裸 shell Fixture Demo | 缺少 `jsonschema` 时失败 | 首次使用引导不足 |
| 隔离发布包 | 构建成功，5 项 smoke 全部通过 | 发布包自包含性成立 |
| CI RC Gate | 11/11 pass | 可公开复现层稳定 |
| Full RC Gate | 12 项中 4 项失败 | 尚未达到 RC |
| 真实生产 run | Final Readiness ready，最终审批有效，12 页导出、0 阻断 | 单案例交付闭环成立 |
| Real Workflow UAT | 16/19 pass，3 warning | 缺完整 Agent 审查证据 |
| PPT Library UAT | 623/631 pass，8 warning | 候选截图和预览存在降级 |
| Suite Status | overall blocked | Library 与依赖快照未闭环 |
| Production Doctor | overall blocked | production run 被 Fixture Preview Gate 错误拦截 |

当前工作区包含 26 个已修改文件和 3 个新增文件。最终审批、RC 退出码、run-mode 继承、发布包注册表和严格 `rc_eligible` 等修复仍未进入远端主分支。下一轮必须先把这组改动变成可审查、可回归、可回退的正式基线。

现有真实 run 只能作为生产演练证据。它生成于候选提交冻结之前，最终审批也早于完整外部审查证据。正式 RC 第一案例必须在候选基线和依赖快照冻结后重新运行全部必需阶段，并在所有质量与 UAT 通过后重新发起最终审批。

## 3. 用户与业务目标

### 3.1 目标用户

- 使用 AI Coding Agent 制作售前解决方案 Deck 的个人开发者或解决方案架构师。
- 需要把真实材料转换为可审核、可追溯、可交付 PPTX 的内部团队。
- 需要从公开 release tree 安装并验证 Deck Master 的外部用户。

### 3.2 用户结果

用户完成一次生产运行后，应得到一个唯一且可信的结论：

```text
真实输入
  → 规划与素材选择
  → 页面生产与渲染
  → 质量审查
  → 最终就绪
  → 人工最终审批
  → 客户导出
  → 可追溯 RC 证据
```

任何诊断、Suite Status、Full RC Gate 和发布报告都必须对同一事实给出一致结论。

### 3.3 业务完成标准

- 一组成功案例可以被不同 Agent 按机器可读状态重复判断。
- 三组真实案例均具备成品、渲染、质量、审批、导出和版本指纹。
- 外部用户可根据公开 tag 与 SHA 获取生产后端。
- Full RC Gate、Production Doctor、Suite Status 和 release smoke 全部通过。
- 客户导出继续强制绑定人工最终审批和最终文件哈希。

### 3.4 RC 对外承诺边界

1.0 RC 只代表三类受控工作流在 Python 3.12、已认证本地依赖、人工监督和最终人工审批条件下可以重复交付。RC 不承诺无人值守批量生产、任意行业材料质量或完全自动化成品生成。

## 4. 范围决策

### 4.1 采用方案：发布闭环优先的局部修复

本轮采用最小发布闭环方案：复用现有 Workflow v2、阶段契约、Final Readiness、RC Gate、Capability Lock 和 UAT 报告，只修复影响发布真相与真实案例资格的代码和证据。

选择理由：当前架构已经支撑真实 12 页交付，主要风险来自状态口径冲突和证据缺失。大规模重构会增加回归面，也会延后 RC 判断。

### 4.2 已排除方案

1. **先拆分全部大文件再做 RC**：工程收益明确，但无法直接关闭发布阻断，延后到 RC 后治理。
2. **降低 Full RC 条件**：会削弱客户交付可信度，不采用。
3. **用 fixture 或补写报告替代真实案例**：违反生产证据原则，不采用。
4. **同步重做 Review Desk 视觉系统**：本轮没有新增 UI 主流程，延后处理。

## 5. In Scope

1. 将当前未提交修复集整理为正式可审查基线。
2. 修复 Production Doctor、Suite Status 与 Shell 退出码的诊断真相。
3. 刷新依赖快照，并将 `ppt-master` 绑定到公开 tag 和明确 SHA。
4. 恢复 PPT Library 生产能力与 Library Status v2 全字段就绪。
5. 补齐现有真实 run 的叙事审查、质量审查和截图证据。
6. 完成三组真实案例，并让严格 `rc_eligible` 达到 3/3。
7. 修复源码仓 Fixture Demo 的依赖预检和错误引导。
8. 完成 Full RC、生产诊断、隔离发布包和对外脱敏证据验证。

## 6. Out of Scope

- Review Desk 大规模视觉重做。
- 新增页面生成模型或新渲染框架。
- 重写 Workflow v2 或阶段契约体系。
- 全量拆分 `scripts/deck_master.py` 和 installer。
- 新增云服务、数据库或远程队列。
- 自动替代人工最终审批。
- 提交客户原始材料、私有基准源、运行产物、密钥或本地环境文件。
- 发布 `v1.0.0` 正式版或直接修改 Production Ready 标识。

## 7. 工作流 A：正式基线与变更治理

### A1. 固化当前修复集

Phase 0 先生成只读基线记录，包含 base commit、变更文件列表、patch SHA256、测试结果和禁止提交文件扫描结果。记录冻结后再创建迭代分支，后续 Agent 不得继续修改未登记的 repair diff。

将当前工作区改动按逻辑拆为独立提交：

1. 最终审批与 RC 退出码。
2. run-mode 继承与发布包完整性。
3. Skill 命令契约与文档。
4. 严格 benchmark / UAT 资格。
5. CI、截图审计与工程治理。

### A2. 基线验收

- 每个提交可独立说明业务目的和验证命令。
- 不包含生成 run、私有 benchmark、客户材料、缓存和本地配置。
- 全量测试、Ruff、`git diff --check` 通过。
- 代码审查确认最终审批无法由旧导出、Autopilot 或导出队列绕过。
- 基线安全扫描覆盖客户标识、绝对路径、密钥模式、大文件、run 目录和 benchmark 私有源。

### A3. 回退

每组提交保持可单独 revert。审批安全修复在任何后续回退中都必须保留。

## 8. 工作流 B：统一诊断真相

### B1. Production Doctor 模式矩阵

```text
agent-doctor
├── preview
│   ├── fixture demo entrypoint
│   ├── preview gate
│   └── preview-safe dependency truth
└── production
    ├── suite status
    ├── production backend
    ├── capability lock
    ├── dependency snapshot
    └── final readiness（仅在传入 run-dir 时）
```

规则：

- `preview_gate` 只属于 preview 模式。
- production 模式不得因 Fixture Preview Gate 失败而阻断。
- production 模式传入 run-dir 时，必须检查 Final Readiness。
- production 模式未传 run-dir 时，输出 `run_not_evaluated`，不得声明具体 run 可交付。
- production 模式未传 run-dir 时，`delivery_evaluated=false`，Final Readiness check 为 `not_evaluated`；环境诊断可以 ready，但该结果不得满足发布 Go 条件。
- CLI `--mode` 与 `request.json.run_mode` 冲突时，返回 `RUN_MODE_MISMATCH`、overall blocked 和退出码 2。
- Production Doctor 的 overall status 由 production 必需检查统一计算。

### B2. 状态与退出码

Doctor check 统一使用 `pass/warn/blocked/not_evaluated`，Doctor 顶层统一使用 `ready/warning/blocked`。本轮集中式退出码映射只覆盖 `agent-doctor`、`suite-status`、`preview-gate`、`rc-gate`、`final-readiness` 和 `release-smoke`，不扩展为全 CLI 错误码重构。

统一规则：

| JSON status | Shell exit code | 含义 |
| --- | ---: | --- |
| `ready` / `pass` | 0 | 可继续 |
| `warning` / `degraded_ready` | 0 | 可继续，但必须显示限制 |
| `blocked` / `fail` | 2 | 必须停止 |
| 内部未捕获异常或远端执行异常 | 1 | 命令执行错误 |

JSON 必须先完整写出，再返回退出码。使用 `--output json` 时，stdout 只能包含一个完整 JSON document；诊断提示写入 stderr；报告文件采用原子写入。argparse 和既有业务异常的全局迁移延后治理。

Warning 分为两类：

- `release_blocking_warning`：Full RC 失败；截图缺失、真实审查缺失、必需 UAT warning 属于此类。
- `advisory_warning`：允许继续，但必须进入 release limitations。

出现 `release_blocking_warning` 时，Full RC 顶层状态必须为 `fail`，Shell 返回退出码 2。

### B3. Suite Status 一致性

- `full_suite_ready=true` 时，不得出现 `suite_installation_blocked`。
- `suite-status.status`、`target_readiness`、`task_readiness` 和 `blocking_summary` 必须可互相推导。
- Library 阻断只影响依赖 Library 的任务，不得伪装成 Skill 安装缺失。
- `client_delivery_ready` 必须由当前依赖快照、Full RC 与生产证据共同决定。

### B4. 验收测试

- production ready run 不执行 Fixture Preview Gate。
- preview run 继续强制 Preview Gate。
- production run 的 Final Readiness blocker 继续阻断 doctor。
- suite 全部安装但 Library blocked 时，阻断类型必须为 `library`。
- `status=blocked` 时 doctor 返回退出码 2。
- 所有 JSON 状态在退出前可被解析。
- 发布 Go Gate 必须传入 exact production run-dir，并要求 `delivery_evaluated=true`。

## 9. 工作流 C：生产依赖可复现

### C1. `ppt-master` 公开绑定

- 生产绑定必须指向公开可获取的 tag。
- Capability Lock 同时记录 remote、tag、完整 SHA 和验证时间。
- tag 指向的 SHA 必须与运行时验证 SHA 一致。
- feature branch 可用于开发，不得作为 RC 发布依赖。
- 依赖契约增加 `public_repo_url`、`release_tag`、`tag_commit_sha` 和 `tag_verified_at`。
- `backend verify` 必须从 canonical HTTPS remote 解析远端 tag，不得只依赖本地 tag cache。
- Capability Lock 保留规范化公开 URL，继续清除 repo path、skill path、SSH remote 和本机路径。

### C2. 依赖快照

- 通过现有生成命令刷新依赖快照，禁止手工编辑 JSON 伪造匹配。
- Suite Status、release tree、capability lock 和 RC report 使用同一份依赖事实。
- 当前依赖发生变化后，旧 RC 报告自动失效。

### C3. 验收测试

- tag 缺失、SHA 不匹配、仓库 dirty、远端不可获取时阻断 Full RC。
- tag 移动返回 blocked/2；远端网络不可用返回 execution error/1，禁止沿用历史 ready。
- release tree 不写入作者本机绝对路径。
- 隔离环境可以从公开来源解析 tag 与 SHA。
- `dependency_snapshot_matches=true` 后才允许 `client_delivery_ready=true`。

## 10. 工作流 D：PPT Library 生产就绪

PPT Library 在独立仓库修复，Deck Master 只维护契约、适配和版本绑定。两边不得通过本机临时文件形成隐式耦合。

跨仓交付必须记录 PPT Library 公共 tag、完整 SHA、Library Status v2 schema 版本、Deck Master adapter 支持范围、clean-environment 验证结果和可回退版本。

### D1. 必需能力

- semantic search ready。
- role selection ready。
- candidate preview ready。
- business ranking ready。
- data hygiene ready。
- Library Status v2 runtime ready。

### D2. 截图与降级规则

- 被选入真实 UAT 的候选页必须有可读取截图。
- 缺截图时，候选不得被标记为完整 preview ready。
- fallback 只能用于 preview/fixture；production 和 benchmark 不允许 fixture fallback。
- 数据卫生阻断必须给出可执行的修复入口和受影响资产数量。
- 截图覆盖率分母使用进入业务排序的全部 eligible candidates。每个 query 记录 requested、returned、eligible、selected、previewable 数量和 candidate IDs，禁止通过删除缺图候选缩小分母。

### D3. 验收

- `library-status.status=ready`。
- PPT Library UAT 无 warning、无 failed。
- 候选截图覆盖率 100%。
- role selection、预览和业务排序各有正向与失败路径测试。
- Deck Master Full RC 的 `library_status_v2_contract` 通过。

## 11. 工作流 E：真实 UAT 与审批证据

### E1. 补齐现有真实案例

现有案例需要补齐：

- 外部叙事审查 task 和 result。
- 外部质量审查 task 和 result。
- 缺失的候选截图。
- 更新后的 UAT 报告和运行指纹。

这些记录必须来自真实 Agent 执行或真实人工审查。不得根据预期结果补写通过记录。

Real Workflow Smoke 必须同时验证 task 与对应 result。Result 必须通过 schema、run ID、scope、reviewer、source fingerprint 和完成状态校验。空目录、仅 task、仅 result、仅文件名匹配或过期 fingerprint 均为 fail。

每类 UAT 必须声明固定 schema、required check IDs 和 expected count。RC Gate 验证检查集完整一致，禁止缺项、重复、skipped、release-blocking warning 和 failed；报告绑定 run ID、候选提交 SHA、依赖快照、最终文件 SHA256 和运行指纹。

### E2. 最终审批

- 审批绑定 run、最终文件 SHA256、审批人、审批时间和 decision。
- 修改最终文件后，旧审批立即失效。
- 审批撤销后，导出凭证立即失效。
- Full RC 只接受工作流原始审批记录与 `final_artifact_approval.json` 同时一致的案例。
- 最终审批必须发生在所有必需质量门禁和 UAT 通过之后。
- 导出队列消费时重新验证审批、最终文件哈希和运行绑定，避免撤销后继续消费旧队列。
- 最终审批时间必须晚于全部必需 UAT 和质量报告完成时间；任一必需报告在审批后更新，旧审批自动失效。

### E3. UAT 通过条件

- Generation UAT pass。
- Render UAT pass。
- PPT Library UAT pass。
- Real Workflow Smoke pass，0 warning、0 failed。
- Final Readiness ready。
- Export Queue 产物数量大于 0，blocked count 为 0。

审批负向测试覆盖审批 JSON 修改、原始审批记录修改、跨 run 复制、拒绝审批、撤销后旧队列消费，以及审批校验至写入队列期间最终文件发生变化。Symlink 测试分别覆盖最终 PPTX、审批文件、工作流原始记录和导出队列；任何关键证据指向 run-dir 外部均失败。

## 12. 工作流 F：三组真实案例与 RC 资格

### F1. 案例覆盖

三组案例应覆盖不同生产形态：

1. 历史模板迁移与重组。
2. 真实材料驱动的新页面生成。
3. 历史资产复用、改写与新增页面混合。

具体材料必须经过授权并保留在本地私有目录。仓库只保存脱敏元数据和汇总。

三组案例必须在执行前冻结各自 `benchmark_case.json`，记录固定 case ID、授权材料摘要、目标页数区间、reuse/adapt/generate 最低占比、输入完整度、受众、交付目标、门禁、是否允许导入既有成品、允许重跑次数和重跑原因。所有失败 run 保留在内部汇总，禁止执行后只挑选成功案例。

历史锁定成品案例只证明迁移、审核与交付控制，不用于证明新页面生成质量。

### F2. `rc_eligible` 硬条件

每组案例同时满足：

- 工作流完成。
- `final_ready=true`。
- `export_ready=true`。
- 所有必需质量门禁通过且无阻断。
- 所有必需 UAT pass。
- Render v2 产生实际文件，产物数量大于 0。
- 无待办步骤。
- 最终审批有效。
- 报告、产物、代码提交和运行指纹一致。

每组案例生成本地 `RC Evidence Manifest`，至少绑定：

- candidate commit SHA；
- release manifest SHA256；
- dependency snapshot SHA256；
- case manifest SHA256；
- case ID、run ID 和 run started at；
- 最终 PPTX、Render manifest、质量报告、全部 UAT、审批和导出队列 SHA256；
- 报告生成器版本。

Aggregate 必须从 Evidence Manifest 和底层证据重新计算资格，不得直接采信报告内的 `eligible=true`。

Evidence Manifest 只能由官方命令原子生成，禁止手工编辑。`run_started_at` 必须晚于候选提交和依赖快照冻结时间；case manifest 变化后，关联 run、Evidence Manifest 和 RC 报告全部失效；Aggregate 记录 Evidence Manifest 自身 SHA256。

### F3. 业务指标

每组案例记录：

- 总耗时。
- Agent 执行耗时和人工等待耗时。
- 返工次数。
- 首次质量通过率。
- 最终就绪与导出结果。
- 质量阻断及处理结果。
- 代码、依赖和运行指纹。

任何效率提升主张必须来自三组案例的真实测量。样本不足时使用“待验证目标”口径。

计时协议统一使用工作流事件：起点为 run 创建并完成输入绑定，终点为客户导出成功；分别记录 Agent active time、工具等待、人工等待和人工操作，失败重跑全部计入总耗时。公开结果提供单案例值、中位数和范围，不从三例外推普遍效率承诺。

### F4. Aggregate 验收

- Full RC 通过一个本地三案例 evidence manifest 接收三组隔离 run，并逐案例输出通过或失败原因。
- 所有计数按唯一 `case_id + run_id` 计算；普通报告与 RC 报告只形成一个资格单元。
- `complete_real_case_pairs=3`。
- `final_ready_case_count=3`。
- `rc_eligible_case_count=3`。
- aggregate status 为 `report_ready`。
- 缺任一审批、成品、渲染、导出或 UAT 证据时 aggregate 失败。
- 重复 case/run、重复材料 fingerprint、报告对不一致、未知 schema 或底层哈希漂移时 aggregate 失败并返回退出码 2。
- Internal Aggregate 记录 `attempt_count`、`failed_run_count`、`superseded_run_ids` 和每次失败原因，确保失败样本可追溯。

Phase 0 先修复 Aggregate emitter 与 `benchmark-aggregate-report` schema 漂移。新增字段必须先进入契约，再进入 emitter 和 RC Gate；旧报告迁移规则必须有测试。

## 13. 工作流 G：首次使用与发布验证

### G1. Fixture Demo 依赖预检

- `scripts/demo.sh` 启动前检查 Python 版本和必需依赖。
- 依赖真源来自 `pyproject.toml`；预检至少覆盖 Python 版本、`jsonschema` 和 CLI import。
- 依赖缺失时输出一条明确的安装命令并返回退出码 2。
- 不自动修改用户 Python 环境。
- 正确环境继续生成 12 页 fixture 并通过 Preview Gate。
- 缺依赖时不得创建任何 run 文件。
- 干净源码 checkout 与隔离 release 安装分别验收；目标 TTHW 为五分钟内完成安装、12 页 Demo 和 Preview Gate。

### G2. 发布包

- release tree 包含 `skills/manifest.json`、`skills/stage-contracts.json` 和对应 SHA256。
- 隔离环境执行 `--help`、`suite-status`、`workflow status`、`next-step`、CI RC Gate。
- release smoke 不读取源码仓文件。
- release manifest、capability lock 和 SHA256SUMS 无私有路径和客户标识。
- Release E2E 使用临时 HOME、仓库外 cwd、清空 `PYTHONPATH`、禁止 editable install，并只使用 release-local Python。
- release tree 不得包含指向源码仓或用户 HOME 的 symlink。CI 默认将源码仓重命名或设置为不可读来验证零读取；文件访问审计只作为补充证据。

### G3. 隐私与公开 Aggregate

- 内部 Aggregate 与 public Aggregate 分离生成。
- Public Aggregate 只允许 case alias、工作流类型、页数、状态和汇总指标。
- 发布验证递归扫描整个 release tree、RC JSON/Markdown、Public Aggregate 和对外证据包。
- 扫描拒绝外部 symlink、绝对路径、客户 denylist、原始 source path、邮箱、Token 和密钥模式，并输出扫描文件数与 `violations=[]`。
- 扫描报告记录 scanner version、rule-set SHA256、扫描文件数、跳过文件数和跳过原因；任何未声明跳过项均失败。

## 14. 数据流与失败边界

```text
公开代码提交
  │
  ├── CI Tier RC ──────────────→ 可公开复现证据
  │
  └── Release Tree ────────────→ 隔离安装与 smoke

授权真实材料（本地）
  │
  └── Production Run
       ├── Library / Generation / Render
       ├── Quality + External Reviews
       ├── Final Readiness
       ├── Human Approval
       ├── Client Export
       └── Benchmark RC Report
                    │
                    ├── Internal Aggregate ─→ Full RC Gate
                    └── Public Aggregate ───→ 对外脱敏证据
```

失败规则：

- 输入缺失：停止在对应阶段，不创建占位产物。
- 外部工具失败：保留 handoff 状态，禁止写入成功报告。
- 报告过期：根据提交、依赖或运行指纹自动失效。
- 最终文件变化：审批和导出资格自动失效。
- 质量出现 P0：禁止 override 和客户导出。
- Full RC 失败：保留 JSON/Markdown 报告并返回退出码 2。
- 预期负向测试返回 blocked 属于测试通过证据，不触发人工生产动作。

## 15. 测试矩阵

| 层级 | 必需验证 |
| --- | --- |
| Python 3.11 | 公开 Preview、基础 CLI、契约与单元测试 |
| Python 3.12 | 生产后端、PPT Library、Render v2、完整 UAT |
| 单元测试 | 模式矩阵、状态归并、退出码、审批哈希、snapshot freshness、`rc_eligible` |
| 集成测试 | Suite Status、Production Doctor、Library Status、Final Readiness、Export |
| 负向测试 | 审批篡改/复制/撤销/竞态、文件篡改、依赖 SHA/tag 漂移、缺截图、UAT 裁剪、报告自声明、重复案例、报告过期 |
| Fixture E2E | 12 页生成、Preview Gate、run-mode 继承、next-step |
| Release E2E | 新目录构建、隔离安装、5 项 smoke、无源码仓读取 |
| Real UAT | 三组预注册真实案例，固定 check 集，全部重新计算为 `rc_eligible` |
| Full RC | 当前版本全部 required checks pass；逐案例证据完整 |

## 16. 分阶段交付与提交顺序

### Phase 0：正式基线

- 整理当前修复集。
- 全量回归与安全扫描。
- 评审后进入迭代分支基线。

### Phase 1：诊断真相

- Production Doctor 模式修复。
- Suite Status 语义统一。
- doctor 退出码统一。
- 定向与全量测试。

### Phase 2：依赖与 Library

- `ppt-master` 公开 tag/SHA。
- 依赖快照刷新。
- PPT Library 修复与绑定升级。
- Library UAT pass。

### Phase 3：真实 UAT

- 将现有案例保留为演练证据并关闭已知三项 warning。
- 候选提交与依赖冻结后重新运行第一组正式案例。
- 全部质量和 UAT 通过后重新审批与导出。
- 使第一组正式案例重新计算为 `rc_eligible=true`。

### Phase 4：三案例闭环

- 完成另外两组授权真实案例。
- 生成脱敏 aggregate。
- 3/3 `rc_eligible`。

### Phase 5：发布验证

- Fixture、CI RC、Full RC、Production Doctor、release smoke 全绿。
- 刷新 release evidence 文档。
- 形成独立 Go/No-Go 决策包。

## 17. Agent 任务包建议

实现阶段建议使用互不重叠的任务包：

| 任务包 | 写入范围 | 交付 |
| --- | --- | --- |
| A：Baseline Integrator | 当前 repair diff、对应 tests/docs | 串行冻结可审查基线，完成后释放文件 ownership |
| B：Diagnostic Truth | doctor、suite status、定向测试 | 独占诊断状态与退出码实现 |
| C：Dependency Closure | backend binding、capability lock、Deck Master adapter | 公开 tag/SHA、snapshot 与跨仓集成 |
| D：Library Readiness | PPT Library 独立仓 | Library Status/UAT pass；不写 Deck Master 仓 |
| E：Evidence Integrity | UAT、benchmark report/aggregate、证据 schema | 先关闭报告自证与 UAT 假阳性 |
| F：Real Cases | 授权本地 run、私有证据与 public aggregate | 3 组重新计算为 `rc_eligible` |
| G：Release Verification | 所有 owner 释放后的 RC/release 文件 | 最终 Go/No-Go；默认不改业务模块 |

同一文件只允许一个写入 owner。A 是所有实现任务的串行前置；A 完成后 B、C、D、E 可按文件 ownership 并行。F 等待 C、D、E；G 等待全部任务完成。真实材料任务包不得把原始材料写入代码仓。

`scripts/skills/installer.py` 由 C 独占。B 独占 `scripts/deck_master.py`，先完成 Doctor 和状态规则测试设计；涉及 installer 的 Suite Status 需求以 patch requirement 交给 C 统一实现。`scripts/runtime/builder_backend.py` 由 C 独占；`scripts/runtime/rc_gate.py` 在 C 完成依赖闭环后移交 E，B/C 最终集成测试串行执行。

## 18. 发布准入与停止条件

### 18.1 Go 条件

- Production Doctor status `ready`。
- Suite Status 的 required capabilities 全部 ready。
- `client_delivery_ready=true`。
- PPT Library Status/UAT pass。
- 三组真实案例 3/3 `rc_eligible`。
- CI RC 和 Full RC 全部 pass。
- release tree 隔离安装和 smoke pass。
- 客户导出审批负向测试全部通过。
- 公开依赖可按 tag 与 SHA 复现。

最终执行顺序固定为：

```text
候选提交冻结
→ 三案例 Evidence Manifest 与报告
→ Full RC 写入报告
→ 刷新依赖与 RC evidence projection
→ Suite Status
→ Production Doctor（传入 exact rc_eligible run-dir）
→ 最终 Go/No-Go 审计
```

### 18.2 Stop and Report

- Production Doctor 返回 blocked。
- required Skill 或 capability 缺失。
- 外部 Agent handoff 等待真实结果。
- Final Readiness 存在 blocker。
- Schema 不匹配且没有迁移路径。
- 需要未授权客户材料或私有后端。
- 任一测试试图通过 fixture 兜底生产或 benchmark。

### 18.3 No-Go 条件

任一 Go 条件未满足时，继续维持 Technical Preview，不创建 1.0 RC tag。

## 19. Definition of Done

本 Spec 完成需要同时满足：

1. 当前修复进入正式可追溯基线。
2. 诊断 JSON、Shell、CI 和 Makefile 对同一状态给出一致结论。
3. Production Doctor 不再读取 Fixture Gate 作为生产阻断。
4. PPT Library 和生产依赖达到公开可复现的 ready。
5. 三组真实案例具备完整成品、质量、审批、导出和指纹证据。
6. Full RC Gate 所有 required checks 通过。
7. 发布包在隔离环境完整通过。
8. 对外文档只包含脱敏汇总和可公开复现信息。

## 20. GSTACK REVIEW REPORT

### Review status

- Product/CEO cross-review：Round 1 为 7.4/10、HOLD；修订后 9.0/10、PASS。
- Engineering plan review：Round 1 为 6.8/10、暂缓；修订后 9.1/10、PASS。
- QA/DevEx adversarial review：Round 1 为 6.6/10、CHANGES_REQUIRED；修订后 8.8/10、PASS。
- Final disposition：Spec 可进入实现拆包；Production Release 继续 HOLD，直到全部 Go 条件通过。

### Review rounds

- Round 1 识别并关闭：报告自证、UAT 空结果/裁剪、三案例重复计数、案例后选、审批攻击面、无 run doctor 假阳性、隐私扫描缺口和 release smoke 借用源码环境。
- Round 2 验证全部 P0 关闭，并补齐 Evidence Manifest 失效链、失败 run 统计、blocking warning、关键证据 symlink、隐私扫描规则版本和文件 ownership。
- 三位 reviewer 全程只读，没有并行修改仓库。

### Review principles

- 只接受能追溯到 1.0 RC 准入的范围。
- 优先复用现有契约和运行时。
- 所有通过结论必须由机器可读证据支持。
- 真实案例证据不得通过补写或 fixture 生成。
- Aggregate 必须从底层证据重新计算，禁止接受报告自声明资格。
