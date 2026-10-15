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

1. `task start` 带 `--supported-protocol generation.v1`，并逐项声明工作单的实际 required_capabilities，包括新请求的 content_requirements_v1。Desktop 执行身份用当前真实会话/轮次 `codex:<thread_id>:<turn_id>`；受信 SDK controller 使用实际可追踪的执行 locator，不伪造不可得的 thread/turn 或平台调用 ID。
2. 从工作单的 `generation_input` 保存准确 JSON。Page、design_context、template_ref、basis 必须保留任务的真实基准；prompt 保留准确文本，references 写固定文件 Ref 与角色，parameters 只写将实际请求的参数。缺 model/seed 不从配置倒填；不保存密钥。准备内容不代表已经提交。
3. `requests freeze --project … --task-id … --input request.json --base-revision … --operation-id …` 返回 request_id、input_hash 及核心保存的 input。不要自行归一化空白/Unicode 或重新构造历史请求。
4. `task call begin` 加 `--request-id …`，保存回包 attempt_id，再执行一次真实工具调用。网络传输重放使用相同 ID；实际重试需新额度和新 Attempt。unknown 先核实，不自动释放或重发。
5. 当前 Codex 原生图片事件能独立记录提示词、transparent_background 和返回 PNG。要核对无参考图调用，使用以下严格形状，JSON 参数必须来自冻结 input 的原值，不加变量、条件或其它执行语句：

```javascript
const result = await tools.image_gen__imagegen({"prompt":"这里放冻结的准确全文","transparent_background":false});
generatedImage(result);
```

这是调用形状示意，不能把示例文字当本次 prompt。可在首行使用 functions.exec 的 `// @exec:` 设置；其余形状保持原样。核心同时核对运行时保存的调用、原生完成事件、同一调用返回的 PNG，单有这段 Host 文字并不构成证据。普通含变量调用仍可采集原生记录，但参考参数保持未知。

6. 将当前真实 thread_id、turn_id、工具 item_id 写为 `{ "source":"codex_session.v1", "thread_id":"…", "turn_id":"…", "item_id":"exec-…" }`，交给 `task call settle --attempt-id … --report observation.json --outcome consumed`。核心自行读取该本地运行时事件及原始输出，不接收任意日志路径。非空参考图仅在上述严格调用形状中增加 `referenced_image_paths` 的 JSON 字符串数组时可核验：路径必须是本项目冻结 Ref 对应的对象文件，文件 hash 正确且调用开始后未修改；核心记录角色 `reference`。其它包装、外部路径、变量、调用后修改或未暴露的模型/seed 保持未知；缺所需字段不得声称相符。实际参考图流程的验收另见 W07 报告。
7. 实际看图后，按原信封提交文件，并增加 `generation_result` 的 request_id 与 attempt_id。task accept 核对原图字节与真实观察；输入差异拒绝采用，已发生用量保留。用 `requests show`、`attempts show` 和 `view --page-id … --lineage` 反查固定关系。

观察层级由核心确定。Host JSON 即使填写 `provider_receipt`、provider 或 signature，也只作为 Host 申报。这个采集器基于当前用户的 Codex 本地运行时记录，不是供应商签名验证。

## RC3 受信 SDK 原生图像观察

当前宿主的真实 `image_gen__imagegen` 事件若没有 Desktop session 文件，不能造 JSONL 或把输出复制成 Desktop 完成事件。受信 Host controller 可在 Python SDK 启动时配置 `NativeImageRegistry` 和 `NativeImageRuntime`，通过 protected_transport 的 provider 验证真实工具参数、原始 PNG 与完成观察。公开 JSON 只选择 `{source:"native_host_image.v1",provider_id,event_id}`，不能自报信任。

先按工作单实际 required_capabilities 领取、冻结并 begin。新 preparation 的 parameters 显式为 `{"transparent_background":false}`；只冻结本次工具可实际接收的参数。controller 绑定 `image_binding` 的 exact Task/Request/Attempt/allowance、prompt、参数、ordered refs、control 和真实 execution/install identity 与 settlement reader identity。provider 完成记录同时绑定原始 PNG hash、真实开始/完成时间和有效期；未知 platform invocation/model/seed/费用保持 null/unknown/not_reported。SDK 发行的 opaque image context 仅在同一 Runtime 内作为 `tasks.call_settle(..., adapter_context=context)` 参数，不能从 JSON 反序列化。

该保证是实际 controller 观察的 host_attested，没有不存在的供应商签名，也不防共同权限的恶意 Host。SDK 记录原始观察、proof 和 output；普通 Host JSON 保持 host_reported。缺失、过期、外来或控制变化后的 proof 会被拒绝赋级与接纳，但 consumed/unknown 已发调用仍结算，预算不恢复。受信观察不是恢复执行或采用权限。Desktop 原采集版本和历史记录保持原样；所有候选仍需显式采用与当前资格检查。

control 仅绑定该 Task 的真实视觉输入/目标和当前控制；仅 notes 或无关页变更由共享 registered freshness 判断，不能因此重建旧 Request 或丢失未变视觉输出的来源。正文、角色、箭头、目标及暂停/撤权等实际变化仍阻止旧输出接纳。classic 原协议继续原工作单，不因一个新技术 writer floor 自动消费新 requirements 或省略能力声明。

数量判断缺必要数据时返回内容阶段补依据并保留固定文案/限定，不生成装饰数量图或“示意数据”兜底。只有固定稿件明确需要、且不制造量化印象的定性机制或教学示意可保留；不能把空白依据变成推测值。

native SVG/readback 的正式 Page 原子绑定同时检查表格行列归属和节点责任实际几何。合法整体平移/缩放保留关系；同文字换归属或反箭头不能仅凭文字集合通过。工程编译检查与真实非作者模型阅图、人类验收分别记录。

可运行两阶段样例：`examples/workbench/w02_host_roundtrip.py`。prepare 只建立隔离合成项目并返回真实 ID；Host 在两阶段间执行真实 ImageGen；complete 采集、结算、采用并核对唯一调用账。它不替代 SVG/PPT、内容专业或用户验收。
