# 内容到设计：保留关系，不按框架名称套版

Design 消费固定Page、确认方向与作用范围。下列规则只决定表达方式，不授权重写结论、删必要限定或制作未获授权的页面。

## 先识别关系
比较关系→共同标准的表格或分面；时序关系→步骤或时间线；因果/机制假设→明确箭头及条件；组成→分组与分母；教学辨别→关键差异可同时观察的案例对。

同一方法没有唯一版式。问题树可以只用一句综合判断和一张差异表表达；Toulmin不必画六个框；SCR不必占三个章节页；Pugh可以使用自然语言和数值，不必展示符号计分。

## 三类不得丢失的语义
- 比较：各列的范围、单位、时间窗一致；正负符号必须与实际标准方向一致。
- 机制：观察事实、拟议设计和待验证箭头区分；图形位置不把相关变因果。
- 条件：影响本页结论的前提在读者能看到的位置；不能降为几乎不可读的脚注。

## 页面装不下怎么办
先识别重复与无贡献装饰，再提出拆页/分组/附录候选。需要修改正文、关键比较项或概念边界时交回Content/用户，不静默裁切。可用总览矩阵＋下一页必要细节；不执行“一律压成一页”的规则。

三种语义示例见 [semantic-layout-examples](../assets/design/semantic-layout-examples.md)。完整案例after稿是内容依据示范，不是排版尺寸标准。字号、画布和渲染仍沿用实际工作单与physical-units；本文件不规定70/20/10面积比例。

## 内容字段与上屏边界

新冻结输入的 `content_requirements.text_visibility=customer_visible_only.v1` 规定：只有固定 Page 的 `customer_visible` 提供上屏文字。`page_role`、`content_profile`、`density_rationale`、来源定位、作者核验和内部追溯是非上屏设计上下文，不逐字排到画面，也不因存在这些字段就追加免责声明。

- `content_profile` 是构成分类：`simple` 单一重点、`evidence` 支持主张的依据、`mechanism` 定性机制/关系、`data_dense` 必要的定量细节、`mixed` 多种用途。它不是证据等级；`evidence` 不要求显示内部来源，`mechanism` 不要求添加“未实测”。
- `density_rationale` 解释信息密度和应保留的业务关系，供设计判断空间；不是作者自证或待印刷正文。
- `required_qualifications` 是绑定 Narrative 中实际 `qualification` 节点的 ID；空数组合法，不能填条件句或预设产品节点名。必要业务条件应已写入 `customer_visible`；缺失时回到内容阶段，不在设计阶段擅自拼句。合法公开来源、业务前提和必要限定照原稿保留，不能按“来源/假设”等关键词删除。

没有实际 Plan 页职责的历史/导入稿保留 `null` profile/rationale 和空资格列表，不推断缺失内容。旧冻结输入没有 `text_visibility` 时保留其原投影与规则；不得回写新标识或补改旧任务方法。新策略只随新的正式准备/冻结生效，历史产物不因此被宣称已接受新审查。

## 逐页设计策略与有效布局（design_policy.v1）

新生产准备默认 `model_designed`：在固定正文、单位、归属、节点与有向关系内选择空间排布；旧 `layout_hint` 仅作建议，不根据表格或节点数猜策略。需要明确约定布局时，在 Page.visual_spec.design_policy 写入 `version=design_policy.v1`、`strategy=agreed_layout`、非空 `layout_instruction`，并记录 `purpose`、`primary_object`、`free_layout`、`table_roles`。自主策略也使用这些字段；非空提示或节点数量不是质量证明，封面不需要凑节点。

显式页策略的 layout_instruction 替换旧 Page.layout_hint、有效 requirements.layout_hint、继承的布局说明及规范 composition；其他规范维度继续生效。需要局部补充时 `visual_spec.design_overrides.layout_notes` 替换项目 layout_notes，空串表示明确清空。项目 style 的 `layout_page_ids` 只限制 layout_notes，缺省全部页，空数组无页；颜色、字体不因此失效。修图时先提交这些正式依据，再重新准备/冻结，不能只在调用端追加相反提示。Plan 的真实页职责和正文语义仍保留，不用排版策略重写内容。

`table_roles` 逐项记录实际表格 `block_id` 和 `comparison|content_inventory`。未声明的表按真实比较表保留。采集表可改空间组织，但全部单元文字、数值、单位及行列归属必须保留；不能把去表格理解为删内容。固定边、责任归属不随两种策略变化。

两种策略都须消费可编辑边界，不能只把蓝图称为“editable”：图像生成返回的是重建参考图，本身不是原生可编辑幻灯片。文字、关系连线与主要业务对象保持可分离，按实际 compiler 支持子集重建为原生 PowerPoint 文字与形状。照片、获准 logo、纹理、复杂插画允许成为有明确范围的位图素材；位图整体可替换，内部不能逐对象编辑。不得把要求可编辑的正文、关系和主要业务对象压入素材，更不能整页嵌图后宣称可编辑。对于超出支持子集的效果，在生成或重建前说明需要原生重画、局部素材化还是简化，以及视觉与可编辑性影响；不静默降级、不一律禁照片/阴影/插画，也不以此固定构图。相关说明是方案/生产上下文，不增加可见正文、对象类型或审批。

读取历史 Page/规范/冻结请求不会补策略或改旧字节。新准备在 resolved_design_context 与实际 prompt projection 冻结消费版本和字段；显式新字段或新策略准备的正式提交提高 `minimum_writer=design-policy.v1`，不支持此边界的旧 writer 必须拒绝继续写。旧冻结没有此策略时继续按原投影读取，正式重派发后才使用新准备规则。不新增人类审批或生产授权。
