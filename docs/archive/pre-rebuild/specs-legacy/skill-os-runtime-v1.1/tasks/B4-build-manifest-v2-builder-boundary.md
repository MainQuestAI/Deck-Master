# B4 — Build Manifest v2 & Builder Boundary

## 1. 目标

让 Production Builder 只消费批准的 Page Package 白名单字段。

## 2. In Scope

- Build Manifest v2。
- Page Package projection。
- legacy preview adapter。
- PPT Master adapter contract。

## 3. Out of Scope

不重做 PPT Master 视觉内核。

## 4. 允许修改路径

- `scripts/runtime/build.py`
- `scripts/runtime/builder_backend.py`
- `scripts/build/`
- `docs/contracts/build-manifest.v2.schema.json`
- `tests/test_build_manifest_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. production direct preview input blocked。
2. whitelist projection。
3. package hash / asset hash。
4. backend contract version check。
5. legacy adapter 显式且重新 Review。

## 6. 测试

- internal field leakage。
- missing/changed package。
- backend v1/v2 compatibility。
- legacy adapter。
- source fingerprint。

## 7. 成功标准

- 客户 Artifact 中 internal-only 泄漏为 0。

## 8. 依赖与并发

依赖 B3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
