# Deck Master 高密度 Builder 下一轮迭代 Spec

日期：2026-08-03
状态：下一轮迭代 Spec 草案
适用范围：Deck Master vNext 高密度 PPT Builder 的产品边界、能力迁移、阶段合同和验收门禁

## 0. 结论

下一轮高密度 Builder 的核心路线确定为：

1. 内容层沿袭 CyberPPT 的内容增强框架，保留证据底表、内容脑暴、SCR、逐页计划、信息密度规划和内容锁。
2. 视觉层使用 ImageGen 生成图片版 PPT 蓝图，蓝图承担构图、层级、密度和视觉方向基准。
3. 重绘层吸收新版 `native-svg-redraw` 的图片到原生 SVG 流程，把视觉还原、自审、主线程复核和可编辑 PPT 前置条件做成硬门禁。
4. 交付层参考 `ppt-master` 的 SVG 到 Native DrawingML PPTX 经验，重新设计并实现可编辑 PPTX 编译链。
5. 后处理层接入 `officecli` 的检查、可视化预览和局部编辑能力，作为 PPTX 质量闭环的一部分。

本 Spec 只定义下一轮迭代的目标形态、迁移边界和验收条件。具体工程包、Schema 定稿、命令设计和实现路径后续进入 GStack 体系展开。

## 1. 当前依据

### 1.1 已确认需求

用户当前认可的最佳链路是：

```text
Deck Master 上下文处理
→ CyberPPT 内容增强与 ImageGen 图片蓝图
→ 图片蓝图到原生 SVG 重绘
→ SVG 到可编辑 PPTX
→ officecli 后链路检查和局部修版
```

关键判断：

- CyberPPT 在内容密度、版式完成度和咨询式页面结构上表现领先，需要沿袭其内容增强能力。
- CyberPPT 的图片蓝图适合作为高密度设计蓝图，最终交付还需要可编辑结构。
- 图片到 SVG 是本轮自建 Builder 的关键中间层，需要重点解决还原度、文字溢出、坐标漂移、图标失真和结构可编辑问题。
- SVG 到 PPTX 的旧链路只能作为参考，新实现需要重新开发，以便消解现有 Skill 之间的实现冲突。

### 1.2 MVP 证据

参考任务已经跑通前三页图片蓝图到原生 SVG 的 MVP：

- P01-P03 已完成原生 SVG 重绘。
- `xmllint` 结构校验通过。
- `validate_native_svg.py` 结构校验通过。
- 禁用节点扫描通过，未发现整页图片、`data:image`、`foreignObject`、`style`、`script` 等不可控结构。
- 视觉预览可用，页面主结构、卡片、连线、文字层级和页面密度具备进入下一阶段的基础。

MVP 的剩余边界：

- 当前证据只覆盖前三页，未覆盖全 deck。
- 当前证据覆盖图片到 SVG，尚未覆盖 SVG 到可编辑 PPTX。
- 当前校验仍偏结构层，下一轮需要加入新版 `native-svg-redraw` 要求的视觉自审、局部对照、主线程复核和状态门禁。

## 2. 迁移原则

### 2.1 迁移对象

本轮从既有 Skill 中迁移的是：

- 产品能力。
- 阶段合同。
- 产物形态。
- 质量门禁。
- 失败处理方式。
- 已验证的工作流经验。

代码实现需要重新设计和重写。既有脚本可以作为行为样例、验收样例和测试夹具来源，不能直接绑定下一轮 Builder 的技术路线。

### 2.2 Deck Master 内部分工

沿用 Deck Master 既有 Skill Suite 职责：

- `deck-sourcing`：决定证据、来源、事实冲突和材料可信度。
- `deck-producer`：把证据与故事线转成页面内容包、逐页计划和内容锁。
- `deck-builder`：把内容包、蓝图、SVG 和 PPTX 产物组装成交付文件。
- `deck-quality`：执行结构、视觉、可编辑性、证据和客户可见口径验收。
- `deck-review`：承接人工审阅、返修意见和版本裁决。

高密度 Builder 应作为 `deck-builder` 的一个受控生产路径暴露，前置依赖 `deck-sourcing` 和 `deck-producer` 的结构化产物。是否另设独立 Skill 名称，留给 GStack 评审裁决。

### 2.3 成功标准

下一轮迭代最小成功标准：

