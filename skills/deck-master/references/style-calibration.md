# 固定版本的跨页风格校准

## RC3 初始设计与重设计

新 `style_input.v3` 使用 `intent=initial_design|restyle|feasibility`、真实 target_page_ids、固定 reference_refs，以及七项结构化 recipe_draft：palette、typography、density、composition、spacing、lines、icons。typography 使用项目实际 font_id 与三个明确字号；allowed_overrides 和 page_rules 记录许可和逐页完整替换。page_profiles、layout_rationale、sample_targets、uncovered_cases、tradeoffs 是规划证据，不能覆盖可执行参数或页面事实。

initial_design 不要求旧蓝图或风格图；restyle 要求每个目标的当前真实原图与独立风格参考。实际调用附件按目标原图 target_original 在先、独立参考在后的固定顺序传递，外部参考使用导入的原始字节。feasibility 可以只讨论真实 Narrative/Plan，保存建议或配方仍为零图像调用；不能据此派发实际样页。

确认配方并不授予执行权限。首批显式选择一页或两页均可，需当前 Request/authorization 的范围、调用和候选预算覆盖；两个结果可反序返回，每个只保存候选。采用与扩展各自记录，不自动扩大范围。配方 Ref 不被“最新配方”替代。晚到、暂停、撤权或目标改变不抹去已发调用。

新工作单声明 content_requirements_v1；v3 配方另声明 style_recipe_v3。production_request 保存解析后的 design_context、完整 content_requirements 与真实 content_basis。实际 prompt 使用同一完整要求和已编译 recipe_parameters；单位、限定、表格归属及节点/方向关系始终来自 Page。Plan 提供该页角色与全局论证推进；imported_mapping 未知角色保持 null，无 Narrative 时不制造主线。notes 和未消费的字体不进入图像 prompt。

以下 v1/v2 段落保留其原先的一页首试合同；新 v3 流程遵循本节。

`deck-master styles propose --project … --input style-input.json` 只保存建议预览，不创建任务。输入合同为 `style-input.v1`：项目/基准版本、固定 reference（page_id/revision_id/artifact_ref/role=reference）、明确 target_page_ids 与 instruction。默认借用 palette/typography；可显式传 dimensions 的 palette、typography、density、lines、composition。构图不默认借用。页面正文不来自参考页。

读取 proposal.conflicts 并请用户取舍，resolutions 以 conflict_id 为 key，取 `keep_target` 或 `use_reference`；重新 propose。检测仅涵盖明确的极简/高密度词对，不声称理解所有语义冲突。可按 W05 合同提供 prompt_selection（prepared_prompt/submitted_prompt + text_range.v1）；任意文本不自动切段。Host 提取的文字放 host_suggestion，仍是未确认建议，不得当成历史实际 prompt。

`styles confirm --proposal-id … --base-revision … --operation-id <UUIDv4>` 确认不可变配方。更新以 parent_recipe_id 创建新建议/新版本；旧配方不改。响应丢失查询原 operations，不创建新确认。`styles list/show` 支持 `--revision`。

`styles plan --input plan-input.json` 的输入为 recipe_id、page_ids、max_calls。首轮只能一个目标；返回既有 change_plan 后用 `changes commit` 派发，当前采用不变。沿用 `changes handoff` 的原任务 ID、generation_input 和调用额度。

工作单 `stage_request.style_recipe_ref` 要求额外声明 `--capability style_recipe`。Host 不读取“最新配方”替代此引用；冻结请求必须保留 style_recipe_ref、constraints、目标 Page、参考图和完整 prompt。工具调用只使用该已冻结请求。参考图只提供选定维度；逐项检查目标标题/事实/数字，不能承诺图像模型必然保留。生成不理想返回真实候选与问题，不伪造验收。

用户比较并采用首张候选后，再传 adopted_candidate_id 和明确其它 page_ids 计划扩展。必须是本配方当前采用且依据有效的原图候选；未选择页及参考页不变。目标基准变化报告逐页 style_conflict，不能更新配方锚点以隐藏冲突。改变目标范围/基准先创建新配方版本，再试一页。取消/unknown/晚到遵循原恢复协议。

此命令不改默认入口、HOME 安装或发布；真实效果评估与合成机制测试分别记录。
