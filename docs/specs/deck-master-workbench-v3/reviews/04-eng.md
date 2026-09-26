# AutoPlan 第3阶段：工程评审

冻结输入：autoplan-eng-kh0Tvp/eng-implementation.md，SHA256 `86d19054898c330f636b52283dbe38b31b79ef4a6bc157303b1a2fb4283a5be2`。方法全文2156行已读。原生审查完整INPUT匹配；用户中断后在同一冻结输入恢复，未重置已完成阶段。

## Scope Challenge 与现有实现

保留用户完整范围，按M1a/M1b/M2/M3交付，一张卡一次。核心对象新增仅为原系统缺失的语义，不另设模型执行器、调用账或新UI事实源。

| 需求 | 已读源码/测试 | 复用与新增 |
|---|---|---|
| 原子写/历史 | store.py:_commit_locked、test_store_transactions.py | 复用对象不可变、项目锁与current最后切换；新增长期operation receipt及故障恢复 |
| 局部正文/失效 | editing.py:255–280 | 复用page hash/design校验、历史operation查找；扩充原图适用性与候选采用 |
| 固定读取 | view.py:20；web.py | project_view已有revision；Web透传及按页/摘要新投影 |
| Host结果 | tasks.py:1056、test_tasks.py | 复用Task/call allowance与取消晚到；新增result_refs与请求Attempt绑定 |
| 安全 | web.py:107–147 | 已有所有GET的Host检查、Origin及X-Deck-Token；新路由继承，不能宣称从零补防线 |
| 输入变化 | test_review_round3.py | 既有inputs会因有序页/正文变化拒绝旧结果；扩充大纲/来源显示 |
| 导出 | editing.py:282、test_export.py | 复用共享门控；新增固定revision及engineering、明确review兼容变化 |

复杂度检查：W06按核心和Web两连续改动即可，不为租约/hold另造调度器。UI个人状态单独可恢复journal，不进入业务revision，不成为执行事实。合成Host仅作测试，不是第二生产执行器。

## 双声音结果与处置

原生：5项（2 P1、3 P2），全部纳入。外部：18项，完成且格式有效；完整原文及modelUsage保存在04-eng-outside.md/.json。外部模型claude-opus-5-5，session67f43fbe-3941-4e8f-a14c-3e0323d8a076；原生模型身份未由工具返回。

| 维度 | 原生 | Claude Code | 共识 |
|---|---|---|---|
| 架构 | operation/基准缺口 | launcher/UI状态/竞争 | CONFIRMED：需补确定契约，具体措施有差别 |
| 测试 | 崩溃/并行/文字/规模 | 状态交错/安全/升级 | CONFIRMED：新行为需新增自动验证 |
| 性能 | 300页与资源边界 | 缩略图/摘要/装配 | CONFIRMED：现计划需量化 |
| 安全 | 现防线存在，继承回归 | 误称Host/token缺失；另提注入/metadata | DISAGREE：按源码保留现防线，增加新风险测试 |
| 错误恢复 | 动态端口/幂等 | UI-state/心跳 | CONFIRMED：需恢复明确；不采用心跳提案 |
| 部署 | 未独立评价 | launcher/Skill矩阵 | N/A：不冒充双声共识 |

共识4/6；1分歧由源码判定；1未共同覆盖。没有双方要求削减用户范围的User Challenge。

