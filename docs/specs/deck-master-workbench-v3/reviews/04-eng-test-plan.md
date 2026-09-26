# 工程验收与回归计划

2026-09-26；代码基线 cad56e0；分支 codex/generation-workbench-spec；仓库 MainQuestAI/Deck-Master。
本文件规定未来实施所需证明。本轮仅阅读既有测试并验证合成原型，没有执行新功能或真实 Host 验收。

## 已有覆盖与新覆盖图

标记：EXIST=已读到既有行为测试；GAP=新功能测试待实现；→E2E=真实服务浏览器；→EVAL=真实生成结果人工与规则复核。EXIST不表示本轮运行通过。

```text
工作台入口 W03 → registry / create / service identity
 ├─ EXIST test_web.py: 自动启动、复用、跨入口revision一致
 └─ GAP test_workbench_entry.py: 空registry/坏路径/旧格式/创建冲突/服务换端口/无Host →E2E
链路 W01/W02 → Document / ContentPlan / request / attempt / artifact
 ├─ EXIST test_tasks.py: envelope/晚到/幂等/异payload拒绝
 ├─ GAP test_workbench_projection.py: 历史只读/缺对象/未知prompt/乱序结果/字段兼容
 └─ GAP test_generation_requests.py: 调用前冻结/多attempt/能力缺失/hash不符/证据冲突/无回执
画廊与单页 W04/W05 → 摘要 / 按页 / 固定比较
 ├─ EXIST prototype/validation: 仅合成交互 smoke（不是正式Web）
 └─ GAP test_workbench_browser.py: 同层不替代/过滤外选页/键盘/缩放/焦点/1280与1440/300页 →E2E
意见 W06 → 原始对象坐标 / change plan / operation / task
 ├─ EXIST test_store_transactions.py: objects/revision/pointer崩溃、CAS、read_set
 ├─ GAP test_workbench_annotations.py: scope条件/rect变换/text codepoint/excerpt/同页多意见
 └─ GAP test_change_operations.py: all-or-none/双击/失联/跨崩溃与其他写入后重放/同ID异payload →E2E
候选 W07 → 冻结请求 → Host → candidate → adoption
 ├─ EXIST test_tasks.py: 取消晚到仍结算但拒绝覆盖
 └─ GAP test_candidate_adoption.py: 两类基准/无关revision/同页竞争/批量零或全/仅目标失效 →E2E
风格 W08 → 参考固定图 + 保留目标内容 + 一句要求
 └─ GAP test_style_recipe.py: 引用角色/未知prompt/冲突/试1页再扩/失效参考 →EVAL
内容 W09 → inputs / content_update / lineage
 ├─ EXIST test_review_round3.py: 重排删增改使旧input任务失效，调用事实不回滚
 └─ GAP test_workbench_content.py: 大纲映射/缺来源/合并拆分新ID/正文草稿/上传≠读取 →E2E
恢复 W10 → journal / operation query / task lifecycle
 └─ GAP test_workbench_recovery.py: 断线退避/隐藏暂停/30分钟边界/取消重交接/双方冲突/离线草稿恢复 →E2E
交付 W11 → 固定revision → shared checks → file
 ├─ EXIST test_export.py: review/delivery/未完说明/门控/专业证据未知
 └─ GAP test_versioned_export.py: review兼容变化/engineering/并发新结果不换文件/敏感内容/恢复新revision →E2E
安装 W12 → wheel/sdist / assets / skill / supported Python
 └─ GAP test_workbench_package.py: 无外网资源/字体license/干净安装全部脚本/回退旧UI同兼容core →E2E
```

## 每包可执行断言

