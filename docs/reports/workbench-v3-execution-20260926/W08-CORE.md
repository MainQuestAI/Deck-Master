# W08 固定风格配方与试作核心

基线 `c17ba512db3efb4196b0e88dcab2d604eb23b053`。实现提交 `1bccae4e68156f3e71556253f33f69a5536de8e8`，[PR #58](https://github.com/MainQuestAI/Deck-Master/pull/58) 已合入 main：`38d0b446592e8558b9126cfa85a484d2bddf557b`，最终 head `5a164c71e475d1172291f0cf157c649d371d5b3c` 的 8 项 CI 通过。本切片新增共享契约、服务、CLI/HTTP 与 Host 指引；核心交付时尚未接入前端；后续浏览器和真实风格评价见 [W08-UI](W08-UI.md)，用户验收未代签。

## 实现

`styles propose` 固定参考原图版本、目标 Page/原图锚点、短要求及选定维度；默认仅 palette/typography。原始 prompt 按已有 lineage 的 prepared/提交观察来源展示，缺失不补造；选段复用 W05 精确 code-point 校验。Host 建议仅为未确认文本。明确极简/高密度词对产生逐页冲突，须显式 keep_target/use_reference 后重新提案。该词对检测是有限检查，不承诺理解全部语义冲突。

`styles confirm` 通过 operations/CAS 保存不可变版本，不创建任务或消耗额度。parent_recipe_id 生成新版本及 diff；原配方保持。恢复沿原操作已提交事实查重。`styles list/show` 支持固定 revision。

`styles plan` 复用 change_plan，首次只允许一页原图 trial；扩展须给出本配方已明确采用、仍为当前且生成依据有效的候选，以及明确其它目标页。计划及提交都重新校验所有目标锚点，逐页报告冲突；未选页/参考页不改。Host 任务、冻结请求存同一 style_recipe_ref，保留目标内容约束，原有额度、取消、晚到和候选采用规则继续生效。不读取最新配方替代已派发版本。

复用变化：changes 构造带额外要求的预备请求后重新计算 prompt_sha256，避免 lineage 把自己的预备稿判作损坏；没有重写任何历史请求。活动合同一份、规格镜像一份。新 writer 边界 style-recipes.v1 由各后续写入保持。

## 已取得的验证

- W08 13 项测试，加既有 changes/candidates/generation_protocol，共 **52 passed**。包括固定配方与精确选段、确认不派发、回执索引丢失后重放、版本 diff、Host 能力拒绝、HTTP Origin/token、逐页冲突、冻结输入篡改拒绝、合成生成与采用扩展。
- [11 项可复现流程](w08/core/checks.json)：显式合成工具事件，共 2 次合成调用记录、真实模型调用 0。目标 Page 引用始终不变，参考页和第一张已采用页不受扩展影响；原图采用后仅目标 SVG/预览和依赖整稿失效。[输入](w08/core/input.json)、[建议](w08/core/proposal.json)、[确认](w08/core/confirm.json)、[单页计划](w08/core/p02-plan.json)、[扩展计划](w08/core/p03-plan.json)。
- [旧核心实际拒写](w08/core/old-core-checks.json)：固定前版源代码运行 continue，退出 4、pointer 字节不变。隔离目录运行，未安装实际 HOME。
- Ruff 通过；完整 rebuild **863 passed，137.48 秒**。

前端接入与一次真实参考→试作采用→余页扩展仍待实施。合成图片不用于判断事实保持、风格改善或未选维度退化；这些必须分别阅图留证。

## 复现与恢复

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w08_style_transfer.py --out /tmp/new-style-mechanism
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/rebuild/test_styles.py
```

新输出目录必须不存在。`style_invalid` 为 CLI 2 / HTTP 422，`style_conflict` 为 CLI 5 / HTTP 409；不可读固定版本沿共享 operation_unavailable 为 CLI 4 / HTTP 503。说明见 [恢复入口](../../agent-recovery-playbook.md#style-calibration)，Host 方法见 [风格协议](../../../skills/deck-master/references/style-calibration.md)。
