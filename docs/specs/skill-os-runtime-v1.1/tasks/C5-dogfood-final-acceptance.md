# C5 — Dogfood & Final Acceptance

## 1. 目标

用真实可脱敏的项目流程证明 Skill OS 解决了交接和确认问题。

## 2. In Scope

- 新 Run。
- Legacy Run bootstrap。
- Quality repair loop。
- user confirmation usability。
- evidence pack。

## 3. Out of Scope

不提交私有客户原文。

## 4. 允许修改路径

- `docs/qa/skill-os/`
- local-only run evidence
- sanitized acceptance summaries

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 新 Run 走完整 9 Stage。
2. 至少 3 个高影响 approval。
3. final export approval 绑定 artifact hash。
4. legacy bootstrap。
5. repair return path。
6. Review Desk 使用记录。

## 6. 测试

- acceptance matrix。
- stage consistency。
- stale mutation。
- approval invalidation。
- export blocking。

## 7. 成功标准

- 所有 Master Spec 量化指标达到。
- 无未登记 P0。

## 8. 依赖与并发

最终任务，依赖 C4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
