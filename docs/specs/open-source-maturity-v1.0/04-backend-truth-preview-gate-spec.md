# 04 — Backend Truth And Preview Gate Spec

## 1. 目标

修复后端依赖误报 ready、本机路径默认值和 M1/M2 gate 混用问题。M1 使用 `preview-gate`，M2 才使用 `rc-gate`。

## 2. 必须修复的风险

1. `scripts/runtime/builder_backend.py` 中不能保留作者本机桥接路径默认值。
2. `_generation_bridge_status()` 未配置时不能返回 `bound_verified`。
3. 未配置 production backend 时，production 命令必须阻断，并给出 fixture/demo 路径。
4. `setup-status` / `suite-status` 必须清楚显示后端未配置状态。
5. M1 的 `preview-gate` 不能要求真实后端或 benchmark。

## 3. 状态语义

| 场景 | 状态 | 用户可读说明 |
|---|---|---|
| 未配置 production backend | `unbound` 或 `not_configured` | 当前可运行 fixture demo；production backend 未配置 |
| 配置但未验证 | `configured_unverified` | 已发现配置，需要运行 verify |
| 配置且验证通过 | `bound_verified` | 可进入 production / M2 验证 |
| 配置损坏 | `invalid` | 给出修复命令和失败原因 |

## 4. preview-gate 范围

`preview-gate` 必须验证：

1. editable install 可用。
2. fixture demo run 存在且结构可读。
3. Review Desk 可启动或静态资源可访问。
4. 未配置 backend 时不误报 ready。
5. README / Quick Start 指向的命令可复用。

`preview-gate` 不验证：

1. 真实 benchmark。
2. production backend。
3. browser smoke required gate。
4. M2 release tree 回滚。

## 5. 允许修改路径

1. `scripts/runtime/builder_backend.py`
2. `scripts/runtime/rc_gate.py`
3. `scripts/deck_master.py`
4. `scripts/runtime/`
5. `tests/`
6. `README.md`
7. `docs/quick-start.md`

## 6. 测试与验证

```bash
python -m unittest discover -s tests
python -m pytest tests/test_skill_manifest.py tests/test_workflow_cli.py tests/test_skill_os_release_contract.py -q
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

需要补负向测试：

1. 未配置 backend 时 status 不返回 `bound_verified`。
2. 删除或损坏 bridge 配置时 production 命令阻断。
3. `preview-gate` 在未配置 backend 时可通过 fixture demo。

## 7. 成功标准

1. M1 无 production backend 时仍能公开演示。
2. M1 不会对外误报 ready。
3. M2 保留 `rc-gate` 的真实 release 判断。
