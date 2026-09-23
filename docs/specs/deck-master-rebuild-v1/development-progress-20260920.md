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

## 阶段 1 完成：WP03 收口

WP03 最后一张卡 T15 关闭（见下节）。**阶段 1（WP02/WP03 收尾）按计划完成**——T07/T08/T09/T11/T12/T13/T14/T15 整卡关闭，T10 工程 AC 关闭（仅差 AC-B04/V02/V07 非工程证据）。回归 137 → 294 项全绿。

## T15 整卡关闭：导出与状态汇报收口

- `export --purpose review|delivery` 落地（`working` 保留为 review 别名）;review 导出附真实未通过/未评估清单（取自 evaluate_current);delivery 拒绝信息带具体维度；delivery.json 新增 `unresolved`/`professional_evidence`/`evidence_level` 字段。
- 新建 `tests/rebuild/test_export.py`(7 项）:fail 稿 review 导出如实标注、delivery 拒未解决 must_fix、缺人类审阅 not_evaluated 不假通过、exit 0≠专业通过；扩充 test_service_flow.py(+3):editability 诚实声明、UI/导出无原生 Office 编辑数据声明、旧件 unknown 不升级。
- UI 补"可编辑形状与文字"诚实标注；`check_summary`/`_professional_evidence` 与 evaluate_current 同源抽出。
- AC-V06(诚实交付,T25 关闭）交接输入齐备：delivery.json 证据字段 + 4 个对照测试名。
- 验证：定向 23 passed；`tests/rebuild` 全量 **294 passed**(284+10)。
- 状态同步：tasks.json/subtasks.csv 中 T15 及子任务标记 `implemented_verified`；T15.md 交接回填已记录。
- 工作树待提交变更：`editing.py`、`cli.py`、index.html/style.css、`test_service_flow.py`、新建 `test_export.py`。

## Review 轮次与 P1/P2 修复（2026-09-21）

- 对 T08–T15 开发轮次(0a3f316..954b59b)做独立只读 review(独立 plan 代理),结论:无 P0;6 条 P1、11 条 P2。
- P1 全部修复:①文本描边声明子集边界(真实 SVG 零使用,显式 SvgError);②导出 editability 读 artifact 自身字段(旧件 unknown 如实);③`professional_review_required_for_delivery` policy 在 delivery 导出生效;④失效指纹改为 SVG 实际引用资产集(T12 S13 证据语义修正+注册新资产零失效反例);⑤抗锯齿样例改 GaussianBlur(1.5) 并按 07.4 校准阈值;⑥review 依赖新鲜度补 style 指纹+未知 kind 保守判 stale。
- P2 全部修复:OperationJournal status、CSP 头合并、浏览器拒绝如实 available、spec 10.3 路由补齐(/api/pages/{id}、/api/tasks、/api/reviews、POST /api/check)、挂起任务只屏蔽 scope 维度、privacy 交叠串、transform 括号垃圾校验、SvgError 结构化 page/element、空文本显式拒绝、cli 死条件与 NeedsTool→exit 3、letter-spacing 单点写入。
- 全量 **309 passed**(294+15),ruff 全过;7 份真实交付 SVG 回归解析通过。

## T17 整卡关闭：唯一默认入口与文档（阶段 2 首张，2026-09-21）

- 新 CLI legacy 层：`_legacy_dispatch` 按 spec 09.6 三类处理旧命令——7 别名（执行新语义）、18 指引（exit 2 typed JSON）、60+4 退役（exit 2）；绝不 import/exec 旧 scripts/deck_master.py；旧 run 格式在全部写路径拒绝（`legacy_run_format`，零就地初始化）;`deck-master legacy-map` 打印全表。
- 统一入口：`[project.scripts] deck-master = deck_master.cli:main` 启用；修复 venv editable 把 scripts/ 挂进 sys.path 导致 `python -m deck_master` 进旧 parser 的环境问题；wheel entry_points 断言；无 v2 开关。
- 解除绑定：README/AGENTS/任务索引/恢复手册/migration 文档全部改新口径；5 个旧 spec 目录加 ARCHIVED.md 标记（零删除）;product-capability-manifest.json 未改字节（退役归 T24）。
- 新建 `tests/rebuild/test_cli.py`(24 项）;AC-I04 关闭,AC-C06 交接 T04。
- 验证：定向 40 passed；全量 **333 passed**(309+24);ruff 全过；`deck-master --version` = 1.0.0.dev2。
- 状态同步：tasks.json/subtasks.csv 中 T17 及子任务标记 `implemented_verified`；T17.md 交接回填已记录。
- 遗留：旧套件 17 个失败测试（test_skill_installation 等）归 T24;AGENTS.md "Stop And Report" 小节仍引用旧命令名（现走映射，语义不冲突，可后续润色）。

## T19 整卡关闭：发布资源与许可证清理（2026-09-21）

- 归属：B0/K0 提取头保留（测试断言 wheel 字节含归属注释）;compiler-extraction.json 与 geometry.py 实际函数集双向精确匹配；THIRD_PARTY_NOTICES.md 按本 venv 实际版本重写（python-pptx 1.0.2/Pillow 12.3.0/numpy 2.5.3/jsonschema 4.26.0,dev 依赖单列不分发）。
- 元数据：pyproject 转 PEP 639(`license = "Apache-2.0"`),wheel licenses/ 目录携 LICENSE+NOTICE，构建弃用警告消除。
- AC-I08 = test_install.py +2:wheel(57 项）+sdist(186 项）+release 树逐项排除客户材料/密钥四正则内容扫描/字体二进制，正向能力件全在；**未发现真实泄露路径**，无需改 build_hook/MANIFEST。
- 验证：定向 7 passed；全量 **335 passed**(333+2);ruff 全过。
- 状态同步：tasks.json/subtasks.csv 中 T19 及子任务标记 `implemented_verified`；T19.md 交接回填已记录。
- 工作树待提交：THIRD_PARTY_NOTICES.md、pyproject.toml、test_install.py。

## T18 整卡关闭：旧 run 只读导入（2026-09-22）

- 新建 `src/deck_master/legacy.py`：显式 schema/version 判别（v1 页包/HD run/v1 draft 目录，零子串猜版本）；`inspect_legacy` dry-run 计划（字段/媒体 sha/未知指针/旧状态历史）;`import_legacy` 只读导入（源全量 hash 前后一致校验、零写入、零脚本执行）;v1→v2 正文/关系/稳定 ID 映射（未知 block 形态抛 `LegacyNormalizationRequired` 带指针，不静默丢）;旧 completed/pass 仅历史说明，新项目 reviews 空、review_status not_evaluated；缺源 `original_sha256=null`、全零 hash 拒绝、补文件不追认。
- CLI:`deck-master import legacy --input <old-run> --out <new-project> [--inspect]`;migration 文档补用法节。
- 新建 `tests/rebuild/test_legacy.py`(15 项）+ fixtures(v1-draft、hd-run)；定向 15 passed，全量 **350 passed**(335+15),ruff 全过。
- 状态同步：tasks.json/subtasks.csv 中 T18 及子任务标记 `implemented_verified`；T18.md 交接回填已记录。
- 工作树待提交：legacy.py、test_legacy.py、fixtures/legacy/、cli.py、migration 文档。
- 遗留：asset_bindings 的 design_context 注册与 HD 含 PPTX 路径留待真实 v1 样本扩展（同模式，已声明）。

## T20 + T16 整卡关闭：候选隔离安装端到端（2026-09-22，阶段 2 收官）

- AC-I05 = `test_isolated_install_runs_full_local_flow`(wheel+sdist 参数化）：空 HOME、清 XDG/cache/PYTHONPATH、cwd 移出仓库,`python -I` 断言模块路径在 venv site-packages 不在仓库,doctor compose/render 如实、create→continue 真实 Host 任务;记录解释器路径、模块来源、wheel SHA、doctor module_path。
- AC-I06 = `test_isolated_resources_resolve_inside_package`:importlib.resources 在 -I 下解析 schema/static/SKILL/references 全部落在包内,不借 checkout。
- T20.02/03 隔离全链(compose→blueprint→reconstruct→**真实 soffice produce**→export review→单页修改重装配）;T20.04 非 16:9+真实字体+Logo+搬迁+缺字体分步诊断;T20.05 安装版入口走 begin/settle/cancel 额度语义。T20.02 真实生图引用 2026-09-16 Host 证据。
- T16 收尾：候选安装/激活/回滚/activated doctor 在显式测试前缀经 T20 复验;新增 `DECK_MASTER_NO_AUTO_VIEW` 非交互闸。
- CI:新建 `.github/workflows/rebuild.yml`(Python 3.12 + ruff + tests/rebuild,push/PR 触发）。
- 验证：定向 14 passed；全量 **357 passed**(350+7);ruff 全过。
- 状态同步：tasks.json/subtasks.csv 中 T20/T16 及子任务标记 `implemented_verified`；卡面交接回填已记录。
- 工作树待提交：cli.py、test_install.py、新建 rebuild.yml。

## 阶段 2 Review 修复轮（2026-09-22）

- 第二轮独立 review(阶段 2,8775a4a..eaafd83)：无 P0;4 P1(全在 legacy.py 静默丢弃族)+ 10 P2。全部修复：未映射字段/形态/节点边一律 `LegacyNormalizationRequired` 带指针;`--out` 在源目录内写入前拒绝;导入媒体 provenance 记 `legacy_import`;CI 按 11.8 拆 unit/render/report 三 job;setuptools floor≥77;隔离 venv 三级兜底离线可跑;T16/T18 卡面回填。
- 全量 **367 passed**(357+10),ruff 全过；提交 2154d7a。

## T24 整卡关闭：旧源/测试/合同退役（2026-09-22）

- 按 T01 处置表逐路径退役:scripts 旧树 177 文件删除(living 引用先修零);tests 非 rebuild 123 文件退役(migrate/retire 判定入 `inventory/old-tests-disposition.md`,17+8 个已知失败点名,零 skip);docs/contracts 58 份与旧 spec/活文档全部 git mv 归档 `docs/archive/pre-rebuild/`(零删除历史);ci.yml→ci-legacy.yml;product-capability-manifest.json 归档 v09 副本。
- 引用归零证据:`inventory/scan_old_references.py` 扫描器入库,`inventory/reference-scan.md` 记录 177 路径 blocking references=0;old-files.csv verification 列逐行回填。
- AC-L05/L06 = test_package_boundary.py 升级口径(`test_old_file_disposition_executed`/`test_retired_tree_has_zero_living_references`);退役后干净 wheel 重建 56 项无 scripts 泄漏。
- 全量 **368 passed**;ruff 全过;T18 legacy 导入能力保留(25 测试全绿)。
- 状态同步:tasks.json/subtasks.csv 中 T24 及子任务标记 `implemented_verified`;T24.md 交接回填已记录。
- 保留未动(按硬约束):runs/、第三方 skills、字体、docs/assets、.gstack/.impeccable/.zcode(查不明即保留)。

## T24 Review 补刀轮（2026-09-23）

- 第三轮 review(T24 退役):无 P0;4 P1(随包 installation.md 教授退役命令/根活文档失效链接/扫描器盲区/处置表模板化)+ 6 P2。全修:installation.md 重写新安装口径;CONTRIBUTING/ROADMAP/DESIGN/模板清零;扫描器扩面(根 *.md+references+36 词 needle,先抓 65 命中后修零);可靠性条目点名替代;新增 contracts parity 断言(抓到 task.v1 drift 已修);reference-scan blocking=0、retired hits=0——AC-L05 严格成立。
- 全量 368 passed,ruff 全过。

## 下一阶段

WP05 剩余:T21/T22 冻结对照(**等用户 P1 陌生材料与受众用途**)、T23 专业阅稿与桌面编辑(**等用户安排**)、T25 最终默认切换(依赖 T22/T24,T24 已满足)。

## T14 整卡关闭：完整四视图工作台

- 新建 `tests/rebuild/test_web.py`(9 项）:revision 跟随编辑且 review 解释与 web 状态一致（U02)、CLI accept 自动 `view --open`+无浏览器返回真实 URL+服务失败 null+原因+服务复用（U03)、同源 token/路径白名单/XSS textContent+CSP（U06)。
- 扩充 `test_workbench_e2e.py`(+4)：四槽字节级真实文件+版本（U04)、finding 可寻址 page/element(U04)、反馈 awaiting_host 不假 running+真实执行才更新（U05)、静态资源键盘切页/缩放/非颜色状态（U07 工程部分；浏览器目视沿用 2026-09-16 人工证据）。
- 新实现/修复：CLI 自动打开接线（`_attach_workbench_url`,accept/create/import-draft);`web.open_view` 容错（原 spawn 失败直接抛出 → 现返回 unavailable+真实原因）;app.js 补 `bindKeys`/`bindZoom`,index.html 补缩放工具栏与 `role="status"`/`aria-live`/`aria-selected`;test_cli_chain 断言更新（行为强化）。
- 验证：定向 19 passed；`tests/rebuild` 全量 **284 passed**(271+13)。
- 状态同步：tasks.json/subtasks.csv 中 T14 及子任务标记 `implemented_verified`；T14.md 交接回填已记录。
- 工作树待提交变更：`cli.py`、`web.py`、静态资源三件套、`test_cli_chain.py`、`test_workbench_e2e.py`、新建 `test_web.py`。

## T13 整卡关闭：重试历史与真实成本

- T13.04：新增 4 轮真实 repair 流归档测试（独立 ref 全可读、repair 零图像调用）；新增**无进展停止守卫**(service repair 分支:同 findings sig + 同候选 page ref → `repair_no_progress`,停止≠通过；候选真实变化放行新轮）。
- T13.05：两执行争最后名额双重拒绝；settle 幂等/异结果拒绝/同 invocation_ref 跨额度拒绝；**call_allowances 新增 evidence_level**(host_reported/provider_verified,有工具签发 invocation_ref + settle 报告才记 provider_verified,不隐式升级；task.v1.schema.json 可选字段向后兼容）。
- T13.06:restore 不重获名额（consumed/unknown/evidence_level 全保留）、降上限不抹消耗、多轮历史可追溯。
- 修复：repair 守卫初版误用 content_identity(repair 采纳合法清预览槽导致永不触发），改比 page ref。
- 验证：定向 25 passed；`tests/rebuild` 全量 **271 passed**(263+8)。
- 状态同步：tasks.json/subtasks.csv 中 T13 及子任务标记 `implemented_verified`；T13.md 交接回填已更新。
- 工作树待提交变更：`src/deck_master/service.py`、`tasks.py`、`resources/contracts/task.v1.schema.json`、`test_budget.py`、`test_tasks.py`。

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
