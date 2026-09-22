# B4 — Export & Review Workspace Enforcement

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B3 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让 Export 和工作台严格服从 final readiness。

## 3. In Scope

- Export gate。
- UI final readiness。
- artifact inspection。
- approval。
- delivery package。

## 4. Out of Scope

不重写页面审查交互。

## 5. 必须实现

1. Client export 前强制 final readiness ready。
2. Internal export 可降级但必须标记。
3. Delivery package 包含 artifact manifest、lineage、readiness、approvals。
4. UI 展示 blockers、stale、editability。
5. API 不再自行推断 export ready。
6. 浏览器动作 smoke。

## 6. 允许 / 预期修改路径

- `scripts/orchestrate/export_queue.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/*`
- `tests/test_export_queue.py`
- `tests/test_preview_server.py`
- browser smoke scripts

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- blocked export。
- ready export。
- internal degraded export。
- P1 override。
- stale after approval。
- UI parity。

## 8. 成功标准

- 任何 client export 与 final readiness 不一致均为测试失败。
- 用户能看到明确修复动作。

## 9. 风险

避免在 UI 隐藏底层 refs；主标题用业务语言，详情可展示技术证据。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
