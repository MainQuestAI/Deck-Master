# 既有合同的最小增量与接线要求

| 对象 | 本轮字段/语义 | 写方和校验 |
|---|---|---|
| request | build_route；创建时origin_run_mode和策略不可被Agent重写 | Runtime；旧Run读取adapter；新默认native |
| build_manifest | engine_id/version/subset_version、build_revision、canonical_revision_ref、per-page输入hash与产物 | Run adapter；编译完成不等于delivery_ready |
| render_result.v2 / artifact_manifest | 来自同一committed revision、相对产物路径、实际文件hash、render/compile状态与native编辑属性 | 引擎；现有字段映射，不新建第二套正式导出产物 |
| narrative_plan | 新Run的唯一选定主线；基于资料、方案与用户有效决定 | 公共Planner；recommended≠approved |
| Page Package v1 | canonical status=ready_for_build；现有claim/evidence/design/diagram refs真实 | Producer；有条件迁移legacy ready；坏文件不忽略 |
| content_lock | narrative_ref/hash、package_ref/hash、source_refs、精确文字、style/ref、visibility与版本 | Runtime快照；不允许蓝图任务修改事实 |
| MBB旧投影 | derived_from narrative/lock及hash、projection_only=true等效标识 | 单向adapter；无独立新主线写权 |
| blueprint manifest/receipt | authoring origin、host实际执行证据等级、actual_image_hash、content/style/action绑定、allowed_delta | 既有receipt扩展；null元数据不得虚构；签名不代表服务真实性 |
| page_scene | 引用同一SVG/Content Lock、node/edge/model_ref、text/asset/editability、geometry校验 | 重建Agent；SVG仍是实际视觉源 |
| external review v2 | scope严格semantic、review coverage、逐package内容hash与方案/来源依赖 | 独立审查任务；不是前缀匹配或声明pass |
| action envelope | run_id/revision、输入与输出hash、scope、permission、attempt预算、cancel/supersede状态 | 既有workflow.actions扩展；CAS与写锁在真实调用方生效 |
| approval / final lineage | current revision + export artifact hash集合；批准人来源 | 用户决定+Runtime；不接受模型代批准 |
| capability lock / suite registry | bundled deck_native；legacy ppt-master标optional compatibility | 发布/安装；系统工具与宿主状态分开 |

## Canonical status兼容

新写入只写ready_for_build。读legacy ready时先检查来源/合同/批准有效性；通过后在迁移revision写规范值并保留original_status。draft/blocked/stale不能通过字符串替换变成ready_for_build。额外的original_status放入既有兼容metadata或迁移报告，不强行塞进不允许额外字段的schema。

## 构建revision与指纹

定义`content_fingerprint`为带顺序的page_id+各实际Package内容hash+公共Narrative/Solution/Diagram及使用来源指纹集合；`visual_fingerprint`再加入blueprint/svg/scene/assets/style/allowed_delta；`build_fingerprint`再加入compiler/subset/字体/renderer与输出profile。hash算法和canonical serialization固定并测试。

不得使用时间戳、文件名或仅index hash代替内容依赖；也不要因无关材料添加导致所有内容决定失效。核心内容变更和视觉变更分别决定需重跑哪些检查，但新的整体PPTX必须绑定新的最终批准。

## 状态动作输出（既有状态的目标扩展）

返回`awaiting_agent_build`/既有同义状态时，next_action含kind、run_id、action_id、expected_revision、scope_pages、input_refs、output_refs、required_schema、acceptance_command、resume_command和budget。缺真实工具返回blocked+capability明细；缺业务决定返回awaiting_user_decision+一个具体问题。保持旧状态兼容映射，不增加平行Run状态机。

## 小型内部编译边界

compiler只读批准输入、产生PPTX和trace。它不读用户HOME、不联网、不调用PPT Master、不选择主线、不处理审批。render adapter处理真实渲染。最终文件识别仍由Deck Master现有artifacts/lineage接口承接。

## 内容批准与逐页人工操作

编译请求中的approval_ref可引用符合现有政策的内容批准或预授权记录；不新增每页必须用户手工签字的关卡。Runtime验证该记录作用域、来源与当前内容hash。最终交付仍需当前整套文件的用户批准，技术内容校验不得冒充最终批准。
