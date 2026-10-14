# RC3-02 当前 Head CI 守门

结论：FAIL_ENGINEERING_CI。当前四组 Unit 矩阵均失败，不得合并。

- PR：#117，源 Head `0d12a9d78ed0526f0fb74d1b8abed0a2ec154b4e`。
- 实际被测 PR merge SHA：`2b6764d91afecaa5765c4379f39772e2b735ef64`，与 PR metadata 一致。
- Base：`8e274576e7a93de7d10c054558991878501fff0c`。
- 精确 Run：`38639118685`（#489），观察 2026-10-14 21:23:49 UTC 时仍有 browser 执行，Group report 待依赖。
- 四矩阵各：`3 failed / 1845 passed / 3 skipped / 456 deselected`。
- Render：`53 passed / 2254 deselected / 22 warnings`。

三项失败均位于 `test_rc3_notes_transactions.py`，共用 `_completed_visual` 第 35 行：`service.continue_project(project)['pending_tasks'][0]`，列表为空导致 `IndexError`。失败测试为：

- `tests/rebuild/test_rc3_notes_transactions.py::test_notes_edit_preserves_completed_visual_and_actual_review_bytes`
- `tests/rebuild/test_rc3_notes_transactions.py::test_visual_open_finding_not_fixed_by_notes`
- `tests/rebuild/test_rc3_notes_transactions.py::test_actual_completed_visual_notes_assembly_export_zero_image_ledger`

四个 Job 的必要完整 trace 分别归档 `raw/job-<job_id>-failure-trace.txt`（ID：116109825642、116109825671、116109825796、116109826700）。初步怀疑 unit job 无渲染器而 fixture 依赖渲染继续阶段；此为待 Owner 证明的假设，不是 CI 日志已经证明的根因。

真实日志给出 3 个 skip，但 `-q` 未输出具体测试 ID 或原因，不能把它们编成通过，更不能把本地1851作为CI数字。旧 RC3-01、daily/source/mixed PR113 均被排除。

守门员已通知 Root 与 Owner，未修改源码、重跑、评论、推送或合并。文档独立审查与专业/桌面/人类验收另行记录。
