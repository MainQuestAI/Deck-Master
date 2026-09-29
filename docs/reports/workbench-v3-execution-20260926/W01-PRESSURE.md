# W01 完整压力补证

实现提交 `e21be437f033b112dc15779fe51e45d267cc6bf8`。W01-AC01 完整压力工程条件通过；用户验收仍未执行。W04 首屏、W10 持续运行指标不由本报告代签。

300 页 × 5 候选 × 3 Attempt：1,500 候选、4,500 Attempt，共 20,113 个对象、46,705,544 字节。候选图片为实际 960×540 PNG；种子 20260930。混合层继承 gallery 工厂：原图缺失、SVG、PPT 预览、旧版依赖及历史 revision。Attempt 包含 success 1500 / failure 900 / cancelled 1200 / unknown 900。正式契约、非空请求/观察/图片和对象 hash 均校验，代表性首尾页经过候选 list/show 读取。

这是一份明确标注的只读性能数据集：没有模型调用和原生 Host 证据，不代表可重放的生产调用历史；`host_reported` 观察明确写明合成来源。生产生成管线不使用此工厂。

| 指标 | 原实现 | 实现提交复测 |
|---|---:|---:|
| 5 次预热后 100 次 loopback summary p95 | 2196.92 ms | 206.16 ms |
| p50 | 1956.38 ms | 129.34 ms |
| 最大值 | 2247.92 ms | 226.45 ms |
| 冷读取（另计） | 1000.11 ms | 877.29 ms |
| 采样记录内完成的后台状态更新 | 81 | 5 |

门槛固定为 p95 ≤250ms，从 HTTP 客户端发起到 JSON 解析完成。后台线程连续调用真实 `service.task_start/task_cancel`，每次完成后间隔 250ms；每次操作包括 Store 提交、schema 校验及正常 pending task 投影。原实现和复测采用同一数据集与更新规则，耗时降低导致采样时段较短，因此完成的后台操作数较少。原始样本记录每次读取的 revision 与已完成更新数；线程未发生异常。

瓶颈：原缓存容量 2048，小于摘要工作集 2498，三轮顺序读取的缓存命中均为零。仅增大容量的独立诊断把无后台负载的单次读取从约 983ms 降到约 204ms。最终实现将缓存上限设为 4096；按已验证的对象路径语法检查各级目录和文件，省去重复 realpath；摘要不复制完整任务指令/结果，并一次建立页面任务索引。每次读仍检查路径、符号链接、文件 inode/size/mtime/ctime；缓存未命中仍校验 JSON、hash 和 schema，跨项目键含规范根路径。非 POSIX 保留原 Store 路径解析。

独立观测摘要未读取 candidate / generation_request / generation_attempt / tool_observation 正文；读取对象统计和缓存指标见 after.json。阶段、任务与历史返回保持原协议。

验证：相关 pytest 60 passed（workbench_reads / web / candidates / package_boundary），包含新增热缓存后对象、bucket、objects 目录及图片符号链接拒绝、跨页任务投影隔离。Ruff 与 git diff --check 通过。环境详情含 macOS、硬件型号、物理内存和 Python 版本记录在原始结果；此项为 HTTP 测量，browser/viewport 不适用。

- [完整数据 manifest](w01/pressure/manifest.json)
- [原实现 100 次样本](w01/pressure/before.json)
- [实现提交 100 次样本](w01/pressure/after.json)

复现：

```sh
PYTHONPATH=src python examples/workbench/w01_pressure.py --out /tmp/new-pressure-proof
# 复用明确标注的同一压力项目；跳过已完成背景任务
PYTHONPATH=src python examples/workbench/w01_pressure.py --out /tmp/new-measurement --existing /tmp/new-pressure-proof
```

输出目录必须新建。项目保留在本地供 W04/W10 后续测量，仓库只提交工厂和 JSON 证据。读取性能通过不等于真实 Host、用户验收、安装或发布通过。
