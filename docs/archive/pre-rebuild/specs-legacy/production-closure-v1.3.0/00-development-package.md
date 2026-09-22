# Deck Master v1.3.0 Production Closure 开发包总控

日期：2026-07-03  
状态：Current Implementation Sync  
主 Spec：[`../deck-master-v1.3.0-production-closure-spec.md`](../deck-master-v1.3.0-production-closure-spec.md)  
执行入口：[`README.md`](./README.md)｜[`implementation/development-plan.md`](./implementation/development-plan.md)

## 1. 这份文档解决什么问题

这份文档用于把 v1.3.0 当前的规划、真实实现状态、分包边界和后续发布固化方向收成一份总控说明。

它回答四个问题：

1. 当前这一轮已经做到哪一步
2. P1-P5 每个开发包各自负责什么
3. 哪些问题已经闭环，哪些仍是发布边界
4. 接下来和 ChatGPT 讨论时，应该固化哪些证据与口径

## 2. 当前阶段事实

截至 2026-07-03 当前仓状态，v1.3.0 可以明确分成两段：

### 2.1 已经闭环的部分

1. `ppt-master` 已经进入 `bound_verified`，并可作为 production backend 真相
2. Deck Master 主仓已具备 `backend bind/status/verify/unbind` 相关能力
3. `suite-status`、`setup-status` 已能输出外部依赖真相
4. `deck_capability_lock.json` / suite truth 已承载 `external_dependencies[]`
5. `ppt-deck-pro-max` bridge 已固定 SHA：`9444d88f573c3afa567bfb1763041325ef765313`
6. 3 个 real benchmark case 已生成 report / RC report 成对证据
7. aggregate 已进入 `report_ready`
8. `rc-gate` 已通过，required failures 为 0

### 2.2 仍需发布固化的部分

1. Review Desk 是否已经用安全摘要完整展示同一套 readiness
2. active workspace repair 是否纳入本次 release 风险说明
3. browser smoke 是否从 optional 证据提升为正式发布门禁
4. clean install / dogfood 证据是否需要追加到发布包
5. run 级最终成片 readiness 是否与 suite/client delivery readiness 分开列示

### 2.3 当前最关键的判断

这一轮的主判断很明确：

1. v1.3.0 的难点已经从“本仓缺少功能”转成“发布证据和用户口径要稳定”
2. 后续开发包应围绕 evidence pack、release note、Review Desk 展示和回归门禁推进
3. P2/P3/P4/P5 的主线能力不要再被当成待开始功能
4. 当前闭环是系统级、发布级闭环；单个 run 的最终成片仍需外部 render / writeback 结果支撑

## 3. 当前分支的已知问题

以下问题已经在本轮实现中暴露出来，属于开发包设计必须正面处理的内容：

### 3.1 P2 真相分裂已收口为回归风险

此前分支暴露过四个典型风险，当前应作为回归检查保留：

1. release lock 写入时过早把 backend 视为 `bound_verified`
2. backend binding 已验证，但 runtime 仍未接通时，状态表达容易看起来像 `ready`
3. 环境变量 override 还可能绕开正式 binding registry
4. `setup-status` 的外部依赖 schema 仍然偏松，公开契约不够硬

### 3.2 P3-P5 已拿到外部事实

1. `ppt-deck-pro-max` bridge 已有 release 级 SHA 锁定
2. benchmark 已有真实 report，不再停留在 metadata 层
3. RC gate 已拿到完整的外部依赖闭环证据

## 4. 开发包总览

| 包 | 名称 | 核心对象 | 解决的问题 | 当前状态 |
|---|---|---|---|---|
| P1 | PPT Master Backend Certification | `hugohe3/ppt-master` | backend 具备可认证入口 | 已完成 |
| P2 | Deck Master Backend Binding And Lock | Deck Master 主仓 | Deck Master 正式绑定、显示、锁定外部 backend 真相 | 已完成，需保留回归证据 |
| P3 | PPT Deck Pro Max Bridge Lock And Smoke | `ppt-deck-pro-max` + Deck Master | generation bridge 进入 release truth | 已完成，SHA 已固定 |
| P4 | Real Benchmark Execution Closure | Deck Master + 私有资产 | 3 个 real report + aggregate 真正可用 | 已完成，aggregate=`report_ready` |
| P5 | RC Gate Dogfood Release Closure | Deck Master | RC 全绿、clean install、5050 dogfood | RC gate 已完成，dogfood/browser 证据待发布口径确认 |

## 5. 每个开发包的边界

### 5.1 P1 负责什么

P1 只负责把 `ppt-master` 提升到“可认证 backend 包”。

P1 交付后应当能回答：

1. 这个外部仓是不是 Deck Master 认识的 backend
2. 它有没有 manifest、smoke、writeback 最小能力

P1 不负责：

1. Deck Master 如何绑定这个 backend
2. release lock 如何记录这个 backend
3. client delivery 是否已经放行

### 5.2 P2 负责什么

P2 只负责把外部 backend 真相收进 Deck Master 主仓。

P2 交付后应当能回答：

1. 当前绑定的 backend 是谁
2. 当前绑定 SHA 是谁
3. 当前 release 锁定的是谁
4. 当前 readiness 的证据来源是什么，若回归失败应从哪里排查

P2 不负责：

1. `ppt-deck-pro-max` bridge 正式来源
2. 真实 benchmark
3. RC gate 最终放行

### 5.3 P3 负责什么

