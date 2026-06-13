# Deck Master v0.9.9 Installation Chain Hardening Spec

## 目标

把 Deck Master 的真实用户安装链路固定下来：Deck Master 自身安装在 `~/.deck-master`，Codex / Claude Code / Hermes 等 Agent 目录只保留入口软链接。

## 用户安装模型

```text
~/.deck-master/
  releases/
    <version>/
      scripts/
      skills/deck-master/
  current -> ~/.deck-master/releases/<version>
  bin/deck-master
  runs/
  logs/
```

Agent 侧入口：

```text
~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.claude/skills/deck-master -> ~/.deck-master/current/skills/deck-master
```

## 约束

- `install-skill` 默认源必须优先使用 `~/.deck-master/current/skills/deck-master`。
- 只有在安装源不存在时，开发仓库内运行才允许回退到仓库 `skills/deck-master`。
- CLI 必须支持 `--source-skill-dir`，供 Setup、测试和受控调试显式指定源。
- `validate-skill` 必须同时验证 symlink 指向和 `SKILL.md` 可发现格式。
- `uninstall-skill` 只能删除指向预期 Deck Master skill 源的 symlink。
- 安装器不能覆盖 Agent 目录里的真实文件夹。

## 验收

- 临时 Agent skill 目录安装后，`deck-master` 是 symlink。
- 默认源存在时，symlink 指向 `~/.deck-master/current/skills/deck-master`。
- 传入 `--source-skill-dir` 时，安装、验证和卸载都以显式源为准。
- 缺少 YAML frontmatter 的 `SKILL.md` 会被拒绝。
- 重复安装幂等，`--force` 只替换 symlink。