1. 输入为真实 Page Package、内容锁和 ImageGen 蓝图。
2. 至少跑通 3 页端到端链路：蓝图图片 → 原生 SVG → 可编辑 PPTX 候选页。
3. 每页具备蓝图、SVG 预览、并排对比图、局部图标/复杂区对比图、自审 JSON、主线程复核 JSON。
4. PPTX 候选页不能退化为整页图片，标题、主要正文、关键数字、表格核心文字、SO WHAT 区域和来源脚注应为可编辑对象。
5. officecli 或等价检查工具能读回 PPTX 页面结构、文本和基础问题报告。
6. 失败页面必须停在返工状态，不能进入交付确认。

## 3. 能力迁移地图

| 来源 Skill | 迁移内容 | 在新 Builder 中的位置 | 实现要求 |
| --- | --- | --- | --- |
| `cyber-ppt` | 证据底表、内容脑暴、SCR、逐页页面计划、信息密度规划 | `deck-sourcing` / `deck-producer` 前置阶段 | 沿袭流程与产物含义，重新定义 Deck Master 合同 |
| `cyber-ppt` | ImageGen 高密度页面蓝图提示词、风格样张、组件签名、视觉 QA 思路 | Builder 蓝图阶段 | 复用提示词组织经验，重写 prompt builder 和记录机制 |
| `native-svg-redraw` | 原图分析、原生 SVG 重绘、禁用节点、`data-pptx-*` metadata | Builder SVG 重绘阶段 | 按新版视觉还原合同落硬门禁 |
| `native-svg-redraw` | Sub Agent 自审、主线程复核、`validate_visual_review.py` 形态、批次状态权限 | Builder 视觉 QA 阶段 | 迁移为 Deck Master 质量合同，后续决定脚本内置或外部调用 |
| `ppt-master` | SVG 到 Native DrawingML PPTX 的转换经验、可编辑对象约束、PPT 画布映射 | PPTX 编译阶段 | 参考合同和坑点，新实现需要独立开发 |
| `product-design:image-to-code` | 选定图片为视觉真相源、同尺寸对照、局部区域审查、阻塞式设计 QA | 蓝图到 SVG 的视觉验证 | 迁移 QA 方法，避免只做结构校验 |
| `officecli` | PPTX 结构查看、文本读回、截图/HTML 预览、OpenXML 检查、局部修版 | PPTX 后链路 | 作为检查和修版工具，不承担核心生成职责 |

## 4. 目标阶段链路

### 4.1 Stage A：内容增强与证据底座

输入：

- 用户原始材料。
- Deck Master Workspace 上下文。
- 已有品牌、风格、模板、行业知识和项目约束。

输出：

- `evidence_table.json`。
- `storyline_options.json`。
- `scr_storyline.json`。
- `deck_density_plan.json`。

硬要求：

- 每个事实、数字、判断、建议、caveat 和管理层含义都要绑定证据 ID。
- 不能让 ImageGen 生成事实、数字、Logo 或来源。
- 冲突数据必须保留差异、来源和 caveat。
- 低密度页要在内容层补强，不能把密度问题推给视觉层。

### 4.2 Stage B：逐页内容锁

输入：

- `scr_storyline.json`。
- `deck_density_plan.json`。
- Page Package。

输出：

- `slide_content_lock.<page_id>.json`。
- `page_material_pool.<page_id>.json`。
- `blueprint_prompt_brief.<page_id>.json`。

硬要求：

- 标题、副标题、关键正文、数值、图表数据、表格结构、SO WHAT、来源和 caveat 在蓝图生成前锁定。
- 内容锁需要保留可编辑性目标，明确哪些信息必须在最终 PPTX 中可编辑。
- 蓝图 prompt 只能引用内容锁摘要和视觉要求，不能临时补事实。

### 4.3 Stage C：ImageGen 蓝图生成

输入：

- `slide_content_lock.<page_id>.json`。
- `blueprint_prompt_brief.<page_id>.json`。
- 风格锁和品牌约束。

输出：

- `blueprint.<page_id>.png`。
- `blueprint_prompt.<page_id>.txt`。
- `blueprint_manifest.<page_id>.json`。
- `blueprint_component_signature.<page_id>.json`。

硬要求：

- Prompt 必须显式禁止页码、内部标注、wireframe 标签、执行元数据和 prompt 标签。
- Prompt 必须要求高密度咨询式页面、清晰信息区、表格/图表/注释/图例/SO WHAT 的完整呈现。
- 蓝图生成后需要记录图片尺寸、目标画布、风格编号、内容锁 hash、信息区数量和主要组件清单。
- 蓝图文字只能作为视觉定位参考，最终文字以内容锁为准。

