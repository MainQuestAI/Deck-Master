# RC5 工程验收与内容验证边界

本回执描述当前接续工作树的实际检查，不代表发布、用户认可或专业内容质量通过。资源完整性快照见 `library-integrity.json`：66 个登记资源、4 个公开入口、76 个发布映射文件；本地 Markdown 文件链接和示例标注检查通过。快照只应与当次源码字节配对。

## T01–T12 覆盖映射

| 条件 | 可复现覆盖 | 当前证据 / 边界 |
|---|---|---|
| T01 目录/入口 | `check_content_method_library.py`、`test_rc3_resource_inventory.py`、`test_rc5_resource_catalog.py` | 统一 catalog/build 映射；重复ID/路径拒绝；4入口保留 |
| T02 非法文件与路径 | `test_rc5_resource_catalog.py::test_catalog_rejects_invalid_graph_and_paths`、`test_rc5_library_acceptance.py::test_library_checker_reports_real_defects` | 未登记、缺失、symlink、逃逸、错误依赖均有拒绝行为；不使用HOME补找 |
| T03 M04+E04 | `test_rc5_library_acceptance.py::test_actual_m04_e04_dependency_bytes_are_small_and_frozen` | 真实M04、E04 walkthrough/input/after被选入，before与无关E01不进入；逐文件核对SHA |
| T04 后绑定再冻结 | `test_rc5_resource_catalog.py::test_final_bound_phase_builder_preserves_explicit_selection`、`test_refreeze_recomputes_defaults_without_inferring_selection` | 显式选择在最终阶段生效；旧阶段基础资源退出；不把暂态manifest当选择 |
| T05 旧Task | `test_rc5_library_acceptance.py::test_legacy_manifest_hash_drift_is_not_resigned`、既有frozen basis测试 | RC4形状release+原SHA不被改写；新字节不等于旧字节时basis_changed |
| T06 full/delta/新会话 | `test_rc5_resource_catalog.py`上下文测试、`test_rc4_work_context.py`、真实E04新会话测试 | 资源仍为method传输；冷会话返回全文；manifest模式不谎称context_ready |
| T07 四类范围 | `test_rc3_four_skills.py`、`test_compose_v2_phases.py`、`test_rc3_legacy_speech_continuation.py`、`test_rc3_import_scope.py`、`test_rc3_design_requirements.py`、`test_rc3_design_feasibility.py`、`test_scope_and_delegation.py` | 路由本身不是授权；只写正文/口播/设计/审阅复用现有事务与范围拒绝测试。实际CLI文字范围探针另见scope-probe-review.md；不把文字探针当Runtime写入E2E |
| T08 打包/安装 | `test_rc3_resource_inventory.py`、`test_rc5_resource_catalog.py`wheel检查；主线程实际wheel/sdist/managed验收 | 干净提交5d5db8cf的wheel/sdist及隔离managed安装完成，76文件一致；见package-verification.json |
| T09 示例隔离 | 真实E04测试（transport kind为method）、库example标注、四入口说明 | 证明字节分类和教学边界存在；模型是否把示例当客户事实须在完整稿评审检查，不以分类断言专业PASS |
| T10 算术 | `test_rc5_library_acceptance.py`六算子、错误预期、零分母/非法算子/NaN/表达式/缺值/布尔/重复键/超大输入 | 只检查显式公式；不验证来源真实性、分母业务适用或因果 |
| T11 审阅身份/覆盖 | `test_rc3_review_policy_workflow.py`、`test_external_review_readback.py`、库工具输出professional_content_review=NOT_RUN | 返回字节与专业判断分开；独立审阅与人类认可必须真实发生 |
| T12 旧路径/13 ID | catalog保留约束、旧Task drift、`test_rc3_four_skills.py`与旧speech回归 | 历史路径不变；旧13 ID并非新库总数上限 |

## 当前运行记录

所有 pytest 运行使用工作树 `PYTHONPATH=src` 与可用Python环境，`-B`禁止生成Skill目录缓存。不会把其他checkout的可编辑源码误当待测版本。

