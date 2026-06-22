# A2 — PPT Deck Pro Max Bridge

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A2` |
| Repository | `MainQuestAI/PPT-Deck-Pro-Max` |
| Depends on | A0, A1 contract freeze |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让 PPT Deck Pro Max 可直接消费 Deck Master handoff，并导出 canonical v2 generation results。

## 3. In Scope

- Bridge import。
- Bridge project manifest。
- Page/task ID 保留。
- Agent dispatch context。
- Real artifact export。
- Producer provenance。
- Bridge tests。

## 4. Out of Scope

不维护 Deck Master Run State；不自行声明 final readiness；不重写 Deck Master planner。

## 5. 必须实现

1. 新增 `deck-master-import`。
2. 新增 `deck-master-export`。
3. 将 Deck Master task 映射到 clean page / visual composition / asset jobs。
4. 导出每页 result JSON。
5. 未完成页不得 completed。
6. 输出 producer version、source SHA、artifact checksum。
7. 禁止向 Deck Master Run 外写 canonical state。
8. Bridge 支持 image-led HTML 页面源。

## 6. 允许 / 预期修改路径

- `scripts/run_deck_pipeline.py`
- `scripts/deck_master_bridge.py`（新增）
- `references/deck_master_*.schema.json`
- `tests/test_deck_master_bridge.py`
- `README*` bridge section

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- import fixture handoff。
- malformed handoff。
- ID round-trip。
- page artifact export。
- missing page。
- partial batch。
- checksum。
- no path escape。

## 8. 成功标准

- Deck Master handoff 可一条命令导入。
- 至少 3 页真实 HTML/PNG artifact 导出。
- v2 schema valid。
- 不出现假后缀文件。

## 9. 风险

现有 PPT Deck Pro Max pipeline 状态可能与 Deck Master page task 不一一对应，需要显式 mapping 文件。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
