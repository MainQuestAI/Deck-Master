# 工程 Spec 索引

返回 [文档导航](../README.md)。本目录收录现行开发稿与历史规划，不是安装教程。
当前架构与操作边界以 [AGENTS.md](../../AGENTS.md) 和 [Rust 重写开发稿](rust-rebuild/README.md) 为准。
实施/验收状态从对应源码和实际检查确认；历史材料中的“ready”“最终”“完成”等原文
限定在其记录时点。保留历史路径供追溯和旧线维护，不据此恢复旧任务或前置手续。
2026-10-30 起 `*/contracts/` 下的 schema 副本已全部删除（85 份与运行合同逐字节相同，
审计见 [overdefense-audit-20261030](../diagnostics/overdefense-audit-20261030.md) OD-D1）；
旧 Python 线的活动 schema 只有 [src/deck_master/resources/contracts](../../src/deck_master/resources/contracts/) 一处，
旧线规格正文引用合同请直接链接该目录，不再建立副本；它不是 Rust 线的协议入口。

## 当前架构与下一轮拟实施主题

现行实现：[Rust 重写开发稿](rust-rebuild/README.md)。核心在 `rust/`，生产工具在 `deck-tools/`，WebUI 在 `frontend/` 并由 `deck serve` 提供，新 Skill 在 `deck-skill/`。切片 S0–S6 已合入；发版说明见 [1.1.2](../releases/1.1.2.md)，安装与首次运行见 [getting-started](../getting-started.md)。

下一轮主题是「商业表达与专家共创改稿闭环」，身份为**拟实施**，版本号未定。
通过会话与分文件包按切片推进，采用的设计并回既有 [Rust 开发稿](rust-rebuild/README.md) 对应段落；
本索引不挂第二套完整 spec，也不把外部分文件包整包复制进仓库作为另一套权威。

## 历史规划与旧线记录

[2026-10-29 商业表达能力套件](deck-master-business-expression-20261029/README.md) 是可借鉴的产品目的与历史规划材料，
其中 D00–D08、Narrative.v2 与 execution-index 不是当前任务队列。
下列 RC4/RC5 等材料保留已合入时点与旧线合同；旧 Narrative 合同、writer 等级、方法冻结与证明链已在 Rust 线退役，
不是新开发前置。现行边界见开发稿 §2.1；维护旧线按 AGENTS.md 第 12 节。

| 目录 | 定位 |
| --- | --- |
| [Content WebUI](deck-master-webui-content-methods-20261020/README.md) | PR130 已合入；固定版本读取、方向采用及审阅交接，原记录保留时点 |
| [RC5 content methods](content-methods-rc5/README.md) | PR127 已合入；资源目录、Host 选择及冻结方法合同，实际证据按 SHA 读取 |
| [RC4 increment](deck-master-next-iteration-20261019/README.md) | 旧线增量记录；N1–N6 台账与方法/恢复合同，报告保持原候选身份 |
| [rebuild v1](deck-master-rebuild-v1/README.md) | 旧线 src-layout 和运行核心基线；库存/镜像/示例被测试引用，不移动 |
| [Flow Quality](deck-master-flow-quality-v1.1/README.md) | 旧线内容/生产链合同与兼容样例，内含不可变项目对象 |
| [Content Collaboration](deck-master-content-collaboration-v1.2/README.md) | 旧线协作/权限/范围与审阅合同，按旧线维护范围使用 |
| [Workbench v3](deck-master-workbench-v3/README.md) | 原 W01–W12 实施输入及协议/示例；不是当前全部工作面能力清单 |
| [RC3](deck-master-v1.0.0-rc3/README.md) | 四职责与 RC3 实施/兼容基线；旧卡的开放状态不等于当前主线状态 |
| [WebUI v4](deck-master-webui-v4-20260930/README.md) | 原 UI 接线与能力合同，按 DESIGN 的现行设计源解释 |
| [Icon Quality](deck-master-icon-quality-v1/README.md) | 图标范围/契约与测试关联，保留原位 |

## 时点方案、审查与历史实施记录

以下保留以解释演进和已记录问题，不应据此重复实施或把旧验收视为新候选验收。
其中仍可能有有效约束或待处理项；是否关闭需按实际任务判断，不由本索引统一宣布完成。

- [v1 RC closure](deck-master-v1-rc-closure/README.md)
- [Deep Quality fixes](deck-master-deep-quality-fixes/README.md)
- [WebUI usability v1](deck-master-webui-usability-v1/README.md)
- [WebUI usability iteration](deck-master-webui-usability-v1-iteration/README.md)
- [2026-10-01 design alignment](webui-design-alignment-20261001/README.md)
- [2026-10-02 merged review](webui-merged-review-20261002/)
- [2026-10-18 WebUI audit](deck-master-webui-audit-20261018/README.md)

后续独立 WebUI 工作应使用其实际批准的规格；这里的历史名称或 AC 数量不能代替新任务。
RC5 方法库已由 PR127 合入；规格及旧报告中的开放状态保留原时点，不等于最终发布验收。

## 更早的架构

退役架构的 Spec 已在 [pre-rebuild archive](https://github.com/MainQuestAI/Deck-Master/blob/62dfcfc5637f0bee2358074c4458047689dd5299/docs/archive/pre-rebuild/README.md)。
旧路径、旧截图、旧测试结论用于追溯；旧 Python 线活动 schema 仍以
[src/deck_master/resources/contracts](../../src/deck_master/resources/contracts/) 为准。
