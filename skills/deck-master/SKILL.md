---
name: deck-master
description: 从任务、材料或已有项目协调内容、设计、制作和审查，按有效范围连续推进及恢复；需要策划、写稿、样页或只读审查时分配到对应职责。
---

# Deck Master

## Use when

新任务、完整制作、续作、局部修改或职责未明；需协调 Content、Design、Review 与授权内 Producer。

## Do not use when

已明确只策划/写稿/口播、只设计或只读审查时，直接使用对应 Skill 的独立范围。原始指令同时肯定要求写稿、设计、审查等多个职责时，由 Master 协调；不要因其中出现“设计/审核”就改投单一职责，也不要把否定动作或业务主题中的审核流程当作审查请求。点名职责优先，超出该职责的工作通过明确交接处理。已有合法决定与授权继续有效，不为了换 Skill 重新询问。

## 方法与允许产物

涉及内容的新任务，按 method-selection 识别交流任务与内容缺口，将拟采用的方法/案例 ID 随现有派发输入交给负责角色，由 Runtime 验证并冻结。不另建方法任务、分析审批或第二份内容真源；不默认读取十卡六例。新策划通过 `create --business-framing` 使用新版起步包；无 Task 时可用 `methods --business-framing --phase framing|argument --read` 读取实际组合，后续及审查在冻结前按需选卡。旧任务只读原 manifest，已确认方向和范围继续有效。

1. 读原始指令、来源、当前 request/eligibility/completion，区分决定、授权与具体文件认可。省略格式的新建默认 workbench.v3/rc3；不选择旧协议规避资格。
2. 对新任务形成任务理解、拟议范围、关键未知和下一责任；通过同一 Runtime create/start_request，保存真实 instruction evidence。模型建议不得记成用户已接受决定。
3. 按请求的职责调用 Content/Design/Review；传同一项目、固定版本与 scope，不复制状态。完整制作只有在资格允许时才交 Producer 继续蓝图→SVG→真实 PPT→逐页/最终检查。
4. 每次接纳后读取 completion/continue；用户只要内容或样页时到本次完成即返回，不隐式整套制作。已有非空稿可打开实际 Studio 供查看，打开不代表授权生产。
5. 费用按实际 begin/settle 记录；取消、暂停、撤回或 basis 过期后仍结算真实已发调用，拒绝稿件采用。不重复执行已完成调用。
6. 两用途版本按同一 start_request 的 variant_transition 选定源 revision/export；先固定第一份，再生成第二份独立 Plan/Page/output。编辑旧版本明确源与页/字段，不能用 restore 全项目模拟窄改。

允许产物：任务理解、范围与影响说明、待决定项、下一责任及授权范围内实际作品；所有持久化写入经 Runtime service/CAS。

## 退出条件与下一责任

本次 completion 已完成时返回其 outputs/checks；needs_reviewer/awaiting_decision 返回可读稿、具体缺口及下一责任。full_deck 交付按准备附上的实际文件执行 eligibility/handoff-check，工程与专业/人类/桌面状态分列。不得把旧 Desktop 记录称为本轮实际桌面已验。

完整制作或局改在内容前审返回 needs_reviewer 时，正常安装可用同一发布版执行
`review native --project <dir>`（已有待执行前审 Task 可加 `--task-id`）。此操作通过本机已登录 ChatGPT 的 Codex 原生客户端创建新的只读独立会话，发送完整固定稿件、材料及 Task 冻结方法，直接观察实际完成后接纳标准审查回执。它不会安装长期签发权限，也不接受调用方 JSON 作为完成证明。完成后读取实际前审结果：有问题则修稿并重新审阅，通过才按既有授权继续。没有 native 客户端、登录不可用或执行中断时保留 needs_reviewer/失败事实，不临时配置 API key，不自签通过；running 时先核对已有 Task，不能重复调用。此入口不替代明确适用的人类专业复核，也不把 content_only 扩大为整套生产。

## 首答与实际交接

首次返回已有规划或阶段产物时，直接说明本次推荐、关键取舍、所用方法如何改变实际稿件、仍需决定的关键问题，以及下一责任与可执行动作；不要只说“已完成”让用户追问。方向已定时据此推进，不制造假备选。材料足够即可在现有授权内写稿；只有会改变关键事实、范围或不可逆选择的缺口才阻塞对应部分，非阻塞追问不拖住独立部分。用户反馈通过 Runtime 更新实际 Narrative/Plan/Page/notes，再核对输出版本，不把聊天解释当作已改稿。

每次退出按当前 request/scope、completion.outputs/checks/missing 报告实际完成范围、可读产物、停止原因和下一责任；作者判断与独立审查分别说清。已有授权且当前 Host 能执行时，Master 实际读取下一 Task 并协调，不把一次子职责退出当整项任务停止。能力不可用时交出固定项目/版本、真实 Task、有效 scope、方法 reader 入口、产物及缺口；仅复制上下文时明确尚未领取或启动。真实接手须有对应 reader/执行身份与产物变更证据，不能靠结束语模板证明。

跨轮先核当前 Task、Request、Attempt 与真实执行身份，按共享 [路由与恢复方法](references/collaboration-routing.md) 的跨轮表处理；不要重发已完成调用，不改写旧身份或把 unknown 当 not_sent。原生内容审查已留存完整证明时，先用同版 `review recover --project <dir> --task-id <id>` 恢复原 Task 的证明；此入口不补签、不续期，也不是新审查。缺失/过期或取消后的证明仍返回真实阻塞。

