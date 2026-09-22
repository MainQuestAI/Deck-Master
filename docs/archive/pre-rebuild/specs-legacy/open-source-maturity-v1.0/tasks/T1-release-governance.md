# T1 — Release Governance

## 1. 目标

补齐开源治理文件、Apache-2.0 license、Technical Preview 发布口径和 release checklist。

## 2. In Scope

1. `LICENSE`
2. `CONTRIBUTING.md`
3. `SECURITY.md`
4. `CODE_OF_CONDUCT.md`
5. `THIRD_PARTY_NOTICES.md`
6. `CHANGELOG.md`
7. `docs/releases/2026-07-06-release-checklist.md`
8. README 首屏治理链接和 Status

## 3. Out Of Scope

1. preview-gate 实现。
2. Review Desk 视觉修复。
3. production backend 开源改造。

## 4. 必须实现

1. Apache-2.0 license。
2. DCO 贡献口径。
3. Best-effort Technical Preview 维护承诺。
4. preview / pre-release tag 语义。
5. M1/M2 Go 条件。

## 5. 验证

```bash
rg -n "Technical Preview|Apache-2.0|DCO|preview|pre-release|Best-effort" README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md docs/releases
```

## 6. 交付报告

必须列出新增治理文件、版本/tag 口径、仍需人工确认的 release 操作。
