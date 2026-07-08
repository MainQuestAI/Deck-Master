# Open Source Maturity Development Plan

## 1. 执行原则

本轮按 M1 严格口径推进，先拿 public Technical Preview，再进入 M2 RC。所有任务都必须能回连到 acceptance matrix。

## 2. 并行分组

| Lane | 任务 | 可并行条件 |
|---|---|---|
| A | T1 Release Governance | 立即开始 |
| B | T2 Packaging And CI | 与 T1 并行，version 字段等 T1 口径 |
| C | T3 Backend Truth And Preview Gate | 与 T1/T2 并行，最终验证依赖 T2 |
| D | T4 Docs First Run Demo | T1 初稿后开始 |
| E | T5 Public Fixture Seed | T4 demo 命令冻结后开始 |
| F | T6 Repo Hygiene And Release Tree | T1/T2/T3 同步推进 |
| G | T7 Review Desk Design Minimum | 读完 DESIGN.md 后开始 |
| H | T8 M2 RC Hardening | M1 验收后开始 |

## 3. 推荐顺序

```text
Day 0:
  T1 + T2 + T3 start

Day 1:
  T4 + T5 + T6 start
  T3 negative tests

Day 2:
  T7 design minimum
  M1 preview-gate
  release checklist evidence

After M1:
  T8 M2 RC hardening
```

## 4. M1 集成检查

集成前必须确认：

1. `python -m pip install -e ".[dev]"` 成功。
2. `python -m unittest discover -s tests` 通过。
3. pytest 合约子集通过。
4. fixture demo 生成 10+ 页。
5. `preview-gate` 通过。
6. `git ls-files .gstack` 为空。
7. Review Desk M1 静态扫描通过。
8. README / Quick Start 不含作者本机路径和 placeholder。

## 5. 任务交付报告模板

```text
任务：
修改文件：
实现摘要：
验证命令：
验证结果：
影响的验收项：
剩余风险：
建议后续：
```
