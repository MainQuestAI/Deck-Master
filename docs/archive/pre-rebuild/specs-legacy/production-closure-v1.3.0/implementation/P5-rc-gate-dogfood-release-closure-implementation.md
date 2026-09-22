# P5 细化实现稿 — RC Gate Dogfood Release Closure

日期：2026-07-03  
状态：Completed / Current Evidence Synced  
对应任务包：[`../tasks/P5-rc-gate-dogfood-release-closure.md`](../tasks/P5-rc-gate-dogfood-release-closure.md)

## 1. 目标

把 v1.3.0 的最终放行条件收口到一份可验证结果里。当前仓状态已经完成本轮最小闭环：

1. `rc-gate` 已能检查外部依赖闭环
2. `external_dependency_closure` 已作为 required check 通过
3. CLI / suite / setup 已能给出 `production_backend_ready=true`、`client_delivery_ready=true`
4. `client_delivery_ready=true` 已建立在外部依赖、benchmark aggregate 和 RC gate 证据之上

clean install、5050 dogfood、browser smoke 和 Review Desk 截图仍建议作为发布增强证据继续固化。

## 2. 当前事实

### 2.1 当前 RC gate 已有外部依赖闭环检查

当前 `scripts/runtime/rc_gate.py` 的 required checks 主要包括：

1. `schema_json_parse`
2. `artifact_validator`
3. `release_smoke`
4. `fixture_e2e`
5. `benchmark_aggregate`
6. `external_dependency_closure`

当前 `rc_reports/rc_gate_report.json` 显示：

1. `status=pass`
2. `checks=7`
3. `required_failures=0`
4. `optional_warnings=0`
5. `external_dependency_closure=pass`
6. `browser_smoke` 已支持真实 Review Desk 浏览器 smoke；当前默认策略仍可选跳过，但 `--require-browser-smoke` 可提升为正式门禁

### 2.2 UI / CLI 状态漂移已转为回归风险

本轮审查补充的约束仍需作为回归标准保留：

1. backend / bridge 需要单一事实源，不能一处读 registry，一处读候选路径扫描
2. release lock 要锁外部依赖身份和验证结果
3. `setup-status` 和 Review Desk 不能各自重算真相
4. 主 UI 文案不能泄露绝对路径和原始命令

### 2.3 当前 `client_delivery_ready` 已有真实放行条件

当前 `suite-status` 输出 `client_delivery_ready=true`，其证据包含：

1. RC gate passed
2. `external_dependency_closure_passed=true`
3. dependency snapshot matches
4. current dependencies 与 RC report dependencies 一致
5. benchmark aggregate 为 `report_ready`

边界：

1. `setup-status` 当前仍可能因为 active workspace 材料缺失显示 `needs_repair`，这不应覆盖 suite/client delivery readiness 的已闭环事实。
2. 当前 closure 证明的是系统级 readiness；生产 run 仍需等待外部 render / writeback 回写后，才能进入最终客户成片判断。
3. 当前 real benchmark 报告仍显示 `final_ready=false`、`export_ready=false`、`quality_blocked=true`，因此不能把 P5 写成“每个 run 都已最终交付”。

## 3. 本轮实现范围

允许修改：

1. `scripts/runtime/rc_gate.py`
2. `scripts/deck_master.py`
3. `scripts/skills/installer.py`
4. `scripts/runtime/setup_status.py`
5. `scripts/preview/server.py`
6. `scripts/preview/workspace_api.py`
7. 必要时补 `scripts/preview/static/`
8. `tests/test_rc_gate.py`
9. `tests/test_skill_installation.py`
10. `tests/test_preview_server.py`
11. `tests/test_review_desk_skill_os.py`
12. `docs/releases/`
13. `docs/qa/`
14. `docs/migration/`

本轮不做：

1. 不新增 production 能力
2. 不扩新的 benchmark case
3. 不做大的前端信息架构改版

## 4. 设计方案

## 4.1 已新增 `external_dependency_closure` required check

当前 RC gate 已加入 required check：

```text
external_dependency_closure
```

检查项：

1. `ppt-master` 已绑定且 verify 通过
2. `ppt-master` 已进入 capability lock
3. `ppt-deck-pro-max` bridge 已固定 SHA
4. `ppt-deck-pro-max` bridge 已进入 capability lock
5. benchmark aggregate=`report_ready`

details 至少返回：

1. backend binding id / SHA
2. bridge binding id / SHA
3. benchmark aggregate status
4. 缺失项列表

