# W10 运行台与恢复前端

共享核心 PR #56 已先合入 main `45e645e7dc6b8f537d852343fae48a77bd98ca49`。前端初始实现 `703ec7349c6983548d08c07b0093026fc7f5d2b1`，统一可见性刷新后的源码提交 `7036f8e962f33f78a90fcc5b5ea1f506e47d3010`。完整持续浏览复测已通过，前端 [PR #57](https://github.com/MainQuestAI/Deck-Master/pull/57) 已合入 main `c17ba512db3efb4196b0e88dcab2d604eb23b053`，最终 head `d18b872d3ef3b88b93f98ac54712121b5875ffa3` 的 8 项 CI 全通过；用户验收未代签。

## 行为

运行记录每页最多 30 项，按修改组、执行状态和“需我处理”筛选。正常 running 不成为人的待办；真实接手时间与执行标识来自 Task。旧记录缺时间时写明未记录，不以最后更新时间代替。任务详情关联原请求、Attempt、额度、结果与作用页；修改交接保留原要求和复制提示。只将非候选结果标为已读，候选仍须明确决定。

当前执行状态单独刷新，页面与候选比较保持固定阅读版本。翻到后续任务页时固定任务版本，背景返回不会重排已读列表。个人记录保存筛选、页码、版本、已读标记和取消待核实标记；项目 ACK 后可跨端口恢复，未 ACK 的 origin 副本仍走既有手动导入机制。

取消先保存待核实标记，再请求原 Task；断线后不会自动再次取消或派发。用户可核实同一任务，再明确请求取消。单次取消发送中按钮禁用；只有读取 Task 终态才清除标记。30 分钟提示核实，不自动继续、重新分配额度或调用模型。

摘要统一活动 3 秒、闲置 15 秒、隐藏暂停、focus 立即读取、失败退避至 30 秒；焦点连续触发仍最多一个轮询请求在途。页面从浏览器缓存返回时旧请求不能更新新一代状态。单页、候选比较与修改交接订阅同一刷新入口。候选集合按 30 条渲染，跨页保留选择，背景版本未变时不反复拉取整组候选。

## 已完成的验证

- [主流程浏览器](w10/ui/browser-checks.json) 13 项通过，覆盖分页快照、跨页选择、正常运行待办区分、取消未知恢复与明确重试、1280/1440 宽度及零浏览器 JS 错误。并行重载曾超出默认 5 秒断言窗口；改为 15 秒后通过，该等待仅为功能测试，不计作首屏性能证据。
- 70 项相关 pytest 已通过，包含核心运行投影、journal、候选及新轮询生命周期故障测试；此前核心 PR #56 有独立完整 rebuild 回归。统一刷新后的源码又通过轮询与包边界 5 项检查。
- [计时器/可见性/focus/bfcache 故障注入](w10/ui/poll-lifecycle.json) 10 项通过。测试曾发现恢复时双计时器，已修复并保留回归。
- [浏览器轮询接入](w10/ui/polling-checks.json) 6 项通过。隐藏状态由明确注入的 `document.hidden` 与真实 DOM 事件提供，未冒充 macOS 窗口最小化验收；实际单页和运行台不再发摘要请求，恢复立即读取，延迟响应下 focus 不重叠。
- [跨 origin 恢复](w10/ui/recovery-checks.json) 5 项通过。真实 journal ACK 后新端口/空浏览器存储恢复页码与取消待核实；31 分钟仅为明确的时钟故障注入，不冒充实际等待。
- [局部损坏与空状态](w10/ui/error-checks.json) 3 项通过。只在可丢弃合成项目中暂时损坏 Task，并恢复原字节；其它记录保留，错误含对象、原因、动作和离线 docs_ref。空 Task 列表提供内容和画廊入口。
- W07 [主流程 15 项](w10/ui/w07-regression.json)、[边界 11 项](w10/ui/w07-edges-regression.json)、W06 [主流程 23 项](w10/ui/w06-regression.json)/[边界 14 项](w10/ui/w06-edges-regression.json)、W05 [15 项](w10/ui/w05-regression.json)通过。都属于实际服务与 Chromium 的合成机制验证。
- [wheel 资源核对](w10/ui/wheel-assets.json)：29 个前端文件与固定源码提交逐字节一致，隔离构建，未安装到实际 HOME。
- 故障重载和断开读取时，现有服务端会记录 BrokenPipe；浏览器未出现 JS 异常，已存 Task/业务操作不因此回滚。该日志现象不计作模型失败，也没有被隐藏或伪造为干净日志。