### 4.4 Stage D：蓝图解析与元素登记

输入：

- `blueprint.<page_id>.png`。
- `slide_content_lock.<page_id>.json`。
- `blueprint_component_signature.<page_id>.json`。

输出：

- `visual_element_inventory.<page_id>.json`。
- `blueprint_measurement_table.<page_id>.json`。
- `svg_redraw_task_package.<page_id>.json`。

硬要求：

- 每页必须登记标题、正文、数字、表格、图表、卡片、图标、连接线、箭头、图例、注释、来源和 SO WHAT 区域。
- 每个 P0/P1 元素需要记录蓝图 bbox、目标 SVG bbox、PPT 目标 bbox、容差和可编辑性目标。
- 图标密集页、流程页、架构页、矩阵页、时间线页和复杂曲线页必须标注重点复核区域。
- 画布尺寸不能硬编码，应从蓝图 metadata 和目标 PPT 尺寸推导。

### 4.5 Stage E：原生 SVG 重绘

输入：

- `svg_redraw_task_package.<page_id>.json`。
- `slide_content_lock.<page_id>.json`。
- `blueprint.<page_id>.png`。

输出：

- `page.<page_id>.svg`。
- `page.<page_id>.preview.png`。
- `page.<page_id>.comparison.png`。
- `page.<page_id>.review.subagent.json`。
- `page.<page_id>.review.main.json`。

硬要求：

- SVG 根节点需要清晰 viewBox、目标画布和 `data-pptx-page-role`。
- 主要对象需要稳定 id、语义分组和 `data-pptx-bounds`。
- 文字使用 `<text>/<tspan>`，主要卡片使用 `<rect>`，连接关系使用 `<line>/<path>/<polygon>`。
- 禁止整页 `<image>`、大面积蓝图截图、`data:image`、`foreignObject`、外部 CSS、`style`、`script`、`iframe` 和不可控外部依赖。
- 图标需要逐个核对语义、外轮廓、内部结构、负空间、方向、线宽、颜色、尺寸和对齐基线。
- 文字、卡片、箭头、连接、图例、页脚和来源不能遗漏。
- 出现文字溢出、容器溢出、视觉重心漂移、区域层级错误、连接关系错误或 unresolved issue 时，页面必须返工。

### 4.6 Stage F：视觉自审与主线程复核

输入：

- SVG。
- SVG 预览。
- 原始蓝图。
- 并排对比图。
- 关键区域局部裁图。

输出：

- `page.<page_id>.review.subagent.json`。
- `page.<page_id>.review.main.json`。
- `svg_redraw_batch_manifest.tsv`。

Sub Agent 自审要求：

- 必须生成并检查原图/预览并排图。
- 必须覆盖整页版式、高密度区域、图标局部、文字裁切、连线和箭头。
- 自审 JSON 至少包含 `self_review_count`、`revision_count`、`issues_found`、`unresolved_issues`、`icon_checks`、`layout_checks` 和 `visual_status`。
- 自审 JSON 必须包含可追溯路径：`source`、`svg`、`preview`、`comparison`，存在图标时还要包含图标局部原图裁图和预览裁图。
- 自审 JSON 必须通过 `validate_visual_review.py --required-role subagent` 形态的校验。
- `unresolved_issues` 必须为空，`visual_status` 才能进入 `self_pass`。
- 有发现问题时，必须先返修，再重新自审。

主线程复核要求：

- 主线程重新渲染 SVG。
- 主线程独立检查并排对比图和局部裁图。
- 主线程复核 JSON 需要引用上游自审 JSON。
- 主线程复核 JSON 必须通过 `validate_visual_review.py --required-role main` 形态的校验。
- 只有主线程可以写入 `review_pass`。
- 当前批次全部 `review_pass` 后，才允许进入下一批。

状态权限：

| 执行角色 | 可写状态 |
| --- | --- |
| Sub Agent | `generated`、`auto_pass`、`needs_revision`、`self_pass` |
| 主线程 | `needs_revision`、`review_pass`、`blocked` |

### 4.7 Stage G：SVG 到可编辑 PPTX 候选页

输入：

