# T03 × T04 联合集成门禁记录

日期：2026-10-13。范围：内容协作 v1.2 的 T03（分阶段内容生产）与 T04（统一资格与范围）两卡合流验证。基线 main `293579f1`（含 T00–T02）；合入分支 `impl/t03-content-production`（head `54b82c15`）与 `impl/t04-eligibility-scope`（head `bcb27cd7`）。

本记录只包含合成 fixture 与仓库内命令结果，不含客户材料、生成 runs 或绝对本地路径。

## 1. 合并与冲突

- 合并提交 `bf3d4563`（integration/t03-t04）。试合并预演（`git merge-tree`）显示唯一冲突在 `src/deck_master/service.py`：T03 的相位派发分支与 T04 的 `eligibility.guard("dispatch.compose")` 落在同一函数入口。
- 解决规则（事先约定）：**先 gate 再分派**——routing 判定在任何任务对象存在之前消费请求的 intent/scope/decision 状态（CONTRACTS §6.2 row 1），随后 collaboration.v1 项目走相位 compose.v2 派发，旧项目保持 compose.v1 字节不变。合并后 6 个重叠文件自动合并，无其它冲突。

## 2. 联合门禁发现（两卡单独分支不可见的问题）

| 发现 | 根因 | 修复 |
|---|---|---|
| **绑定 digest 两套实现不一致**：T03 盖章的 binding 在 T04 gate 重算时全部判 stale | T03 按 `slice_key` 排序后取 sha256；T04 直接对 sha256 值排序。两个"顺序无关"的实现产生不同字节 | `eligibility.binding_eligibility_digest` 委托 `collaboration_binding.eligibility_digest`，单一实现；跨卡回归 `test_one_binding_digest_shared_by_dispatch_and_gate` 用两种排序必然分歧的 fixture 锁死 |
| **compose.v2 写集合在 accept 侧不可见**：page_copy/narrative 的 targets 为空，scope 检查空转（信封写集合不受检查） | `_accept_targets` 只认识 v1 信封槽位；v2 的写集合在 `payload` 内 | `_compose_v2_targets` 按 variant 提取 pages/layers（page_copy/speech/input_revision/narrative/framing）；未知层名由 variant 解析器拒绝 |
| **规划态 deck 请求的页覆盖**：speech/input_revision/审查派发在 planner scope（`page_ids=[]`）下被判越界 | §2.1"空集恒指没有页面"被实现为"规划态不覆盖任何具体页"，而 §3.4 的物化规则只在派发时发生 | `_page_coverage_from_binding`：当前 Plan 即页集合的冻结投影（§2.1）；有界任务 binding 的 write_scope 是同一集合（§3.4）；plan-creating 相位（page_copy）由其自身结果固定集合（§11.5）。层仍须在请求范围内，冻结集合之外一律拒绝 |
| **import_draft 的资格判定被结构性阻塞遮蔽** | T03 的 `ImportRequiresPhasedPath` 排在 T04 的 guard 之前 | 调整为 §6.1 次序：形状 → **资格判定** → 写作边界路由检查。review_only/paused 得到精确 reason code；范围内稿件仍停在该写边界检查并给出两条真实恢复路径 |
| **change.commit 派发无绑定任务**（AC-R03 局改在受管项目内不可用） | `changes._new_task` 不写 binding；T04 的无条件兜底在 allowance.allocate 处停住 | 在 reserve 之前 `stamp_task(phase="production", page_ids=[...], adoption_policy=trial?candidate_only:within_scope)`；低于 collaboration.v1 的项目字节不变（stamp_task 为 no-op） |
| **T03 新增公开入口未分类** | `service.revision_compose_task` 不在入口清单 | `eligibility_entries` 增行（dispatch.compose，说明调用方的 gated 边界）；覆盖测试重新全绿 |

## 3. 过渡态测试更新（保留意图，改变构造）

