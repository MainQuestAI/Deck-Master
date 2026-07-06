# Deck Master v1.3.0 Production Closure 执行清单

日期：2026-07-03
状态：已校正到当前实现状态，用于固化 v1.3.0 外部依赖、真实 benchmark 和 RC 收口证据
范围：`ppt-master` 生产后端认证、`ppt-deck-pro-max` bridge 固定化、真实 benchmark、RC 放行
关联仓库：

- Deck Master：`<repo-root>`
- `ppt-master`：`https://github.com/hugohe3/ppt-master`
- `PPT-Deck-Pro-Max`：本地 bridge 分支 `codex/deck-master-bridge`，当前已知 SHA `9444d88f573c3afa567bfb1763041325ef765313`

## 1. 本文定位

本文用于记录 v1.3.0 Production Closure 从执行清单到当前真实实现状态的收口结果，明确：

1. 已经完成的闭环事实。
2. 仍需保留的发布边界。
3. 后续 Spec 应继续固化的证据和口径。
4. 每个阶段的验收依据。

后续正式 Spec 应在本文基础上收敛发布证据、用户可读状态和后续演进边界，避免继续围绕已完成能力补功能。

## 2. 当前真相

截至 2026-07-03 当前仓状态，Deck Master 主仓已经完成 v1.3.0 Production Closure 的核心闭环。P2/P3/P4/P5 的主线事实已从“阻断待实现”更新为“证据已生成，后续关注固化与发布口径”。

### 2.1 `ppt-master` 已进入 production backend 真相

当前 `ppt-master` 的正式源码仓已经明确：

- `hugohe3/ppt-master`

当前 `suite-status` / `setup-status` 已能输出：

1. `ppt-master` binding status 为 `bound_verified`
2. 固定 SHA：`23de38ce5fa8c39003b0643def710afb2a36c892`
3. verified 为 `true`
4. validated capabilities 覆盖 `render`、`smoke`、`writeback`
5. `production_backend_ready=true`

因此，本轮不再把 `ppt-master` 描述成“未被认证”的阻断项。后续重点是保留固定 SHA、验证时间、release lock 和 clean install 证据。

### 2.2 `ppt-deck-pro-max` bridge 已进入 release truth

当前 Deck Master 与 `PPT-Deck-Pro-Max` 的跨仓库 bridge 已具备固定化事实：

1. 来源：`MainQuestAI/PPT-Deck-Pro-Max`
2. bridge 分支：`codex/deck-master-bridge`
3. 固定 SHA：`9444d88f573c3afa567bfb1763041325ef765313`
4. binding status 为 `bound_verified`
5. validated capabilities 覆盖 `dispatch_import`、`generation_result_export`、`result_import_contract`

后续重点是把这组证据作为发布说明和回归检查的固定输入，而不是继续把 bridge 当成待开始范围。

### 2.3 benchmark 已从 metadata 进入真实报告闭环

当前仓库里已经有 3 个 `real_metadata` benchmark case：

- `real_retail_growth`
- `real_manufacturing_geo`
- `real_healthcare_enablement`

当前 `benchmarks/results/aggregate/benchmark_aggregate_report.json` 已经是：

1. `status=report_ready`
2. `benchmark_report=3`
3. `benchmark_rc_report=3`
4. `complete_real_case_pairs=3`
5. complete real case ids 覆盖上述 3 个 case

每个 real case 都已有 `benchmark_report.json` 和 `benchmark_rc_report.json`。raw source 仍遵守 `local_path_only`，不进入 git。

### 2.4 RC gate 已拿到生产闭环证据

当前 `rc_reports/rc_gate_report.json` 为：

1. `status=pass`
2. `required_failures=0`
3. `optional_warnings=0`
4. `external_dependency_closure` 已作为 required check 通过
5. `benchmark_aggregate` 已作为 required check 通过

`suite-status` 当前输出 `production_backend_ready=true`、`client_delivery_ready=true`。`setup-status` 也能透传这两个 readiness 事实，但当前 active workspace 仍有 workspace repair 提示，所以产品口径应区分“套件与交付链路已放行”和“当前工作区材料仍需补齐”。

### 2.5 生产构建路径的边界

