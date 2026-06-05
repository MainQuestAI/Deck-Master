# Slide Win-Rate Feedback MVP

Date: 2026-06-06
Status: MVP IMPLEMENTED

## 结论

本轮把 Slide 胜率追踪从规划项推进到本地可运行闭环：基于 `export_queue.py` 导出的页面队列，记录 Deal 的赢/输结果，并按 slide 来源统计使用次数、赢单次数、输单次数和胜率。

这先解决反馈数据的采集和统计。等 PPT Library 提供稳定 slide id 与 metadata 写回入口后，再把统计结果写回 PPT Library，用于搜索排序。

## 新增能力

- `scripts/feedback/record_deal.py record`：记录一次 Deal 结果。
- `scripts/feedback/record_deal.py summary`：统计 slide 使用与胜率。
- `examples/feedback/approved_queue.json`：样例审批队列。
- `tests/test_feedback.py`：覆盖记录、统计、无效 outcome 和空日志。

## 运行方式

记录结果：

```bash
python3 scripts/feedback/record_deal.py record examples/feedback/approved_queue.json --log feedback/deal_results.jsonl --deal-id retail-demo-001 --outcome won
```

查看统计：

```bash
python3 scripts/feedback/record_deal.py summary --log feedback/deal_results.jsonl
```

## 数据口径

- `won`：该 Deal 赢单，队列中的页面都获得一次赢单记录。
- `lost`：该 Deal 输单，队列中的页面都获得一次输单记录。
- `unknown`：结果未知，只计使用次数。
- `win_rate`：`wins / (wins + losses)`，未知结果不进入分母。

## 后续边界

- PPT Library 提供稳定 slide id 后，把当前 `slide_key` 替换为真实 slide id。
- PPT Library 提供 metadata 写回入口后，把本地统计写回搜索索引。
- Deck Master 后续可把胜率作为候选页排序因子之一。