P3 只负责 generation bridge 的 release truth。

P3 交付后应当能回答：

1. 当前 generation bridge 来源仓是谁
2. 当前固定 SHA 是谁
3. dispatch/import/export/import-results 这一条链能不能复跑

P3 不负责：

1. benchmark 资产准备
2. RC gate 汇总放行

### 5.4 P4 负责什么

P4 只负责 benchmark 从 metadata 进入 real report。

P4 交付后应当能回答：

1. 三个真实 case 有没有跑出真实 report
2. aggregate 是不是已经从 `metadata_ready` 进入 `report_ready`

P4 不负责：

1. release 安装树重建
2. RC gate 放行策略本身

### 5.5 P5 负责什么

P5 只负责最终放行闭环。

P5 交付后应当能回答：

1. `rc-gate` required failures 是否清零
2. clean install 是否通过
3. 5050 Review Desk 与 CLI 口径是否一致
4. 当前版本是否具备 release closure 证据

## 6. 包与包之间的依赖条件

```text
P1 -> P2 -> P3 -> P4 -> P5
```

更具体地说：

1. P2 入口条件：P1 已经证明 backend package 可认证
2. P3 入口条件：P2 已经把 backend 真相、SHA、lock 写入主仓口径
3. P4 入口条件：P3 已经把 generation bridge 来源锁死，避免 benchmark 报告漂移
4. P5 入口条件：P4 已经拿到真实 aggregate report，否则 RC 结论不成立

## 7. 当前建议的执行顺序

原执行顺序如下，当前主线已完成：

1. 先收掉 P2 剩余真相问题
2. 再写 P3 bridge 固定和 cross-repo smoke 的正式 Spec
3. 然后写 P4 real benchmark 执行 Spec
4. 最后写 P5 RC gate / dogfood / release closure Spec

当前后续顺序应调整为：

1. 先冻结当前 evidence pack：aggregate、RC gate、suite-status、setup-status
2. 再收发布口径：`production_backend_ready`、`client_delivery_ready`、workspace repair 边界
3. 然后确认 Review Desk 安全展示与 browser smoke 是否纳入发布门禁
4. 最后把后续演进项移出 v1.3.0 closure 范围

## 8. 推荐的后续 Spec 关注点

接下来如果要和 ChatGPT 讨论后续 Spec，建议按下面顺序收口：

### 8.1 先写 Evidence Pack 固化 Spec

这份 Spec 重点要锁四件事：

1. aggregate / RC gate / suite-status / setup-status 的刷新命令
2. 证据文件固定路径
3. 发布前人工核对清单
4. raw benchmark source 不入 git 的保护规则

### 8.2 再写 Release Messaging Spec

这份 Spec 重点要锁四件事：

1. `production_backend_ready=true` 的用户可读解释
2. `client_delivery_ready=true` 的证据边界
3. active workspace repair 的非混淆说明
4. `awaiting_external_render` handoff 与 backend smoke 的边界

### 8.3 最后写 Release Gate Enhancement Spec

这份 Spec 重点要锁四件事：

1. browser smoke 是否提升为 required
2. clean install / 5050 dogfood 的证据格式
3. Review Desk 无绝对路径泄露的验收方式
4. release closure 报告的最终样式

## 9. 每个开发包必须回答的统一问题

后续不管写证据固化、发布口径还是发布门禁增强，都必须回答同一套问题：

1. 这包解决哪个单一问题
2. 它依赖哪个上游包完成
3. 它允许改哪些路径
4. 它禁止顺手扩哪些范围
5. 它改完后，CLI / lock / Review Desk / RC 各自会看到什么变化
6. 成功标准是什么
7. 真实验证命令和证据是什么
8. 如果没做完，剩余点属于代码、外部仓、私有资产，还是人工决策

## 10. 当前建议的管理口径

这轮开发建议按下面口径管理：

1. P1-P5 主线能力视为已完成
2. P2-P5 的旧阻断描述只保留为历史背景，不能再作为当前执行判断
3. 后续主包应转向证据固化、发布口径和门禁增强
4. suite/client delivery readiness 已可作为系统级放行真相
5. run 级最终成片 readiness 继续单列管理，避免与当前 closure 混淆
6. 任何新增能力都必须单独立项，避免混入 v1.3.0 closure

## 11. 交付建议

这份开发包总控文档同步后，后续动作建议固定成三步：

1. 先冻结当前 evidence pack 和发布前核对清单
2. 再补 release note / RC report 的用户可读说明
3. 最后决定 browser smoke、Review Desk 截图、clean install / dogfood 是否作为正式发布门禁

## 12. 关联文档

1. [`README.md`](./README.md)
2. [`implementation/development-plan.md`](./implementation/development-plan.md)
3. [`implementation/P2-deck-master-backend-binding-and-lock-implementation.md`](./implementation/P2-deck-master-backend-binding-and-lock-implementation.md)
4. [`tasks/P2-deck-master-backend-binding-and-lock.md`](./tasks/P2-deck-master-backend-binding-and-lock.md)
5. [`tasks/P3-ppt-deck-pro-max-bridge-lock-and-smoke.md`](./tasks/P3-ppt-deck-pro-max-bridge-lock-and-smoke.md)
6. [`tasks/P4-real-benchmark-execution-closure.md`](./tasks/P4-real-benchmark-execution-closure.md)
7. [`tasks/P5-rc-gate-dogfood-release-closure.md`](./tasks/P5-rc-gate-dogfood-release-closure.md)
