# 06 — M2 RC Hardening Spec

## 1. 目标

M2 把 M1 技术预览推进到正式开源 RC，重点收口 production、设计系统、安全、release tree、社区入口和证据包。

## 2. M2 入口条件

1. M1 全部通过。
2. preview-gate 通过。
3. 公开 demo、README、Quick Start、repo hygiene、Review Desk 最小设计合规已完成。

## 3. M2 必须实现

1. production 所需外部独立仓同步开源、替换为本仓能力，或明确移出正式候选范围。
2. Review Desk 完成全量设计系统收口。
3. README 增加 Review Desk 截图或 GIF。
4. release tree 补正式安装、版本、回滚说明。
5. 本地 POST 写操作增加 token 或 origin 校验。
6. preview server 增加关键异常日志。
7. GitHub issue template、PR template、CODEOWNERS、ROADMAP、dependabot 齐备。
8. `rc-gate --skip-browser-smoke` 和 `rc-gate --require-browser-smoke` 通过。

## 4. 安全边界

`SECURITY.md` 必须说明：

1. 这是本地 localhost 工具。
2. 写操作需要 token 或 origin 校验。
3. 不承诺处理远程多租户威胁模型。
4. 安全报告方式和响应预期。

## 5. 验证命令

```bash
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc-browser --benchmark-dir benchmarks --require-browser-smoke --force
```

## 6. 成功标准

1. release checklist 全绿。
2. release tree 不暴露作者本机路径。
3. README 首屏能表达专业 Solution Deck 审查台价值。
4. 安全边界进入文档和测试。