生产 build 当前已进入 `awaiting_external_render` handoff 路径。`contract_smoke` 仍可作为 backend smoke / fixture / dev 验证证据，但不应再被写成 production build 的客户交付产物来源。

### 2.6 系统级放行与 run 级最终成片的边界

当前 `suite-status` / `setup-status` / RC gate 已证明系统级闭环成立：

1. 外部 backend 与 bridge 已锁定并验证；
2. benchmark aggregate 已为 `report_ready`；
3. `client_delivery_ready=true` 已建立在 RC 和外部依赖证据之上。

但这组证据不等于每个 production run 都已形成最终客户成片。当前 benchmark 报告仍显示：

1. `readiness.final_ready=false`
2. `export_ready=false`
3. `quality_blocked=true`
4. aggregate `metrics.final_ready_count=0`

因此，v1.3.0 当前闭环证明的是“系统已经具备真实生产交付链路与发布级真相”，每个具体 run 仍要等外部 render / writeback 回写结果后，才能进入最终客户交付判断。

## 3. 核心决策

本轮执行按以下决策推进。

### 3.1 `ppt-master` 以 GitHub 仓为唯一真源

`~/.codex/skills/ppt-master`、`~/.deck-master/current/skills/ppt-master` 这类安装态目录继续保留用于运行，但不再作为生产认证真源。

v1.3.0 的生产后端认证、SHA 固定和 release 追溯，统一以 `hugohe3/ppt-master` 仓为准。

### 3.2 v1.3.0 优先采用“外部依赖固定 SHA”模式

本轮不引入新的 vendoring 方案，也不尝试把完整 `ppt-master` 内化进 Deck Master release tree。

本轮只解决三件事：

1. 外部仓可绑定；
2. 绑定后可认证；
3. 认证后可锁定 SHA 并进入 capability lock。

### 3.3 真实 benchmark 资产留在私有目录

benchmark case 的 raw source 继续遵守当前策略：

- `local_path_only`
- raw source 不入 git
- 仓库只保留 sanitized metadata

### 3.4 执行顺序固定

v1.3.0 的推进顺序固定为：

1. `ppt-master` 认证
2. bridge 固定
3. benchmark 闭环
4. RC 收口

在前一阶段未通过前，不进入后一阶段。

## 4. 四阶段执行清单

## 阶段 A：`ppt-master` 生产后端认证

目标：让 Deck Master 能对 `ppt-master` 给出稳定的生产可用判断。

### A1. 补正式 backend manifest

仓库：`hugohe3/ppt-master`

动作：

1. 在 `skills/ppt-master/` 下补 `deck-master-backend.json`。
2. 明确声明：
   - backend 名称
   - schema version
   - supported contracts
   - `render`
   - `smoke`
   - `writeback`
3. 明确 skill 根目录就是 Deck Master 的 production backend package root。

验收：

1. Deck Master 后端检查不再报 manifest missing。
2. Deck Master 后端检查能读到 `render / smoke / writeback`。

### A2. 补 smoke 路径

仓库：`hugohe3/ppt-master`

动作：

1. 增加一个最小 smoke 入口。
2. smoke 至少覆盖：
   - manifest 解析
   - 关键脚本入口可调用
   - 最小 render/writeback 契约有效

验收：

1. `ppt-master` 可独立运行 smoke。
2. Deck Master 可把 smoke 结果记为 verified evidence。

### A3. 明确 Deck Master 兼容文档

仓库：`hugohe3/ppt-master`

动作：

1. 增加一份 Deck Master backend integration 文档。
2. 文档写清：
   - skill 根目录位置
   - manifest 位置
   - smoke 命令
   - Deck Master 读取的最小契约

验收：

1. 外部仓不再依赖口头约定。
2. Deck Master 可以基于文档与 manifest 自动验证兼容性。

阶段退出条件：

1. `ppt-master` 仓可被 Deck Master 识别为完整 backend package。
2. 生产后端认证在技术上具备可落地前提。

## 阶段 B：Deck Master 主仓绑定与锁定

目标：把“环境里刚好有一个 skill”升级为“正式绑定的外部生产依赖”。

### B1. 增加 backend bind 机制

