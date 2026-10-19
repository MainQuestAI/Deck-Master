# PR124 第二轮指定复审修复

复审对象为 `87bbccab9c57af0e5bb981b8916c11e0d929462e`，完整结论见[指定聊天复审](https://chatgpt.com/c/6ad57133-6f3c-83ea-879a-72865126ed6c?messageId=bf975b08-4005-5363-bf22-233df3c31bc9)。原四项 P2 明确关闭，顶栏无新阻塞；原 head 的 PR/push 两套完整 CI 已成功。以下两项新增 P2 单独修复，不以旧 CI 抵消新反例。低成本 P3 同轮补齐，真实台账原本的70项映射没有错误。

| 新发现 | 修复与实际证据 |
| --- | --- |
| R2-P2-1：preparing 跳过 identity=null 的 witness | witness 不论身份是否已确认，都必须仍匹配 intent 中冻结的 expected 身份。证据缺失或不一致在重建准备 namespace 前即报 installation_recovery_conflict，外部 current、残留与原 journal 不动。普通未确认 .after 仍不认领，保留原 inode/hash/mode，并允许原请求用新准备 namespace 接续。 |
| R2-P2-2：真实旧 logical Host 请求被 canonical 字符串误拒 | 仅对没有 host_access_path 的真实旧格式，保留原 logical Host 字符串绑定；新格式继续绑定实际目录。请求匹配与后续父目录、访问链、动作所有权证明分开，不 resolve 任意旧路径来放宽绑定，不改旧 terminal journal。 |
| R2-P3：台账汇总漏验完整 AC ID→Owner 集合 | 直接读取原 traceability.json，在汇总前拒绝缺失、未知、替换 ID 和 Owner 错配。没有第二份硬编码70项清单，也不修改逐项判定、证据或用户延期观察。 |

生产代码仅改 install.py 的请求匹配和准备物验证，activation_transaction.py 未改；CLI、项目 writer floor、协议、授权和 provider 不变。新增历史控制测试的 CI 浅克隆只补取 bc6bd55a07b249660e6af8ab4b19a147bb2caf14、001c8f101e07cab1b230e0745a6f0b17fb54882e 两个固定对象，原 RC3 baseline 获取不变。

## 反例和回归

修复前对应五例均 FAIL。真实 a08 旧安装后，当前子进程在 current witness 创建而身份未落盘时 exit91；外部移除原 current/witness 并重建同目标路径，在确定性身份碰撞控制下，旧恢复错误 completed/verified 并把外部 current 移入 .before。修复后明确报冲突，外部真实 dev/inode/target 与原 journal SHA256 全部不变。

本机 overlay 分配尝试未实际复用原 inode。这里明确使用一致作用于真实外部 inode、硬链接及 rename 后位置的 dev/inode 碰撞映射，不声称实测发生了内核 inode 复用。真实进程死亡和所有实际路径变化仍保留。缺失和同目标替换 witness 的两个负例都经过；已有正常 .after/.witness 中断恢复和外部普通残留保护没有放宽。

旧 completed 由实际 bc6bd55a 包在真实 a08→symlink Host 环境生成：旧版原 UUID 回放成功，87bb 误拒；修复后 recovered=true/verified、原 journal 字节及受管状态不变。另一 logical alias 即使指向同一实际目录仍拒绝。旧 prepared 由实际001c8f10 包生成，包含三条真实 Host 新增动作；显式/隐式原请求均恢复 completed，保留原 request、step 路径和 inode；替换访问 alias 则冲突并保留外部 inode。未通过手改 JSON 制造兼容证据。

- 原安装恢复集合扩展后 **297 passed，0 skipped**；新增兼容文件合计27项，其中本轮新增7项。
- 原47个实际子进程死亡窗口全部在指定断点 exit91，恢复42 completed、5 rolled_back。collector 的 previous 缺失及漏载 pending_captured 两次准备问题如实保留；修正 fixture/collector 后完整重跑，未改生产逻辑或替换失败结果。
- 台账 **9 passed**：替换 ID 后仍70条、遗漏、额外未知 ID 和 Owner 错配均拒绝；FAIL/BLOCKED/NOT_RUN、未完成 CI 和本地延期语义保持。
- 源码 Ruff、workflow YAML、固定历史 fetch 及 git diff whitespace 检查通过。

精确命令、逐项 before/after、原 journal 和原47窗口记录的 SHA256 见 [N2补充证据](N2-review2-evidence.json)。重叠集合不相加。

## 新构建与真实安装核验

干净构建源 `158c8b3e944a11fc04629e935e089bfb5a7f66bd`，tree `01bc716c597523ab8c846e37bcc02acb12f816c5`，source_dirty=false，版本1.0.0rc4，release identity `158c8b3e944a-9ee7ef6359b3`。

wheel SHA256 `9ee7ef6359b3d462cb24d65505b9da598f05c644cd57a56afdfc38b0e1d9a8d0`；sdist SHA256 `4abc6c7025e1702494df7425a323acd77f4338bc84a5c1b12df1d6334a521dbc`。使用既有依赖离线构建、全新 prefix 无索引无依赖下载安装，不激活用户 HOME。新包核验23份 canonical 资源、四 Skill、69 schemas、275成员与90源码模块，见 [安装身份](Installed-resource-identity.json)。旧0c08包和六例浏览器证据保持其原身份，不重标新包。

真实新 wheel 的四个安装文件 **242 passed，0 failed/errors/skips**：compat27、transaction169、four-links23、Host23。候选34个实际加载模块均来自新 prefix 且 hash 匹配 wheel；主进程及110个候选子进程受导入守卫约束，另一个只读资源审计也通过；守卫违规0，源码 conftest 插入被拦截。五个真实旧包子进程及11次 a08 helper 单列为已按固定 git 对象校验的历史 control，不算作候选安装模块。详见 [安装回归](Installed-review2-N2.json)，完整 raw 身份、导入审计和 journal 进入候选包。

额外整组本地打包尝试曾得到249 passed、3 failed、4 setup errors，因 DNS 无法下载 setuptools/候选依赖而停止，exit2；原日志保留，不计整组通过。最终远端完整 CI 单独核验，不以本地聚焦代替。

## 交接边界

唯一70项台账记录本轮受影响项的真实反例及通过证据，汇总仍是带时间的组装快照。新证据提交的完整精确 head CI 在组装时尚未启动，终态由 PR checks 与最终候选 CI-terminal.json 提供，不为回填 CI 另造提交循环。当前 head 外部复审不从测试通过推定。

只读代码复核未发现本修复的实质问题。当前 canonical 方法与 UI 字节未变，N6 真实 Host 输出和 Runtime 采用仍保持原执行身份；不重标为新 wheel 执行。用户本地真实效果/可用性及可信 Host 回执验收继续延期。Darwin 分支未在本环境执行；未合并、发版、部署、改授权或激活真实 HOME。
