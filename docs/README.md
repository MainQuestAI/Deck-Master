# 文档导航

先按要完成的事情选入口。这里区分当前使用说明、继承的工程合同、候选方案和历史证据；
目录里的版本号或一条旧 PASS 都不能证明当前安装、最新候选或公开 Release 已通过。
包版本、源码提交、发行包、用户安装分别核验，不从文档名称推断发行状态。

## 使用 Deck Master

1. [安装与首次运行](getting-started.md)：依赖、Host 要求、安装验证、只读示例与升级。
   先用明确标注的只读示例理解界面；它不调用模型，也不代表真实制作验收。
2. [README Quick Start](../README.md#quick-start)：有实际材料与外部 Host 时的任务流程；
   Task ID、结果与授权必须来自真实执行，不能直接粘贴占位符或把复制交接当作模型调用。
3. [任务索引](agent-task-index.md)：按内容、设计、审查、续作、修改、导出找到当前命令。
4. [恢复手册](agent-recovery-playbook.md)：缺工具、冲突、未知回执、中断和历史版本的处理。
5. [迁移说明](migration-to-rebuilt-core.md)：旧项目与旧命令的边界；不在旧 run 上直接初始化新格式。

没有模型、工具或审查能力时保留实际缺口。只读演示、工程检查、实际 Host 制作、
专业认可与正式交付是不同证据，不承诺几分钟内生成任意完整成品。

## 贡献、方法与工程来源

| 目的 | 入口 | 如何使用 |
| --- | --- | --- |
| 贡献和验证 | [CONTRIBUTING](../CONTRIBUTING.md)、[现行 CI](../.github/workflows/rebuild.yml) | 按修改范围运行必要检查；旧日志不能替代候选检查 |
| 敏感安全问题 | [SECURITY](../SECURITY.md) | 按实际可用私密渠道处理，不在公开反馈中贴敏感证据 |
| Agent 工作规则 | [AGENTS](../AGENTS.md) | 开发任务路由与安全边界，不是用户安装教程 |
| 四职责入口 | [Skill resolver](../skills/RESOLVER.md) | Master / Content / Design / Review 共用方法源与 Runtime |
| 运行时 schema | [活动合同目录](../src/deck_master/resources/contracts/) | 唯一活动 schema 来源；历史镜像不得反向覆盖 |
| 设计约束 | [DESIGN](../DESIGN.md) | 由该入口选择当前设计；旧原型和模拟按钮不证明已有服务 |
| 工程规格与依赖 | [Spec 索引](specs/README.md) | 先读分配任务所需的增量和继承合同，不按全部历史卡重新实施 |
| 测试与审查证据 | [报告索引](reports/README.md) | 先核对日期、源码 SHA、范围、未执行项及是否同一发行文件 |
| 历史/归档 | [归档索引](archive/README.md) | 追溯原始决定，不能充当当前命令说明 |

[CHANGELOG](../CHANGELOG.md) 与 [ROADMAP](../ROADMAP.md) 分别承载发布记录和演进说明；
实际发布资产需另核实。未合并 PR 的文档、后续 WebUI 规格和设计样本不自动成为当前能力。

## 文档身份与历史保全

当前用户与Agent入口、继承规范、测试所需schema镜像以及现行DESIGN引用的原型保留在工作树。
时点报告、旧架构和明确被接替的评审记录收于[单一离线历史归档](history/README.md)，原路径、字节和SHA均可追溯。
测试向量与历史评价原字节迁入稳定fixtures；当前运行别名仍读取的manifest原位保留。
归档内容不是信息删除，也不证明当前实现通过。此治理方案正式应用与最终CI需要 Codex 核验。