| 卡 | 必须测试的分支与期望 | 方法/文件 |
|---|---|---|
| W01 | 当前与固定历史各自正确；空页/坏引用局部错误；旧字段保留；缺实际prompt不得补造；读不提交 | test_workbench_projection.py，单元+服务 |
| W02 | request冻结后不可变；Attempt追加；协议不支持在调用前拒绝；hash差异不作为匹配候选；晚到只记事实 | test_generation_requests.py，契约+真实Host一次绑定 |
| W03 | 新建/打开/取消/路径冲突/旧项目/Host缺席；伪服务身份拒绝；端口变化后读项目侧已同步草稿 | test_workbench_entry.py，服务+浏览器 |
| W04 | 原图/SVG/PPT层不串；缺图/坏图可继续；筛选保留选择；300页压力、网络/解码上限、无外部请求 | test_workbench_browser.py，→E2E |
| W05 | 固定比较不追current；未知实际prompt明确；正文/意见/选区不串页；来回和刷新位置保留 | 同上，→E2E |
| W06 | scope必填条件；中英/emoji/组合/CRLF精确选区；批量某条坏则零任务；双击同ID同结果；断电后插入其他写入重放不重复 | test_workbench_annotations.py / test_change_operations.py，契约+故障注入+→E2E |
| W07 | 无关页更新候选仍可replan；同页竞争只有一个采用；正文basis变化拒绝；取消晚到；批量原子；当前/历史/候选不混 | test_candidate_adoption.py，集成+两轮真实Host |
| W08 | 参考只迁移指定风格，P08事实数字保留；未知prompt仍可参考图试作但不伪造；P09未选择不执行；重复扩展不多调 | test_style_recipe.py + 真实阅图 →EVAL |
| W09 | 材料已上传与读取判断分开；重排保持ID；合并拆分新ID/来源；旧选区不迁移；未改页产物保留 | test_workbench_content.py，→E2E |
| W10 | 29:59/30:00/30:01；无回执不伪处理中；取消重交接新ID；服务500/失联/多tab保存冲突保留两份；端口被占恢复 | test_workbench_recovery.py，假钟+真实服务 →E2E |
| W11 | 导出开始固定版本；之后current变不改bytes；历史看不写、恢复新版本；审阅包不含原始材料/路径/秘密；delivery门控仍生效 | test_versioned_export.py，内容检查+下载 |
| W12 | 从最终代码重新构建；两Python版本；隔离HOME、静态/字体/图标/Skill全包；旧UI回退可操作且不使用旧不兼容writer | test_workbench_package.py，隔离安装+人工 |

## 关键回归契约（CRITICAL）

用户原计划已授权保留：immutable原始图、原子提交、固定版本、取消后晚到保护、未改页产物保留、旧UI可用、delivery共享检查、调用事实不可回滚。本方案扩大可视化与操作面，不削减上述规则。上述断言与新增接口同时进入各卡，不能等W12补测试。

现有test_store_transactions、test_tasks、test_web、test_export、test_review_round3继续作为基础回归；新增review导出不再带完整工程目录是明确兼容变化，需要W11把现有断言迁到engineering并保留review可读说明，不能仅删失败断言。

## EVAL与人工阅图

W02验证真实请求绑定。W07两轮真实局部视觉修改，均看原图、SVG、PPT阶段；W08固定P07参考/P08目标，比较改前后，逐字核对标题、数字、来源和页面归属。记录模型/参数/实际输入证据等级，不承诺同prompt确定输出；样本包括内容错误、prompt漏条件、模型偏离、SVG还原错、旧项目prompt未知。合成Host仅测协议，不算视觉质量或真实工具执行。

## 故障登记

| 故障 | 当前新增功能有测试/处理吗 | 必须交付的可见行为 | 所属 |
|---|---|---|---|
| 指针已切但响应/索引未写 | GAP；基础原子写已在 | 查UUID返回原结果，禁止重复任务 | W06 |
| 跨页结果改变全局revision | GAP | 重新plan采用，区分生成依据是否真的变 | W07 |
| 旧候选覆盖新图 | GAP | current pointer CAS拒绝，保留候选 | W07 |
| 换端口失去浏览器草稿 | GAP | 恢复已同步journal；未同步提供恢复文件 | W03/W06 |
| emoji范围偏移 | GAP | 摘录不匹配拒绝，保留意见 | W06 |
| 300页大图耗尽内存 | GAP | 缩略图/解码限额、局部错误可重试 | W04 |
| 外站写入/目录越界/恶意SVG | EXIST基础；新路由GAP | 拒绝访问，无脚本执行，无任意文件 | W03/W11 |
| 导出中途新图返回 | GAP | 本次文件继续固定已选版本 | W11 |

这些是未实施功能的待建覆盖，不是已上线静默故障。所有故障已有指定处理与验收owner，计划层“无处理且无测试要求且静默”的未分配critical gap为0；实现层仍待证据。

## 页面与操作走查

/v2/ 项目入口 → 新建/打开；总览 → 画廊 → 单页 → 标注 → 影响计划 → 持久交接 → 候选比较 → 采用 → 运行 → 固定导出。检查1280×800与1440×900、键盘可达、焦点返回、对比4.5:1、双击/后退/刷新/离线/两个tab。

## 待决策

无新增待用户选择事项；测试范围来自用户全链路要求与AutoPlan授权自动决定。全部正式实现验收尚未执行。
