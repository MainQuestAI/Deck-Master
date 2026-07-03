# P3 细化实现稿 — PPT Deck Pro Max Bridge Lock And Smoke

日期：2026-07-03  
状态：Draft v0.1  
对应任务包：[`../tasks/P3-ppt-deck-pro-max-bridge-lock-and-smoke.md`](../tasks/P3-ppt-deck-pro-max-bridge-lock-and-smoke.md)

## 1. 目标

把 `ppt-deck-pro-max` 从“本机已有 bridge 实现”推进到“Deck Master release 可追溯的 generation bridge 依赖”，并完成本轮最小闭环：

1. Deck Master 能回答当前 generation bridge 来源仓库是谁
2. Deck Master 能回答当前 generation bridge 固定 SHA 是谁
3. capability lock 能写入 bridge 依赖快照
4. cross-repo smoke 能证明 dispatch/import/export/import-results 可复跑

## 2. 当前事实

### 2.1 bridge 实现基础已经存在

当前本机可核验的 bridge worktree 位于：

```text
/Users/dingcheng/Coding-Project/02-key-project/PPT-Deck-Pro-Max-deck-master-bridge
```

git 信息：

1. `origin=https://github.com/MainQuestAI/PPT-Deck-Pro-Max.git`
2. `branch=codex/deck-master-bridge`
3. `HEAD=9444d88f573c3afa567bfb1763041325ef765313`
4. worktree 当前干净

### 2.2 历史证据已经证明 bridge 契约可跑

仓内已有历史证据与测试入口：

1. `docs/specs/real-production-closure/implementation/test-evidence.md`
2. `tests/test_generation_session_bridge.py`
3. `tests/test_generation_handback.py`
4. `tests/test_uat_generation_tool.py`

现有证据说明：

1. Deck Master 能生成 dispatch package
2. PPT 侧 bridge 能导入 dispatch package
3. PPT 侧 bridge 能导出 canonical `deck_generation_result.v2`
4. Deck Master 能导入结果并刷新 run 状态

### 2.3 当前缺口仍然很明确

当前 bridge 还没有进入 v1.3.0 release truth：

1. `deck_capability_lock.json` 还没有 bridge 依赖快照
2. `suite-status` / `setup-status` 还不能回答当前使用的是哪个 bridge SHA
3. Review Desk 还不能安全展示 bridge 来源摘要
4. 现有 bridge 证据还停留在历史实现层，没有进入本轮 release gate

## 3. 本轮实现范围

### 3.1 外部仓

允许修改：

1. `PPT-Deck-Pro-Max` bridge manifest / 说明文档
2. `PPT-Deck-Pro-Max` bridge smoke 脚本或测试
3. `PPT-Deck-Pro-Max` 侧与 Deck Master 对接的 CLI 入口

### 3.2 Deck Master 主仓

允许修改：

1. `scripts/skills/installer.py`
2. `scripts/generation/dispatch.py`
3. `scripts/generation/handback.py`
4. `scripts/deck_master.py`
5. `tests/test_generation_session_bridge.py`
6. `tests/test_generation_handback.py`
7. `tests/test_skill_installation.py`
8. 必要的 smoke / UAT 文档

### 3.3 本轮不做

1. 不处理 `ppt-master` backend bind 逻辑
2. 不跑真实 benchmark
3. 不让 `client_delivery_ready` 在本轮改成 `true`
4. 不做新的 UI 版式重构

## 4. 设计方案

## 4.1 bridge 真相沿用 P2 的外部依赖模型

建议默认决策：

1. 不再新开第二套 lock 结构
2. 直接沿用 P2 的 `external_dependencies[]`
3. 为 `ppt-deck-pro-max` 增加一条 `dependency_kind=generation_bridge` 记录

建议字段：

```json
{
  "name": "ppt-deck-pro-max",
  "dependency_kind": "generation_bridge",
  "repo": "https://github.com/MainQuestAI/PPT-Deck-Pro-Max.git",
  "repo_path": "/Users/dingcheng/Coding-Project/02-key-project/PPT-Deck-Pro-Max-deck-master-bridge",
  "git_branch": "codex/deck-master-bridge",
  "git_sha": "9444d88f573c3afa567bfb1763041325ef765313",
  "verified": true,
  "verified_at": "2026-07-03T12:00:00+08:00",
  "validated_capabilities": [
    "dispatch_import",
    "generation_result_export",
    "result_import_contract"
  ]
}
```

