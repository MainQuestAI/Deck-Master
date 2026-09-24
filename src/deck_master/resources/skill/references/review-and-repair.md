# 审阅与返修(reference)

最终六维解释在 `src/deck_master/review.py` 的 `evaluate_current(document, reviews,
artifacts)`；逐页解释在 `evaluate_page_visual(entry, reviews, artifacts)`。接收、
`continue`、读取、UI 与导出按相同记录和当前依赖判定，不把逐页通过当作最终通过。

- `review_stage=page_visual`：SVG 接收后的当前页预览生成后执行。Host 实际查看
  Page、原图和 SVG 预览，提交 `blueprint_content`、`blueprint_fidelity`、
  `readability` 三类记录；subjects 必须包括这四个当前对象，dependencies
  必须包括当前 Page、蓝图、SVG、设计样式与批准资产。缺项不能派发下一页；
  `must_fix` 只返修本页，然后重审。重复提交同一 Page/SVG 而未关闭发现时停止循环。
- `review_stage=final`：整套真实 PPT 渲染、文件读回后执行下列六维审阅。
  旧记录无 `review_stage` 时解释为 final；逐页记录不能补足 conversion、privacy
  或最终 readability 等维度。

- status(07.2):有 open `must_fix` → `fail`;必需维度(content /
  blueprint_content / blueprint_fidelity / conversion / readability /
  privacy)× 当前页集合缺执行记录 → `not_evaluated`;已执行但有未处置
  `needs_judgment` → `needs_review`;全部完成且问题修复或有具体理由 → `pass`。
- 当前性:Review 的 subjects 必须含当前 `outputs.pptx` 与该页 `page` ref,
  dependencies 的 sha 必须与当前对象一致;旧产物上的 pass 只作历史
  (stale),不覆盖当前 fail。
- 空 reviews / 空 findings / 空登记都不是高分:`not_evaluated`。
- 像素差异分流:`triage_render_difference` 按区域有序规则给出
  must_fix / needs_judgment / accepted_variance,不做指标投票。
- 独立性:`validate_independence` — host_self/tool 永不独立;
  independent_host 与 human 类型需要真实 `execution_ref`,模型不得代填。
- 返修关闭:只有 `replaces` 指向旧 Review 不可变 ref、同 `review_id` 与
  `finding_id`、subjects 新增当前新产物、且有实际复查 observations /
  evidence 的新 Review 才能把 finding 记为 fixed;仅改 resolution、旧
  subjects、过期证据均被拒(接收侧 `tasks._adopt_review` 已校验)。
- 源图期待独立于输出 SVG 登记:`source_expectations` 对未识别维度保持
  `not_evaluated`,coverage 不满记 1。
