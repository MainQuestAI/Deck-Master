# PR #189 复审 P1 修复记录

基准：`db893525`（远端 `codex/integration-closeout-20261025` 第二轮头部，含 `6efc0911` 等 10 个新提交）。本轮处理独立复审（`c217d342..f06a8061` 修复增量复审）确认的三项 P1，均为保守方向误拒或错误分类，无放行风险。PR 保持 Draft，未合并、发布或迁移实际 HOME。

## 与第二轮远端提交的整合

复审期间远端并行推进了第二轮修复。对齐结果：

| 复审 P1 | 远端处置 | 本轮处置 |
| --- | --- | --- |
| P1-1 blueprint 候选 basis 缺 frozen visibility | `6efc0911` 已修，代码与复审建议逐字同款（`**frozen_design_options(prepared['resolved_design_context'])`） | 不重复修代码；`7ef02e25` 补充升级稳定性契约的固化回归 |
| P1-2 原图审查读取链缺 frozen visibility | 未修 | `150c992c` 修复 |
| P1-3 abandon 的 pending pointer 冲突未类型化 | 未修（`d443f122` 重写 discover/collect 后该路径仍可达，`abandon` 内 `clear_pending` 裸调用未变） | `0eb1528e` 修复，并在新 discover 语义上复验 |

## 修复决策

### P1-2 原图审查读取链（`150c992c`）

`original_review.packet()` 重算 `resolved_design` 用默认 `text_visibility=True`，冻结包缺该字段 → `inputs_current` 语义比较必不等 → 升级前 dispatch 的原图审查任务在 `validate_result` 抛 `StaleInputContext`；`reference_status` 用单一 current 包与全部历史冻结包全等比对 → 历史 pass 全部失配 → `not_evaluated`，expand 权限被误拒。修复三处联动：`packet()` 新增 `frozen_design` 参数（新派发路径保持完整 current 投影）；`inputs_current` 按任务自身冻结契约比较；`reference_status` 逐条历史按其冻结契约对齐重算，单行契约不可读（未知版本）时该行保守不采纳，不中断整个读取。`effective_requirements` 由协作决策构成、不含 `text_visibility`，故只需线程化设计参数。

回归（`test_pr189_visibility_compat.py`）：legacy 任务未变化时 `inputs_current` 为真、历史 pass 保持 `pass` 且 expand 放行、读取无写入（`store.load_document()` 前后相等）；真实 Page 变化仍保守（`inputs_current` 假、expand 阻断）。红：未修复树两断言失败；绿：本修复，且守卫用例在两侧都通过（证明未软化）。

### P1-3 abandon pointer 冲突类型化（`0eb1528e`）

`abandon` 先持久化 abandoned 回执再 `clear_pending`；当 pointer 已指向另一个存在事务时 `clear_pending` 抛无 `transaction_id` 的裸 `ValueError`，CLI 归类为 `invalid_input`（提示与实况无关），而磁盘上事务已 abandoned。修复：包装为 `installation_transaction_conflict`，携带 `transaction_id`、`state='abandoned'` 与 `details.pending_pointer='retained'`；abandoned 回执不变，pointer 不属于本事务故永不清理（收敛依赖下次 activate 的 pointer repair）。有意不做 `recover_transaction` 预检拦截：预检会让无关 stale pointer 阻止 abandon 本身。

测试（`test_install_transaction_controls.py`）：原"corrupt or different pointer"用例的随机 UUID 分支实际在 `discover` 失败、未触达 `clear_pending`，拆分为损坏 pointer（discover 拒绝、场景不变）与 pointer 指向另一存在 completed 事务（断言 typed 冲突、`transaction_id`/`state`、磁盘 journal 已 abandoned、pointer 保留、同 reason 重试幂等且不重写回执）两个用例。红：未修复树以裸 `ValueError` 失败；绿：typed 冲突。该测试在远端 `d443f122` 的新 discover/collect 语义上复验通过。

### P1-1 固化回归（`7ef02e25`）

远端已修，本轮回归锁定升级稳定性契约：同一未变化 legacy 输入在"升级前语义"与"升级后代码"下 `generation_basis` 逐键相等，digest 恒等于 frozen 壳的记录编码；真实设计变化（Page intent 变更 + plan 链接同步）仍产生不同 digest。未修复树上一断言失败（digest 漂移），配合 `6efc0911` 通过。

## 验证记录

| 套件 | 结果 |
| --- | --- |
| `test_pr189_visibility_compat.py` | 8 passed（4 个新用例） |
| `test_install_transaction_controls.py` + `test_install_transaction_recovery.py` | 30 + 若干 passed（1 新 + 1 改写，含新 discover 语义复验） |
| `test_rp20_original_review.py`、`test_pr189_finding_endpoints.py`、`test_pr189_reopened_finding.py`、`test_selected_file.py`、`test_style_v3_contract_consistency.py`、`test_pr189_authorization_reissue.py`、`test_pr189_operation_reader.py` | 225 passed |
| `test_rc3_adopted_design_handoff.py` | 41 passed |
| `test_rc3_native_visual_reuse.py`、`test_rc3_plan_visual_consumption.py` | 36 passed |
| `ruff check src/deck_master tests/rebuild`（CI 范围） | 通过 |

红绿方法：每项修复先在未修复树确认新用例以声明中的确切路径失败（digest 漂移 / 语义失配 / 裸 ValueError），修复后转绿；守卫用例（真实变化仍拒绝）在修复前后都通过，证明没有软化既有拒绝。全部旧断言、时限与 skip 保持不变；远端 CI 以推送后的检查为准，首跑失败不覆盖。

## 边界

复审记录的 P2 项（eligibility 来源请求快照搜索性能与异常面、completed 例外的 paused 残留、存量无绑定 Task 的重签迁移、OperationReader 坏缓存自愈、`refreshControl` 并发三态、handoff 历史诊断 IO 与 symlink 行为、提交切分卫生、rc3-s12 workflow 触发方式确认）不在本轮，保持待跟进；其中 handoff 历史诊断与 workbench 副本重放与远端 `0e76b79b`/`435a758c` 有交叠，跟进时先对齐远端现状。真实 Host/专业产物、S3、Frozen A 外部资源、用户视觉认可及实际 HOME 迁移继续单列，工程检查不替代这些验收。
