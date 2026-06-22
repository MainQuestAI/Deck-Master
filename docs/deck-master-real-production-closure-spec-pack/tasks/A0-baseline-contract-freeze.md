# A0 — Baseline & Contract Freeze

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A0` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | None |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

锁定三仓实际开发起点、能力版本和本轮 canonical contract，防止后续按不同假设并行开发。

## 3. In Scope

- 核验三仓 HEAD。
- 核验全量测试。
- 核验本机 suite、依赖和安装冲突。
- 提交 implementation spec、baseline lock、capability lock 草案。
- 冻结 schema 名称、状态语义和 CLI 名称。

## 4. Out of Scope

不实现业务功能；不修复现有代码。

## 5. 必须实现

1. 新增 `baseline-lock.json`。
2. 新增 `implementation-spec.md`。
3. 新增 `implementation-spec.json`。
4. 新增 `spec-deviation-log.md`。
5. 生成三仓 source SHA 和 dependency inventory。
6. 确认真实 benchmark 候选项目。

## 6. 允许 / 预期修改路径

- `docs/specs/real-production-closure/implementation/`
- `docs/contracts/`
- `product-capability-manifest.json`（仅必要 metadata）
- `capability-lock.json`（新增）

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- JSON parse。
- Schema lint。
- `git diff --check`。
- 记录全量测试基线，不允许伪造通过。

## 8. 成功标准

- 所有 SHA 明确。
- 所有 contract 名称无冲突。
- 每个后续 Task 的依赖可定位。
- 评审明确以实际 implementation spec 为 baseline。

## 9. 风险

最大的风险是跨仓库 HEAD 变化。必须先 pin，再开发。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
