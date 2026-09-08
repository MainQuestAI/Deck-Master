# SC-1.1 Spec 偏差登记

| 日期 | 任务/PR | 原约束 | 实际采用方式 | 原因/证据 | 对业务目标与兼容性影响 | 关联验收 | 是否需用户裁决 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 2026-09-07 | ND-01 | 目录名/落位由仓库惯例 | 内核落 `scripts/native_pptx/`（编译器文件名保留 pptx.py/svg_native.py/svg_paint.py；svg.py 的纯片段拆至 svg_pipeline.py；canvas 常量独立 canvas.py）；HD 六模块以 sys.modules 别名 shim 保持入口 | "目录名是目标建议"（spec 02 §2.3）；身份断言测试证明单一实现 | 旧 HD 调用方零破坏（全量回归证明） | CMP-06/07 | 否 | closed |
| 2026-09-07 | ND-01 | 编译器不得调用业务校验 | compile_pptx 的 validate_approved_svg 内部调用改为**适配器注入参数**（缺失则拒绝编译） | spec 03 §3.2"Run adapter 校验后传入"；保持 native 层无业务依赖 | 行为等价（engine 注入同一验证器）；直接调用 compile_pptx 的测试已更新为显式注入 | CMP-07 | 否 | closed |
| 2026-09-07 | ND-02 | 发布/安装不要求 ppt-* | 本轮完成路由/none/探针；**manifest required 策略与 release 树 required 改造未实施**（涉及 library_status._contract_state 三方一致性校验联动，需独立提交验证） | 会话上下文预算；宁可如实欠交 | suite-status 仍按旧 required 报告外部能力；native 探针已可作为替代证据源 | IND-01/07 部分 | 否 | open（下一增量） |
| 2026-09-07 | ND-03 | image_blueprint 真实宿主链 | 派发 envelope（awaiting_agent_imagegen 诚实态）已落地；**真实 ImageGen/视觉重建/桌面编辑用例 not_run**——本宿主无该工具（host-capability-probe 实测），不以合成 SVG 冒充 | 规格 §0.5 明确禁止以缺工具冒充真实工具测试 | HST 组与 UAT-01/02 保持 not_run；direct_svg 路径已真实 L2 | HST-01—07、UAT-01/02 | 否（工具授权属 outcome_pending 通道） | open |
| 2026-09-07 | ND-04 | 逐文件内容指纹当前性 | 现实现=index sha 绑定 + 编译前 pin-hash 校验；**逐页内容哈希进入语义门当前性**未完成（QA-03 完整深度） | 两级校验已覆盖"包集合变更即过期"；单页变化粒度留待增量 | 不影响本轮门语义精确性（F-N09 已封闭 external_visual 冒充） | QA-03 | 否 | open（下一增量） |
| 2026-09-07 | ND-05 | 旧 Run 迁移 | 本轮**未触碰**旧 Run 执行路径（HD 薄 shim 保持行为等价，回归全绿）；build migrate CLI、MIG 组、七类差分矩阵专项用例、8—12 页真实全链（需真实工具）未实现，如实 not_started/not_run | 上下文预算；禁止以 fixture 顶替真实工具测试 | 旧 Run 兼容零破坏；完整迁移收口待下一增量 | MIG-01—06、UAT-01/02 | 否 | open |
| 2026-09-07 | 全轮 | 整轮完成定义 | 本轮为**增量工程交付**：主链默认路由/内核/none/门禁精度/原子修订可用并有测试；"默认真实内置生产全链真实工具验收"未完成 → 状态 `in_progress`，不得标 engineering_complete | spec 00 §0.5 完成标准第 1/2 条未满足 | 无 | 全表 | 否 | open |

| 2026-09-08 | PR31 评审修复 | 评审六项 P1 | 批次 1—3 已落地：P1-01 native 接入 run_build + 标准产物回写；P1-02 required 策略统一（manifest/installer/agent-doctor native 探针驱动，ppt-* 全转 optional，迁移覆盖全部套件技能）；P1-03 revision 先建快照后指针切换 + 身份含目标路径 + 尝试账本 + 预算锁内强制；P1-04 调用方 action_id + 派发时指纹 + 锁内重算（可调用）+ 冲突拒绝；P1-05 完整页集覆盖 + 资产解析 + SVG hash pinning + 坏包阻断；P1-06 v1 仅历史可读（legacy 标记 + 门拒绝）+ 逐包文件内容指纹 | PR31 评审（2e5340a）逐项复现确认 | HST 真实工具用例仍 not_run（宿主无 ImageGen）；render_pptx 渲染器接线与 MIG apply/rollback 仍 open | 全表 | 否 | closed（工程面） |
| 2026-09-08 | PR31 评审修复 | 次要三项 | 路由持久化（build/route.json，首写固化，旧 HD Run 密度延续）；失败预算按尝试计数（追加账本）；探针分级（kernel smoke 实测 validate+parse，fonts 需真实 truetype 加载，整体 degraded_ready 如实） | 同上 | renderable 级探针待渲染器接线 | IND-05 | 否 | closed（工程面） |

> 与 SC-1 偏差表的关系：SC-1 open 项（W-02—W-04 typed triggers、envelope autopilot 接线、真实后端 smoke/UAT）按 supersession map 继续有效；PPT Master 绑定前置已由本包 ND-D01 替换为 native 探针（A-03/A-08 处置见 SUPERSESSION_MAP）。
