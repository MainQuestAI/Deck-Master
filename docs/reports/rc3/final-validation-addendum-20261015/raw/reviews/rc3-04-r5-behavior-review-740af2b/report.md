# RC3-04 R5 C3 安装态独立复审：PASS_LIMITED

固定 HEAD `740af2bddbc1199762c750be2f98474feaadb5a6` / tree `0ef706cca75acefaba218f714ffbc5c29f5d8aae`，parent R4 `02a6d44da85cf4ecde9d84d4587f648587c41597`。本轮只审查 C3 收窄错误隔离的变化，**四条有限实际安装轨迹首轮 4/4 PASS，无 must-fix**。没有重跑 R4 的九项行为矩阵、原 16 Host 流程、browser、unit 或 recovery 宽套件。本结论不代表整卡或真实效果验收。

## 固定安装与只读边界

实际执行 Python 为 `/workspace/work/rc3/reviews/env-04-r5-installed-740af2b/bin/python`，使用绝对路径、`-I -B`、私有 review cwd、短 TMPDIR、offline wheelhouse。执行前等待 Root 明确 READY，没有抢跑安装。这是同 wheel 的独立非 editable CI-like validation 环境，版本 `1.0.0rc3`；不是 managed release 激活或 HOME/Host 切换证明，也没有往 managed 安装里添加 dev 依赖。

wheel SHA256 `0690dd667da48d4fe47fc2202489f73a9e029900a010163b72ef2ae2e4ddc48e`；managed manifest `fb6271c4bf24c4c4662183d44127bdd8651c86718cde7c967d5e0c431bf7cae5`。Root 的四角色严格报告 `e6e5867ff56aa3dd6660786846709c064120214ffeacccd6f9cae688e375a722` 仅引用为 270 canonical + 1 generated / PASS_BYTES_ONLY，不当作真实 Host 方法应用或专业判断。

本 reviewer 独立核对全部 **3944 tracked 文件** 与 Root fixed before，HEAD/tree/status 均精确相同且 clean；独立枚举 validation 包与 managed 包各 **358 文件**（包括原有 bytecode）。四条探针前后两份 `identity-before.json` / `identity-after.json` 逐字相同，所有 tracked、包文件、模块/版本与 manifest 不变。没有改核心、源码、产品测试、旧项目、已有安装、SDK validator、Git 或门禁。

先实际预载 30 个 installed deck_master 模块，再追加仅固定 `tests/rebuild` helper 路径，具名 helper 只构造 L1 输入。最终审计的 **50 个 deck_master 模块 origins 全部位于固定 R5 validation site-packages**；没有 source core、PYTHONPATH、pytest/conftest 或 monkeypatch，没有执行 imported test 函数。`run1/runtime-origins.json` 保存完整来源。

## 四条实际轨迹

| 场景 | 真实前置和观察 |
|---|---|
| C3 真实 icon Task 坏 JSON | 使用明确 L1 icon fixture，经当前 public request/方向/grant/fidelity workorder 和实际零 image-call icon dispatch，定位 Document.tasks 的真实 Ref，然后只损伤自己新建项目的该对象 bytes。损坏前前审 satisfied=true；损坏后前审 unreadable/satisfied=false、所有 required units missing、review_refs/satisfied_units 为空、via=null，并保留原件恢复提示。 |
| restricted asset | 只允许 p1 blueprint、最多 1 call / 0 candidate 的真实 grant；先通过实际 L1 current manuscript fidelity task/claim/adoption，证明前审健康。当前 update_design 拒绝 restricted 资产，完整项目不变；另以明确 L1 历史坏设计 commit 注入故障后，preproduction、实际 strict blueprint dispatch、public continue 均传播原 ModelError，path 精确为 design_context/allowed_asset_ids，没有改标 unreadable 前审缺证。 |
| unspecified asset | 与上例同样独立创建、同样窄范围与真实前审前置；三处均传播 ModelError / design_context/allowed_asset_ids / not allowed for external use。没有派发 blueprint 或预留/开始 image call。 |
| missing asset | 当前 update_design 以实际 ServiceError/unreadable 拒绝缺失 artifact，完整树不变。另在自建 L1 历史坏设计中，preproduction 与 strict blueprint dispatch 传播 StoreError，path 精确 asset:logo；public continue 返回 needs_input、无 pending_tasks，首 finding 为 broken_asset_reference / asset:logo，next_action=restore_or_replace_asset。 |

