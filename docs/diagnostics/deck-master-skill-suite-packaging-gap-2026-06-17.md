# Deck Master Skill Suite Packaging Gap Diagnosis

日期：2026-06-17
范围：当前 `main` / `1041541`，已安装 release `main-1041541`，本机 Codex / Claude skill 目录，v0.9.12 Skill Suite Runtime 实现与安装状态。

## 一页结论

v0.9.12 已经完成了 Skill Suite Runtime 的检查层、状态层和部分 handback contract，但没有完成真正的 Skill Suite packaging、迁移和安装接管。

当前真实安装结果是：

- `~/.deck-master/current/skills/` 下面只有 `deck-master`。
- `ppt-library` 和 `ppt-deck-pro-max` 仍停留在 `~/.codex/skills/` 的历史实体目录。
- `ppt-quality-gate` 仍停留在迈富时 PPT 工作坊的 draft 目录。
- `ppt-master` 是 Codex 目录里的外部 adopted symlink，且 CLI readiness 缺失。
- Claude Code 侧目前只有 `deck-master` symlink。

因此，当前系统能“知道”哪些 companion skills 应该存在，也能报告它们的 readiness；但还没有把这些 companion skills 作为 Deck Master release package 的一部分安装、迁移、覆盖或统一软链接。

## 当前事实

### 1. Deck Master 安装树

当前 release：

```text
/Users/dingcheng/.deck-master/current -> /Users/dingcheng/.deck-master/releases/main-1041541
```

当前内置 skill：

```text
/Users/dingcheng/.deck-master/current/skills/deck-master
```

缺失的预期 companion skill package：

```text
/Users/dingcheng/.deck-master/current/skills/ppt-library
/Users/dingcheng/.deck-master/current/skills/ppt-deck-pro-max
/Users/dingcheng/.deck-master/current/skills/ppt-quality-gate
/Users/dingcheng/.deck-master/current/skills/ppt-master
```

### 2. Codex skill 目录

当前 Codex 侧：

```text
/Users/dingcheng/.codex/skills/deck-master -> /Users/dingcheng/.deck-master/current/skills/deck-master
/Users/dingcheng/.codex/skills/ppt-library
/Users/dingcheng/.codex/skills/ppt-deck-pro-max
/Users/dingcheng/.codex/skills/ppt-master -> /Users/dingcheng/.codex/skills/.backups/ppt-master-repo-668131f0/skills/ppt-master
```

问题：

- `deck-master` 已符合真实安装模型。
- `ppt-library` 是历史实体目录，且 `SKILL.md` 缺 YAML frontmatter。
- `ppt-deck-pro-max` 是历史实体目录，虽然具备 Skill 结构，但没有被 Deck Master release 接管。
- `ppt-quality-gate` 不存在于 Codex skill 目录。
- `ppt-master` 是外部 adopted symlink，未纳入 Deck Master release tree。

### 3. Claude Code skill 目录

当前 Claude Code 侧：

```text
/Users/dingcheng/.claude/skills/deck-master -> /Users/dingcheng/.deck-master/current/skills/deck-master
```

缺失：

```text
/Users/dingcheng/.claude/skills/ppt-library
/Users/dingcheng/.claude/skills/ppt-deck-pro-max
/Users/dingcheng/.claude/skills/ppt-quality-gate
/Users/dingcheng/.claude/skills/ppt-master
```

### 4. suite-status 真实判断

当前 `deck-master setup-status --include-suite --output json` 返回：

- setup: `ready`
- production_ready: `true`
- suite: `degraded_ready`
- full_suite_ready: `false`

具体 companion 状态：

| Skill | Codex 状态 | Claude Code 状态 | 影响 |
|---|---|---|---|
| `deck-master` | ready | ready | 主控可用 |
| `ppt-library` | real_dir_conflict | missing | library sourcing blocked |
| `ppt-deck-pro-max` | real_dir_conflict | missing | new generation blocked |
| `ppt-quality-gate` | missing | missing | standalone audit blocked |
| `ppt-master` | blocked_cli_missing | optional_missing | render export optional missing |

