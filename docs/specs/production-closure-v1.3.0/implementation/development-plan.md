# v1.3.0 Production Closure — 开发计划

分支建议：`feat/v1.3.0-production-closure`  
主仓：`/Users/dingcheng/Coding-Project/02-key-project/Deck-Master`  
主 Spec：`docs/specs/deck-master-v1.3.0-production-closure-spec.md`  
目标：记录外部 production backend、外部 generation bridge、真实 benchmark 和 RC gate 已收成可验证闭环，并明确后续发布固化事项

## 执行原则

- P1-P5 的主线能力已按依赖顺序完成，后续变更必须保护现有证据链。
- 外部仓修改继续走独立 PR 或独立提交，再回填固定 SHA。
- 每个新增变更完成后都要补真实验证，不接受只写文档、不留证据。
- capability lock、suite-status、Review Desk 三处对同一 readiness 口径必须保持一致。
- raw benchmark source 保持本地私有，不进入 git。
- `production_backend_ready` 与 `client_delivery_ready` 分开治理，前者不能自动代表后者。
- 生产构建路径当前已进入 `awaiting_external_render` handoff；`contract_smoke` 只保留为 backend smoke / fixture / dev 证据，发布口径不能把它写成客户产物来源。
- 当前 closure 证明的是系统级 readiness；单个 run 的最终成片 readiness 仍需外部 render/writeback 回写后单独判断。

## 开发包总览

| 任务 | 仓库 | 核心交付物 | 关键验证 |
|---|---|---|---|
| P1 | `hugohe3/ppt-master` | `deck-master-backend.json`、smoke、兼容文档 | Deck Master backend verify 可通过 required checks |
| P2 | Deck Master | `backend bind/status/verify/unbind`、`backend_bindings.json`、`external_dependencies[]`、状态真相输出 | suite/setup/UI 都能显示已绑定 backend 与 SHA |
| P3 | `PPT-Deck-Pro-Max` + Deck Master | bridge 正式 SHA、cross-repo smoke、bridge lock entry | dispatch → import → export → import-results 闭环可复跑 |
| P4 | Deck Master + 私有资产 | 3 个 real benchmark report、3 个 benchmark RC report、aggregate report | aggregate 从 `metadata_ready` 进入 `report_ready` |
| P5 | Deck Master | RC external dependency closure check、release closure、dogfood evidence | `rc-gate` required failures = 0 |

当前证据状态：

1. P2：`suite-status` / `setup-status` 已能输出 `production_backend_ready=true`
2. P3：`ppt-deck-pro-max` 已固定到 `9444d88f573c3afa567bfb1763041325ef765313`
3. P4：aggregate 已为 `report_ready`，3 个 real case report pair 齐全
4. P5：`rc_reports/rc_gate_report.json` 为 `pass`，required failures 为 0，`external_dependency_closure` 通过
5. 真实 benchmark 报告当前仍显示 `final_ready=false`，因此 run 级最终成片状态不能用本轮 closure 直接替代

## 任务依赖与当前状态

```text
P1
 ↓
P2
 ↓
P3
 ↓
P4
 ↓
P5
```

当前说明：

- P1-P5 的依赖顺序已经完成；
- 后续不应把 P3/P4/P5 当成待实现主线；
- 允许继续补发布证据、Review Desk 展示、browser smoke 和 clean install / dogfood 口径。

## 阶段退出标准

### P1 Exit

1. `ppt-master` 拥有 Deck Master 可读 backend manifest
2. smoke 命令存在并可运行
3. Deck Master backend verifier 能识别 required operations
4. manifest、smoke、最小 writeback 样本都有证据
5. 当前 `client_delivery_ready=true` 建立在 P2-P5 完整证据之上

### P2 Exit

1. Deck Master 可绑定外部 backend
2. capability lock 可写 `external_dependencies[]`
3. `suite-status` / `setup-status` / Review Desk 可读绑定真相

### P3 Exit

1. `ppt-deck-pro-max` bridge 有正式 SHA
2. cross-repo smoke 可复跑
3. capability lock 可记录 bridge 信息

### P4 Exit

1. 三个 real case 目录可解析
2. 三个 real case 都生成真实 report
3. aggregate=`report_ready`

### P5 Exit

1. `external_dependency_closure` check 通过
2. `rc-gate` required failures = 0
3. clean install / dogfood 证据仍建议作为发布增强继续固化

## 后续提交节奏

P1-P5 主线已完成。后续建议按发布固化形成提交：

1. evidence pack 固化与刷新说明
2. release note / RC report 用户可读口径
3. Review Desk 安全展示和 browser smoke / clean install / dogfood 门禁增强

## 风险登记

### 风险 1：发布口径混淆 suite readiness 与 workspace repair

影响：

- `suite-status` 已经 ready，但 `setup-status` 仍可能因为 active workspace 材料缺失显示 repair
- 用户可能误解为 v1.3.0 closure 仍未完成

缓解：

- 发布说明中单列 active workspace repair 边界
- Review Desk 摘要区区分 suite/client delivery readiness 与 workspace material readiness

### 风险 2：`contract_smoke` 被误读为生产客户产物来源

影响：

- backend smoke 证据中仍可能出现 `contract_smoke_output`
- 如果发布文案不加区分，容易误伤 production closure 可信度

缓解：

- 明确生产 build 已进入 `awaiting_external_render` handoff
- `contract_smoke` 仅作为 smoke / fixture / dev 证据

### 风险 3：browser smoke 仍是 optional

影响：

- 当前 RC gate 已支持真实 Review Desk browser smoke
- 但发布策略上仍可选择 optional 或 required
- 如果发布标准要求前端全链路验收，需要把 `--require-browser-smoke` 纳入正式门禁并固定证据路径

缓解：

- 主线程决定 browser smoke 是否升级为 required
- 如升级，补 5050 Review Desk 首页和 run 详情截图或自动化检查

## 交付报告要求

每个任务完成后，Agent 交付报告必须包含：

1. 修改文件
2. 外部仓 SHA
3. 状态 / schema 变化
4. 测试命令与真实结果
5. 未完成项
6. 风险
7. 建议下一任务入口
8. 对 `production_backend_ready`、`client_delivery_ready` 两个状态的明确口径

当前已知口径：

1. `production_backend_ready=true`
2. `client_delivery_ready=true`
3. active workspace repair 是工作区材料边界，需独立说明
4. run 级最终成片 readiness 仍需单列说明，避免与 suite/client delivery readiness 混写
