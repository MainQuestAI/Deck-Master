# 审阅与返修(reference)

统一解释在 `src/deck_master/review.py` 的 `evaluate_current(document, reviews,
artifacts)`:接收(submit)、读取(load/`editing.review_status`)、UI 与导出
(`editing.export_project`)共用这一份判定,不各写否决 if。

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
