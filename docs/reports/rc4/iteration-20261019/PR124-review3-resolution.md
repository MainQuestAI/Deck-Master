# PR124 第三轮指定复审修复

最新[指定聊天复审](https://chatgpt.com/c/6ad57133-6f3c-83ea-879a-72865126ed6c?messageId=25f7d858-fd3a-5752-8dd1-4beb88f4effa)覆盖 `72a1bde8247ac0a1933f5e4b8bbc8496675303e9`，仅余一项 P2：preparing 恢复必须验证全部必需旧对象见证。之前已登记 identity=null witness、真实旧 logical Host 和 AC→Owner 项明确关闭，保持关闭；72a1 的两套成功 CI 保留其历史身份，不抵消新反例。

## 完整集合修复

`Plan.begin()` 已持久化全部冻结 watched 路径及旧身份，但 preparations、inode_anchors、steps 起初均为空。原恢复只遍历已有 preparations，所以空列表或部分登记可以漏过旧对象所需的证明。真实退出后，外部删除并同目标重建未被固定的 inode，在身份复用时会被错误认领。

生产修改仅在 `install.py`：以原有、已验证完整的 frozen watched 为所需集合，对每个既存 regular/symlink 要求有完整 expected 身份匹配且实际仍存活的 witness，再检查全部受管路径、父目录和已登记准备物。列表非空、已登记其他路径或普通 `.after` 都不替代完整覆盖。缺失、未登记、未创建或后来丢失的证明在重建 namespace 前即返回 `installation_recovery_conflict/preparing`；原 journal、外部路径和全部准备物保持原字节及身份。

准备顺序同步前移：先为所有冻结旧对象建立见证，再创建正式替换 `.after`。`activation_transaction.py`、journal 格式、状态机、旧请求语义、CLI 和授权未改。完整集合已被物理固定时，最后一个 witness 即使 identity 仍为 null，仍可证明旧 inode 并正常接续；普通未确认 `.after` 的外部残留继续保留，由原请求使用新 namespace 接续。

## 反例与兼容证据

- 修复前四例失败：真实子进程在 begin 返回或部分登记后 exit91，原 UUID 仍错误 completed/verified。begin 反例把外部 current 移入 `.before`。
- 新增12例覆盖空列表、非空但缺部分、只缺最后路径的登记、最后 intent 已登记但未创建、首个已创建却尚未确认的 witness 仍不足，以及完整集合后分别丢失 current/launcher/Host 见证。负例保全整个实际现场和原 journal；没有手改持久化 JSON 制造覆盖。
- 扩展源码集合 **309 passed，0 failed/errors/skips**；47个实际进程退出窗口全部 exit91，恢复42 completed、5 rolled_back，保留每例退出后与恢复后的完整 journal。
- 实际 bc6 completed、001c prepared 的旧 logical Host 原请求回放、充分证明的正常恢复、普通外部 `.after` 保全与 opt-out 全部保持通过。台账与包边界另16项通过，重叠集合不相加。

本机 overlay 对每个 raw 场景尝试1000次仍未实际复用原 inode；本轮局部复现明确使用确定性 dev/inode 碰撞控制，真实退出和 unlink/recreate 单列，不声称本机实测内核复用。指定复审曾独立实测两次真实复用，保留为复审输入。

旧正例原本停在第一个旧对象 witness，此时完整证明尚未建立。原生产断点保留不动，新负例直接测试该真实窗口；正例改为最后一个旧 Host witness 已创建、身份确认尚未落盘的完整证明边界。第一次修复后的旧 fixture 诊断为31例中5失败，原日志和解释保留，不冒充最终通过或隐藏首个窗口。

独立只读代码复核未发现新增问题，完整集合来自原验证器已核验的 watched 全集，未以 preparations 或 anchors 的非空状态代替。完整身份包含 dev/inode/type 及 target 或 hash/mode；仍存活的同 inode 硬链接固定该旧对象，再逐路径验证受管路径和父目录。未将目录扩大为新的硬链接义务。

## 新构建和实际安装

干净源 `97f41626771357ff51fcfdba7a510db9299233ac`，tree `4f143eb92b9823dfb895538fc5b8c2749f3bddda`，source_dirty=false；版本1.0.0rc4，release identity `97f416267713-3cf22b1ee61c`。

wheel SHA256 `3cf22b1ee61cf5b4e1ec93dcc8506acfea90a18ae7a872bb392abcab94cc4f67`，sdist SHA256 `6356bd9a11df2ac27d60ec3d605b0527df6d5d6e466dafdf3867e3d6e739d67c`。离线构建后安装至全新 prefix，checkout 外以隔离 Python 运行；23 canonical、四 Skills、69 schemas、275 package members、90 source modules 和 I05 全部验证。

真实新 wheel 的五文件安装回归 **254 passed，0 failed/errors/skips**，包括本轮12个完整覆盖例；候选主进程与实际子进程导入均按 wheel hash 核验，固定历史包控制单列，不计作候选安装导入。完整详情见 [N2第三轮证据](N2-review3-evidence.json)、[新安装回归](Installed-review3-N2.json)及[资源身份](Installed-resource-identity.json)。旧158包/72a1 CI 和 N6 保持其原身份。

## 交接边界

唯一70项台账保留真实失败历史，重算汇总并保持本地延期观察不变。报告组装时新最终证据提交的完整 CI 尚未启动，终态由同一 PR checks 与最终候选 `CI-terminal.json` 提供，不为回填 CI 造新提交循环。测试和 CI 不代替指定聊天当前 head 的最终复审。

N6 不重跑；用户本地效果、可用性及可信 Host 回执验收继续延期。17个历史分支只读清理候选保留，当前未合并、未删除分支。最终指定复审通过且收到执行指令后才重新核验合并与清理条件；未发版、部署、改授权或激活真实 HOME。
