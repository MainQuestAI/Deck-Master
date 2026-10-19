# 06 可直接交给 Codex 的执行指令

## 使用方式

把完整 Spec 包提供给执行 Codex，并让它从本文件开始。下面的指令适用于用户已经要求实施本包时；当前交付仅完成开发输入，没有替用户执行产品修改、合并、发布或本机激活。

---

## 执行指令正文

你要在 Deck Master 现有架构上完成本包 N1–N6 的实现与验收，直到形成可核验的下一候选和完整交接。不要只回复计划，也不要在每个可逆开发步骤前重复请求确认。

### 一、先固定实际基线

审查基线是 a08bc68c1cbbbc806205104c2bb01f3f096305f0，当前源码版本1.0.0rc3，建议下一候选1.0.0rc4。

先读取工作区 AGENTS，检查 git status、实际 HEAD 与远端差异、工具链与安装。**需要 Codex 核验**本机实际事实；不能用本包里旧 CI 或隔离审查的通过数代替新候选结果。保留用户变更，按需要创建隔离分支/worktree，不 reset 或清理用户目录。

阅读顺序：

1. README、01-ITERATION-PLAN、02-BASELINE-AND-DECISIONS。
2. 03-ARCHITECTURE-AND-COMPATIBILITY，固定 I01–I08。
3. 04-EXECUTION-PLAN、05-ACCEPTANCE。
4. 当前执行任务卡及它明确依赖的卡，不要求先读完整历史文档。
5. traceability.json 和台账模板。为该候选建立唯一执行台账，初始NOT_RUN。

如果 main 已更新，指出影响六卡的实际差异并调整实现定位；不要把所有历史审查重做一遍。只有新的事实改变产品范围或既有用户决定时才提出具体问题，其他可执行工作继续推进。

### 二、按依赖实施

先并行推进 N1、N2、N3；N5可整理活动入口，N6可读取完整材料/既有稿并定位问题。

- N1：共用 committed/not_found/unknown resolver，普通 inputs.update 新写使用原子receipt；保持安全非UUID旧ID、旧digest和原成功外壳。新重放先于上传和材料读取。not_found 不等于可新写，仍查旧日志与log-only no-op。旧HTTP只补窄错误适配，Python只修eligibility.describe已确认快照边界。
- N2：持久安装事务，复用锁和所有权检查。支持transaction-id、KeyboardInterrupt、动作后未记状态的进程死亡、prepared/pending窗口和补偿再死亡。保护外部文件，opt-out全程不碰Host。精确重放旧事务不改变后来current。
- N3：在实际新Task producer冻结manifest和适用argument policy，首次相关写入原子提升rc4-content.v1。新argument按弱连通验证，qualification引用纳入，自环/共用来源不掩盖孤立节点。按实际review_units派发方法、稳定排序，旧Task按冻结依据读取或basis_changed正式重派。
- N4A：在N3接口稳定后增加显式work_context.v2，v1默认不变；full先完成无损等价，再做delta/manifest。有副作用的入口先协商后执行，方法/来源正文按真实bytes hash去重。
- N4B：在N1resolver稳定后优化历史查询；冷进程建立canonical覆盖，热态检查签名，新增revision增量解析。未知不能负缓存，磁盘checksum不能证明不存在，索引不可覆盖旧operations日志。
- N5：统一README/AGENTS/CLAUDE/ROADMAP/意图索引与恢复入口。四Skill共用canonical方法，合同唯一镜像保留，候选版本由集成Owner一次更新。历史资料保留时点，查清引用后才归档。
- N6：依据实际完整稿中的问题，完成至少一项实质canonical方法改进，在一项完整正常任务中使用当前方法并完成修订/适用产物复核。材料可公开或中性，实际模型应用不能由脚本答案替代。

所有修改只围绕该卡责任。不按大文件行数重构全仓，不引入新provider/数据库/引擎，不恢复PPT Master绑定。

### 三、必须保持的兼容行为

- 输入同族跨入口精确重放允许，不同族同ID拒绝；原提交结果与当前版本分开。
- 新普通no-op可创建receipt-only revision，业务basis/页/Task不变化；旧历史no-op不回填。
- 旧log-only no-op仅日志完整时可恢复；唯一证据全部丢失时不能伪造结果。
- 新持久字段对历史schema可选，对新producer必写；纯读、旧receipt精确重放、v2读取不升级项目。
- 旧writer对提升floor的项目先拒写，不能丢字段或降floor。
- 升级前真实committed Task/receipt已接纳的旧proposal，未改且当前scope/decision/CAS仍有效时，可沿原语义首次采用；新 proposal、原 proposal 改写、旧 Task 新提交、伪造旧标记及孤立对象不享受例外。
- 方法字节改变后用新Task消费，不给旧Task换hash。N4只传输N3清单。
- work_context.v2不是Taskprotocol、阅读证明或专业认可；冷会话可取完整原文，原图/正文/notes/限定不能缩水。
- 安装回滚不自动意味着项目可由旧writer继续编辑。

### 四、测试与真实任务

每张卡优先运行聚焦正反例，保存实际状态和字节证据。N1/N2/N3/N4 的机械验证可使用明确标注的合成项目；N6需要实际Host输出与完整约定产物。

沿现有CI完成候选必要的单元矩阵、renderer、required browser、installed wheel和offline职责。测试命令与环境按当前仓库核验，不以skip掩盖必要工具缺失。每次变更后仅补受影响回归和必要对照，足够后进入交付。

正常任务只完成已约定范围：content_only交完整内容包，full_deck交实际PPT与适用预览/notes。不恢复固定Frozen A/B、听众人数、真人计时、默认人工签字。真实独立前审在本次既有政策要求时保持，由实际非作者执行，换Skill名字不算独立。

如果确实缺少必要模型/渲染能力，把受影响AC标BLOCKED或NOT_RUN，说明具体缺口，继续完成其他已授权研发。没有新客户材料时优先用完整公开/中性材料。不能只交空台账或工程PASS就关闭N6。

### 五、提交与交接

代码、方法与文档同步git，遵守仓库既有DCO/提交规则。按04的文件所有权避免多个Agent同时修改service/method_resources的同一段。跨卡接口变更必须同步消费者和本包。

最终给用户：

1. 具体改了什么、为什么，以及对使用流程的影响。
2. 准确候选SHA/tree、版本和可取得的构建包。
3. 70条增量AC的唯一台账、真实验证命令与结果、失败修复及未执行项。
4. 新旧操作、Task/方法、writer、v1/v2、安装恢复的兼容说明。
5. N6具体问题、方法diff、真实稿件与适用产物、修订和复查结论；没有可比首稿则不声称数字提升。
6. 当前安装与发布状态、已知限制和后续动作。

先完成可审阅候选和证据。只有当时已经获得对应授权，才推送/合并、发布tag/Release或激活用户实际HOME；没有这类授权不影响其余实现与验收，也不把未发布写成产品代码失败。

结论区分“工程候选完成”“六项迭代全部完成”“公开发布完成”“本机激活完成”。不得以其中一个替代其他事实。

---

## 执行者首次反馈格式

开始后简要报告实际SHA与基线差异、环境缺口、当前任务/并行分工和已建立的台账位置，然后直接推进。不要把首次反馈变成新的方案审批。

## 中途出现新问题时

说明具体证据、影响哪条AC、能继续哪些工作以及推荐动作。可以在既有授权范围内自主解决实现细节；涉及新的产品取舍或原本就缺失的用户决定时，完成不受影响部分后提出具体可审阅选项。

