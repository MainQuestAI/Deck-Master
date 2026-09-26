# MIGRATION v1.1：旧 Skill 退役与本机旧安装迁移

## 1. 旧 Skill → 新用法

旧 Skill 全部直接删除，git 历史可查。所有请求都统一进入 `deck-master`。

| 旧 Skill | 原用途 | v1.1 用法 |
|---|---|---|
| deck-init、deck-brief、deck-planner | 建工作区、提炼要点、规划结构 | `deck-master create --source … --task-file …`，由 Host 按 content-methods 写完整正文 |
| deck-sourcing、ppt-library | 选素材和证据 | 在 `create --source` 里传目录或文件；补材料用 `inputs update` |
| deck-producer、ppt-deck-pro-max | 逐页生成、导入结果 | `continue` → blueprint/reconstruct 工作单 → `task accept` |
| deck-builder、deck-builder-high-density、ppt-master | 渲染和重建 | 使用同一条 continue 主链路，由工作台查看 |
| deck-quality、deck-review、ppt-quality-gate | 质量门和交付审阅 | 最终 review 工作单（按缺口的六维）→ `export --purpose delivery` → `handoff-check` |
| deck-autopilot | 自动推进 | 循环调用 `continue`，直到 done 或出现具体阻塞 |
| deck-doctor | 诊断 | `deck-master doctor` |
| deck-setup、deck-upgrade | 安装和升级 | `deck-master install activate` / `rollback`（会注册 Codex Skill） |
| deck-learn | 记录反馈 | 不再提供。局部意见用 edit/feedback |

也要删除：`skills/manifest.json`、`skills/stage-contracts.json`，以及 `skills/deck-master/prompts/`、`skills/deck-master/schemas/`。`skills/RESOLVER.md` 改成一行，指向 `skills/deck-master/SKILL.md`。

旧 run 目录仍能被 cli.py 的 legacy 检测识别，并提示迁移方式，这部分行为不变。

## 2. 本机旧安装现状（2026-09-25 只读核对）

| 路径 | 现状 |
|---|---|
| `~/.deck-master/current` | **真实目录**，只有 `companion-manifest.json`（schema v3，release main-cc8cf46，`bundled_symlink_only`） |
| `~/.deck-master/releases`、`previous`、`bin` | 不存在 |
| `~/.codex/skills/deck-*` | 15 条符号链接，都指向 `~/.deck-master/current/skills/<name>`，**全部是断链**（包括 deck-master） |
| `~/.codex/skills/ppt-*` | 4 条旧符号链接，同样指向本安装的 `current/skills/`：ppt-master、ppt-library、ppt-deck-pro-max、ppt-quality-gate |
| `~/.codex/config.toml` | 没有 deck 相关的 skills 配置，只有一条项目 trust_level。**不需要改** |
| `~/.codex/skills` 其他条目 | gstack*、artifact-template-* 等第三方 Skill，**不能碰** |

结论：现在 Codex 里看到的 deck 系列 Skill 全部失效。现有 activate 会因为 current 是真实目录而拒绝执行，所以必须先做一次迁移。

## 3. 迁移过程（由 `install activate` 自动执行，SPEC §8.3）

1. 识别旧布局：current 是真实目录，并且里面只有符合特征的 companion-manifest.json。不符合的，拒绝执行并报告。
2. `mv ~/.deck-master/current ~/.deck-master/legacy-companion-<ts>`。只移动，不删除。
3. 删除 `~/.codex/skills/` 下同时满足以下三点的条目：
   - 是符号链接；
   - 名字匹配 `deck-*` 或 `ppt-*`；
   - 目标以 `~/.deck-master/current/skills/` 开头。

   本机预期 19 条（15 条 deck-*、4 条 ppt-*）；数量只用于验收，不作为硬编码删除条件。
4. 正常完成 activate：建立 releases/<id>、current、previous、bin。
5. 建立受管链接：`~/.codex/skills/deck-master` → `~/.deck-master/current/skill/deck-master`。
6. 输出迁移报告：移走了什么、删除了哪些链接（本机预期 19 条）、跳过了哪些条目。

## 4. 老板操作步骤（代码合并后）

1. 由 Codex 实施 T1–T9，并在隔离 HOME 中通过 AC-18。
2. 老板在本机执行：`deck-master install activate`（具体命令以实施后的帮助为准）。
3. 检查：`ls -l ~/.codex/skills/deck-master` 应指向 `~/.deck-master/current/skill/deck-master`，并且 `ls ~/.codex/skills | grep deck-` 只剩 `deck-master` 一条。
4. 新开一个 Codex 会话，走一遍 AC-17 的 7 步场景。
5. 出问题时执行 `deck-master rollback`。如果要回到迁移之前，`legacy-companion-<ts>` 目录还在，但它本身就是失效状态，没有恢复价值，确认无误后可以手动删除。

## 5. 不做的事

- 不注册到 Claude Code（`~/.claude/skills`）或 `.agents/skills`。
- 不修改 `~/.codex/config.toml`。
- 不自动删除 `legacy-companion-<ts>` 目录。

### 2026-09-26 迁移范围补充

只读核对发现另外 4 条旧链接：ppt-master、ppt-library、ppt-deck-pro-max、ppt-quality-gate，同样指向本安装前缀的 current/skills/。它们与 15 条 deck-* 一并按上述归属规则处理；外部前缀链接和真实文件/目录不动。禁用 Host 注册时不清理，随后正常激活可依据有效备份 manifest 补做清理；失败时按原补偿规则恢复。真实 HOME 尚未迁移。
