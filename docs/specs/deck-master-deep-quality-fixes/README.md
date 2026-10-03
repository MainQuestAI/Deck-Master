# 深入质量审查修复 · Q01–Q14

修复基线：main `88558b5bfc4fa1f7637e33e4f5a6392fa3f08377`。本轮覆盖 3 项 P1、11 项 P2；一个修复 PR，不增加项目格式、CLI 命令或 HTTP 路由。先运行失败反例，再修复和复核。原验收稿及历史检查记录不改写；合成测试不等于真实 Host 或客户验收。

| ID | 修复内容 | 回归入口 |
|---|---|---|
| Q01 | 每个浏览器文档独立写缓冲；继承身份只作恢复提示，旧副本保留 | `test_deep_quality_browser.py::test_cloned_window_offline_drafts_both_survive` |
| Q02 | 根据原生文字对象与 IR 验证完整内容项，拆分、透明、小字号不能被当成装饰 | `test_deep_quality_compiler.py::test_split_required_atom_is_not_decorative` |
| Q03 | 采用实际变更时失效整稿；continue 验证输出 SVG 依赖，修复旧 writer 留下的陈旧输出 | `test_deep_quality_state.py::test_adopted_svg_continue_rebuilds_existing_ppt` |
| Q04 | 单页内容采用原子退役受影响活跃任务，无变化不退役 | `test_deep_quality_state.py::test_content_adoption_retires_only_obsolete_tasks` |
| Q05 | 输入试作在接收候选、完成任务前验证 Host 协议与能力 | `test_deep_quality_state.py::test_input_trial_rejects_unclaimed_host_before_completion` |
| Q06 | 图标计划绑定请求代次；取消选页、刷新后晚回包不能重新启用提交 | `test_deep_quality_browser.py::test_unselected_icon_page_cannot_be_dispatched_by_late_plan` |
| Q07 | 当前版本路由不输出 null；兼容读旧 revision=null 链接 | `test_deep_quality_browser.py::test_handoff_navigation_opens_current_task` |
| Q08 | 历史候选列表固定 revision | `test_deep_quality_browser.py::test_historical_candidate_list_never_acquires_future_candidate` |
| Q09 | 计划阶段 409 不依赖业务 pending，保留草稿并展示恢复面板 | `test_deep_quality_browser.py::test_annotation_plan_conflict_keeps_draft_and_opens_recovery` |
| Q10 | 清理计划失败恢复预览按钮，原面板可重试 | `test_deep_quality_browser.py::test_clear_plan_network_failure_allows_retry` |
| Q11 | tspan 复用样式归一化，局部透明度及非法属性明确处理 | `test_deep_quality_compiler.py::test_tspan_style_and_local_opacity_reach_ir` |
| Q12 | 颜色 alpha 与对象/填充/描边 alpha 相乘，包括文字和渐变 stop | `test_deep_quality_compiler.py::test_rgba_alpha_multiplies_in_native_fill_stroke_and_text` |
| Q13 | 对不能保持语义的透明分组明确拒绝，保留 SVG，不栅格化 | `test_deep_quality_compiler.py::test_translucent_group_rejects_multiple_paint_operations` |
| Q14 | 可选 Node 出口使用等比 contain 缩放和居中偏移 | `test_deep_quality_compiler.py::test_node_contain_transform_matches_canvas` |

所有测试位于 `tests/rebuild/`。`test_deep_quality_render.py` 补充局部 SVG/真实 PPT 的像素、对象和检查结果。Node recording adapter 单元测试只证明坐标变换；实际 artifact-tool 编译与渲染另行验证，不以适配器替代真实出口。

## 已确认的透明分组边界

组透明度为 0/1 时保留原处理。介于 0/1 时只允许单一绘制操作安全下推；多对象或同一对象同时具有填充和描边被拒绝，包括几何上互不相交的多对象，避免依赖不完整的相交判断。错误返回页面、元素和 `group_opacity` feature，要求重绘为显式不透明几何。本轮不实现原生组合成，也不输出栅格替代图标。

## 兼容与恢复

