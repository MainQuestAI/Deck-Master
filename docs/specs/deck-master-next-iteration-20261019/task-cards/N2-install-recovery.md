# N2｜安装切换的持久记录与中断恢复

## 0. 任务登记

| 项目 | 约定 |
|---|---|
| 唯一 Owner | N2；本卡所有 `AC-N2-*` 均由 N2 实现、举证和收口 |
| 建议目标版本 | `1.0.0rc4`；当前固定基线仍为 `1.0.0rc3` |
| 固定代码基线 | `MainQuestAI/Deck-Master@a08bc68c1cbbbc806205104c2bb01f3f096305f0` |
| 任务性质 | 安装控制面的恢复完善；本文是待执行 Spec，不代表安装器已修复 |
| 实施前置 | Codex 核对当前 base/head、已安装 release 布局及原测试的实际要求；用户本机安装情况另行核验 |
| 与项目 Runtime 的关系 | 安装记录独立于项目；不增加 Document、Task、调用预算或任何项目业务对象 |

**目标结果：从单 Skill 扩展为四 Skill、回退到较少 Skill，以及确实需要新增/移除 Host 链接的切换，在用户中断或进程终止后能够识别已完成步骤并安全完成或补偿；无法证明路径仍归本事务所有时保留证据并明确报冲突。**

## 1. 范围

### 1.1 本卡目标

1. 把现有进程内补偿升级为有持久阶段记录的安装事务，复用既有 `install.lock`、路径预检查、release 验证及原子文件写工具。
2. 可捕获的 `KeyboardInterrupt` 执行补偿；无法捕获的进程终止，由下一次同请求恢复。
3. 添加可选 `--transaction-id <UUIDv4>`，支持精确恢复 `activate` 或 `rollback`，尤其是结果已完成但回包丢失的 rollback。
4. 保留旧单 Skill release、四 Skill release、旧 companion 迁移及 `--no-host-registration` 的现有边界。
5. 保留外部路径变化的实际证据，恢复时不把外部新文件、目录或链接当成事务产物处理。

### 1.2 非目标

- 不重写候选安装、wheel 下载、venv 建立和整个发布系统；failed candidate 是否允许同 release ID 重装不在本卡处理。
- 不改变四个公开 Skill 的职责、内容或方法资源来源。
- 不增加数据库、后台常驻服务、项目运行审批或真实模型调用。
- 不修改第三方 Skill、Host 配置、其他 Host 的注册，也不根据失败自动切换另一套安装。
- 不保证历史版本 writer 能理解新项目，也不降低任何项目 writer floor。
- 不把“已有四条完整链接、只切换 current”的普通升级笼统标成缺陷；本卡复现与重点验证是真实链接增删窗口。
- 不主动执行用户真实 HOME 的安装、迁移或清理。用户本地安装目录、实际已加载 Skill、当前运行 release 等均**需要 Codex 核验**。

## 2. 现状证据与缺陷基线

