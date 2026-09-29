# W07 核心实现与验证记录（核心切片）

基线：W06 UI PR #52 合并 `fc800d500462c720963f3f9e60d87ce0f90aa838`。当前分支 `codex/workbench-w07-core`，实现提交：`9ce30b15f793578d9bc9f604373fa728507cb172`。参考来源补充提交：`4e22054a13fd81cbc03ca68b4de170a0e1b13681`。核心 PR [#53](https://github.com/MainQuestAI/Deck-Master/pull/53) 待 CI 合并。本报告不表示前端或整卡完成。

- `changes plan/commit` 增加显式 `mode=auto|trial`、目标阶段与历史原图引用。旧 W06 输入的计划重算保持原样。参考文件来自已提交版本，冻结时不允许更换指令或遗漏附件。
- Trial 沿用 Task、调用额度、Host 声明、结果校验和原子回执，只保存 Candidate。`continue` 与自动任务复用排除 trial；实际未知调用与预算仍按原策略处理。
- `candidates list/show/plan/adopt` 及同源 HTTP 共用服务。生成依据、目标槽引用、project CAS 分开核对；长度一与批量采用同一事务，冲突零采用。候选采用后清除目标下游与整稿输出，其它页引用保留。
- 新 writer `candidates.v1` 拒绝旧 writer 降级。成功任务回执可恢复候选 ID；workbench.v3 的取消晚到重复返回仍是冲突，不报告已采用。旧格式返回约定保留。
- `stages assemble` 复用既有整稿编译，校验当前原图、SVG、预览和逐页审图；新格式 `build` 也不能绕过此门禁。显式编译结果与 OperationCommit 同指针提交，CAS 变化时不采用输出。

验证分层：

- 全量 rebuild：833 passed，134.59 秒。随后补强显式 assemble writer 升级与固定历史参考图测试；最终候选与 package-boundary 定向测试 22 passed（6.05 秒），CI 将再跑完整矩阵。
- 相关候选/观察/生成/逐页门禁/任务回归：103 passed。取消后的旧格式重放约定保留，新格式明确返回冲突。
- 真渲染测试使用 rsvg-convert、soffice、pdftoppm，校验审图前拒绝编译、审图后产生整稿与按页预览、同操作重放不再次编译。页面和审阅记录是明确的合成测试输入，不是人工质量验收。
- 原生附件采集新增严格 JSON literal + 同调用 PNG 回包 + 同项目对象路径/hash/调用前文件时间校验。7 项正反例覆盖变量、外部路径、改写、符号链接、迟到文件和无项目上下文；仅观察 reference 角色。真实参考图 Host 往返仍未验证。
- `w07_trial_adopt.py --help` 及 CLI 试作提交样例通过：保存真实返回 ID/原操作 payload、生成 handoff、当前产物槽不变；没有模型调用。
- Ruff、git diff --check、活动 schema/唯一镜像字节一致检查通过。

真实参考图调用、真实 SVG Host 往返、浏览器比较/采用及用户验收尚未完成，W07-AC07 保持未验证。工作台功能仍显式 opt-in；没有默认入口切换、实际 HOME 安装迁移或发布。

候选 show 补充已核对的固定参考来源（原 page/revision/artifact/file），不从当前稿推测。该补充连同非空参考图的合成事件完整往返通过 43 项候选/采集测试（6.04 秒）；这仍不是真实 Host 证据。
