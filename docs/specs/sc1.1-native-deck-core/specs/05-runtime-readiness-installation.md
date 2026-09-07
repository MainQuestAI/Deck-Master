# 05｜默认路由、任务就绪、安装与执行闭环

## 5.1 能力判断必须按任务

| 任务 | 必需 | 不得作为阻断 |
|---|---|---|
| 原材料理解/方案设计 | 已授权材料读取与文本推理；关键研究需要实际研究工具 | PPT Master、图片生成、历史库、PPTX renderer |
| 默认新页 image_blueprint | 原生编译、图片生成/读取/SVG宿主动作、SVG/PPTX renderer、字体 | 外部 PPT Master 绑定、独立 ppt-* Skill、未使用的 Library |
| 明确 direct_svg | 原生编译、SVG编写/读取、renderer、字体 | ImageGen、外部 PPT Master |
| 编译已有批准 SVG | compiler、当前锁/scene/asset | Web、ImageGen、用户重做主线 |
| 导出当前批准文件 | 文件及当前质量/批准有效 | 无关新生成工具；但新的校验实际需要的依赖不能忽略 |
| 旧 PPT Master Run 继续 | 该 Run 显式记录的旧后端 | 只影响该 legacy 任务，不影响新 native |
| library=none | 无库生产决策 | ppt-lib 可执行程序与资产索引 |
| library=real/auto且已选库 | 实际检索程序、授权索引 | 未使用的旧 PPT Master |

任务就绪输出必须分别有 local_runtime、host_tools、content_inputs、required_missing、optional_unavailable 和 status。`unknown` 不能当 true；`installed`/`contract_declared` 不等于 `verified`。环境变量的 true 或一个 reviewer/skill 名称不能代替真实能力证据。

一份 status 同时说明“软件内核已就绪”和“当前宿主没有图片工具”是合法状态；不得把它混成“需要绑定 PPT Master”。

## 5.2 默认安装与发布树

新默认安装只发布 Deck Master 代码、compiler、contracts、method references 和明确依赖清单；不包含整套 PPT Master runtime/template/workflow、旧同名 Skill 必需链接或默认后端绑定。

source/editable/release-tree/installed launcher 均须走同一 native 路由。`product-capability-manifest.json`、skills/manifest、installer SUITE_SKILLS、release lock、suite-status、setup-status、agent-doctor、rc-gate 的 required 策略统一。

去掉默认外部后端 required 时，新增真实 native capability probe，而不是删除验证或把 backend_ready 写常量 true。native 状态只依赖本次引擎版本、依赖、renderer/字体和真实 probe。更换二进制、SVG子集或环境指纹后旧 probe 失效；用户资料不参与全局软件能力证明。

依赖解析不得 fallback 到 `~/.codex/skills/ppt-master`、外部项目路径或 PATH 中的 `svg_to_pptx.py`。可选 Library 程序按原 SC-1 托管逻辑继续，和用户索引分开；历史资产缺失的无库新建保持正常生产。

## 5.3 CLI 目标增量

以下为需要实现/扩展的接口，不是当前已可执行命令：

```bash
deck-master build prepare --run-dir <run> --profile native --authoring-mode image-blueprint
deck-master build run --run-dir <run> --profile native
deck-master build status --run-dir <run> --output json
deck-master build retry --run-dir <run> --page-id P001 --stage svg
deck-master agent-doctor --mode production --run-dir <run> --output json
deck-master autoplan --run-dir <run> --library-mode none
deck-master build migrate --run-dir <old-run> --to-profile native --dry-run
```

profile/authoring CLI 参数用横线、内部 JSON 用下划线，集中标准化一次。已有 flags 的可用性与命令分组需要 Codex 核验；若仓库有等价入口可复用但必须记录规范示例和测试，不允许只实现内部函数不接 CLI。

`none` 必须出现在共享 parser 及所有 auto/workflow 参数传递，并由 sourcing 输出每页 generate/adapt（仅使用已批准资产时）等真实决策；不写一个空 imported/real selection 骗过 downstream。模式 auto 的运行错误和合法0命中仍要区分。

## 5.4 主状态和入口一致性

`next-step`、`run-state`、`workflow status`、`agent-doctor`、Review Desk、`final-readiness` 读取同一 route/current revision 和 gate resolver。不得新链 completed 但全局仍 needs_builder_backend，再由 final-readiness 强制覆盖成 ready。

返回 awaiting_agent_* 时携带可执行 action：action_id、kind、run_id、build_revision、scope_pages、input_refs/hashes、output contract、acceptance_command、resume_command、remaining_budget、required_tools。现有 action envelope 是承载点，不另建 action 服务。

只缺 semantic_review 时，返回准备/执行/导入语义审查动作，不再返回 render gate。只缺最终批准时，不再重新询问主线/风格。待 Agent 工作与待用户决定严格区分。

## 5.5 原子性、幂等与边界

使用每 Run 写锁或等效并发控制，结果提交时重新计算 input fingerprint（不能相信调用方传来的字符串）。在一个锁周期内比较 expected revision、验证权限/停止状态、验证所有 staged files、切换 committed revision，再生成事件/投影。逐文件 rename 不保证整批原子，必须通过中断测试。[R12]

action_id/run_id/page_id 必须安全且由 Runtime 分配或校验；禁止路径穿越、absolute output、跨run/symlink escape。scope_pages 不能只被写进日志而不被检查；内容任务不能写审批/来源/已批准归档。相同 action+输入+输出重复幂等，相同 action 不同输出冲突拒绝。取消/旧输入的晚到结果留审计，不激活。

多页动作中第2个文件失败、marker写入失败、进程终止后，读取者只能看到完整旧 revision 或完整新 revision。异常应可恢复，不要求用户手工改 events 或 manifest。

## 5.6 问题归属和批准

只补本链路所需 typed questions：已给 Brief 信息、核心主张/反方疑问/证明顺序、主线选择、风格、真实范围与最终导出。专业问题归 Agent；用户真实决定不能以自动推荐代填。合法否定/false/空禁词列表按各自类型接受，不能用全局 vague token 规则拒绝。

问题依赖精确到决定影响的字段/版本；单页配色不能废弃客户目标。已有明确用户选择可以通过 Runtime 写入引用，不重复访谈。不存在授权才提问，不能以“少问”为由跳过最终批准。