- `pytest -q tests/rebuild/test_rc5_library_acceptance.py`：22 passed（0.57秒）。
- `python -B tools/check_content_method_library.py`：PASS，结果已保存。
- RC5 catalog / RC4 context / four skills / compose phases / legacy speech / import scope / review policy 合并回归：147 passed，1 failed。失败为framing基础清单新增`method-selection`后旧测试仍断言3项；已交由runtime负责人修正预期，保留其phase/scope语义断言。重跑结果应追加于此。

## 内容验证输入及未运行边界

三个新题在工作树外的 `../evaluation-inputs/`，均为原创可公开的虚构材料、6页完整正文与备注：冷链配送经营诊断、博物馆入场方案选择、场馆交接判断教学。不是E01–E06种子回放。已完成6份实际模型稿（36页）、独立Agent审阅及3份另存修订稿，见paired-manuscript-review.md。原始稿保留，没有将全部原始稿记为专业通过；人类认可仍未运行。完整结果存于工作树外。

- 设计需求、设计可行性、scope/delegation、external review readback 合并回归：115 passed（2.68秒）。
- runtime负责人更新framing预期后，定向重跑该失败项与22项真实库验收：23 passed（0.94秒）；已知失败已消除。资源完整性快照随后刷新PASS。

## 集成与复现

- Host接线65项定向测试通过，独立审查修复import-draft参数回归、输入修订选择恢复、只读审阅stage映射及非法选择写对象副作用。
- 全量执行发现历史Task兼容性回归：RC5新增默认指南不应使未变化的旧依据失效；已修复并补测原字节不变/变化两路。
- 新Task方法列表和writer floor更新为真实新默认，固定历史快照与旧selector没有批量改写。相关受影响模块分别复跑通过。
- 完整单元命令：`python -B -m pytest -q tests/rebuild -m "not render and not browser" --basetemp ../pytest-rc5-unit`。macOS默认`/private/var/...`会触发既存评测工具的private目录拒绝，故使用工作树旁专用临时目录，不改安全规则。完整日志保留在工作树旁`unit-suite-verified.log`；最终线上全矩阵结果以PR当前准确HEAD的Checks为准。
- 本机初轮render为12 failed / 121 passed / 1 skipped；4项为已修正的新writer断言，相关用例已定向通过。剩余8项分别为源/原生图像等同性与字形溢出坐标，在未修改的PR原始1e66ae05上复跑同样8 failed / 1 passed，不能记为当前本机全绿，也不扩展本轮为渲染引擎修改。原始日志与基线对照保留在工作树旁。
- clean-source构建与安装证据绑定5d5db8cf；其后证据文档提交不应被误报为已重新构建的包。没有tag、Release、真实HOME激活或人类专业认可。

## 完整运行读回与跨平台修复

- 本地完整单元运行：3461 passed、2 skipped、1 failed、635 deselected。唯一失败为相对解释器路径 `../venv/bin/python` 在子进程规范化后触发严格身份比对；原始 PR 同样复现。使用规范绝对解释器路径重跑 `test_rc3_image_events.py` 全模块：28 passed（7.03秒）。没有修改身份或权限断言。
- `e7f6e125` 的 Linux Python 3.11 / Node 24 单元任务：3461 passed、2 skipped、1 failed。新增超长输入用例的自动参数名称进入 `PYTEST_CURRENT_TEST` 环境变量，触发 Linux 单个环境字符串长度限制，未到达算术脚本。修复为短语义测试 ID，保留原超长输入及拒绝断言；最终全矩阵结果须读回修复后的准确 HEAD。
- `e7f6e125` 的 PR/push Linux真实渲染任务均 SUCCESS；修复后的完整 CI 状态见 PR Checks。

## PR127 独立评审后的云端修复

三项 P2 及 A/B 窄回归的修复、完整验证状态与外部访问限制见
[云端修复回执](pr127-review-fixes-cloud.md)。本轮 clean-source 包验证单列为
[package-verification-cloud-review.json](package-verification-cloud-review.json)，
资源快照见 [library-integrity-cloud-review.json](library-integrity-cloud-review.json)。
原 `5d5db8cf` 包证据和本机测试历史保留，不用当前文档 head 覆写其来源。
