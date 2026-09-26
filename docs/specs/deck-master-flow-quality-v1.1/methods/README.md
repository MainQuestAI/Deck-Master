# 方法正文采用说明（v1.1）

本目录是**待采用草案**，不是已安装的 Skill，也不是第二个可编辑源。请先与 canonical `skills/deck-master/` 以及 src 镜像独有的那一行（SPEC §7.1）合并，再落到 canonical。不要把 Spec 目录注册成 Skill。

| 草案 | 采用位置 | 操作 |
|---|---|---|
| SKILL.md | skills/deck-master/SKILL.md | 合并主循环、输入修改和方法读取规则；保留现行有效的制作协议 |
| source-reading.md | references/source-reading.md | 改写材料发现、完整读取和版本/用途处理的方法 |
| content-methods.md | references/content-methods.md | 保留专业方法，去掉旧对象、旧命令和 D1/D2 |
| input-update.md | references/input-update.md | 新增，写持续修改的方法；不新增公开 Skill |
| review-and-repair.md | references/review-and-repair.md | 并入按缺口派发的六维审阅，保留 PR33 已有的关闭条件 |

草案里的新命令（`inputs show/update`、`--task-file`）是本 Spec 约定、尚未实现的接口，实现之前不要用它们操作客户项目。安装后，方法之间的引用一律使用 Skill 内的相对路径。
