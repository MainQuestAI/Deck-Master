# Deck Master Demand-to-Preview AutoPlan

Date: 2026-06-06
Status: IMPLEMENTED

## 结论

Deck Master 已从“读取现成组装计划并预览”推进到“从用户需求自动生成可审查 Deck 草案”。

当前入口可以从 brief 创建 run，自动生成叙事计划、调用 PPT Library 或 fixture 候选、判断每页来源、创建 PPT Deck Pro Max 生成任务包，并生成 `preview_manifest.json` 交给 Web UI 审批。

## 新增入口

只做规划：

```bash
python3 scripts/deck_master.py plan \
  --brief "零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送" \
  --industry retail
```

一口气跑到预览：

```bash
python3 scripts/deck_master.py autoplan \
  --brief-file examples/briefs/retail_digital_transformation.txt \
  --industry retail \
  --library-mode fixture
```

打开预览：

```bash
python3 scripts/preview/server.py runs/<run_id>
```

导出审批队列：

```bash
python3 scripts/deck_master.py export --run-dir runs/<run_id>
```

## Runtime 产物

每个 run 会形成以下核心文件：

- `request.json`：用户需求入口。
- `narrative_plan.json`：自动规划的页面结构。
- `library_results/selection.json`：PPT Library 或 fixture 候选结果。
- `sourcing_plan.json`：每页的 `reuse`、`adapt`、`generate`、`manual_placeholder` 决策。
- `generation_tasks/index.json`：需要交给 PPT Deck Pro Max 的生成任务。
- `orchestration_plan.json`：转换给现有 preview 构建器的页面计划。
- `preview_manifest.json`：Web UI 审批状态源。
- `events.jsonl`：运行轨迹。

## 已实现边界

- `auto` 模式会优先尝试真实 `ppt-lib`，不可用时降级到 fixture 候选，保证仍能生成可审查草案。
- 第一版先创建 PPT Deck Pro Max 任务包和项目目录，不强制自动跑完整生成流水线。
- Preview UI 已展示来源决策、理由、候选、风险和生成任务。
- 现有 `build_run.py` 增加 `--preserve-existing`，可以在同一个 run 目录中刷新预览，不清掉前序规划产物。

## 验证

```bash
python3 -m unittest discover -s tests
python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-smoke-runs --run-id smoke-retail --force
python3 scripts/deck_master.py export --run-dir /tmp/deck-master-smoke-runs/smoke-retail
```

当前测试覆盖：运行时状态、brief 入口、叙事规划、PPT Library 客户端、来源决策、生成任务、端到端 autoplan、原 preview/adapters/feedback/orchestration 能力。
