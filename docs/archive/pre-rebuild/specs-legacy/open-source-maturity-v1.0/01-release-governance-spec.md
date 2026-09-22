# 01 — Release Governance Spec

## 1. 目标

把 Deck Master 的开源治理、License、版本、维护承诺和 Technical Preview 发布口径固定下来。

## 2. 用户可见承诺

M1 对外只能表达：

1. Status：Technical Preview。
2. License：Apache-2.0。
3. Release：preview / pre-release tag 可用。
4. Stability：不承诺正式版，不发布 stable release。
5. Support：Best-effort technical preview。

## 3. 必须新增或修改

| 文件 | 要求 |
|---|---|
| `LICENSE` | Apache-2.0 全文 |
| `CONTRIBUTING.md` | 开发流程、测试要求、DCO 口径 |
| `SECURITY.md` | M1 报告方式、M2 安全边界计划 |
| `CODE_OF_CONDUCT.md` | 社区行为准则 |
| `THIRD_PARTY_NOTICES.md` | 依赖 license inventory 或生成方式 |
| `CHANGELOG.md` | preview 版本记录 |
| `pyproject.toml` | license、version、console script、dev extra |
| `skills/manifest.json` | suite/version/license 口径 |
| `product-capability-manifest.json` | capability/license 口径 |
| `docs/releases/2026-07-06-release-checklist.md` | D0-D7 决策记录和 release gate |

## 4. 版本规则

1. `pyproject.toml` 是包版本真相源。
2. `skills/manifest.json` 记录 suite version，并在 release checklist 写清与包版本的关系。
3. M1 tag 使用 preview / pre-release 语义，例如 `v0.9.14-preview.1` 或等价命名。
4. M1 tag 不能被 README、CHANGELOG 或 GitHub release 文案描述为 stable。

## 5. 测试与验证

至少验证：

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_skill_manifest.py tests/test_skill_doc_contract.py tests/test_skill_os_release_contract.py -q
```

补充静态检查：

```bash
rg -n "/Users/|/home/|placeholder|TODO: publish|stable release" README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md docs/releases
```

## 6. 成功标准

1. GitHub 能识别 Apache-2.0 license。
2. README 首屏能看到 Technical Preview、License、安装入口和限制说明。
3. release checklist 明确 M1 Go / No-Go。
4. 版本、tag、manifest、CHANGELOG 没有互相冲突。
