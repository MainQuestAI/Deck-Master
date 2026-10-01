# U03：个人总览阅读偏好与清理

基于 U02 最终合并 `b7e90405e9aa51e8d86d282b9b4309b56fca4a8d`，工程提交 `f8c2613`，最终展示修订 `f73b9e84d991f5ade8a5fb8daf71d1354260d6fa`。U01/U02 托管 CI 的四组合单元、真实渲染、浏览器/隔离安装及汇总均成功，PR85/86 已合入。

| AC | 实现与验收 |
|---|---|
| U03-1 | 独立 ui_overview.v1 能力及 GET/POST，恢复优先显式有效 URL → 项目/固定版本保存稿 → 默认值。搜索、待处理筛选和排序刷新/跨工作面可恢复；不会恢复批量勾选或计划 |
| U03-2 | 严格项目身份/已提交固定 revision；最多 12 个版本按明确修改淘汰，读取/轮询不增长历史。新版本不继承旧版本偏好；固定历史保留自己的读设置 |
| U03-3 | CAS 两窗口只有一个写入赢家；冲突保留当前输入并明确选项目稿或窗口稿。真实已保存响应被丢弃时，先按原内容核实，再保存后写输入。损坏文件不阻塞总览，保留原文件并可下载窗口副本 |
| U03-4 | 清理覆盖 overview_preferences 的清单、etag 复核、完整记录备份及日志，并持有 overview.lock。原偏好清为空 CAS 屏障；清理前无记录也建立屏障，阻止延迟的 null-etag 首次写复活旧状态。损坏/外项目偏好隔离保留 |
| U03-5 | 核心、HTTP 和浏览器检查 business 指针/内容/历史不变，未创建任务或制作调用；只读示例也可保存个人阅读偏好 |

新核心/HTTP、旧清理与模块 33 项通过；完整 Python 3.12/Node 24 单元 1013 项通过；完整 Chromium 回归 18 项通过，均 0 skip。最后把冲突显示改为可读搜索/范围/页序、元数据折叠后，实际窄屏双窗口回归及所有模块解析 2 项再次通过。Ruff、diff check 通过。

[单元](evidence/u03/unit.log) · [核心/清理](evidence/u03/core.log) · [浏览器](evidence/u03/browser.log) · [最后展示复验](evidence/u03/final-detail.log) · [390px 冲突](evidence/u03/overview-conflict-mobile.png) · [机器记录](evidence/u03/validation.json)。

无 ui_overview.v1 的旧核心使用窗口会话态，不能假报项目已保存。严格 ui_position.v1 不增加字段。B05 清理 schema 的 item kind 增加 overview_preferences；旧业务 Document 格式和制作协议保持不变。全部样本是合成工程证据，真实 Host/质量仍未验。
