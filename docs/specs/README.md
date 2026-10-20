# 工程 Spec 索引

返回 [文档导航](../README.md)。本目录是版本化的开发输入和继承合同，不是安装教程。
实施/验收状态只能从对应源码、候选台账和实际检查确认；“ready”“最终”“完成”等原文
限定在其记录时点。保留路径以兼容测试、schema 镜像、冻结清单与开放任务，不批量搬移。

## 当前主线使用的增量与继承合同

| 目录 | 定位 |
| --- | --- |
| [RC5 content methods](content-methods-rc5/README.md) | PR127 已合入；资源目录、Host 选择及冻结方法合同，实际证据按 SHA 读取 |
| [RC4 increment](deck-master-next-iteration-20261019/README.md) | 继承的增量入口；N1–N6台账与方法/恢复合同，报告保持原候选身份 |
| [rebuild v1](deck-master-rebuild-v1/README.md) | src-layout 和运行核心的继承基线；库存/镜像/示例被测试引用，不移动 |
| [Flow Quality](deck-master-flow-quality-v1.1/README.md) | 内容/生产链继承合同与兼容样例，内含不可变项目对象 |
| [Content Collaboration](deck-master-content-collaboration-v1.2/README.md) | 协作/权限/范围与审阅合同，不能因名称版本较旧而废弃 |
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

退役架构的 Spec 已在 [pre-rebuild archive](../archive/pre-rebuild/README.md)。
旧路径、旧截图、旧测试结论用于追溯；活动 schema 仍以
[src/deck_master/resources/contracts](../../src/deck_master/resources/contracts/) 为准。
