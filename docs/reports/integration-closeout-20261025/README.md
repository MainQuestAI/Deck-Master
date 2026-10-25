# 整合收口 · 2026-10-25

当前阶段：已建立第一阶段源码候选；UI 与修复主线的交叉整合尚未完成。这里记录整合事实和接续入口，不把源 PR 的 CI、工程验证或文档补齐当作专业签收。

## 固定输入

以远端 main `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` 起步，正常合并：

| 输入 | 固定 HEAD | 本候选处置 |
| --- | --- | --- |
| [PR184](https://github.com/MainQuestAI/Deck-Master/pull/184) | `7bbf204658dfc39f53fa34352543168e7eee1e65` | 已纳入文档基准；本轮补充两个开放审查的任务卡遗漏，不修改原 PR 线程状态 |
| [PR185](https://github.com/MainQuestAI/Deck-Master/pull/185) | `bf4f661bfec4aa28db2869aaf43494d6cf0f4b8d` | 已纳入 RP 实现和其全部历史；专项验收残项保留 |
| [PR187](https://github.com/MainQuestAI/Deck-Master/pull/187) | `870db06e7067c935b2331ade7f39e6bc20b8393d` | 已纳入 current_work、outline、来源/外部报告返修和后续测试诊断 |
| [PR109](https://github.com/MainQuestAI/Deck-Master/pull/109) | `7307dcfc027c4aca2b83b5eb9db616fce1e6f867` | 已纳入两个工作流的 upload-artifact v7；未改变测试矩阵或门限 |
| [PR188](https://github.com/MainQuestAI/Deck-Master/pull/188) | `159cfd63e9bcf71c10d98dad45a1a2567eb52136` | 待交叉整合；本候选当前没有其新版 UI |
| [PR147](https://github.com/MainQuestAI/Deck-Master/pull/147) | `ad2f278cd637f29b5665fcf71d7064098faf617b` | RP-00 已移植对应窄修复；不重复整枝合并。最终须结合 PR188 的兼容接口重验覆盖 |
| [PR113](https://github.com/MainQuestAI/Deck-Master/pull/113) | `0af67a4d7015725e663b4db09c50e241974d9e53` | 不并入当前候选；旧稿 CI 失败且有冲突，先对照后续已合并 RC3 范围，未授权自动关闭 |

精确 PR、检查和未解决线程见 [观察快照](pr-snapshot.json)。当前 7 个源 PR 保持原状态；其中 6 个最终检查通过，PR113 仍失败。源 PR 没有 APPROVED 审查；源 PR 通过不覆盖本整合候选。

## UI 交叉整合

在第一阶段提交 `935e4229c8e6dd77e0a33a95b5cd2724185c685e` 上执行：

```sh
git merge-tree --write-tree 935e4229c8e6dd77e0a33a95b5cd2724185c685e 159cfd63e9bcf71c10d98dad45a1a2567eb52136
```

结果为 **36 个冲突文件、71 个冲突块**：合同 2、runtime 11、前端/示例 11、测试 12。另有 24 个双方均修改但文本自动合并的文件，仍需语义核对。逐文件三阶段 blob 身份和重叠清单见 [机器记录](ui-merge-preflight.json)，原始输出见 [Git 记录](ui-merge-preflight.txt)。虚拟冲突树不是可运行候选，也未写入本分支。

整合保留的行为：

- PR188 的已确认 UI 层级、阅读/编辑/来源边界、控件和导航；PR187 的 current_work v2 与 outline 审查不能退回旧 UI 状态推断。
- 默认 `/api/project` 保持完整兼容，新 UI 协商轻量控制读取；轮询单飞及过期响应隔离保持，不将轻量读投影用于写入资格。
- 已采用正文按提交回执和当前产出判断；未知调用、取消、暂停后的精确重放、原 finding 和外部报告归属保持。
- 活动合同以 `src/deck_master/resources/contracts/` 为准；文档镜像同步。不通过删除断言、提高门限或重新归类失败来解除整合阻断。

## 接续顺序与完成条件

| 阶段 | Owner | 状态 | 依赖、范围与下一动作 |
| --- | --- | --- | --- |
| I0 固定来源 | 当前整合 Agent | DONE | 保留原 PR SHA、CI 和线程事实 |
| I1 第一阶段候选 | 当前整合 Agent | SOURCE_READY | 纳入 184/185/187/109；在独立 Python 3.12 环境做针对性回归，结果单列 |
| I2 UI/runtime 交叉整合 | 当前整合 Agent | PENDING | 依赖 I1 固定提交；36 个冲突和 24 个自动合并重叠逐项核对，先合同/恢复，再投影/轮询，再 UI/测试；不得整文件选一边 |
| I3 完整工程门禁 | 当前整合 Agent / GitHub CI | PENDING | 在最终候选跑全部四组单元、渲染、真实浏览器与汇总，保留失败/重试/跳过身份 |
| I4 最终安装与连续任务 | 当前整合 Agent | PENDING | 依赖 I2/I3；从同一冻结源码构包、核对包内资源及模块路径，再跑离线/固定下载与连续任务 |
| I5 专业与外部专项 | 真实 Host、审查者与老板 | NOT_RUN | 逐项对应 RP16/19/20/21/24/28/30、PR188 AC14/18、S3 效果和视觉认可；工程测试不替代。跨执行复用产品决策不在本轮新增授权内 |
| I6 合并与 PR 整理 | 老板决定、整合 Agent 执行 | PENDING | 依赖候选与相应验收明确；提供最终差异、检查与残项后决定合并，源 PR/Issue 不自动关闭 |

任何阶段的新源码必须产生新的候选身份；不得把源 PR 的历史检查改写成整合候选通过。当前阶段没有发布、默认安装切换、真实 HOME 迁移、模型调用或客户项目写入。
