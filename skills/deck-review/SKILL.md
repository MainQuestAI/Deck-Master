---
name: deck-review
description: 只读审查项目快照、外部PPTX或明确文件集，检查内容、关系、口播、视觉与交付证据并返回具体findings；不制作、不自动修复，换Skill名称不产生独立身份。
---

# Deck Review

## Use when

用户只要审稿、批评、检查事实/推论/页序/视觉/口播/转换/隐私或核对交付文件；源可以是固定项目快照、外部文件或明确文件集。

## Do not use when

要写稿/修稿用 Content，方案/样页用 Design，完整制作/执行返修用 Master。Review 自身不生图、不转换为生产项目、不接纳候选，也不把“只审”解释为可修。

## 方法与允许产物

按 method-review 检查实际判断、理据、替代方案与正文，不因表格或术语齐全而通过。按审阅范围选必要方法卡与校准例，作者采用的方法不是审阅真理。检查样例数字被写成客户事实、相关性变唯一因果、设计措施变已验证保证等问题；给出具体位置、影响和修订建议，仍保持只读。

实际读取指定范围、当前文件/固定快照、任务与相关来源，再读 review-and-repair、content-methods、content-calibration、physical-units；前审按工作单的完整方法集。定位到页/atom/行列归属/责任箭头/实际文件 hash，写期待、实际、事实/推论依据、用途影响、F0–F3、修复责任层及验证边界。稀疏、教学示意、诚实未知须按用途判断，不强造数字或删限定。

严格只读使用 `external_review.evaluate` 或文档化 review evaluate，persistence=none；不创建项目、Task、Review 或控制记录。报告/临时文件放源目录外，不接受重叠目录、别名/符号链接、错 SHA 或覆写源。输出 findings、工程观察、source_unchanged、needs_reviewer/needs_tool 和真实覆盖限制；缺阅图/渲染不判 pass。用户另有明确保存意图才由 Master 走固定原稿绑定/CAS的 review import，保持原来源与证据等级。

作者自审标 host_self；同作者换 Skill 名、task、execution ID 或提示词不会变成 independent。独立执行须有实际非作者执行与受信回执，人类 professional 须真实人类通道；缺能力明确 needs_reviewer。字符回读不替代关系/实际渲染，旧 Desktop 记录不等于本轮桌面验收。

## 退出条件与下一责任

返回可读报告、证据/范围、未完成维度的具体原因即完成约定审查；未验证项保留缺口。下一责任按问题归属 Content/Design/Master 或交付判定；本职责不制作也不自动修复。

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

共创后的审查按固定版本核对原话来源、正式采用依据和实际前后差异：用户经验是否改变了
推荐、正文及受影响图表关系，还是仅贴了方法标签；改写有无删改数字、范围、因果强度、
承诺、责任、否定或条件。必要术语和承担功能的回顾不得仅因重复或不够短而列为必须修改。
沿原 finding_id、owner、replaces 和当前对象引用复查；未阅实际图像或 PPT 就保留视觉缺口。
