# P5 — RC Gate Dogfood Release Closure

## 1. 目标

在外部依赖和真实 benchmark 闭环完成后，让 RC gate、clean install 和 dogfood 一次收口。

## 2. In Scope

- `external_dependency_closure` required check
- RC gate 重跑
- clean install
- Review Desk / CLI 状态一致性验证
- dogfood 证据整理

## 3. Out Of Scope

- 新增生产能力
- benchmark case 扩容
- 新的 frontend 大改

## 4. 允许修改路径

- `scripts/runtime/rc_gate.py`
- `scripts/deck_master.py`
- `scripts/skills/installer.py`
- `scripts/runtime/setup_status.py`
- `scripts/preview/workspace_api.py`
- `tests/test_rc_gate.py`
- `tests/test_skill_installation.py`
- `tests/test_review_desk_skill_os.py`
- `docs/releases/`
- `docs/qa/`
- `docs/migration/`

## 5. 必须实现

1. RC gate 增加 `external_dependency_closure`
2. 该检查至少验证：
   - `ppt-master` 已绑定且 verify 通过
   - `ppt-master` 已进入 capability lock
   - `ppt-deck-pro-max` bridge 已固定 SHA
   - bridge 已进入 capability lock
   - benchmark aggregate=`report_ready`
3. 完成一次 clean install
4. 完成一次 Review Desk / CLI 状态一致性验证

## 6. 测试与验证

至少验证：

1. `release-smoke`
2. `rc-gate`
3. `suite-status`
4. `setup-status`
5. Review Desk 首页与 run 详情

## 7. 成功标准

1. `rc-gate` required failures = 0
2. `client_delivery_ready=true`
3. CLI 与 UI 对外部依赖阻断原因口径一致
4. v1.3.0 具备正式放行条件

## 8. 依赖与并发

依赖 `P4`。  
这是最终收口包。

## 9. Agent 交付报告

必须输出：

1. RC report 路径
2. clean install 结果
3. dogfood 结果
4. release note / QA 文档更新点
5. 剩余风险
