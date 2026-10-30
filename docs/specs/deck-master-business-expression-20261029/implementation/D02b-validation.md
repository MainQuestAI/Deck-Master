# D02b 选卡接线与验证

2026-10-30：工程接线已实现，缩小后的上下文真实模型内容验证运行中，工作单元保持进行中。D02 整卡、D06a 及 I1 专业验收未关闭。

## 实现范围

新版包以 Task 的 `business-framing.v1` 能力隔离。framing 自动冻结来源规则、内容方法、选择指引与 M01；argument 的起步包含 M02／M07／M08，Host 可在派发前按具体任务选 M03／M04／M05 等。不是全卡加载，不要求普通作者选择方法编号。新合同目前仍通过 `create --business-framing` 启用；旧调用不静默切换协议，新作者入口由 D06a 接入。

独立读取可显式选择新版包，项目准备从实际 writer floor 推导，不能用准备请求覆盖项目合同。CLI `methods --business-framing --phase framing|argument --read`、Skill reader（含 work_context.v2）、准备 handoff 和实际派发使用同一 selector。已有 Task 始终读取原 manifest；字节漂移正式退役重派，保留原对象与调用事实。纯写稿、口播及已有确认稿不被默认重开策划。

大纲 dispatch、完整前审 dispatch、native review、CLI 与 `/api/reviews/native` 贯通 `selected_resource_ids`；HTTP 同时支持已有 outline subject。未知／越范围选择在原生会话启动前拒绝，pending／recovery 不接收补卡，恢复沿原 Task 与方法清单完成。新版内容审查 Task 协商框架读取能力，完整 packet 仍携带材料全文、任务事实、Narrative、Plan 及本次 Page，不用作者自评代替材料。native 的可信执行、收据及取消／晚到保护沿原路径，未引入新审批或自签身份。

修改三份角色入口及 canonical content-methods 的重复必读表述：实际 Task 以冻结 manifest 为准，例子按缺口选择，catalog 的 input／after／walkthrough 依赖完整展开。没有修改 HOME Skill 或安装入口。未新增平行方法账本或运行 schema。

## 实际字节与服务级探针

[完整依赖字节](D02b-method-bytes.json) 使用实际 reader 返回的 UTF-8 全文，含全部 catalog 依赖；保持 R2 的两份任务和显式选卡。

| 组合 | R2 实际方法字节 | D02b 当前方法字节 |
| --- | ---: | ---: |
| 两样本 framing | 47,962 | 29,127 |
| 会员首提 argument | 68,616 | 49,781 |
| 售后竞标 argument | 73,100 | 54,265 |

差异主要来自按新版能力取消普遍携带的 19,036 字节案例索引，canonical 指引同时增加了条件说明。不是 token、时长或总提示节省，也不能据此宣称内容质量不降。必要来源／协议仍在；显式选用的完整案例及其依赖仍全量返回。

[零调用服务探针](D02b-probe-summary.json) 由当前 Host 将已获作者认可的 P01-A 标注为 v2，在新本地项目实际冻结新版 framing／argument、读取全部方法、claim／accept，完成 plan_only／closed、0 Page、未采用。默认 framing 实际 29,127 字节，argument 最小包 39,977 字节；它不含上述任务按需添加的 M04／M10，不能混为同一比较。该探针证明接线与合同可运行，不是新模型生成、独立评审、作者新结论或正式采用。

## 工程验证

- 开工收集 D02 指定四文件：43 项用例。
- 既有相关八文件首轮：121 passed，9.87s。
- 23 文件相关回归：380 passed，34.50s，包含新增测试最初 15 项。此后只补充行为检查，新增文件最终 19 passed；覆盖完整案例依赖、新项目准备与派发一致、字节漂移正式重派、原生完成观察恢复且不重复调用。
- 新检查还覆盖旧任务不改、新包自动起步、后续 Host 选卡、CLI 与 work_context.v2、完整框架 packet、HTTP outline 选卡、非法选择零调用拒绝及 pending 不补卡。原生测试全部使用明确合成 transport，仅为工程机制证据，不冒充独立模型判断。
- 首轮新检查有 5 处测试输入／预期错误：未建立临时父目录、误用 packet.sources（实际是 materials）、误把 catalog 合法的 content-to-visual 当成越范围资源。按真实接口修正测试，未放宽产品校验；越范围用实际不允许的 template-page-draft 验证。
- 修改代码、测试与拟议校准 runner 的 Ruff 通过；`git diff --check` 通过。未运行渲染、PPT 导出或作者 UI 验收。

## 仍需完成

R2 的真实内容使用原完整包；本单元的 v2 和缩小上下文改变了模型实际输入，因此不能将 R2 的内容改善直接记作本单元效果通过。作者已明确回复“分配 4 次验证 D02b”，`D02b-call-plan.json` 单独冻结同两份任务各 framing＋argument、累计 28／32，只用现有订阅、零新增 API 费用、不自动重试。授权前实测 runner 会在建项目和消耗请求前拒绝；授权后按该冻结计划运行，不启用留出。

D02-AC01／02／04／05／07 有工程证据；AC03 的具体方法作用与 AC06 的完整审查输入已有接线及机制证据，真实模型内容验证保持未完成。AC08／09 沿 D02a 保留方法返回与效果、字节与内容的区别；接线后仅完成字节核对，内容结论待上述校准。D02 整卡不关闭，D06a 依赖关口不提前通过。

原始探针位于本机 `deck-master-business-expression-20261030/d02b-probe-r1/`，含原始信封、方法全文、接纳回执及 audit 源文件。仓库只保留去除本地路径的摘要。原 I0、R1、R2 全部运行和冻结快照保留；后续 canonical 字节变化不改写历史调用证据。
