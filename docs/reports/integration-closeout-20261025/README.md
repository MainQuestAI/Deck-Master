# 整合收口 · 2026-10-25

当前阶段：已完成第一阶段候选及 UI/runtime 交叉整合，正在运行完整工程门禁。这里记录整合事实和接续入口，不把源 PR 的 CI、工程验证或文档补齐当作专业签收。

## 固定输入

以远端 main `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` 起步，正常合并：

| 输入 | 固定 HEAD | 本候选处置 |
| --- | --- | --- |
| [PR184](https://github.com/MainQuestAI/Deck-Master/pull/184) | `7bbf204658dfc39f53fa34352543168e7eee1e65` | 已纳入文档基准；本轮补充两个开放审查的任务卡遗漏，不修改原 PR 线程状态 |
| [PR185](https://github.com/MainQuestAI/Deck-Master/pull/185) | `bf4f661bfec4aa28db2869aaf43494d6cf0f4b8d` | 已纳入 RP 实现和其全部历史；专项验收残项保留 |
| [PR187](https://github.com/MainQuestAI/Deck-Master/pull/187) | `870db06e7067c935b2331ade7f39e6bc20b8393d` | 已纳入 current_work、outline、来源/外部报告返修和后续测试诊断 |
| [PR109](https://github.com/MainQuestAI/Deck-Master/pull/109) | `7307dcfc027c4aca2b83b5eb9db616fce1e6f867` | 已纳入两个工作流的 upload-artifact v7；未改变测试矩阵或门限 |
| [PR188](https://github.com/MainQuestAI/Deck-Master/pull/188) | `159cfd63e9bcf71c10d98dad45a1a2567eb52136` | 已逐块接入新版 UI；交叉行为取舍见 [整合记录](merge-resolution.md) |
| [PR147](https://github.com/MainQuestAI/Deck-Master/pull/147) | `ad2f278cd637f29b5665fcf71d7064098faf617b` | RP-00 已移植对应窄修复；不重复整枝合并。最终须结合 PR188 的兼容接口重验覆盖 |
| [PR113](https://github.com/MainQuestAI/Deck-Master/pull/113) | `0af67a4d7015725e663b4db09c50e241974d9e53` | 不整枝合并；来源对照发现祖先授权撤回后的任务写门控缺口，已独立复现并做当前合同下的窄修复。其余旧稿差异保留，未自动关闭 |

精确 PR、检查和未解决线程见 [观察快照](pr-snapshot.json)。当前 7 个源 PR 保持原状态；其中 6 个最终检查通过，PR113 仍失败。源 PR 没有 APPROVED 审查；源 PR 通过不覆盖本整合候选。

## UI 交叉整合

在第一阶段提交 `935e4229c8e6dd77e0a33a95b5cd2724185c685e` 上执行：

```sh
git merge-tree --write-tree 935e4229c8e6dd77e0a33a95b5cd2724185c685e 159cfd63e9bcf71c10d98dad45a1a2567eb52136
```

结果为 **36 个冲突文件、71 个冲突块**：合同 2、runtime 11、前端/示例 11、测试 12。另有 24 个双方均修改但文本自动合并的文件，仍需语义核对。逐文件三阶段 blob 身份和重叠清单见 [机器记录](ui-merge-preflight.json)，原始输出见 [Git 记录](ui-merge-preflight.txt)。上述是合并前的固定预检记录。后续已在本分支逐块解决全部冲突，并核对自动合并重叠；取舍与复现见 [整合记录](merge-resolution.md)。

整合保留的行为：

- PR188 的已确认 UI 层级、阅读/编辑/来源边界、控件和导航；PR187 的 current_work v2 与 outline 审查不能退回旧 UI 状态推断。
- 默认 `/api/project` 保持完整兼容，新 UI 协商轻量控制读取；轮询单飞及过期响应隔离保持，不将轻量读投影用于写入资格。
- 已采用正文按提交回执和当前产出判断；未知调用、取消、暂停后的精确重放、原 finding 和外部报告归属保持。
- 活动合同以 `src/deck_master/resources/contracts/` 为准；文档镜像同步。不通过删除断言、提高门限或重新归类失败来解除整合阻断。

## 接续顺序与完成条件

| 阶段 | Owner | 状态 | 依赖、范围与下一动作 |
| --- | --- | --- | --- |
| I0 固定来源 | 当前整合 Agent | DONE | 保留原 PR SHA、CI 和线程事实 |
| I1 第一阶段候选 | 当前整合 Agent | TARGETED_PASS | 纳入 184/185/187/109；独立 Python 3.12 定向核心 234 通过，真实 Chromium 35 通过；未执行最终全量和安装门禁 |
| I2 UI/runtime 交叉整合 | 主 Agent + 3 个子 Agent | IMPLEMENTED | 36 个冲突和 24 个自动合并重叠逐项核对；新版 UI、current_work、审查/返修与恢复边界已接入，仍以 I3/I4 最终结果为准 |
| I3 完整工程门禁 | 当前整合 Agent / GitHub CI | PENDING | 在最终候选跑全部四组单元、渲染、真实浏览器与汇总，保留失败/重试/跳过身份 |
| I4 最终安装与连续任务 | 当前整合 Agent | PENDING | 依赖 I2/I3；从同一冻结源码构包、核对包内资源及模块路径，再跑离线/固定下载与连续任务 |
| I4a 外部兼容与性能专项 | 历史安装资源与工程验收 owner | PARTIAL | Frozen A 两条单元参数例及一条渲染例缺固定旧安装；RP28 真实候选采用/恢复已有渲染回归，完整工具链 CPU 收益另需计量，不额外要求模型或人工专业批准 |
| I5 专业与实际任务专项 | 真实 Host、审查者与老板 | NOT_RUN | RP16/19/20/21/24/30、PR188 AC14/18、S3 效果和视觉认可仍需对应实际证据。bounded settled-image reuse 与外部报告记录/返修清单已实现，不能沿用旧文档的笼统“未实现”；单调用迁移等范围扩展不在本轮新增授权内 |
| I6 合并与 PR 整理 | 老板决定、整合 Agent 执行 | PENDING | 依赖候选与相应验收明确；提供最终差异、检查与残项后决定合并，源 PR/Issue 不自动关闭 |

任何阶段的新源码必须产生新的候选身份；不得把源 PR 的历史检查改写成整合候选通过。当前阶段没有发布、默认安装切换、真实 HOME 迁移、模型调用或客户项目写入。

在 `9abdcb7b` 的完整门禁期间，来源清理又复现祖先授权撤回后的实际任务启动/正文接纳缺口；安装回归另发现一个嵌套折叠标题的旧测试定位歧义。后续窄修复和回归见 [收口补充](closure-followup.md)。`9abdcb7b` 的已通过结果保留为旧候选证据，不能覆盖补丁后的最终候选。

## 第一阶段验证

冻结测试提交 `a07fb1610550fa3e4a5a28cc4e6fde4b0b1d877d`，产品树 `c88cbb4ce13c8d34e87f0430dfc83f08e59a5fd9`。本段与 [机器记录](validation.json) 为随后文档补充，未改该产品树。

- Python 3.12.15 / Node 26.12.0；17 个核心模块 **234 passed / 26 deselected**，覆盖 current_work、outline、普通来源 finding、外部报告修复交接、暂停重放、回执、候选、原件、旧包边界和 native 恢复；合成身份与报告测试不是实际模型/专业验收。
- 四个真实 Chromium 模块 **35 passed / 19 deselected**，使用 `--require-browser`，覆盖两入口 current_work、模态导航、30 页轮询重用及原生 close 后的键盘焦点。Playwright 1.64.1 / Chromium 156.0.8078.4，使用独立任务目录中的官方浏览器。
- 轮询 Node 专项 15 条、Ruff、完整 main→候选 whitespace、任务卡与机器定义一致性、四个来源的 ancestry 和 UI188 未纳入检查通过。
- 浏览器首次 **29 failed** 全部为启动时缺少匹配 Chromium；无已执行 UI 断言失败。官方安装首次 TLS 重置后自行重试成功，再执行上述 35 项。原失败 JUnit 保留，未改用例、断言或时限；不记作首次全绿。
- 完整 diff 检查发现源分支 `action-summary.js` 多一个末尾空行；仅删除该空行，未修改 JS 行为。最早 207 项核心结果属于 `9adc6ebc`；本节记录重新冻结后的 234 项，不能混用 SHA 或累加测试数。

原始 JUnit 留在本任务 worktree 的父目录，未冒充公开附件；机器记录给出摘要与 SHA256。以上仅为第一阶段历史结果，不把该定向通过表述为最终整合交付通过。后续 UI188 交叉整合与验证另见整合记录。
