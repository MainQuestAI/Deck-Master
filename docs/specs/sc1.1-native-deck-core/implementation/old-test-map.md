# SC-1.1 Q0｜既有测试地图（old-test-map）

## 保持通过（回归硬底线）

- 全量套件（本分支复跑结果记于 acceptance-tracking）；其中直接踩编译链的关键文件：`test_high_density_builder*.py`、`test_high_density_distinct_acceptance.py`、`test_high_density_icon_stability.py`（它们同时是七类页差分代理：提取前后必须同样通过）。
- `test_build_runtime.py`、`test_page_package.py`、`test_sc1_page_packages_views.py`、`test_sc1_actions_and_gates.py`、`test_gate_freshness.py`、`test_next_step.py`、`test_skill_installation.py`、`test_workspace_learning_pack.py`、`test_sc1_feedback_metrics.py`。

## 编码了旧 D04 假设、需要调整语义（不是删除断言，而是改目标身份）

| 测试/位置 | 旧假设 | SC-1.1 处理 |
|---|---|---|
| `test_build_runtime.py` production 系列（backend gate 先行） | ppt-master 绑定是生产前置 | ND-02：native 路由先于外部查询；旧 tests 改为 route-level（native 不查 binding），legacy-ppt-master 用例保留 |
| `test_next_step.py`（HD 目录优先、缺门映射） | 目录优先 + render gate 兜底 | ND-02/ND-04：route/revision 解析 + semantic 动作映射；反例测试先行 |
| `test_skill_installation.py`（suite required 含外部整包） | ppt-master 整包 required | ND-02：required 策略统一改 native 内置能力 probe |
| `test_preview_gate*`/fixture 演示 | 旧默认路径 | 保留 fixture/dev 输入路径（兼容），不作为生产证据 |

## Q0 要求的反例测试（先写，先失败）

1. 无 binding 生产构建被伪报 ready（F-N02）→ 已有 env 测试；补"native 路由不调用 builder_backend_status"断言。
2. none parser：`--library-mode none` 全链 CLI 接通前 parser 拒绝（F-N07）。
3. 语义误匹配：external_visual 报告冒充 semantic 通过（F-N09）。
4. 第二文件中断：action commit 中断后必须完整旧 revision（F-N10，升级为 revision 指针）。
5. ready_for_build 一致性：包写 "ready" 而消费端/Schema 不认（F-N08）。
