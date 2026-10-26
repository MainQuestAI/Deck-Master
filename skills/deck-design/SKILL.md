---
name: deck-design
description: 独立设计方案、版式可行性与限定样页试作；消费确认正文、信息关系、模板和品牌，返回recipe、样页候选与覆盖范围，不自动改主线或扩到整套制作。
---

# Deck Design

## Use when

只做视觉方案、模板/品牌分析、代表页布局、密度与阅读距离判断、先试一页或限定样页。

## Do not use when

需要补论据/重写内容用 Content；只读审查用 Review；整套制作协调用 Master。不能为设计强制重建已确认稿的 Narrative，也不能以设计为由删正文、改箭头责任或更换结论。

## 方法与允许产物

按 content-to-visual 保留比较范围、因果/假设区分、责任与必要限定。只读本次语义关系相关示例，不重跑内容分析；Toulmin、Pugh、SCR 不对应固定版式。内容放不下时提出具体拆分/压缩候选，交 Content/用户，不静默改稿。

读真实 Page 全稿、Plan 对应条目或合法 imported_mapping、来源/决定、template/recipe 与固定 scope。独立读取 visual-reference、style-calibration、candidates-and-stages、blueprint-svg 与 physical-units。先判断关系（矩阵归属、流程方向、对比条件、层级）与密度/阅读距离，再提出能承载完整正文的版式；无法承载时给出具体内容取舍候选，交 Content/用户决定，不静默删字。

方案包括 Design/recipe、适用页型、代表页选择、布局理由和未覆盖范围。外部试作只对明确授权页和 allowance 执行，固定准确 generation_input/prompt/refs/canvas/物理尺寸后调用真实 ImageGen；按实际能力 freeze/begin/settle。原始蓝图、原 prompt 和失败均保留；无工具返回 needs_tool，不造图。

方案与试作前按实际 compiler 支持子集说明可编辑边界：文字、关系连线和主要业务对象应可分离地重建为原生可编辑 PowerPoint 文字与形状。照片、获准 logo、纹理和复杂插画可作为有明确范围的位图素材；素材整体可替换，但内部不能逐对象编辑，不能承载本应可编辑的正文、关系或主要业务对象，更不能以整页嵌图冒充可编辑重建。所需效果超出支持子集时，先说明原生重画、局部素材化或简化的处理与视觉、可编辑性影响，不静默降级。此边界同时适用于 agreed_layout 与 model_designed，仍保留各自构图自由，不一律禁照片、阴影或插画；说明属于生产上下文，不追加上屏文案或新的审批流程。沿用已冻结请求与方法，不以新说明补改旧输入。

样页候选不是采用；显式采用也不扩大页集合/调用预算。生产与重建的正文来自固定 Page，视觉来自固定原图；信息关系不可仅靠字符覆盖判定。按 physical-units 核对实际 p:sldSz、逐角色 run 字号、SVG 与原生 PPT 留白，不能改 converter 常数或在外层补一套未冻结字体。

## 退出条件与下一责任

请求的方案/限定样页候选和覆盖说明已返回即结束本职责。零调用方案读取 styles.propose 返回的 completion 与 proposal_ref；completed 只表示本次范围的方案产物已返回，不是用户确认或样页生产许可。尚未确认的提案不属于 Document 已提交状态，保留返回的固定 Ref，不要求用户为了结束本职责而确认。已确认规范由 continue 按当前 request、scope 与 basis 回读；历史或局部方案不能冒充新请求的完整结果。缺内容依据交 Content，缺样页选择交用户决定，获得范围授权后由 Master/Producer 接续。完成/needs_tool/needs_reviewer 按 Runtime 真正状态与产物分列，不自动整套制作。

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