- `page.<page_id>.svg`。
- `slide_content_lock.<page_id>.json`。
- `visual_element_inventory.<page_id>.json`。
- `page.<page_id>.review.main.json`。

输出：

- `page.<page_id>.pptx` 或 deck 级 PPTX 候选文件。
- `svg_to_pptx_candidate_manifest.<page_id>.json`。
- `pptx_editability_report.<page_id>.json`。

硬要求：

- 只有 `review_pass` SVG 可以进入 PPTX 编译。
- 标题、主要正文、关键数字、表格核心文字、SO WHAT、来源和页脚需要转成 PPT 可编辑文本。
- 卡片、线条、箭头、基础图形、表格框线和主要视觉节点需要优先转成可编辑形状。
- 复杂视觉可以转为原生路径或受控图片资产，但必须在 manifest 中标注可编辑性牺牲。
- PPTX 渲染图需要与 SVG 预览、原始蓝图做对照。

### 4.8 Stage H：PPTX 后链路检查与修版

输入：

- PPTX 候选页或 deck。
- `svg_to_pptx_candidate_manifest`。
- `pptx_editability_report`。

输出：

- `officecli_inspection_report.json`。
- `pptx_visual_comparison.png`。
- `builder_quality_gate.json`。
- 修版记录。

硬要求：

- 必须能读回 PPTX 文本、页面对象和基础结构。
- 必须检查整页图片退化、文字缺失、对象越界、表格错位、来源缺失和不可编辑关键内容。
- 发现问题后进入返工，返工来源需要回到 SVG 或内容锁，避免只在 PPTX 里做不可追溯修补。

## 5. 新增或扩展 Artifact 清单

以下 Artifact 为下一轮工程设计输入，字段尚未定稿：

| Artifact | 归属阶段 | 用途 |
| --- | --- | --- |
| `evidence_table.json` | Stage A | 事实、数字、判断和 caveat 的证据底座 |
| `storyline_options.json` | Stage A | 多条故事线、取舍和适用场景 |
| `scr_storyline.json` | Stage A | 最终 SCR 与管理层判断链 |
| `deck_density_plan.json` | Stage A | 全 deck 信息密度、页面角色和补强点 |
| `slide_content_lock.<page_id>.json` | Stage B | 每页最终可用内容真相源 |
| `page_material_pool.<page_id>.json` | Stage B | 图表、表格、数字、注释和 SO WHAT 物料池 |
| `blueprint_prompt_brief.<page_id>.json` | Stage B | 传给 ImageGen prompt builder 的结构化输入 |
| `blueprint_manifest.<page_id>.json` | Stage C | 蓝图生成记录、尺寸、风格、hash 和组件摘要 |
| `blueprint_component_signature.<page_id>.json` | Stage C | 蓝图页面结构和组件密度签名 |
| `visual_element_inventory.<page_id>.json` | Stage D | 全元素登记、优先级、bbox 和可编辑目标 |
| `blueprint_measurement_table.<page_id>.json` | Stage D | 坐标换算、容差和反测基准 |
| `svg_redraw_task_package.<page_id>.json` | Stage D | 发给重绘阶段的完整任务包 |
| `page.<page_id>.review.subagent.json` | Stage F | 重绘自审记录 |
| `page.<page_id>.review.main.json` | Stage F | 主线程视觉复核记录 |
| `svg_redraw_batch_manifest.tsv` | Stage F | 批次状态和推进权限 |
| `svg_to_pptx_candidate_manifest.<page_id>.json` | Stage G | SVG 到 PPTX 转换记录 |
| `pptx_editability_report.<page_id>.json` | Stage G | PPTX 可编辑性读回报告 |
| `builder_quality_gate.json` | Stage H | 最终质量门结论 |

## 6. 与现有 Deck Master 合同的关系

### 6.1 Page Package

现有 `page-package.v1` 仍是页面级输入真相源。下一轮需要新增或扩展以下字段方向：

- `content_lock_ref`：指向逐页内容锁。
- `blueprint_ref`：指向 ImageGen 蓝图记录。
- `visual_element_inventory_ref`：指向视觉元素登记。
- `editability_targets`：声明每类内容的可编辑性目标。
- `quality_gate_refs`：声明 SVG 自审、主线程复核和 PPTX 检查结果。

具体字段需要后续 Schema 设计确认。

### 6.2 Build Manifest

现有 `build-manifest.v2` 已有 `builder_backend`、`output_profile`、`pages`、`editability_target` 等概念。下一轮应扩展：

