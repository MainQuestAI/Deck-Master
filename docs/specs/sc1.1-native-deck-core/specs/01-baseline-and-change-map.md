# 01｜固定基线、静态事实与修改地图

## 1.1 基线

开发基线：PR #30，分支 `codex/sc1-solution-core`，HEAD `4977f89573d18a282c605360dc55f751443a2b21`。本次在线读取时 PR open/unmerged，base SHA 为 `bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1`。[R01]

PR 描述仍提及旧中间 HEAD `d5c3040`，不作为代码基线。其“1583 passed + 119 subtests”是作者报告，不是本次复跑证据。源码是在连接器按固定 SHA 读取，没有取得完整本地 checkout，也没有执行产品测试；本地能力、环境、状态和效果均**需要 Codex 核验**。

若开始实施时 PR30 已有新提交或已合并：先做差异映射，保留本包已确认裁决；不得自动重置、revert、清理 worktree 或丢弃用户修改。

## 1.2 已看到的代码事实及对应动作

| ID | 远端静态证据 | 本轮应处理 | 不能据此声称 |
|---|---|---|---|
| F-N01 | installer 的 `install_managed_backend()` 复制完整源包后仍提示 bind [R02] | 从默认安装与 required 集移除整包；仅旧兼容保留 | 安装闭环已通过 |
| F-N02 | runtime/build.py 调用 builder_backend_status 与 production_requires_builder_backend [R03] | 新引擎路由先于外部状态查询；禁纯删 if 后伪报 ready | 去掉提示即可独立 |
| F-N03 | high_density/pptx.py 已有 compile/readback 与原生对象输出 [R04][R05] | 先提取函数和依赖，再通过差分测试 | 当前所有真实页面可无后端运行 |
| F-N04 | 高密度协议独立进行 MBB 主线选择及内容锁 [R06] | 公共 Narrative 为新 Run 唯一主线；MBB 成为派生适配 | 修改目录就解决重复规划 |
| F-N05 | next_step 优先发现 high_density/status；常规缺项写死 ppt-master [R07] | 以固定 route 和 canonical revision 解析，不以目录存在优先 | 所有默认入口已一致 |
| F-N06 | next_step 在只缺 semantic review 时仍可能返回 render gate [R07] | 缺语义时返回 prepare/import 语义任务，不重复 render | quality gate 增一枚即可完成 |
| F-N07 | CLI library choices 是 auto/real/fixture，尚无 none [R08] | none 接通 parser、start、autoplan、sourcing、resume、doctor | task_readiness 写了 none 就能用 |
| F-N08 | Schema status=ready_for_build；常规生产消费者要求 ready [R03][R09] | 统一写值并对旧 ready 作受控迁移，不接受任意同义词 | 声称“消费 Package”已足够 |
| F-N09 | semantic gate 用 external_* 前缀匹配；单靠 index 哈希判当前性 [R10] | 精确 scope/type/覆盖与逐文件内容指纹，图/来源联动 | external_visual 可代替 semantic |
| F-N10 | action commit 逐文件 rename、无跨文件提交指针；预算统计已提交项 [R12] | 复用 envelope，但采用 revision 暂存+单指针提交、失败尝试计入预算 | 函数 docstring 的 all-or-nothing 已得到证实 |
| F-N11 | 偏差登记含 HD 公共投影、typed questions 与接线欠项 [R11] | 按真实调用图补必须接线，登记旧案继承状态 | 八个开发段落都写了就已 engineering_complete |

以上静态观察不是本地故障复现。Codex 应补最小可复现实例，再以本包验收验证最终行为。重点是收口，不是扩大为任意 bug 清理工程。

## 1.3 可复用成果

从 PR30 继承 Context 和 Research 结构、Solution Model、公共叙事/Page Package 生产、Diagram View、质量审查契约、反馈接受率修复、安装所有权保护。不得重新声称这些功能全已验收；其真实调用方接入仍需要 Codex 核验。[R01][R11]

内置渲染候选：`scripts/high_density/pptx.py`、`svg_native.py`、`svg_paint.py`、`svg.py`、`visual.py`。内容候选：`high_density/content.py`、`production/page_package.py`、`build/manifest.py`。能力检查/安装/路由候选：`runtime/builder_backend.py`、`skills/installer.py`、`skills/capability_lock.py`、`runtime/next_step.py`。

## 1.4 必查入口与修改面

| 面 | 必查文件（现有路径；完整调用关系需要 Codex 核验） | 要达成的行为 |
|---|---|---|
| CLI/默认配置 | scripts/deck_master.py、product-capability-manifest.json、skills/manifest.json、skills/stage-contracts.json | 一个固定 native 默认，没有外部产品 required |
| 状态 | runtime/setup_status.py、run_state_resolver.py、next_step.py、skill_route.py、final_readiness.py、rc_gate.py | task_ready 与整套安装状态分离；不由旧目录触发错误路由 |
| 构建 | runtime/build.py、runtime/render*.py、build/manifest.py、high_density/engine.py 与编译子模块 | 单写入者、原生编译、两类旧适配 |
| 内容 | planning/narrative_planner.py、production/page_builder.py、page_package.py、diagram_views.py | 不制造第二份主线或事实；状态值一致 |
| 执行 | workflow/actions.py、handoff.py、questions.py、decisions.py、approval.py、现有 autopilot 实现 | 能派发/接受/继续；幂等、权限、版本、预算真实生效 |
| 质量/交付 | quality/gate_policy.py、gate_freshness.py、external_review.py、delivery/validate.py、orchestrate/export_queue.py | 当前语义不能用视觉门替代；输出绑定有效版本批准 |
| 安装/发布 | skills/installer.py、capability_lock.py、pyproject.toml、release 构造、容器/CI入口 | 依赖随产品，旧外部目录不被探测或改写 |
| 指引 | AGENTS.md、CLAUDE.md、README、known-limitations、主 Playbook、两个 Builder Skill、recovery/index | 不再引导默认用户绑定 PPT Master；新旧明确 |

Q0 交付 baseline-diff、call-graph、reuse-vs-replace、old-test-map、host-capability-probe、dependency-closure 六份简报即可；不得以长期文档盘点替代实现。
