# 来源、证据边界与本地待核验

**本包以用户提供的SC-1 Spec及PR #30固定SHA为依据。目标架构/新增接口/测试阈值属于本轮建议与约束，不是声称当前已经实现。**

远端代码是静态读取，不是完整checkout运行。尝试取得源码归档未成功，因此没有在本环境复跑产品测试；后续全部本地文件/安装/能力/测试/效果需要Codex核验。此前历史P2—P5评估不是本轮实现基线。

| 标识 | 来源 | 支持范围 | 证据等级 |
|---|---|---|---|
| R01 | [PR #30 metadata](https://github.com/MainQuestAI/Deck-Master/pull/30) | 本次在线读取HEAD=4977f89573d18a282c605360dc55f751443a2b21；open/unmerged，base=bcb5b37；PR正文中间HEAD和作者测试数字不作本次实测。 | 本次连接器读取 |
| R02 | [scripts/skills/installer.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/skills/installer.py#L1408-L1436) | install_managed_backend仍接受完整源包并提示backend bind。 | 本次连接器固定SHA读取 |
| R03 | [scripts/runtime/build.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/runtime/build.py) | 生产路径仍关联外部builder_backend；Package消费者要求ready，准备manifest与当前source fingerprint。 | 本次连接器固定SHA读取 |
| R04 | [scripts/high_density/pptx.py compile_pptx](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/pptx.py) | 编译函数以本地SVG/Scene/ContentLock生成原生Presentation及trace；路径提取和整体运行仍需Codex核验。 | 同对话上一轮已读取同SHA；本次补读同文件回读部分 |
| R05 | [scripts/high_density/pptx.py readback/render](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/pptx.py#L990-L1175) | 实际soffice/pdftoppm渲染调用、对象类型/文字/trace/几何和hash回读。 | 本次连接器固定SHA读取 |
| R06 | [skills/deck-builder-high-density/references/stage-protocol.md](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/skills/deck-builder-high-density/references/stage-protocol.md) | 既有MBB/ImageGen/Scene/SVG/PPTX阶段、原生对象/视觉指标与真实工具要求；不是已通过的效果报告。 | 本次连接器固定SHA读取 |
| R07 | [scripts/runtime/next_step.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/runtime/next_step.py#L1-L235) | HD目录优先分支、ppt-master missing项、缺semantic时quality command选择。 | 本次连接器固定SHA读取 |
| R08 | [scripts/deck_master.py library args](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/deck_master.py#L3045-L3070) | 共享library choices当前只有auto/real/fixture。 | 本次连接器固定SHA读取 |
| R09 | [docs/contracts/page-package.v1.schema.json](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/docs/contracts/page-package.v1.schema.json#L1-L150) | status枚举含ready_for_build而非ready；实际消费者差异需用调用链复现。 | 本次连接器固定SHA读取 |
| R10 | [scripts/quality/gate_policy.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/quality/gate_policy.py#L1-L130) | semantic gate接受external_*前缀；语义input_current检查index hash。 | 本次连接器固定SHA读取 |
| R11 | [SC-1 implementation/deviation-log.md](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/docs/specs/sc1-solution-core-independence/implementation/deviation-log.md) | HD公共投影、问题类型和action调用方接线等偏差记录；状态以实际代码/测试为准。 | 同对话上一轮已读取同SHA；本次PR metadata再次提及欠项 |
| R12 | [scripts/workflow/actions.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/workflow/actions.py#L1-L265) | staging后逐文件rename、applied marker、scope声明与预算计已提交；不能仅靠docstring证明批次原子。 | 本次连接器固定SHA读取 |
| R13 | [scripts/high_density/svg_native.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/svg_native.py) | 已有共享SVG parser、path/transform/use支持子集；与旧prose存在需核对范围。 | 同对话上一轮已读取同SHA |
| L01 | 用户提供 SC-1 完整 Spec 与 88 项验收（原 ZIP 附件） | 读取原规格D04/D05/任务与原88项JSON；继承效果阈值并逐项映射，不使用过时P2—P5材料替代。 | 本次从附件本地读取 |

## 本地必须核验的事项

实际HEAD与当前PR状态、未提交改动、compiler依赖闭包/许可、所有核心schemas和consumer状态值、安装launcher与release内容、宿主工具观测接口、OS/Python/字体/renderer、原生编辑软件、真实生成与视觉质量、旧Run和客户资产位置、所有测试命令及结果。

## 来源优先级

用户本次明确纠偏→本包正式替换条款→原SC-1未冲突要求→固定SHA源代码事实。代码当前如何实现不决定产品必须继续如此；旧规格中已被撤销的backend身份不能继续当不可改变约束。

## 审查边界

本包不是完整PR30 code review，也不宣布PR30可合并；所列静态接线问题用于形成增量实现目标，确定性复现和本地修复需要Codex核验。Schema自检只证明四个目标窄合同及样例的结构，不证明底层图形引擎、真实性、安全性或交付能力。