- `builder_backend=high_density_blueprint_svg_pptx` 候选命名。
- page build 中记录 `blueprint_manifest_path`。
- page build 中记录 `svg_review_main_path`。
- page build 中记录 `pptx_editability_report_path`。
- deck 级记录质量门状态和阻塞页。

### 6.3 Generation Result

现有 `generation-result.v2` 已支持 `page_svg`、`page_png`、`page_pptx`、`deck_pptx` 和 `quality_report`。下一轮可复用 artifact kind，增加 metadata 约束：

- SVG artifact 必须带主线程 `review_pass` 证据。
- PPTX artifact 必须带可编辑性读回证据。
- 质量报告需要区分内容、视觉、可编辑性、证据和客户可见口径。

## 7. 视觉还原与可编辑性门禁

### 7.1 SVG 结构门禁

页面进入视觉复核前必须通过：

- XML 结构校验。
- 禁用节点扫描。
- `viewBox` 与目标画布检查。
- `data-pptx-page-role` 检查。
- P0/P1 对象 id 与 `data-pptx-bounds` 检查。
- 文本节点存在性检查。

### 7.2 视觉还原门禁

页面进入 `review_pass` 前必须通过：

- 整页并排对比。
- P0 区域局部对比。
- 图标局部对比。
- 文字裁切检查。
- 容器边界检查。
- 连接线端点和方向检查。
- 表格密度和语义字号检查。
- 视觉重心、区域分割、层级、卡片尺寸、间距和对齐检查。

任何 `unresolved_issues` 都阻塞通过。

### 7.3 PPTX 可编辑性门禁

PPTX 候选页进入 deck 级组装前必须通过：

- 标题和主要文本可读回。
- 关键数字和来源可读回。
- 主要卡片、线条、箭头和基础图形可编辑。
- 整页图片面积低于阈值，且不能承载主要文字或事实。
- 复杂图片资产有明确登记、面积、原因和替代方案说明。
- PPTX 渲染图相对 SVG 预览没有明显压缩、遮挡、错位和溢出。

## 8. 冲突记录与待裁决问题

### 8.1 PPTX 编译路线

冲突：

- CyberPPT 参考链路偏 PptxGenJS。
- PPT Master 参考链路偏 SVG 到 Native DrawingML。
- 新 Builder 目标要求高还原与可编辑同时成立。

待裁决：

- 采用单一自研编译器，还是先支持一个最小后端。
- SVG 是否作为唯一中间表示。
- 文本、表格、图表、复杂路径和图片资产的转换优先级。

建议：

- 下一轮先做单一后端，目标是 3 页端到端跑通。
- 保留后端抽象字段，但暂不引入多后端复杂度。

### 8.2 图片资产准入

冲突：

- CyberPPT 可接受小范围复杂视觉图片。
- Native SVG Redraw 强调主要页面内容原生重绘。

待裁决：

- 允许图片资产的最大面积。
- 允许图片资产的类型。
- 图片资产是否可进入最终 PPTX。
- 可编辑性牺牲如何在报告里披露。

建议：

- P0 信息不能以图片承载。
- 复杂纹理、照片、地图底纹、细节装饰可以进入候选白名单。
- 每个图片资产必须有面积、位置、原因和替代方案登记。

### 8.3 蓝图文字与真实内容

冲突：

- ImageGen 蓝图文字存在漂移、变形和事实不可靠。
- 视觉还原需要尊重蓝图布局。

待裁决：

- OCR 在流程中只做定位参考，还是参与内容校对。
- 内容锁替换蓝图文字时，如何处理行宽变化。
- 标题和表格密集页是否需要人工确认换行。

建议：

- 最终文字一律来自内容锁。
- OCR 只用于定位、区域识别和疑点提醒。
- 文字溢出优先回到 SVG 布局调整，必要时回到内容锁裁决。

### 8.4 高还原与可编辑范围

冲突：

- 视觉越复杂，越容易产生大量 path。
- 可编辑范围越大，PPTX 结构越复杂。

待裁决：

- 哪些对象必须原生可编辑。
- 哪些对象允许成为不可编辑但可缩放的路径。
- 哪些对象允许成为受控图片。

建议：

- 文字、数字、来源、SO WHAT、主卡片和主要连接关系列为必须可编辑。
- 装饰纹理、复杂背景、照片和非事实承载图像可降级。
- 降级必须记录，质量报告中单独列出。

