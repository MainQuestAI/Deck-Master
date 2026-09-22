# B2 — Sourcing Plan v2

## 1. 目标

把每页来源、证据、权限、时效和生产决策固化为 Producer 的唯一来源输入。

## 2. In Scope

- schema/runtime migration。
- PPT Library adapter。
- per-page completeness。
- approval readiness。

## 3. Out of Scope

不写最终页正文；不修改 PPT Library 内核。

## 4. 允许修改路径

- `scripts/sourcing/`
- `scripts/tools/ppt_library_client.py`
- `docs/contracts/sourcing-plan.v2.schema.json`
- `tests/test_sourcing_plan_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 每个 page task 一条决定。
2. 允许六类 decision。
3. source authority/freshness/permission 字段。
4. 缺口显式。
5. v1 safe migration。

## 6. 测试

- 0/1/multiple candidates。
- permission blocked。
- stale evidence。
- incomplete page coverage。
- v1 migration。

## 7. 成功标准

- Producer 不再猜测来源决策。

## 8. 依赖与并发

依赖 A5，可与 B1 部分并行。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
