# 代码基线：生成工作台 v3

核查日期：2026-09-26。本线程重新核验远端 main、主要接口与上轮基线差异；新增只读/故障探测见 ../../reports/workbench-v3-execution-20260926/REVIEW.md。源码基线：`d1c7c4600cb0fc781070116ed8cc8a1ff6b8b7ca`（`d1c7c46`）。本文件是只读代码核查；没有跑生产项目，也不证明运行或真实 Host 验收通过。后续编码前必须核对当时 main，不把本快照当永久现状。

主结论：现有核心有不可变对象、任务、版本和主要成品链路；旧 Web 投影没有完整呈现这些关系。内容整合/大纲、可编辑生成请求、试作候选/采用及显式阶段重跑需要扩展核心，不能仅靠前端页签补齐。

## 1. 每层实际能力

| 层 | 已实现事实 | 可复用到 v3 | 仍需新增 |
|---|---|---|---|
| 任务与材料 | Document.task、sources[]；稳定 source_id、original_sha256、extract；提取对象包含 original_file 不可变引用 | create、inputs show/update；输入摘要及 content_basis 对齐判断 | Web 完整投影；材料片段到内容/页面导航；已选入/已提取/已用于成稿分开 |
| 内容整合/大纲 | 活动 Document 没有独立整合/大纲字段；初始 compose 直接接收 pages + page_order | Page 标题与顺序只能导出“当前目录” | ContentPlan 版本、章节/页目标/来源关系、compose 协议及旧项目缺字段兼容 |
| 逐页稿 | Page v2 含稳定 page_id、正文块/列表/表格ID、visual_spec、citations | 文字原子、直接改稿、局部 content_update；未改页产物保留 | 大纲与页关系、合并/拆分来源、UI 结构编辑和下游影响预览 |
| 预备提示词 | production.project_prompt 拼出 prompt/projection 和 SHA；blueprint task 把 Page 与请求对象存入 inputs | 读取派发时请求和有效风格，不需重新拼冒充历史 | GenerationRequest 生命周期、编辑草稿、差异、模板/参考图/attempt 的固定关联 |
| 实际提示词/原图 | Artifact 可回传 submitted_prompt、generated_from_page、invocation_ref；图片与文本进不可变对象库 | 有记录时准确显示当次提交文本与原图 | submitted_prompt 非必填，旧图不能保证存在；新协议需调用前冻结实际请求、结果后绑定 |
| SVG/预览 | SVG 采用前检查 data-blueprint-sha256；SVG 预览派生自当前 SVG | 原图对照、编译、逐页预览/复核 | 完整 lineage 投影；显式只修SVG的变更计划及历史适用性 |
| PPT/预览/交付 | 按有序 SVG 集合编译 native PPT，渲染、回读、object trace、review/delivery 导出 | 原生可编辑输出、质量门禁、history/restore | 指定版导出、engineering；PPT预览直接父对象关联加强；浏览器下载白名单 |

## 2. 影响产品定义的事实与缺口

### 2.1 对象存储和版本底座可以复用

`Store.put_blob` 按 SHA256 写 `.deckmaster/objects/{prefix}/{digest}.{ext}`，相同内容复用、不同内容不能覆盖；`revisions/{revision_id}.json` 不可变，`current.json` 指向当前版本。Document 有 project_id、revision_id、parent_revision_id。页面身份不是页码，重排后不应改 page_id。

依据：[store.py](../../../src/deck_master/store.py) 基准行 61、98、193、208；[document.v1.schema.json](../../../src/deck_master/resources/contracts/document.v1.schema.json) 行 10、14、18、180。

### 2.2 大纲是新增工作对象，不能伪装成已有数据

Document 活动模型根属性在行 807–823 列出且 additionalProperties=false；没有 outline/content_plan。初始 compose 采用 `pages/page_order` 写当前稿。可以把现有标题投影为目录，但必须标“由当前稿推导”；不能声称该目录是生成前确认的大纲或有当时的材料整合记录。

依据：[document.v1.schema.json](../../../src/deck_master/resources/contracts/document.v1.schema.json) 行 807；[tasks.py](../../../src/deck_master/tasks.py) 行 1079；[Page契约](../../../src/deck_master/resources/contracts/page.v2.schema.json) 行 380。

### 2.3 预备提示词与实际提示词已有区别，界面必须保持

`project_prompt` 从 customer_visible、visual_spec、有效 style/fonts/permitted_assets 拼请求，主动排除 speaker_notes/internal_only。请求带 prompt_sha256/projection_sha256。`open_blueprint_task` 存请求对象，绑定 task 输入与 dispatch_revision。Host 指令要求保存实际提交 prompt；但 schema 中 provenance 只要求 source_type，submitted_prompt/generated_from_page 可省略。`_build_artifact` 只有收到 submitted_prompt_file_id 才把实际文本写入对象库。

因此“有预备请求”不等于“有真实执行 prompt”。新模型保留 prepared/submitted 两个事实；缺记录显示未记录。新历史关系应来自固定引用，不能从最新 Page 重算再贴到旧图上。

