# 03｜WP-A：托管安装、能力内化与按任务就绪

## 3.1 目标与边界

默认安装交付 Deck Master、四个产品能力的方法/适配器、标准 PPT Master 生产后端和 PPT Library 可执行程序。开发来源可以多仓库，用户安装不得要求手工 clone、切分支、绑定开发者 worktree 或保留旧全局 Skill。

“全新安装”不等于无系统依赖：Python、操作系统渲染工具以及宿主的推理/网络/图片生成能力仍需明确检测。缺少系统工具时返回准确修复指引，不冒充已经安装。标准路径不能因为宿主缺 ImageGen 而被阻断。

## 3.2 托管组件规范

扩展既有 release tree / `deck_capability_lock.json`；不要建立平行安装注册中心。
每个组件至少记录：稳定组件名、来源仓库/分发源、固定提交或版本、下载包 SHA-256、适配器版本、契约版本、相对安装路径、启动命令、Python/系统依赖、许可证/NOTICE、安装所有权和验证结果。

上游来源与具体 commit 本包不臆造。A1 必须验证可公开获取/可再分发、生产契约匹配以及真实 smoke。未验证版本不得以 latest/main 浮动拉取替代。若上游没有 Deck Master 需要的 manifest，由随产品分发的适配层生成，不能要求用户修改上游源码。

建议树形布局（目标路径，需 Codex 与现有安装器对齐）：

```text
<managed_root>/
  releases/<release_id>/
    skills/
    capabilities/ppt-master/runtime/
    capabilities/ppt-library/runtime/
    capabilities/ppt-deck-pro-max/
    capabilities/ppt-quality-gate/
    reference-packs/
    deck_capability_lock.json
  current -> releases/<release_id>
  bin/deck-master
  data/                         # 用户数据不随 release 回滚或删除
```

不要复制开发机 `.venv` 作为可迁移运行环境。安装时用受支持解释器和固定依赖在目标位置创建环境。PPT Library 可使用组件独立环境，避免与主包依赖冲突。运行时路径来自当前锁定组件，不先搜索任意 PATH。显式 external override 仍可保留，但必须显示来源、版本、所有权与验证状态。

## 3.3 四项能力的内化边界

| 能力 | 本轮必须纳入 | 不要求本轮重写 |
|---|---|---|
| PPT Master | 可再现标准生产后端、必须的 scripts/templates/references/workflows、契约适配、实际 build/render 验证 | 上游全部工具与历史分支 |
| PPT Library | 运行程序、固定依赖、能力发现、真实搜索/选择/反馈适配、授权索引入口 | 检索算法、用户已有资产库、全部历史知识治理 |
| PPT Deck Pro Max | Deck 内用到的页面规划/写作/视觉方法与参考、生成 handback | 不相关的独立产品入口 |
| PPT Quality Gate | 适用的语义/证据/视觉审查方法和结果协议 | 独立产品的全部 UI/命令 |

A1 输出 `capability-migration-matrix.md`，逐条列出“原方法/程序 → 内置位置 → 调用入口 → 回归案例”。没有实际源码或方法包时标记未知，需要 Codex 核验；不能把一个转发 SKILL.md 当作全部能力已迁入。

PPT-Deck-Pro-Max 桥接显式退役：`scripts/runtime/builder_backend.py` 中钉在第三方非默认分支（`codex/deck-pro-max-bridge` 分支固定 SHA）的 `DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 绑定是最脆弱的外部依赖；A1/A3 完成方法内化后必须移除该绑定路径与“HEAD 等于固定 SHA 才算 verified”的逻辑，production 生成只走 Agent 派发。退役前先确认无其他调用方。

## 3.4 安装事务和所有权

安装顺序：解析锁定组件 → 准備暂存 release → 验证包哈希与来源 → 创建目标环境 → 组件真实 smoke → suite 校验 → 原子激活 current → 安装归属明确的宿主入口。
失败保留旧 current；中断恢复不使用半成品 release。安装日志与公开报告不输出令牌或客户路径。

旧独立 `ppt-master` 等目录默认不改动。优先通过项目级 Deck Master 路由避免同名冲突；迁移时明确 origin/target/hash/ownership。独立目录只在显式授权后可做可回滚迁移。卸载只能清理本产品管理的入口与 release，不能删除 workspace、索引、原始资料或外部后端。

Codex 的项目级/全局模式按当前实现核验；Claude Code 至少覆盖现有支持的安装/迁移/回滚模式。不得未经测试声称所有宿主具有同等项目级支持。

## 3.5 任务能力执行计划

新增 `deck_capability_execution_plan.v1`，是由 Runtime 从当前任务与环境推导的可重算投影。内容包括 task_type、library_mode、build_profile、研究策略、需要的产品能力/宿主能力/系统工具/数据资源、已验证来源和阻断原因。

不要修改旧 `full_suite_ready` 含义来掩盖组件缺失。扩展状态版本，清楚区分：产品安装完整、组件运行可用、本次数据准备、本次任务可执行。旧字段继续按旧约定计算并标记 deprecated 映射；新的 task_ready 为本次任务决策依据。即使 task_ready=true，也必须展示 full suite 的缺项。

| 场景 | 必需 | 不应成为本次阻断 |
|---|---|---|
| new_solution + library none + standard | 材料读取、宿主推理、托管标准 build/render | 空历史库、未授权索引、缺 ImageGen |
| library real | 以上 + 托管 Library 可执行、授权索引范围和可查询数据 | 没有高密度能力 |
| high_density | 共同内容 + 当前 high-density 必需工具和已批准风格 | 未使用的外部标准后端不应成为高密度本次任务阻断；默认完整安装仍需验证标准后端 |
| diagnosis | 当前状态读取 | 未安装生成工具不妨碍报告诊断 |
| local_edit | 已选 profile、本次修改影响的能力 | 与此次修改无关的研究、旧 corpus、已完成访谈 |

`library_mode=none` 的规范：不调用 ppt-lib、不创建虚假 selection、不产生 manual_placeholder；为每页形成明确 `generate` 或当前页继续使用的 sourcing 决策。记录 `selection_status=not_requested`，不得写成 `library_ready`。`real` 模式无结果时可以按已允许的“无命中则新建”政策继续；程序故障不能被当成无命中。

## 3.6 安装完成的硬验收

隔离 HOME 和 PATH、旧 Skill 不可见、旧后端路径不可用，默认安装仍能完成：标准真实两页 PPTX+渲染；托管 Library 对授权合成资产的真实检索；所有 required 方法引用可读；当前版本状态可读；卸载不删用户数据；升级失败和回滚保持旧 Run 可读。

Fixture 是安装诊断补充，不替代真实后端验证。标准后端的 smoke 必须检查文件可打开、页数、预期文字、图形/图表与可编辑结构、实际渲染，不只检查退出码或 manifest=true。
