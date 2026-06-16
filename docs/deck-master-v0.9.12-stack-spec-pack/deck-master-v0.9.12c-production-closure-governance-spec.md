# Deck Master v0.9.12c Spec - Production Closure & Governance

## 1. 目标

在 v0.9.12a/v0.9.12b 基础上，完成本轮业务目标的闭环：反馈事件、Review Cockpit readiness、quality blocking 接入、suite E2E smoke、release QA 和安全发布收口。

本 Stack 是业务闭环和发布治理，不再扩大 companion 深算法范围。

## 2. 非目标

- 不把 feedback 默认真实写入 PPT Library DB。
- 不实现完整 P3 Asset Intelligence。
- 不实现完整 P4 Quality Governance。
- 不实现 hosted/team mode。
- 不新增 remote package manager。

## 3. 修改边界

允许修改：

```text
scripts/deck_master.py
scripts/runtime/sourcing_import.py
scripts/runtime/metrics.py
scripts/feedback/*
scripts/preview/server.py
scripts/preview/static/index.html
scripts/preview/static/app.js
scripts/preview/static/style.css
scripts/review/readiness.py
skills/*/SKILL.md
docs/releases/*
docs/qa/*
tests/*feedback* / tests/*cockpit* / tests/*e2e* / tests/*release*
```

当前代码基线已确认 Review Cockpit 入口是 `scripts/preview/server.py` 和 `scripts/preview/static/*`，feedback 入口已有 `scripts/feedback/record_deal.py`，runtime import 入口已有 `scripts/runtime/sourcing_import.py`。不得新建平行 `scripts/web/review_cockpit/*` 或 `scripts/integrations/*` 目录；若 production closure 仍缺少 readiness 聚合能力，优先复用 `scripts/review/readiness.py`，再评估是否新增最小 runtime 模块。

## 4. Feedback Event Queue

### 4.1 Storage

新增：

```text
runs/<run_id>/external/ppt_library/library_feedback_events.jsonl
runs/<run_id>/imports/import_log.jsonl
```

事件 shape：

```json
{
  "schema_version": "deck_master_ppt_library_feedback_event.v1",
  "event_id": "fb_evt_001",
  "run_id": "customer-run",
  "timestamp": "2026-06-16T00:00:00Z",
  "source": "deck-master",
  "event_type": "page_source_approved",
  "page_task_id": "page_03",
  "beat_id": "beat_03_solution_map",
  "candidate_id": "cand_001",
  "canonical_slide_id": "canonical_xxx",
  "source_deck_id": "deck_xxx",
  "outcome": "approved_for_adapt",
  "notes": "Selected as source reference for adapted page.",
  "idempotency_key": "run:customer-run:page_03:cand_001:approved_for_adapt"
}
```

### 4.2 CLI

```bash
deck-master record-library-feedback --run-id <run_id> --outcome <value> [--dry-run]
deck-master record-library-feedback --run-id <run_id> --outcome <value> --apply
```

要求：

- 默认 dry-run / event queue。
- `--apply` 是 experimental 显式能力，不进入 v0.9.12c 必做验收。
- 如果实现 `--apply`，必须显式开启。
- `--apply` 前必须通过 `library-status`、schema validation、idempotency check。
- `--apply` 失败不得删除 event queue。
- 若 PPT Library 不支持 negative outcome，则记录 warning，不伪造成功。

## 5. Review Cockpit / Readiness Integration

Review Cockpit 或 equivalent status output 应显示：

- suite readiness。
- task capability readiness。
- imported library selections。
- generation handoff sessions。
- quality findings blocking/warning。
- feedback events pending/applied/failed。

若当前 Review Cockpit UI 未暴露这些数据，至少需要 CLI/manifest 层可读。

实现边界：

- 优先在现有 `scripts/preview/server.py` API 和 `scripts/preview/static/*` 前端中扩展。
- 如果 UI 改动风险过高，本 Stack 可先通过 CLI/JSON readiness 输出满足验收，再把完整 UI banner 留给后续小 PR。
- 不创建第二套 Review Cockpit。

## 6. Quality Blocking 接入

要求：

- PPT Quality Gate imported findings 中 severity=blocking 的 findings 应影响 delivery readiness。
- export/delivery reporting 前必须检查 blocking findings。
- override 必须显式记录 reason/operator/timestamp。
- 具体 export 阻断实现若当前仓库已有 gate engine，应复用；不要重写。

## 7. Import Log

所有 import 类命令必须写：

```json
{
  "schema_version": "deck_master_import_log.v1",
  "import_id": "imp_001",
  "run_id": "customer-run",
  "timestamp": "2026-06-16T00:00:00Z",
  "source_skill": "ppt-library",
  "source_artifact": "/absolute/path/selection.json",
  "artifact_sha256": "sha256...",
  "import_type": "library_selection",
  "status": "imported",
  "warnings": []
}
```

覆盖类型：

```text
library_selection
quality_findings
generation_result
render_result
feedback_event
```

## 8. E2E Suite Smoke

必须提供 temporary HOME smoke：

1. suite install。
2. setup-status --include-suite。
3. create or prepare test workspace。
4. create test run。
5. import fake PPT Library selection。
6. create generation handoff。
7. import fake generation result。
8. import fake quality findings。
9. record feedback event dry-run。
10. validate readiness/cockpit output。
11. export/delivery blocked when blocking finding exists。
12. override path works only with explicit reason。

真实机器检查只能运行 non-mutating status，不得改用户 workspace。

## 9. Release QA

新增或更新：

```text
docs/qa/v0.9.12-suite-runtime-qa.md
docs/releases/v0.9.12-release-notes.md
```

QA 必须记录：

- Stack A test summary。
- Stack B test summary。
- Stack C test summary。
- temporary HOME smoke。
- real-machine non-mutating status。
- known limitations。
- rollback notes。
- 若 `--apply` 未实现，QA 必须明确记录：feedback apply 是 experimental follow-up，本轮仅 event queue / dry-run。

## 10. 验收标准

- feedback 默认只写 event queue，不默认写外部 DB。
- `--apply` 如实现，必须显式开启且有 idempotency guard；如未实现，不影响 v0.9.12c 通过。
- Review Cockpit/readiness 可看到 suite、library、generation、quality、feedback 状态。
- blocking quality findings 会阻断 delivery readiness。
- 所有 import 命令写 import log。
- End-to-end suite smoke 通过。
- v0.9.11 production guards 保持有效。
- release notes 和 QA report 完整。

## 11. 给 Codex 的执行提示

```text
你正在开发 MainQuestAI/Deck-Master v0.9.12c：Production Closure & Governance。

前提：v0.9.12a/v0.9.12b 已完成。

目标：实现 feedback event queue、optional apply、Review Cockpit/readiness 集成、quality blocking、import log 统一和 E2E suite smoke。

禁止：
- feedback 不得默认真实写入 PPT Library DB。
- 不实现完整 P3 Asset Intelligence。
- 不重写 P4 Quality Governance。
- 不改 hosted/team mode。
- `--apply` 可跳过；如果实现，必须作为 experimental 显式能力。

完成后输出：
- 修改文件清单。
- 新增/修改 CLI。
- E2E smoke 命令和结果。
- release QA 文档。
- 已知限制和 rollback 方法。
```
