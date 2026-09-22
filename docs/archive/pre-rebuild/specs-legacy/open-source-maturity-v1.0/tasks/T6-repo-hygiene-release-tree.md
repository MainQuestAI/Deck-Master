# T6 — Repo Hygiene And Release Tree

## 1. 目标

清理公开入口会暴露的内部产物，并让 release tree 具备基础开源包装。

## 2. In Scope

1. `.gstack/qa-reports`
2. `.claude`
3. `.gbrain-source`
4. `.impeccable`
5. `docs/qa/`
6. `scripts/skills/installer.py`
7. release manifest

## 3. 必须实现

1. Git 不再跟踪 `.gstack/qa-reports`。
2. 必要 QA 证据迁入公开 docs 或 release artifact。
3. 公开入口文档无作者本机路径。
4. release tree 含 README、LICENSE、Known Limitations。
5. release manifest 默认不写入作者本机绝对路径。

## 4. 验证

```bash
git ls-files .gstack
rg -n "Users/|home/|gstack-autoplan|restore|internal-only|客户|售前" README.md docs docs/qa scripts/skills || true
```

## 5. 成功标准

外部用户看到的是产品仓库和必要证据，不会看到内部过程噪音。
