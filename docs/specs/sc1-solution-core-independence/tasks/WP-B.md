# WP-B｜公共方案内容内核任务卡

共同约束：代码复用优先。实际文件名和调用路径需要 Codex 核验；新增内部模块可以选用仓库惯例，但不得新增用户入口或平行状态机。生产 Agent 输出需要真实执行，不用 Fixture 规则冒充。

## B1 完整材料读取与 Context Pack v2

依赖：Q0 目标契约。
涉及：`context_intake/local_sources.py`、`context_pack.py`、资料 inventory、契约/导入验证。
实现：混合资料解析与宿主抽取；覆盖/失败范围；来源版本与精确定位；v1 兼容；来源/证据 ID 消歧；摘要仅导航。
验收：材料末尾关键约束进入 Brief；文件局部未读不会假称完整；文档/图片在同一 workflow handoff 下承接；不得向用户索取本应可读的总结。
测试：I-01—I-07。

## B2 缺口驱动研究

依赖：B1、已有阶段内动作适配。
涉及：context_intake、既有 Skill references、runtime action 投影；拟新增研究任务 helper。
实现：问题/影响对象/来源优先级/查询脱敏/预算/终态；宿主实际执行；结果进入同一 Context Pack；反证和适用边界。
验收：研究不是泛行业文章；无网络时真实报告；无结果允许 inconclusive；不得对外发送未授权客户文本。
测试：R-01—R-06。

## B3 Brief、Judgments 与证据支持纠偏

依赖：B1/B2。
涉及：`conversation/brief_compiler.py`、`narrative/judgment_builder.py`、claim map/graph/evidence gate。
实现：生产消费真实 Agent 提炼；分离事实/建议/假设/推导；证据 unreviewed 与 supported 分开；废除计数/无风险标记自证；派生值可复算。
验收：不是把 business_goal 改成“核心问题”；空 risk_flags 无证据不会通过；同数值不同口径不误判支持。
测试：S-01、S-02、S-03、S-04。

## B4 Solution Model、公共 Narrative 与 HD 方法提取

依赖：B3；A5 同时接入。
涉及：planning/narrative/advisory、`high_density/content.py`、`engine.py`、contracts、既有 decisions。
实现：方案模型；主张/取舍/组件/验收关系；候选与推荐主线；公共 narrative 唯一写入；提取而非复制高密度纯内容逻辑；旧 MBB 适配。
验收：无空 Page Package 的循环依赖；两条真实内容不同候选或单一可行路径说明；新 Run 高密度不重复问主线；旧 Run 未迁移可读。
测试：S-05—S-08、N-01—N-05。

## B5 Page Package 实质内容与 sourcing 接入

依赖：B4、A4。
涉及：`production/page_package.py`、generation task/session/handback、page_tasks/sourcing、standard build adapter。
实现：具体页结论/论据/机制/业务含义；来源适用性；none/real 两种策略；当前版本内容写入与索引完整性；客户投影。
验收：不把制作要求写成正文；标准真实消费 Page Package；不能静默掉字段；无来源页面不能用自己自证；不漏页。
测试：P-01—P-05、S-04。

## B6 方案视图、原生图形与两条 Builder 集成

依赖：B4/B5。
涉及：拟新增内部 diagram helper、Page Package visual_spec、已支持 SVG/标准后端入口、high_density adapters。
实现：四类 View、模型关系一致性、图表数据绑定、原生可编辑输出；HD 延续原生 SVG/provider/回读标准；局部变更影响。
验收：图文同源；模型不存在的节点/关系不能靠画图新增；旧 Blueprint 不伪造新 receipt；standard 无 ImageGen 能生产，HD 不降门禁。
测试：D-01—D-06、P-03—P-05、N-04—N-05。
