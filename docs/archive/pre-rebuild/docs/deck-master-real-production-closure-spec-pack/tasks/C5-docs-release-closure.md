# C5 — Documentation & Release Closure

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1-C4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让安装、使用、故障诊断、能力边界和发布说明与真实实现一致。

## 3. In Scope

- README。
- Quick start。
- Agent guide。
- Migration。
- Troubleshooting。
- Release notes。
- Architecture update。
- Known limitations。

## 4. Out of Scope

不写超出实现的市场承诺。

## 5. 必须实现

1. 一条最短 Production path。
2. 一条 Agent path。
3. Build profiles 和 editability。
4. Fixture boundary。
5. Install/upgrade/rollback。
6. Benchmark 结果。
7. Known limitations。
8. 删除旧 placeholder 叙述。

## 6. 允许 / 预期修改路径

- `README*`
- `docs/releases/`
- `docs/guides/`
- `skills/*/SKILL.md`
- `docs/specs/index`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- docs command smoke。
- link check。
- CLI help parity。
- forbidden stale command scan。

## 8. 成功标准

- 文档命令可执行。
- 对外口径与 RC 证据一致。
- 不再把 flat-image 说成 fully editable。

## 9. 风险

文档最容易滞后，必须从 CLI help 和 schema 自动生成部分内容。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
