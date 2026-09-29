# 生成工作台 v3 执行索引

当前活动卡：**W09 内容与来源调整，共享核心实施中**。W10 前端 PR #57 已合入 main（`c17ba51…`），最终 head 的 8 项 CI 通过；完整 20 分钟压力堆内存增长 2.07%，图片边界通过。W08 核心 PR #58 与前端 PR #59 已依序合入 main；浏览器试作/采用/扩展与保存恢复已验证，真实图像评价保留未选构图漂移，不代签用户验收。

- [独立 Review：4 P1、3 P2](REVIEW.md)
- [外部原始复核与取舍](OUTSIDE-REVIEW.md)
- [执行状态及 87 条 AC](execution-state.json)
- [W01 实现提交、46 项回归、浏览器与性能证据](W01.md) / [完整 300×5×3 压力补证](W01-PRESSURE.md)
- [W02 恢复切片](W02.md) / [冻结请求、Attempt 与真实 Host 证据](W02-PROTOCOL.md) / [ContentPlan 与来源版本](W02-CONTENT-PLAN.md)
- [W03 独立入口、服务生命周期与个人草稿](W03-CORE.md) / [前端与真实浏览器验证](W03-UI.md)
- [W04 缩略图与个人画廊状态核心](W04-CORE.md) / [同层画廊及图片资源验证](W04-UI.md)
- [W05 单页证据、制作摘要与精确文本选段核心](W05-CORE.md) / [提示词工作台与固定比较](W05-UI.md)
- [W06 标注、明确范围的计划、操作恢复与交接核心](W06-CORE.md)
- [W06 版本绑定意见、可核实保存与持久交接前端](W06-UI.md)
- [W07 候选与阶段核心](W07-CORE.md) / [比较采用前端与真实 Host](W07-UI.md) / [执行边界](W07-PLAN.md)
- [W09 内容操作核心](W09-CORE.md) / [执行边界](W09-PLAN.md)
- [W08 风格校准界面与真实效果](W08-UI.md) / [固定风格配方核心](W08-CORE.md) / [执行边界](W08-PLAN.md)
- [W10 运行台共享核心](W10-CORE.md) / [前端、恢复与持续浏览](W10-UI.md)
- [修订后的包顺序](../../specs/deck-master-workbench-v3/packages/README.md)
- [交接原件](handoff/HANDOFF.md) / [26 个输入的原始 manifest](handoff/manifest.json)
- [当前用户设计快照](design-snapshot/index.html) / [8 文件 SHA256](design-snapshot/sha256-manifest.json)
- [本轮新增故障探测](independent-probes.json) / [远端 main 复核](remote-main-check.json)

执行：W01 核心切片 → W02 → W03 → W04 → W05 → W06 → W07 → W01 完整压力补证 → W10 → W08 → W09 → W11 → W12。

先交可审查的共享核心 PR，合入 main 后前端接入。一次只激活一张卡；切片合入不等于全卡 AC 通过。W01-AC01 的 300×5×3 压力依赖 W02/W07 真实契约，必须后续由 W01 补齐，不能以 300 页基础采样代签。

真实 Host、浏览器、安装与发布分别记录；未进行默认入口切换、实际 HOME 迁移或生产发布。旧 214 测试/17 观察及设计原型回归不计入新 UI 验收。