- 原缓存可读取；新窗口只写新副本，不清除另一窗口内容。已经丢失的本机输入无法补回。
- 非法 Host 结果不会先把任务标为 completed。旧版已经形成的不可采用候选保留；重新创建试作并正确执行 task start，不补造接手事实。
- 旧版正文采用留下的 stale reconstruct，通过已有 task cancel 和 continue 重新派发；不得编辑项目对象或复活旧任务。
- 同一采用请求重放保持幂等，批量单页冲突仍全批拒绝。新产物引用与任务退役在一次事务内发布。
- 编译器和 pipeline 的文件摘要参与候选预览缓存身份；修复后重新生成检查。历史输出不批量重写，旧绿色报告不作为本轮验收证据。

## 验收顺序

F01 失败反例 → F02 三项 P1 → F03 状态/UI → F04 编译 → F05 核心、必需浏览器、真实渲染、wheel/sdist 隔离安装、300×5×3 压力与 20 分钟长跑、独立复审及当前 PR head CI。图像池网络/解码/缩略图/大图上限维持 6/2/60/4。

## PR97 外部评审定向修复（R1–R3）

在 `274838c6407f0c9ee0774155f4dc5b80f519793f` 上重新打开 Q02、Q03；保留此前验收记录，以下新增证据关闭这两项的遗漏。工程验收与人类视觉确认分别记录，本轮不合并、不执行真实 HOME 安装。

| 编号 | 行为与完成条件 | 回归入口 |
|---|---|---|
| R1 / Q02 | 显式绑定优先；无绑定按规范化字符区间分配，同文案承载必须足够且全部可读；不同正文不能共用区间。存在唯一必要承载时先保留该承载，再排除其它正文的交叠候选；其余无法确定的交叠保守阻断并提示补绑定。 | `test_external_review_readback.py` |
| R2 / Q02 | `noFill`、solid alpha=0、全透明渐变不可读；部分透明渐变不误判，未知填充/继承不默认通过。Node 出口的文字 `none` 被第三方输出为黑色时，由现有公共 DrawingML 后处理恢复源填充及透明度。整稿和候选共用检查，检查模块摘要参与候选缓存身份。 | `test_external_review_readback.py`、`test_external_review_render.py` |
| R3 / Q03 | final review/repair 先核对整稿输出；page_visual 只核对相应页面的 Page、原图、SVG 和 SVG 预览。整批采用后在同一事务退役失效非 trial review/repair；continue 恢复旧 stale pending。 | `test_external_review_lifecycle.py` |

无变化引用采用、重复请求、有效 trial、无关页级审阅和调用事实保留；旧任务迟到结果拒绝，单页冲突阻止整个批次。新增文件是内部检查实现，不改变 CLI/HTTP、schema 或最低写入版本。

验证顺序：新增失败反例 → 定向回归与真实 `produce` → 独立只读复审 → 固定源码 → 完整核心、必需浏览器、真实渲染 → wheel/sdist 隔离安装与安装后离线 UI → 300 页压力及 20 分钟长跑 → 当前 head CI。证据保存在项目外独立目录，失败记录和原验收稿不覆盖。

实际渲染限制单独记录：本机 LibreOffice 对首 stop 全透明的渐变文字未显示正文，尽管原生 DrawingML 含另一不透明 stop；末 stop 透明的同类文字显示正常。数学 paint 检查不能替代实际局部渲染或视觉认可；该反例及实际 PPT/PNG 保留，不用改变颜色或栅格化掩盖差异。

## 合并前追加复核：渐变 stop 有效区间

复核 `9675230` 发现零宽度不透明 stop 仍可令完全透明的必需正文通过。修复按位置分组同 offset 的 stops，保留首 stop 的左侧 alpha 和末 stop 的右侧 alpha，忽略组内零宽度片段及画布边界外的片段；仅有非零宽度区间或端点延伸可见时通过。不能把同位置 stop 全部折叠为最后一项，否则会误拒绝左侧正常渐变。未知、越界、逆序或缺失的原生位置仍返回 `unverifiable_text_mapping`。

回归入口 `test_gradient_readability.py` 覆盖起点/终点零宽度、内部孤立 stop、重复 offset 左右侧、端点延伸、正常部分透明及无法验证的位置，并执行真实 SVG → PPT → XML → LibreOffice → produce 持久化。数学填充检查与工具渲染差异分别记录；本轮修复不改 schema、接口或项目 writer。

规则依据：[SVG2 渐变 stop 规范](https://www.w3.org/TR/SVG2/pservers.html#StopElement)。源码修复后重跑完整核心和必需浏览器/真实渲染门禁；通过当前 head CI 后按用户授权合并 PR97。
