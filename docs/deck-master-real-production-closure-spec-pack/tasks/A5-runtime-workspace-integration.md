# A5 — Runtime & Review Workspace Integration

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1-A4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让真实 generation/build/render 状态进入 Run State、Next Step 和方案工作台。

## 3. In Scope

- Run stage。
- Next command。
- Workspace APIs。
- Artifact cards。
- Build/render actions。
- Source mode visibility。

## 4. Out of Scope

不做最终 final readiness（B3）；不重构整套前端。

## 5. 必须实现

1. 新增 needs_generation_execution / needs_build / needs_render。
2. Workspace 展示 producer、profile、format、editability。
3. Fixture / imported / real 明确 badge。
4. Artifact invalid 显示阻断。
5. 页面预览使用真实 page PNG/HTML。
6. API 继续兼容旧字段。

## 6. 允许 / 预期修改路径

- `scripts/runtime/run_state_resolver.py`
- `scripts/runtime/next_step.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/*`
- `tests/test_run_state_resolver.py`
- `tests/test_preview_server.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- 状态推进。
- API payload。
- no preview。
- build pending。
- render complete。
- fixture badge。
- browser desktop smoke。

## 8. 成功标准

- 用户能从工作台看清当前卡在 Agent、Build、Render 还是质量。
- 不再出现 completed 但无真实预览。

## 9. 风险

UI 可能同时读取旧 readiness，B3 前需保持兼容层。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
