# Deck Master 生成工作台 v3：独立 Review 与执行接管

交接日期：2026-09-26。用户最新指令：开一个新的线程，基于 A 线或最新 main，对这一轮 12 个开发包做独立 Review，随后由该线程负责开发包执行。

## 目标与当前授权

你是新开的开发负责人线程。先独立核对 12 个包与真实后端、用户调整后的前端设计是否一致，记录问题及修订执行顺序；随后依据评审结果按一张卡一次的方式推进实施。已有实现不重做，设计评审结论不当作生产功能验收。遇到真正影响产品范围或外部验证的阻碍，报告具体缺口；不因常规实现取舍重复请求开工许可。

用户已认可五个工作面的整体结构与功能，并在 OpenDesign 单独调整了前端。保留用户当前视觉修改，不把旧本地原型重新写回 OpenDesign。本轮以工程可实施性为重点，不重新打开整套产品定位讨论。

## 基线与隔离

- 主项目：/Users/dingcheng/Coding-Project/02-key-project/Deck-Master。
- 主项目当前仍是 A 线 codex/flow-quality@3e1c70617701ceb01627e507de1592246ec47927，存在未提交的本轮后端核验报告 docs/reports/。保留这些文件，不在原 A 线执行新包。
- 上轮已在线核验远端 main：d1c7c4600cb0fc781070116ed8cc8a1ff6b8b7ca（Merge pull request #39 from MainQuestAI/codex/flow-quality）。本地有该对象，本轮重新确认其提交信息。
- A 线 3e1c706 与 main d1c7c460 的完整 tree 相同：88dd584bc7101496413af7a5420cab42c8ebd9eb。后端报告因此适用于该 main。
- 本次交接重新访问 GitHub 时，git ls-remote 超时、gh API EOF、GitHub connector 连接失败；无法证明 d1c7c460 仍是此刻远端最新。不把旧的本地 main/origin/main 引用当最新。
- 新线程启动后先 list_artifacts，复用本线程合适的活动 worktree；若没有，使用 Codex create_worktree 建立本线程专属 checkout（建议名 workbench-implementation），显式 ref=d1c7c4600cb0fc781070116ed8cc8a1ff6b8b7ca，随后所有 shell 命令显式使用返回目录。工具 pending 时等待完成，避免手工创建重复 checkout。
- 网络恢复后核对当前远端 main。若更新，先在新 checkout 校准主线，并核对新增变化是否覆盖报告中的缺口；不要切换、reset 或修改原 A/B/设计工作树。
- 开发分支采用 codex/ 前缀。不要复用旧 B 线 cbeebb6 或设计文档分支作为产品代码基线。

## 必读入口（均为现存本地交付）

1. 新 checkout 的 AGENTS.md → docs/agent-task-index.md → docs/agent-recovery-playbook.md；活动合同只用 src/deck_master/resources/contracts/。视觉实现前读 DESIGN.md。
2. 设计总入口：[README](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/README.md)。设计提交 dfeecd9f7a44bc9b2f99fe274c63281cea80c7e4，工作树干净；这是设计交付，不是产品代码基线。
3. [12 包索引](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/packages/README.md)，逐张读取 W01.md–W12.md；[87 条验收](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/ACCEPTANCE.md)。
4. [完整方案](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/PLAN.md)、[交互规范](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/UI-SPEC.md)、[工程规范](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/ENGINEERING-SPEC.md)、[开发接入](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/DX-SPEC.md)。
5. [旧场景继承](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/LEGACY-COVERAGE.md)、[已有 AutoPlan 与四轮 Review](/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/reviews/README.md)。本轮独立评审不能仅转述这些结论。
6. 最新后端实测：[建议报告](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/reports/webui-backend-feasibility-20260926/README.md)、[38 项能力矩阵](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/reports/webui-backend-feasibility-20260926/CAPABILITY-MATRIX.md)、[可复现探测](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/reports/webui-backend-feasibility-20260926/probe_backend.py)、[证据说明](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/reports/webui-backend-feasibility-20260926/evidence/README.md)。报告目前只在原工作树，Git 新 worktree 不会自动带过去；请按这些绝对路径先读取，执行接管时保留引用或复制到自己的交付目录，不删除原件。

## 设计真相与需要纠正的旧状态

