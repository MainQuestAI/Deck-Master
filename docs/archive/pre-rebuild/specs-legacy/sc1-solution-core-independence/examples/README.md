# 合成契约样例说明

本目录全部由规格编写过程人工生成，不来自真实客户，不是 Deck Master 实际执行结果。
六个 JSON 样例分别匹配 contracts 中六份目标 Schema。它们只证明规格之间的数据形状可表达，不证明当前仓库已支持导入，不是可直接交付的完整 Run。

- capability_execution_plan 明确显示后端未验证、task_ready=false。
- context_pack 的证据处于 unreviewed，没有伪造支持审查。
- research_task 只表示待执行任务，没有执行过网页研究。
- solution_model / diagram_view 表示合成设计建议，引用本目录合成来源。
- external_quality_review 含一个故意构造的 P1 缺陷，状态为 rework_required；独立 reviewer/session 字段仅为协议样例，不是实际宿主证明。
- materials/late_constraint.txt 用于说明后置约束读取回归；不在六份样例的业务引用中。

哈希由本包实际文件计算，只验证样例文件的一致性；不是来自真实模型/图片生成工具的 receipt。
