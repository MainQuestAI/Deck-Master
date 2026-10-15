---
name: deck-master
description: 从任务、材料或已有项目协调内容、设计、制作和审查，按有效范围连续推进及恢复；需要策划、写稿、样页或只读审查时分配到对应职责。
---

# Deck Master

## Use when

新任务、完整制作、续作、局部修改或职责未明；需协调 Content、Design、Review 与授权内 Producer。

## Do not use when

已明确只策划/写稿/口播、只设计或只读审查时，直接使用对应 Skill 的独立范围。已有合法决定与授权继续有效，不为了换 Skill 重新询问。

## 方法与允许产物

1. 读原始指令、来源、当前 request/eligibility/completion，区分决定、授权与具体文件认可。省略格式的新建默认 workbench.v3/rc3；不选择旧协议规避资格。
2. 对新任务形成任务理解、拟议范围、关键未知和下一责任；通过同一 Runtime create/start_request，保存真实 instruction evidence。模型建议不得记成用户已接受决定。
3. 按请求的职责调用 Content/Design/Review；传同一项目、固定版本与 scope，不复制状态。完整制作只有在资格允许时才交 Producer 继续蓝图→SVG→真实 PPT→逐页/最终检查。
4. 每次接纳后读取 completion/continue；用户只要内容或样页时到本次完成即返回，不隐式整套制作。已有非空稿可打开实际 Studio 供查看，打开不代表授权生产。
5. 费用按实际 begin/settle 记录；取消、暂停、撤回或 basis 过期后仍结算真实已发调用，拒绝稿件采用。不重复执行已完成调用。
6. 两用途版本按同一 start_request 的 variant_transition 选定源 revision/export；先固定第一份，再生成第二份独立 Plan/Page/output。编辑旧版本明确源与页/字段，不能用 restore 全项目模拟窄改。

允许产物：任务理解、范围与影响说明、待决定项、下一责任及授权范围内实际作品；所有持久化写入经 Runtime service/CAS。

## 退出条件与下一责任

本次 completion 已完成时返回其 outputs/checks；needs_reviewer/awaiting_decision 返回可读稿、具体缺口及下一责任。full_deck 交付按准备附上的实际文件执行 eligibility/handoff-check，工程与专业/人类/桌面状态分列。不得把旧 Desktop 记录称为本轮实际桌面已验。

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
真实工作单的 `method_resources` 是要读取的准确文件、路径与 SHA。用该发布版 Python 调用 `method_resources.read_skill_methods`，传本角色、`entry_mode=named|natural|master|recovery`、真实 project/task_id；自然路由另传原始 text。返回字节只证明读取，实际完成的判断、修改、产物和限制另记。恢复读取当前 scope/决定/撤回和 completion，不重复建项目或补授权。
