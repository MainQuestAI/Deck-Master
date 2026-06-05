# External Tool Adapters

Date: 2026-06-06
Status: MVP IMPLEMENTED

## 结论

本轮补齐 Deck Master 与两个外部项目的薄适配层：

- PPT Library：把 `ppt-lib search --output json` 或 `ppt-lib select-slides` 的 JSON 结果转换成 Deck Master 组装计划。
- PPT Deck Pro Max：把项目里的页面截图产物转换成 Deck Master 组装计划。

Deck Master 不直接接管两个外部项目的运行，只消费它们的稳定产物。这样边界清晰，后续两个项目升级时只需要保持输出契约。

## 新增能力

- `scripts/adapters/ppt_library_to_plan.py`
- `scripts/adapters/deck_pro_max_to_plan.py`
- `examples/adapters/ppt_library_search.json`
- `tests/test_adapters.py`

## 运行方式

从 PPT Library 搜索结果生成 plan：

```bash
python3 scripts/adapters/ppt_library_to_plan.py ppt-library-search.json --output runs/library-plan.json --run-id retail-library-run --title "Retail Library Candidates"
```

从 PPT Deck Pro Max 项目截图生成 plan：

```bash
python3 scripts/adapters/deck_pro_max_to_plan.py /path/to/deck-pro-max-project --output runs/generated-plan.json --run-id retail-generated-run --title "Generated Pages"
```

生成 plan 后继续走同一条链路：

```bash
python3 scripts/orchestrate/build_run.py runs/library-plan.json runs/retail-library-run --force
python3 scripts/preview/server.py runs/retail-library-run
```

## 边界

- 适配器不负责执行搜索、生成或截图。
- 适配器只做字段映射和契约转换。
- 缺失截图会进入 manifest，预览 UI 会显示资源缺失。
