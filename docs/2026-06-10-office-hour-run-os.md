# Deck Master Office Hour: Professional Deck Run OS

Date: 2026-06-10
Status: BASELINE FOR CEO REVIEW

## 1. Conclusion

Deck Master 的下一阶段产品路线是 `Professional Deck Run OS`。

它服务售前解决方案架构师和专业顾问，把会后客户上下文、历史方案资产、当下业务判断和 AI 引导式对话，转成可审查、证据充分、可继续打磨的客户 Solution Deck 草案。

第一阶段不追求替代人工最终判断。它要先把“从方案思路基本确认到第一版可审查草案”的成本，从约 12 小时压到约 2 小时。

## 2. Locked Decisions

- 第一用户：售前解决方案架构师。
- 第一样本：当前用户自己的客户 Solution Deck 工作流。
- 第一场景：会后客户 Solution Deck 草案。
- 现状替代方案：手工拼装历史材料、会议纪要、产品资料和个人判断。
- 核心指标：约 12 小时到约 2 小时。
- 产品形态：专业 Deck 的生产运行时，避免停留在单点页面生成器。
- 首版边界：本地/已导出资料优先，保留人工审查，不做实时飞书拉取，不做长期思考库，不做 reference PPT 自动视觉提取。

## 3. Why This Is Different

主流 AI Presentation 工具主要集中在 prompt/doc/url 到 slides、视觉美化、品牌一致性、协作编辑和导出。

Deck Master 的差异点应压在专业 Solution Deck 的生产过程：

- 论点：这份 Deck 到底要证明什么。
- 论证：为什么这个判断成立。
- 论据：哪些客户原话、数据、案例、产品证据和历史页面能支撑判断。
- 取舍：哪些内容保留、删掉、合并或进入附录。
- 复用：哪些历史优秀页面可以 reuse 或 adapt。
- 审查：哪些页面缺证据、缺主张或存在交付风险。

参考公开资料：

- Beautiful.ai 与 Gamma 对比：https://www.beautiful.ai/comparison/beautiful-ai-vs-gamma
- Prezent AI presentation makers：https://www.prezent.ai/blog/best-ai-presentation-makers
- Zapier AI presentation makers：https://zapier.com/blog/best-ai-presentation-maker/
- Presentations.AI：https://www.presentations.ai/

## 4. Run OS Product Shape

一次 Deck run 应管理以下对象：

- `context_manifest.json`：本次引用的会议转写、客户材料、历史方案和知识片段。
- `conversation_session.json`：AI 追问、用户确认点、已锁定判断和待补缺口。
- `deck_brief.json`：目标受众、业务目标、主张、边界和风格要求。
- `claim_map.json`：核心论点、支撑逻辑、证据需求、已有证据和风险。
- `page_tasks.json`：分层页面任务，包括 planning、retrieval、sourcing、generation。
- `sourcing_plan.json`：每页 reuse、adapt、generate、manual_placeholder 的来源判断。
- `preview_manifest.json`：Web Studio 审查用的页面状态、来源、风险、备注和审批。
- `quality_reports/draft_gate.json`：Draft Gate 对论点、证据链和页面职责的检查结果。

## 5. CEO Review Questions

下一轮 `plan-ceo-review` 应围绕 4 个问题展开：

- 2 小时可审查草案是否是足够硬的 10 倍指标？
- 会后客户 Solution Deck 草案是否是最窄可赢切口？
- `Run OS` 是否会过早平台化，导致首版范围过大？
- 首版能否用一个真实客户项目稳定验证价值？

## 6. Validation Scenario

选择 1 个真实客户项目作为回归样本。

输入：

- 会议转写。
- 客户材料。
- 历史方案摘要。
- 产品资料。
- 用户口头判断。

必须产出：

- deck brief。
- claim map。
- page tasks。
- sourcing decisions。
- preview manifest。
- Draft Gate 报告。

成功标准：

- 2 小时内生成可审查草案。
- 页面主线可用。
- 证据缺口明确。
- 历史页复用可解释。
- 人工能继续打磨。

失败标准：

- 页面泛泛成稿，像普通 AI PPT。
- 证据链不清。
- 历史资产引用没有理由。
- 用户仍需手工重做主线。
