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

## 未完成（下一增量，见 deviation-log）

manifest/release required 策略、旧 Run 迁移 CLI（MIG 组）、七类差分矩阵专项用例、HST 真实工具用例（宿主无 ImageGen）、UAT-01/02、QA-03 逐页内容指纹深度。
