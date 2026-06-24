# B3 — Page Package v1 & Producer Contract

## 1. 目标

建立 Producer 与 Builder 的正式页面级边界，隔离客户可见内容和内部制作信息。

## 2. In Scope

- Page Package schema。
- index / validator。
- generation result refs。
- PPT Deck Pro Max adapter contract。

## 3. Out of Scope

不构建最终文件；不重写 production intelligence 算法。

## 4. 允许修改路径

- `scripts/production/`
- `scripts/generation/`
- `docs/contracts/page-package.v1.schema.json`
- `tests/test_page_package.py`
- PPT Deck Pro Max bridge 对应分支

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. required pages 全覆盖。
2. customer_visible / internal_only 严格分区。
3. claim/evidence/asset bindings。
4. source fingerprint。
5. Generation Result 可引用 package。

## 6. 测试

- schema / content boundary。
- internal leakage negative tests。
- missing page / evidence。
- cross-repo bridge contract smoke。

## 7. 成功标准

- Builder 可只依赖 Page Package。

## 8. 依赖与并发

依赖 B1、B2。跨仓库变更需独立 PR 和固定 SHA。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
