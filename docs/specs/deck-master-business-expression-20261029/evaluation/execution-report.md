# D00a / D00 执行记录

时间：2026-10-29，Asia/Shanghai。代码基线 `035845f228d1ba4cd7fc9b41cdedd8fd734043df`。分支 `codex/business-expression-d00`；隔离工作树实施，原 checkout 未修改。

## 已完成的工程与输入检查

重新 `git fetch origin`；相对方案代码基线 `ce4ef8b2` 只有文档变更，`src/skills/tests` 无差异。按现有 Agent 入口、恢复规则与 D00 卡核对，未实施 D01 或修改活动 Runtime 合同、产品方法。

为本次评测选择 5 包明确合成输入，固定开发 2/留出 3 和各自首提/竞标任务。`manifest.json` 与 `tasks.json` 保存版本 hash。两包开发材料完整读取，原始字节、SHA、全部行定位及末尾约束均一致；留出只核验字节/hash，不创建项目。所选材料没有电子表格，X01 保持 inactive；该结论不代表 xlsx 已获支持。

真实 `service.create` 创建 4 个独立开发项目，均为 `content_only / plan_only`、0 Page、framing `awaiting_host`，正式冻结方法来源 `current`，每任务实际返回 46,524 bytes 方法；内容字节和 SHA 保存在本地证据目录。仅证明返回与入口，不证明 Host 应用或内容效果。

首次分诊脚本把新 Task 的状态错误地预期为 `pending`，实际为 `awaiting_host`，因此 r1 报失败；修正检查后以新目录运行 r2 通过。失败目录保留，未把该脚本错误报告为产品缺陷。

| 验证 | 本次结果 |
| --- | --- |
| 独立 Python 3.12.12 venv，可编辑安装本工作树 | 成功；未激活 HOME Skill 或修改默认安装 |
| `python -m deck_master doctor --step compose` | ready，module_path 指向本工作树；professional_evidence=not_evaluated |
| D00 指定的两文件 `pytest --collect-only -q` | 41 项用例可收集 |
| `pytest -q`：test_content_contracts、test_rc5_resource_catalog、test_rc5_host_selection、test_sources、test_main_iteration_sources | 105 passed，5.50s |
| `evaluation/triage.py --out <新目录>` r2 | pass，0 模型调用；详见 input-triage.json |
| `ruff check` 两个评测脚本 | 通过 |

## 评测条件与授权

作者已明确回复“按上述订阅额度执行”：最低档，5 包合成材料，I0 8 份配对策划小样，现有订阅额度最多 32 次请求，零新增 API 付费，不购买额度。`freeze.json` 固定具体请求模型 ID、推理设置、预算、材料与实验/模板 hash；`protocol.md` 保留公平基线、盲评与失败保留规则。冻结前没有模型生成结果或评分。

D08 的规模、质量门槛和模板已固定；其完整内容调用费用未授权，不能从 I0 预算暗扣。模型实际响应未暴露的后台快照和采样字段保持未知，CLI 版本、登录状态或请求 ID 不作为实际后端快照证明。

## 内容生成与作者关口

I0 已按冻结方案完成 8 份完整策划：2 开发包 × 首提/竞标 × 基线/实验。每份沿真实 Task start/accept 产生 framing 和 argument/planned Plan 提案，不向 strict v1 添加字段，不执行正式采用或 Page 生产。原始提示、输出、接纳/拒绝、方法实际字节、token 用量、时间和错误留在仓库外。仓库 [generation-evidence.json](generation-evidence.json) 保存去除本地路径的实际调用、版本/hash 与工程核对；相同方法清单按有序 manifest hash 去重，不复制方法正文。

