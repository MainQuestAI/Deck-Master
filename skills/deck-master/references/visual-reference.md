# 外部截图视觉规范

工作单 visual_analysis 提供固定图片及摘要，逐张实际读取 preview 图片，保留原件。声明 changes.v1 与 visual_reference capability 后领取 style_analyze。禁止图像调用，不分配额度。

返回 kind=style_analyze 与 style_analysis，后者仅含 dimensions / palette / font_suggestions / conflicts / limitations。dimensions 含 palette、typography、composition、spacing、density、lines、icons；每项 summary 及 evidence，evidence 为 reference_id、归一 region[x,y,w,h]、observation、certainty(observed/approximate/unknown)。palette 为 #RRGGBB。font_suggestions 为 family/approximate/reason。conflicts 为 reference_ids/description。limitations 为文本数组。不确定信息明确说明，不伪造精确字体或业务事实。不返回 Page、SVG、reviews、usage_events。核心绑定参考并生成安全拆解图。

用户确认后 v2 配方经现有单页 trial、比较、采用、选页扩展。冲突须选择一个参考重新分析，不能过滤图片却保留混合规则。新原图试作声明 style_recipe、visual_reference、candidate_result、generation 能力，保持目标完整正文并记录真实调用。不能自动采用。

执行真实生图前读取固定请求并 freeze / call begin。Codex 原生采集要求单次调用采用带引号键名的 JSON 字面量，形式为 `const result = await tools.image_gen__imagegen({...}); generatedImage(result);`，可保留第一行 @exec pragma，不附加其它语句。prompt、参考路径、参数须与固定请求完全一致；完成后用本次原生调用 item_id 结算。引用证据未知或不匹配时不采用，不手工填写观察记录补过检查。