## 真实 Host 补证

本轮真实原生 ImageGen 一次，冻结提示词/固定参考/返回图字节匹配。真实 Codex Host 在两页项目中交错返回 auto SVG 与 trial SVG；固定候选比较不漂移，浏览器采用第一页候选后第二页完整记录不变。真实接手时间与当前 turn 身份可反查。[完整补证](W07-UI.md#2026-09-30-真实交错补证)。

另一个当前 Host SVG 任务取消后提交晚到结果，CLI 返回 5，取消状态保留且 pages/candidates/outputs 不变；没有新增图像调用。[原始检查](w07/real-host-interleaving/late-result-checks.json)。这是实际 Host 的恢复行为，页面业务事实仍是合成演示，非客户验收或专业视觉审查。

## 完整压力的首次失败与诊断

固定 W01 300 页 × 5 候选 × 3 Attempt manifest，1440×900 Chromium，每 10 秒切层/滚动/开页/切候选/返回，并对既有压力后台任务做真实 start/cancel。首轮完整 1,200 秒，[30+30 个窗口样本](w10/pressure/first-run-samples.jsonl)中位数从 62,288,832 到 134,414,188 bytes，增长 115.79%，超过 20% 门槛。[首次结果](w10/pressure/first-run-checks.json)原样保留，不记通过。图片边界 6/2/60/4 全程满足，无生成/采用/continue 写入。

独立诊断快照发现旧 gallery viewport 与 candidate row 被 `GC roots → Global handles → DevTools console` 直接持有，[保留链](w10/pressure/dom-retaining-paths.txt)。页面全局监听数量没有随切换增加。清 console entries 未解除这些调试句柄；改为返回布尔值的同步等待并释放等待句柄后，相同源码、相同夹具在更多页面循环中不再持续累积。对照的 [DOM 等待样本](w10/pressure/dom-waits-samples.jsonl)与[布尔等待样本](w10/pressure/boolean-waits-samples.jsonl)保留；这些为约 90 秒诊断，不能替代 20 分钟验收。

第二次完整测量从开始就使用布尔等待；不清 console、不清应用缓存、不重载页面、不主动 GC。仍使用 [300,600) 与 [900,1200] 秒窗口、每个窗口至少 20 个样本、增幅 ≤20% 的同一门槛。[完整结果](w10/pressure/checks.json)：1,200.002 秒、120 个原始采样，中段/末段各 30 个样本，中位数 8,515,600 → 8,692,088 bytes，增长 **2.07%**，通过 ≤20% 门槛。[原始采样](w10/pressure/samples.jsonl)保留。60 次真实后台 start/cancel 更新；图片并发/缓存 6/2/60/4 全程满足，浏览器 JS 错误 0，前端仅写 gallery/ui-state，未发起生成、采用或 continue。[硬件](w10/ui/host-environment.json)：Apple M5 Pro、64 GiB；Chromium/Python/macOS 版本见结果 JSON。

## 复现

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w10_browser.py --out /tmp/new-w10-browser
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w10_browser_recovery.py --out /tmp/new-w10-recovery-browser
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w10_browser_polling.py --out /tmp/new-w10-polling-browser
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w10_browser_errors.py --out /tmp/new-w10-error-browser
node examples/workbench/w10_poll_lifecycle.mjs
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w10_pressure.py --fixture /tmp/existing-w01-fixture --out /tmp/new-w10-pressure
```

压力命令默认完整 20 分钟；`--smoke` 仅为 60 秒冒烟且不会通过完整门槛。所有输出目录必须不存在。浏览器 trace 与含本机路径的原始 CLI 回包保留在本机临时证据目录，不提交原始业务运行目录。