## 4.2 状态真相只能来自同一事实源

P5 已落地的核心约束：

1. RC gate、`suite-status`、`setup-status`、Review Desk 都从同一份外部依赖真相派生
2. Preview API 不再单独重算与 CLI 含义冲突的 ready 字段
3. release lock、binding registry、runtime status 之间要能互相校验

后续继续保持：

1. 顶层 readiness 统一从 `setup_status()` 和 suite payload 派生
2. Preview API 负责透传和安全裁剪，不负责再定义一套业务规则

## 4.3 Review Desk 的最小产品化收口

P5 不做大视觉改造，只做真相收口：

1. 首页能解释当前阻断属于 backend、bridge、benchmark，还是 workspace
2. 主界面只显示安全摘要，不显示绝对路径
3. 诊断层可以保留详细字段，默认界面不直出

这部分需要吸收当前审查结论：

1. DOM 不应出现 `/Users/`
2. DOM 不应出现 `/private/`
3. DOM 不应出现 `--run-dir`

## 4.4 clean install / dogfood 验证协议

P5 后续发布增强建议至少完成一次标准验证：

1. 重建 `~/.deck-master/current`
2. 执行 `release-smoke`
3. 执行 `suite-status`
4. 执行 `setup-status`
5. 启动 5050 Review Desk 验证首页和 run 详情

发布增强输出要能回答两个问题：

1. 干净安装后，系统还能不能认出同一套外部依赖
2. CLI 和 Review Desk 对当前阻断原因是否一致

## 5. 测试设计

### 5.1 RC gate 回归

后续改动至少执行：

```bash
python3 -m unittest tests.test_rc_gate tests.test_skill_installation
```

### 5.2 Preview / Review Desk 回归

后续改动至少执行：

```bash
PYTHONPATH=scripts python3 -m unittest tests.test_preview_server tests.test_review_desk_skill_os
```

### 5.3 最终命令验证

当前已复核 `rc_reports/rc_gate_report.json`、`suite-status`、`setup-status`。后续发布前至少执行：

```bash
python3 scripts/deck_master.py release-smoke --no-smoke
python3 scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc-gate --force
python3 scripts/deck_master.py suite-status --target codex --output json
python3 scripts/deck_master.py setup-status --include-suite --output json
```

如需浏览器验收，再补：

1. 5050 Review Desk 首页截图
2. run 页截图
3. 移动端截图
4. 如需对外承诺 run 级最终成片 readiness，再补外部 render/writeback 的真实回写样本

当前本轮已验证：

1. `rc-gate --require-browser-smoke` 可通过
2. `browser_smoke` 不再只是静态资源存在性检查
3. smoke 会启动临时 Review Desk、打开 fixture run，并检查前台不出现 `/Users/`、`/private/`、`--run-dir`、`python3`

## 6. 风险

### 风险 1：状态口径继续分叉

影响：

1. CLI 显示 blocked
2. UI 显示 ready

处理方式：

1. 所有外部依赖状态统一从单一事实源派生
2. 测试覆盖 CLI、API、UI 三层

### 风险 2：主 UI 再次泄露路径和命令

影响：

1. 产品面上暴露本机实现细节

处理方式：

1. 安全摘要和诊断字段分层
2. DOM 断言覆盖绝对路径和原始命令

### 风险 3：render runtime 以后打开时出现状态不同步

影响：

1. `suite-status`
2. run-state
3. build runtime

这三处可能出现阶段漂移。

处理方式：

1. 把 runtime 开关读取点收成共享判断
2. 在 P5 增加一组“runtime 打开后阶段联动”预演测试

## 7. 完成定义

按当前仓状态，P5 已满足以下核心完成条件：

1. `rc-gate` 已新增 `external_dependency_closure` 且 required failures = 0
2. `suite-status` / `setup-status` 已输出 `production_backend_ready=true`
3. `suite-status` / `setup-status` 已输出 `client_delivery_ready=true`
4. `client_delivery_ready=true` 建立在真实 backend、真实 bridge、真实 benchmark 和 RC 全绿之上
5. 当前完成定义针对 suite/release 级 readiness，不直接等于每个 run 的最终成片 readiness

发布增强仍建议补齐：

1. clean install 证据
2. 5050 Review Desk dogfood 证据
3. 主 UI 不暴露绝对路径和原始命令的截图或自动化断言
4. browser smoke 是否 required 的最终决策