| 本次实际观测 | 结果 |
| --- | --- |
| 生成请求／独立会话／完成 turn | 16／16／16；没有工具调用或生成重试 |
| 完整策划 | 8/8，Narrative.v1 + planned ContentPlan.v2，均为未采用提案 |
| 请求范围 | 8 个项目均 completed/closed，0 Page，current Narrative/Plan 均未采用 |
| 来源与计划引用 | 全部来源版本、单行定位、Plan 节点/限定引用有效；这是定位和工程检查，不是事实语义评审 |
| 首次接纳 | 15/16；1 次来源对象 path 抄写错误被拒绝，原始结果保留 |
| 技术修正 | 仅修正该 path：source ID、原件 hash 和 extract SHA 已正确且一致，替换为原任务给定的对象路径；不改节点、主张、正文、定位或选项；额外模型请求 0 |
| 费用与额度 | 已启动 16/32 次；保留 12 次辅审 + 4 次失败重试余量；新增 API 付费和购买额度均为 0，套餐 token 无法据此换算实际金额 |
| token（CLI 原始观测） | input 804,656（其中 cached 253,952），output 199,677；reasoning_output 25,799 为另存的原始字段，不重复相加 |
| 冻结完整性 | 材料、任务、协议、实验补充、模板及生成脚本 SHA 与首个调用前记录一致；留出生成 0 |

CLI 未暴露可证实的后台模型快照或内部网络重试次数；保留具体请求 ID 和可见使用量，不补造未知字段。开始时出现模型目录刷新超时，首个请求随后正常完成并被接纳，未因该日志重发请求。

另实测完成项目的 `deck-master continue --json` 返回 `status=completed`、`next_action=return_requested_content`、`pending_tasks=[]`，未继续 Page 或视觉生产。

四对作者初判稿已生成：P01 会员首提、P02 会员竞标、P03 售后首提、P04 售后竞标。A/B 使用系统随机源分别分配，版本映射单独保存在盲评包之外；包内保留完整可读策划、逐页安排及语义结构/来源对应，只去掉版本身份、方法标识和内部路径。已核对 4 对/8 稿及全部链接，包内无 baseline/experiment 项目标识、方法编号或本地绝对路径。盲评包未包含模型反馈。

本地证据入口（相对本机 Codex 临时目录，不随仓库分发）：`deck-master-business-expression-20261029/author-blind-i0/README.md`。完整运行位于同任务目录的 `i0-r1/`；输入分诊 r1/r2 均保留。应用文件面板打开请求仅返回 queued，不能声称用户已经看见。

2026-10-29 收到作者“基本同意 kimi”的反馈及四份外部评审，见 [评审核对记录](review-reconciliation-20261029.md)。2026-10-30 作者明确回复“是，按此结论继续”，确认 P01-A／P03-A 与 P02-B／P04-B 可展开并同意进入 D01／D02a，见 [作者继续结论](author-go-20261030.md)。据此关闭 D00-AC03 及 D00；未补造此前缺失的作者初判、逐项分数或外部模型身份证明。I0 原始 16 次生成、冻结条件和全部结果保持不变；D02a 的新增四次校准另有明确额度分配，不改写 I0 结果。

2026-10-29 I0 阶段校验（历史记录）：三个评测脚本 Ruff 通过；JSON、证据链接、71 项 AC 的唯一归属、8 份策划/16 请求及三个去重方法 manifest 的 hash 均有效；`git diff --check` 通过。当时 `git diff --exit-code origin/main -- src skills tests` 无差异，未提前实施后续产品单元。生成运行和盲评包均留在本地，没有提交原始运行或正式采用。

2026-10-30 后续：D01 已实施 Narrative.v2 与能力边界，服务级零页面策划可正确接纳和顺序采用，最终相关回归 313 passed；[D01 证据](../implementation/D01-validation.md) 区分工程通过与专业内容判断。D02a 经明确授权新增 4 次调用，累计 20／32，均首次工程接纳，但两份策划仍有具体取舍回退；[D02a 记录](../implementation/D02a-validation.md) 保留原结果、R2 修订及待决第二轮额度。D02b 尚未启动；未安装 HOME、合并或发布。
