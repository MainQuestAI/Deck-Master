# 02｜目标架构、路由与唯一数据归属

## 2.1 公共链路

原材料 → Context/Research → Brief/Claim Evidence → Solution Model → 公共 Narrative → Page Tasks/Sourcing → Page Packages → Content Lock → 图片蓝图 → Scene+SVG → 内置编译 → PPTX/渲染/回读 → 专业审查/定向修复 → 当前版本批准/导出。

不新增公开 Skill；`deck-builder` 负责新默认构建。现有 `deck-builder-high-density` 继续作为密度/旧 Run 兼容入口，不拥有另一套内容事实和编译器。

## 2.2 正交字段（目标协议，不是当前能力声明）

| 字段 | 值/默认 | 语义 |
|---|---|---|
| engine_id | deck_native（新 Run 默认）；legacy_ppt_master（显式兼容） | 编译执行身份，不以客户选项显示底层项目 |
| authoring_mode | image_blueprint（默认）；direct_svg（显式） | 图形生产来源，二者调用相同原生内核 |
| density | standard/high；已有页面密度可继承 | 页面信息密度，与是否图片蓝图独立 |
| library_mode | none/auto/real；没有授权库时 none | sourcing 行为，不决定编译器身份 |
| origin_run_mode | production/benchmark/fixture/dev | 创建时记录；不可用修改 request 把生产转 fixture 来交付 |
| output_profile | 沿用 production_pptx/client_delivery | 所需产物；不静默少生成声明过的格式 |

`build_route` 随 request 固定，schema 见 contracts/build-route.v1.schema.json。当前 engine_version、SVG 子集版本和 build_revision 在执行计划/产物记录，不让用户手填。

### 路由规则

新 Run 无 profile：native + image_blueprint；新 Run `--profile native` 相同。新 Run 旧 `--profile standard` 映射 native 并给一次兼容说明。新 Run `--profile high-density` 映射 native、density=high，不启用独立后端。

已有 Run：先读已保存 route，再读构建/产物契约推断旧 engine。旧 high_density 由 legacy-HD adapter 消费既有路径；旧 standard 仅在明确历史后端痕迹下认作 legacy_ppt_master。无法判断则只读并给出迁移计划，不默认当新 Run 改写。对旧 Run 指定与其不符的 profile，返回迁移要求；不得在普通 status/doctor 中迁移。

显式 `--profile legacy-ppt-master` 只用于旧模式或明确请求；仅此路由检查旧 binding。缺失它不阻断 native。旧行为作为兼容，不作为发布默认路径必测依赖。

## 2.3 三层内部设计（目标位置可映射）

1. **公共内容与视觉任务层**：复用 SC-1 现有模块；构造宿主任务、生成蓝图、重建与修订。
2. **Native compiler 层**：建议 `scripts/native_pptx/`；纯编译、SVG 解析、样式映射、对象追踪。没有项目业务规划、PPT Master 绑定、HOME 探测或网络调用。
3. **Run adapter / engine 层**：建议 `scripts/build/native_engine.py`；把 Run 的内容锁、Scene、SVG 与资产投影为编译输入，写回标准 artifact/build/render/lineage；宿主动作通过既有 workflow envelope。

目录名是目标建议，Codex 可以调整但必须保持职责、依赖方向和验收。不得复制两份解析器/编译器供新旧路径独立演化。

## 2.4 数据归属与依赖方向

| 对象 | 权威写方 | 下游如何使用 |
|---|---|---|
| Context/证据 | 原材料和经核验研究导入 | 事实/来源；不从图片反填 |
| solution_model | 方案设计任务，经 Runtime 接受 | 问题、机制、组件、边、阶段、取舍 |
| narrative_plan | 公共规划任务及用户有效决定 | 新 Run 唯一主线；推荐不等于用户已选择 |
| page_packages | Producer，经 schema/来源/授权校验 | 唯一页面内容输入；标准状态 ready_for_build |
| content_lock | 根据批准 Package 生成的不可变快照 | 文本/数字/术语与业务限定；不能被视觉任务写 |
| blueprint | 已授权 ImageGen 真实输出及已接收修订 | 视觉来源；内部标注不进入正式页面 |
| scene | 重建任务的语义旁注，经 Runtime 校验 | 元素ID、文本引用、组件映射、编辑目标；不是第二布局真相 |
| approved_svg | 重建任务的视觉源，经规范化和检查 | 几何/样式/z-order 的实际输入 |
| PPTX/trace/readback | 本地编译器与渲染器 | 编译结果，不是新的事实来源 |
| gate/approval/current revision | Runtime | 当前版本有效性与批准；不接受 Agent 宣称已批准 |

新 Run 的 MBB compatibility projection 只从公共 Narrative、证据引用和 Package 投影。原 HD MBB 文件可以继续存在，但加 `derived_from`，不允许独立写入主线。不得先创建空 Package 再要求其作为 Narrative 的起点。暂缺内容时回到 Producer/Planner，不能靠 build 补模板。

## 2.5 当前版本与派生文件

复用现有 build manifest 作为 committed revision 清单，增加单一 `build/current_revision.json` 原子指针（如仓库已有同职责对象则复用并登记）。建议不可变数据位于 `build/revisions/<revision_id>/`。跨文件提交先完整暂存、校验、写 revision manifest，最后在 Run 锁内比较旧 revision 并单次切换指针。

`build/build_manifest.json`、`render_results/render_result.json` 等旧固定位置只做兼容投影。所有新消费者在读取时验证 projection_revision 与 current 一致，不一致必须重建投影，不能把部分投影当有效版本。不能同时把“新 pointer”和“旧固定目录”各当真相。

页序改变影响整 deck fingerprint 和批准；单页颜色修改影响该页视觉、整体 PPTX 与最终批准，不必废弃未变的业务目标决定。来源/方案变化按被引用关系计算影响集。旧 revision 永久保留到用户授权的清理策略，不自动覆盖已批准客户文件。

## 2.6 安装依赖边界

内置组件至少包含编译、验证、回读适配、schemas、方法引用和测试样例；以相对模块导入加载。第三方软件包与系统工具清单随 release 记录版本/来源；用户基础工具缺失由 doctor 给准确动作。不得检测 native 就绪时运行外部 PPT Master 目录探测；可选 Library 与模型运行环境各自报告，不污染本次任务 readiness。
