# W02：内容整合、大纲与版本化来源

本切片基线 main `09f4486a453d2132a18dbefd10f99ef7317e8fd5`，前置 [PR #43](https://github.com/MainQuestAI/Deck-Master/pull/43) 已合并，精确 head `906f08ceb3157587463119e39f70e10b574d08e6` 的两套 Python 3.11/3.12、真实渲染及 Group report 均通过。

## 当前结果

显式 `workbench.v3` 项目的新 compose 工作单声明 `compose.v1` 及 `content_plan`、`versioned_source_links` 能力。旧 Host 无声明时不能开始或采用这类结果。旧项目与已有旧协议任务仍走原规则。

ContentPlan 保存输入整合摘要、稳定章节/页目标 ID、页用途、材料版本和 locator、未解决事实。正文仍只在 Page 中保存。核心校验最终每页都有唯一目标，每个目标属于一个章节，来源版本与任务输入一致，定位确实存在于那版提取中；无来源的目标必须明确缺少的依据。

这只能证明引用定位存在，不能证明论断成立或 Host 已阅图。原始 SHA256 不可得时仍为 null，不以文件名或假 hash 补造。

采用正文时同时保存计划和 Page refs、更新 Document.content_plan、写入 Task.result_refs 和原子操作回执。input_revision 仍只提交 content_update 的正文差异，同时提交覆盖全稿的新计划；未改页保持原引用。计划版本通过不可变 ref 精确定位，version 数字表示其 previous_ref 链上的顺序，不能代替 ref 作为版本身份。

## 读取、兼容与历史

- `view --content-plan [--revision …]` / `GET /api/content-plan?revision=…` 共用固定快照读取。
- 摘要仅给计划状态、ref、版本及数量；按页 lineage 给对应目标、章节和固定来源版本。
- 无历史计划时返回 `derived` 目录，goal_id/purpose 未知；只读不生成 ContentPlan。
- Page、页序或材料输入变化时保留原计划并标 `basis_changed`；旧材料链接标 version_changed/missing。
- 损坏的计划局部报 unreadable，仍可读其余页面。历史恢复取当版计划引用，保留当前 writer 边界及调用事实。
- 新项目 minimum_writer 为 content-plan.v1。对上一核心 `09f4486…` 的[实测](w02/content-plan/old-core-compatibility.json)中，旧 reader 退出 2、writer 退出 4，指针未变；旧核心没有实现友好升级界面。

完整的新 UI/旧核心启动界面组合待 W03 的能力检测和浏览器验证；W02-AC02 保持部分验证。新 UI 尚未产生，不能用旧 UI 或 schema 测试代签。

## 验证与复现

[可运行脚本](../../../examples/workbench/w02_content_plan.py)从实际 CLI 回包取任务/来源版本，声明能力、采用合成正文与计划、用原 operation 公开 CLI 重放，再读固定版本及单页链路。
首次采用调用共享 Service，避免打开浏览器；没有模型调用，不算真实 Host 内容质量验收。

```sh
PYTHONPATH=src python examples/workbench/w02_content_plan.py --out /tmp/w02-content-plan-example
PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/rebuild/test_content_plan.py
```

[原始检查](w02/content-plan/checks.json)、[完整信封](w02/content-plan/result-envelope.json)、[存储计划](w02/content-plan/stored-plan.json)、[固定版读取](w02/content-plan/outline.json)及相应 CLI 退出码/回包已保存。合成项目目录和本地路径未归档。

首轮相关回归 202 passed / 6 render deselected。补充并发大纲、页序及 writer 检查后的定向回归 125 passed / 7 render deselected；随后补充空白缺口的拒绝，ContentPlan 行为共 18 项；最终 ContentPlan 与包边界定向 22 passed。Ruff 通过。
覆盖错误材料/版本/locator、重复或遗漏目标、缺依据、重复正文字段、无 Host 能力、指针提交后响应丢失、后续编辑重放、输入修订/未改页、材料替换、并发计划变化、旧稿只读、导入计划、恢复、CLI/HTTP 一致及局部损坏。

W02-AC01 已有核心/CLI/HTTP 工程证据；AC02 的旧稿与 reader/writer 部分已验证，新 UI 组合由后续 W03 联测后补记。AC03–07 延续协议切片证据及其字段覆盖边界。默认入口、真实 HOME 安装及发布均未执行。
