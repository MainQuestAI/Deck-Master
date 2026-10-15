# RC3-04 R3 独立行为 delta 复审：PASS（有限实际安装范围）

固定 HEAD `a53a265321ca6bb15f347bbe23b5143fe8b7378c`，tree `31cca075ac76877908e04f030f0c4e815d3a6268`，parent `573a46a85bf93d71a13652756bc3a6cdb1fab6ae`。本 reviewer 对授权的 F9/C6 delta 完成 **5/5 有效轨迹，未发现 must-fix**。此结论不等于整卡 PASS，也不代替 Root 的 fixed broad suites、code/UI/B review、专业/人类或目标桌面验收。

## 固定身份与执行来源

实际产品 Python 为 `/workspace/work/rc3/candidate-04-a53a265/prefix/.deck-master/releases/a53a265321ca-01177541b9a1/venv/bin/python`，所有探针使用绝对路径、`-I -B`、私有 cwd `/tmp/rc304br3`、短 TMPDIR，无 PYTHONPATH 或 conftest 注入。加载 `env.sh` 仅为工具链；shell 显式 PIP_NO_INDEX=1 和本地 wheelhouse。所有 imported deck_master 来自该实际安装，版本 `1.0.0rc3`，非 source env / 旧 release。

manifest SHA256 `a338a72fb577890e77fbf6f5b0f25663f551b85d77eb04f85706a9c59c59368e`；wheel `01177541b9a1bc38aefb50fd6c8e8499b6bae4a6afe59b7b467693fc1bd740fb`。Handoff 实际 SHA256 `23178a7d2383ecd08b88fe4240d30cff4a126fe3f88cb5221508e02e1da3326d`。Root 的四角色严格 byte report SHA256 `9209595b80d313436dd9bbd98443466f8e0da5668e55517271db907afc3bcb4c` 仅引用为其 PASS_BYTES_ONLY，非本 reviewer 的真实 Host 应用证明。

本 reviewer 以 Root fixed source-before 为基线，自行比较 **3622 tracked files**；实际安装包自行枚举 **358 files**。`source-install-before.json` / `source-install-after.json` 均确认固定 HEAD/tree，前后 changed tracked / installed paths 为空。没有修改产品、产品测试、fixture、Git 或 gate。私有 probe 与全部项目/事件只在本 review 目录内。

## 实际公开正负轨迹

| Case | 结果与实际边界 |
|---|---|
| F9 原句及有限路由 | 原句“请协调这次档案值班培训的策划与后续职责，先把真实范围和下一责任说明白，不制作整套PPT。”逐字输入，返回 deck-master / content_intent=null。另 14 条有限控制覆盖中文统筹、英文 orchestrate、主题为协调的正文写作、三个显式 Skill 优先、审查/恢复、原 F7 p2 句和四个 content 子意图，全部预期正确。 |
| F9 实际 method read | 在真实已创建项目上 public read_skill_methods(natural) 为原句返回 Master 与当前原 request；实际 method path 全位于固定 release，逐文件读取 bytes/hash 与返回值一致。尝试 Content 职责以 ValueError 拒绝。整个项目树、Task、scope/授权和费用前后不变；host_application=not_recorded，不冒充 Host 已执行方法。 |
| C6 公开 inputs auto | 用明确零调用授权，真实 content_ops.inputs 更新 audience 且 reason 包含 API、Page v2、proposal Ref、换行和 emoji。真实 compose.v2 input_revision Task 在 live listing / detail / fixed listing 显示一致安全摘要，完整保留 reason；内部 UUID operation、compose.v2/changed_layers/Ref 包装不混入摘要。 |
| C6 公开 editorial auto | 公开 narrow p1 request / direction / grant，再 content_ops.plan/commit rewrite，产生真实 compose.v2 Task。p2 和当前 Page refs 保留，摘要只展示原用户要求及“其余页面保持”；原 raw instruction 完整可读且不改。 |
| C6 inputs / editorial trial | 分别执行真实公开 trial workorder，摘要与 auto 同样保留用户原话并清楚显示候选语义；没有执行 Host/adoption，也未开始外部调用。 |

执行记录按 1 条 F9 case + 4 条 C6 workorder case 计 **5 条**，不是将表中辅助步骤另算通过数量。原始 `run1/results.json`、`events.jsonl`、`runtime-identity.json` 和成对 snapshots 保留。没有 case FAIL 或探针修正重跑。

每个真实 C6 Task 均核对 stored Task / public raw instruction 保持相同，live/fixed/display 一致且整个项目树读取前后不变，call_allowances 为空，未改变权限或费用。在这些真实 Task 的**私有复制值**上，再运行安装的纯 task_row 投影：每 Task 各测试追加普通文字、追加换行说明、未知 template，共 **12 条控制全部全文 fallback**，复制值也不被函数修改。公开 API 不提供任意改写 immutable Task.instruction，本 reviewer 没有向 Store 注入改写值；这 12 条是纯投影边界测试，不冒充持久化公开更新场景。

## 精确复用与未运行

`r2-r3-byte-delta.json` 保存从 R2 原安装记录到 R3 的完整路径/hash 比较：source 共 52 changed/new paths，产品仅 method_resources.py、run_desk.py 和两处 UI JS；实际安装 non-bytecode 也仅这四项改变。实际安装有 87 个 pyc hash 跨 release 改变，原差异完整保留，未将其说成“整个安装与 R2 相同”。

R2 已过 C5 / Plan / reconcile / four-layer / F8 / style 等模块的实际 `.py`、相关 contracts/resources 未发生本轮业务改动；另逐项记录 service、content_ops、content_plan、content_production、tasks、collaboration/binding/budget、eligibility、generation、restoration、editing、visual_styles、store/models 等 **17 个实际安装模块 hash 相同**。依 Root 授权复用 R2 的有界证据，不重复相关测试。R2 原报告 SHA256 `ae12afd0a74d20abfc6864bff2db3d046c660c9c72c670df3754fc6625f23c87` 保留原候选标签；该复用不把 R2 的未测权限/费用/全矩阵自动转为通过。

测试变化仅只读抽查九文件，详见 `test-delta-readonly-review.md`、`selected-test-delta.diff` 与文件 hashes；没有发现所读范围内明显弱化领域结果或新增产品绕行权限。明确说明九个工程 render case 已从发布正例变为“正式拒绝 + 外部真实工程诊断”；其 compiler/readback/pixel/geometry 断言保留，不能混称完整 production 正例。这个只读结论不作为 installed 行为证据，不代替 code reviewer 的全 delta 审查。

UI-O1/O2 由独立 UI reviewer 负责；B 的 F9 实际职责输出、Root unit/render 均未由本 reviewer 重复。未运行 benchmark、模型/imagegen/外部付费调用、真实 native receiver、独立专业 reviewer/human、目标 PowerPoint、全 CLI/HTTP/Studio 套件或原 12 risk groups 全重跑。所有本地业务数据明确 L1_SYNTHETIC，无受信 context/伪 native/human。

该有限 delta 已完成，停止扩展；整卡状态与 merge 决定由 Root 汇总原规范、固定套件及其他独立审查后给出。
