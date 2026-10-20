# PR127 后续 Web UI：内容理解与方法依据

状态：**开发 Spec v1.1，A/B 已实现、WU08 验证部分完成**。2026-10-20。

本轮让用户在现有工作台中看懂方法依据、论证主线、正文证据及审阅问题，并完成有界的方向采用与修改交接。保留现有五工作面和单页制作链。

这是一次独立于 PR127 的 Web UI 迭代；产品实现和未闭合验收见 [交付回执](../../reports/webui-content-methods/DELIVERY.md)，不表示正式发布。

| 文档 | 用途 |
|---|---|
| [SPEC](SPEC.md) | 产品目标、确定范围、两段增量及完成条件 |
| [BASELINE](BASELINE.md) | PR127 最新核对、旧报告修正、实施启动门槛 |
| [UI-SPEC](UI-SPEC.md) | 页面级布局、交互、文案、状态与响应式 |
| [API-SPEC](API-SPEC.md) | 拟新增读模型、既有写事务、冻结与错误语义 |
| [TASKS](TASKS.md) | WU00–WU08 开发卡、文件边界、依赖及交付 |
| [ACCEPTANCE](ACCEPTANCE.md) | 50 项行为验收及分层验证 |
| [HANDOFF](HANDOFF.md) | PR127 完成后的实施入口 |
| [traceability.json](traceability.json) | 功能—开发卡—验收项的机器可读对应 |
| [inputs/impact-report.md](inputs/impact-report.md) | 原始影响报告快照；状态更新以 BASELINE 为准 |
| [validation.json](validation.json) | 本规格包自身检查；不代表产品测试 |

默认实施顺序：WU00 → WU01 → WU02 → WU03 → WU04 → WU05 → WU06 → WU07 → WU08。每卡完成相称验证后接续，不以文档勾选代替运行证据。

只读接口、字段及能力标识中标为“拟新增”的部分，是本轮开发合同，实施后的准确状态须对照执行账本，不从规格文字推断通过。现行持久 schema 真源仍是 `src/deck_master/resources/contracts/`。

v1.1 修订与原文保存见 [修订记录](REVISION-NOTES.md)。当前 [WU00 执行账本](execution-ledger.json) 已记录父线程确认的最终基线与 CI，G0 通过；完整 WU01–WU08 默认同一独立新 Draft PR。