这样做的理由很直接：

1. backend 和 bridge 统一走一套 release truth
2. P5 的 `external_dependency_closure` 可以一次性检查
3. 用户能在同一位置看到 production backend 和 generation bridge 的来源

## 4.2 bridge 正式来源的口径

P3 需要把“实现分支存在”收口为“release 可追溯来源存在”。

建议口径：

1. v1.3.0 可接受 `codex/deck-master-bridge` 作为正式 bridge 来源
2. 前提是 repo URL、branch、SHA、验证结果全部写入 lock
3. 后续是否合回 `main`，留到正式 spec 或外部仓治理阶段决策

本轮重点是把来源固定住，不让 release 继续依赖“本机某个目录刚好可用”。

## 4.3 cross-repo smoke 路径

P3 的 smoke 应固定为以下 4 段：

1. Deck Master `generation-session create / dispatch`
2. PPT bridge `deck-master-import`
3. PPT bridge `deck-master-export`
4. Deck Master `import-generation-results`

约束：

1. export 只能消费 PPT 侧已经存在的 assembled HTML 和截图
2. export 不能临时伪造页面产物
3. 结果必须是 canonical `deck_generation_result.v2`
4. Deck Master 导入后要能推进 generation / build / render 相关状态

## 4.4 状态输出

P3 后建议至少新增两类真相输出：

### suite / setup

`external_dependency_status[]` 新增 bridge 条目，字段至少包含：

1. `name`
2. `dependency_kind`
3. `repo_label`
4. `git_sha`
5. `binding_status`
6. `verified`
7. `summary`

### capability lock

release build 时把 bridge 依赖快照写进 `deck_capability_lock.json`。

最低要求：

1. 这次 release 依赖的 bridge repo 可追溯
2. 这次 release 依赖的 bridge SHA 可追溯
3. 这次 release 依赖的 bridge 验证结果可追溯

## 5. 测试设计

### 5.1 外部仓验证

至少执行：

```bash
python3 -m unittest tests.test_deck_master_bridge
/Users/dingcheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests
```

补充说明：

1. 现有历史证据显示 system Python 缺 `python-pptx`
2. 全量 PPT 仓测试默认使用 Codex bundled Python 更稳

### 5.2 Deck Master 主仓验证

至少执行：

```bash
python3 -m unittest tests.test_generation_session_bridge tests.test_generation_handback tests.test_uat_generation_tool
python3 -m unittest tests.test_skill_installation
```

### 5.3 cross-repo smoke

至少执行一次真实 smoke，并留存：

1. dispatch package 路径
2. PPT 侧 import 项目目录
3. export 产出的 `deck_generation_result.v2` 路径
4. Deck Master 导入后的 run 状态

## 6. 风险

### 风险 1：bridge 来源口径还没完全稳定

影响：

1. `codex/deck-master-bridge` 是当前可验证来源
2. 如果后续 spec 改成必须合主线，P3 交付口径需要补一轮更新

处理方式：

1. 本轮先固定 SHA
2. 在文档里显式写出 branch 和 repo
3. P5 只认 lock 中的固定来源

### 风险 2：PPT 侧环境依赖不统一

影响：

1. 本机 system Python 可能跑不完外部仓测试

处理方式：

1. 默认采用 bundled Python 跑全量验证
2. smoke 命令单独留出最小必跑路径

### 风险 3：bridge 能力被误写成已完成客户交付

影响：

1. generation bridge 固定完成后，系统容易给出“生产已闭环”的错觉

处理方式：

1. P3 只解锁 bridge 追溯真相
2. `client_delivery_ready` 继续留给 `P4/P5` 收口

## 7. 完成定义

满足以下条件，可认为 P3 完成：

1. `ppt-deck-pro-max` bridge 来源仓与 SHA 已固定
2. `deck_capability_lock.json` 已写入 bridge 依赖快照
3. cross-repo smoke 已真实跑通并留有证据
4. `suite-status` / `setup-status` 能展示 bridge 摘要
5. `client_delivery_ready` 仍保持真实口径，没有被提前放行
