# 性能验收：最终产品冻结 05b0d875

2026-10-04，最终产品源码 `05b0d875d2cc890966ab10d730bf62d072ae871b`。完成后复核 `src/`、`skills/`、`pyproject.toml`、`examples/` 与冻结提交无差异。源码检验后新增的文档与行为测试不改变本次运行产品。

## 结果

显式合成负载为 300 页 × 5 个候选 × 3 次 Attempt，即 1,500 候选、4,500 Attempt。真实 Chromium 运行正式门禁并正常退出（exit 0）；不是 smoke。

| 验收项 | 实测 | 门槛 | 结论 |
|---|---:|---:|---|
| 暖摘要 | 100 次，p95 62.759ms；p50 43.881ms；max 73.636ms | 至少 100 次，p95 ≤250ms | 通过 |
| 长跑 | 1200.003s；120 个十秒交互槽采样 | 完整 1,200s | 通过 |
| 中段内存 | 300–600s，30 样本，中位数 19.444MiB | 至少 20 样本 | 通过 |
| 末段内存 | 900–1,200s，30 样本，中位数 19.849MiB | 至少 20 样本 | 通过 |
| 内存增长 | 2.083% | ≤20% | 通过 |
| 图像池峰值 | 网络 / 解码 / 缩略图 / 大图 = 6 / 2 / 60 / 3 | 6 / 2 / 60 / 4 | 通过 |
| 浏览器错误 | pageerror / console error 均无 | 无错误 | 通过 |

首个冷摘要 2005.246ms 单独保留，不进入暖摘要 p95，不用它代替“真实 30 页首屏 ≤2s”证据。30 页首屏与真实业务运行由单独业务/浏览器验收记录负责。

## 压力路径与方法

在既有画廊滚动、原图/SVG 切换、单页阅读缩放、候选分组/切换、总览对象定位路径上增加以下行为，每条 10 轮：

- 共享比较画布 100%、放大、归一化平移、适应窗口。
- 历史分页及全部记录切换（fixture 有 45 次明确的合成产物元数据历史）。
- 外部截图参考及已完成分析规则读取，包含最终版本的 hydration 与已保存任务/规范目录读取。
- 视觉拆解图展开、实际图像加载及离开后释放。

API 读取事实包括 history 50 次、styles/references 10 次、styles 20 次、tasks 107 次。背景仅领取/取消工厂预分配的合成任务，60 次状态变更，不派发真实制作。浏览器 POST 仅 `gallery` 与 `ui-state`，未发生候选采用、生图或继续制作请求。

内存取 Chromium `Performance.getMetrics` 的 JSHeapUsedSize，每个十秒交互槽后采样；比较固定时间窗中位数。未强制 GC、清缓存、重载页面或改门槛。环境：Chromium 153.0.8010.12、macOS-27.0-arm64-arm-64bit、Python 3.12.12、1440×900。

## 证据与边界

仓库外证据目录：`Deck-Master-private/webui-usability-20261004/evidence/pressure-usability-qualifying-05b0d87/`。保留 `checks.json`、`warm-summary.json`（全部 100 次样本）、`samples.jsonl`（120 次浏览器样本）、`local-only.har` 和 `final-window.png`。工厂目录为同级 `pressure-fixture-20261004/`，manifest 与 usability-fixture 明确记录 synthetic、model_calls=0、native_host_evidence=false。

该门禁证明真实浏览器在显式合成规模下的性能与资源边界。截图分析结果、历史变更与背景任务均明确为合成 fixture，不是实际 Host 分析、真实 30 页修改、跨 origin 恢复或用户视觉认可的替代证据。独立图标局部比较压力未在本例启用；共享候选比较已启用。

## 前序中断全部保留

以下正式长跑因独立复审发现产品缺陷、冻结源码被替代而终止；各目录保留 interruption.json 和原始已跑事实，不是性能阈值失败，不计为通过。

| 旧产品冻结 | 已完成事实 | 处理 |
|---|---|---|
| `ece47b3` | 240.86s / 25 样本 | nonqualifying、source_superseded；新产品缺陷修复后重新冻结 |
| `230ffd4` | 430.37s / 44 样本 | nonqualifying、source_superseded；新产品缺陷修复后重新冻结 |
| `88da633` | 941.17s / 95 样本 | nonqualifying、source_superseded；新产品缺陷修复后重新冻结 |

另保留 140 秒 smoke `pressure-usability-smoke-20261004/`，它从开始即 nonqualifying。只有本报告的最终 05b0d875 完整运行用于关闭正式门禁。
