# 来源与边界

取证日期：2026-10-23。方案输入为原“梳理修复方案”、六点只读复核，以及用户指定的第二轮前链路/Web UI 审计。私有原始文件、客户正文、截图、路径和执行身份未提交；公开复核入口使用下列 Issue 与固定源码。

## 版本

|对象|读取结果|含义|
|---|---|---|
|远端 main / 基准 PR 起点|`afcc23d1654a6ce24583677c4de9d4a80f0f89bd`|代码历史起点，不含本机全部窄补丁|
|[PR147](https://github.com/MainQuestAI/Deck-Master/pull/147)|Open / Draft / unmerged，head `ad2f278cd637f29b5665fcf71d7064098faf617b`|已有性能修复独立 PR；缩略图及发布残项未完成|
|观察安装源码|`18ac1d6d70d7e24d445ca5e558b659353adf2c5d`|含 #138 空发现、#139 原件读取及 PR147 同等改动，不把本机激活视为主线合并|
|#138 窄补丁|`84a63131f51d`|只覆盖空 findings 替换，复杂恢复仍待完成|
|#139 补丁|`f1ac7a714a6c9f25ebdaf5c68847afb25192328e`|候选原件引用修复，待正规集成验证|

前序复核将 267 个包文件与激活源码比较、PR147 的 11 个改动文件与激活文件比较，均未见差异；9 项已有定向回归在激活包上通过，原生审查测试使用合成 transport。它们是限定范围的历史复核证据，不是本方案所有产品修复或真实调用已通过。本轮未重跑这些产品测试。

## 新审计公开证据

|来源|公开入口|
|---|---|
|v3 规范被隐藏|[#181](https://github.com/MainQuestAI/Deck-Master/issues/181)|
|历史状态被当当前待办|[#182](https://github.com/MainQuestAI/Deck-Master/issues/182)|
|回执展开全部待办|[#183](https://github.com/MainQuestAI/Deck-Master/issues/183)|
|#132 新证据|[评论 6346416139](https://github.com/MainQuestAI/Deck-Master/issues/132#issuecomment-6346416139)|
|#134 新证据|[评论 6346418010](https://github.com/MainQuestAI/Deck-Master/issues/134#issuecomment-6346418010)|
|#141 新证据|[评论 6346416670](https://github.com/MainQuestAI/Deck-Master/issues/141#issuecomment-6346416670)|
|#164 新证据|[评论 6346417584](https://github.com/MainQuestAI/Deck-Master/issues/164#issuecomment-6346417584)|
|#165 新证据|[评论 6346417124](https://github.com/MainQuestAI/Deck-Master/issues/165#issuecomment-6346417124)|

本轮开始时已读取全部 51 个 Issue 正文及 40 条评论。相比前序快照为 3 个新 Issue、5 条新评论。Issue 的原始观察和后续评论都保留；本轮正文的“当前实施方案”节用于消除旧建议冲突，不伪造已完成状态。

## 不扩大证据结论

- 第二轮审计结论是 Design QA blocked；只读巡检、问题登记与修复是不同结果。
- 原审计核对 35 条不同实际图像调用，分轮 4/17/14；这里复用已公开结论，未发起新调用或推算费用。
- 用户已认可最终图片→SVG→PPT 的视觉还原。正式快照没有登记某份外部交付，不代表该文件视觉失败，也不把转换器列为主整改对象。
- 当前快照的 13 页原图、12 页当前原图依据及 SVG、1 页 stale/missing、无正式 PPT 槽位是特定时点事实，不是本方案承诺修完或替用户制作。
- #183 已证实回执体积膨胀，未测该路径 CPU；一次候选 GET 约2.476秒不等于 p95。#182 有后续产物也不足以断言所有旧 findings 已闭合。
- #134 跨轮拒绝保留正确的 execution 身份保护；先区分 Host 执行失误、指引不足及真实缺接口。
- 1280×800 同尺寸对照有效；1440×900 和窄屏视觉验收待准确捕获。390px DOM 无导航越界不代替完整视觉验收。
