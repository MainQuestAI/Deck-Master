# RC3-04 前置切片

本切片基于 RC3-00 接收后的 main `deb9e4e3007a6d72476d6290663ca840c4f3e556`，只提供 RC3-01 所需的方法/Host 消费及证据边界。它不关闭 RC3-04 完整切片，也不将工程检查等同于专业、Owner、听众或桌面验收。

## 方法与实际入口

- editable 从运行模块所属 checkout 的 `skills/deck-master` 读取；安装版从该包的资源读取。不借用 cwd、另一安装或陈旧 editable 包副本。canonical Skill 缺失会报具体错误。
- `deck-master methods --kind compose --phase argument --read` 返回真实 UTF-8 字节及 hash，保持 CRLF。preproduction review 读取已有 source/content/examples/review 方法；内容补强和 calibration 由 RC3-01 加入。
- `deck-master methods --project PROJECT --task-id TASK` 返回实际工作单、派发方法身份、当前方法身份和正文；`basis_changed` 保留历史方法身份，不把新方法反写旧 Task。`runtime_returned_bytes` 只说明 Runtime 返回了字节，不证明 Host 应用了方法。
- `deck-master capabilities` 同时显示 source/module/package/install 身份、实际方法 digest 和三类受信通道能力。源码存在、包安装、Host 读取/应用分别记录。

最小协作 CLI 复用原 SDK 事务与权限：`collaboration show`、`request start/replace`、`decision`、`adopt-proposal`、`migration describe/apply`。读操作不写 current；写操作复用 base revision、operation ID、原收据幂等及统一 eligibility。输入文件包含 `base_revision`/`operation_id` 与相应业务对象，也可用同名 flag。源码中的例子、tests 的合成稿件不能当作用户确认来源。

RC3-01 可从真实 `create --project-format workbench.v3` 开始，显式 migration describe/apply，然后以当前指令来源建立 request，沿 compose.v2 工作单、decision/adopt 提交内容，不需要私有 Store 初始化或生产 fixture。默认 writer 切换、Studio、外部报告、四 Skill 安装和最终 RC3 版本统一由完整切片交付。

## 受信 provider 边界

`review_evidence.ProviderRegistry` 仅由受信服务启动代码注册 `ReceiptProvider` 实例；没有默认 provider，不从请求 JSON、CLI flag、环境变量模块路径动态载入 provider。注册代码属于部署信任边界，运行任意 Python 的调用者不能因此被当成人类。`ProviderRuntime(registry).bound()` 在受信服务初始化域绑定并封存该实例的 issuer；普通 new registry/register/mint 不改变当前 Runtime，foreign context 被拒绝。请求处理器不能从 JSON 选择 Runtime 配置。该边界不承诺抵御同权限代码重新配置可信 bootstrap。当前环境不存在可直接核验 collaboration 平台收据的适配器，故三个能力默认 false，审查稿保持可读取并返回 `needs_reviewer`。

provider 实现 `health/fetch/verify`；其 `verify` 必须通过受信的非作者 Host controller 直接观察 native spawn/canonical sender/完成状态/固定输入与输出，或受信传输/外部签发者验签，验证真实执行身份/完成事实及作者来源，不接受作者自报或同 Host 改 ID。普通独立模型前审不要求平台密码学签名；真实 native controller 路径可以明确保留 host_attested 保证。CLI/HTTP 提供的 JSON、哈希、TTY、截图、本地同权限密钥不建立身份隔离。本模块只在 provider 完成认证后检查 Runtime 精确绑定：project、request、Task、完整 packet、subjects、作者执行身份、只写 Review 的范围、规范化结果 hash、事件和有效期。真实 native 观察、签名算法/传输与身份核验由实际 provider 集成提供，不能把该 SDK 接口的存在当成已有真实认证能力。

通道健康能派发，完成回执才能接纳；能力 context 中没有未来回执。完成 receipt 经选择器 `provider_id/event_id` 查询、认证后产生 opaque `TrustedContext`；JSON、普通 dict、拷贝或直接创建同名对象不能生成它。Python SDK 可调用 registry.review_context 后传入 service.accept_result。实际集成在受信 bootstrap 注册 provider，并在 `ProviderRuntime(registry).bound()` 域内调用服务；CLI `task accept --review-receipt-selector FILE` 只接收选择器，没有 provider 时诚实拒绝。

完成审查的原始认证事件和绑定 proof 进入不可变 Store，并随 Task result_refs 在接纳事务中引用。user_event 的认证原始 bytes 必须与已有 transport_receipt_ref 存储的 bytes 完全一致；不同认证原件被拒绝，不改变 source_ref，也不把仅存hash当成认证审计。缓存 context 在消费时重查当前 Runtime issuer、对应 provider/channel 健康与 issued/expires；过期或离线的用户事件不升级 verified_user，按 traceable 保持真实 Host 转述等级。结果费用结算仍先于内容接纳；已提交相同结果的幂等重放不要求 provider 再在线，不会再次执行或恢复权限。既有 synthetic dict adapter_context 的 Python 调用必须迁移到明确的、测试目录内的 provider double；生产不继续把裸 dict 当受信 context。普通 `host_attested_instruction` 不依赖受信 provider，保持原保证等级和可用性。

## 证据限制

`tests/rebuild/synthetic_review_provider.py` 只用于 synthetic L1，未打包，未修改或绕过 gate。其正例验证谓词与事务组合，不证明真实平台认证、人类身份或专业认可。真实 subagent 执行档案可证明实际不同执行者完成了独立初判，并支持 L2 工作流与 traceable L3 模型评阅；受信非作者 controller 将 native 观察接入此 SDK 后可满足普通独立模型前审。未接入可核对 provider 时仍 needs_reviewer，不冒充 verified_user 或人类 professional delivery。人类 Owner、受众与桌面验收按用户本次安排延后，保持未运行。

## SDK 接入最小范例

以下 `NativeControllerProvider` 是实际 Host 集成提供的对象，当前包不安装或伪造它。它的 fetch/verify 读取 controller 直接观察到的 native 返回、canonical sender、完成记录和固定结果，不能从稿件作者的项目 JSON 取“已验证”声明。

```python
from deck_master import content_review, review_evidence, service
from deck_master.store import Store

registry = review_evidence.ProviderRegistry()
registry.register(native_controller_provider)  # 受信非作者 controller 初始化
runtime = review_evidence.ProviderRuntime(registry)  # 封存当前服务的 issuer
with runtime.bound():
    work = content_review.dispatch_preproduction_review(
        project, adapter_context=registry.channel_context())
    task = work["task"]
    # controller 真正派发独立执行，实际完成后才有 event_id / result_payload
    store = Store(project)
    context = registry.review_context(
        store, store.load_document(), task, result_payload,
        {"provider_id": native_controller_provider.provider_id, "event_id": event_id})
    service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=result_payload,
        adapter_context=context)
```

`ReceiptProvider` 的属性为 `provider_id/adapter_version/authentication/channels`，方法签名为 `health() -> bool`、`fetch(event_id: str) -> bytes`、`verify(raw: bytes) -> dict`。实际独立 controller 只注册 `channels=("independent_review_receipts",)` 和 `authentication="protected_transport"`，不因观察到模型运行就开放 verified_user/human。`review_evidence.review_binding(store,document,task,envelope)` 给出应由真实事件绑定的 project/request/task/packet/subjects/authors/write_scope/result 字段；verify 返回这些经过观察核对的字段，加 provider_id/event_id/channel/executor_ref/issued_at/expires_at。request/author/结果不能由作者声明改写。只写 Review 的任务限制仍由原 accept 路径校验。
