# Stack B — Production Boundary & Autopilot v2

## 目标

把 Sourcing、Producer、Builder 的职责和 Artifact 边界固定，并让 Autopilot 按 Stage Contract 和 Approval Policy 工作。

## 包含任务

- B1 Forcing Questions & Decision Log
- B2 Sourcing Plan v2
- B3 Page Package v1 & Producer Contract
- B4 Build Manifest v2 & Builder Whitelist
- B5 Autopilot v2

## 关键约束

- Production Builder 不再直接消费旧 Preview Manifest。
- Builder 只能读取 Page Package 白名单字段。
- Sourcing Plan 不得包含最终页正文。
- Producer 不得构建最终文件。
- Autopilot 不得自行接受高影响 Handoff。

## Stack Exit Criteria

- 一个新 Production Run 可从 approved planner handoff 走到 Quality Handoff。
- Brief / Planner / Sourcing 审批按策略停顿。
- Producer required pages 均有 valid Page Package。
- Builder customer-visible leakage test 为 0。
- Repair mode 可按 finding owner 返回正确 Stage。
