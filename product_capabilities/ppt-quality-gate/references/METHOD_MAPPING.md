# ppt-quality-gate 方法/代码/参考资料映射（SC-1 C1 前置）

| 类别 | 资产 | 位置 | 用途 |
|---|---|---|---|
| 代码 | 外部语义审查协议 | `scripts/quality/external_review.py` | 任务/结果契约、独立性证据、Runtime 校验 |
| 契约 | external quality review v2 | `docs/specs/sc1-solution-core-independence/contracts/external-quality-review.v2.schema.json`（目标） | 六维量规词表 |
| 方法 | 语义审查与定向返修 | `skills/deck-master/references/methods/semantic-review-and-repair.md` | 审查观察、返修任务、复审范围 |
| 提示词 | 审查 prompt | `skills/deck-master/prompts/quality_reviewer.prompt.md` | v1 五维 → v2 六维升级在 PR-06 落地 |

工程门（结构/一致性）与语义审查分离：哈希/receipt 证明“查过什么”，不证明内容真实（D11）。
