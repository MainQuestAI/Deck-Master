# N5 活动文档与入口核对（2026-10-19）

本报告记录基于 `a08bc68c1cbbbc806205104c2bb01f3f096305f0` 的共享 RC4 工作树文档变更与聚焦验证，不是最终候选 SHA、已发布 Release 或实际用户 HOME 安装证明。源码候选已由集成 Owner 统一更新为 `1.0.0rc4`；本报告不维护第二份执行台账。当前验收状态只以 [execution-ledger.json](execution-ledger.json) 为准，下列 AC 表仅供唯一 Owner 集成判断。

## 活动入口与职责

| 路径 | 处置 | 依据与消费者 |
|---|---|---|
| [README](../../../../README.md) | 活动保留，补齐正常入口 | 产品、候选状态、真实 create/continue → methods → task start → accept、提案决定/采用、content_only 与 full_deck、输入恢复和 N6 真实缺口；不复制六卡验收表。 |
| [AGENTS](../../../../AGENTS.md)、[CLAUDE](../../../../CLAUDE.md)、[意图索引](../../../agent-task-index.md) | 活动保留，链接当前增量 | README → 仓库规则/意图 → 本次卡或精确方法；继承 RC3/Flow Quality/rebuild 的相关合同，历史不作为所有任务的必读前置。四职责仍共用一个 Runtime、实际 scope 和当前控制。 |
| [ROADMAP](../../../../ROADMAP.md) | 收敛到当前六卡与唯一台账 | 不另写完成矩阵、不把旧 preview 里程碑或维护者环境当当前前置，不宣布发布。 |
| [恢复手册](../../../agent-recovery-playbook.md) | 活动保留，按错误与状态导航 | 保存简短恢复判断；完整输入与安装步骤链接原有 canonical 文件。另纠正缺 UI 时使用已移除界面的旧指引。 |
| [input-update](../../../../skills/deck-master/references/input-update.md)、[installation](../../../../skills/deck-master/references/installation.md) | 在原有真源补齐 N1/N2 合同 | 原 ID/base/payload/路径上下文、历史/当前结果与 unknown、旧日志/no-op 边界；UUIDv4 固定事务、历史 receipt 与当前观测、补偿/冲突保留、opt-out 和锁。没有新建同职责方法副本。 |
| [四 Skill](../../../../skills/RESOLVER.md) 的 `SKILL.md` | 活动保留，方法正文保持一处 | 明确 I05 冻结有序清单、旧 Task 不拼当前角色默认值、basis_changed 正式重发、完整适用前审方法并集、v2 full/冷上下文及传输证据边界。Content/Design/Review 不新增 references 目录。 |
| [CONTRIBUTING](../../../../CONTRIBUTING.md)、[PR template](../../../../.github/PULL_REQUEST_TEMPLATE.md) | 活动保留，CI 真源继续是 [rebuild.yml](../../../../.github/workflows/rebuild.yml) | 给真正收集并执行的聚焦命令；保留 Python 3.11/3.12 × Node 22/24、render、required browser、wheel/offline 与 installed recovery 责任及 DCO；去掉不存在的伪 CLI gate。 |
| Runtime contracts 与受控 spec mirrors | 全部保留 | `src/deck_master/resources/contracts/` 唯一活动 schema；69 个 packaged schema 恰好对应 69 个无重名镜像，逐字节一致。N4 v2 只新增当前增量下的一个对应镜像。 |
| [旧 CLAUDE](../../../archive/maintainer-environment/CLAUDE-before-rc4-20261019.md) | 维护者环境说明历史保留 | 与固定基线 `CLAUDE.md` bytes/SHA 完全一致；当前入口只链接说明其历史身份，不假定索引、worktree pin、Mac 服务、固定端口或部署已存在。 |
| `product_capabilities/` | 可归档候选，继续保留 | 在 src/tools/build/CI/四 Skill/活动入口的本轮字符串核对未见生产依赖，但 rebuild disposition、旧合同/报告和历史 SHA 清单存在合法引用，未证明全局零引用；没有为关闭 N5 强行归档或删除。 |
| `resources/static/v2/` | 活动保留 | Studio HTML 实际引用其 CSS、图标和模块；pyproject、doctor、build_release 与 installed UI 测试也消费它，不能按目录名推断退役。 |
| 旧 specs/reports/archive | 历史保留，缩小默认阅读面 | N5 不改写旧 SHA、日期、失败记录或“当时 PR 待合并”等事实；显式历史登记继续保留，代码不因位于历史/日期目录获得扫描豁免。 |
| 当前增量原始 19 份 payload | 原文保留 | 对接收时 `manifest.sha256` 再次核对 19/19；未用改 Spec 原文来使活动守卫通过。新增实际 schema mirror 不冒充原始交付文件。 |

