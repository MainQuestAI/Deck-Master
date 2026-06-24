# A2 — Workflow State Resolver

## 1. 目标

基于 Contract、Artifact、Handoff、Approval 推导全 Stage 状态，同时保留 Runtime Sub-stage。

## 2. In Scope

- Workflow State v1。
- Stage entry/exit validator。
- Fingerprint / stale propagation。
- Snapshot writer。

## 3. Out of Scope

不实现 Handoff mutation 和 Approval mutation。

## 4. 允许修改路径

- `scripts/workflow/`
- `scripts/runtime/run_state_resolver.py`
- `docs/contracts/workflow-state.v1.schema.json`
- `tests/test_workflow_state.py`
- `tests/test_stage_validation.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 9 个 Stage 状态可推导。
2. current skill stage 与 runtime stage 分开。
3. missing / invalid / stale artifact 分类。
4. 上游变化传播 stale。
5. Snapshot 可完全重建。

## 6. 测试

- empty/new/partial/completed/stale runs。
- upstream mutation stale propagation。
- corrupt handoff/approval ignored as invalid fact。
- deterministic resolver output。

## 7. 成功标准

- 同一 Run 重算结果稳定。
- 不再只按单文件存在判断完成。

## 8. 依赖与并发

依赖 A1。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
