# RC3 云端接续与 S12 工程回归

2026-10-17，新云环境 `/workspace/Deck-Master` 已启动。本次接续保留原实验、失败、费用和授权边界；未操作用户 Mac，未合并、发布或激活日常安装。

恢复起点为 main `43d4bc8ccbd1850564e9391c84e98db3c424eae4`，PR120 Draft head `48ee08616ec3ad977302c8c34556f2608cad1130`；原七组 CI #516 成功。S12 独立候选 `7c8edea7538645a89d712b671e37b976daf9e386` 尚未进入 PR120，原 gate #517 与专项 workflow #1 均失败。后者在 job env 引用不可用的 `runner.temp`；前者 unit 在两页 fixture 的单页 Request 范围处被正常拒绝，另有 installed recovery 的浏览器点击超时，二者分别保留，不把该超时归因于 S12。

本地恢复分支 `codex/rc3-cloud-resume-20261017` 基于该独立候选。代码修复提交 `54b974e7551d4eea59586fc1cb9fc8daa701355f`，tree `ef11e3b98cd2db518a77328298fd6f7bace0b4a4`；仅修 S12 companion、其中性 fixture/隔离依赖和专项 workflow。`src/`、四 Skill、原 controller/image_controller/image_event_controller/m02_recorder/S11 及原七组 workflow 相对 PR120 原字节不变。

## 恢复清单

| 项目 | 实际核验与后续边界 |
|---|---|
| 执行归属 | 环境初启仅见服务进程，单 worktree 无其他本地开发/测试；两次远端核对 main/PR120/S12 refs 未变化。原线程 interrupted 为委托消息提供的历史；本工具集无会话历史/状态读取接口，不能证明其他独立云环境没有执行者。后续推送只快进，远端变化即停止核对。 |
| 仓库合同 | 已读 AGENTS、task index/recovery playbook、RC3 README/TASKS/ACCEPTANCE/SOURCE_GUIDE、RC3-00～05、S11/S12 及相关最终 handoff；原 v1.2 ACCEPTANCE 的 L0–L6、F0–F3、E1/E2/E3 和用户/听众边界继续适用。精确文件身份见 `verification.json`。 |
| 原 S12 JSON 合同 | 仓库卡引用的 Root-S12/prospective JSON 没有恢复；卡中声明的 13595B / `d1f401…` 不能当成本次已读原件。独立审查只能给仓库范围的有限结论，不能宣称该缺失合同全部通过。 |
| 易失产物 | `/dev/shm` 为空；`/workspace/shared`、scratch、library-files 无原实验。Library 精确名检索及 10-14 后文件清单未找到对应副本，未下载无关文件。Personal Context 返回不可用。 |
| S14–S19 | 当前远端所有分支和工作区均无对应任务卡；原线程历史不可读，已请求已授权持久化位置。依赖原合同的实施阻塞，未根据摘要补造卡片或扩大功能。 |
| M02 / E1 / E2 / E3 | 原 M02 项目、注册、共同 IG/已花费用、当前 Request、原安装和 S11 独立报告未恢复。旧绝对路径与卡中 hash 仅为查找线索，不认证当前可复用。禁止用新中性 fixture 补原实验，也不重新建立正式 root、凭据、池或模型预算。 |
| 后置人工验收 | Owner、听众、完整试讲/计时、目标 PowerPoint 与适用 professional 证据仍需真实执行，未用模型代答。 |

## S12 修复与实际结果

原 event helper 的加载和 bootstrap 都要求其登记的兄弟文件路径。修复将经过原 hash/Ref 校验的 helper 解析集中到 `original_event`，供原 epoch 读取以及 mark/seal 的 bootstrap 使用。没有改写旧登记、替换全局 B 安装、放宽旧 helper 检查或返回自造 SDK 身份。

中性 fixture 明确请求其实际提交的两页；原 scope guard 仍原样执行。六场景全部把旧 helper 放在独立目录，以覆盖读取、派发和回调路径。隔离子解释器在父进程来自 venv 时显式取得测试依赖目录；只添加普通路径，不运行父目录的 `.pth`，实际每个 Runtime/resource 字节与 own wheel 核对，所有已加载 Runtime 模块必须来自独立前缀。

| 运行 | 结果与保存方式 |
|---|---|
| 本地 r0 | 1 fail / 11 pass；独立前缀无法取得父 venv 的 pytest，六场景未进入。保留首次 stderr。 |
| 本地 r1 | 1 fail / 11 pass；真实异目录 helper 在 `mark` 的 bootstrap 路径拒绝。保留首次错误与部分 SDK 记录。 |
| 本地 r2 | 普通 pytest **12 pass / 0 skip**，37.29s。六场景实际执行、**81 检查 / 524 函数观测**。 |
| 相关回归 | S11、M02 recorder、M02 image profile、image events **84 pass**，34.42s；其中 S11 wrapper 另实际执行其既有 43 个隔离 carrier 用例，不重复加计为外层测试数。首次选择了不存在文件的命令收集错误单列保留。 |
| 静态检查 | 全部 src/tests Ruff 通过；五个新 S12 Python 目标实际 compile 通过；diff whitespace 检查通过。 |

六场景为：原 PNG 两页采用与 settlement lost ACK/query、terminal unknown、malformed first callback、grant committed/lost ACK、grant outcome durable/return interrupted、原 read production 达 13/12 时保留已花事实并阻止采用。每个场景保留独立公开 SDK 轨迹；历史/Host/图片均标合成。真实模型、图像工具和 renderer 调用为零，未新增正式 M02、managed admission 或 S11 完整导出。

原始完整本地证据位于 `/workspace/rc3-recovery-20261017/`，含失败目录、own wheel、实际安装、完整 commands/SDK/errors/原件；未删除或覆盖。仓库只保留精选中性摘要、精确 Refs 和错误，不提交 generated project、IG 私钥、缓存或虚拟环境。`verification.json` 给出原证据 hash、六场景检查和源码身份。

## 验收与未关闭项

独立复审及独立复跑结果见后续 `independent-source-review.md`。新 CI 必须按准确 head 分列，旧 #516 不覆盖 S12；当前运行状态与实际限制记录在 `status.json`。

唯一台账仍是 `../evidence-ledger.json`：37 AC = 2 PASS / 10 BLOCKED / 25 NOT_RUN；13 CQ = 1 PASS / 3 BLOCKED / 9 NOT_RUN，候选身份仍空，release NOT_RUN。本次 L0/L1 工程补修不改变任何 AC/CQ Owner 的签结论，也不能消除原 F0/F1/F2、预算和对照记录。委托中 Q1/Panel0 F2、Q2 缺口和 M02 完整链待恢复原件后逐项核实；未把摘要写成新的通过证据。

正式推进 M02/后续卡仍须恢复原合同、原账本/产物及准确安装；若无法恢复，需要按原权限进行独立登记的新合法运行，并与旧实验分开。当前不具备重启原效果实验所需的可核预算，因此未发起此类模型或图像调用。
