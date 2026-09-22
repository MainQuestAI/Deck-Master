# 任务组织｜一个业务迭代，八个建议 PR

## 基本规则

同一大轮次完成 WP-A/B/C。PR 数量是执行建议，不是产品需求；可在职责清楚和可回滚前提下调整。不得把“内容内核”“真实 UAT”无限延后到另一轮来宣布本轮完成。

所有本地事实需要 Codex 核验。每个 PR 的实现以实际落库 Spec 与 deviation log 为评审 baseline，不以过时聊天中的文件名或版本号判断违规。

## PR 顺序

| PR | 任务 | 合并前必须证明 | 不得宣称 |
|---|---|---|---|
| PR-01 | Q0 基线、复用调用图、目标契约/迁移矩阵、验收样例 | baseline 报告、已知失败用例、Schema 与旧读写差异清楚 | 还未实现的运行时或质量升级已完成 |
| PR-02 | A1—A4 托管组件/标准后端/Library/任务就绪 | 隔离组件安装、标准真实 smoke、none 无假数据、required 依赖正确 | 仅安装目录存在即生产可用 |
| PR-03 | B1—B3 材料、研究、Brief/判断 | 后置约束、混合材料/宿主 handoff、来源与反证、无自证 | Context Pack 有字段即深度理解完成 |
| PR-04 | B4 + A5 公共方案/叙事、问题 authority | 不依赖空 Page Package、双写消除、强制提问规则实改、旧 HD 可读 | 再建一套不被主线调用的内容引擎 |
| PR-05 | B5—B6 页面/架构视图/标准与 HD | 真实 Page Package 消费、四类视图、两条构建内容一致、局部修改影响 | 能画图即架构正确；PNG 套壳即可编辑 |
| PR-06 | C1—C3 语义审查/定向修复/交付门 | 异步迟到/幂等/中断/权限、独立审查覆盖、当前批准、导出安全 | 新旧错误被改 status 变成通过 |
| PR-07 | C4—C5 反馈口径与对照 harness | 通过率公式复现并修复、样本预登记、失败/人工投入不漏记 | 合成报告等于真实效果提升 |
| PR-08 | A6 + C6 集成迁移/UAT/文档/发布 | L1/L2/L3、旧路径隔离、三类真实样本、完整指导和证据索引 | 缺真实工具仍宣称正式收口 |

## 并行与共享文件所有权

A 的组件封装与 B 的方法/契约设计可并行；公共 narrative 定稿后才能做生产兼容。C 的验收量规与输入记录可以从 PR-01 同步准备，不到最后临时定义标准。

共享文件只由本轮集成 owner 收口：`scripts/deck_master.py`、`skills/manifest.json`、`skills/stage-contracts.json`、`product-capability-manifest.json`、`scripts/runtime/final_readiness.py` 和统一 gate policy。并行 Agent 提交变更建议/测试，不各自改一个版本后互相覆盖。

推荐每个独立任务使用隔离 worktree；顺序依赖任务基于已合并 main 开发。合并动作仍由用户/既有仓库流程批准，不自动修改 GitHub 保护或权限。

## 每个 PR 的固定交付

提交 Spec deviation、修改清单、关键设计、兼容/迁移说明、测试命令与实际结果、未覆盖项、对照 acceptance IDs、真实/Fixture 证据区别和回滚方式。测试失败不能省略；跳过项有原因和对完成性的影响。

## 整轮汇报状态

`not_started → in_progress → engineering_complete → outcome_pending / sc1_accepted`。工程完成与效果待验可并存；不得用一个“完成百分比”掩盖关键验收尚未执行。
