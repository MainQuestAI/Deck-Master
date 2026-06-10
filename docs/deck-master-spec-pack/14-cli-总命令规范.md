# Deck Master Spec Pack

## 19. Spec 14：CLI 总命令规范

### 19.1 Workspace

```bash
init-workspace
register-workspace
validate-workspace
```

### 19.2 Run lifecycle

```bash
start-conversation
build-brief
build-judgments
build-claim-map
build-claim-graph
plan
build-page-tasks
autoplan
resume
status
next-step
validate-run
```

### 19.3 Retrieval / sourcing

```bash
search-library
decide-sourcing
```

### 19.4 Build skill

```bash
create-generation-tasks
run-build-skill
ingest-build-artifact
```

### 19.5 Preview / review

```bash
build-preview
open-preview
review-page
replace-source
convert-to-generate
lock-source
```

### 19.6 Quality

```bash
quality-gate draft
quality-gate render --artifact <pptx> --expected-pages <n>
quality-gate delivery --artifact <pptx> --expected-pages <n> --forbidden <term>
```

### 19.7 Export / feedback

```bash
export
record-delivery-outcome
record-feedback
```

### 19.8 命令输出格式

所有 CLI 成功输出 JSON：

```json
{
  "run_id": "retail-conversation",
  "run_dir": "/abs/path/to/run",
  "status": "preview_ready",
  "next_step": "open_review_cockpit",
  "artifacts": ["preview_manifest.json"]
}
```

失败输出 stderr，但结构化错误必须写 event。

---