## 恢复与读取核对

- 输入：新原子 receipt 的精确重放先于素材读取；保留原 payload/base/ID/路径上下文。原结果版本与当前版本分列，原 pending_tasks 要由新的 continue 更新。unknown 不允许换 ID/base 重做。旧日志按原记录验证，log-only no-op 的全失日志能力边界明确；普通 unchanged 可推进 receipt-only revision，而 Page/input basis、任务和调用不变。普通 inputs 与 content.inputs 不混用操作族或摘要。
- 安装：可选 canonical UUIDv4 精确绑定与冻结 rollback；匹配 pending 自动恢复，异请求显式拒绝。完成回执是历史事实，当前链接是独立观测；无 ID 的新 rollback 可再次切换。补偿中断、外部冲突、保留 backups 和 unknown 不伪报恢复。opt-out 不解析/读取/锁定/写 Host，prefix → Host 锁顺序明确。
- 方法与兼容：I05 是有序清单唯一来源。旧 Task 仅使用可证明的 RC3 selector/digest；缺失/drift 保留事实并走正式 reissue，未决调用先结清。新持久 manifest/policy 与 `rc4-content.v1` 原子保存；只读、旧接受结果重放与有 committed 证明的旧 proposal 不追溯升级。安装 rollback 不降低项目 writer floor。
- 读取：实际 `capabilities.read_protocols` 决定是否请求 v2，未请求保留 v1，显式不支持不静默降级。full 默认且可重新取回；manifest 不 ready；CLI 没有可信 session/context generation 观测，cache offer 不能省略正文。完整来源、Page/notes、限定、原图与物理约束须保留。返回或省略字节不证明 Host 阅读、应用、审查独立性或批准。

上述说明核对了 N1/N2/N3/N4 实现交接与实际 CLI。`final-readiness` 是 main 中保留的兼容适配入口，不能因它不在 argparse 子命令列表就称其不存在。18 组其他文档命令通过实际 parser 检查；这仅验证入口/flag，不冒充已完成业务任务或授权操作。

## 已执行验证

1. 文档示例的聚焦组实际收集 28 项并执行：`test_package_boundary`、`test_entry_capabilities`、`test_rc3_early_methods`、`test_rc3_content_methods`，结果 **28 passed in 12.36s**。该次运行早于最后补入的逐出现位置/原始 Spec 断言，不用它替代后续守卫结果。
2. 最终 N5 守卫及职责/传输组：`test_package_boundary`、`test_rc3_four_skills`、`test_rc4_work_context`，结果 **72 passed in 15.39s**；原始摘要 [N5-focused-tests.log](N5-focused-tests.log)，[JUnit](N5-focused-junit.xml)。两组有重叠，不相加为唯一测试数。
3. 七条 package-boundary 检查覆盖四 Skill/CLAUDE、明确负面/历史文字、真正正向误用、同一行先否定后执行、无关 retired 字样、日期目录和历史目录内代码、唯一镜像集合与 bytes。没有新增整片 Spec 豁免；两个冻结 inventory 工具只按明确文件登记其合法扫描用命名。保存本报告后复核 **7 passed in 11.11s**，见 [N5-guard-final.log](N5-guard-final.log)。
4. 修改的 Python 测试 Ruff、`git diff --check` 通过；原始 Spec 19/19 SHA 通过；旧 CLAUDE byte-identical；14 个活动 Markdown 文件的 45 个本地文件链接和本报告首版的 18 个链接存在。链接检查限所列入口/报告，未做全仓/外网爬虫或锚点可达性证明。

