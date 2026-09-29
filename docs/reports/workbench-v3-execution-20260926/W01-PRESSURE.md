# W01 完整压力补证

状态：执行中，尚无完整压力通过结论。基线 `9e6b6e1b804eea7b843f716165fbde2ce04a72be`，分支 `codex/workbench-w01-pressure`。

固定条件沿用 ENGINEERING-SPEC §6：300 页 × 5 候选 × 3 Attempt，混合层历史及成功/失败/取消/unknown，5 次预热后 100 次 loopback summary，从客户端发起到 JSON 解析完成，后台真实任务状态写入同时运行，p95 ≤250ms。摘要不得展开候选/Attempt 正文。先测原实现，再依据瓶颈修改。

数据仅作读取性能合成项目，正式 schema、实际非空 PNG/请求/记录与可核对 hash。`host_reported` 明确写明合成数据；没有模型调用、真实工具回执或可执行生成历史声明。生产生成管线不调用此工厂。保留真实用户项目、HOME、安装和旧入口不变。

脚本：`examples/workbench/w01_pressure.py`。输出目录必须新建，包含项目、manifest、后台操作和原始延迟样本。W04 首屏和 W10 持续运行后续复用同一 manifest；本卡不提前宣称这些指标通过。
