---
name: deck-master
description: 从任务、已有讨论与文件材料创建、继续和修改专业演示文稿；保留完整正文、真实蓝图、SVG、可编辑 PPT 和实际审阅。需要补材料、换受众或恢复同一项目时继续沿用已有决定。
---

# Deck Master

公开一个入口；内容编辑、页面设计、转换与审阅是工作职责，不要求用户逐个调用其他 Skill。需要生图时使用当前 Codex 会话内置 ImageGen，不配置 Provider 或 API Key。

## 从当前任务开始

先接收用户已给出的任务、材料、输出位置和已确认决定，不重新完成标准问卷。分清：这次要让谁理解或判断什么、对方已经知道什么、现场讲解还是独立阅读、用户实际要求的篇幅与范围。

先从本次 Host 加载的 Skill 入口路径解析所属发布版，后续所有 `deck-master` 命令都使用该发布版的 CLI。把 `skill_entry` 设为本次加载的 `SKILL.md` 路径（保留 Host 入口路径，供激活或回滚后重新解析），执行以下 Python 片段取得命令参数数组；用数组调用，路径含空格也不拆分：

```python
from pathlib import Path

skill_file = Path(skill_entry).expanduser().resolve(strict=True)
release = skill_file.parents[2]
python = release / "venv/bin/python"
if (skill_file != release / "skill/deck-master/SKILL.md"
        or release.parent.name != "releases"
        or release.parent.parent.name != ".deck-master"
        or not (release / "release.json").is_file()
        or not python.is_file()):
    raise RuntimeError("Skill is not in a complete managed release; check installation")
deck_master_cli = [str(python), "-I", "-m", "deck_master"]
```

执行时使用 `subprocess.run([*deck_master_cli, ...], ...)`。不从 HOME 或 PATH 猜测另一套安装。激活或回滚后，重新读取 Host 入口的 Skill 并重新绑定命令。若明确使用源码开发安装，按 installation 方法确认该 checkout 的虚拟环境，并用其 Python 执行 `-m deck_master`；通过 doctor 的 `module_path` 核对源码归属。无法确认安装来源时停止并报告。工作单 `method_resources` 给出的是本次任务该读的方法文件的真实路径，直接读取；不要凭记忆或其他版本的说明执行。

## 正常循环

1. 文件和目录都可以直接传给 `create --source`，任务字段用 `--audience/--scenario/--presentation-mode/--page-limit/--decision` 或 `--task-file` 传入。目录较杂时，自己挑出相关文件后逐个传入；选料不需要用户审批文件清单。核对返回的 `sources_skipped` 和 `sources_errored`。
2. `create` 返回完整工作单。核对 project_context、原始任务与当前 sources 后，实际阅读材料，按工作方法写完整 Page v2 正文与页序；不调用旧规则 Planner，不先填通用目录。
3. `task start` 后完成任务；`task accept` 接收结果后继续调用 `continue`。等待 Host 表示需要执行，不代表结果已经生成；退出码与返回 status 分开理解。
4. 首次出现非空页面时，沿当前自动工作台协议启动/打开真实 UI。同一项目复用入口，失败稿和待修改稿也可看。无浏览器时提供实际可用地址或具体不能启动原因。
5. 按当前任务执行蓝图、SVG 重构、逐页审阅及实际 PPT 制作。读原图、保留原始蓝图、使用授权素材和实际可见正文，不用整页图片或简图偷换约定。
6. 最终按 review_plan 缺口完成实质审阅，处理具体问题，再按 review/delivery 目的导出并执行既有 handoff-check。工程通过不自动等于人类专业认可。

## 自动工作台（必守）

create --draft / import draft / compose 结果**第一次形成至少一页后，主 Skill 必须立即自动调用 `deck-master view --open`**，再继续逐页制作；service 响应的 `next_action=auto_view_then_production` 就是该动作。不需要用户手动执行 view。同项目复用同一服务与 URL；服务失效才重启并更新实际地址。

## 真实性规则

- 任务输入里只装真实读取的资料与已确认决定；不调用规则 Planner、不循环 claim、不从数组取模配论点、不用固定痛点/风险/CTA 补页。
- `task accept` 前文件已写入本次 operation 的 staging；`produced_against` 与任务派发 hash 一致，否则先重读新输入。
- 外部图像调用先按额度事务 begin，完成后 settle；未执行不报 consumed。
- 蓝图任务只调用当前 Codex 会话的内置 ImageGen；不请求 Provider/API Key。实际提交 prompt、原始图片和可得 invocation ref 一并保存。
- 没有实际阅图/渲染/人类检查的项目保持未验证标注；工程通过不升级为内容专业。
- 普通取舍按当前规则决定，不把每一步交回用户；缺工具、缺授权、真实用户决定是停止条件。

## 用户改变要求时

局部改字、图形偏好继续使用 edit/feedback。新增材料、换受众、改用途或替换正式要求，用 `inputs update` 保存有效输入，不只写在聊天或 repair instruction 中。

处理 `compose/intent=input_revision` 时读取新输入、变化说明与全稿概览，检查相关正文和跨页结论；提交 content_update，只包含真正改变的完整 Page、新增/删除 ID 和最终页序。无影响时给出具体理由，不能据“没有显式引用”自动断言无影响。未改页保留。

