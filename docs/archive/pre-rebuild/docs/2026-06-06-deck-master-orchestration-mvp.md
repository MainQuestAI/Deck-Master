# Deck Master Orchestration MVP

Date: 2026-06-06
Status: MVP IMPLEMENTED

## 结论

本轮补齐 Deck Master 编排层的最小闭环：用一份组装计划 JSON 生成 `runs/<run_id>/preview_manifest.json`，把外部页面资产接到 `links/`，再交给 Web 预览 UI 审查。用户确认后，可以导出下一步 PPTX 生成或人工组装要用的页面队列。

这一步先解决运行时状态和审批流，不直接调用 PPT Library 或 PPT Deck Pro Max。真实工具接入后，只要输出同样的计划字段，就能进入同一条预览与审批链路。

## 新增能力

- `scripts/orchestrate/build_run.py`：从组装计划生成可预览 run 目录。
- `scripts/orchestrate/export_queue.py`：从已审查 manifest 导出页面队列。
- `examples/orchestration-plan/deck_plan.json`：样例组装计划。
- `tests/test_orchestration.py`：覆盖 run 生成、软链接、队列导出和无效决策。

## 运行方式

生成预览 run：

```bash
python3 scripts/orchestrate/build_run.py examples/orchestration-plan/deck_plan.json runs/sample-orchestrated-run --force
```

打开预览 UI：

```bash
python3 scripts/preview/server.py runs/sample-orchestrated-run
```

导出确认队列：

```bash
python3 scripts/orchestrate/export_queue.py runs/sample-orchestrated-run --decision approved
```

## Runtime-first 对齐

- **状态存储**：`runs/<run_id>/preview_manifest.json`
- **恢复方式**：重新启动预览服务读取同一个 run 目录
- **工具结果回写**：PPT Library 和 PPT Deck Pro Max 后续写入组装计划或 manifest
- **人工审批点**：Web UI 写回 `decision` 和 `notes`
- **错误展示**：缺失资产保留 manifest 记录，UI 显示 `asset_exists=false`
- **执行轨迹**：manifest 保存来源类型、来源路径、叙事角色、理由和置信度
- **评测闭环**：`export_queue.py` 输出确认页队列，后续可统计保留率、替换率和来源命中率
- **版本治理**：每次组装使用独立 `run_id`

## 后续边界

- 真实 PPT Library 接入：把搜索 top-k 结果转换为组装计划页面。
- 真实 PPT Deck Pro Max 接入：把生成页预览图和项目路径写入组装计划。
- 胜率追踪：在导出队列基础上追加 Deal 结果记录，再写回 PPT Library 的 slide metadata。
