# Root RC3-03 p04 真实工程试验入口

这是中间入口脚本，尚未执行 SDK 集成或图像调用。只在新冻结源码完成独立复审 PASS、且 Root 接纳对应隔离 wheel 后执行。脚本 admission 仅验证安装身份与实际 wheel/core 字节，不能代替代码复审结论。

固定输入为同目录 `input-project` 的 107 个原始文件和真实对话授权来源 `controlled-pilot-authorization-note.json`。脚本校验二者固定哈希，复制完整八页工程到指定的新工作目录，每一步检查全八页、Narrative、Plan、内容依据、来源与 outputs 的 Ref 均保持，并通过实际 Store 字节读取器逐个核对工作副本中全部原始 immutable object 的字节数和 SHA，包括 `sources[].extract` 及内容对象内的嵌套 Ref。对象集合只来自固定复制清单，不将任意文字路径或历史 URL 当成 Ref，也不回源下载补偿缺失。不会改原工程或纯输入副本，不导入测试 fixture。

建议 Root 分三次执行，每次检查实际结果后再继续。所有命令使用同一 `--project`、`--manifest`、`--expected-source` 与 `--out`。路径示例留待 Root 选择；`--project` 和 `--out` 必须是本 pilot 目录下彼此分离的新目录，均不得包含或落在 `input-project` 内。

```bash
<admitted-installed-python> -I -B /workspace/work/rc3/native-image-pilot-03/prepare-pilot.py init --project <new-working-project> --manifest <admitted-manifest> --expected-source <reviewed-full-source-sha> --out <new-preparation-records>
<admitted-installed-python> -I -B /workspace/work/rc3/native-image-pilot-03/prepare-pilot.py feasibility --project <same-working-project> --manifest <same-manifest> --expected-source <same-full-source-sha> --out <same-preparation-records>
<admitted-installed-python> -I -B /workspace/work/rc3/native-image-pilot-03/prepare-pilot.py begin --project <same-working-project> --manifest <same-manifest> --expected-source <same-full-source-sha> --out <same-preparation-records>
```

- `init`：逐文件核对 source-copy；核对实际 installed site-packages、interpreter prefix、manifest、release 与 wheel 全 package 文件；创建新工作副本及初始内容证据。无正式 Request 或 Task。
- `feasibility`：明确替换原 content-only Request，创建 p04 only、design only、exploratory 的正式 design_trial Request 与零调用/零候选 grant，actions 仅 design.feasibility/design.propose。提交基于实际稿件角色、布局、完整限定、实际字体与配色的 v3 feasibility proposal；不 confirm、不 dispatch。此阶段可选；若执行后报错，禁止直接进入 begin。
- `begin`：明确替换当前 Request；p04 only，layers 为 design/blueprint，purpose exploratory，无 Plan manifest 扩权。正式新 grant 为 1 call、1 candidate、candidate_only；actions 精确为 design.propose/design.update/change.commit/task.start/call.begin/allowance.allocate/task.accept，无 candidate.adopt。随后通过实际 propose → confirm → plan(max_calls=1) → commit → task_start → 完整 prepared_input getter → freeze → call_begin，停在 BOUND_NOT_DISPATCHED。

初始设计使用零参考、显式 `transparent_background=false`；保留实际颜色、字体和字号。布局来自 p04 的四节点主链、三条原始关系、两行三列异常表。满字、方向、责任、限定与表格归属继续由真实 SDK requirements/getter 完整传递。不能放下的内容应报告不可行，不能压缩字号、删改正文或挪入备注。

每步在执行前独占保存精确 SDK 参数（含真实 operation_id/base_revision），执行后保存实际返回 JSON 与完整当前 Document；保存真实 Task、prepared input、Request freeze、attempt、实际待发送 tool arguments 和安装身份。SDK 返回为内存对象，记录是其无损 JSON 表达，并非平台原始传输字节。异常保存实际 payload、类型、traceback，立即停止；不自动重试、不 rollback，不补造成功记录。若调用已提交但结果保存失败，应按实际 Store 状态检查，不能再次派发。已有记录或错误会阻止重入。

`begin-completed.json` 给出实际 task_id/request_id/attempt_id/allowance_id，可供 Root 的独立 `native-controller.py prepare` 绑定。此脚本没有 imagegen、settle、accept、adopt、SVG、compiler、desktop 或评审签发入口。call_begin 只预留一次调用，实际图像调用数仍为 0。Root 应在真正发送前通过 controller 的共享 freshness/control/attachment 复查。

授权证据为真实对话与清楚标注的 Root 有限工程选择，SDK 计算 host_attested；没有 verified_user、人类或平台签名声明。Q2-B p04 是已见工程回归样页，本次不会被记成公平 E2、原始 12 任务、人类受众或桌面验收。完整八页 outputs 保持原状，之后一页工程 PPTX 也不得冒充整套交付。

`stop_conditions` 使用空列表，不把自然语言塞入 schema 的条件代码字段，也不虚构自动执法代码。范围、操作集合、调用与候选额度、candidate_only 及无采用权限仍由正式字段约束；遇错停下和不得重试的工程要求仍保留在真实授权来源与本入口控制中。run-01 的 grant 输入 schema 错误及已成功的 Request 保留原件，不重试、不回滚；修复入口只用于全新 run-02。