## 根因判断

### 根因 1：release package 只有 `deck-master`

仓库当前 `skills/` 目录只包含：

```text
skills/deck-master/
```

`suite-install` 会查找 `~/.deck-master/current/skills/<skill-name>`。由于 companion skill package 不存在，它只能报告 `source_missing` 或在 Codex 目录中发现历史实体目录冲突。

### 根因 2：安装器按“报告缺口”设计，没有执行迁移接管

`scripts/skills/installer.py` 的 suite installer 当前行为：

- 如果 source package 不存在，返回 `source_missing`。
- 如果 target 位置已有实体目录，返回 `real_dir_conflict`。
- 不覆盖真实目录。
- 不备份历史目录。
- 不把外部 skill 复制或整理成 release bundle。

这个设计符合 v0.9.12 Stack A 的保守边界，但没有满足“安装 Deck Master 时配套安装完整 Skill Suite”的产品预期。

### 根因 3：`setup` 只配置 workspace，不执行 suite install

`deck-master setup` 当前负责：

- 写 `~/.deck-master/config.json`
- 设置 active workspace
- 设置 default runs dir
- 写 companion manifest
- 校验 setup status

它没有自动执行：

```text
deck-master suite-install
deck-master suite-repair
```

所以 workspace setup ready 与 suite ready 会出现分裂：用户看到 Deck Master 可用，但真实 companion 能力仍然阻断。

### 根因 4：测试接受 degraded suite

当前测试覆盖了：

- suite status 能报告 missing companions。
- suite-install 能安装 available 的 `deck-master`。
- suite-install 能报告 missing companions。

测试没有要求：

- release package 内必须存在 required companion skills。
- Codex / Claude 目录必须全部变成 symlink。
- 历史实体目录必须被安全迁移或明确阻断。
- 安装后 `full_suite_ready=true`。

这导致 CI 能通过，但用户视角下 Skill Suite 没有完整落地。

## 与产品预期的偏差

预期模型：

```text
~/.deck-master/current/skills/
  deck-master/
  ppt-library/
  ppt-deck-pro-max/
  ppt-quality-gate/
  ppt-master/                # optional

~/.codex/skills/<skill> -> ~/.deck-master/current/skills/<skill>
~/.claude/skills/<skill> -> ~/.deck-master/current/skills/<skill>
```

当前模型：

```text
~/.deck-master/current/skills/
  deck-master/

~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.codex/skills/ppt-library          # legacy real directory
~/.codex/skills/ppt-deck-pro-max     # legacy real directory
~/.codex/skills/ppt-master -> external backup path
```

因此，当前 v0.9.12 更接近“Skill Suite readiness inspector”，还没有达到“Skill Suite installer / migrator / package owner”。

## 后续修复方向

下一轮应该独立定义为 **Skill Suite Packaging & Migration**，不再只补 adapter。

关键工作：

1. 明确 Deck Master release package 内应包含哪些 skill package。
2. 把 `ppt-quality-gate` 从迈富时 draft 晋升为正式 skill package。
3. 为 `ppt-library` 提供 Deck Master curated skill package，保留外部 CLI / 数据库生命周期。
4. 为 `ppt-deck-pro-max` 提供 Deck Master curated skill package，保留独立仓库生命周期。
5. 定义历史实体目录迁移策略：备份、替换为 symlink、回滚。
6. 让 `setup` 或 first-run ceremony 明确提示并执行 suite install / repair。
7. 调整测试：安装后 required suite skills 必须可见；历史冲突必须有可执行迁移动作。

## 本文档用途

本文档只记录当前缺口和根因，不直接规定最终 Skill 体系。最终 Skill 体系应由产品架构文档定义，再反推 packaging、installer、migration 和 setup 流程。