| 已核验事实 | 固定源码证据 | 本卡承接 |
|---|---|---|
| 安装按 prefix 使用文件锁 | [install.py L23-L28](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L23-L28) | 复用，不新增第二套安装服务 |
| 当前补偿事务只在进程内保存 action/lambda，无持久记录 | [install.py L30-L86](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L30-L86) | 不能在进程死亡后知道已完成到哪一步 |
| `_compensated()` 仅捕获 Exception | [install.py L72-L86](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L72-L86) | Ctrl-C 的 KeyboardInterrupt 未进入原补偿分支 |
| current 先切换，随后同步公开 Host 链接 | [install.py L493-L529](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L493-L529) | 链接扩展中断时可留下半完成入口集合 |
| 现有 helper 已有 path/inode 与父目录身份检查 | [install.py L34-L69](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L34-L69)、[install.py L392-L447](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py#L392-L447) | 应扩展现有所有权判断，不能改成只比较目标字符串 |
| 原安装测试覆盖四条链接冲突及 OSError 补偿 | [test_rc3_install_four_links.py L50-L121](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/tests/rebuild/test_rc3_install_four_links.py#L50-L121) | 复用，新增用户中断与进程死亡断点 |
| 安装方法要求四入口一起注册、出错补偿并明确不改第三方路径 | [installation.md L23-L46](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/skills/deck-master/references/installation.md#L23-L46) | 修复实现与方法承诺之间的恢复差异 |

本轮已在与现有四链接测试同性质的合成 release fixture 中复现：旧 release 仅有 `deck-master`，升级至四 Skill release，在创建 `deck-design` 时注入 `KeyboardInterrupt`；结果 `current=releases/new`，仅 master/content 已注册，design/review 缺失。所有路径在 `/tmp`，未进行真实 wheel 安装或实际 HOME 迁移。

这证明特定中断窗口存在，不证明用户本机正处于该状态。用户环境的真实安装事实、路径及修复效果均**需要 Codex 核验**。

## 3. 外部合同先冻结

### 3.1 命令与请求身份

保留现有命令，添加可选参数：

```bash
deck-master install activate --prefix <prefix> --release-id <id> \
  [--transaction-id <UUIDv4>] [--no-host-registration]

deck-master install rollback --prefix <prefix> \
  [--transaction-id <UUIDv4>] [--no-host-registration]
```

- 不带 transaction ID 的现有调用继续工作；首次事务由安装器生成 UUIDv4，并在结果中返回。
- 指定 ID 时，ID 在该 prefix 的安装记录中唯一。相同 ID、相同请求恢复原事务；相同 ID、不同目标、动作、Host root 或注册选项返回冲突。
- rollback 在创建事务时冻结要回退的目标 release、当时 current/previous 和 Host 注册范围。恢复不能再次读取后来已经变化的 previous 并把它当成原目标。
- **未完成事务：** 同 prefix、同请求再次调用时，自动恢复已有事务，不生成另一个安装事务。
- **已完成的 activate：** 同一目标仍可返回原有 `already_active` 语义；带 ID 时返回该事务原结果。
- **已完成的 rollback：** 带原 ID 的重试只返回原结果；不带 ID 再次调用保留原有“依据现在 previous 再切回”的行为。这两个动作不能自动猜测为同一个请求。
- 程序需要在 rollback 回包丢失后精确重放，应在首次调用前生成并保存 transaction ID；不强迫普通交互用户增加确认步骤。

### 3.2 请求指纹

新事务至少固定：

```text
verb                       activate | rollback
prefix                     规范化绝对prefix
target_release_id          首次计划确定的目标，rollback同样固定
target_release_identity    release.json及已验证方法资源清单的SHA256
register_host              true | false
host_root                  首次解析的实际Host skill root；opt-out为null
transaction_id             UUIDv4
```

当前/previous 的旧目标、受管路径前态、拟执行 action 集合属于**冻结的计划**，不是重试时重新生成的指纹。相同请求不因事务自己已经改变 current/previous 而变成冲突。相对 prefix 只在入口解析一次；恢复记录中的路径不能被新的环境变量悄悄替换。

### 3.3 状态与结果

持久状态最少为：

| 状态 | 含义与后续 |
|---|---|
| `prepared` | 前置检查和计划已持久化，尚未执行正式切换 |
| `applying` | 正在按冻结步骤切换；每步有可检查的状态 |
| `compensating` | 正按反序恢复旧状态；步骤自身同样可恢复 |
| `completed` | 新目标、launcher、相关 Host 链接全部验证完成；原结果已持久化 |
| `rolled_back` | 原请求未生效，且相关受管路径已验证回到旧状态 |
| `recovery_conflict` | 存在外部修改、资源变化或无法证明所有权；保留证据，不继续覆盖 |

`rolled_back` 的同 ID 请求返回原中断/失败及补偿结果；若用户要再次执行原切换，应发起新 ID/不带 ID 的新请求。处于 `applying/compensating` 的未终结记录，原请求继续原恢复方向。不得自动把恢复失败说成已经回退。

原成功字段 `status/release_id/previous/cli_active/host_skill/skill_links` 保留，追加 `transaction_id/transaction_state/recovered`。报错至少包含 transaction ID、当前阶段、能否证明旧/新状态和明确下一动作，不把路径冲突显示成“安装成功”。

精确重放返回的是**原事务当时的完成结果**，不是当前安装健康报告。如果后来另一个事务切换了 current，保留原结果并另带 `observed_current_release_id` 与 `current_install_state` 的独立只读观测；观测失败明确 unknown，不把原 `cli_active/host_skill` 解释为当前仍成立，不重新切回原 release。

## 4. 持久记录方案

### 4.1 保存位置与归属

在既有安装 prefix 内保存安装控制信息，建议布局如下，实施时统一到一个内部路径 helper：

```text
<prefix>/.deck-master/
  install.lock
  activation-pending.json
  transactions/activation/<transaction-id>.json
  transactions/activation/<transaction-id>.work/
```

- transaction JSON 使用 `activation_transaction.v1`，是本机安装记录，不是项目 schema；无需新增项目 writer 名称。
- `activation-pending.json` 是指向一个未终结事务的可恢复入口，不是第二份计划或业务真相。
- JSON 及 pending 更新复用现有 `_atomic_write_bytes()` 的文件 fsync、原子 rename、父目录 fsync。新目录和准备文件的持久性必须在故障注入中验证。
- 记录只包含声明式 action 与身份信息，不能保存并重放 shell 命令、Python lambda、pickle 或任意代码。
- 未知记录版本、损坏 JSON、与 prefix/transaction ID 不符的记录必须拒绝执行，保留原文件。
- 终结记录保留。不要在本卡增加通用清理或历史压缩；legacy companion 目录仍按既有策略保留。

### 4.2 每个动作的记录

每个受管操作至少记录：

| 字段 | 要求 |
|---|---|
| `step_id/kind` | 稳定顺序和有限动作类型：父目录准备、launcher、受管link替换/创建/移除、legacy companion移动 |
| `path` 与 `parent_identity` | 冻结的受管路径及父目录dev/inode身份，恢复时重新检查 |
| `before` | absent / symlink原目标 / 受管launcher hash与mode / 已验证legacy目录身份 |
| `prepared` | 准备文件或链接的位置、dev/inode、hash/target，以及独立备份位置 |
| `expected_after` | 计划预期结果；不能仅凭“此位置现在是任意symlink”判定已完成 |
| `step_state` | planned / ready / applied / restored；状态与实际路径交叉核验 |
| `observed` | 最近一次实际核验与冲突信息，供解释恢复结果 |

**核心约束：必须能处理“文件系统动作已经完成，但 step_state 还没写回”的死亡窗口。** 仅在每次动作后 append 一条日志并不能满足本卡。

### 4.3 复用原 helper 的方式

- `_replace_link()`：先在同文件系统准备具名链接，记录其 lstat 身份并刷盘，再执行正式 rename。恢复可通过准备项身份、目标路径身份和旧备份判断动作是否已完成，不能只靠链接字符串猜测。
- `_unlink()`：事务内需要移除的受管链接，先移动到事务指定的备份位置并保留原 inode/target，再记录完成；不要直接删除唯一旧状态。终结后是否清理备份不属于完成前置。
- `_move()`：冻结且验证 source/destination，备份路径在 plan 阶段唯一分配；移动后未写回日志时，目标位置的原 inode/manifest 可证明执行状态。
- launcher：完整内容写入准备文件、fsync 后发布，记录原模式和身份，避免将半写入 launcher 当成可运行入口。
- `_mkdir()`：即时异常仍使用现有反向补偿。进程死亡后无法证明是本事务创建的父目录不得删除；保留未使用空父目录可以作为清理说明，不能以强行删除来追求目录树完全相同。
- `_Undo` 可以保留为当前进程快速补偿器，但其恢复行为必须对应同一持久 action。不得让进程内补偿与进程外恢复拥有不同的路径范围。

准备项和备份必须与被操作路径处于同一文件系统。prefix 的 `.work` 不能被假定与 Host root 同盘；Host 链接所需准备/备份使用其受管父目录内、由事务 UUID 唯一命名的位置，并把身份和路径写入同一安装记录。每个涉及的父目录分别 fsync；不以跨文件系统复制加删除冒充可恢复的原子 rename。

实现者可以使用少量内部类型和 helper；不得复制一份完整 install.py 作为新安装器。

## 5. 执行与恢复算法

### 5.1 首次执行

1. 解析命令与可选 ID，取得既有 prefix `install.lock`。
2. 读取 pending 记录。如果存在未终结事务，先按第 5.2 节处理，不能直接开始第二个切换。
3. 调用既有 `_checked_release()`、activation/Host preflight 和 legacy dry run，形成精确 action 列表；四条公开路径都要预检查。若 `register_host=false`，action 中不能包含任何 Host 路径，也不得做 Host 清理。
4. 需要修改同一个 Host root 的受支持并发安装者必须共享排他锁。优先复用现有安全 `locked_file()`，在 Host root 下使用一个明确受管锁文件；固定“prefix lock → Host registration lock”的顺序。取得 Host 锁后重新验证计划相关路径、迁移前态及目标资源，再冻结最终计划；不能直接执行锁前观察形成的过期计划。opt-out 完全跳过 Host 锁和 Host 写入。非协作外部修改仍由每步身份校验识别。
5. 将 plan、原路径身份、目标资源指纹及原请求持久化为 `prepared`，再更新 pending 入口。任何正式切换必须发生在完整计划可恢复之后。
6. 将状态改为 `applying`，执行准备/正式应用步骤。每步应用前重核期望前态；动作后核验实际结果并记录 step_state。
7. 完成 current/previous、launcher 与应注册/退役的 Host 链接整体核验；目标 release 的方法与安装资源仍通过原验证。
8. 把完整原成功结果写入 `completed` 记录并刷盘，再清除 pending 入口。清除 pending 失败不否定已完成事务，下一次读取应识别终结记录，不再次执行。

### 5.2 再次调用与进程死亡恢复

恢复先确定记录，再检查实际文件状态，不能先重新运行 `_activate_locked()`：

1. 相同 ID 存在时按其记录处理；无 ID 但存在 pending 时，仅当 verb、目标及注册范围与冻结请求一致才自动接续。若进程在完整 prepared 落盘后、pending 写入前死亡，持有 prefix 锁时检查本 prefix 的有限 activation 记录；仅一个可验证未终结计划且请求匹配时补建 pending 接续。多项冲突或记录损坏时保留证据并拒绝猜测，不直接开新事务。已 completed/rolled_back 记录不能据此被恢复为未完成事务。
2. `prepared/applying`：逐项比对 before、prepared、expected_after 及父目录身份。已证明完成的步骤不重复；明确未完成的步骤执行一次；动作已完成而日志未写回的步骤先补记状态。
3. `compensating`：继续反向恢复，不转成重新安装。恢复完成后写 `rolled_back`。
4. `completed`：带相同 ID 直接返回原结果，包含 `recovered=true`；不修改 previous、不重新注册、不创建新记录。若当前已由后续事务切换，另按第 3.3 节声明当前独立观测，不能把历史成功伪装成当前安装事实。
5. `rolled_back`：带原 ID 返回原失败及已回退事实，不悄悄重新执行。新操作使用新身份。
6. 路径不符合任何可证明状态、Host root 变化、目标资源指纹变化或出现未知路径所有权，写 `recovery_conflict`；尽可能完成仍能证明安全的补偿，但不能覆盖外部修改。
7. 同 prefix 的不同新请求遇到未终结事务时返回 `installation_transaction_pending` 和原 transaction ID，指向使用原请求恢复。无须增加审批；不能自动取消前一事务后切到新目标。

### 5.3 KeyboardInterrupt 与异常补偿

- 捕获 `KeyboardInterrupt` 后先将事务持久化为 `compensating`，再反序恢复所有已应用且所有权仍可验证的动作。恢复后核验完整旧受管状态并写 `rolled_back`。
- CLI 可返回 exit 130 与结构化 `installation_interrupted`；必须明确 `transaction_state`。不能吞掉中断后继续安装，也不能只报“失败”而缺少是否已回退的事实。
- 普通异常沿相同补偿器处理，保留原错误类型/原因，并输出可恢复 transaction ID。
- 补偿自身再次中断或进程被终止，记录保留在 `compensating`，下一次原请求继续补偿。
- `SIGKILL`、`os._exit()` 等不能靠捕获异常处理；正确性来自持久准备项、身份检查和第 5.2 节恢复。**仅把 except Exception 改为 except BaseException 不构成本卡完成。**

## 6. 所有权、兼容与错误语义

### 6.1 所有权规则

1. 保留既有第三方链接/文件/目录拒绝逻辑。安装计划不能接受任意用户传入路径作为可操作 step。
2. 每个动作与补偿都验证父目录身份、原路径身份和准备项身份。备份恢复遇到新占用不能覆盖；保留备份和冲突位置。
3. 已识别的外部修改绝不覆盖。对无法证明由本事务创建的文件、链接或目录，进入 conflict；不要把内容相同视为路径归属相同。
4. 冲突结果提供受影响的受管路径、预期/观测类型、事务阶段和备份位置；不得报告“原安装完整恢复”。原有可用入口能否运行由实际检查决定，不能从新旧 release 名称推断。
5. `--no-host-registration` 在首次执行、补偿和恢复三条路径都不触碰 Host 目录、锁文件、Skill 链接、配置或legacy Host清理。

### 6.2 错误表

| 错误码 | 建议退出码 | 状态与动作 |
|---|---:|---|
| `invalid_transaction_id` | 2 | ID不是规范UUIDv4；无切换，纠正参数 |
| `installation_transaction_conflict` | 5 | 同ID绑定不同请求；保留原记录，使用原请求或新ID |
| `installation_transaction_pending` | 5 | 同prefix存在另一未终结请求；先恢复原事务 |
| `installation_interrupted` | 130 | 用户中断；明确 rolled_back 或仍需恢复，不猜成功 |
| `installation_recovery_conflict` | 5 | 外部路径/目标资源变化或所有权不明；保留证据及备份，明确哪个事实需核验 |
| `installation_recovery_unavailable` | 4 | 持久记录或文件状态无法读取/验证；原请求保持unknown，不覆盖或重建记录 |
| 既有 `host_skill_conflict` 等 | 保留 | 前置路径冲突不切换current；现有兼容行为继续适用 |

### 6.3 旧状态兼容

- 无任何 transaction 记录的既有安装可以直接启动新事务；不能因没有历史事务就声称旧安装不合格。
- 旧的单 Skill 与 skillless release 仍按现有 `_checked_release()` 兼容规则处理；本卡不借恢复名义要求重建全部旧 release manifest。
- 旧 companion 迁移继续只处理已验证 companion 清单与精确受管链接；冻结原迁移计划并纳入同一事务，不增加扫描范围。
- 现有四链接已经齐备时，计划可以没有 Host 增删动作；同目标 activate 保持无额外变更。
- 新的安装记录不改变项目 writer floor。rollback 后旧 Runtime 是否能写某个项目仍由项目已有边界拒绝，不能通过恢复来降级。

## 7. 模块落点与开发顺序

| 顺序 | 模块 | 具体工作 |
|---|---|---|
| 1 | `install.py` 与少量同包内部 helper | 有限动作模型、事务读写、身份签名和固定计划；复用原锁与原子写 |
| 2 | `install.py` 的 `_replace_link/_unlink/_move/_mkdir` 和 launcher准备 | 为每个实际增删动作增加可恢复准备项与step判定，保持原路径范围 |
| 3 | `activate/rollback/_compensated` | 统一正常应用、即时补偿、进程后恢复；冻结rollback目标 |
| 4 | `cli.py`、必要的 `errors.py` | 可选transaction-id、结构化阶段结果、exit130与冲突错误 |
| 5 | 安装方法与恢复手册 | 写清带/不带ID的rollback语义、pending恢复和冲突证据检查 |

不要把实现切成需要长时间支持两套安装器的迁移。先提交内部恢复原语和定向fixture，再接入activate/rollback及CLI，最后完成进程死亡矩阵。

## 8. 验收标准（均为待执行）

每项唯一 Owner 均为 **N2**。下列测试使用独立临时 prefix 和合成 Host root，不使用真实 HOME；故障点必须覆盖“动作完成而日志尚未写回”。

| AC ID | Given | When | Then |
|---|---|---|---|
| AC-N2-01 | 无事务历史的旧单Skill安装，以及完整四Skill安装 | 正常activate四Skill目标或同目标重复activate | 原CLI成功字段兼容；四入口/launcher/current一致；同目标不重复新增操作；目标资源验证不减弱 |
| AC-N2-02 | 单Skill→四Skill需要逐条新增链接 | 在每条实际链接增删前后、current切换前后注入KeyboardInterrupt | 即时补偿可验证时恢复完整旧受管状态并exit130；每次记录明确rolled_back；不留下被声明成功的缺链状态 |
| AC-N2-03 | 同一冻结事务已有准备项和一部分动作完成 | 子进程在准备完成、动作完成未记日志、pointer切换后、最终结果落盘前等位置终止 | 原请求下次恢复同一事务；已完成动作不重复；最终完整新状态或原恢复方向的完整旧状态 |
| AC-N2-04 | 使用transaction-id的activate/rollback已完成但回包丢失；另有一例其后又完成了不同切换 | 原ID和原请求重放 | 返回原事务结果与recovered标记；current/previous/Host链接不变化、不再切回；后续切换存在时独立报告当前观测，不把历史成功当作当前健康 |
| AC-N2-05 | 一次不带ID的rollback已完成，另有一次未完成的rollback | 分别再次运行不带ID的同命令 | 已完成者按旧语义依据现在previous新切回；未完成者冻结原目标继续原事务；文档与测试明确两者区别 |
| AC-N2-06 | 四Skill→单Skill/skillless回退需要移除受管链接 | 在移除及其补偿前后分别中断或终止 | 旧链接备份可验证且不丢；恢复按原目标收敛；不会把已删除链接误认为无需记录的成功 |
| AC-N2-07 | 原事务应用/补偿过程中，外部替换某个受管链接、launcher或父目录 | 恢复原事务 | 返回recovery_conflict，保留外部内容与可恢复备份；只补偿所有权仍可证明的步骤；不虚报完整回退 |
| AC-N2-08 | 同transaction-id不同目标/verb/Host root/注册选项，或两个prefix竞争同Host root | 并发执行 | 请求身份冲突拒绝；受支持安装者锁顺序一致；只能一方修改某个受管集合，另一方不覆盖外来链接；无死锁 |
| AC-N2-09 | `--no-host-registration` 与可迁移旧companion布局 | 正常、KeyboardInterrupt及进程后恢复各执行一次 | Host目录、锁、全部链接与配置字节/身份不变化；CLI迁移仅按原合同；带注册时只处理原精确清单 |
| AC-N2-10 | 补偿已开始，随后补偿再次中断或事务记录/pending入口写入失败 | 原请求继续 | 不重启正向安装；正确区分completed、rolled_back、unknown；已completed但pending未清可被识别而不再次执行 |
| AC-N2-11 | 事务JSON损坏/未知版本、目标release资源变化或record被复制到另一prefix | 尝试恢复 | 不解释为命令、不使用另一环境的路径、不删除原记录；结构化拒绝并保留证据 |
| AC-N2-12 | 既有路径冲突、旧release、四链接正常补偿fixture与安装验证门禁 | 运行本卡定向回归并审查结果 | 原第三方保护和资源检查继续成立；AC证据记录实际SHA/命令/断点/状态；真实HOME迁移明确未被合成测试代替 |

## 9. 测试复用与证据标准

优先复用：

- `tests/rebuild/test_rc3_install_four_links.py`：逐链接冲突、升级、rollback、opt-out及原OSError补偿。
- `tests/rebuild/test_install_host_skill.py`：旧companion、第三方路径、legacy release、受管根与回滚。
- `tests/rebuild/test_install.py`：现有候选资源一致性与安装验证，选择相关用例回归；本卡不重新定义全部打包门禁。
- 新增聚焦文件建议为 `tests/rebuild/test_install_transaction_recovery.py`，承载有持久记录的进程死亡与请求身份矩阵。

测试实现要求：

1. 主断言比较受管路径实际lstat/目标/内容/模式、current/previous、事务阶段及最终结果，不以异常被捕获或某函数运行一次作为充分证据。
2. KeyboardInterrupt 用正常异常注入；进程死亡用独立子进程在明确断点 `os._exit()` 或定向终止该子进程，不能杀共享测试服务或实际Host。
3. 每个子进程使用明确合成 prefix 和 Host root，复用当前fixture对 `_codex_skill_root()` 的隔离方式；不需要读取真实HOME内容。
4. 覆盖正常异常、未记后置日志的死亡窗口和补偿中再次死亡；不能全部用OSError替代进程终止。
5. 目标wheel/完整renderer链的真实执行证据沿既有发布门禁复用，合成activation测试不得标成真实用户安装验收。

当前执行环境、适用测试名、原测试能否通过均**需要 Codex 核验**。本卡不提前填写通过数，也不把审查时74项定向测试通过移作本次修复证据。

## 10. 交付物与完成判定

1. 限定安装模块与CLI改动，可选transaction-id的使用合同。
2. `activation_transaction.v1` 的本机记录结构、有限动作定义、状态迁移和未知版本处理说明；保存在开发文档，不加入项目业务schema。
3. 定向测试与 `install-recovery-evidence.json`：执行SHA、每个断点、原请求ID、旧/新目标、实际路径结果、恢复方向及未验证事项。
4. 更新 `skills/deck-master/references/installation.md`、`docs/agent-recovery-playbook.md`：原请求恢复、精确rollback重放、冲突备份与opt-out边界。
5. PR说明清楚回答：在哪类链接增删下原先会半完成、本PR如何从持久事实恢复、测试覆盖了哪些中断位置。

完成以全部 `AC-N2-*` 和必要原回归满足为准。新事务文件存在、捕获了BaseException或合成fixture正常运行均不能单独宣告完成。真实安装、真实已加载Skill、本机HOME迁移、现有客户项目在回退后的可继续性均**需要 Codex 核验**，也不由本卡自动授权执行。
