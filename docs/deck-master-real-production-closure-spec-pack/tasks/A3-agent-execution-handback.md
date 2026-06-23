# A3 — Agent Execution Package & Handback

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1, A2 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把 Production generation 从假 subprocess 改为真实 Agent 驱动任务包，并自动验证回写。

## 3. In Scope

- prepare / dispatch / import。
- Codex-first skill instructions。
- Bridge invocation guidance。
- Execution receipt。
- Batch import。

## 4. Out of Scope

不内置模型 API；不在 CLI 后台异步等待 Agent。

## 5. 必须实现

1. 移除 Production bundled fake execution。
2. `dispatch` 输出可直接供 Agent 执行的 package。
3. 状态为 `awaiting_agent_execution`。
4. 支持 batch result import。
5. 每次 import 写 receipt。
6. 已导入结果幂等。
7. Agent 失败可恢复。
8. Fixture adapter 迁入 test-only。

## 6. 允许 / 预期修改路径

- `scripts/capabilities/ppt_deck_pro_max.py`
- `scripts/generation/dispatch.py`（新增）
- `scripts/generation/session.py`
- `skills/ppt-deck-pro-max/`
- `skills/deck-master/playbooks/`
- `tests/`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- Production dispatch。
- Fixture dispatch。
- no executor。
- batch partial import。
- duplicate import。
- retry。
- receipt and event。

## 8. 成功标准

- Production 命令不生成 placeholder。
- Agent package 包含完成任务所需上下文。
- Agent 完成后可一条 import 命令回写。

## 9. 风险

需要避免 Agent package 泄露超出 Run 的客户资料；只打包允许的 source refs。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
