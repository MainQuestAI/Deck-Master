# A1 — Generation Result v2 & Session Migration

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A0 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立可信 generation handback，消除 ambiguous completed 和缺 artifact metadata 的问题。

## 3. In Scope

- `deck_generation_result.v2`。
- Generation session v2 状态。
- v1 normalize / migration。
- run/session/path/fingerprint/checksum validation。
- typed events。

## 4. Out of Scope

不实现 PPT Deck Pro Max 生产；不实现 build。

## 5. 必须实现

1. 增加 v2 validator。
2. Completed/partial 必须有真实 artifact。
3. 所有 artifact 必须 run-relative。
4. 导入时计算或校验 SHA。
5. v1 仅在安全 normalization 后接受。
6. Production 禁止 v1 placeholder。
7. 状态改为 `result_files_present → results_imported → quality_required / ready_for_build`。
8. 错误写 rejected import log。

## 6. 允许 / 预期修改路径

- `scripts/generation/handback.py`
- `scripts/generation/session.py`
- `scripts/validators/`
- `scripts/runtime/run_state_resolver.py`
- `docs/contracts/`
- `tests/test_generation_*`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- valid v2 import。
- run mismatch。
- session mismatch。
- absolute / traversal path。
- checksum mismatch。
- missing artifact。
- legacy valid migration。
- legacy placeholder rejection。
- stale fingerprint。

## 8. 成功标准

- v2 contract tests 100% pass。
- Production 无 artifact 不可完成。
- 旧 fixture 测试仍可通过显式 fixture profile。

## 9. 风险

迁移可能破坏现有 tests，必须增加 profile-aware compatibility。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