依据：[production.py](../../../src/deck_master/production.py) 行 81、96、137；[service.py](../../../src/deck_master/service.py) 行 512、525、537；[tasks.py](../../../src/deck_master/tasks.py) 行 391；[artifact契约](../../../src/deck_master/resources/contracts/artifact.v1.schema.json) 行 119、144、169、195。

### 2.4 风格参考与候选采用尚未形成产品能力

已有 `design_context.styles/default_style_id` 与每页 `visual_spec.style_ref`，可复用风格解析和指定页依赖判断。没有“参考页版本+选定提示词片段+目标页内容保持”的 StyleRecipe，也没有生成候选池或独立人工采用决定。当前 task accept 在验证成功后即写当前 slots；历史对象继续存在，不等于用户可选择的候选集合。

依据：[production.py](../../../src/deck_master/production.py) 行 22、32；[page契约](../../../src/deck_master/resources/contracts/page.v2.schema.json) 行 341；[tasks.py](../../../src/deck_master/tasks.py) 行 1071、1102、1113。

### 2.5 改稿不会自动重做原图

`edit_page` 改 Page 后保留 blueprint，清该页 SVG/两个预览及整稿 outputs，并使有关未完任务 superseded。`update_design` 只使实际设计依赖变化的页失效，也保留 blueprint。continue 只在没有 blueprint 时开生图任务，否则缺 SVG 时走 reconstruct。因此新 UI 的“修改提示词后重新试作原图”必须有显式核心服务，不能沿用 `/api/edit` 就声称实现。

局部 content_update 已支持 upsert/remove/page_order；未改页保持所有 slots，改动内容或顺序让整稿输出失效。材料更新后的 compose 判断影响可复用。

依据：[editing.py](../../../src/deck_master/editing.py) 行 251；[service.py](../../../src/deck_master/service.py) 行 711、1458、1565；[tasks.py](../../../src/deck_master/tasks.py) 行 732、783。

### 2.6 任务与结果需要完善关联

Task 有 result_refs，但新任务初始化为空；accept 把 task 标 completed 时没有填入该字段，结果引用只在返回值中返回。新读模型需要补持久化请求→任务/attempt→结果→采用关联，并为旧项目以 revision/change/inputs 投影可确证部分。不得宣称所有旧记录链条完整。

依据：[task契约](../../../src/deck_master/resources/contracts/task.v1.schema.json) 行 120；[tasks.py](../../../src/deck_master/tasks.py) 行 605、639、1056、1167。

### 2.7 标注有可复用几何，但缺独立用户变更语义

Artifact 的 reference_regions 有 region_id、bbox_normalized、expected_text_refs 等；Page 文字块和可见原子有稳定身份。但它们不等于跨版本用户意见系统。现有 Web feedback 仅把单页 instruction 变成 repair task。新标注应绑定确切 page/layer/artifact/version，保存不执行；多区域、文本范围与变更意图必须保留结构。

依据：[artifact契约](../../../src/deck_master/resources/contracts/artifact.v1.schema.json) 行 200；[content.py](../../../src/deck_master/content.py) 行 30、45；[web.py](../../../src/deck_master/web.py) 行 120。

### 2.8 Web 能力小于核心能力

`project_view(revision=)` 已支持历史，但 HTTP `/api/view`、单页 API 只读当前。投影只有 Page、artifact slots、pending tasks、reviews、简化 design、outputs；task sources/prompt/完整设计上下文在 Host task_summary 内。POST 仅 edit/feedback/cancel/restore/check/export。没有独立项目启动入口或完整链路 API。

依据：[view.py](../../../src/deck_master/view.py) 行 20、90；[web.py](../../../src/deck_master/web.py) 行 109、165、183；[service.py](../../../src/deck_master/service.py) 行 394。

### 2.9 导出、历史和门禁应延用且明确兼容变化

当前 export 支持 review/delivery（working 为 review 别名），必须有当前 PPT。review 包含 page.json、原图/SVG/预览及整个不可变工程数据；并非新版要求的可外发审阅包。新 review 脱敏与新增 engineering 是明确的兼容行为变化，必须迁移说明。restore 生成新版本，外部调用事实与 user stop 不回滚。

PPT 的依赖是有序 SVG 集合；当前 PPT 预览 derived_from 指向 SVG，并非直接指向对应 PPT Artifact。应固定 revision 确定其所属成品，并补明确父关系，不依据文件名猜。

依据：[editing.py](../../../src/deck_master/editing.py) 行 287、333、375、384；[pipeline.py](../../../src/deck_master/pipeline.py) 行 289、311、317、323；[cli.py](../../../src/deck_master/cli.py) 行 192。

## 3. 不重新发明的底座

沿用 Store 原子写及已验证的 operation_id 行为（task accept 丢回执恢复见 F03，不视为完整通用幂等）、page_hash 冲突、cancel-first/late-result 拒绝、输入摘要、真实质量检查、不可变历史。引用关系可以投影时不重复存储第二份；任务状态只来自核心，不让前端自行推导“处理中/完成”。

