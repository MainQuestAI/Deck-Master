# 生成工作台 v3 执行索引

当前活动卡：**W04，缩略图与个人画廊状态核心切片进行中**。W03 核心 PR #45 与前端 PR #46 已合入 main，前端提交 `8eabda9…` 的 8 项 CI 全绿；当前基线 `f3c9b617b868748ea09765ff072858f563f65b8f`，分支 `codex/workbench-w04-core`。W03 保留系统目录弹窗的实机复核项，用户验收及 W12 安装验收尚未签收。

- [独立 Review：4 P1、3 P2](REVIEW.md)
- [外部原始复核与取舍](OUTSIDE-REVIEW.md)
- [执行状态及 87 条 AC](execution-state.json)
- [W01 实现提交、46 项回归、浏览器与性能证据](W01.md)
- [W02 恢复切片](W02.md) / [冻结请求、Attempt 与真实 Host 证据](W02-PROTOCOL.md) / [ContentPlan 与来源版本](W02-CONTENT-PLAN.md)
- [W03 独立入口、服务生命周期与个人草稿](W03-CORE.md) / [前端与真实浏览器验证](W03-UI.md)
- [W04 缩略图与个人画廊状态核心](W04-CORE.md)
- [修订后的包顺序](../../specs/deck-master-workbench-v3/packages/README.md)
- [交接原件](handoff/HANDOFF.md) / [26 个输入的原始 manifest](handoff/manifest.json)
- [当前用户设计快照](design-snapshot/index.html) / [8 文件 SHA256](design-snapshot/sha256-manifest.json)
- [本轮新增故障探测](independent-probes.json) / [远端 main 复核](remote-main-check.json)

执行：W01 核心切片 → W02 → W03 → W04 → W05 → W06 → W07 → W01 完整压力补证 → W10 → W08 → W09 → W11 → W12。

先交可审查的共享核心 PR，合入 main 后前端接入。一次只激活一张卡；切片合入不等于全卡 AC 通过。W01-AC01 的 300×5×3 压力依赖 W02/W07 真实契约，必须后续由 W01 补齐，不能以 300 页基础采样代签。

真实 Host、浏览器、安装与发布分别记录；未进行默认入口切换、实际 HOME 迁移或生产发布。旧 214 测试/17 观察及设计原型回归不计入新 UI 验收。
