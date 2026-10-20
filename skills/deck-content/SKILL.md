---
name: deck-content
description: 独立策划、论证、逐页写稿和口播：只做策划、按确认大纲写完整正文、只写指定页讲稿或提供完整内容包；完成内容后返回，不自动制作PPT。
---

# Deck Content

## Use when

材料研究、受众目标、内容规划、完整逐页稿、确认稿改写、限定页/字段局改、只写 cues/verbatim 口播，或 content_full。

## Do not use when

只要视觉方案/样页用 Design；只读检查用 Review；要整套作品或跨职责恢复用 Master。已确认稿且只照稿设计时，不强制重建 Narrative。

## 方法与允许产物

读取工作单冻结的基础方法和本次选中方法卡/案例；缺资源时沿正式重派发路径补齐，不在同一冻结 Task 私加文件。按认知缺口选择分析、论证、权衡、叙事或教学操作，先形成成立的内容，再按 page-writing 写完整正文。案例不是客户事实，数字脚本仅检查显式算式；说明页和教学页不强制结论标题或商业 CTA。

实际读取工作单指定的 source-reading、content-methods、content-examples，前审再读 content-calibration。区分事实、推论、建议、未知和权威版本；建立受众的起点、目标、论证关系、页间推进与必要限定。完整表格/流程/例子应承载具体业务对象、归属、条件与异常，不能只有标签、泛化小卡片或用备注藏关键限定。

同一 Runtime request.intent=content_only，下列子意图分别独立接纳，不压为一次不可检查全稿：

| 子意图 | 允许产物与完成 | 不超出的范围 |
| --- | --- | --- |
| plan_only | Narrative、ContentPlan、只读论证/计划投影、具体未知/取舍与适用检查 | 不继续 page_copy/口播/设计 |
| write_only | 已确认方向/稿件范围内完整 Page 正文、semantic mapping、页序与约定内容检查 | 未约定不写口播，不做样页/PPT |
| speech_only | 当前固定 Page 或合法 imported_mapping 上的逐页 notes/segments、整稿投影及估时 | 不改上屏正文/页序/视觉，不补造 Narrative |
| content_full | Narrative、Plan、完整逐页稿、约定的 cues/verbatim 和检查组成的内容包 | 不接续图像、SVG 或 PPT |

live 默认 cues，明确逐字稿才 verbatim；read_alone 默认 none。未知用途不凭空套 live。条件、单位、来源和行动边界需在上屏稿自包含。来源/方向变动按正式 inputs update；四层 input_revision 只改声明的 Narrative/Plan/Page/speech，保留未受影响对象。不只改投影 Markdown。

## 退出条件与下一责任

以 Runtime `completion.state` 及该子意图的 outputs/checks/missing 判断完成，不用全项目 work_complete；completed 正常返回内容产物和检查，后续 continue 不要求补制作授权。检查缺口返回 needs_reviewer/awaiting_decision 与现有可读稿，不能把 blocked 当成功。下一责任可以是用户决定、Review、Design 或调用者；未请求视觉生产时到此退出。

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
