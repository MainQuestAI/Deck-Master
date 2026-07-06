# P2 细化实现稿 — Deck Master Backend Binding And Lock

日期：2026-07-03
状态：Draft v0.1
对应任务包：[`../tasks/P2-deck-master-backend-binding-and-lock.md`](../tasks/P2-deck-master-backend-binding-and-lock.md)

## 1. 目标

把 `ppt-master` 从“可认证的外部 backend 包”推进到“已正式绑定、可追溯、可写入 release truth”的状态，并完成本轮最小闭环：

1. Deck Master 能回答当前绑定的 backend 是谁
2. Deck Master 能回答当前绑定的 backend SHA 是谁
3. `suite-status` / `setup-status` / Review Desk 对 backend 状态使用同一套真相
4. `deck_capability_lock.json` 能记录当前 release 依赖的外部 backend

## 2. 当前事实

### 2.1 P1 已完成的部分

当前已经具备：

1. `ppt-master` 外部真源仓存在 Deck Master backend manifest
2. smoke 可执行，并可产出通过 `validate_render_result` 的最小样本
3. `builder_backend.py` 已能对单个 backend 包做严格认证
4. 当前 live backend 默认为：
   - `~/.codex/skills/ppt-master`

### 2.2 当前还缺什么

当前系统仍缺失“正式绑定”概念：

1. `suite-status` 还不能回答“当前绑定的是哪一个 repo / SHA”
2. `setup-status` 还不能明确输出 backend 来源与 verify 结果
3. `deck_capability_lock.json` 还没有 `external_dependencies[]`
4. Review Desk 还没有稳定展示 backend 来源、SHA、verify 状态的区域

### 2.3 当前高风险点

如果直接把 P1 的认证结果当成 P2 完成，会出现三类问题：

1. release truth 仍然不可追溯
2. `production_backend_ready` 仍可能建立在“本机碰巧有一个外部目录”之上
3. 用户看得到“backend 已认证”，但回答不了“这次 release 绑定的到底是哪一个 backend”

## 3. 本轮实现范围

### 3.1 主仓代码

允许修改：

1. `scripts/runtime/builder_backend.py`
2. `scripts/skills/installer.py`
3. `scripts/runtime/setup_status.py`
4. `scripts/deck_master.py`
5. `scripts/preview/server.py`
6. `scripts/preview/workspace_api.py`
7. `scripts/preview/static/app.js`
8. `docs/contracts/setup-status.v2.schema.json`
9. `tests/test_skill_installation.py`
10. `tests/test_preview_server.py`
11. 新增绑定相关测试文件

### 3.2 本轮不做

1. 不修改 `ppt-master` 外部仓实现
2. 不处理 `ppt-deck-pro-max` bridge SHA 固定
3. 不处理 real benchmark
4. 不打开真实 external render runtime
5. 不把 `client_delivery_ready` 改成 `true`

## 4. 设计方案

## 4.0 审查补充约束

P2 在正式实现前，先固定四条约束：

1. backend binding 必须成为单一事实源，不能一边读 registry，一边靠候选路径扫描得结论
2. release lock 不能只锁 suite / capability 名称，必须锁外部 backend 身份与验证结果
3. `setup-status`、Preview API、Review Desk 不能各自重算一套不同的 ready 口径
4. 主界面展示只允许安全摘要，绝对路径与原始命令留在诊断层

## 4.1 引入正式绑定注册表

新增本地注册表：

```text
~/.deck-master/backend_bindings.json
```

建议结构：

```json
{
  "schema_version": "deck_backend_bindings.v1",
  "bindings": [
    {
      "name": "ppt-master",
      "repo_path": "/abs/path/to/ppt-master",
      "skill_path": "/abs/path/to/ppt-master/skills/ppt-master",
      "git_remote": "https://github.com/hugohe3/ppt-master.git",
      "git_branch": "main",
      "git_sha": "668131f0ac05289c169a05a66c03182066fdccaf",
      "worktree_dirty": true,
      "verified": true,
      "verified_at": "2026-07-03T12:00:00+08:00",
      "validated_capabilities": ["render", "smoke", "writeback"]
    }
  ]
}
```