| 测试 | 原前提 | 更新 |
|---|---|---|
| `test_real_dispatch_without_binding_cannot_be_accepted` 等 3 条 | "真实派发无 binding" | 真实派发（现在盖章）后经共享 `_strip_binding` 注入为升级前形态（MIGRATION §3.5），无条件兜底照测 |
| `test_replace_reports_unbound_active_tasks_honestly` | 同上 | 同上；`unbound_tasks[]` 报告与后果断言不变 |
| `test_blueprint_dispatch_requires_scope_and_authorization` | 授权后停在"缺 binding" | 授权后**成功派发**且携带 phase=production binding（合流后的正确状态） |
| `test_continue_routes_when_the_request_covers_the_work` | 覆盖的工作停在 needs_input | 覆盖的工作派发相位任务（awaiting_host）且带 binding |
| `test_review_only_request_refuses_page_import_and_blueprint_dispatch` | import 报 EligibilityBlocked | import 走 §6.1 次序先得 scope_exceeded（精确拒绝）；blueprint 拒绝不变 |
| `test_page_copy_keeps_membership_change_behind_the_scope`、`test_input_revision_refusals` | 越界写集合报 variant 层 EnvelopeError | 同一拒绝由 gate 前置为 `EligibilityBlocked(scope_exceeded)`（更早、类型化；variant 层检查仍在） |
| `test_import_draft_on_a_collaboration_project_is_blocked_with_recovery` | 结构性阻塞 | 两段式：范围外→`EligibilityBlocked`；范围内→`ImportRequiresPhasedPath`（恢复指引不变） |
| 审查 fixture 的请求 scope | layers 缺 `review` | full_deck 请求包含其流程合法写入的 review 层（§6.3 前审是 full_deck 的必需单元） |
| binding 派发 fixture | 请求不命名页 | 页先存在、请求命名 `page_ids` 与层集合 |

新增 `tests/rebuild/test_t03_t04_integration.py`（4 条）：共享 digest（决定性 fixture）、受管项目内 change 派发+接纳端到端、无授权 commit 拒绝、相位任务在 gate 下接纳端到端。

## 4. 验证账本

| 检查 | 状态 | 实际结果与边界 |
|---|---|---|
| 联合全量非浏览器回归 | PASS | `1628 passed, 455 deselected`（Python 3.12.12，pytest 9.1.1；含两卡全部测试与新增 4 条集成测试） |
| Ruff / diff whitespace | PASS | `ruff check src/deck_master tests/rebuild`；`git diff --check` |
| 旧项目行为不变 | PASS | T03/T04 各自声称的"低于 collaboration.v1 字节不变"在合流后由全量既有测试与 stamp_task no-op 路径继续锁定 |
| 联合门禁对生产路径的资格 | 记录 | 本增量仍不翻转 create 默认 writer、不对旧项目启用 enforcement；两卡合并通过不等于启用发布（MIGRATION §5.3） |
| 真实 Host / 人类审查收据 / 用户与听众验证 | NOT_RUN | L2–L6 证据归 T07/T08，本记录不声称 |

实际命令：

```sh
PYTHONPATH=src python -m pytest -q tests/rebuild -m 'not render and not browser'
python -m ruff check src/deck_master tests/rebuild
git diff --check
```

## 5. 遗留与移交

- **create 默认 writer 翻转**（新项目启用 collaboration.v1 与迁移提示）：联合集成/发布步骤单独判定，本分支不做。
- **visual_styles.py 的 style_analyze 派发**：design 相位在 T05 落地前保持诚实拒绝（入口清单已注明）。
- **§12 CLI/HTTP collaboration API、严格只读项目外报告、真实身份适配器**：T07。
- **PPTX notes 编译与回读**：T06。**真实内容/视觉/使用效果**：T08。
- PR 结构：T03、T04 各自基于 main 的 Draft PR 记录两卡审查；本集成分支为第三个 PR（跨卡修复与联合门禁），依赖前两者。
