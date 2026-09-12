# 04｜图片蓝图、SVG 重建与宿主任务

## 4.1 默认端到端行为

新 Run 选 native 时，默认 authoring_mode=image_blueprint。Agent 先从现有材料完成方案和页面内容，不要求用户提供逐页稿。公共主线和风格已有有效授权时直接复用。生产进入 Builder 后不能重新开展一轮独立 MBB 访谈。

阶段动作依次为：validate_content → prepare_blueprint → awaiting_agent_imagegen → review_blueprint → awaiting_agent_reconstruct → validate_svg → visual_review → compile → readback → quality_review → awaiting_final_approval / deliverable。它们是既有 deck-builder 内部动作，不是第二套公共工作流。

先完成两张代表页（通常为封面/结论页之一与架构/信息密集页之一）验证风格与可编译性；风格已锁定无需再次向用户索要同一确认。通过后批量处理 pending_pages，失败只返回失败页。代表页选择由 Agent 根据任务判断，不增加必须用户拍板的技术步骤。

## 4.2 ImageGen 输入与事实边界

仅给批准后的 customer-visible 投影：精确标题、结论、正文、数据、必要限定、组件关系、视觉意图、风格/字体、画布。内部证据ID、工具路径、SCR/MBB标签、动作指令、调试说明不得进入图片。需要保留的业务条件和数据口径不能被当作“内部注释”删掉。

Page Package/Content Lock 是文本和事实来源；Diagram View 是组件/关系来源；图片是视觉来源。图片错字、错误数字、箭头反向、漏限定不得回写成新事实。Agent 应按内容锁修复，必要时重生蓝图，不让用户重填材料。

页码/页ID不交给 ImageGen 猜。沿用本项目默认图片蓝图无生产标注；需要客户可见页码时由构建器在明确授权的正式页脚中生成，并进入内容/版式检查。不得趁本轮改架构取消既有客户安全规则。

## 4.3 宿主能力与来源证据

不新增内置 Provider/模型服务，也不强绑具体模型名称。至少检测宿主是否实际提供图片生成、图片阅读、文件回传/写入、SVG生成与工具调用；注册 Skill 不代表工具可用。首次能力状态 unknown 时发真实轻量探针或报告 unknown，不能自动标 ready。

复用现有 blueprint prompt/manifest/provider receipt，区分：

- `host_tool_observed`：宿主确实执行工具并由可信适配器记录输出文件/实际元数据；缺 provider request_id 的宿主写 null 及 metadata_level，不能制造 ID。
- `provider_verified`：工具提供可验证请求/响应字段，按可用字段校验。
- `imported_reference`：用户已有图片；可用于明确的还原任务，但不能充当新 ImageGen smoke。
- `fixture`：仅 deterministic regression，不进入生产或真实能力证据。

以上是 provenance 目标语义，不是增加四个 Provider。Runtime 的本地签名仅证明本地绑定完整性，不声称证明外部服务真实性。若实际工具无法回显任意 nonce，不得要求用户提供服务签名密钥或伪造回显；使用 Runtime action_id、输入hash和宿主观测收据完成绑定，明确证据等级。可疑、无观察或只写“已生成”的结果不能满足 fresh provider smoke。

实际模型名、请求ID和调用时刻来自宿主可得信息；若不可得则 null+reason，不把用户所说“GPT-6 Astra”填写成已验证执行来源。探针与操作证据需要 Codex 核验。

## 4.4 蓝图检查与修复

检查全页、标题、正文、页脚、角落及架构/图表局部。错字、漏字、无依据数字、内部文字、关键关系错误分别记录。小范围文字缺陷可在 SVG 重建中按锁定文本修正，并保存 `approved_delta`（允许的视觉差异）；严重布局/结构问题必须重新生成。不能为了像素一致复制错误，也不能借文字修正任意改掉批准风格。

默认每页每类动作最多3次尝试（首次+2次修复），失败、超时和取消前已经调用的成本计入预算；幂等重复接收同一结果不再次计费/计次数。宿主无法提供 token/cost 时记录 calls 和 elapsed，不虚构金额。预算内可修复问题由 Agent 继续，不要求用户重复说继续；预算耗尽保留已完成页和可读报告。

## 4.5 图片到 SVG 的生成合同

必须加载 `methods/IMAGE_TO_SVG.md` 与当前 compiler-supported subset。输出真实 SVG 和 Scene 旁注，同时保留 stable element_id、component/model_ref、text_ref、asset_ref、layer/group 等映射。SVG 几何与 Scene 的几何约束必须一致；Scene 不得脱离 SVG 独立生成 PPTX。

文本从 Content Lock 拷入，不 OCR 后作为新文本；图像读取用于确定布局和视觉。架构箭头方向同时与 Diagram View 比较。照片/插画为独立登记资产；禁止把整页图片、分块整页图片或业务文字裁片放进 SVG。所有主要图形必须存在可编译原生元素。

Agent 对不支持的 SVG 元素改写为支持子集，不能要求用户安装完整 PPT Master。重建成功后运行真实 SVG renderer、与蓝图比较、原生编辑目标检查；仅写 JSON pass 不算完成。

## 4.6 直接 SVG 与局部修改

`direct_svg` 是明确选择的补充模式，与默认图片蓝图共用 compiler。无 ImageGen 时准确报告缺项，并给出已有可选模式；不能静默切换，也不能伪造一张图片冒充生成完成。用户已提前授权的 direct_svg 路径可直接继续。

单页改字/颜色时，根据用户变更复用原布局，不强制重新 ImageGen。旧蓝图保留为视觉参考，明确新 Content Lock 和允许差异；修改了结构、主要数据或主视觉则重新生成受影响页。无关页面、有效业务决定与历史批准文件不变；当前整套PPTX改动仍需要新版最终批准。
