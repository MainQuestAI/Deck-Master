# T3 — Backend Truth And Preview Gate

## 1. 目标

修复 backend ready 误报，并新增 M1 `preview-gate`。

## 2. In Scope

1. `scripts/runtime/builder_backend.py`
2. `scripts/runtime/rc_gate.py`
3. `scripts/deck_master.py`
4. `tests/`
5. README / Quick Start 中的状态说明

## 3. 必须实现

1. 移除默认本机桥接路径。
2. `_generation_bridge_status()` 未配置时返回 `unbound` 或 `not_configured`。
3. production 命令在后端未配置时阻断。
4. `setup-status` / `suite-status` 给出修复命令。
5. `preview-gate` 验证 fixture demo 和 Review Desk，不要求真实 backend。

## 4. 负向测试

1. 未配置 backend 时不能出现 `bound_verified`。
2. 损坏 backend 配置时 production 命令失败。
3. 未配置 backend 时 `preview-gate --expect-unconfigured-backend-ok` 可通过。

## 5. 验证

```bash
python -m unittest discover -s tests
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```
