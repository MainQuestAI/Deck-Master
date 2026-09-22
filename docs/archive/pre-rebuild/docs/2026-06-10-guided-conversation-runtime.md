# Deck Master Guided Conversation Runtime

Date: 2026-06-10
Status: IMPLEMENTED

## 结论

Deck Master 已新增“本地上下文 + 引导式对话 + 论点编译 + Draft Gate”的首版链路。

这条链路的目标是服务专业客户方案 Deck：用户先提供本地或已导出的资料，例如会议转写、项目摘要、历史方案说明；Deck Master 在一次 run 内引用这些资料，生成可追踪的上下文清单、对话会话、Deck brief、claim map、page tasks、preview manifest 和 Draft Gate 报告。

当前边界很明确：

- 只引用本地或已导出资料。
- 不实时拉取飞书。
- 不依赖 OpenViking 在线可用。
- 不建设新的长期思考库。
- 不追求一次性最终 PPTX。

## 新增入口

从本地上下文开始一次引导式 Deck run：

```bash
python3 scripts/deck_master.py start-conversation \
  --context-file examples/context/retail_meeting_transcript.txt \
  --industry retail \
  --run-id retail-conversation
```

编译 Deck brief：

```bash
python3 scripts/deck_master.py build-brief --run-id retail-conversation
```

编译 claim map：

```bash
python3 scripts/deck_master.py build-claim-map --run-id retail-conversation
```

继续跑到 Web Studio preview：

```bash
python3 scripts/deck_master.py autoplan \
  --run-id retail-conversation \
  --library-mode fixture
```

运行 Draft Gate：

```bash
python3 scripts/deck_master.py quality-gate \
  --run-id retail-conversation \
  draft
```

也可以用 `--run-dir` 指向任意 run 目录续跑。

## Runtime 产物

新增产物：

- `context_manifest.json`：记录本次 run 引用了哪些本地资料，包括路径、类型、摘要、hash 和来源 id。
- `conversation_session.json`：记录引导式对话模式、关键追问、上下文引用和已锁定判断。
- `deck_brief.json`：把上下文和对话整理成 Deck 目标、受众、业务目标、核心观点和边界。
- `claim_map.json`：记录核心论点、为什么重要、支撑逻辑、证据需求、证据引用和风险。
- `page_tasks.json`：将页面任务分成 `planning / retrieval / sourcing / generation` 四层，避免多阶段字段混在一起。
- `quality_reports/draft_gate.json`：检查业务目标、论点、页面主张和证据缺口。
- `quality_reports/draft_gate.md`：给人读的 Draft Gate 报告。

原有产物继续保留：

- `request.json`
- `events.jsonl`
- `narrative_plan.json`
- `library_results/selection.json`
- `sourcing_plan.json`
- `generation_tasks/index.json`
- `preview_manifest.json`
- `approved_queue.json`

## 当前能力

- 本地文本资料可以被纳入 run，并生成运行时引用清单。
- 引导式对话首版会生成默认追问，围绕受众、主论点、证据、历史资产和删减边界。
- Deck brief 会从上下文摘要和 request 中提取核心观点。
- Claim map 会判断是否存在可用证据引用。
- Planner 会继续生成 narrative plan，并同步生成分层 `page_tasks.json`。
- `autoplan --run-id` 可以从已有 conversation run 续跑到 preview。
- Draft Gate 会优先检查内容逻辑和证据链。

## 验证

```bash
uvx pytest
```

当前测试覆盖：

- 本地 context manifest。
- conversation session。
- deck brief。
- claim map。
- Draft Gate。
- 本地资料到 preview manifest 的端到端链路。
- 原有 brief autoplan、preview、sourcing、export、feedback 能力。

Smoke test：

```bash
tmp=$(mktemp -d)
python3 scripts/deck_master.py start-conversation --context-file examples/context/retail_meeting_transcript.txt --industry retail --runs-dir "$tmp" --run-id smoke
python3 scripts/deck_master.py build-brief --run-dir "$tmp/smoke"
python3 scripts/deck_master.py build-claim-map --run-dir "$tmp/smoke"
python3 scripts/deck_master.py autoplan --run-dir "$tmp/smoke" --library-mode fixture
python3 scripts/deck_master.py quality-gate --run-dir "$tmp/smoke" draft
rm -rf "$tmp"
```
