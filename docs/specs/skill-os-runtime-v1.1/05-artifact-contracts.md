# Artifact Contracts

## 1. Run 目录新增结构

```text
<run>/
  workflow/
    workflow_state.json
    current_handoff.json
    handoff_index.json
    handoffs/
      <handoff_id>.json
    approval_log.jsonl
    decision_log.jsonl
    preauthorization.json          # optional
    bootstrap_report.json          # legacy only
    evidence/
      <stage_id>/
  sourcing_plan.v2.json
  page_packages/
    index.json
    <page_id>.json
  build/
    build_manifest.v2.json
```

## 2. `deck_skill_handoff.v1`

核心字段：

- handoff identity；
- from / to Stage；
- contract version；
- status；
- input / output artifact refs 与 hashes；
- stage output fingerprint；
- exit validation；
- decisions；
- unresolved warnings；
- approval policy；
- accepted/rejected metadata；
- stale / superseded metadata。

## 3. `deck_workflow_state.v1`

这是派生快照，包含：

- current Skill Stage；
- Runtime Sub-stage；
- 9 个 Stage 的状态；
- completed / stale stages；
- current Handoff；
- Approval summary；
- missing / invalid / stale artifacts；
- next Skill；
- allowed / blocked actions；
- source fingerprint；
- resolver version。

## 4. `deck_stage_approval.v1`

Approval Log 每行一条记录。状态变更使用新记录，不覆盖旧行。

必须绑定：

- approval id；
- handoff id；
- transition；
- stage output fingerprint；
- bound artifact hashes；
- actor / role；
- decision；
- reason；
- created / decided / expires；
- preauthorization reference（如有）。

## 5. `deck_decision_record.v1`

记录：

- question id / category；
- answer；
- actor；
- source type；
- stage；
- required / assumption allowed；
- evidence refs；
- input fingerprint；
- created at。

## 6. `deck_sourcing_plan.v2`

每个 Page Task 必须有一条决定：

```text
reuse
adapt
generate
evidence
manual
blocked
```

每条决定至少包含：

- page / task identity；
- claim / evidence need；
- selected source candidates；
- source authority 与 freshness；
- reuse permission / usage constraint；
- asset role；
- missing evidence；
- production budget class；
- decision reason / confidence；
- approval readiness。

Sourcing Plan 不得包含最终客户页正文。

## 7. `deck_page_package.v1`

### 7.1 允许 Builder 读取

```text
customer_visible
audience_context
visual_spec
asset_bindings
citations
style_refs
build_requirements
```

### 7.2 Builder 禁止读取到客户文件

```text
internal_only
production_rationale
agent_instructions
unresolved_questions
review_conversation
private_source_excerpt
```

### 7.3 最小结构

- identity / order；
- customer-visible title / subtitle / body blocks / labels / footnotes；
- speaker notes（独立）；
- visual composition；
- approved assets；
- claim / evidence bindings；
- provenance；
- internal-only notes；
- quality intent；
- build requirements；
- source fingerprint。

## 8. `deck_build_manifest.v2`

必须引用 `page_package`，而不是直接引用任意 Preview 字段。

每页记录：

- page package path / hash；
- page order；
- customer payload hash；
- approved asset hashes；
- target output modes；
- editability target；
- style lock；
- backend requirement。

## 9. Legacy Adapter

旧 `preview_manifest` 到 `page_package` 的转换必须：

- 显式调用；
- 写 `legacy_imported=true`；
- 不创造缺失正文或证据；
- 缺少客户可见字段时阻断；
- 生成 migration report；
- 重新进入 Review。
