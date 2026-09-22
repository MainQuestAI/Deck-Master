# C1 — Review Desk Skill OS View

## 1. 目标

在 Review Desk v0.3 中展示 Stage Ladder、Handoff、Approval、Stale 和 Next Skill。

## 2. In Scope

- API projection。
- stage rail。
- handoff accept/reject。
- resume autopilot。
- safe display copy。

## 3. Out of Scope

不重做整体布局；不在前端推导 Stage。

## 4. 允许修改路径

- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/`
- `tests/test_review_desk_skill_os.py`
- `tests/test_preview_static_contract.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 9 Stage 状态展示。
2. awaiting approval 与 blocker 区分。
3. accept/reject 写 Runtime。
4. stale 原因可见。
5. raw path/command 不上主界面。

## 6. 测试

- 早期无 Preview。
- awaiting approval。
- stale。
- repair。
- ready for export。
- mobile / desktop smoke。

## 7. 成功标准

- 用户不需理解 Runtime code 即可推进。

## 8. 依赖与并发

依赖 B5。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
