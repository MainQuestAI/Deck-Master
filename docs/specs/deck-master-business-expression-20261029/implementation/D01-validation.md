# D01 执行与验证

日期：2026-10-30。D00 作者已明确允许进入 D01／D02a，原初判及外部模型身份缺项保留，不补造。

## 已实现

新增 Narrative.v2、business-framing.v1 能力及原子 writer floor；原 compose.v2、Plan.v2、Page.v2 保留。显式 `create --business-framing` 启用新策划，新版默认入口留给 D02b。新旧读取、结果接纳、源定位、计划绑定、顺序采用、实质修复摘要和作者沿革均已适配；无独立业务事实副本。

活动 schema 仅在 resources/contracts 编辑。既有 package-boundary 镜像检查要求合同集合一致，因此同步 document.v1 历史镜像，增加指向 canonical v2 schema 的符号链接；本商业表达套件不复制运行 schema。首次扩大回归时，该镜像集合检查发现缺项，已修正后复验。

## 真实服务级样本

以已获作者认可的 P01-A 内容为依据，由当前 Host 增补 v2 策略/主题标注，在新的本地项目完成 framing 与 argument 接纳、plan_only 完成关闭、新有界请求、覆盖两个具体 Ref 的 direction 决定、顺序采用 Narrative/Plan、大纲 packet 及 argument API 读取。三个主题为活动名单、门店执行、跟进复盘；全程 0 Page，旧请求仍关闭。

P01-A 的导出能力越前表述在新副本的节点与对应计划职责中收紧；冻结原稿未改。原始节点、替换记录、两个信封、接纳/采用回执和完整 packet 保留在本地 `deck-master-business-expression-20261030/d01-probe-r1/`；仓库只收摘要 `D01-probe-summary.json`。

这是当前 Host 对既有内容的合同标注与工程核验，新增外部模型调用 0；不当作新版自动生成质量、独立评审、作者界面体验或客户接受的证据。

## 测试与检查

- D01 原指定三文件先收集用例；现有相关四文件首次运行 59 passed。
- 新增 `test_business_framing.py`，19 项行为检查覆盖 strict v1/v2、引用完整性、旧 Host 拒绝、虚假方法绑定、只读不提级、旧 core 拒绝新指针、限定职责不重开策划、取消保护、原请求关闭后的新有界请求及两步采用间输入变化。
- 最终相关回归（19 个文件）313 passed，17.72s：新合同、content contracts、dependency slices、collaboration binding、compose phases、content plan、insight、preproduction、RC4 review、outline、package boundary、RC5 selection/catalog、RC3 content methods、design workflows/requirements、request source identity、method preparation、selective review。
- Ruff 与 `git diff --check` 通过。测试中使用明确合成的机制输入，不将测试 fixture 作为生产或 benchmark 回退。

首次新测试中的异常类型、空指针访问和 Plan projection 预期有误，已按现有真实接口修正；未放宽产品校验。业务合约仍强制注册 projection，并保留真实 Host/决定/basis/CAS 检查。

## AC 证据对应

| AC | 本次证据 |
| --- | --- |
| 01 | v1/v2 严格分派测试；argument API 实际返回完整业务框架 |
| 02 | 新 Task 能力协商、旧 Host claim 拒绝；声明新能力却返回 v1 被拒绝 |
| 03 | 旧读取 pointer 不变；首个新 Task 原子提级；旧 core 对新 pointer 只拒绝不写入 |
| 04 | framing/argument/direction 及新合同 input_revision 四项 basis；scenario/共识变化使决定与 Plan 后续采用失效 |
| 05 | 既有 RC3 内容/设计回归；write_only/speech_only/design_trial/review_only/edit 不允许显式 opt-in 重开 |
| 06 | 结果版本、冻结方法/hash/位置、来源与 Task/Plan basis 核对；取消后不可接纳；原有恢复/CAS 回归 |
| 07 | 原 plan_only 请求关闭，创建有界后续请求后顺序采用两个 Ref；中断时不混入旧 Plan；outline 读取匹配对象 |
| 08 | `D01-consumers.json` 完整清单及逐文件处理；含隐式字段和 JS 消费者 |
| 09 | `D01-contract-decisions.md` 冻结四态、content_impact.v2、API/UI 兼容规则；D05 尚未实施该分析 |

后续仍需 D02b 入口/审查选卡接线、D06 专门作者界面及 D03 真实生成接入。它们不被本次合同工程通过提前关闭。
