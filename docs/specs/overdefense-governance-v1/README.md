# Deck Master 过度防御治理 v1

日期：2026-09-01  
状态：Iteration Spec  
主 Spec：[`00-master-spec.md`](./00-master-spec.md)  
执行计划：[`implementation/development-plan.md`](./implementation/development-plan.md)  
验收矩阵：[`acceptance/acceptance-matrix.md`](./acceptance/acceptance-matrix.md)

## 1. 本包定位

本包把 2026-09-01 全仓过度防御审查发现的 19 个活跃问题和 1 个历史残留，收成一轮可执行治理规格。

核心目标很直接：让 Deck Master 能从已确认的故事线和风格继续生成可编辑 PPTX，不再被不存在的密钥、不可操作的人工证明、正常业务词误杀、历史报告永久 veto 和角色盲质量门禁卡死。

## 2. 成功口径

完成本治理包后，一条生产 PPT 链路必须满足：

1. 用户确认故事线和风格后，运行态进入真实生成，不要求聊天里粘贴密钥。
2. `制作`、`投标`、`评审`、`评分`、`内部`、`Brief` 等正常业务词不会被默认当成 P0。
3. 客户可见安全检查只检查真实客户可见内容，不扫描内置 slide layout / master 的默认占位元数据。
4. 高密度构建完成后，`next-step` 不会反复返回同一条 render gate。
5. 质量报告只对当前 artifact 生效，过期报告不能永久阻断最终放行。
6. P1 override 在导出队列、最终 readiness 和 delivery validation 三处语义一致。
7. 批量页审阅、角色化图片策略、页面角色化证据规则全部可用。

## 3. 文档结构

```text
overdefense-governance-v1/
  README.md
  00-master-spec.md
  implementation/
    development-plan.md
  acceptance/
    acceptance-matrix.md
```

## 4. 执行建议

按四个治理阶段执行：

1. `ODG-A`：先修 P0 闭锁和误杀。
2. `ODG-B`：再清掉不存在的人工证明链和不可操作审批链。
3. `ODG-C`：再做页面角色化和批量审阅，降低 64 页生产成本。
4. `ODG-D`：最后收口输出 profile、历史报告、watch 和残留文档。

每个阶段都必须有一条干净 happy path 验收。不能只证明坏输入会被拦。