### 8.5 批量并行与逐页门禁

冲突：

- 大 deck 需要批量效率。
- 高还原页面需要逐页审查。

待裁决：

- 每批页数。
- first-page gate 的通过标准。
- Sub Agent 自审和主线程复核的并行边界。

建议：

- 下一轮 MVP 先以 3 页为单位。
- 每批全部 `review_pass` 后再进入下一批。
- 主线程只做复核和状态裁决，重绘可并行。

### 8.6 风格丰富度

冲突：

- CyberPPT 的固定风格稳定。
- 用户反馈 CyberPPT 视觉颜色和整体表达偏单调。

待裁决：

- 是否保留 8 种风格作为默认稳定集。
- 是否新增 Deck Master 自有风格锁。
- 如何保证风格扩展不削弱内容密度。

建议：

- 先保留 8 种风格作为 baseline。
- 新增风格锁时必须同时定义色板、网格、图表语言、表格语言、图标系统和来源体系。
- 每个风格都要通过同一套密度与可编辑性门禁。

### 8.7 Skill 边界

冲突：

- 用户需要完整高密度 Builder 能力。
- Deck Master 已有 `deck-sourcing`、`deck-producer`、`deck-builder`、`deck-quality` 等分工。

待裁决：

- 新能力作为 `deck-builder --profile high-density`，还是新增独立入口。
- 内容增强框架落在 `deck-producer`，还是由 Builder 内部拉起。
- 重绘阶段是否成为独立可复用 skill。

建议：

- 产品口径优先放在 `deck-builder` 高密度模式。
- 内容增强仍归 `deck-producer`，避免 Builder 同时承担事实处理。
- 图片到 SVG 重绘能力保留独立模块边界，便于复用和替换。

## 9. GStack 推进建议

### 9.1 office-hours

目标：

- 收敛产品边界。
- 确认新能力入口。
- 确认首版 MVP 页数、质量标准和可编辑范围。

建议讨论问题：

- 高密度模式是否进入 `deck-builder`。
- SVG 是否作为唯一中间表示。
- 图片资产准入阈值。
- 视觉还原和可编辑性冲突时的优先级。

### 9.2 plan-ceo-review

目标：

- 从产品竞争力角度评审路线。
- 判断这条链路是否足以形成 Deck Master 下一版差异化。
- 确认 MVP 对外可演示边界。

建议评审点：

- 高密度内容能力是否明显强于普通大纲生成。
- 图片蓝图是否能稳定提高版式质量。
- 原生 SVG 和可编辑 PPTX 是否能解决二次编辑问题。
- 质量门禁是否足以避免交付翻车。

### 9.3 plan-eng-review

目标：

- 把本 Spec 拆成工程开发包。
- 定义 Schema、命令、目录结构、测试夹具和最小实现路径。

建议拆包：

- P1：内容锁和蓝图 manifest。
- P2：蓝图解析与元素登记。
- P3：原生 SVG 重绘任务包与审查合同。
- P4：SVG 到 PPTX 最小编译器。
- P5：PPTX 可编辑性和视觉 QA。
- P6：端到端 3 页 demo 和回归夹具。

### 9.4 qa-only

目标：

- 对 MVP 输出做独立验收。
- 建立后续 benchmark 标准。

建议验收：

- 结构校验。
- 视觉还原。
- 图标还原。
- 文字溢出。
- PPTX 可编辑性。
- 证据链回溯。
- 客户可见口径。

## 10. 下一轮暂不覆盖

下一轮先不展开：

- 全 70+ 页 deck 自动化生产。
- 多 PPTX 编译后端并行。
- 完整风格系统重建。
- 复杂图表数据引擎。
- 客户可见模板市场。
- 生产发布和开源打包。

这些能力应在 3 页端到端 MVP 通过后再进入独立 Spec。

## 11. 本 Spec 的完成条件

本 Spec 完成后，后续 GStack 可以直接围绕以下问题开工：

1. 高密度 Builder 在 Deck Master Skill Suite 中的入口和职责。
2. 从 CyberPPT 迁移的内容增强合同。
3. 从新版 `native-svg-redraw` 迁移的视觉还原合同。
4. SVG 到 PPTX 自研编译器的最小可行范围。
5. 3 页端到端 MVP 的验收标准。

后续工程实现必须以可验证 artifact 为中心推进，每个阶段都有输入、输出、门禁、失败状态和返工路径。
