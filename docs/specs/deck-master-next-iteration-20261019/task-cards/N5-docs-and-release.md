# N5｜活动文档、版本入口与冗余治理

## 0. 任务登记

| 项目 | 约定 |
|---|---|
| 唯一 Owner | N5；集成 Owner 负责接受最终版本与报告 |
| 固定基线 | MainQuestAI/Deck-Master@a08bc68c1cbbbc806205104c2bb01f3f096305f0 |
| 目标版本 | 建议 1.0.0rc4；当前仍为 1.0.0rc3 |
| 状态 | 待开发 Spec；没有修改现有活动文档或发布版本 |
| 前置依赖 | 活动入口梳理可立即开始；最终命令、兼容说明和版本收口依赖 N1–N4 及 N6 的实际改进 |
| 主要结果 | 外部读者和执行 Agent 能从少数活动入口得到正确当前流程；历史资料保留时点与来源；代码、候选包与安装身份可核对 |

本卡解决活动说明漂移和重复维护。不是按文件数量删文档，也不把历史报告更新成新的运行事实。用户本机安装、活动 Skill、实际工具及后续候选行为均**需要 Codex 核验**。

## 1. 基线问题与处理范围

| 基线问题 | 固定证据 | 本轮处理 |
|---|---|---|
| README 是 rc3，ROADMAP 仍将 preview.4 视为当前，并要求旧 backend bind | [README](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/README.md)、[ROADMAP](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/ROADMAP.md) | 路线图以本轮六项为当前计划，明确源码/候选/发布状态，不再要求旧绑定 |
| CLAUDE 将某维护者的索引、worktree pin、Mac launchd 和端口当作新克隆已配置事实 | [CLAUDE](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/CLAUDE.md) | 收敛到 AGENTS 和真实能力检测；维护者机器说明移入明确标注的可选运维记录 |
| Agent入口同时突出旧 rebuild 与 Flow Quality，多版本关系难判断 | [AGENTS](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/AGENTS.md) | 增加当前增量入口和继承顺序，不复制所有历史 Spec |
| Quick Start 简化了 framing 后的协作/执行阶段 | README Quick Start | 补可顺序执行的分阶段引导，指向实际 continue 返回动作；不能虚构从一条命令直接到交付 |
| CONTRIBUTING 将两次完整 pytest 当成 focused checks | [CONTRIBUTING](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/CONTRIBUTING.md) | 给真正聚焦验证和最终 CI 的职责分工，保留必须的 gate |
| pyproject 的 CLI 注释仍称入口尚未打开 | [pyproject](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/pyproject.toml) | 修正过时注释，console script 行为不变 |
| 活动扫描只列 skills/deck-master，root_files 没有 CLAUDE | [package boundary tests](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/tests/rebuild/test_package_boundary.py) | 扩展四 Skill 与 CLAUDE；禁止整片新增豁免以绕过失败 |
| product_capabilities 是约 13 KB 的旧声明候选，目前未发现生产导入 | 根目录声明与现有包清单 | 执行前核验代码/工具/构建/活动文档引用，确认后可归档；不因目录名字像旧模块就删除 |
| docs 中有大量旧 Spec 和定点报告 | 上轮工作树盘点 | 优先缩减活动阅读面；历史保留，不设“必须删掉某比例”指标 |

## 2. 活动文档职责

沿用已有文件，不新建与它们职责相同的一套顶层索引。

