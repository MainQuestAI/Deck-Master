# SC-1 落库修订记录

| 项 | 内容 |
|---|---|
| 修订日期 | 2026-09-07 |
| 修订来源 | 仓库侧对规格包的落地审查（对照基线 `4199a6a` 的代码核验） |
| 原件版本 | SC-1 Spec v1.0（原件以独立 commit 落库，其 SHA256SUMS 在该提交上仍然可独立验证） |
| 修订范围 | 只修订规格包文档与自检工具；不声称任何产品能力已实现 |

原件的事实声明经逐项核验（F01—F05、复用映射 R1—R8 全部属实）；本修订只补审查中发现的缺口，不改变 D01—D12 裁定与三个工作包的范围。

## 修订一：验收追溯补全

- `acceptance/cases.json` 全部用例新增 `spec_ref` 字段，回指 `specs/` 主治理章节；总数 88 → 91。
- 新增三个此前无专属用例的验收项：A-13 分层就绪状态可读（specs/03）、I-08 高风险假设不冒充客户事实（specs/04）、Q-13 无来源支持的数字被发现（specs/07）。
- `specs/08`、`specs/09` 补齐缺失的验收节（§8.8、§9.7）；`acceptance/MATRIX.md` 同步至 91 项。

## 修订二：审查提示词升级显式化

`tasks/WP-C.md` C1 显式写入 `skills/deck-master/prompts/quality_reviewer.prompt.md` 的 v1（五维英文）→ v2（六维量规）升级，并要求核对 `narrative_advisor`、`source_decision_reviewer` 维度词表；此前该集成步骤仅有隐含要求，存在被遗漏后语义审查跑在旧词表上的风险。

## 修订三：Q0 基线清单扩充

`specs/01` §1.4 追加 F06—F12 七项已核实的静态缺陷（生产叙事模板化与样例过滤误伤、fixture 渲染来源失真、generation_result v1/v2 schema 断代与悬空引用、RESOLVER 路由错位、agents 元数据版本漂移、Review Desk 审批不回写反馈、render_handoff 恒真探针），全部进入 Q0 最小复现与核验范围。

## 修订四：Narrative Plan v3 结构草案

新增 `contracts/narrative-plan.v3.schema.json` 与合成样例 `examples/narrative_plan.json`，字段语义严格对齐 `EXTENSION_DELTAS.md` 的 Narrative Plan 目标 v3 字段表（此前该中心对象是六份 schema 中唯一只有文字描述的对象）。`tools/validate_spec_pack.py` 扩展至 7 份 schema / 7 份样例 / 21 个反例（新增 stale model hash、未知 selected candidate、cyclic beat dependency 三个反例）。样例与既有 solution_model/context_pack 样例的 ID 生态交叉一致。

## 修订五：PPT-Deck-Pro-Max 桥接退役显式化

`specs/03` §3.3 与 `tasks/WP-A.md` A1 显式点名：`scripts/runtime/builder_backend.py` 中钉在第三方非默认分支固定 SHA 的 `DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 绑定为最脆弱外部依赖，方法内化完成后必须退役，production 生成只走 Agent 派发。

## 完整性再生

本修订同步再生：`DEVELOPMENT_SPEC.md`（按拆分文件重新拼接，头部计数更新）、`SPEC_SELF_CHECK.json`（自检脚本实跑结果）、`PACK_MANIFEST.json` 与 `SHA256SUMS`（含新增文件）。`tools/validate_spec_pack.py` 结果为 passed（7 schema / 7 样例 / 21 反例全拒 / 91 用例）；该结果仍然只是规格包结构自检，不是产品测试。