仓库：Deck Master

动作：

1. 增加 `backend bind` 类入口。
2. 绑定记录至少包含：
   - dependency name
   - repo path
   - skill path
   - git SHA
   - verify status
   - last verified at

验收：

1. 用户可以直接看到当前绑定的是哪个 `ppt-master` repo。
2. 用户可以直接看到当前绑定 SHA。
3. 用户可以直接看到认证状态。

### B2. 扩展 capability lock

仓库：Deck Master

动作：

1. 在 `deck_capability_lock.json` 中增加 `external_dependencies[]`。
2. 每项至少记录：
   - `name`
   - `repo`
   - `git_sha`
   - `validated_capabilities`
   - `verified_at`

验收：

1. release build 产物中能看到外部依赖锁。
2. capability lock 可以回答“当前 release 依赖的外部版本是谁”。

### B3. 扩展状态真相输出

仓库：Deck Master

动作：

1. `suite-status` 增加 `external_dependency_status[]`。
2. `setup-status`、Review Desk 首页增加：
   - 当前 backend 绑定
   - SHA 是否漂移
   - backend smoke 是否通过
   - 当前阻断归属

验收：

1. CLI 与 UI 不再只输出 blocked。
2. 用户能读懂下一步到底是修 backend、修 bridge，还是补 benchmark。

### B4. 对齐 capability copy 与 runtime 口径

仓库：Deck Master

动作：

1. 检查 `product_capabilities/ppt-master/`。
2. 检查 `product_capabilities/ppt-deck-pro-max/`。
3. 确保 capability copy、runtime 判断、release lock 三者口径一致。

验收：

1. production capability 不再停留在旧 operation 集。
2. build / render / generation 的状态含义一致。

阶段退出条件：

1. Deck Master 能正式绑定 `ppt-master`。
2. Deck Master 能把外部依赖写入 capability lock。
3. suite truth 中能看到外部依赖状态。

## 阶段 C：`ppt-deck-pro-max` bridge 固定化

目标：把现有 bridge 从“本机实现”升级成“release 可追溯依赖”。

### C1. 确认正式来源与正式 SHA

仓库：`PPT-Deck-Pro-Max`

动作：

1. 确认 `codex/deck-master-bridge` 是否合入正式主线，或明确保留为独立 bridge 来源。
2. 固定一个正式 SHA。

验收：

1. Deck Master 不再依赖“某个本机目录当前刚好有实现”。
2. bridge 版本有唯一可引用的提交。

### C2. 补 cross-repo smoke

仓库：Deck Master + `PPT-Deck-Pro-Max`

动作：

1. Deck Master 写 `dispatch_package.json`。
2. bridge import dispatch。
3. bridge export `deck_generation_result.v2`。
4. Deck Master import result。
5. run state 正常推进。

验收：

1. 有一条可复跑的 smoke 路径。
2. smoke 结果能进入 release evidence。

### C3. 回填 bridge 到 capability lock

仓库：Deck Master

动作：

1. capability lock 记录 `ppt-deck-pro-max` 外部依赖。
2. release build 将 bridge SHA 写入 lock。

验收：

1. capability lock 中可同时看到 `ppt-master` 和 `ppt-deck-pro-max` 两类外部依赖。

阶段退出条件：

1. generation 外部 bridge 有正式来源。
2. bridge SHA 能进入 release truth。
3. cross-repo smoke 有证据。

## 阶段 D：真实 benchmark 与 RC 收口

目标：把“metadata 已准备”提升为“真实生产闭环已验证”。

### D1. 建 3 个私有 benchmark 目录

位置：`~/deck-master-local-benchmarks/`

动作：

为以下 case 建立私有目录：

- `real_retail_growth`
- `real_manufacturing_geo`
- `real_healthcare_enablement`

每个 case 至少具备：

1. `context_pack.json`
2. `raw/`
3. `workspace/`
4. 最小可运行输入材料

验收：

1. `benchmark_case.json` 中引用的本地路径全部存在。
2. benchmark case 校验通过。

### D2. 逐个 case 跑真实 benchmark

仓库：Deck Master + 外部依赖

动作：

每个 case 依次完成：