两个资产权限场景和 missing 场景分别只给 `dispatch.blueprint`、p1、blueprint layer 的有界权限，没有借用 t06 helper 的宽预算。1 call 是实际授权上限，不是发生的调用；所有实际 image/provider 调用均未开始。fidelity 记录是明确 host_self / L1 合成协议，不冒充独立模型、native 或人类质量证据。坏设计 commit 是显式私有历史故障构造，没有伪造 Task、来源、权限或受信回执，也没有 monkeypatch validator。

坏 icon Task 场景中，`collaboration.describe` 与 `ui_journal.project_info` 实际返回原 revision；dispatch.blueprint blocking card 明确 allowed=false/unreadable；`icons.listing` 的原提案仍 dispatch_unknown。直接调用 strict `production.resolve_page_rendering_design` 继续以 ModelError 拒绝，path=`blueprint/provenance/generation_request`、detail 保留 generation lineage。公开 `pipeline.produce` 实际以 preproduction_blocked / unreadable 拒绝。不是仅看状态文本判断严格 resolver 已保留。

每条故障轨迹均保存完整树/Document/Current bytes 的前后记录；所有读取、current write 拒绝、strict dispatch 拒绝、continue 与 produce 拒绝都没有改变项目。损坏 Task bytes 保持原损伤，原 Ref/授权/费用记录不被修补。没有 bundle、生产输出、额外 Task 或隐藏的权限刷新。C3 delivery 的原 decision_needed 证据保留 R4 原标签，本轮没有重复或将其升级为独立 unreadable delivery 判据；本轮也不宣称新 HTTP/Studio/PW 检查。

## R4 证据精确复用

`precise-reuse.json` 将 R4 冻结的实际 validation 包清单与 R5 实际包清单逐项比较：**271 个非 bytecode 成员中 270 个逐字相同，只有 eligibility.py 改变**。87 个 pyc 跨安装不同，完整列出，不说成两套安装整体相同。R5 自身的 358 包文件在本次探针前后全部相同。

唯一产品源码 delta 是 `eligibility.preproduction_state`；其余所有 top-level AST 节点相同。content_production（C2）、C1 三个 UI JS、方法/合同、production 严格 resolver、tasks、service、writer/version/打包规则等实际安装 bytes 均未改变。上述字节事实支持 Root 精确沿用 R4 C1/C2/UI 的原证据；它不表示 reviewer 在 R5 重新跑过它们。R4 本 reviewer 行为报告 SHA256 `e2e97076fb5f61511f33c60f6ce6b5de1344c227686da5f0aac5907cd8951c76` 保留原 9/9 范围与初始作者错误说明，不覆盖重写。

本次使用的 icon_store/confirm/dispatch、fidelity/source_snapshot/authorization helper、_prepare_production/_draft_page 函数另有 R4→R5 精确源字节相同证明；test_service_flow 的其他原测试变更不参与这些 helper 的行为解释。与 Owner live focused 结果不同，本报告结论来自固定 R5 wheel-installed SDK 的实际轨迹。

## 限制与停止状态

没有 reviewer 探针失败或作者修正重跑；全部首轮原件保留在 run1。Root 记录的 R4 原三失败、磁盘耗尽、中断宽测试和后续诊断均保持其原状态，本 reviewer 不将它们归为本轮通过，也不声称 R5 broad/CI 已完成。整体 fixed/installed recovery、source browser/unit、独立代码/UI 与 exact-head CI 由 Root 汇总。

没有真实模型、imagegen、provider、外部付费、人类、professional policy、目标 PowerPoint 桌面或 E1/E2/E3 效果执行。没有读 private oracle、Writer 原生结果或答案库。此目录的 L1 Store 原件只供机械追溯；交接时只复制安全报告、日志和清单，不将 Store/registry/runtime key 当用户交付件。

结论为 **PASS_LIMITED，无 must-fix**；C3 的预期故障读隔离保留，资产权限与缺失资产原错误/恢复契约已在固定安装中恢复。完成后停止执行。
