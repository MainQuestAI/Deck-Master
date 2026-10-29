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

I0 生成正在按冻结方案执行。每份沿真实 Task start/accept 产生 framing 和 argument/planned Plan 提案，不向 strict v1 添加字段，不执行正式采用或 Page 生产。原始提示、输出、接纳/拒绝、方法实际字节、token 用量、时间和错误留在仓库外。

目前没有作者初判、三模型辅审或作者终判，未得到 go。按冻结流程先交盲评包并保存作者初判，再给三模型互盲评议，最后由作者终判；至少一套可展开结构须由作者本人确认。工程通过不代替这个关口，D01 及后续依赖仍为 planned。
