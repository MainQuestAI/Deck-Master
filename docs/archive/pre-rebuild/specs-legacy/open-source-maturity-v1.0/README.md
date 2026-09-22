# Deck Master Open Source Maturity Spec Pack

日期：2026-07-06
状态：Development Spec
来源计划：`docs/planning/2026-07-06-open-source-maturity-iteration-plan.md`

## 1. 目标

本 Spec 包把开源成熟度迭代计划拆成可执行开发包，服务两个里程碑：

1. M1：public Technical Preview，严格闸门，通过后可公开展示和试用。
2. M2：正式开源 RC，完成 production、设计系统、安全、社区和 release tree 收口。

已拍板口径：

1. M1 直接 public，状态标记为 Technical Preview。
2. 允许 preview / pre-release 语义 tag，不承诺正式版，不发布 stable release。
3. 当前 Deck Master 仓库全仓 Apache-2.0 开源。
4. M1 采用严格口径：License、pyproject、README/Quick Start、公开 demo、repo hygiene、后端真相、Review Desk 最小设计合规、preview-gate 全部通过。

## 2. 文件入口

| 文件 | 用途 |
|---|---|
| `00-master-spec.md` | 总控 Spec，定义边界、里程碑和任务依赖 |
| `01-release-governance-spec.md` | public Technical Preview、License、版本、治理文件 |
| `02-first-run-demo-docs-spec.md` | README、Quick Start、demo 脚本、外部用户首跑 |
| `03-public-fixture-seed-spec.md` | 10-12 页公开 fixture demo 数据 Seed |
| `04-backend-truth-preview-gate-spec.md` | 后端真相、误报 ready 修复、preview-gate |
| `05-review-desk-design-minimum-spec.md` | M1 Review Desk 最小 DESIGN.md 合规 |
| `06-m2-rc-hardening-spec.md` | M2 RC、安全、社区、正式 release tree |
| `implementation/development-plan.md` | 推荐执行顺序与并行方式 |
| `tasks/` | 可交给 Agent 的独立任务包 |
| `acceptance/acceptance-matrix.md` | M1/M2 验收矩阵 |
| `acceptance/qa-test-plan.md` | 验证命令与测试计划 |
| `acceptance/screenshot-checklist.md` | README / Review Desk 截图清单 |

## 3. 推荐执行顺序

```text
T1 release governance
T2 packaging ci
T3 backend truth preview gate
T4 docs first run demo
T5 public fixture seed
T6 repo hygiene release tree
T7 review desk design minimum
M1 acceptance
T8 m2 rc hardening
```

## 4. Agent 使用规则

每个任务包必须遵守：

1. 只改任务包允许的路径。
2. 先补测试或验证命令，再改实现。
3. 交付报告必须列出修改文件、验证命令、真实结果、剩余风险。
4. 不得把 fixture-only 路径写成 production 路径。
5. 不得在公开文件中保留作者本机绝对路径、内部 agent 痕迹、客户敏感内容。
