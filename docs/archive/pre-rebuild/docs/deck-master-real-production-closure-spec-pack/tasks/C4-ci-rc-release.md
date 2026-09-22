# C4 — CI, RC Gate & Release Artifact

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1-C3 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把本轮验收固化为 CI/RC gate，并生成发行物。

## 3. In Scope

- CI jobs。
- contract tests。
- fixture E2E。
- package smoke。
- browser smoke。
- RC report。
- archive/checksum。

## 4. Out of Scope

CI 不运行私有真实客户资料。

## 5. 必须实现

1. CI 增加 schema、artifact validator、release tree smoke。
2. Fixture E2E。
3. Browser smoke。
4. Release archive。
5. SHA256SUMS。
6. RC report command。
7. Real benchmark 结果以外部 evidence import。

## 6. 允许 / 预期修改路径

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `scripts/release/`
- `scripts/benchmark/report.py`
- `tests/`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- Linux CI。
- temp HOME。
- release archive unpack。
- moved repo test。
- browser smoke。
- RC blocked/pass fixtures。

## 8. 成功标准

- Main branch CI 稳定。
- Release artifact 可下载和验证。
- RC gate 缺任何证据都 blocked。

## 9. 风险

Playwright/LibreOffice 在 CI 的可用性可能不稳定，应分 required deterministic job 与 platform smoke。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
