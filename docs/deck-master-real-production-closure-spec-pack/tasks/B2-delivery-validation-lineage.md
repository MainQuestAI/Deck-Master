# B2 — Delivery Validation & Lineage

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B2` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B1 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

修复交付验证的弱失败，并建立最终版本 lineage。

## 3. In Scope

- delivery validator。
- required formats。
- page count。
- source fingerprint。
- gate snapshot。
- review snapshot。
- final lineage。

## 4. Out of Scope

不决定最终 ready；该结论由 B3 聚合。

## 5. 必须实现

1. Parse failure 生成 P0。
2. 必需产物缺失 P0。
3. 页数不一致 P0。
4. stale P0。
5. 客户要求 native 但 flat-image 为 P1。
6. 写 `final_version_lineage.json`。
7. 保存 gate / approval refs 和 hashes。
8. 验证结果可重跑且幂等。

## 6. 允许 / 预期修改路径

- `scripts/delivery/validate.py`
- `scripts/delivery/lineage.py`（新增）
- `scripts/quality/gate_runner.py`
- `tests/test_delivery_validation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- invalid pptx。
- missing PDF。
- page mismatch。
- stale。
- flat/native requirement。
- gate snapshot。
- idempotency。

## 8. 成功标准

- 任何不可解析交付文件都不能 pass。
- lineage 可追到每页输入和 producer。

## 9. 风险

Lineage 文件可能较大，应保存 refs 和 hashes，不复制全部内容。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