依据：[tasks.py](../../../src/deck_master/tasks.py) 行 840、856、879；[editing.py](../../../src/deck_master/editing.py) 行 255、395；[models.py](../../../src/deck_master/models.py) 行 409、435。

## 4. 可复现检查与证据边界

本次：读取 AGENTS、任务索引、恢复手册、活动 contracts、service/tasks/view/web/store/production/editing/pipeline/cli；用 rg 核查 outline/candidate/prompt/references 路径。没有验证任何真实项目是否保存实际 prompt，没有把 optional schema 能力当已有项目数据。
编码阶段测试优先复用 tests/rebuild/test_store_transactions.py、test_tasks.py、test_production.py、test_page_visual_gate.py、test_service_flow.py、test_web.py、test_export.py 等；每包具体验收见 [开发包](packages/README.md)。本次文档核查不需要运行渲染或外部模型。

## 5. SVG/PPT可编辑性与质量摘要补充核查

再次只读核查同一d1c7c46，未执行真实Office编辑或生产调用。以下能力不等于Web已有呈现，需W05/W11投影接入。

| 可支持的UI摘要 | 当前真实字段/来源 | 能说明什么；不能说明什么 |
|---|---|---|
| 形状和文本可编辑声明 | Artifact.editability = editable_shapes_and_text / not_applicable / unknown；pipeline为自产PPT写前者 | 这是输出能力声明；不等于桌面编辑实测，也不承诺原生Office图表Edit Data或原生表格单元格 |
| 每页文字/形状统计 | readback报告 pages[].page_id/text_runs/native_shapes | text_runs计PPT XML的a:t节点；native_shapes计p:sp，包含文本shape；不是文本框数量、也不是非文本图形数 |
| SVG输入图像元素 | object_trace的pages[].shapes[].kind，可计算kind=image数量 | 可新增读投影计算并标“SVG输入图像元素（推导）”；d1c7c46没有raster_count/image_count持久字段，不能叫PPT光栅化比例或假装已统计 |
| 字体声明与可用诊断 | design_context.fonts[].fallback_font_ids；doctor(fonts=…)给requested/matched_family/file与ready/unavailable | fallback链只校验引用/循环；不是已发生替换。pipeline要求真实匹配字体，否则needs_tool，不能显示自动fallback成功 |
| 工程检查 | render_report.status/findings/pages；包含文字缺失/不一致、过小/透明、越界、节点/连线发现 | 来自当前PPT XML与Page/SVG核对；不等于审美或专业使用认可 |
| 专业/桌面编辑评估 | review.kind=professional_use/desktop_editing，status、subjects、reviewer、observations/findings/evidence；导出professional_evidence | 只有相应输出的记录才呈现；无记录not_evaluated。导出顶层desktop_editing仍固定not_evaluated，不能混作已测 |

准确源码位置：

- [artifact.v1.schema.json](../../../src/deck_master/resources/contracts/artifact.v1.schema.json) 行254–260、277–292：PPT必需editability及明确边界；[pipeline.py](../../../src/deck_master/pipeline.py) 行55–59写能力声明。
- [pipeline.py](../../../src/deck_master/pipeline.py) 行162–168回读a:t，286–287写text_runs/native_shapes及visual_review/desktop_editing=not_evaluated。形状越界/节点连线发现位于行201–285；这没有OCR。
- [compiler/api.py](../../../src/deck_master/compiler/api.py) 行28–31、49–62：object_trace即compile-input.json，含每页IR shapes、输入SHA及fonts文件SHA；[compiler/native.py](../../../src/deck_master/compiler/native.py) 行50–63：image生成picture，text走原生文字。
- [document.v1.schema.json](../../../src/deck_master/resources/contracts/document.v1.schema.json) 行609–624声明fallback_font_ids；[models.py](../../../src/deck_master/models.py) 行250–277只校验声明/环；[pipeline.py](../../../src/deck_master/pipeline.py) 行43–53真实匹配失败直接needs_tool；[doctor.py](../../../src/deck_master/doctor.py) 行55–61报告请求/匹配字体。
- [review.v1.schema.json](../../../src/deck_master/resources/contracts/review.v1.schema.json) 行14–35的kind/status、93–128 reviewer、175–233 element_refs与evidence；[editing.py](../../../src/deck_master/editing.py) 行225–236按当前PPT subjects读专业/桌面证据，350–366写导出摘要。新UI按所选快照读取这些事实并用核心freshness判断适用性，不凭最后一个字符串宣布通过。

没有发现OCR、图像文字叠加选择层或现成PPT光栅计数能力。首版图片用点/框意见，文本意见限真实正文与prompt；SVG有稳定内部元素ID时可定位元素，但不能由PNG自动获得同等语义。UI可以展示能力声明+工程事实+人工/专业检查三组摘要，不能折叠成单一“完全可编辑/已专业验证”标志。
