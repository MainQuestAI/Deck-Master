# SC-1 Spec 偏差登记

| 日期 | 任务/PR | 原约束 | 实际采用方式 | 原因/证据 | 对业务目标与兼容性影响 | 关联验收 | 是否需用户裁决 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 2026-09-07 | Q0/PR-01 | F08"运行时 handback 强制 v2 且无 v2 schema" | 修正记录：`docs/contracts/generation-result.v2.schema.json` 在基线已存在（commit 979adec）；残留问题改为"skill 侧 schema 滞留 v1 + 同一契约散落 4 处 + ppt-library-handoff.md 悬空引用" | 实测 `git cat-file -e 4199a6a:docs/contracts/generation-result.v2.schema.json` 通过；`handback.py:32` 强制 v2 | 无范围变化；A1 schema 统一任务不变，证据更准确 | F08、A-01 | 否（事实修正，非范围裁决） | open |
| 2026-09-07 | Q0/PR-01 | Q0 产物路径由仓库惯例决定 | 落位 `docs/specs/sc1-solution-core-independence/implementation/`（baseline-audit / reuse-map / schema-migration-map / capability-migration-matrix / deviation-log / acceptance-tracking） | 仓库先例：`docs/specs/real-production-closure/implementation/`、`docs/specs/skill-os/implementation/` | 无；实现映射文件回写至本包 `agent/IMPLEMENTATION_MAPPING.md` | — | 否 | closed |
| 2026-09-07 | Q0/PR-01 | 开发环境 Python 要求 | 系统 Python 3.14 超出 `requires-python >=3.11,<3.14`；venv 固定 3.12（AGENTS 默认） | `pyproject.toml` requires-python；本机 /opt/homebrew/bin/python3.12 存在 | 无；A6 安装文档需写明 3.11—3.13 支持范围 | A-01 | 否 | closed |
| 2026-09-07 | Q0/PR-01 | 真实标准 smoke（A-03/A-04/P-01） | 本机 PPT Master 后端 unbound、release 树残缺，真实 smoke 无法立即执行；先以测试映射 + 托管安装落地，后端可用后补真实证据并如实登记 blocked→pass | `agent-doctor --mode production` blocked 实测；AGENTS 禁止虚报生产就绪 | A-03/A-04/P-01 等"真实工具"用例在环境具备前保持 blocked；不以 Fixture 顶替 | A-03、A-04、P-01、E-01—E-06 | 若最终无法取得真实后端/样本，整轮按规格报告 `engineering_complete / outcome_pending`，不需预先裁决 | open |
| 2026-09-07 | PR-02/A1 | 锁 schema 版本递增 | capability lock 以 **v1 加性扩展**落地（新增 `components`、`runtime_components`、`pinning_policy` 键），不升 v2 | rc_gate/agent-doctor 等 v1 读者只取 `external_dependency_status`，加性键零破坏（`runtime/rc_gate.py:1051`）；避免无消费方的版本跳变 | 无破坏；schema-migration-map §2 相应记录 | A-01、A-02 | 否 | closed |
| 2026-09-07 | PR-02/A2 | runtime_ready 语义 | 恒真 contract_probe 退役：无真实 smoke 证据时 `runtime_ready=False`（source=`smoke_evidence_missing`）；env `DECK_MASTER_PPT_MASTER_RUNTIME_WIRED` 只能阻断不能伪报 ready；ready 唯一可信来源=绑定记录中的真实 smoke 证据 | F12 验收"A-04 不经环境变量伪报 ready"；2 个既有测试按新语义更新并映射 A-04 | 更诚实；依赖 contract_probe=True 的旧下游（suite-status render_runtime_ready）在无证据时如实转 blocked | A-04、A-02 | 否 | closed |
| 2026-09-07 | PR-02 | 八 PR 顺序 | A1—A4 以单 commit 交付（PR-02 合并执行） | 00-delivery-plan："PR 数量是执行建议，不是产品需求" | 无；每任务测试映射保持 | — | 否 | closed |

> 本表仅登记普通实现偏差；标准后端取消、真实研究删减、用户工作量目标弱化、语义审查降级、范围扩大不属于可自行登记的偏差（包内模板约束）。