| ID | Finding / 置信度 | 自动决定与原因 | 验证/owner |
|---|---|---|---|
| N1 | 长期幂等缺崩溃协议，9/10 | 同次业务revision可达receipt，锁内查重，索引可重建；现editing历史查重可复用而非推翻Store | W06跨3崩溃点+插入写入再重放 |
| N2 | candidate基准混用，9/10 | 生成basis与采用CAS分开；无关变化只重新plan | W07并行/同页竞争/内容变化 |
| N3 | 动态origin丢草稿，10/10 | 项目UI journal+浏览器临时缓冲；只对服务确认过草稿承诺跨端口恢复，离线尾部下载/导入 | W03/W05/W06换端口 |
| N4 | 文本索引跨语言错位，10/10 | 原始Unicode codepoint左闭右开，JS映射，excerpt核对，不隐式规范化 | W06中文emoji/组合/CRLF |
| N5 | 性能阈值未定，9/10 | 300页多候选Attempt，预定p95/并发/cache/heap约束 | W01/W04压力 |
| E1 | launcher拓扑缺失，8/10 | 采用独立轻量registry服务；拒绝“生产launchd固定5050”无证据断言 | W03生命周期/身份 |
| E2 | DNS rebinding无防线，2/10 | 不成立，web.py已有Host拒绝；新GET继承与回归，不新造读token产品 | W03伪Host |
| E3 | Cookie跨端口，2/10 | 当前X-Deck-Token无Cookie，保留instance隔离，不引入Cookie | W03跨服务token拒绝 |
| E4 | 已查看推高业务revision，9/10 | UI-state独立journal，读取业务对象不写 | W03/W05 |
| E5 | 自动生产与试作争用，7/10 | 不加page hold，比较固定对象不变，采用CAS/replan；按现生产规则合法current变化如实显示 | W07竞争；避免强制人工逐页审批 |
| E6 | 交接自由文本注入，8/10 | 数据与可执行动作分开，引用材料不可信；Skill只执行核心枚举动作，禁止把材料shell当命令 | W02/W06注入样例 |
| E7 | 审阅metadata泄露，8/10 | 检查PNG/SVG/PPTX含隐私元数据，输出清理副本，canary；不改immutable原件、不盲删用户可读内容 | W11 |
| E8 | SVG内联命中攻击面，8/10 | 安全图像渲染+已有稳定ID几何映射；无法映射用rect；不建设主动iframe脚本桥 | W05/W06 |
| E9 | 粗revision导致冲突，8/10 | 摘要增量ref/cache，目标basis判定，commit仍锁内CAS，不采纳删除原子项目CAS | W01/W06/W07 |
| E10 | 装配风暴，7/10 | 采用只标失效不启动装配；沿核心continue/明确继续制作绑定有序快照，一活跃任务去重 | W07/W10 |
| E11 | 缩略图派生缺口，8/10 | 新图后台派生、旧图渐进；project/hash/variant缓存，冷暖分开 | W04 |
| E12 | 新增心跳/lease，5/10 | 不采纳新调度协议，保留30分钟提示与取消重交接；未知调用不自动重发 | W10测试睡眠后未知状态 |
| E13 | Skill矩阵，8/10 | 明确新旧协议兼容矩阵；已支持rebuilt项目正常读，新writer向前补可选数据；pre-rebuild旧格式拒绝写 | W02/W12 |
| E14 | 状态交错需确定测试，9/10 | 脚本化fake Host通过公共CLI，固定seed交错；区别真实Host证据 | W06/W07 |
| E15 | 恢复page需incarnation，4/10 | 不增加身份维度，沿page_id+task_id+固定ref，取消terminal任务不复活，新操作新task | W09/W11删除后恢复晚到 |
| E16 | 自动/手动GC，6/10 | 本期不加删除不可变历史，展示磁盘占用；候选“放弃”仅逻辑状态，回收待后续明确授权 | 后续TODO，不削本次功能 |
| E17 | 历史派生复用，6/10 | 可复用已验证完整依赖相同对象；不能凭原图hash绕过设计/检查依赖，缓存不是完成门槛 | W07/W11 |
| E18 | registry竞态，9/10 | 锁+原子写，last activity留UI-state | W03 |

## 架构

```text
launcher registry+身份 ──启动/复用──→ 单项目HTTP(/v2/)
                                      │只调用shared Service
CLI / Host Skill ────────────────────┤
                                      ↓
              Document / Store锁 / immutable objects / current CAS
                  ├─ContentPlan/Page/source refs
                  ├─Task + call ledger ← request + Attempt
                  ├─ChangeSet + committed operation receipt
                  └─Candidate → 显式采用 → 当前产物/下游失效
投影view ──summary/hash按需──→ ES Modules UI
个人草稿/已查看/位置 ─→ project UI journal（独立sequence，不驱动生产）
固定revision ─→ shared check → 审阅/交付/工程包
```

共享schema/核心/CLI/Skill先main，再同步前端。依赖卡索引已经无环。按项目规则串行一张卡，无并行实施lane；可并行独立只读评审，但不得同时改shared models/tasks/view。

