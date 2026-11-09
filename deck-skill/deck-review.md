---
name: deck-review
description: 用 Rust deck 审查当前作品、外部可读稿或 PPTX。默认只读，按页或区域返回问题、影响和建议；不改正文、不生图、不采用候选。
---

# Deck Review

对照正文、正式提示词、原图和成品，指出具体问题。默认不修改作品。

命令是 Rust CLI `deck`。不要调用 Python `deck-master`。读取和意见命令见 [commands.md](references/commands.md)。

## 接受什么

当前作品、外部可读稿或 PPTX，或作者圈定的页。审查可以只覆盖内容、只覆盖画面，或对照已经做出来的成品。范围以这次的请求为准，不自动扩成重写方案。

## 不做什么

不改正文，不调用生图，不执行 `deck run adopt`，不把候选收成正式页。不因为方法文件读过、对象数对了或箭头数量对了，就称语义或视觉通过。没有实际看图，视觉项记未执行。

自查、其他执行和真人是三种记录，不能互相代替。换到本入口自己看稿，仍然是 `self_check`。

## 默认阅读

先读 [method-review](references/method-review.md)。按问题再读相关方法卡，以及实际的正文、task.md、原图或 PPT。

校准例见 [calibration-cases.json](assets/review/calibration-cases.json)，按问题选用，不当成关键词裁判。表达是否只剩标签，见 [content-calibration](references/content-calibration.md)。不必先读完整的内容长文。

有 PPT 和回读时，先读现有 findings 的页和对象定位，再做专业阅图。沿用的机械问题代码与预期关系不足时的边界见 [method-review](references/method-review.md#机械发现与阅图定位)。

## 三层 QA

分别报告 Q1 业务语义、Q2 视觉保真／可读性／专业完成度、Q3 可编辑性与 Office 兼容。独立判断、回读边界及原图／成品证据分开记录的执行口径见 [三层 QA](references/method-review.md#三层-qa) 与 [成品证据](references/method-review.md#内容主视觉与成品)。

## 怎样返回

每一条都写明页及对象／区域（错归因附原句）、实际问题、影响、修改建议、分级（Critical／Major／Minor）和参考依据，以及这次没有验证的维度。分级按 [method-review](references/method-review.md#缺陷分级) 判断，依据指出对应正文、提示词或实际产物的具体位置。内容关系错，建议交内容；主视觉选错或正式提示词漏了关系，建议交设计；正式 task.md 与附件清单正确、实际调用却改写或漏传，建议交调用，按 task.md 原文与 attachments.json 修正提交；蓝图里关系还在、重建或编译丢了，建议交重建。只建议复审受影响的范围。

作者明确要求把意见保存进作品时，使用 `deck review add`，并写上 method：

- 当前 Host 自查：`--method self_check`
- 另一个执行或模型看稿：`--method other_model`
- 真人：`--method human`

不要省略 `--method`。这条命令的默认值是 `human`，不能用来记录自查。意见落实后才 `deck review resolve`；不能采纳的说明原因，不为了清零去改稿。

案例或作者给出的算式文件，可以用 `python -m deck_tools.case_numbers` 复算。退出码只说明算式，不说明归因、来源或 ROI，也不是审查通过的条件。

## 交接

把报告交回作者。要改内容时交 Deck Content，要改画面或提示词时交 Deck Design，要跨着做完时交 Deck Master。审查本身停在报告，或停在作者要求保存的意见。
