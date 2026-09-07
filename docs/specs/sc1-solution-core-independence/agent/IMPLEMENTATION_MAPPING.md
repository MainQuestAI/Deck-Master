# SC-1 实现映射（Q0 输出位置）

按 `agent/START_HERE.md` 要求，Q0 产物已固定到仓库惯例位置。先决任务（Q0）完成后，各 PR 的实现以本目录文档为 baseline。

| Q0 交付物 | 落库路径 |
|---|---|
| baseline-audit（HEAD/基线差异、测试结果、环境条件、F01—F12 复现、五链路答案） | `docs/specs/sc1-solution-core-independence/implementation/baseline-audit.md` |
| reuse-map（规格 §1.2 逐条核验 + 补充可复用资产） | `docs/specs/sc1-solution-core-independence/implementation/reuse-map.md` |
| schema-migration-map（版本冻结表、旧读写差异、迁移规则） | `docs/specs/sc1-solution-core-independence/implementation/schema-migration-map.md` |
| capability-migration-matrix（能力/安装现状 → SC-1 目标矩阵） | `docs/specs/sc1-solution-core-independence/implementation/capability-migration-matrix.md` |
| deviation-log | `docs/specs/sc1-solution-core-independence/implementation/deviation-log.md` |
| acceptance tracking（91 项状态 + 前置阻塞） | `docs/specs/sc1-solution-core-independence/implementation/acceptance-tracking.md` |

## PR 顺序与实现映射速查

| PR | 任务 | 必读 baseline | 关键接入点 |
|---|---|---|---|
| PR-01 | Q0（本轮已交付） | — | 本目录全部 |
| PR-02 | A1—A4 | baseline-audit §3/§5、capability-migration-matrix | `installer.py`、`builder_backend.py`、`ppt_library_client.py`、manifest/lock |
| PR-03 | B1—B3 | reuse-map §1（local_sources/context_pack/brief_compiler/judgment_builder） | `context_intake/`、`conversation/brief_compiler.py`、`narrative/judgment_builder.py:120-135` |
| PR-04 | B4+A5 | reuse-map（narrative_planner/advisory/high_density）、F03/F06 | `planning/narrative_planner.py`、`page_budget.py`、`advisory/narrative.py`、`workflow/questions.py` |
| PR-05 | B5—B6 | baseline-audit §5.1/§5.2（标准不消费 Page Package、HD MBB 边界） | `production/page_package.py`、`runtime/build.py`、`build/manifest.py`、`high_density/` |
| PR-06 | C1—C3 | baseline-audit §5.3（gate 绑定）、F11 | `quality/`、`runtime/final_readiness.py`、`preview/server.py`、workbench |
| PR-07 | C4—C5 | F01 复现、F11 | `learning/pack.py:64-148`、`assets/feedback.py`、benchmarks |
| PR-08 | A6+C6 | capability-migration-matrix §2/§3 | suite migrate/install、release verify、docs |

## 事实修正（相对原规格文本）

- F08 的"无 v2 schema"已过时，见 `deviation-log.md` D-001 与 `schema-migration-map.md` §2。