| 文件/区域 | 唯一职责 | 应保留/应转移 |
|---|---|---|
| README.md | 产品用途、当前状态、最短正常入口、边界和主要文档链接 | 不复制完整开发 Spec 或逐项验收台账 |
| AGENTS.md | 仓库规则、当前开发入口、真源与执行边界 | 链接本轮包；旧规格按继承关系引用 |
| CLAUDE.md | Claude 入口适配和必要差异 | 通用规则链接 AGENTS；机器事实必须可检测或标为可选配置 |
| docs/agent-task-index.md | 用户意图 → 当前命令/Skill/恢复入口 | 增加当前迭代与历史入口区，不再创建同职责的新索引 |
| docs/agent-recovery-playbook.md | 按真实错误码恢复 | 接收 N1/N2/N3/N4 的已实现恢复方式 |
| ROADMAP.md | 当前六项计划、状态和后续决策条件 | 旧路线移到历史引用，不继续作为当前默认前置 |
| CONTRIBUTING.md | 开发环境、聚焦验证、PR/DCO要求 | 总 CI 真源仍为工作流，避免另一套矩阵漂移 |
| skills/*/SKILL.md | 四角色触发、输入输出、禁止越界与真实方法入口 | 不复制 canonical 方法正文到四个目录 |
| skills/deck-master/references/ | 唯一可编辑的方法与安装/恢复说明 | N6/N1/N2/N3 的有依据增量合并至原文件 |
| docs/specs/ | 已定义合同与任务的版本化开发输入 | 本轮只一个增量包，活动入口链接它 |
| docs/reports/ | 带 SHA、日期和范围的证据快照 | 报告固定事实不当作实时状态；有需要时加跳转说明 |
| docs/archive/ | 历史实现与旧材料 | 保留可追溯性，不纳入默认执行路径 |

默认阅读路径应是 README → AGENTS/意图索引 → 本次任务卡/所需方法。只为解决当前任务才继续进入相关历史合同，不把“通读全部历史 specs/reports”设为开始工作的要求。

## 3. 具体开发工作

### 3.1 当前入口和命令说明

1. README 状态同时区分 package version、候选验证状态和已发布 Release。代码未实现前使用“规划”，合入后基于实际结果更新。
2. Quick Start 补足以下概念顺序：创建并导入真实来源 → 根据 continue 的 framing/argument/page_copy/speech 等当前任务工作 → 按实际协作决定与既有 claim/start/accept 合同执行 ；content_only 完成完整内容与适用审查/导出，full_deck 再查看实际图片/PPT 预览并按 review/delivery 用途导出。示例只教当前确实支持的命令与 envelope。
3. 不固定每个项目都要走同样的 phase 数；已确认稿导入仍按 imported_mapping 合同，教学不强制 CTA。
4. 输入变更展示原 operation ID/base/payload 的恢复方式、不同族不能混用 ID、unknown 的排查入口，以及 unchanged 可带 receipt-only revision 的新行为。
5. 安装说明展示精确 transaction-id、未完成恢复与无 ID 新 rollback 的区别；活动版本与四 Skill 必须由实际 install/capabilities 读取核对。
6. v2 读取说明仅在实际支持的入口使用；告知 full 默认、完整原文取回、basis_changed 恢复和 v1兼容。
7. 使用中性材料与示例目录；不能把维护者绝对路径、端口或默认存在的本机索引写成用户的当前环境。

### 3.2 冗余与归档

先形成小型路径处置表，列出“活动保留、合并后链接、历史保留、可归档候选”及消费者。该表属于本卡证据，不建设新文档数据库。

- 重复操作步骤：选择已有职责文件为真源，其他活动文件保留简短上下文和链接。
- 方法正文：四 Skill 的入口可不同，实际方法正文仍只一处；不要为减少正文长度删掉必要反例、限定与恢复说明。
- 历史报告：保留原 SHA、日期、失败/修复记录；在当前入口标出它是某候选快照。不要把旧“PR待合并”改成“当时已合并”。
- candidate product_capabilities：逐项做引用核验，确认不是运行/打包输入后才移入明确历史位置并修复合法历史链接。无法确定时保留并记录后续，不影响其他文档收口。
- 不删除现有 68 份 schema 的受控镜像；N3 修改既有镜像，N4 新响应合同增加且只增加一个对应镜像。
- 不删除 static/v2：当前 studio HTML 仍依赖它。资源精简必须有真实依赖与 installed UI 验证，不按目录名称推断退役。
- 不删除客户材料、生成 runs、真实产物、字体、第三方 Skill；不运行历史重写或全目录清理。

### 3.3 文档守卫

扩展现有 package-boundary 测试的活动表面至四 Skill 和 CLAUDE。测试关注会误导执行的退役命令、错误绑定指引、旧代码依赖及不受控镜像；不因出现“PPT Master”这个名词就失败。README 中“无需绑定”或历史迁移说明属于合法上下文。

对维护者机器指引，用小型、明确的规则检查“默认已配置”断言或不当活动指向；不要建立泛化 NLP 评分、全仓严格链接爬虫或每次 CI 联网检查外链。验证新增守卫时须有：

- 一个当前活跃四 Skill/CLAUDE 的错误示例能被捕获；
- 一个合法的否定/迁移/历史上下文能通过；
- 日期命名目录不会自动获得豁免；
- 非代码历史证据可按现有显式登记规则处理，代码不能借位置逃逸。

新增 schema 的集合守卫继续保证 packaged set 与全部受控 spec mirrors 相等、无同名多份、逐字节一致。不要通过删旧镜像或宽泛忽略目录消除失败。

### 3.4 候选版本与实际资源

由 N5/集成 Owner 在最终代码与方法变更合入后统一更新候选版本。核对实际包含版本的文件与构建脚本，不凭记忆列固定完整清单。

至少覆盖 package metadata、__version__（若实际存在）、README状态、release manifest、安装树及 capabilities 暴露的实际方法身份。新构建 wheel 的 method/source/hash 必须来自该候选字节，不借 editable checkout 成功。

当前 latest Release 旧于源码不是自动发布授权。代码候选、隔离安装验证、用户本机激活、公开 tag/Release 状态分别报告。安装回滚不降低项目已提升的 writer floor。

### 3.5 旧 PR 与当前执行状态

核对旧 draft PR113 是否已被 PR120–123 等替代，只记录其替代关系、剩余差异及建议处置。不得将一个旧 draft 状态当作当前代码未合并的证据，也不在本轮 Spec 交付时自动关闭 PR。

当前执行台账是唯一 PASS/FAIL 状态源。README、ROADMAP、PR说明和收口报告以它为投影，不能各维护一张互相漂移的完成表。

## 4. 验收标准

所有 AC 的唯一 Owner 均为 **N5**，当前均待执行。

| AC ID | Given | When | Then |
|---|---|---|---|
| AC-N5-01 | 新读者从 README/AGENTS/CLAUDE/意图索引进入 | 按当前任务导航到 N1–N6 与四 Skill | 能找到唯一当前增量入口和规则优先级；无强制旧backend绑定、假设已存在的本机索引或冲突的当前版本声明 |
| AC-N5-02 | 本轮候选与中性完整材料 | 按 Quick Start 和 continue 的实际阶段完成 N6 可复用的普通任务路径 | 文档命令、任务/envelope与实际输出相符；协作/执行必要步骤没有被示例跳过；缺能力真实报告，不用fixture冒充成品 |
| AC-N5-03 | N1/N2/N3/N4 已固定并实现的恢复与读取合同 | 阅读输入/安装/旧Task/v2的活动说明并执行聚焦用例 | 原ID/base、unknown、noop revision、transaction-id、basis_changed与full取回均被准确解释；没有虚构新命令或隐含审批 |
| AC-N5-04 | 含日期/SHA的旧report、旧spec及可归档声明候选 | 执行活动入口整理与获证据支持的移动 | 历史事实与原失败记录保留；引用完整；候选无足够零引用证明时保留且说明；不重写Git历史或用户产物 |
| AC-N5-05 | 同一操作步骤或方法在多个活动文件出现 | 收敛到已有职责真源 | 活动副本改为清晰链接；四Skill方法正文仍只有canonical来源；不因缩短文件删必需方法/反例/限定 |
| AC-N5-06 | 四Skill、CLAUDE的错误活动指引，以及合法否定/迁移/历史正例 | 运行扩展后的package-boundary守卫 | 错误能检出、合法上下文通过；日期不自动豁免；无整片目录忽略以压掉失败 |
| AC-N5-07 | N3改动现有schema，N4新增只读schema | 运行活动合同/镜像集合与bytes一致检查 | 每一package schema恰有一个受控镜像；集合相等；不复制第二套Task/schema真源或删除既有镜像 |
| AC-N5-08 | 最终候选代码、method字节和构建wheel | 在隔离安装读取version/capabilities/四Skill路径hash并与候选比对 | 版本与实际安装资源一致；没有借checkout方法；源码/候选/隔离安装/本机激活/公开Release各自状态诚实 |
| AC-N5-09 | CONTRIBUTING、CI工作流与本轮证据规则 | 核对并实际使用聚焦验证和最终gate说明 | 不将两次全套pytest伪称focused；required browser/render/installed职责保留；测试命令真实可用，缺能力不假PASS |
| AC-N5-10 | 当前候选台账、六卡证据、旧draftPR替代关系和已知限制 | 生成最终入口/迭代报告/交接说明 | 状态来自同一台账，准确标SHA与证据层；本轮未发布/未激活不写已完成；相关文件可导航、无缺失本地链接 |

## 5. 实施与验证建议

先修直接影响执行的活动入口，再整理被它们引用的文档；无需通读和重排所有历史材料。新增守卫使用少量正反例验证真实误导风险，不为标点、拼写和纯链接重排写实现镜像测试。

聚焦验证优先现有 tests/rebuild/test_package_boundary.py、test_entry_capabilities.py 和安装/四 Skill 路由相关测试。N5-02 与 N6 正常任务可共用同一证据，N5-08 可消费 N2/N3 的最终候选 installed 证据；唯一 Owner 仍分别判断各自 AC，不能重复制造整套实验。

## 6. 完成输出

- 当前活动入口的代码差异、文档处置表及合法历史引用。
- 六项恢复/读取/兼容方式的准确活动说明。
- 聚焦守卫结果、真实正常路径引用、版本/安装身份和镜像一致证据。
- 由唯一台账生成的当前候选交接与限制；未执行的用户本机激活和外部发布单列。

不设文档减量百分比，也不要求完成可选历史归档才能关闭已达成的活动入口工作。若活动入口仍有矛盾、文档教了不存在的能力或安装方法身份不一致，本卡不能通过。