详细 hash、命令、范围和实际源码 capability 观测在 [N5-document-evidence.json](N5-document-evidence.json)。其 `canonical_checkout` 身份和旧 editable metadata `1.0.0.dev2` 只是本地源码环境观测；不能拿来关闭最终 wheel/installed 身份验证。源码 `__version__` 与 capability `package_version` 此时均为 `1.0.0rc4`。

## AC 建议，供唯一台账 Owner 采用

| AC | 建议与证据 | 仍需处理 |
|---|---|---|
| AC-N5-01 | 建议 PASS：当前入口/继承顺序、六卡、四职责与实际环境检测可导航。 | 最终候选入口快照由集成确认。 |
| AC-N5-02 | PASS（实际正常路径证据）：Quick Start 顺序/Task envelope 与实际 N6 阶段一致；用户真实方向记录后，Narrative/Plan/六页 v2 由 Runtime 接纳，content_only continue 返回 completed。 | 实际路径见 [N6](N6-evidence.md) 与 [采用证据](N6-runtime-adoption.json)。本地真实效果/可信 Host receipt 验收单列延期，不虚标专业通过，也不将额外前审作为 content_only 门槛。 |
| AC-N5-03 | 建议 PASS：六项恢复/读取/兼容说明已按 N1–N4 实现与 focused evidence 核对；N5 72 项含 frozen basis/v2/职责实际回归。 | 根 Owner 最终复核 N1/N2/N3/N4 收口证据。 |
| AC-N5-04 | 建议 PASS：处置表、历史 bytes、原 19 payload 和产品声明保留原因均可核对。 | 不强迫完成可选归档。 |
| AC-N5-05 | 建议 PASS：原有入口和 canonical refs 各守职责；四 Skill 无独立方法副本。 | 最终 wheel 验证另属 N5-08。 |
| AC-N5-06 | 建议 PASS：七条边界检查及真实误放行正/合法历史负面样例已通过。 | 无整片新增免检。 |
| AC-N5-07 | 建议 PASS：69/69 集合、无重名和 bytes 一致，保留全部既有镜像。 | 最终候选如改合同须再次执行现有 gate。 |
| AC-N5-08 | 建议 NOT_RUN：源码版本已统一，但本工作流未验证最终候选 wheel、release manifest、隔离实例和四 Skill bytes/hash。 | 消费集成 Owner 的准确候选 SHA/安装证据；HOME、公开 Release 仍独立报告。 |
| AC-N5-09 | 建议 PASS：聚焦命令已收集并实际执行，CI 说明逐项核对当前 workflow，DCO 与 required gate 保留。 | 本报告不声称最终 exact-SHA CI 已通过。 |
| AC-N5-10 | 建议 NOT_RUN：活动入口、证据与限制已提供，唯一 ledger 尚待最终候选集成；旧 PR 状态由根 Owner 实际读取。 | 等候最终 ledger/SHA、旧 PR113 处置报告、安装/CI 与当前候选交接；不能凭本报告自行填 PASS。 |

根 Owner 已实际核验 PR113 仍是 open draft，且与当前 main 分叉；后续 PR120–123 已合并。其 compare 文件有 300 项上限，不能宣称已逐文件证明覆盖全部旧差异。建议保留历史并由 Owner 记录过期总 Draft 的处置建议；N5 未关闭该 PR。

N5 没有提交、推送、创建/关闭 PR、改授权、付费调用、修改真实 HOME、merge、tag、Release 或部署。没有 N5 动作处于批准等待、被拒或结果不确定；剩余阻断是明确的 Runtime/验证边界，最终发布与状态收口由集成 Owner 处理。