- OpenDesign 项目标识：deck-master-generation-workbench-v3-20260926；主入口 index.html，补充状态 states.html。使用 OpenDesign MCP get_artifact(include=all) 只读提取当前内容，实施时以前端最新版本为依据。
- 预览曾为 http://127.0.0.1:52366/api/projects/deck-master-generation-workbench-v3-20260926/raw/index.html 。端口属于当时 daemon，不保证一直可用。本次 get_project 返回 Transport closed；不因此启动重新生成或用旧文件覆盖用户修改。
- 设计目录 prototype/ 是修改前的可运行合成原型与历史 QA 证据；后端报告 evidence/opendesign-read-snapshot.json 保存上轮读取用户调整版六个活动文件的 hash。当 MCP 暂不可用，可先审查功能和后端，并把当前视觉源未重新读取明确列出。
- PLAN / CODE-BASELINE 中 cad56e0、尚未获设计确认、A 线待合并等旧描述不能覆盖本交接的当前事实。结构已获用户认可，A 线 PR39 已在上述 main 合并。更新这些状态时只改接管后的文档副本，不改用户设计。
- 架构仍是 Python 本地服务 + 原生 JavaScript ES Modules；/v2/ 与旧入口并存。生成仍通过既有 Host/CLI，共用项目真相。

## 本次独立 Review 重点

后端报告已详述触发方式、代码位置和 P01–P16（含 P09a）证据。本轮请验证差距归属、卡片是否覆盖、前置是否足够，而非直接按原型按钮接旧 API。

1. W01/W05：核心能读历史，HTTP 却忽略 revision，包括不存在的版本也返回当前。固定版本比较必须先补通。
2. W02：prepared prompt 已保存，应复用；实际提交和输出绑定并非必有。真实请求冻结、参考图传递和可信来源等级需真实 Host 证明。
3. W06：旧 feedback 会丢选区/客户端操作 ID，不支持整批事务。同页多意见、原子性、操作重试、未知保存恢复需持久事实。
4. W06/W10：Host 结果写当前成功但回执写失败后，原操作重放会冲突；这是已复现的恢复缺口。Task.result_refs 和接手/执行事实投影也不完整。
5. W07/W08：现有 accept 直接更新当前，trial candidate/adopt 是新增语义。先完成真实单页试作，再扩跨页风格；不把回滚当前当成候选。
6. W09：inputs_update/content_update 已在 main；直接 reorder/remove 服务、内容计划和合并拆分来源仍需补，不重复 A 线能力。
7. W11：现有 review 仍要求当前 PPT，且包含工程对象；engineering/指定版本/导出下载未有。新三用途导出需按规格重新验收。
8. W03/W04/W10/W12：独立入口、summary、草稿跨刷新保护、30 分钟核实恢复仍需接入；画廊不要擅自改变现有逐页原图→SVG→复核的调度。

报告建议序列为 W01 → W02 → W03 → W04 → W05 → W06 → W07 → W08 → W09 → W10 → W11 → W12，W10 可在 W07 后优先。与原开发包索引不同之处是 W02 提前。请独立验证依赖后同步 PLAN、包索引和验收归属，不只在 Review 中另写一套顺序。

## 接管完成与逐包执行

先提交一份独立评审：按严重性列出有证据的问题、涉及的包/AC、建议修订；核对 12 包与 87 条 AC 的唯一归属、依赖无环、已有能力复用与真实验证前置。给出修订执行顺序、首张可执行卡、尚未解决的具体阻碍。保存到自己的 checkout，并建立简洁执行索引。

Review 收口后按修订后的卡片继续推进。共享核心/schema/CLI/Host 改动与前端接线分开，核心先进入 main 后再接前端；一次一张卡。每卡记录实际 commit、代码/接口范围、兼容说明、验证命令和证据、剩余事项。保持原图不可变、页面身份、固定比较、幂等、取消晚到保护和质量门禁。默认切换、真实 HOME 迁移与发布沿用既有单独授权，交接本身不等于发布。

现有后端验证为 214 个测试通过 + 17 项核心/HTTP 观察；含合成项目和故障注入，不含真实模型、真实 Host、浏览器新版验收或正常安装。12 包生产 AC 尚未由这些证据关闭。不要为复述已有绿色结果重跑全部测试；针对新结论、变化和高风险差距选验证。

## Suggested skills

- plan-eng-review：独立核对依赖、契约、事务、失败恢复、测试覆盖与实施顺序。
- plan-devex-review：核对 CLI/HTTP/Host 的实际可操作性和可复现样例。
- review：有具体实现 diff 后做缺陷优先代码评审。
- qa-only / browse：有真实本地服务后验证交互，不拿合成原型代签后端。

按实际任务选择，不机械重跑整套 AutoPlan 或重新生成视觉稿。遵循当前 Skill 与 AGENTS 的适用边界。
