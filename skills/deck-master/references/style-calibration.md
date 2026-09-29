# 固定版本的跨页风格校准

`deck-master styles propose --project … --input style-input.json` 只保存建议预览，不创建任务。输入合同为 `style-input.v1`：项目/基准版本、固定 reference（page_id/revision_id/artifact_ref/role=reference）、明确 target_page_ids 与 instruction。默认借用 palette/typography；可显式传 dimensions 的 palette、typography、density、lines、composition。构图不默认借用。页面正文不来自参考页。

读取 proposal.conflicts 并请用户取舍，resolutions 以 conflict_id 为 key，取 `keep_target` 或 `use_reference`；重新 propose。检测仅涵盖明确的极简/高密度词对，不声称理解所有语义冲突。可按 W05 合同提供 prompt_selection（prepared_prompt/submitted_prompt + text_range.v1）；任意文本不自动切段。Host 提取的文字放 host_suggestion，仍是未确认建议，不得当成历史实际 prompt。

`styles confirm --proposal-id … --base-revision … --operation-id <UUIDv4>` 确认不可变配方。更新以 parent_recipe_id 创建新建议/新版本；旧配方不改。响应丢失查询原 operations，不创建新确认。`styles list/show` 支持 `--revision`。

`styles plan --input plan-input.json` 的输入为 recipe_id、page_ids、max_calls。首轮只能一个目标；返回既有 change_plan 后用 `changes commit` 派发，当前采用不变。沿用 `changes handoff` 的原任务 ID、generation_input 和调用额度。

工作单 `stage_request.style_recipe_ref` 要求额外声明 `--capability style_recipe`。Host 不读取“最新配方”替代此引用；冻结请求必须保留 style_recipe_ref、constraints、目标 Page、参考图和完整 prompt。工具调用只使用该已冻结请求。参考图只提供选定维度；逐项检查目标标题/事实/数字，不能承诺图像模型必然保留。生成不理想返回真实候选与问题，不伪造验收。

用户比较并采用首张候选后，再传 adopted_candidate_id 和明确其它 page_ids 计划扩展。必须是本配方当前采用且依据有效的原图候选；未选择页及参考页不变。目标基准变化报告逐页 style_conflict，不能更新配方锚点以隐藏冲突。改变目标范围/基准先创建新配方版本，再试一页。取消/unknown/晚到遵循原恢复协议。

此命令不改默认入口、HOME 安装或发布；真实效果评估与合成机制测试分别记录。
