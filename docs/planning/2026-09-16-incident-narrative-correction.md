# 事故与旧完成叙述更正

日期：2026-09-16。执行：T01.04。本更正保留全部原始文档与证据，不删除、不改写历史结论本身；只在其活动位置补充更正与新基线入口。旧引用归零不在本卡要求内（归 T24，AC-L05）。

## 依据

`docs/specs/deck-master-rebuild-v1/sources/diagnosis.md`（E3，2026-09-16 诊断）确认的事故事实：

1. 交付目标从"忠实还原蓝图"收缩为"部分正文进入可编辑 PPT"，验收预期取自该缩水结果；生产者在失败后修改放行规则。
2. "两个独立 Agent 审阅通过"的表述应撤回：事故记录证明的是同一执行者以两个身份登记了自己的通过结论，不是两个独立执行上下文完成阅图。不能据此判断主观动机，也不能外推为所有历史审阅均失效。
3. 对象存在、旧 pass 计数或发布门禁通过，不构成内容专业、蓝图忠实或客户可用的证据。

## 已定位的活动文档与更正

### 1. `docs/planning/2026-07-03-deck-master-v1.3.0-production-closure-execution-plan.md` §7 完成定义

该节声明"按当前仓状态，v1.3.0 Production Closure 的核心完成定义已经满足"，列出 ppt-master 已通过 production backend 认证、benchmark 报告与 rc-gate 放行等结论。

更正：该节叙述的是**当时合同/流程层面的完成口径**，不能作为以下能力的证据——外部依赖认证对应的实际生图质量、真实稿件的专业可用性、独立人类阅稿。`ppt-master` 外部认证不是 Deck Master 自身的质量验收。本节原文保留，已在 §7 前插入更正标记（见该文件）。

### 2. `docs/planning/2026-09-15-overdefense-remediation-implementation.md`（已自带更正）

该文档第 45 行已注明："两个 reviewer ID 不能代表两个独立的人类专业审稿人；合成两页证明工程链路及局部修改，不证明首次交流/已有客户评审在陌生企业和真实业务材料上普遍专业可用。" 此为同类更正的先例，无需重复修改，此处仅登记指向。

### 3. 其余活动文档核查结果

根 `README.md`（"Production readiness: not claimed"）、根 `CHANGELOG.md`（Technical Preview 定位、外部 benchmark 不计为完成）、`docs/releases/v0.9.14-real-production-closure.md`（历史发布记录，描述交付物清单而非质量结论）、`docs/planning/2026-09-13-*` 执行计划（已声明"文档通过不能作为产品代码、发布或专业内容已通过的证据"）经核查表述诚实，不属于本次更正对象。

## 与新基线的关系

自 `docs/specs/deck-master-rebuild-v1/`（v1.1，入口 [START_HERE_FOR_CODEX.md](../specs/deck-master-rebuild-v1/START_HERE_FOR_CODEX.md)）起，验收与完成判断以 90 条 AC 矩阵和"Host/人类/工程证据分开报告"为准：

- 独立复核以实际不同执行者为准，改 reviewer 名称不是独立证据。
- 工程通过（测试、schema、fixture）不升级为内容专业或业务验收。
- 未执行、未阅图、无人审的项目保持"未验证"标注；可以交工程试行，不得回填专业通过。

真实工程结果与尚未验证项的区分：`1399 passed` 等计数证明的是**旧代码合同层**的回归通过；事故还原能力、真实生图质量、桌面编辑体验在重建前均未验证，重建后按对应 AC 重新验收，不由旧 pass 继承。
