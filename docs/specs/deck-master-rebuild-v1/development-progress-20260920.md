# 开发执行记录 2026-09-20

接续 [development-progress-20260916.md](development-progress-20260916.md)。

## 阶段 0：环境修复

- `.venv` 补装 `setuptools`，修复 test_install.py 两个打包用例的环境性失败；`tests/rebuild` 全绿口径统一为 137 passed。

## T08 整卡关闭：纯SVG接口与派生IR

- 新建 `tests/rebuild/test_svg_parser.py`（43 项，全部通过）：`test_svg_to_ir` 覆盖 spec 06.2 全部正向条目（基本几何含 path M/L/H/V/C/S/Q/T/A/Z 绝对/相对、嵌套变换 translate/scale/rotate/matrix、linear/radial gradient 含 stop-opacity、中文多行 tspan、symbol/use 含 viewBox 缩放、批准 PNG 三种 preserveAspectRatio、直线端点方向、data-atom-id 绑定、无关 data-* 属性放行）；`test_unsupported_and_unsafe` 36 个参数化反例，断言 SvgError 且诊断含 page/element 定位与 recovery，不静默删图。
- 修复 3 处实现 bug（均在最早出错层，未削弱既有拒绝行为）：
  1. `src/deck_master/compiler/geometry.py` `_parse_path`：arc flags 经 `int()` 截断，`sweep=0.5` 被静默当 0；改为严格校验 in (0.0, 1.0)。
  2. `src/deck_master/compiler/svg.py` text 分支：x/y/font-size/letter-spacing/dx/dy 裸 `float()` 解析，nan/inf 静默入 IR；新增与 `num()` 同措辞的有限性检查。
  3. `src/deck_master/compiler/svg.py` style 预处理：缺冒号声明抛裸 ValueError；改为显式 `malformed style declaration` 可定位诊断。
- AC-K09（不支持与安全）与 AC-B06（单手写源）由本卡关闭；AC-K01 实际隔离 PPT 生成仍归 T10。
- 验证：`.venv/bin/python -m pytest tests/rebuild/test_svg_parser.py -q` → 43 passed；`tests/rebuild` 全量 → 180 passed（原 137 + 新 43）。
- 状态同步：`task-cards/tasks.json` 与 `subtasks.csv` 中 T08 及 T08.01–T08.05 标记 `implemented_verified`；T08.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/compiler/geometry.py`、`src/deck_master/compiler/svg.py`、新建 `tests/rebuild/test_svg_parser.py`（用户确认后提交）。

## 下一动作

T09 已关闭（见下节）。WP02 余下大卡为 T10（真实渲染与首段完整闭环）。

## T09 整卡关闭：绘制缺陷逐项修复

- 修复 3 处 DrawingML 写出缺陷（`src/deck_master/compiler/native.py`）：
  1. shape spPr 子元素顺序错误（fill 落在 ln/effectLst 之后，违反 DrawingML 序列，桌面 PowerPoint 会判需修复文件）→ geom→fill→ln→effectLst；
  2. text rPr 子元素顺序错误（fill 落在 latin/ea/cs 之后）→ fill→latin→ea→cs；
  3. 旋转文本双重变换（预定位块 + sh.rotation，探针实测盒子漂移出负坐标）→ 删除预定位，glyph 旋转只由 sh.rotation 承担一次。
- 测试：新建 `tests/rebuild/test_text.py`（5 项，字体经 fc-match 解析本机 Hiragino Sans GB，含 fallback 与缺字体报错契约）；扩充 `test_geometry.py`（+5：正/负斜率与反向线端点方向、旋转圆 190500×190500 EMU、旋转椭圆解析极值、等比缩放圆角与图标描边、非等比带描边显式 SvgError）；扩充 `test_paint.py`（+2：fill/stroke opacity=0 写入、组 opacity 相乘含 0）。全部经 compile_deck 真实 PPT 解包 slide XML 读回。
- AC-K02–K07 六条由本卡关闭；桌面 PowerPoint 实际打开编辑仍归 T10/T23 人工层。
- 验证：定向 20 passed；`tests/rebuild` 全量 193 passed（180+13）。
- 状态同步：tasks.json/subtasks.csv 中 T09 及 T09.01–T09.05 标记 `implemented_verified`；T09.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/compiler/native.py`、`tests/rebuild/test_geometry.py`、`test_paint.py`、新建 `test_text.py`。

## T10 工程 AC 关闭：真实渲染与首段完整闭环（整卡未关）

