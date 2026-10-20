# 验证与审查报告索引

返回 [文档导航](../README.md)。本目录保存时点证据，不是自动更新的当前产品状态页。
读报告先看源码 SHA、日期、执行环境、命令、输入、适用范围、失败/未执行项；
只有相同候选身份的证据可以直接用于该候选。主线合入、发行、用户环境激活分别记录。

| 记录 | 范围与保留原因 |
| --- | --- |
| [RC4 iteration ledger](rc4/iteration-20261019/README.md) | AGENTS 关联的 N1–N6 时点台账、恢复/安装/方法/内容证据；旧包哈希保持原义 |
| [RC4 native review Host record](rc4/native-review-normal-host-20261019.md) | 实际正常 Host 路径的历史观察，不是全平台或普遍质量保证 |
| [RC3](rc3/) | 各卡、安装、原生图像/备注、收口与恢复记录；开放 PR/兼容测试仍可能依赖，不搬移 |
| [Content collaboration](content-collaboration-v1.2/) | 协作实现与审阅证据，按各记录指定版本解释 |
| [PR108 review](pr108-review-20261013.md) | 单次评审结果，不是当前未修缺陷总表 |
| [Controlled collaboration audit](controlled-collaboration-audit-20261012/) | 注册的历史审查记录；保持原路径和字节 |
| [Skill flow review](skill-flow-review-20261012/README.md) | 历史职责链检查；不作为新入口独立性证明 |
| [Workbench v3 execution](workbench-v3-execution-20260926/README.md) | W系列工程/浏览器/安装证据，含冻结设计快照 |
| [WebUI/backend feasibility](webui-backend-feasibility-20260926/README.md) | 当时的可行性分析，不是当前发布清单 |

其他证据位于 [docs/qa](../qa/) 和 [docs/reviews](../reviews/)，保持原路径。
[设计来源](../../DESIGN.md) 决定当前设计约束；报告附带原型/截图只是其时点观察。
需要查已退役架构请去 [归档索引](../archive/README.md)。

## 引用规则

- 链接到原报告并标出日期/SHA，不把数字搬到“当前全部通过”的结论中。
- 不修改原测试日志、raw产物、hash索引或不可变对象来消除历史失败。
- 原始材料不在仓库时明确不可复核，不能用索引本身代替读过原稿。
- 新候选、后续修复与未合入 PR 应形成自己的证据，不覆盖旧记录。
- 文档导航的整理不关闭开放任务，也不签发专业认可或正式发布。
