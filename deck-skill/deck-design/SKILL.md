---
name: deck-design
description: 用 Rust deck 做已有正文的页面设计、样页和指定页视觉返修。先决定主视觉，再按正式 task.md 生图、重建 SVG 并构建可编辑 PPT。
---

# Deck Design

在已有正文上决定这一页怎样被看懂，并在授权范围内做出蓝图、SVG 和可编辑 PPT。不重写内容方法，也不把样页扩成全稿。

命令是 Rust CLI `deck`。不要调用 Python `deck-master`。生图、重建和构建的命令见 [commands.md](references/commands.md)。

## 接受什么

已有正文的页面设计、样页、指定页的视觉返修，或 Master 交来的制作范围。输入是当前作品里的正文、layout、目的和样式。

只要样页时，做到约定的页就停。指定页返修不改未点名页面的语义、素材和主视觉。

## 不做什么

内容里的段落、要点或表格不决定画面。不按“封面”“流程”“阶段”“计划”“分工”这类标题自动禁表或换版式。不在调用 ImageGen 时另写一份更短的提示词。不给模型追加“禁止照片、只要扁平色块”这类任务里没有的风格前缀。

必须改正文、删掉必要条件或改判断时，退回内容，不在设计步骤里静默改掉。没有实际阅图，不称这一页视觉通过。

## 默认阅读

先读 [content-to-visual](references/content-to-visual.md)，再看当前作品的 style、[视觉系统](references/design-system.md) 和 [svg-subset](references/svg-subset.md)。需要图标、界面或场景时按 [视觉资产](references/visual-assets.md) 选用并登记页范围、来源与许可。

语义对照见 [semantic-layout-examples](assets/design/semantic-layout-examples.md)。不必先读完整的内容长文。方法卡只在要核对某个关系从哪来时再打开。

生图前先用 `deck get` 读取并锁定作品 style，至少确定 palette 和 fonts，画布沿用默认；有品牌规范时用 `deck put` 写入同一字段，无品牌用默认值。构建前若本机没有该默认字体，用 `deck doctor` 换成已安装字体。风格口号只进共享设计参考，不进 purpose / layout；不设八张样张确认硬门。不给模型追加任务里没有、模型里也不存在的风格前缀。

## 主视觉与制作

先用一句写明这一页的画面必须让读者看出的对象、方向和分支。比较和查阅可以继续以表为主视觉。已写明的阅读任务或构图句要求状态、路径、闭环和旅程时，让关系成为主视觉，正文按关系组织，表最多当取材；生图前修订顺序见共享的 [page-writing](references/page-writing.md)。

再按实际需要进入 [commands.md](references/commands.md) 的相应制作步骤；蓝图仍可用的局部返修直接进入 SVG 修正，需要新蓝图时才从生图开始：

1. **需要新蓝图时：** `deck run start image` 之后，读取该次 task.md 的原文作为 ImageGen 的 prompt，附件只使用 attachments.json 里的文件。
2. **需要新蓝图时：** 交回、比对、需要时 `deck run adopt`。取消后或依据已变的结果只保存。
3. 重建 SVG 前读共享的 [还原策略](references/reconstruction.md)，元素与绑定按 [SVG 子集](references/svg-subset.md)。SVG 按原图的布局和关系重建，正文取 content，文字绑定 atoms。错漏文字、局部排版和依据明确的连线可以沿用原图直接改 SVG。业务关系有歧义时问内容，主结构要重排时先改蓝图再重建。
4. 在范围内 `deck build`，再用 `deck export pptx`。缺页、依据已变和构建之后又改过，按命令输出里的字段照实说明。

`soffice` 不可用时停在 SVG 交回失败，不手写 PPTX，也不绕过 `deck build`。

## 交接

交回主视觉那一句、本次范围内的蓝图或 SVG 或 PPT，以及和正文的比对。内容关系错了退回内容。审查指出的视觉问题只改受影响的页。