- 新建 5 个测试模块（20 项，全绿）：`test_compiler_geometry.py`（AC-K14：4:3 Document 走真实 produce 全链，PPT sldSz=9144000×6858000 EMU，prompt 采用 canvas 无 16:9 隐藏默认）；`test_readback.py`（AC-K08/K10：7 项，含 reversed_arrow/missing_node/missing_edge/全文级 hidden_or_tiny/越界定位）；`test_render.py`（AC-K11：rsvg 与 soffice+pdftoppm 真实渲染语义断言，缺 renderer 经 NeedsTool 标未验证）；`test_drawingml.py`（AC-K13：子集支持范围矩阵+子集外显式失败）；`test_compiler_api.py`（AC-K01：HOME/cwd/env 隔离、中途改字节拒绝、失败不发布）。
- 扩展：`svg.py` IR 捕获 `data-node-ref`/`data-edge-ref`；`pipeline.readback` 新增 missing_node/missing_edge/reversed_arrow（首末点 vs 节点 bbox 中心；直边强语义、曲线边弱语义 limitation 已记录）、全文级 hidden_or_tiny_text（局部装饰豁免）、slide 越界定位。
- 未发现需修复的既有 bug；现有行为全部回归保留。
- 验证：定向 20 passed；`tests/rebuild` 全量 **213 passed**（193+20）。
- 整卡未关闭：AC-B04（两张同业务异布局源图 Host 阅图）、AC-V02（P1 陌生材料——仍等用户到料）、AC-V07（min 证据见 2026-09-16 记录）。
- 状态同步：tasks.json/subtasks.csv 中 T10.01–T10.04/T10.06 标记 `implemented_verified`，T10 卡保持 in_progress；T10.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/compiler/svg.py`、`src/deck_master/pipeline.py`、5 个新测试模块。

## T11 整卡关闭：统一审阅解释与真返修

- 新建 `src/deck_master/review.py`：纯解释模块 `evaluate_current(document, reviews, artifacts) -> CheckSummary`(status/dimensions/stale/missing_dimensions,07.2 语义）+ 配套纯函数 closing_review（R06 关闭链）、validate_independence（R05）、triage_render_difference（R04 像素三分类）、privacy_findings（R07）、classify_finding（C05 计算复算/无依据数字/建议只读）、source_expectations（B07）。
- 重构 `editing.review_status` 整体走 evaluate_current——service(load)/view(UI)/export_project（导出闸）三入口同一份解释（AC-R03)。
- `tasks._adopt_review` 增加 replaces 链接收校验（R0 存在/同 review/共享 finding_id/subjects 新增复查对象，悬空 replaces 改 EnvelopeError)。
- 修复预存 bug:tasks.py:348 F821(`pid` 未定义，repair scope 检查命中即 NameError)。
- 新建 `tests/rebuild/test_review.py`(25 项，真实 Store + PIL 合成 PNG 三类样例）;10 条 AC 全部关闭。
- 新增 `skills/deck-master/references/review-and-repair.md` 简短引用。
- 验证：定向 25 passed；`tests/rebuild` 全量 **245 passed**（220+25）。
- 状态同步：tasks.json/subtasks.csv 中 T11 及子任务标记 `implemented_verified`；T11.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/review.py`、`editing.py`、`tasks.py`、`tests/rebuild/test_review.py`、`skills/deck-master/references/review-and-repair.md`。

## 阶段 1 剩余

WP03:T13 整卡（依赖 T12 已满足）、T14 四视图工作台、T15 导出收口。

## T12 整卡关闭：局部修改与并发恢复

- 新增 18 项测试（四模块）,11 条 AC 全部关闭：S03 幂等、S04 依赖分层（task 管理不失效、正文编辑仅失效当页）、S05 局部编辑（无关页 hash/ref 双不变+整 PPT 重装配+旧件找回）、S06 多页事实、S07 页集合（重排/删页稳定 ID、历史不混回）、S08 并发重基（异页安全/同页冲突无最后写覆盖）、S09 取消竞态（cancel 先赢晚到结算不采用/accept 先赢 cancel 不删产物/同 hash 重放仍拒）、S10 恢复重定位（新 revision 不回滚调用事实/搬迁 refs 可读/源 hash 核验）、K15 资产字体重定位（对象 Ref 读 Logo/字体指纹/缺字体不阻旧媒体/发行不打包字体）、S13 有效样式失效。
- 新实现：`service.update_design(design_context, base_revision)`(operation=design_update，提交前逐页 resolve_design 试解析拒半态）；统一失效助手 `_rendering_state`/`_apply_rendering_invalidation`(canvas 变化全页成组失效；style 变化仅有效 style 变动页；blueprint 永保留）;import_asset 重构复用同一助手。
- 验证：定向 60 passed；`tests/rebuild` 全量 **263 passed**(245+18)。
- 状态同步：tasks.json/subtasks.csv 中 T12 及子任务标记 `implemented_verified`；T12.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/service.py`、test_install/test_service_flow/test_sources/test_store_transactions/test_tasks。

## T07 整卡关闭：原图保持与文案往返

- 新增 7 项测试（test_content.py +4、test_production.py +3），四条工程 AC 全部关闭：
  - AC-B03 = `test_copy_roundtrip_keeps_original_page_prompt_and_blueprint`：真实 Store 流（draft→continue→采纳蓝图信封），edit_page 产生新对象/新 revision，原 Page、蓝图字节、prompt blob 旧 ref 重读字节不变；小改正文后下一任务为 reconstruct（不强制重生原图）。
  - AC-B05 = `test_previews_never_become_reference_and_reencode_fails_binding`：重编码（单像素扰动）的 svg_preview/ppt_preview 不进入 reference_images；以重编码 sha 绑定的 SVG 在 accept 时被 EnvelopeError 拒绝。
  - AC-B08 = 4 项：edge 元数据永不进正文 atom；label_ref 指向真实可见 atom 且 assign_missing_ids 往返保留；悬空端点拒；未知 target 属性被 schema 拒绝。
  - AC-B10 = `test_new_design_mode_and_failed_review_is_preserved`：reference_mode=new_design 进 prompt projection；失败 review 旧 ref 字节不变、状态不被后续通过回填。
- 本卡未发现需修复的 src bug；仅测试构造对既有契约如实对齐（edit_page 状态词、节点必填字段、dependencies 带 kind、finding kind 枚举）。
- 验证：定向 27 passed；`tests/rebuild` 全量 **220 passed**（213+7）。
- 状态同步：tasks.json/subtasks.csv 中 T07 及子任务标记 `implemented_verified`；T07.md 交接回填已记录。
- 工作树待提交变更：`tests/rebuild/test_content.py`、`test_production.py`。
