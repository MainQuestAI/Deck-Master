# 02 — First Run Demo And Docs Spec

## 1. 目标

让外部用户在 10 分钟内完成首跑：安装、生成 fixture demo、打开 Review Desk、完成一次审批、看到 readiness/export。

## 2. 首跑故事线

```text
clone repo
-> create venv
-> pip install -e ".[dev]"
-> run fixture autoplan
-> open Review Desk
-> approve one page
-> view readiness/export
-> run preview-gate
```

## 3. README 结构

README 首屏建议按以下顺序组织：

1. What：Deck Master 是什么。
2. Status：Technical Preview。
3. Who：适合谁使用。
4. Install：最短安装命令。
5. Run Demo：10 分钟 fixture demo。
6. Review Desk：本地审查台入口。
7. Capability Boundaries：production backend 边界。
8. License：Apache-2.0。
9. Contributing / Security。

## 4. Quick Start 要求

`docs/quick-start.md` 必须包含：

1. 环境前提。
2. 安装命令。
3. fixture demo 命令。
4. Review Desk 启动命令。
5. 审批一页的步骤。
6. readiness/export 查看方式。
7. 常见失败场景和修复命令。
8. 未配置 production backend 时的用户可读解释。

## 5. demo 脚本

新增或补齐 `scripts/demo.sh`：

1. 默认使用 fixture / local-only 路径。
2. 不依赖作者本机路径。
3. 输出下一步命令。
4. 失败时给出可操作错误信息。

## 6. production 文档一致性

以下文件不得把 fixture-only 命令包装成 production 路径：

1. `README.md`
2. `docs/quick-start.md`
3. `skills/deck-master/SKILL.md`
4. `skills/ppt-master/SKILL.md`

## 7. 验证命令

```bash
python -m pip install -e ".[dev]"
python scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

## 8. 成功标准

1. 外部用户不需要知道内部仓库和本机路径。
2. demo 能稳定打开 Review Desk。
3. 文档清楚区分 fixture demo 和 production backend。
4. `preview-gate` 通过。
