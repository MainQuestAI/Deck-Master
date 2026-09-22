# P2 — Deck Master Backend Binding And Lock

## 1. 目标

让 Deck Master 正式绑定外部 backend，并把认证结果写入 capability lock 和状态真相输出。

## 2. In Scope

- `backend bind/status/verify/unbind`
- `backend_bindings.json`
- `deck_capability_lock.json.external_dependencies[]`
- `suite-status` / `setup-status` / Review Desk 外部依赖状态

## 3. Out Of Scope

- `ppt-master` 外部仓内的实现
- `ppt-deck-pro-max` bridge SHA 固定
- real benchmark 执行

## 4. 允许修改路径

- `scripts/deck_master.py`
- `scripts/runtime/builder_backend.py`
- `scripts/runtime/setup_status.py`
- `scripts/skills/installer.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/`
- `docs/contracts/setup-status.v2.schema.json`
- `tests/test_skill_installation.py`
- `tests/test_review_desk_skill_os.py`
- 新增绑定相关测试文件

## 5. 必须实现

1. 新增 backend bind 命令组
2. 新增本地 bindings registry
3. capability lock 增加 `external_dependencies[]`
4. `suite-status` 输出 `external_dependency_status[]`
5. `setup-status` 输出 backend 维度阻断摘要
6. Review Desk 首页与 run 投影可展示 backend 来源与 SHA

## 6. 测试与验证

至少验证：

1. bind / status / verify / unbind 正负向测试
2. capability lock 写出外部依赖
3. `suite-status.production_backend_ready` 只由已绑定且已认证 backend 决定
4. Review Desk API / UI 能读到 backend 状态

## 7. 成功标准

1. 用户能回答“当前绑定的 backend 是谁”
2. 用户能回答“当前绑定 SHA 是谁”
3. release build 能回答“这次 release 用了哪个外部 backend”

## 8. 依赖与并发

依赖 `P1`。  
完成后才能进入 `P3` 正式验收。

## 9. Agent 交付报告

必须输出：

1. 修改文件
2. bindings registry 结构
3. capability lock 字段变化
4. CLI 与 UI 状态变化
5. 测试命令与真实结果
6. 未完成项与风险