确实缺少必须由用户裁决的信息时，在对话中问一个具体问题，说明已知条件以及它为什么影响任务。已有决定不重复问。用户答复后，用 `inputs update` 写入 `existing_decisions`（完整集合）再继续，不要用「已批准」之类的话填空。

## 连续制作与返修

`task accept` 后继续执行 `continue`，直至 `ready_for_export`、用户停止或具体输入/工具缺口。
`awaiting_host` 是交接请求，不是已执行；先 `task start` 再做 Host 工作。CLI 返回 3 时读取 stdout JSON 并处理其中任务，不能把它当成执行失败直接终止。
当前项目仍有待执行任务时，不把外部排版、旧稿选编或单页预览当作本次新稿完成。用户纠正产物后，先重读同一项目的 `continue`，处理它返回的任务。内容与制作分开比较是评价维度，不是跳过蓝图、SVG 和 PPT 制作的许可。

- `reconstruct`：实际读取原图、完整 Page 和允许资产，以任务reference_images给出的实际图片hash读取原图，先写原图模块/关系期待，再输出单份原生 SVG；SVG根写data-blueprint-sha256为该原始图片字节哈希，不能复用同正文另一张图的SVG充当还原。若纠正文案或补标签，同一信封提交更新后的 Page 和理由。不得改写原图，不能仅改 SVG 隐藏正文错误。
- `reconstruct` / `repair` 接收 SVG 时使用正式编译器解析同一份 Page、设计与批准资产；不支持的元素或属性当页修正后重交。`continue` 随后生成当前页 SVG 预览，缺工具或字体按返回原因处理。
- `review_stage=page_visual`：实际打开当前 Page、原始蓝图、SVG 预览，逐项核对正文、数字、模块、图标语义、连线方向和遮挡。按任务给出的 subjects 与 dependencies 提交 `blueprint_content`、`blueprint_fidelity`、`readability` 三类记录；未审不能进入下一页。`must_fix` 只返修当前页；`repair` 只提交 Page/SVG，待新预览生成后在独立 `review` 任务复核。关闭发现需 `replaces`，保持同一 review_id、finding_id、页、kind 与 stage，并证明本页产物实际改变；`needs_judgment` 可在同一产物上凭具体理由、观察和证据记录 `accepted_variance`。原图文字有误时以 Page 与来源纠正，并保留原图及差异记录。
- 所有页面逐页通过后，`continue` 本地执行整套编译、SVG/PPT 渲染和真实文件回读；不需要手写外部编译脚本。失败回到明确的 Page/SVG/编译层处理，不通过重新生图掩盖。
- `review_stage=final`（旧任务缺字段时同义）：按工作单 review_plan 的实际缺口提交 content、blueprint_content、blueprint_fidelity、conversion、readability、privacy 中尚未有效覆盖的维度；已经有效的维度不再要求，额外发现问题照常提交。逐页审图不能代替最终转换检查。Host 自审写 host_self，不能写独立或专业验收。
- `edit --page … --base-revision … --page-hash … --operation-id …` 修改正文后继续重建受影响页；原图保留。`history list/restore` 恢复产生新 revision。
- 输入更新期间（`input_alignment=needs_reconciliation`）：`export --purpose review/working` 允许且产物标注「待按新要求更新」；`--purpose delivery` 和 handoff-check 被拒绝，先完成派发的 input_revision 任务。
- `export --purpose delivery` 要求当前工程审阅通过。导出完成不等于专业或桌面验收完成。
- 在最终回复附上 PPTX 前，对**准备附上的那个文件**调用 `handoff-check`。它必须与当前项目的 `outputs.pptx` 字节一致，且当前页蓝图、SVG、预览、渲染报告和 Host 任务完整；`blocked` 时不得称为本次项目成稿。`--purpose review` 只核对工程来源与制作链，`--purpose delivery` 还要求当前工程审阅通过。该检查不替代人工专业/桌面验收。

统一入口：`deck-master`(console entry = `deck_master.cli:main`)与 `python -m deck_master` 完全同路；退役的旧入口不属于新流程。

## 按动作读取方法

- 成稿：source-reading、content-methods；需要例子时读取 content-examples。
- 输入修订：再读 input-update。
- 生图/重构：读取既有 blueprint-svg 与实际页面/原图。
- 审阅/返修：review-and-repair 与当前 review_plan；内容问题读取相关来源，不只看图。

## 不得偷换的边界

不把开发场景编号当日常成稿流程，不强制痛点、风险、CTA 或每页推荐。正式需求、已发生事实与设计建议保持可区分，但不因没有效果数据拒绝合理方案推理。

不在用户补材料后重启整个项目；不让旧工作单覆盖新决定；不伪造已读取、独立审查、Provider 验证或用户认可。失败原因属于内容就改内容，属于转换就修对应产物，不重签哈希或改基准制造成功。

## 停止与安全

缺输入或工具、需要真实用户决定、用户叫停时停止并说明。保留无关页与已确认设计；私密/内部材料不进客户可见产物；不伪造证据或绕过当前门禁；无授权不导出交付。
