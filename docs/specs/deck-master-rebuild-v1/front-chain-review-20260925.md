# 真实需求入口与 Skill 编排复核

日期：2026-09-25。基于代码候选 9034568 和当前工作区。此次为评审，未修改运行时代码或安装配置。

## 结论与范围

用户已认可当前内容、视觉结果和 Builder 的可用性。下一步应在修通入口后，用一项真实需求完成真实方案；不再默认复跑开发对照组。生成端保持现状，有实际问题再修。

当前主要断点在任务信息交接、材料入口和 Skill 安装/说明一致性。无需新增 Planner 或多 Agent 调度平台。

## 已核实问题

| 优先级 | 问题与证据 | 影响 | 最小调整 |
| --- | --- | --- | --- |
| P1 | `service.py:264` 的 `task_summary` 未投影 Document.task；`open_compose_task` 的 inputs 为空，instruction 为通用提示 | brief、受众、用途、页数、既定决定虽已存盘，但 create/continue 工作单不携带；恢复任务依赖聊天记忆或额外读底层文档 | 所有 Host 工作单加入当前任务事实；明确既定决定优先于方法示例 |
| P1 | `cli.py:76` create 未暴露 service.create 已有的 audience/scenario/presentation_mode/page_limit/existing_decisions | Host 经唯一 CLI 入口不能完整登记结构化任务，presentation_mode 固定使用默认 live | 增加一个可选任务 JSON 输入，沿用现有字段；自然语言 brief 继续可用，不增加必填问卷 |
| P1 | Skill 宣称普通材料目录可作为 source；`sources.py:315` 只接受文件 | 传目录实际返回 FileNotFoundError，即使目录存在 | 增加目录发现与选入清单；明确版本、排除输出/缓存，登记真正选入文件；不盲目全量导入 |
| P1 | 当前本机 `.codex/skills/deck-*` 等链接指向 `.deck-master/current/skills/…`，目标 SKILL.md 不存在；`install.py` 只激活 CLI，未注册 Host Skill | 开发工作区可以执行，不证明新任务中可发现并调用正确 Skill | 安装候选同时准备唯一 master 的可发现入口，检查 CLI 与 Skill 来自同一候选；切换时保留回滚 |
| P2 | 主 Skill 加载的 `content-methods.md:15–26` 仍讲旧对象、import-plan 和不存在的 playbook；末尾 D1/D2 使用另一套示例定义 | 活跃说明混入旧模型，易让 Host 找不存在的说明或误套示例任务 | 改为当前 Task → Page → Host result 的术语；例子用业务场景命名，去掉 D1/D2 协议式标签 |
| P2 | CLI/service 有 Page 编辑、资产导入、设计更新，未提供任务事实与新来源的正式更新入口 | 中途改变用途、页数或补材料难以持久保存并可靠续跑 | 增加范围明确的输入更新，沿用现有 revision/失效逻辑；先重新判断受影响内容，再决定需重制哪些页 |

限定：仓库中存在 19 个 Skill 入口，不等于新版会同时加载 19 个。MANIFEST.in 与 tools/build_hook.py 已只打包主 Skill，这个方向应保留。本机链接失效是当前环境事实，不能推断所有安装环境都失效。旧命令存在兼容映射，不能把旧名称一概表述为不存在；问题是活动方法仍引导旧流程。

## 定向复现

使用当前 `.venv/bin/python`，在自动清理的临时目录创建一份合成 MD；调用 service.create，传入独有 brief/audience 和 page_limit=9，再调用 continue_project。

- create 响应包含 brief 标记：false。
- continue 响应包含 brief 标记：false；包含 audience 标记：false。
- pending task 带 sources/source_reading，但没有任务事实字段。
- 将真实存在的临时目录作为 source：FileNotFoundError，material not found。
- 检查本机 master/planner 的链接目标：SKILL.md 均不存在。
- 主 Skill 方法文件链接检查：content-methods 指向的 ../playbooks/codex-run-solution-deck.md 不存在。

未运行全套 tests/rebuild，未生成新 PPT；此次没有行为修改，无需重跑已接受的制作样本。

## Skill 精简与协作安排

对外保留一个 `deck-master`。主文件只写触发条件、入口、连续推进、恢复与交付边界。内部按需读取三组方法：

1. 内容：合并 brief/planner/sourcing 的有效方法，包含任务理解、材料选入、证据、叙事与完整逐页正文。source-reading 保留为阅读技术附录，长示例按需读取。
2. 制作：保留现有蓝图 → SVG → 逐页审图 → PPT 链，收纳 builder/producer 的有效说明，不改已验证生成机制。
3. 审阅与修订：整合 quality/review 的重复规则，保留早期审图与最终真实 PPT 审阅的区别。

init/setup/upgrade/doctor 是安装维护说明，按需查询；不作为做方案的必经阶段。autopilot 的连续推进规则归主 Skill。旧入口先盘点实际依赖，再归档或保留短兼容跳转；不删除历史材料或旧运行。

Host 负责理解用户意图、完整正文与修改决策；运行时负责文件、状态、任务派发和过期结果保护。Skill 是方法，不是一名独立 Agent。当前阶段无需固定多个 Agent 接力：如以后确需委派资料阅读或独立审阅，应有明确输入输出，由主 Host 汇总，运行时接受结果保持单一写入入口。

同时精简工作单：成稿派发内容方法；蓝图派发制作方法；审阅派发审图要求。当前 task_summary 无论任务种类都附三份内容资源，可改为按任务选择，避免反复加载不相关说明。

## 建议实施顺序与真实验收

1. 修任务事实投影、CLI 结构化输入、目录材料入口和中途输入更新。用小型行为测试覆盖首次创建、恢复、补资料与修改约束，不生成整套评估稿。
2. 清理主 Skill 活动引用，整理三组内部方法；补同版本 Skill/CLI 安装与发现检查。在独立候选验证，暂不改用户默认入口。
3. 按正常使用方式开始一项真实需求，从现有材料和自然语言任务进入，完成可业务审阅的逐页稿并交给 Builder。只在缺失信息影响方案时提问；已确认答案持续有效。
4. 以真实使用判断是否还需调整：首次稿是否对应受众及待决定事项，事实/建议是否清楚，中途修改是否保留、能否连续交付。记录自然出现的问题和必要修订，不要求额外计时表，不将代码测试替代业务判断。

上述工作归已有内容输入、成稿与安装交接责任范围，不重开 T21/T23 的已接受结果。T10 历史限制保留说明。
