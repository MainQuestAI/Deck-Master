# Deck Master 下一轮完整迭代方案与开发 Spec

- 文档版本：1.0
- 编制日期：2026-10-19
- 开发基线：`a08bc68c1cbbbc806205104c2bb01f3f096305f0`
- 当前源码版本：`1.0.0rc3`
- 建议候选版本：`1.0.0rc4`
- 状态：**开发输入已编制；本轮产品实现与验收尚未执行。**
- 适用范围：已获用户认可的 N1–N6 六项增量。本包不是正式发布、合并或本机激活记录。

## 决策摘要

保留当前 Runtime、不可变对象、revision/CAS、Host Task、四 Skill 和原生图片 → SVG → 可编辑 PPT 生产链。下一轮先修复恢复和内容合同缺口，再减少上下文与历史读取成本，最后以正常材料任务验证并实际改进首稿与返修质量。

本轮交付不是“只清理代码和补文档”。N6 必须产出可定位的方法或布局改进，并应用于实际内容与产物。工程测试、Agent 的实际检查、用户认可、真实使用反馈分别记录，不能相互替代。

## 阅读入口

| 文件 | 用途 |
|---|---|
| [01-ITERATION-PLAN.md](01-ITERATION-PLAN.md) | 目标、六项范围、资源分配、迭代顺序与完成定义 |
| [02-BASELINE-AND-DECISIONS.md](02-BASELINE-AND-DECISIONS.md) | 固定基线、审查事实、设计裁决及不做事项 |
| [03-ARCHITECTURE-AND-COMPATIBILITY.md](03-ARCHITECTURE-AND-COMPATIBILITY.md) | 架构边界、跨卡接口、协议与存量兼容 |
| [04-EXECUTION-PLAN.md](04-EXECUTION-PLAN.md) | 可执行批次、并行方式、文件所有权、集成与回退 |
| [05-ACCEPTANCE.md](05-ACCEPTANCE.md) | 验收规则、必要回归、证据与完成条件 |
| [06-CODEX-HANDOFF.md](06-CODEX-HANDOFF.md) | 可直接交给 Codex 的完整执行指令 |
| [task-cards/](task-cards/) | N1–N6 的具体开发任务与唯一 AC 判据 |
| [traceability.json](traceability.json) | AC → 唯一 Owner → 任务卡/验证主题的可校验映射 |
| [templates/execution-ledger.json](templates/execution-ledger.json) | 当前候选的执行台账模板，初始 NOT_RUN |
| [templates/quality-observation.json](templates/quality-observation.json) | N6 的正常任务观察与改进记录模板 |
| [tools/validate_spec.py](tools/validate_spec.py) | 本包结构与追踪关系校验；不验证产品实现 |
| [VALIDATION.md](VALIDATION.md) | 本次 Spec 包的实际校验记录 |

建议后续将包内正文置于仓库 `docs/specs/deck-master-next-iteration-20261019/`，以 AGENTS/README 中的单一链接进入。当前包交付不修改产品仓库。

## 规则的唯一来源

1. 用户本轮明确指令优先。2026-10-18 已取消的固定实验、固定听众人数和真人试讲，不恢复成隐含门槛。
2. 跨任务设计以 [02 的 D01–D14](02-BASELINE-AND-DECISIONS.md#3-设计裁决) 和 [03 的接口合同](03-ARCHITECTURE-AND-COMPATIBILITY.md) 为准。
3. 每条 AC 的具体 Given/When/Then 仅在对应任务卡维护；总验收文件和 JSON 索引只引用。
4. 每个候选只有一份执行台账维护 PASS/FAIL/BLOCKED/NOT_RUN/NOT_APPLICABLE。历史报告不随当前候选改写。
5. Runtime schema 真源继续是 `src/deck_master/resources/contracts/`；既有唯一 spec 镜像同步更新，不另复制一套活动 schema。
6. 本包中的新能力名和路径属于目标设计，不能据此报告当前产品已经支持。

## 六张开发卡

- [N1：输入更新、操作恢复与入口一致性](task-cards/N1-operation-recovery.md)
- [N2：安装事务与中断恢复](task-cards/N2-install-recovery.md)
- [N3：论证结构、Review 派发与方法依据](task-cards/N3-content-review.md)
- [N4：工作上下文去重与操作历史索引](task-cards/N4-context-and-history.md)
- [N5：活动文档、版本入口与冗余治理](task-cards/N5-docs-and-release.md)
- [N6：正常任务中的首稿与返修效果改进](task-cards/N6-quality-improvement.md)

## 使用本包时的状态边界

“Spec 包通过校验”只表示文档、AC 和执行输入自洽。产品当前行为以固定 SHA 的代码与实际运行证据为准。后续执行环境、用户本机安装位置/版本、工具可用性以及新候选结果均**需要 Codex 核验**。

