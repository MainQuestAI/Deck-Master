# B1 — Artifact Validation

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack A complete |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立统一 artifact truth validator。

## 3. In Scope

- magic bytes。
- MIME。
- package parse。
- checksum。
- path safety。
- placeholder detection。
- stale detection。
- validation report。

## 4. Out of Scope

不判断商业质量和视觉审美。

## 5. 必须实现

1. 实现 PNG/JPEG/PDF/PPTX/HTML/SVG validator。
2. PPTX 检查 ZIP 核心文件。
3. HTML 检查 page container 和数量。
4. placeholder token / tiny file 规则。
5. checksum mismatch 阻断。
6. 输出 `artifact_validation_report.v1`。
7. Production invalid 一律 P0。

## 6. 允许 / 预期修改路径

- `scripts/validation/artifacts.py`（新增）
- `scripts/validation/signatures.py`（新增）
- `scripts/validators/`
- `tests/test_artifact_validation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

覆盖所有格式的 valid/corrupt/fake/empty/path traversal/checksum mismatch/stale。

## 8. 成功标准

- 伪后缀 100% 检出。
- parse error 不被吞掉。
- validator 可被 generation、render、delivery 复用。

## 9. 风险

过严的最小尺寸规则可能误伤，规则应 profile-aware。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