设计理由：

1. `repo_path` 解决“绑定的是哪个仓”
2. `skill_path` 解决“Deck Master 实际检查的是哪个 skill 根”
3. `git_sha` / `git_branch` 解决“release truth 追溯”
4. `verified` / `verified_at` / `validated_capabilities` 解决“绑定不等于已认证”

## 4.2 CLI 命令组

新增：

```text
deck-master backend bind ppt-master --repo <repo_path>
deck-master backend status
deck-master backend verify ppt-master
deck-master backend unbind ppt-master
```

建议行为：

### bind

1. 校验 `repo_path` 是 git worktree
2. 默认把 `skill_path` 解析为 `<repo_path>/skills/ppt-master`
3. 立即调用 verify
4. 将 verify 结果与 git 元信息写入注册表

### status

输出：

1. 当前所有 bindings
2. 每项 binding 的 repo / SHA / branch / dirty
3. 每项 binding 的 verified 状态
4. backend package 认证摘要

### verify

1. 读取已有 binding
2. 重新执行 package 认证
3. 刷新 git 信息和 verified 时间
4. 回写注册表

### unbind

1. 删除注册表中的对应 binding
2. 不删除外部仓
3. 不删除本机 `~/.codex/skills/ppt-master`

## 4.3 绑定真相优先级

P2 后需要明确两层概念：

1. `backend package exists`
2. `backend is formally bound`

本轮统一口径：

1. `inspect_builder_backend_package()` 继续回答“某个 package 是否可认证”
2. `production_backend_ready` 只由“已绑定且已认证”决定
3. `builder_backend_status()` 增加 binding 维度信息，并优先读取 binding registry
4. production run 若没有 active binding，应继续阻断

## 4.4 suite/setup 真相

### suite-status

新增顶层：

1. `external_dependency_status[]`

每项至少包含：

```json
{
  "name": "ppt-master",
  "binding_status": "bound_verified",
  "repo_label": "hugohe3/ppt-master",
  "repo_path": "/abs/path/to/ppt-master",
  "skill_path": "/abs/path/to/ppt-master/skills/ppt-master",
  "git_sha": "668131f0ac05289c169a05a66c03182066fdccaf",
  "git_branch": "main",
  "worktree_dirty": true,
  "verified": true,
  "verified_at": "2026-07-03T12:00:00+08:00",
  "validated_capabilities": ["render", "smoke", "writeback"],
  "summary": "已绑定 PPT Master backend，当前 SHA 已认证。"
}
```

状态口径建议：

1. `unbound`
2. `bound_blocked`
3. `bound_verified`
4. `bound_verified_runtime_blocked`

### task_readiness

P2 后：

1. `ppt_master_backend=ready` 只在 `bound_verified` 时为 `ready`
2. `render` 仍由 `backend_render_runtime_ready()` 控制
3. `client_delivery` 仍保持 `blocked`

### capability 状态

P2 后：

1. `ppt_master.render.v1`
2. `ppt_master.handback.v1`

在 runtime 未接通时应为：

```text
blocked_runtime_not_wired
```

不能再出现 capability 显示 `ready`，但 `task_readiness.render=blocked` 的分裂口径。

### setup-status

顶层增加：

1. `external_dependency_status[]`
2. `workspace_ready`
3. `production_ready`
4. `production_backend_ready`
5. `client_delivery_ready`

继续保留，并让 `blocking_summary[]` 明确区分：

1. workspace repair
2. backend unbound
3. backend verify failed
4. runtime not wired

## 4.5 capability lock 扩展

`deck_capability_lock.json` 增加：

