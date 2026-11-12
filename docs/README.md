# 文档导航

先按要完成的事情选入口。这里区分当前使用说明、拟实施目标和历史证据；
目录里的版本号或一条旧 PASS 都不能证明当前安装、最新候选或公开 Release 已通过。
包版本、源码提交、发行包、用户安装分别核验，不从文档名称推断发行状态。

## 使用 Deck Master

现行作者入口是 Rust 命令 `deck`、本机 `deck serve` 和 四个职责 Skill（[Master](../deck-skill/deck-master/SKILL.md)、[Content](../deck-skill/deck-content/SKILL.md)、[Design](../deck-skill/deck-design/SKILL.md)、[Review](../deck-skill/deck-review/SKILL.md)）。
安装与命令见 [安装说明](getting-started.md) 和 [README Quick Start](../README.md#quick-start)；已发布版本见 [1.1.3 发版说明](releases/1.1.3.md)。

1. [安装与首次运行](getting-started.md)：`scripts/install.sh`、`deck serve`、Host 与渲染依赖、已知限制。
2. [README Quick Start](../README.md#quick-start)：安装后在 Codex 里用一句话指向 `examples/first-run`，再 `deck serve` 看第一份稿。其余命令见 [commands.md](../deck-skill/references/commands.md)。
3. [Rust 重写开发稿](specs/rust-rebuild/README.md)：现行架构（Rust 核心 + deck-tools + WebUI）。
4. 已有 `legacy-export.v1` 档案仍可用 `deck import` 导入；旧 Python 工作台与官方导出器已移除，历史说明见已发布的 [1.1.0 发版页](releases/1.1.0.md#upgrade-and-migration)。

没有模型、工具或审查能力时保留实际缺口。只读演示、工程检查、实际 Host 制作、
专业认可与正式交付是不同证据，不承诺几分钟内生成任意完整成品。

## 贡献、方法与工程来源

[核心理念](product-philosophy.md)说明 Deck Master 服务讲述者的商业任务，以及内容有效加工的标准。
下一轮拟实施主题是「商业表达与专家共创改稿闭环」，版本号未定，见 [Spec 索引](specs/README.md#当前架构与下一轮拟实施主题)。
按会话与分文件包推进，采用的设计并回既有 Rust 开发稿段落，不整包入库另建第二套权威。
[2026-10-29 商业表达套件](specs/deck-master-business-expression-20261029/README.md) 仅供借鉴产品目的和追溯历史规划，
D00–D08、Narrative.v2 与 execution-index 不作为现行开工清单。

| 目的 | 入口 | 如何使用 |
| --- | --- | --- |
| 贡献和验证 | [CONTRIBUTING](../CONTRIBUTING.md)、[CI](../.github/workflows/rust.yml) | Rust、deck-tools、WebUI 和安装脚本检查 |
| 敏感安全问题 | [SECURITY](../SECURITY.md) | 按实际可用私密渠道处理，不在公开反馈中贴敏感证据 |
| Agent 工作规则 | [AGENTS](../AGENTS.md) | 与 Rust 开发稿共同确定当前架构与操作边界；AGENTS 为最高开发规范 |
| 新线 Skill | 四个职责 Skill（[Master](../deck-skill/deck-master/SKILL.md)、[Content](../deck-skill/deck-content/SKILL.md)、[Design](../deck-skill/deck-design/SKILL.md)、[Review](../deck-skill/deck-review/SKILL.md)） | 调用 `deck`；命令见 [commands.md](../deck-skill/references/commands.md) |
| 设计约束 | [DESIGN](../DESIGN.md) | 由该入口选择当前设计；旧原型和模拟按钮不证明已有服务 |
| 工程规格与依赖 | [Spec 索引](specs/README.md) | 现行架构读 rust-rebuild；旧 Narrative、writer、方法冻结与证明链已退役，不是新开发前置 |
| 发版记录 | [releases](releases/README.md) | 当前跟进与限制见 [1.1.3 说明](releases/1.1.3.md)；1.0.0 仍是准备记录 |
| 测试与审查证据 | [报告索引](reports/README.md) | 核对日期、源码 SHA、范围、未执行项及是否同一发行文件；维护者验收仅是特定版本/机器观察，不是跨环境保证 |
| 历史/归档 | [归档索引](archive/README.md) | 追溯原始决定，不能充当当前命令说明 |

[CHANGELOG](../CHANGELOG.md) 与 [ROADMAP](../ROADMAP.md) 分别承载发布记录和演进说明；
实际发布资产需另核实。未合并 PR 的文档、后续 WebUI 规格和设计样本不自动成为当前能力。

## 文档身份与历史保全

当前用户与Agent入口、继承规范、测试所需schema镜像以及现行DESIGN引用的原型保留在工作树。
时点报告、旧架构和明确被接替的评审记录收于[单一离线历史归档](history/README.md)，原路径、字节和SHA均可追溯。
测试向量与历史评价原字节迁入稳定fixtures；当前运行别名仍读取的manifest原位保留。
归档内容不是信息删除，也不证明当前实现通过。此治理方案正式应用与最终CI需要 Codex 核验。
