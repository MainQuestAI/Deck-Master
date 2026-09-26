# 合成往返示例说明（v1.1）

这里的公司、数据、输入和页面全部为合成内容。它们不是真实用户材料，也不是 Host 的运行成绩。

- `request-live.json` / `request-read-alone.json`：同一套材料、两种任务（现场讲解和独立阅读），都不指定固定目录。可以作为 `--task-file` 的输入。
- `materials/`：合成材料。`unrelated-catalog.md` 用来测试「补了无关材料」。
- `initial-pages.json` / `revised-pages.json`：完整的 Page v2 结构示例，视觉部分只写文字意图，没有生成蓝图或 PPT。
- `src-company` / `src-operations` / `src-interface` 是夹具里固定的 ID。真正 create 之后要换成 CLI 返回的 `src-<uuid8>`，不能假定按文件名生成。
- `input-context-before/after.json`：输入投影夹具，不是完整 Document。`input_digest` 按 SPEC §5.1 的算法计算。
- `update-interface.json`：`inputs update` 的 patch，内容是 V1 只读接口 → V2 允许保存草稿、正式提交仍由员工确认。
- `update-no-effect.json`：补一份无关材料。是否有影响要由 Host 判断，代码不能凭文件名自动断定无影响；Host 判断无影响时，提交空 upsert，并写出具体的 `unchanged_reason`。
- `result-input-revision.json`：`content_update` 只提交 p03。`expected-effects.json` 用来验证 p01/p02 的正文 hash 不变，以及禁止出现的说法。它不能证明图像或 PPT 已被保留，实施后要做真实集成验证。
- `project/.deckmaster/objects`：只用于核对示例中 ref/hash 的合成对象，不是可运行项目，不能拿 continue 的输出冒充运行结果。

v1.0 里的 `sources-selected.json`（source manifest）和 `questions.json`（request-input）已随范围删减移除。
