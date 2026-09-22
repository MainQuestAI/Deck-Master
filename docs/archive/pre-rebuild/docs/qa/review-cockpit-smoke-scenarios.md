# Review Cockpit Smoke Scenario Coverage Matrix

日期：2026-06-17

## 目的

本文件从 `origin/codex/deck-master-endgame-runtime` 历史分支提取 Review Cockpit smoke 测试思路，并对照当前 `main @ e812ea4` 的测试覆盖。

本文件只定义测试场景和覆盖状态，不迁移旧脚本、不迁移截图、不改变运行时代码。

## 覆盖矩阵

| 历史 smoke 场景 | 历史证据 | 当前主线对应入口 | 当前覆盖状态 | 当前测试或后续动作 |
|---|---|---|---|---|
| 质量阻断可见 | `p1-run-os-core/qa-report.md`：`gateCards=1`、`runBlockers=4`、`exportBlockers=5` | Review Cockpit `/api/review-summary/<run_id>`、`review.readiness.compute_deck_readiness`、quality gate reports | 已覆盖 | `tests/test_review_cockpit.py` 覆盖 readiness 结构和 blocking reasons；`tests/test_quality_gate.py` 覆盖 gate 阻断 |
| 高风险筛选 | 历史 smoke：`filteredRiskPages=3` | Review Cockpit quality summary、quality findings 展示和筛选 | 部分覆盖 | 后台质量报告已覆盖；前端筛选动作建议后续补一条轻量浏览器 smoke |
| 导出阻断说明 | 历史 smoke：导出阻断卡片、跳转页面、复制阻断说明 | `review.readiness` 的 `blocking_reasons`、`orchestrate.export_queue`、Review Cockpit export queue API | 部分覆盖 | `tests/test_review_cockpit.py` 覆盖 export readiness；建议后续补导出阻断文案复制的浏览器级断言 |
| 重跑质量门禁 | 历史 smoke：单 gate 重跑、全部 gate 重跑、history/diff 持久化 | `quality-gate draft`、`generation_session.quality_required_at`、fresh draft gate 判断 | 部分覆盖 | `tests/test_generation_session_bridge.py` 和 `tests/test_run_state_resolver.py` 覆盖 freshness；旧分支的 UI 重跑动作列入 backlog |
| 审查操作写回 | 历史 smoke：批准、拒绝、note 持久化 | Review Cockpit page review action API、`review.workbench.execute_review_action` | 已覆盖 | `tests/test_review_workbench.py`、`tests/test_preview_server.py` 覆盖审查操作和 runtime readiness |
| 导出交付写回 | 历史 smoke：导出队列、交付结果、delivered pages | `delivery.outcome.record_delivery_outcome`、Preview server delivery APIs、export queue | 已覆盖 | `tests/test_delivery_outcome.py` 覆盖交付结果写入；`tests/test_preview_server.py` 覆盖 API 面 |
| 资产健康刷新 | 历史 smoke：workspace asset health refresh、reuse candidates | asset health runtime、Review Cockpit asset signals API | 部分覆盖 | `tests/test_asset_health.py` 覆盖 asset health；建议后续补 Review Cockpit 资产刷新浏览器 smoke |
| 来源标识可见 | 历史分支没有当前 UC story review 的新版字段，但 smoke 价值相近 | `preview_manifest.pages[].candidate_origin` / `library_source`、Review Cockpit source badge | 已覆盖 | `tests/test_ppt_library_client.py`、`tests/test_end_to_end_autoplan.py`、`tests/test_preview_manifest.py` 覆盖字段贯穿；前端 badge 由 UC story review QA 已验证 |

## Backlog

以下旧 smoke 思路仍有价值，但本次归档 PR 不实现：

1. Review Cockpit 高风险筛选的浏览器 smoke。
2. 导出阻断说明的跳转与复制浏览器 smoke。
3. 质量 gate 重跑动作的浏览器 smoke。
4. 资产健康刷新按钮的浏览器 smoke。

建议后续统一放入一个小型 QA hardening 分支，使用当前主线的 Review Cockpit 结构重写，不复用旧分支脚本。

## 当前删除判断

旧 smoke 场景已经有去向：

- 已覆盖：质量阻断可见、审查操作写回、导出交付写回、来源标识可见。
- 部分覆盖：高风险筛选、导出阻断说明、重跑质量门禁、资产健康刷新。
- 未覆盖但仍有价值：浏览器动作级 smoke。
- 已废弃：旧分支的截图批量归档、旧 smoke 目录结构、旧脚本依赖路径。

因此，`origin/codex/deck-master-endgame-runtime` 的继续保留价值已经下降到历史追溯层。待归档 PR 合入并经老板确认后，可删除远程历史分支。
