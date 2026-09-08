# SC-1.1 偏差与未闭环记录

本表以本轮 PR #31 修复为准。历史实现和历史测试不自动构成当前候选验收。旧版本中“宿主无 ImageGen”“MIG apply 未实现”“render 接线未实现”等描述已失去时效，改用实际实现状态与验收状态分列。当前总体 `in_progress`。下表是本轮初始待验收基线，实际已执行内容与残留问题见 [PR31 修复验证记录](pr31-validation-progress.md)；不继续将表内历史 not_run 解读为接口尚未实现。

| 范围 | 当前实现/决定 | 产品验收状态 | 收口要求 |
|---|---|---|---|
| 内核落位 | `scripts/native_pptx/` 与旧 HD 适配继续沿用；不要求复制完整上游产品 | not_run | 在最终候选上验证单一实现、许可/依赖闭包与安装产物 |
| 业务校验 | 适配器向编译器注入校验；不能将缺校验作为允许编译条件 | not_run | 实际调用方正反例、真实编译与回读 |
| 路由/发布安装 | 默认 native、legacy 可选的接线在本轮修复；不再沿用旧 required 前置 | not_run | 干净安装树、源码隔离、哨兵访问和全入口一致性 |
| 宿主工具 | 工具可用性依当前会话现场探测；不能从旧笔记推断不可用 | not_run | 真实 ImageGen 两页、七类重建、桌面编辑；机制 stub 不替代 |
| 修订与指纹 | 完整快照、真实读取器、路由/内容当前性在本轮修复 | not_run | 锁内竞争、进程中断、恢复、旧报告/批准失效和真实消费者 |
| 迁移 | source-bound plan、candidate 编译后 apply、新修订、verify、rollback 已实现；事务测试使用明确标注的编译 stub | not_run | 旧 HD/standard 真实原生构建与迁移回滚、批准产物 hash 保留、缺源只读 |
| 规格映射漂移 | 原 SC1 当前已有 91 项，旧 supersession 只有 88 项；新增 A-13/I-08/Q-13 保守纳入工程验收 | not_run | 逐项给实际证据；不删除额外要求或把 superseded 当 passed |
| 10 页原材料 UAT | 提供公开合成材料与目标，不提供逐页稿；未知客户数据明确留空 | not_run | 真实研究/生产/修复/批准导出和局部修改 |
| 人工与效果边界 | 用户最终视觉复核/文件批准未代签；真实客户配对不在本轮 | not_run / outcome_pending | 人工完成后才能工程收口；L3 不标 accepted |

完整 case 列表见 [engineering-gap-inventory.md](engineering-gap-inventory.md)，记录工具和规则见 [acceptance-tracking.md](acceptance-tracking.md)。本表状态不从测试文件存在、实现提交或 schema 自检推导通过。
