# Web UI 合并版目标审查

日期：2026-10-02。审查基线：`bed476090e2a49b4c679906da2ce762753789d96`。

## 结论

**本轮已达到“新版 Web UI 接入真实制作链、可持续制作与审阅”的主要目标；尚未达到“全部功能对齐和验收项关闭”。** 不需要重做信息架构或视觉方向。下一轮应修复图标保真、比较操作和状态衔接，再关闭真实使用验收。

用户对 30 页内容密度和内容质量的认可继续有效。PR91 图标视觉认可仍待真实用户确认，不能以本次合并、CI 或 Agent 自审替代。

## 合并与验证基线

| 项目 | 实际结果 |
|---|---|
| [PR90](https://github.com/MainQuestAI/Deck-Master/pull/90) | 先合入 main，merge `4a511c8648fc5282a24b6230530a9050a77a8d85` |
| [PR91](https://github.com/MainQuestAI/Deck-Master/pull/91) | PR90 合并后改 base 为 main，再合入，merge `bed476090e2a49b4c679906da2ce762753789d96` |
| 合并内容 | main 的文件树与已验证 PR91 head `c46a3be936694a23fe286f72e817d3abef3bc0f6` 完全一致，无冲突修复或额外功能变更 |
| 合并后 CI | [37001853588](https://github.com/MainQuestAI/Deck-Master/actions/runs/37001853588)，准确绑定 bed4760，7/7 成功：4 组 Python/Node 单元矩阵、真实渲染、必跑浏览器与隔离 wheel UI、汇总 |
| 本次实际浏览器 | 真实 30 页工程的独立副本；5 个主工作面 × 1440×900、1280×800、390×844，共 15 组几何/截图；无整页横向溢出。另走查待办直达候选、单页图标对照、任务已读操作 |
| 缺陷探针 | 实际 Python PPT 编译及 ZIP 回读；真实 SVG 内存范围检查；隔离重试状态探针；浏览器键盘/已读操作；样例选择最小 Chromium DOM 复现 |
| 数据保护 | 原 PR90 验收稿、PR91 真实副本及本次审查副本的业务 revision 均未被审查改动；本次仅在审查副本保存个人阅读状态。客户图稿、截图、操作记录留在仓库外 |

这是一轮目标审查与重点代码审查，不是完整安全审计、屏幕阅读器合规审计或再次执行 30 页制作。本次没有重新进行长跑、真实 HOME 迁移或原生目录选择；既有证据及未完成项分别继承。浏览器记录发现内容工作面 CSP 错误，不能报告“浏览器零错误”。

## 原目标逐项判断

依据当前 [DESIGN](../../../DESIGN.md)、[A UI Spec](../deck-master-webui-v4-20260930/A-UI-SPEC.md)、[B 能力 Spec](../deck-master-webui-v4-20260930/B-CAPABILITIES-SPEC.md)、[U00–U06 计划](../webui-design-alignment-20261001/DEVELOPMENT-PLAN.md)及 [PR91 Spec](../deck-master-icon-quality-v1/SPEC.md)。历史冷墨色 Review Desk 规则已被现行 DESIGN 替代。

| 目标 | 判断 | 对应事实与限制 |
|---|---|---|
| 统一设计及五工作面，连接单页制作链 | 主要达成 | 浅色、黑主按钮、品牌和导航一致；内容/原图/SVG/PPT 为实际数据。三尺寸可读。R07 是局部样式问题 |
| 20–30 页整稿阅读、减少逐文件切换 | 达成工程目标 | 真实 30 页画廊可读，原图/SVG/PPT 各有 30 页；现有虚拟化及图像池边界保留 |
| 总览说明当前事实、待办和下一动作 | 部分达成 | 待办可定位第 6/29 页候选，未猜选第一项；但已读决定未贯通总览（R06）。真实稿仍有 27 页原图依据变化、SVG 适用性待核实，不应当成全稿需要重做 |
| 保存/交接/返回/采用分离、固定版本和原子事务 | 主链已达成，边缘待补 | 实际候选比较能固定双方，候选返回不自动采用；取消/迟到/原子采用已有回归。重试展示 R02、样例身份 R05 尚有缺口 |
| 图标忠实重绘、标准替换、跨页复用及实际 PPT 对照 | 部分达成 | 工作流及 24 个离线标准资产存在，真实副本完成采用；圆端点/连接 R01、透明图标 R03、键盘 R04 影响精细还原与对照 |
| 真实制作、安装、性能及最终用户验收 | 工程证据较完整，验收未全闭合 | U06/PR91 的真实制作、安装、导出和长跑证据保留；两轮候选采用、macOS 目录选择、30 秒真人观察和图标视觉认可仍须分别关闭 |

## 确认缺陷

本次未确认 P0/P1。以下 6 项 P2 与 1 项 P3 均有明确代码或运行证据；不是用测试数量推断缺陷不存在。所有行号对应 bed4760。

### R01 · P2 · 圆端点和圆连接未传到实际 PPT（置信度 10/10）

位置：[compiler/svg.py:169](../../../src/deck_master/compiler/svg.py#L169)、[icons.py:414](../../../src/deck_master/icons.py#L414)。

标准替换在 `g` 上设置 `stroke-linecap="round"` 和 `stroke-linejoin="round"`，但解析器的 `inherited_keys` 没有这两项和 `stroke-miterlimit`。根节点或分组声明的线条属性被丢弃。

复现：分组声明 round、内部折线路径不重复声明；实际编译后解析值是 `butt/miter`，PPT 的 `a:ln` 为 `cap="flat"` 和 `a:miter`。24 个 Lucide 文件也在根节点声明 round。既有目录探针以同一个解析器输出作预期，不能发现这个错误。两出口共享解析器，当前实测 PPT 证据来自 Python 出口。

影响：SVG 看起来圆润而 PPT 更生硬，正好削弱本轮图标精细度目标。修复应从继承语义入手，测试预期直接来自源 SVG 的明确声明。

### R02 · P2 · 重新检查时旧失败遮盖新任务（置信度 10/10）

位置：[candidate_preview.py:159](../../../src/deck_master/candidate_preview.py#L159)、[icon-workbench.js:114](../../../src/deck_master/resources/static/v2/icon-workbench.js#L114)。

`status` 的 `if cached:return _public(cached)` 先于 `_JOBS`。已有持久化 failed 报告时，重试虽然返回 queued，紧接着查询仍返回旧 failed。UI 只在 queued/running 时继续轮询，于是停止跟踪，后台完成后界面仍停在旧失败。

隔离探针保持新生成任务挂起，实际得到 `request=queued/status=failed`。未冒称已完成端到端浏览器失败注入。应明确一次检查的状态身份及缓存/在途任务优先级，并验证失败→重试→自动展示新结果。

### R03 · P2 · 完全透明的重绘图标仍通过“可见几何”检查（置信度 10/10）

位置：[icons.py:338](../../../src/deck_master/icons.py#L338)。

`has_geometry` 只检查包围框宽高。对真实已采用 SVG 的 3 个重绘图标，在内存中把全部选定对象改为 `opacity="0"`，`check_scope` 仍返回 pass。没有向真实工程提交或采用此结果。

影响：工程门不能兑现 `replacement icon must retain visible native geometry` 的明确约束。应检查有效透明度以及是否存在有效填充/描边；仍允许辅助子树为空而同一图标整体保有可见内容。该检查不应扩展为自动审美评分。

### R04 · P2 · 对照画布方向键触发翻页（置信度 10/10）

位置：[project.js:226](../../../src/deck_master/resources/static/v2/project.js#L226)、[icon-workbench.js:25](../../../src/deck_master/resources/static/v2/icon-workbench.js#L25)。

图标 canvas 可聚焦，但全局翻页排除项不含 `.icon-crop-scroll`/图标比较区域。实际浏览器打开第 4 页图标候选局部对照，聚焦 canvas 后按 ArrowRight，URL 变成第 5 页并移除 candidate 参数。

影响：键盘用户不能稳定检查局部细节，违背固定比较与键盘替代要求。应把方向键交给局部阅读区域，并保留阅读标题上的原有翻页快捷键。

### R05 · P2 · 跨页样例使用数组下标保存，列表变化会换样例（置信度 9/10）

位置：[icon-workbench.js:44](../../../src/deck_master/resources/static/v2/icon-workbench.js#L44)、[同文件:79](../../../src/deck_master/resources/static/v2/icon-workbench.js#L79)、[icons.py:253](../../../src/deck_master/icons.py#L253)。

草稿保存 `sample.value`，选项 value 是数组下标；恢复后交接读取 `samples[Number(sample.value)]`。样例不再是当前采用时，listing 会移除它。Chromium 最小 DOM 复现：保存 A 为下标 0，A 被移除后，恢复选择与交接对象都变为 B。

应保存 `sample_candidate_id + sample_icon_index` 等稳定身份；原样例失效时明确要求重新选择。此缺陷会改变用户原选择，但**不等于绕过后续图标范围确认或已经修改稿件**。

### R06 · P2 · “标记已读”与总览待办不一致（置信度 10/10）

位置：[run-desk.js:131](../../../src/deck_master/resources/static/v2/run-desk.js#L131)、[workbench.py:442](../../../src/deck_master/workbench.py#L442)。

任务面把已读身份写入个人草稿的 `run_desk.seen`，总览对所有 completed、有 result_refs、无 candidate_refs 的任务始终生成 review_results。

实际浏览器标记一项结果已读，按钮变为禁用的“已标记读过这些结果”；返回总览后，该 task 仍在 review_results 的 120 个目标中，并继续显示“30 页结果待阅读”。这不是缺少业务质量确认，而是个人阅读状态未贯通工作面。

应统一个人已读投影，以任务身份和结果摘要绑定；只减少“待读”提示，不改变采用/质量/交付事实。新结果必须重新出现。

### R07 · P3 · 内容大纲内联样式被生产 CSP 拒绝（置信度 10/10）

位置：[content-sources.js:121](../../../src/deck_master/resources/static/v2/content-sources.js#L121)、[web.py:83](../../../src/deck_master/web.py#L83)。

`style: 'margin-top:7px'` 经 setAttribute 写入，生产 CSP 不允许内联样式。打开真实六章节大纲出现 6 条 CSP 错误，间距声明未生效。内容仍可阅读，不是主流程阻塞。改用样式类，保留现行 CSP；浏览器门补充 console/CSP 检查，不只捕捉 pageerror。

## 验收债务及产品收口

- **U06 两轮候选决定**：第 6、29 页候选仍待用户采用或保留。保留当前可以结束决策，但不能冒充计划要求的两轮采用实证；若保留，需要另选获认可样例完成采用验证。
- **依据和适用性提示**：原图依据变化与 SVG 未登记显式依赖是真实历史事实。不能为了总览变绿改写原图依据，也不能用用户内容认可替代依赖校验。下一轮需提供“需重做/仅待核实/已明确保留”的可解释处理，并只依据可验证对象建立后续绑定。
- **原生目录选择**：既有 U06 实际点击返回 local action failed；本次未重复唤起系统对话框。需保留取消、失败、超时的准确原因及手动输入降级，再做本机实测。
- **30 秒真人观察和图标视觉认可**：均仍待真人证据。用户已有内容认可不撤回、不扩大；工程通过和真人认可继续分报。
- **过期方案可见性**：当前只列当前 revision 的图标提议。建议明确显示过期原因和重新定位入口；暂归状态收口，不作为本次新增确认缺陷。

## 审查覆盖与排除的误报

主审完成目标/代码/浏览器检查，另有同宿主独立图标审查及只读外部静态审查；外部建议经主审验证后才进入上表。不是三次独立用户验收。

外部静态审查提出“二次编辑导致许可丢失”。复核确认中间 SVG 的 XML 注释可能被解析器去掉，但 `data-icon-license` 保留，实际 PPT 文档说明及公开 SVG 导出均补回 ISC/MIT 全文，因此**不报告为许可整体丢失**。意见删除、多个计划无反馈等未完成适用前提复核，不提升为已确认问题。

脱敏结果见 [evidence/checks.json](evidence/checks.json)，下一轮执行及验收见 [FOLLOWUP-PLAN](FOLLOWUP-PLAN.md)。私密浏览器截图、原始响应和探针输出保存在本机审查目录，不随文档进入 Git。
