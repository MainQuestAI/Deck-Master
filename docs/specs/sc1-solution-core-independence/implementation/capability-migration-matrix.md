# SC-1 Q0｜能力迁移矩阵（capability-migration-matrix）

## 1. 能力与入口现状（基线 bcb5b37）

| 清单 | 内容 | 备注 |
|---|---|---|
| `required_capabilities`（17） | deck-master, deck-setup, deck-upgrade, deck-doctor, deck-init, deck-brief, deck-planner, deck-sourcing, deck-producer, deck-builder, deck-quality, deck-review, deck-autopilot, ppt-master, ppt-library, ppt-deck-pro-max, ppt-quality-gate | manifest 声明 |
| `public_skills`（15） | 15 个 deck-*（含 deck-builder-high-density、deck-learn） | D03：不新增公开入口 |
| `backend_dependencies` | deck-builder → ppt-master | 标准后端默认地位（D04） |
| suite skills（installer 19） | 15 deck-* + 4 ppt-* 兼容别名 | `installer.py:102-529` |
| `product_capabilities/`（4 包） | ppt-deck-pro-max, ppt-library, ppt-master, ppt-quality-gate：capability.json/yaml + contracts/* | deck-* 无 capability 包 |
| skill_routes / RESOLVER.md | RESOLVER.md:16-19 将生产/审查路由到 ppt-* 别名 | F09：与 manifest 公开策略矛盾，A1/A6 收敛 |

## 2. 安装覆盖矩阵（实测）

| 宿主 | global | project scope | 实际内容 | 本机实况 |
|---|---|---|---|---|
| codex | 支持（`~/.codex/skills`） | 支持（`<root>/.agents/skills`） | 每 skill 一个 symlink → 中心 release 树 | **无任何 deck-*/ppt-* 条目** |
| claude-code | 支持（`~/.claude/skills`） | 不支持 | 同上 | symlink 存在但 ≥10 个失效 |
| hermes | 支持（`~/.hermes/skills`） | 不支持 | 同上 | 未安装 |
| custom | 需显式 `--agent-skill-dir` | 不支持 | 同上 | 未安装 |
| cursor/其他 | **不支持** | — | — | 未知宿主支持不虚报（A6） |

- 中心 release 树 `~/.deck-master/current/`：仅剩 `companion-manifest.json` → suite_installation_blocked 的直接原因。
- `ppt-master`：project scope 只 `central_compatibility_only`（`installer.py:2540-2543`），adoption policy `preserve_full_external_or_bundled_symlink`（:413）——外部目录永不覆盖。
- schema/能力包只在 release 树（`contracts/`、`capabilities/`，目录名从 `product_capabilities` 改名复制），宿主目录不落。

## 3. 迁移矩阵（现状 → SC-1 目标）

| 对象 | 现状 | SC-1 目标 | 任务 |
|---|---|---|---|
| PPT Master 后端 | 外部仓库手动绑定；本机 unbound；`DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 钉第三方分支 SHA | 托管固定版本安装 + 真实 smoke 证据；桥接退役，production 生成只走 Agent 派发 | A1/A2 |
| PPT Library | 依赖用户 PATH 的 `ppt-lib`（本机 2.0.1.dev0 可用但不受产品管理） | 可执行程序与环境由产品 lock 管理；asset database 与 release 分离 | A3 |
| 能力锁 | `deck_capability_lock.json` 不存在 | 固定来源/包 hash/版本/契约/许可证/所有权 lock；同 lock 可重复安装 | A1 |
| 就绪语义 | `render_runtime_ready` 由 contract_probe 自报（F12）；suite-status blocked 但 reporting 混层 | 真实 smoke 证据替代自报；按任务就绪（execution plan）；缺组件显式阻断 | A2/A4 |
| library_mode=none | strict 模式强制真实检索；none 决策链未成为一等路径 | none 为正常生产能力：不调 Library、无 fixture selection、页面全覆盖 | A4 |
| 旧 skill 安装迁移 | `suite-migrate-legacy-skills` 已存在；本机 release 树残缺、claude 链接失效 | 隔离旧目录、dry-run/备份/校验/激活（D12）；升级失败回退；用户数据分离 | A6 |
| 版本元数据 | deck-planner/deck-review agents/openai.yaml 停 0.9.13（F10） | 随 release 单点更新 | A1/A6 |
| 方法资产 | 五份专业方法稿在本包 `methods/`，未内置 | 并入既有 skill 按需 references/playbooks，不新增公开入口 | A1/B 系列 |

## 4. 迁移安全约束（沿 D12）

- 迁移先 dry-run → 备份 → 校验 → 激活；不覆盖独立所有权目录（本机 `~/.claude/skills` 失效链接只登记，不代用户删除——Q0 禁止项）。
- 用户数据（run 目录、workspace assets、learning pack）与软件 release 树物理分离；回滚软件不删新数据。
- `external real directory`（外部真实 PPT Master/Library 目录）保留不动。