1. `benchmark-run`
2. 外部 generation
3. render result
4. 必要人工 review checkpoint
5. `benchmark-report`
6. `benchmark-rc-report`

验收：

1. 每个 case 都产生真实 `benchmark_report.json`。
2. 每个 case 都产生真实 `benchmark_rc_report.json`。

### D3. 重跑 aggregate

仓库：Deck Master

动作：

1. 重新生成 benchmark aggregate report。
2. 检查 aggregate 状态和报告数量。

验收：

1. aggregate 从 `metadata_ready` 进入 `report_ready`。
2. 至少 3 个真实 report 被 aggregate 收到。

### D4. 重跑 RC gate

仓库：Deck Master

动作：

1. 重跑 `release-smoke`。
2. 重跑 `rc-gate`。
3. 如需浏览器验证，再加 browser smoke。

验收：

1. `benchmark_aggregate=pass`
2. required failures = 0
3. RC 报告可作为 v1.3.0 放行依据

阶段退出条件：

1. 3 个真实 benchmark case 全部有 report。
2. aggregate 为 `report_ready`。
3. RC gate required checks 全绿。

## 5. 三条泳道分工

为了避免本轮又回到“Deck Master 里补很多代码，但外部链路没真收口”，执行时按三条泳道组织。

| 泳道 | 主要对象 | 核心产物 |
|---|---|---|
| 外部后端泳道 | `ppt-master` | backend manifest、smoke、兼容文档 |
| 外部 bridge 泳道 | `PPT-Deck-Pro-Max` | 固定 SHA、cross-repo smoke、bridge evidence |
| 主仓治理泳道 | Deck Master | backend bind、capability lock、状态输出、RC 收口 |

benchmark 私有资产作为第四类前置条件单独准备，但不进入 git。

## 6. 风险与前提

### 6.1 最大风险

当前最大风险已经从“核心功能未完成”转为“发布证据和用户口径需要继续固化”：

1. `setup-status` 的 suite/client delivery 已放行，但 active workspace 仍可能因为材料缺失提示 repair，需要在产品文案中清楚区分；
2. `contract_smoke` 仍会出现在 backend smoke 证据里，需要避免被误读为生产客户产物来源；
3. 浏览器 smoke 当前已经具备真实 Review Desk 验证能力，但是否升级为正式 required gate，仍需在发布策略中决定。

### 6.2 依赖前提

本清单执行前，默认前提如下：

1. `ppt-master` 仓允许补充 Deck Master backend manifest；
2. `PPT-Deck-Pro-Max` bridge 可以固定正式 SHA；
3. benchmark 私有目录允许在本机建立，并只存本地引用；
4. Deck Master 主仓继续采用外部依赖固定 SHA 路线，不在 v1.3.0 引入 vendoring 改造。

## 7. 完成定义

按当前仓状态，v1.3.0 Production Closure 的核心完成定义已经满足：

1. `ppt-master` 已通过 production backend 认证；
2. `ppt-deck-pro-max` bridge 已有正式来源和固定 SHA；
3. capability lock / suite truth 已能写出和读取外部依赖；
4. 3 个 real benchmark case 全部有真实 report 与 RC report；
5. benchmark aggregate 已进入 `report_ready`；
6. `rc-gate` required failures = 0；
7. CLI、setup status、suite status 已对 production backend 和 client delivery 给出一致放行口径。

仍需人工继续关注：

1. Review Desk 首页是否已经用同一套摘要展示，且不泄露绝对路径；
2. 当前 active workspace repair 是否属于本轮发布阻断；
3. browser smoke 是否要从 optional 证据提升为正式发布门禁。
4. run 级最终成片 readiness 何时作为单独发布口径或后续版本目标单列管理。

## 8. 下一文档

本文之后的 Spec 重点应转向发布固化，覆盖：

1. 当前 evidence pack 的固定路径、生成命令和刷新策略；
2. release note / RC report 对 `production_backend_ready`、`client_delivery_ready` 的用户可读解释；
3. active workspace repair 与 suite readiness 的边界说明；
4. browser smoke、Review Desk 截图和 clean install 的正式发布门禁选择；
5. 后续演进项与本轮闭环事实的分界。
