# W02：冻结请求、Attempt 与真实观察

基线 main `de6293492fca41fbce34e269a4463da111214c2c`；分支 `codex/workbench-w02-protocol`。
本切片已通过 [PR #43](https://github.com/MainQuestAI/Deck-Master/pull/43) 合入 main `09f4486a453d2132a18dbefd10f99ef7317e8fd5`；此文件保留该切片范围，后续 ContentPlan 见 [执行记录](W02-CONTENT-PLAN.md)。
前一恢复切片已通过 [PR #42](https://github.com/MainQuestAI/Deck-Master/pull/42) 合入；本切片不包含 ContentPlan，也没有关闭 W02 整卡。

## 可用结果

新任务在调用前声明 Host 所支持的协议和能力。准确 prompt、Page、设计、模板、参考文件及角色、请求参数、基准一起冻结为 GenerationRequest；核心用 canonical JSON 计算 input_hash。
每次实际调用产生一个 Attempt，绑定原来的 Task.call_allowances；Attempt 只追加输入观察和输出引用，不复制一份独立用量账。
相同 call begin 重放返回相同 Attempt；unknown 保留并阻止新额度，真正的新调用使用新 allowance/Attempt。

原生结果与冻结输入有已知差异时拒绝采用；缺必需观察也拒绝，已消耗的调用事实保留。
Host 报告即使写 provider/signature 或高等级 observer，也不会升级。
采用后的 Artifact、Task.result_refs、请求和 Attempt 可由固定版本 lineage 反查。
summary 只增加 Attempt 数量，正文、完整请求及观察留在详情接口。

## 命令与协议

| 动作 | 当前入口 |
| --- | --- |
| 显式新格式 | create --project-format workbench.v3 |
| 声明能力 | task start --supported-protocol generation.v1 --capability … |
| 冻结输入 | requests freeze --input … --task-id … --base-revision … --operation-id … |
| 绑定调用 | task call begin --request-id … → attempt_id |
| 采集/结算 | task call settle --attempt-id … --report … |
| 反查 | requests show / attempts show；均支持 --revision |
| HTTP | POST /api/requests/freeze；GET /api/requests/Q、/api/attempts/A |

CLI 与 HTTP 复用相同用例；HTTP 写仍要求同源 session token，未给 Host 增设跳过 Origin 的写口。
退出码保留 0/2/3/4/5；能力不符为 2，输入/绑定冲突为 5。具体恢复见 agent-recovery-playbook 的 Generation Protocol。
唯一公共 Skill 和 blueprint-svg 方法已同步。旧工作单走旧协议；新工作单不静默降级。

## 独立观察的真实来源

采集器只接受 thread_id、turn_id、item_id。它在当前用户的 Codex runtime sessions 中找对应文件，核对 session 身份、原生完成事件、调用时间、文件所有权和路径，并比较事件中的 PNG 字节与 runtime 保存文件。
不接受任意日志路径，不读/归档会话推理、聊天全文或其它会话；公开证据只保存所选记录字段和原记录 SHA256。
信任边界是当前用户的本地运行时，**不是供应商签名认证**。

实测 Codex Desktop `0.158.0-alpha.2.1` 的原生图片事件暴露 revisedPrompt、transparentBackground、PNG 与完成时间。
普通带变量的 exec 调用无法据此证明参考图参数，因此[第一轮真实闭环](w02/real-host-partial/checks.json)如实保留 references=unknown，不显示完整输入相符。

进一步验证的窄适配形状是：一个带 JSON 字面量参数的 awaited ImageGen 调用，随后直接 generatedImage(result)，不含其它代码。
采集器不执行或推理任意 JavaScript；只解析这一精确形状，并同时要求原生完成事件及同 call_id 的图片返回字节对应。
只有这三项共同成立，才证明该调用省略了参考图参数。变量、附加语句、不同图片返回均不能升级。
这是实际已执行工具记录的交叉核对，单独一份 Host 声明或代码片段不构成证明。

## 真实闭环证据

[第二轮检查](w02/real-host-literal/checks.json)完成了正式 CLI 的 start → freeze → begin → 真实 ImageGen → settle → accept → 固定 lineage。
所有 ID 来自前一步真实回包；[两阶段脚本](../../../examples/workbench/w02_host_roundtrip.py)不自动伪造或替代中间的 Host 调用。

- request_id：`req-b0741a7a183b46479966d6891dbcdf38`。
- input_hash：`e62ee707ffb1531ce9373ad51fda4d0fc6d999216dca708e84a1d469e71d6fac`。
- attempt_id：`attempt-164c75b9584a4262b52f0f289d5b3f5d`。
- 工具调用：`exec-e7c58705-bb0f-45aa-bd4e-9f730bcf55c2`。
- 原图 SHA256：`0db863ab13734a8609efd81563245fc704f1130e947791ac5de97b4dfab48574`。
- 同一调用账中 1 allowance、1 Attempt、1 consumed；冻结的 prompt、请求的 transparent_background、未传参考图及返回原图对应。

保存了[完整输入](w02/real-host-literal/request-input.json)、[核心冻结回包](w02/real-host-literal/freeze.json)、CLI 进程退出码与 stdout、[Attempt](w02/real-host-literal/attempt.json)、[采用后链路](w02/real-host-literal/lineage.json)和[原始 PNG](w02/real-host-literal/native-output.png)。编码小向量和这个完整请求向量均可重算。
原图是内置工具按冻结 prompt 真实生成的合成业务页，已实际阅图；没有客户素材、供应商密钥或专业验收声明。

能力边界：model/seed 未请求且 runtime 未暴露，保持未知。非空参考图附件与更多参数的独立观察尚未由此适配器验证；不能把此无参考图样例外推为任意图片编辑能力。W05 的强语义须同时看 coverage/comparison，不能只看 observer 标签。

## 兼容与验证

旧项目仍用 v1 pointer，核心不自动迁移。显式新项目用 v2 pointer 与 minimum_writer，旧核心在进入写入前拒绝。
已用真实旧提交 `de629349…` 的源码，在独立解释器中运行旧 reader 和 writer：[机器结果](w02/old-core-compatibility.json)。旧读退出 2，旧写退出 4，指针完全未变；旧版本的错误文案较笼统，按本文使用匹配核心。
旧 UI 仍可以连新核心读取原字段；默认入口没有切换。新增冻结命令在加锁前拒绝旧 run 和无效项目，不在其目录创建新格式布局。

相关回归：237 passed，7 项 render 测试在本地该命令中排除；后续取消/完整向量及旧项目保护用例加入后，定向协议/采集/读投影/schema/CLI 检查 82 passed。Ruff 通过。
新增覆盖：能力不足、冻结重放/异 payload、准确编码、真实读取/HTTP 同源约束、Attempt 与唯一额度、unknown/新重试、取消晚到、不同 prompt/参数/图片、缺参数观察、Host 伪升级、原生调用重复登记、原记录/图片/路径损坏、字面量调用的保守识别。

```sh
PYTHONPATH=src python -m pytest -q -p no:cacheprovider \
  tests/rebuild/test_generation_protocol.py tests/rebuild/test_tool_observations.py \
  tests/rebuild/test_task_receipt_recovery.py tests/rebuild/test_tasks.py \
  tests/rebuild/test_production.py tests/rebuild/test_flow_quality.py \
  tests/rebuild/test_store_transactions.py tests/rebuild/test_workbench_reads.py \
  tests/rebuild/test_web.py tests/rebuild/test_workbench_e2e.py \
  tests/rebuild/test_package_boundary.py tests/rebuild/test_cli.py -m 'not render'
python -m ruff check src/deck_master tests/rebuild examples/workbench
```

W02-AC03/04/05 的核心行为及 AC06 的能力/结果引用有工程证据；AC07 的无参考图真实请求绑定已有独立工具记录。ContentPlan、完整旧稿目录回退与 compose 扩展仍留在 W02 下一切片。新工作面浏览器、安装、用户验收和发布没有由本切片验证。
