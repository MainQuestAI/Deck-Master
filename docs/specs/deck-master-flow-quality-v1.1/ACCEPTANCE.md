# ACCEPTANCE v1.1：18 条验收

证据分三类，不能互相冒充：

- **A**：自动测试，包括单测和集成测试；
- **R**：真实命令输出，在本机隔离 HOME 或真实项目中执行；
- **H**：真实 Codex 会话记录，由老板实际运行。

| AC | 验收内容 | 证据 | 任务 |
|---|---|---|---|
| AC-01 | create、continue、task status 的工作单都含 `project_context.task`，其中包括完整的 7 个字段和 `presentation_mode_source` | A | T1 |
| AC-02 | `method_resources` 按 kind/intent 派发，每项的 path 真实可读、sha256 与文件一致；Task 记录 `method_release` | A | T1 |
| AC-03 | 输入更新后，仍未结束的旧任务显示 `context_status=stale` | A | T1 |
| AC-04 | CLI 的 5 个任务参数和 `--task-file` 都落入 Document.task，合并规则符合 SPEC §3.2 | A | T2 |
| AC-05 | decisions 双来源冲突、task-file 含未知字段、brief 冲突，都返回 exit 2 `task_field_conflict` | A | T2 |
| AC-06 | 用目录作为 source 时：工具目录、锁文件、0 字节文件、`--out` 自身、指向根外的链接进 skipped；名为 `output/` 的普通目录不被跳过 | A | T3 |
| AC-07 | 显式点名的坏文件 → exit 2，且没有半成品 Document；新 ID 为 `src-<uuid8>`，旧 `src-N` 保持不变 | A | T3 |
| AC-08 | `examples/input-context-before/after.json` 的 input_digest 可复算，分别为 `c8955…fffd` 和 `bf032…9945` | A | T4 |
| AC-09 | inputs update 满足：幂等；op 复用但内容不同 → exit 5；base 过期 → exit 5；新材料失败时当前状态不变；只改显示名时不派任务 | A | T4 |
| AC-10 | 更新成功后：开放任务变为 superseded，派出 input_revision；Page、蓝图、SVG、PPT、Review、outputs 全部保留 | A | T4 |
| AC-11 | 用 `result-input-revision.json` 采用后，p01/p02 的正文 hash 等于 `expected-effects.json`，槽位保留；p03 重建；输出中不出现 forbidden_claims | A | T5 |
| AC-12 | **只改 task 字段后，旧 scoped 任务结果被拒绝（exit 5）**；superseded 任务的迟到结果被拒绝 | A | T5 |
| AC-13 | needs_reconciliation 时：delivery 导出和 handoff-check 返回 exit 3 `input_reconciliation_pending`；review/working 导出成功并带标注；c93 旧项目显示为 legacy_current | A+R | T5 |
| AC-14 | 六维只在一处定义；最终工作单只列真实缺口；输入更新后 content/privacy 重新列入；逐页 pass 不能直接变成最终 pass | A | T6 |
| AC-15 | wheel 和 sdist→wheel 中的 `resources/skill` 与 canonical 字节一致；没有 skills-references；CWD 放假文件不影响 `resolve_root`；canonical 中没有 D1/D2 和旧术语 | A+R | T7 |
| AC-16 | `skills/` 只剩 deck-master 和 RESOLVER.md；除历史文档外，没有地方引用旧 Skill 名；legacy run 提示仍然正常 | A+R | T8 |
| AC-17 | **真实端到端**：在仓库外新开 Codex 会话，走完下面的 7 步场景 | H | T9 |
| AC-18 | 安装、回滚、迁移（在隔离 HOME 中）：受管链接正确；已占用 → exit 5 且 current 不切换；旧 companion 布局迁移只删除 15 条断链，第三方 Skill 不变，重复执行结果不变；回滚到无 skill 的旧版本时移除链接 | A+R | T9 |

## AC-17：7 步场景（从仓库外、新开的 Codex 会话启动）

1. 老板给出一个普通材料目录和一句业务任务，其中写明受众和一条已确认的决定。Host 不重复询问已给出的信息。
2. 工作单带有真实的任务、材料和对应方法。首稿正文完整，结构符合场景，而不是套用通用目录。
3. 通过现有工作台显示真实页面，不用外部手工文件冒充主链路的产出。
4. 老板补一份已确认的接口说明（相当于 V1→V2）。Host 用 `inputs update` 写入，只修改受影响的页，其他页保留。更新完成前，delivery 被拒绝。
5. 老板说「改成独立阅读」。Host 更新 presentation_mode，只调整需要改的正文深度，其他页保留。
6. 开一个新会话，从同一项目继续。已确认的决定仍然有效，方法路径指向当前安装。
7. 最终审阅工作单只列出真实缺口的维度。失败项真实返修，导出结果和 handoff-check 一致。

记录要包括：每一步的命令、exit code、工作单摘要、工作台截图，以及第 4、5 步前后 p01/p02 的 hash。

## 必须保留的负向回归

以下每条都至少要有一个 A 类测试：

- 任务事实变化后，旧的 scoped 结果不能被采用；
- 目录里有坏文件时，不能变成假成功；
- 没改的页不能被无故重新生成；
- 旧的 must_fix 不能被普通 pass 覆盖；
- pending reconciliation 状态下不能 delivery；
- readback 失败时不能 delivery；
- 安装器不能覆盖任何用户自己的或第三方的 Skill；
- 方法文件不能从源码 CWD 读到另一版本。

## 不算完成的情况

- 只有 A 类证据，没有 AC-17 的 H 类证据；这种情况只能交付为「工程候选」，并写明未验证的范围。
- 用手写 JSON 或拼出的范例代替真实命令输出。
- 在老板的真实 `~/.codex/skills` 上做破坏性试验。AC-18 必须在隔离 HOME 中完成；真实迁移由老板授权后执行一次。