```json
{
  "external_dependencies": [
    {
      "name": "ppt-master",
      "repo": "https://github.com/hugohe3/ppt-master.git",
      "repo_path": "/abs/path/to/ppt-master",
      "skill_path": "/abs/path/to/ppt-master/skills/ppt-master",
      "git_sha": "668131f0ac05289c169a05a66c03182066fdccaf",
      "git_branch": "main",
      "worktree_dirty": true,
      "validated_capabilities": ["render", "smoke", "writeback"],
      "verified": true,
      "verified_at": "2026-07-03T12:00:00+08:00"
    }
  ]
}
```

release build 行为：

1. 读取当前绑定注册表
2. 读取当前 verify 结果
3. 将外部依赖快照写入 lock
4. `verify_release_tree()` 对 lock 中的外部依赖结构做最小校验
5. 不对外部仓做任何自动修改

## 4.6 Review Desk 展示

P2 只做最小可用展示，不做版式重构。

### 首页 setup 摘要

`/api/setup-status` 返回：

1. `external_dependency_status[]`
2. `blocking_summary[]`

### run projection

`workspace_api.build_workspace_payload()` 增加：

1. `runtime.external_dependencies`
2. `run_summary.external_dependencies`

前端最小展示策略：

1. 首页仍沿用现有 `blocking_summary`
2. 底部 `Build Skill` 面板开始正式渲染 backend 来源、SHA、binding/verify 状态
3. 主界面只显示 `repo_label`、短 SHA、status、summary，不显示绝对路径
4. 绝对路径保留在 API payload 中，前端主界面不直接暴露
5. Preview API 不再重算与 CLI 不一致的 setup / production 真相

## 5. 测试设计

### 5.1 单元与集成

建议新增或补充：

1. `tests/test_skill_installation.py`
   - bind / verify / unbind 基础行为
   - suite-status 在 unbound / bound_blocked / bound_verified 下的口径变化
   - capability lock 写出 `external_dependencies[]`
2. 新增 `tests/test_backend_bindings.py`
   - registry 读写
   - repo -> skill_path 推断
   - git metadata 采集
3. `tests/test_preview_server.py`
   - `/api/setup-status` 返回 `external_dependency_status[]`
4. 如有必要，补 `tests/test_review_desk_skill_os.py` 或 `tests/test_preview_static_contract.py`
   - run projection 中可读 backend 摘要

### 5.2 focused verification

至少执行：

```bash
python3 -m unittest tests.test_skill_installation
PYTHONPATH=scripts python3 -m unittest tests.test_preview_server
python3 scripts/deck_master.py backend bind ppt-master --repo <ppt-master-backend-repo>
python3 scripts/deck_master.py backend status
python3 scripts/deck_master.py suite-status --target codex --output json
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py release-build --output /tmp/dm-release-p2 --force
```

## 6. 风险

### 风险 1：binding 引入后，现有 live backend 状态会回退

影响：

1. 当前本机 `production_backend_ready=true` 可能在引入 binding 语义后回到 `false`

处理方式：

1. 实现完成后立刻执行一次 `backend bind`
2. 用真实绑定结果恢复 `production_backend_ready=true`

### 风险 2：runtime 和 suite 读取来源不同步

影响：

1. build runtime 读到一个 backend
2. suite/setup 却显示另一个 backend

处理方式：

1. `builder_backend_status()` 优先读取 binding
2. `inspect_suite_status()` 使用同一套 binding 摘要

### 风险 3：Review Desk 暴露绝对路径

影响：

1. UI 主界面会暴露 `/Users/...`

处理方式：

1. 主界面只显示 repo label + SHA
2. 路径仅保留在 API / diagnostic 层

## 7. 完成定义

满足以下条件，可认为 P2 完成：

1. `deck-master backend bind/status/verify/unbind` 可用
2. `~/.deck-master/backend_bindings.json` 可稳定读写
3. `suite-status.production_backend_ready` 只由 bound + verified backend 决定
4. `setup-status` 能输出 `external_dependency_status[]`
5. `deck_capability_lock.json` 能写出 `external_dependencies[]`
6. Review Desk 能显示 backend 来源与 SHA
7. `render` 与 `client_delivery` 仍保持真实阻断口径
