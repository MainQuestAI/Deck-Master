# v1.0 → v1.1 修订记录

原始 15 文件由父线程分批转交，14 个 manifest 条目 bytes/SHA 全匹配。原文保留在 Git 提交 `4f7f2a3b`；原包 manifest 保存为 original-package-manifest.json（不含自身 hash）。本版 diff 可用 `git diff 4f7f2a3b -- docs/specs/deck-master-webui-content-methods-20261020 docs/work-items/wi-webui-post-pr127-20261020` 查看。原报告与脚本未修改，脚本未执行。

| 项 | 最小裁决 | 同步验收 |
|---|---|---|
| R1 | can_record_direction_decision / can_adopt / needs_decision，决定复用与部分成功恢复；CAS/证据/原事务保持 | AC19、AC20 |
| R2 | browse/dispatch/selection 独立状态，明确无新阶段 200、expected_basis 冲突 409，始终 preparation_only | AC39、AC41、AC43 |
| R3 | 复用固定 revision Plan 读取，候选仅投影真实可达关联，planned_roles 可无 Page | AC16 |
| R4 | 两份不同合法可达可读 Narrative，支持 current+candidate；历史比较不可写 | AC18 |
| R5 | 删除“旧 v1 finding 无 ID”的错误假设；真实 v1 同样要求 ID/impact/resolution，链接绑定 Ref/revision/ID/索引 | AC27、AC28 |
| R6 | SnapshotRead/ArgumentItem/ObjectRead 判别分支，Review 不可读 data=null，禁止占位业务值 | AC08 |

API-SPEC、UI-SPEC、ACCEPTANCE 与 traceability 同步；9 卡/50 AC、唯一 owner 不变。SPEC/TASKS/HANDOFF 明确全部 WU01–WU08 同一独立 Draft PR，A/B 仅内部增量，确需拆 PR 先说明原因。旧 review 目录只是传输受阻时的历史核对，当前唯一规格入口为本目录 README。

WU00 部分核对已做，G0 仍 pending；产品实现未开始。工程、浏览器、安装、实际 Host、专业阅读、人类认可分层记录。文档检查 PASS 不提升任何产品 AC。

本回合复核结果见 BASELINE.md「本回合只读复核补记」；最新远端观察为 3217a656，未自动升级为最终基线。


## 实施接续状态

以上门槛描述为规格修订时的历史记录。父线程随后确认最终 3217a656 和 CI 39401753812 成功并授权完整实施；当前 A/B 实现与 WU08 未闭合项以 [执行账本](execution-ledger.json) 为准，未宣称全量验收通过。
