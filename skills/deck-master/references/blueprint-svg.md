# Codex 蓝图执行方法

当前版本以 **Codex Desktop** 为唯一已验收宿主。蓝图通过当前会话内置
ImageGen 工具生成；Deck Master 本地包不连接 Provider API、不读取 API Key，
也不声明 Claude、OpenCode 或其他宿主兼容。

收到 `kind=blueprint` 的任务后：

1. 读取 `production_request.prompt`、完整 Page、解析后的设计配置和允许资产。
2. 用 `task start` 领取任务，再用 `task call begin` 消耗本任务的 reserved allowance。
3. 将 `production_request.prompt` 原样提交给内置 ImageGen，并原样保存。需要补充要求时先更新有效输入并重新投影，不在调用时手写另一套正文。不能用后来重建的 prompt 代替。
4. 保存工具返回的原始图片；记录可得的 invocation ref。工具未报告费用或 token 时写
   `not_reported`，不能估算。
5. 实际查看图片，核对页面模块、数值、方向关系和明显文字偏差。原图文字不作为正文来源；
   SVG 重构始终从 Page atoms 恢复精确文案。
6. 用 `task call settle` 记录 consumed / not_sent / unknown，再用 blueprint 信封提交图片、
   实际 prompt、来源和限制。调用已经发送但图片采用失败时仍为 consumed。

当前会话没有图像工具时保持任务 `awaiting_host/needs_tool`。不得改走 fixture、本地占位图、
Provider 配置或向用户索取 API Key。

## generation.v1 工作单

只对明确带 `protocol_version=generation.v1` 的工作单执行本节；旧任务保留上面的协议。
新格式由 `create --project-format workbench.v3` 显式创建，已有项目不原地迁移。

1. `task start` 带 `--supported-protocol generation.v1`，并分别带 `--capability generation_request_freeze`、`--capability attempt_binding`、`--capability native_tool_observation`。执行身份用当前真实会话/轮次 `codex:<thread_id>:<turn_id>`，不能填示例 ID。
2. 从工作单的 `generation_input` 保存准确 JSON。Page、design_context、template_ref、basis 必须保留任务的真实基准；prompt 保留准确文本，references 写固定文件 Ref 与角色，parameters 只写将实际请求的参数。缺 model/seed 不从配置倒填；不保存密钥。准备内容不代表已经提交。
3. `requests freeze --project … --task-id … --input request.json --base-revision … --operation-id …` 返回 request_id、input_hash 及核心保存的 input。不要自行归一化空白/Unicode 或重新构造历史请求。
4. `task call begin` 加 `--request-id …`，保存回包 attempt_id，再执行一次真实工具调用。网络传输重放使用相同 ID；实际重试需新额度和新 Attempt。unknown 先核实，不自动释放或重发。
5. 当前 Codex 原生图片事件能独立记录提示词、transparent_background 和返回 PNG。要核对无参考图调用，使用以下严格形状，JSON 参数必须来自冻结 input 的原值，不加变量、条件或其它执行语句：

```javascript
const result = await tools.image_gen__imagegen({"prompt":"这里放冻结的准确全文","transparent_background":false});
generatedImage(result);
```

这是调用形状示意，不能把示例文字当本次 prompt。可在首行使用 functions.exec 的 `// @exec:` 设置；其余形状保持原样。核心同时核对运行时保存的调用、原生完成事件、同一调用返回的 PNG，单有这段 Host 文字并不构成证据。普通含变量调用仍可采集原生记录，但参考参数保持未知。

6. 将当前真实 thread_id、turn_id、工具 item_id 写为 `{ "source":"codex_session.v1", "thread_id":"…", "turn_id":"…", "item_id":"exec-…" }`，交给 `task call settle --attempt-id … --report observation.json --outcome consumed`。核心自行读取该本地运行时事件及原始输出，不接收任意日志路径。当前版本不证明非空参考图附件或未暴露的模型/seed；缺所需字段不得声称相符。
7. 实际看图后，按原信封提交文件，并增加 `generation_result` 的 request_id 与 attempt_id。task accept 核对原图字节与真实观察；输入差异拒绝采用，已发生用量保留。用 `requests show`、`attempts show` 和 `view --page-id … --lineage` 反查固定关系。

观察层级由核心确定。Host JSON 即使填写 `provider_receipt`、provider 或 signature，也只作为 Host 申报。这个采集器基于当前用户的 Codex 本地运行时记录，不是供应商签名验证。

可运行两阶段样例：`examples/workbench/w02_host_roundtrip.py`。prepare 只建立隔离合成项目并返回真实 ID；Host 在两阶段间执行真实 ImageGen；complete 采集、结算、采用并核对唯一调用账。它不替代 SVG/PPT、内容专业或用户验收。
