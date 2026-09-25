# A-T9 Codex Skill 注册、回滚与旧布局迁移（隔离 HOME 部分）

| 项 | 内容 |
| --- | --- |
| 阶段 / 类型 | A 路 / 核心能力（安装器） |
| 依赖 | A0 合入 `main` |
| 执行者 | AI Agent（可以是 flow-quality 会话，也可以另派） |
| 验收人 | Claude Code |
| 分支 / PR 目标 | 从 `origin/main` 开 `codex/flow-quality-t9` → **`main`** |
| 状态 | 待领取（被 A0 阻塞） |

## 目标

实现 SPEC §8：`install activate` 在 Codex 中注册单一 `deck-master` Skill；`rollback` 能正确撤销注册；一次性迁移本机旧 companion 布局。全部行为在**隔离 HOME** 中用测试证明（AC-18）。

## 背景与输入

- 规格：SPEC §8.1–8.3、§9 错误码，MIGRATION.md，TASKS.md 的 T9 行（路径同 A0）。
- 现有安装代码中的 `_activate_locked`：current 为真实目录时会拒绝执行，迁移逻辑必须在它之前运行。

## 可改范围 / 禁止

- **可改**：install / activate / rollback 相关模块、发布候选构建（`releases/<id>/skill/deck-master/` 从 wheel 的 `resources/skill` 提取）、CLI 帮助、`tests/` 新增测试。
- **禁止（红线）**：
  - 读写真实 `~/.codex`、`~/.deck-master`。所有测试必须用 `tmp_path` 作为 HOME、`CODEX_HOME`、PREFIX。
  - 修改 `config.toml`，或碰 `.system` 和第三方 Skill。
  - 注册到 `~/.claude/skills` 或 `.agents/skills`。
  - 自动删除 `legacy-companion-<ts>`。
  - 发版、打 tag。

## 实施步骤

- [ ] 1. 先写测试（隔离 HOME），覆盖 TASKS T9 的 ①–⑤：
  - ① 全新安装后，`$CODEX_HOME/skills/deck-master` → `PREFIX/.deck-master/current/skill/deck-master`，SKILL.md 可读；
  - ② 目标已被真实目录、真实文件或其他链接占用 → `host_skill_conflict`、exit 5，current 未切换；
  - ③ 构造旧 companion 布局（current 为真实目录，只有 schema v3、`bundled_symlink_only` 的 companion-manifest.json）、15 条 deck-* 断链和若干第三方 Skill → 迁移后只删除这 15 条，第三方原样保留，current 被移到 `legacy-companion-<ts>`；再跑一次结果不变；
  - ④ current 中有其他文件 → 拒绝并报告；
  - ⑤ 回滚到没有 skill 的旧版本 → 链接被移除，结果含 `host_skill_unregistered`，不留断链。
  - 另测 `--no-host-registration`：分开报告 `cli_active` 与 `host_unregistered`。
- [ ] 2. 实现，并输出逐条迁移报告（移动了什么 / 删除了哪些 / 跳过了哪些）。
- [ ] 3. 跑完整测试，开 PR，附一次隔离 HOME 下 `install activate` 的真实命令输出（R 类证据）。

## 验收标准

| AC | 标准 | 对应 |
| --- | --- | --- |
| AC1 | ①–⑤ 与 `--no-host-registration` 均有自动化测试，完整测试全绿 | AC-18 |
| AC2 | 任何测试、脚本都不触达真实 `~/.codex` 或 `~/.deck-master`（验收人检查 HOME / CODEX_HOME 的注入方式） | 红线 |
| AC3 | 错误都带 path、当前状态和下一步动作，退出码符合 SPEC §9 | SPEC §9 |
| AC4 | 迁移幂等，报告逐条列出 | MIGRATION §3 |

## 不在本卡（老板专属，后置）

- T9⑥ / AC-17：仓库外新开 Codex 会话，走 7 步真实场景（H 类证据）。
- 本机真实迁移：`deck-master install activate` 作用在老板的 `~/.codex/skills`。
- v0.9.15 发版、打 tag、launchd 部署。

以上都需要老板单独授权。在它们完成之前，本线只能交付为「工程候选」。

## 验收方法

1. 在独立 worktree 自建 venv，跑完整测试。
2. 在 `/tmp` 下构造隔离 HOME，亲自跑一遍 activate → 迁移 → 重复 activate → rollback，逐条核对报告。
3. `rg -n "expanduser|Path.home" <diff 涉及文件>`，确认 HOME 都可以注入。

## 交接回填

```text
执行者 / SHA / PR 链接 / 完成日期：
测试命令与结果：
隔离 HOME 实跑输出路径：
未验证项（T9⑥ / AC-17、真实迁移）：
```

## 验收记录

| 日期 | 验收人 | 结论 | 说明 |
| --- | --- | --- | --- |
