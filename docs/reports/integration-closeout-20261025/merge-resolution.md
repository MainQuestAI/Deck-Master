# UI 与修复主线整合取舍

本轮把 PR188 `159cfd63e9bcf71c10d98dad45a1a2567eb52136` 正常合并到第一阶段候选 `6e0d15484f8a39f7e6136a766ae0ef55bdd900ae`。固定源 PR 未改变；main 未合并，PR189 继续 Draft。本记录说明工程整合，不代表真实 Host、模型、专业或用户视觉签收。

## 分工与覆盖

主 Agent 负责 `web.py`、`workbench.py`、`run_desk.py`、投影兼容和最终候选；三个子 Agent 分别负责 runtime/合同、前端/轮询、测试/安装边界。共享目录按文件分工，只有主 Agent 操作 Git index/提交。

36 个冲突文件、71 个冲突块均逐块解决，另核对 24 个自动合并重叠文件。未使用整文件 ours/theirs 覆盖。自动合并的五个 repair baseline 历史记录文件与第一阶段候选保持相同；其旧 SHA 和结果不重写为本轮验证。逐文件记录见 `merge-resolution.json`。

## 明确行为

1. **同一套当前关系。** 总览与运行记录统一消费 `CurrentRelationships`；`action_currentness.Projection` 仅兼容旧的 `state/successor_id` 展示字段。保留新 `status/successor_task_id`，以及 action targets 的 operation 身份。旧任务事实不改写；已替换请求的历史失败不再进入当前待办，未知外部调用继续核验。当前待执行任务依赖变化仍给出重规划；后继须是同要求、同范围且真实采用覆盖全部目标页，单个新标签不能消除旧失败。
2. **计数含义。** `count` 保留所有候选，`pending_count` 排除采用、保留当前和历史候选，`stale_count/historical_count` 说明历史量，`actionable_count` 说明可操作量。历史产物仍可查看；未知来源候选可见但不启用动作。
3. **已采用正文与历史证明。** 完成的 compose 按采用回执和当前产出判断，不能用被采用动作自己替换的 dispatch 输入误判过期。依赖完整 canonical ancestry 的历史快照/回执判断只在本次响应缓存；旧祖先损坏后不得复用上次成功摘要。对象签名校验、当前快照固定与按请求重用保留，不能把读缓存当写入资格。
4. **HTTP 兼容和轮询。** 默认 `/api/project` 返回完整控制/资格信息，新 UI 先识别 `project_control_light.v1` 才使用 `light=1`；`details=1` 仍可用。保留 current_work v2、匹配身份的 summary 重用、单飞、暂停/离开页面中止和过期回调隔离。选择页面后轮询不重新出现第二个主动作。v2 仍把可操作动作排在禁用事实之前；不能因二次按 kind 排序把未知候选推为不可点击的主动作。首次/路由读取也核对 artifact/control 的身份配对，只有错配才补读；二次仍错配显示明确重读入口，不能退回旧 next_actions 或展示旧交接数量。首次头栏、历史详情与只读标记同样采用控制 revision，不把固定旧稿误标当前。
5. **UI 与原有能力。** 保留 PR188 的五工作面、阅读/编辑/来源边界、抽屉、控件、菜单和导航，接入 current_work/outline 入口。方法目录仍可读取不适用资源但不能选择；保留窄审阅、原 finding、外部报告返修、正文逐字段差异、初始设计及 v1/v2/v3 原图来源。两入口保留批量恢复和原生 modal-close 焦点行为。首屏几何回归通过消除阅读工具栏重复 margin、空选页容器占位和标题重复间距处理；不缩小字体、控件命中区或隐藏业务内容。
6. **复查。** RP-00 AC2 允许旧无 finding 记录再次审查，适用于既有 v1/v2 阶段；仍校验同一 logical review 和 stage。旧 pass 无 finding 后，实质观察可得出新的坏消息，必须原样接纳并阻断生产；新 finding 只能是 open，不能凭空 fixed/accepted_variance。既有 finding 不能消失。将 PR188 把双方同时换为 final 的负例改为真实跨阶段负例，补同阶段 final 和新问题的正反覆盖。独立复查范围按冻结 owner 精确对应，不回退到无差别全稿复查。
7. **合同与恢复。** 活动 schema 与 docs 镜像一致；v2 继承的候选历史统计和禁用原因与 v1 一并更新，按 mixed/unknown_task × v1/v2 校验真实返回值；保留暂停后的精确重放、取消/迟到结果保护、page_ids 资格范围、outline 与正文审查分离、v3 原始图片引用和 ReadFacts 单次控制快照。

## 验证口径

冻结前统一核心诊断为 243 passed / 25 deselected，覆盖 17 个模块；这还不是四组全量单元矩阵。合并过程中的诊断在本任务独立 Python 3.12 和 Chromium 环境运行；原始 JUnit 存于 task worktree 父目录。诊断包含真实暴露的冲突，失败记录保留，不能累加重试次数伪装测试数量。首次核心诊断发现投影字段/计数、冻结复查范围和新坏消息接收冲突；后续修复与测试均保留行为断言。首次 UI 诊断 61 通过、2 个旧菜单入口失败；按新 UI 实际用户路径适配后补跑 4 项通过，另新增选页/轮询 2 项通过。前端 57 个 JS 语法检查与轮询生命周期 18 项通过。最后的 7 项正式浏览器回归通过：两入口选页/轮询 2、首次 control/artifact 配对与历史只读 2、summary 重用 3；含真实 30 页的双入口读取次数检查。RP22 首屏与阅读 8 项、current_work 对话框 8 项均通过。

本文件记录源码冻结前的已知状态。完整四组单元、渲染、浏览器、最终 wheel/离线安装以 PR189 同一冻结候选的后续门禁记录为准；最终运行摘要会更新到 PR 描述与本地交付记录，避免把源 PR 或前一阶段证据覆盖到新代码上。工程合成审查输入始终标记 synthetic，不触发真实模型或客户项目写入。


## 首轮完整单元的诊断与环境修正

`29c8f732` 首轮完整本地单元结果为 3895 passed、12 failed、138 errors、2 skipped（853 deselected，564.54s），保留原始 JUnit，不记作通过：

- 10 个 failure 与 138 个 setup error 来自 macOS 默认 `tmp_path` 包含 `/private/`，正确触发冻结 Q2/RC3 的私有路径禁止规则。此时尚未进入目标断言。后续运行使用本任务独立普通路径的 `TMPDIR` 和 `--basetemp`，不修改 canonical 路径规则、helper SHA、隔离子进程、时限或断言。
- 多 owner 的“clean recheck”测试此前实际创建 failed/empty 旧记录；改为真实 pass/empty owner，并显式 `force_units` 发起复查。8 个 owner、16 条 review、逐个 replaces 身份、2 次调用断言全部保留；failed/empty 不能直接覆盖为 pass 的负例仍在。
- Python 轮询包装测试仍固定期待旧 15 项，而合并后的 Node 套件已经保留两分支共 18 项；更新数量并明确断言新增过期回调、路由屏障与 light 协商检查。

上述是测试构造/本地执行环境修正，不改产品树。普通路径 smoke 33 项通过；完整矩阵仍以随后冻结提交的全量结果为准。
