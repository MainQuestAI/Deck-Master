---
name: deck-master
description: 用 Rust deck 协调完整制作、续作和跨职责返修。接受作者任务、材料或已有作品，交接内容、设计与审查，并持续完成已授权范围。
---

# Deck Master

运行时仍是同一个作品、同一套 `deck` 命令。这里负责的是任务理解、路由、交接和完成判断，不把内容、设计和审查的方法正文再写一遍。

命令是 Rust CLI `deck`。不要因为本入口的名字调用 Python `deck-master`。用法见 [commands.md](references/commands.md)。

## 接受什么

完整制作、续作，以及需要跨职责才能改完的返修。输入是作者这次的任务、指定的材料，和已经存在的作品。

作者已经点明只策划、只写正文、只写讲稿、只做页面设计或只审阅时，把工作交到对应入口，到该结果就返回。不要因为句子里出现“设计”或“审核”就改投另一项，也不要把业务主题里的审核流程当成审查请求。

## 不做什么

不代写 M01–M10，不代选主视觉，不把自查写成独立评审。四项职责不是四个必须同时启动的作者，也不另做审批或运行时身份认证。

路由对照见 [routing-examples.json](assets/master/routing-examples.json)。那是历史路由示例按当前四项职责改写的结果，用来判断交给谁，不是新线要执行的命令。

## 默认阅读

1. 本文件。
2. [commands.md](references/commands.md)。
3. 按这次真正要做的事，转读内容的 [source-reading](references/source-reading.md)、[method-selection](references/method-selection.md)、[page-writing](references/page-writing.md)，设计的 [content-to-visual](references/content-to-visual.md)，或审查的 [method-review](references/method-review.md)。

不要为了凑齐流程把四份长文一次读完。

## 交接

先读出作者要表达的判断、希望争取的结果、已经有的决定，以及这次的修改范围。只在不同答案会把方向做成相反、且无法按条件继续时集中补问。

- 内容交回主张、页序，以及每页阅读任务 `purpose`、判断句或明确查阅职责 `content.title`、构图句 `layout` 和按结构组织的正文。构图句须有本页关系、对象与方向或分支、分区职责、表的作用及拍扁会丢的关键事实；方法见 [page-writing](references/page-writing.md)。缺任一项先补写，不调用 `run start image`；内容完成不自动生图。
- 生图前按 [视觉系统](references/design-system.md) 读取并锁定作品 style，至少确定 palette 和 fonts，画布沿用默认；有品牌规范时用 `deck put` 写入同一字段，无品牌用默认值。构建前若本机没有该默认字体，用 `deck doctor` 换成已安装字体。风格口号进共享设计参考，不进 purpose / layout；不设八张样张确认硬门，不给模型追加任务里没有、模型里也不存在的风格前缀。
- 设计将 D03 生成的 task.md 原文交给 ImageGen，按 attachments.json 传附件，不另写短提示词，不追加“扁平色块方便还原”等要求；代码当前不会拦截 Host 改写提示词，原样提交靠真实会话观察。设计交回主视觉决定，以及本次范围内的蓝图、SVG 或可编辑 PPT，还有和正文的比对。只要样页就不扩成全稿。正文必须改时退回内容。
- 审查默认只交回按页或区域写明的问题、影响、修改建议和未验证维度。作者明确要求留下意见时，用 `deck review add`，并且显式传入 method：当前 Host 自查是 `self_check`，换成本入口自己看稿也仍是 `self_check`；另一执行或模型阅稿是 `other_model`；真人是 `human`。命令的默认 method 是 `human`，自查不能省略这个参数。
- 审查不改正文、不生图、不采用候选。修复交回内容或设计，之后只复审受影响的范围。没有实际阅图，不称视觉通过。

## 完成

用 `export md` 实际阅读标题、“本页目的”、“布局”和正文组织，核对关键事实与状态分支；查阅任务按构图句留表算成功。这是可读稿检查，不代替 PPTX 画面还原或 T07 视觉人判。说明完成了哪一范围、做了哪些取舍、还有什么没做。已经授权的整项任务，在内容、设计和必要审查之间继续，不把一次子职责的结束当成整项停止。

局部范围和只改讲稿沿用 [page-writing](references/page-writing.md)：只提交 notes 时不启动 image 或 SVG。出错时按 CLI 的错误信息处理，不用占位产物代替失败。
