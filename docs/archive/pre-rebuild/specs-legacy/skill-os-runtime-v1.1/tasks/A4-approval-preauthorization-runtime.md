# A4 — Approval & Preauthorization Runtime

## 1. 目标

建立绑定 Handoff、Transition 和 Artifact Fingerprint 的审批与显式预授权。

## 2. In Scope

- Approval log。
- accept / reject / revoke。
- preauthorization。
- stale approval。
- non-bypassable policy。

## 3. Out of Scope

不实现 UI。

## 4. 允许修改路径

- `scripts/workflow/approval.py`
- `scripts/workflow/policy.py`
- `docs/contracts/stage-approval.v1.schema.json`
- `docs/contracts/workflow-policy.v1.schema.json`
- `tests/test_workflow_approval.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 高影响 Transition 缺审批时阻断。
2. final export 不可预授权。
3. approval 绑定 hashes。
4. expiry/revoke/stale 生效。
5. reject 携带 repair owner。

## 6. 测试

- all transition policies。
- expired / revoked / wrong fingerprint。
- attempted final export preauth。
- duplicate decisions。

## 7. 成功标准

- 不存在无绑定 Approval。
- final export 绕过率 0。

## 8. 依赖与并发

依赖 A3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