安全保持loopback/Host/Origin/token/路径白名单/SVG隔离。新风险是启动器注册与导出内容，因此新增输入边界与元数据回归；不增加账号平台或远端访问。

## Code Quality

1. 失效传播不可在前端与候选Service各写一份；沿editing/tasks共享核心，前端展示影响计划。W07明确唯一判定入口。
2. GenerationRequest冻结输入与Attempt调用事实分开，但调用配额/结算继续唯一Task账；禁止影子用量表。
3. UI draft journal只做恢复，命名与operation receipt分开，不能被误当已提交请求。
4. export仍扩展editing.export_project，不规划不存在的export.py；静态资源是resources/static。DESIGN错误路径已修正。

## Test review

已逐段读取store、editing、view、tasks与五个既有测试文件。完整分支图、每包输入→断言、EXIST/GAP、E2E/EVAL、故障表见[测试计划](04-eng-test-plan.md)，并保存到gstack项目的eng-review-test-plan文件。12个新功能域均有待实现测试族（不是只有两轮人工演示）。基础回归来自已授权保护条件，不重新请求删减授权。

## Performance

摘要不得遍历全部图像bytes；按revision/ref缓存小型投影，详细prompt/attempt分页按需。图像以project+hash+variant缓存，6下载/2解码，60缩略图/4大图上限。300页×5candidate×3attempt固定样本；warm summary p95≤250ms、30页首屏可操作≤2s、20min稳定段heap增长≤20%。冷派生单独记录，不能拿合成SVG prototype的速度代替真实大图。

## NOT in scope / TODO

本轮不加独立执行器、远端协作账号、自由排版、外部PPT回写、自动GC、心跳租约或page hold。用户原有完整范围仍保留。全原图优先策略、自动风格评分、多Host连接在TODOS已有说明；历史blob回收仅补后续候选方向，不执行删除。

## Implementation Tasks

- EN1 P1：W06 durable operation receipt + crash/replay + UI journal恢复边界。
- EN2 P1：W07生成basis与采用CAS分开、固定比较、自动生产竞争及批量原子。
- EN3 P2：W03 launcher拓扑/registry写锁/实例token/换端口恢复。
- EN4 P2：W06文本codepoint/选区转换/不可信交接输入。
- EN5 P2：W01/W04缩略图渐进、分页缓存、300页资源阈值。
- EN6 P2：W11导出metadata/privacy与固定版本、旧项目协议/删除恢复安全回归。

## Decision ledger / Completion Summary

上述N1–N5与E1–E18均按用户AutoPlan请求自动决定；事实修正以现代码为准；无新待用户选择。Approval readiness: PASS（仅设计方案与验收要求的自动决定，不是生产发布授权）。
Scope accepted as-is。Architecture 3项；Code quality 4项；Tests 12个新测试族；Performance 2项。未分配且无错误处理要求的critical gap 0；所有新实现证据未取得。顺序实施1lane、0并行实施。Lake Score N/A（未做覆盖删减选择）。外部completed18、原生completed5，共识4/6。NOT scope/复用/故障表/测试artifact均已保存。实施仍需逐卡验证，不能据计划评审放行发布。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | AutoPlan CEO | 产品范围 | 1 | 完成 | 原生5，外部格式无效 |
| Outside Review | Claude Code / ENG | 独立挑战 | 1 | completed | 18项已逐条处置 |
| Eng Review | AutoPlan ENG | 架构与测试 | 1 | issues_open（工作已落卡） | 21组工程/测试要求；实现未验收 |
| Design Review | AutoPlan Design | UI动线 | 1 | 完成 | 初始6→8 |
| DX Review | AutoPlan DX | 开发接入 | 1 | 完成 | 6.0→7.9 |

**OUTSIDE COVERAGE:** CEO unavailable；Design/DX/ENG completed，不能把后三阶段补算CEO覆盖。
**CROSS-MODEL:** ENG共识4/6；安全现状按源码纠正；原生模型身份未知。
**VERDICT:** 设计与开发契约可继续最终走查；未获得生产实现/发布CLEAR。
NO UNRESOLVED DECISIONS
