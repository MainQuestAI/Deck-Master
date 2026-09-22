# T8 — M2 RC Hardening

## 1. 目标

在 M1 通过后推进正式开源 RC。

## 2. In Scope

1. production 外部依赖收口。
2. Review Desk 全量设计系统收口。
3. `SECURITY.md`
4. `scripts/preview/server.py`
5. `.github/ISSUE_TEMPLATE/`
6. `.github/PULL_REQUEST_TEMPLATE.md`
7. `CODEOWNERS`
8. `ROADMAP.md`
9. dependabot
10. release tree 正式安装、版本、回滚说明。

## 3. 必须实现

1. production 所需外部独立仓同步开源、替换为本仓能力，或明确移出正式候选范围。
2. POST 写操作 token 或 origin 校验。
3. 静默异常日志。
4. `rc-gate` browser smoke 进入 M2 Go。
5. GitHub 社区入口齐备。

## 4. 验证

```bash
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc-browser --benchmark-dir benchmarks --require-browser-smoke --force
```

## 5. 成功标准

release checklist 全绿，并且 release tree 可独立安装、验证、回滚。
