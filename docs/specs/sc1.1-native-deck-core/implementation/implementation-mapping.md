# SC-1.1 实现映射（Q0 → ND-01..ND-05）

| Q0 交付物 | 落库路径 |
|---|---|
| baseline-diff / call-graph / reuse-vs-replace / old-test-map / host-capability-probe / dependency-closure | `docs/specs/sc1.1-native-deck-core/implementation/`（六份） |

## ND 段落 → 实现与证据速查

| 段 | 交付 | 证据 |
|---|---|---|
| ND-01 内核提取 | `scripts/native_pptx/`（pptx/svg_native/svg_paint/visibility/visual 迁移 + svg_pipeline/canvas 拆分 + api.py 门面 + HD 六模块 sys.modules shim + svg.py/blueprint.py 回导入） | `tests/test_sc1_1_native_kernel.py`；HD 全部既有回归 |
| ND-02 路由/就绪/none | `scripts/build/build_route.py`、build.py 路由先行（F-N02）、--library-mode none（F-N07）、page_builder/build ready_for_build（F-N08）、next_step 语义动作映射（F-N06）+ 引擎提示（F-N05）、`native_pptx/probe.py` 真实探针 | `test_sc1_1_native_routing.py`、`test_sc1_1_native_probe.py` |
| ND-03 引擎链 | `scripts/build/native_engine.py`（prepare/submit_svg/run_compile：单一事实源加载 run scenes/locks、注入 HD 业务验证器、native api 编译+回读、imagegen 派发诚实 awaiting） | `tests/test_sc1_1_native_engine.py`（两页真实编译+回读） |
| ND-04 门禁/修订 | gate_policy 语义门精确匹配（F-N09：external_visual + 有效哈希仍拒绝）；workflow/actions revision 指针 + expected_revision CAS + 失败计入预算（F-N10） | `tests/test_sc1_1_gates_and_revisions.py` |
| ND-05 收口 | 本文件 + acceptance-tracking + deviation-log；主 Playbook/README/known-limitations 的 native 默认更新 | 见下 |

## 本轮收口补充

迁移实现位于 `scripts/build/migrate.py`，提供计划、候选构建、apply、verify、rollback；定向事务测试位于 `tests/test_sc1_1_migration_apply.py`。实际产品验收尚未统一执行，不将事务 stub 当作真实迁移通过。

当前验收工具为 `scripts/uat/sc1_1_engineering_matrix.py`，汇集 64 项新 case、88 项映射及原 SC1 新增的 3 项；全部默认 not_run。完整清单见 `engineering-gap-inventory.md`。10 页合成 UAT 原材料位于 `examples/sc1_1_uat/raw_materials.json`，不含逐页稿。

路由、渲染、manifest 和指纹修复由本轮各工作包整合；最终产品证据应绑定同一候选 SHA。真实宿主能力需现场核验，不继承旧笔记的缺工具结论。七类差分、默认两页、完整10页、桌面编辑、隔离安装与用户批准目前均不因实现完成而自动通过。
