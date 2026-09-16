# 01｜目标架构与新核心边界

## 01.1 新建方式

在现有仓库创建 `src/deck_master/`，采用 `src` 包布局。开发初期不改旧安装的 current 链接，不覆盖用户run；新入口通过隔离虚拟环境的 `python -m deck_master` 调用。WP04验证后，把公开 `deck-master` console entry 切到 `deck_master.cli:main`。旧 `scripts/deck_master.py`只保留明确命令映射或退役提示，不允许新任务再次进入旧OS。

分支建议名 `codex/rebuild-mainline-v1`，基于B0创建；若本地已有后续提交，Codex先列出B0至当前HEAD的差异，只补充受影响的映射，不整轮重新讨论。分支名是建议而非已存在事实；创建/切换须有实施授权。不得reset未提交修改或自动切换用户工作树。

这不是一个新的长期profile。新包在切换后拥有唯一正常新建路径；旧代码仅固定旧版使用/只读导入。在隔离验证期间允许两套源码短期并存，但安装和单个run绝不混用两套写入者。

## 01.2 依赖方向

```text
宿主 Agent（阅读、推理、内容主编、图像制作、审阅）
  ↕ 五种工作任务：compose / blueprint / reconstruct / review / repair
CLI / 本地 Web
  → service（用例）
    → content / sources / production / review / export / tasks
      → store / models（文件与数据）
    → compiler.api → svg/geometry/paint/text/drawingml
                     → render/readback（实际文件工具）
  → view（只读派生，与CLI/UI共用）
legacy → 只读旧格式 → content/store；不得import旧engine
install/doctor → 新包资源与实际步骤依赖，不参与内容判断
```

编译包不得import service、tasks、workflow、review政策、安装用户HOME或模型工具；它可以接收显式资产/字体路径和输出目录。上层可以调用编译器，编译器不能读取“已批准”等业务状态。review可以调用实际readback，但readback不决定客户可用。web/cli不得自己重新计算一套就绪逻辑。

在CI中建立AST导入边界测试：新 `src/deck_master` 不出现 `runtime.* / workflow.* / high_density.* / preview.* / build.native_*` 等旧包导入；编译包只依赖其内部、stdlib与声明依赖。抽取时修改import与资源定位，不允许用sys.path插入scripts或HOME仓库偷取实现。边界测试是防实际回流，不建设通用插件注册框架。

## 01.3 目录与职责

下列目录和75项台账是最终范围，不是首份成品前必须创建的文件数。可在现有目标内先完成最小纵向切片，再补全一般能力，不能先造空壳文件。具体35个核心文件及构建/方法/测试等附属目标见 `inventory/new-files.csv`；以下为稳定边界，不要求拆成更多“服务”。

| 子域 | 文件 | 职责与主要接口 |
| --- | --- | --- |
| 内容输入 | sources.py、content.py | 来源登记/读取、PagePackage v2、可见原子、整稿归一化；不生成规则目录 |
| 项目状态 | models.py、store.py、view.py | 五对象校验、不可变对象、原子当前指针、真实页面视图 |
| 宿主工作 | tasks.py、service.py、production.py | 发出具体任务、接收结果、协调转换、按影响继续；不内置LLM |
| 检查交付 | review.py、export.py | 实际观察与当前性、修订、审阅稿/正式导出 |
| 编译内核 | compiler/*.py | SVG解析、IR、几何/画笔/文字、原生对象、渲染与读取 |
| 使用入口 | cli.py、web.py、resources/static/* | 一致命令/API/工作台，失败产物可查看 |
| 兼容部署 | legacy.py、install.py、doctor.py | 只读历史导入、候选安装、实际依赖与模块来源 |

`__init__.py`只暴露版本，不通过import启动engine、扫描HOME或加载字体。schema和静态资源通过 `importlib.resources` 读取，不根据仓库相对路径假定已经checkout源码。

## 01.4 权威来源只保留三层

1. **文档当前状态：**`.deckmaster/current.json`指向一个不可变Document。Document中的pages数组是当前页集合与顺序，不能由目录glob、preview或旧stage推导。
2. **每次制作/检查的输入与结果：**不可变Page、Artifact、Task、Review对象。它们可以被历史Document引用，但不能就地改写为“当前通过”。
3. **呈现状态：**`view.py`读取当前Document及相关对象，派生正文状态、制作进度、检查状态、专业证据状态。派生值可以缓存，但删除缓存不得改变事实或阻断恢复。

不引入一个永续的`status.json`同时接受CLI、UI、review各自写ready。日志是诊断，不是必须重放的另一数据库。current pointer既不是用户批准，也不是质量结论。

## 01.5 核心接口（拟实现签名）

- `service.create_project(brief, sources, output_dir, existing_decisions) -> ProjectView`
- `service.continue_project(project, expected_revision=None) -> ActionResult`
- `service.request_edit(project, page_ids, instruction, expected_revision) -> Task`
- `tasks.accept_result(project, task_id, operation_id, input_fingerprint, result) -> CommitResult`
- `store.commit_change(project, base_revision, read_set, writes, cancelled_task_check) -> revision_id`
- `production.project_prompt(page, resolved_design_context, permitted_assets) -> prompt_text`（配置由同一Document快照解析，不能另取默认值）
- `compiler.api.compile_deck(inputs, options, output_dir) -> CompileResult`
- `review.evaluate_current(document, reviews, actual_artifacts) -> CheckSummary`
- `view.project_view(project, revision=None) -> ProjectView`

签名表达职责；具体Python类型在models中落地。接口不能偷偷回读另一套current，也不能以“调用方承诺已审阅”代替实际输入验证。显式参数包括revision和依赖，避免长操作期间读到半新半旧内容。

## 01.6 首轮生产与调试路线

正常新建：源资料→Host完整稿→接收→逐页蓝图及文案编辑→按原图SVG→编译→实际渲染/读回→审阅/返修→查看与导出。

已有正文：接收完整稿，省略compose。已有用户蓝图：登记原图来源、完成内容对照后重构，不重新生图。独立转换工具可以接受SVG进行转换诊断；不能把这种诊断结果冒充完成了“从材料生成专业Deck”的任务。

所有路径都复用同一Page/Artifact/Review概念；不复制一套fixture、standard、high-density产品状态。fixture仅是测试输入来源，必须如实标记，不能改变production的验收判断。

## 01.7 资产选择失败后的处理

编译器提取首先保持有效行为，然后修已知缺陷。某类SVG特性无法可靠支持时，返回对象级不支持原因，修对应组件或明确更换组件，不建外围规则掩盖。若完整稿仍空泛，改Host方法/源输入，不扩大JSON字段和最低密度限制。

新核心不得直接依赖历史PPT Master仓库。若未来要接其他renderer，应在明确业务需求下通过编译接口适配；本轮不实现可插拔框架。

## 01.8 最早可交付切片

按14.2的`start_after`启动部分能力；`depends_on`仍是整项T任务完成的依赖。T10.min无需等T03全部格式/T09全部通用特性；先用已知TXT/JSON材料、事故页实际需要的SVG子集、真实PPT渲染和只读四视图，紧接T12.min单页修订。原图对照、原件保存、基础原子写入、必要取消/晚到保护不因为“最小”省略。未通过的原图对照不能标完成；未实现格式与特性继续列在最终范围，不能被切片偷偷取消。