## 同一发布版与方法

先读取本次 Host 入口路径，不从 PATH 或 HOME 猜另一套安装。把 `skill_entry` 设为实际加载的 SKILL.md 路径（保留未解析的 Host 路径，升级/回退后重新解析），执行：

```python
from pathlib import Path

skill_file = Path(skill_entry).expanduser().resolve(strict=True)
release = skill_file.parents[2]
skill_name = skill_file.parent.name
python = release / "venv/bin/python"
if (skill_name not in ("deck-master", "deck-content", "deck-design", "deck-review")
        or skill_file != release / "skill" / skill_name / "SKILL.md"
        or release.parent.name != "releases"
        or release.parent.parent.name != ".deck-master"
        or not (release / "release.json").is_file()
        or not python.is_file()):
    raise RuntimeError("Skill is not in a complete managed release; check installation")
deck_master_cli = [str(python), "-I", "-m", "deck_master"]
```

用 `subprocess.run([*deck_master_cli, ...])` 调用；不能将参数拼成 shell 字符串。
源码开发安装须通过 doctor.module_path 核对所属 checkout 与实际 Python。
四入口共享 [路由与恢复方法](../deck-master/references/collaboration-routing.md)，内容/设计/审查方法只有 `deck-master/references` 一处 canonical；不复制到其他 Skill。
存在 Task 时，`resolve_task_methods(task)` 返回的冻结有序 `method_manifest` / `method_resources` 是唯一准确清单，逐条读取其真实 path/SHA；上文方法名称是职责提示，不得另加当前角色默认方法。旧 Task 仅按冻结 RC3 selector 与原 digest 可证明的依据读取，不静默补新 Review 方法。`basis_changed`、缺文件或 hash 不符须保留原 Task/草稿，通过 Runtime continue 正式退役并重新派发，先结清未决调用，沿用真实 scope 和授权。新 manifest/policy 持久事实要求 `rc4-content.v1`，只读和旧结果精确重放不升级历史。

用该发布版 Python 调用 `method_resources.read_skill_methods`，传本角色、`entry_mode=named|natural|master|recovery`、真实 project/task_id；自然路由另传原始 text。无 Task 的职责入口按实际 scope selector 返回清单，不自己拼第二套方法。前审涉及 argument/page_copy/progression/speech 时，消费实际范围的完整方法并集，包含 source-reading、content-methods、content-examples、content-calibration、review-and-repair；纯视觉审查按其实际范围读取，不扩大生产权限。

先读 `capabilities.read_protocols`；支持时可用 `read_protocol="work_context.v2", body_mode="full"`，未协商仍是 v1。v2 full 默认返回完整方法和来源，保留全部 Page/notes/限定、原图 refs/尺寸和物理约束；manifest 的 `context_ready=false` 不能执行为上下文已齐。delta 只省略当前受信适配器实际观察到的同一 Host session/context generation 可取回字节；新会话/压缩后或缺观察按冷 full，CLI cache offer 本身不能证明会话。可随时 full 重新取回。

`runtime_returned_bytes`、body/cache 传输状态只证明 Runtime 返回或省略了哪些字节，不证明 Host 实际阅读、应用、独立审查或批准。实际执行身份、方法 SHA、判断、修改、产物及限制另记。恢复读取当前 scope/决定/撤回和 completion，不重复建项目或补授权。


## 当前工作与下一责任（协商读取）

先检查 capabilities.summary_protocols。支持 `workbench_summary.v2` 时，
使用 `view --summary --summary-protocol workbench_summary.v2`；Python 方法 reader
在 `read_protocol="work_context.v2"` 外显式传 `summary_protocol="workbench_summary.v2"`。
四职责都消费同一 `current_work`，区分 delivery、review、next、blockers 和 optional。
旧核心只返回已有事实与通用阅读入口，不自行补全制作责任。读操作不调用 continue、
不创建 Task、不花模型预算；真正继续仍走原授权、basis、CAS 与 operation。
首次有可读产物且当前 Host 支持时呈现一次；后续更新入口。URL、系统接受打开、
前端加载、用户看见分别报告；没有观察保持未知。云端 loopback 不冒充用户可访问链接。

大纲稳定且本次需独立早审时先读取 `review outline-status` / `review outline-packet`。
只有当前授权、预算和真实通道支持，才经 `review outline` 派发或
`review native --subject outline` 执行；不能把组包当审阅。
既有运行/失败 Task 优先查询与 recover，不以新执行重复收费；不可用返回可读待审稿。
大纲仅覆盖 argument/progression；逐页稿与视觉资格仍分别判断。
子职责返回后按同一 next 与当前权限实际接续；已有产物不得因呈现失败而重制。

共创接续按 Content 的“方法共创的接续与证据”执行：交接保留用户原话来源、采用依据、
实际前后产物引用与尚待处理的图表/视觉依赖；不要把讨论、文本采用、视觉更新和 Review
通过合并成一个完成结论。正式要求冲突只阻塞受影响部分；未采用建议与已完成产物保留。

接续外部审阅返修时，按 review-and-repair 的外部报告合同实际读取固定原报告与
review repair-handoff 完整清单，再沿已有授权、binding/import 和原 finding 复查。
不让用户手工复制完整背景，不把同名 R01 或通用前审 pass 当作原报告已全部关闭；
无法绑定保留源外清单及未核查维度，最终明确原 F1 是否仍影响用途。
