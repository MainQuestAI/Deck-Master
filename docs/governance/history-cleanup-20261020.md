# 历史文档治理记录 · 2026-10-20

本轮只整理使用入口、文档身份和已确认失效引用，不改变运行时、Skill、schema、
版本号、发布状态或仓库线上设置。当前入口为 [文档导航](../README.md)，
历史入口为 [归档索引](../archive/README.md)。没有删除用户资料或历史原件。

## 基线与并行边界

开始时读取远端 main，基线为 `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`。
当时开放 PR 为 127、128、113、109。本轮保留其依赖路径，不把候选内容写为主线能力。

- PR127 的内容方法库/Host 选择不在本轮修改范围。
- [PR128](https://github.com/MainQuestAI/Deck-Master/pull/128) 的 Issue 维护候选
  `666489c7623f6cfff6134f38696731ca35a3a3c8` 已核对文件清单与 README patch。
  本轮不修改 CONTRIBUTING、SUPPORT、SECURITY、Issue/PR模板或其维护指南。
  README 只改历史试用说明，并在 Project Docs 标题下加入分层索引；不改 PR128
  在该列表末尾添加的两条链接。以共同基线做三方文本合并检查无冲突，未实际合并 PR。
- 后续 WebUI 规格/实现不在本轮改写范围；旧 Spec 的 AC 数量和完成态不代替新任务。
- 开放 PR113 相关 RC3 记录和兼容基线保留原位，不能因“较旧”宣布任务已关闭。

## 四类分类与实际处置

[逐文件清单](document-disposition-20261020.csv) 复用成熟度审查的906项盘点。
以 Git NUL 分隔路径核对，其中905项是基线跟踪文档，1项是未跟踪的pytest缓存说明。
后者明确排除，未提交缓存，也未删除工作区缓存。清单分类不代表逐页人工审阅所有文档。

| 分类 | 原盘点项数 | 本轮如何处理 |
| --- | ---: | --- |
| 保留并更新 | 370 | 用户/Agent/工程继承入口与范围外文档原位保留；仅对确认有问题的入口修订，不批量改正文 |
| 合并去重 | 1 | 将RC3试用的“当前使用”职责归并到getting-started；原文移入归档，旧URL/章节保留兼容入口 |
| 历史归档 | 532 | 现有归档及报告/QA按时点证据建立导航；多数原位不动，不移动被冻结或仍被引用的文件 |
| 确认废弃 | 3 | 两个归档README中“旧架构就是当前基线”的导航主张撤回；另1项是非源文档缓存，不是删除3份原件 |

类别用于资料的处理语义，不表示某个目录中所有合同均已失效。
例如RC4台账仍是其增量的权威历史证据；运行合同继续以实际代码/schema为准。
清单中的 `action` 才表示本轮实际动作，`retained_or_archive_path` 保留可追溯位置。
本轮新增的索引和本记录不计入原906项基线。

清单 reason 解释：`outside_docs` = 范围外保持；`reference_preservation` = 引用保护；
`dated_evidence` = 时点证据；`inherited_or_open_contract` = 继承/开放任务合同；
`design_identity` = 设计身份；`superseded_tryout` = 旧试用归并；
`obsolete_navigation` = 旧导航主张失效；`confirmed_link_and_role_error` = 已确认链接/职责错误；
`current_user_navigation` = 当前用户导航；`not_tracked` = 非跟踪缓存。

## 文件变更与理由

| 文件 | 实际变更 |
| --- | --- |
| 根 README | 当前使用指向首次运行，RC3改为历史兼容入口；增加文档/归档总索引，不改安装命令或版本能力声明 |
| docs/README.md | 新建按使用、恢复、贡献、合同、设计、Spec、证据、历史分层的入口 |
| docs/specs/README.md | 新建各Spec目录索引，区分继承合同与时点方案，保留开放状态的不确定性 |
| docs/reports/README.md | 新建按基线/范围读取证据的索引，不用历史PASS证明当前候选 |
| docs/archive/README.md | 新建归档索引，同时解释原位历史材料不等于活动用户说明 |
| docs/rc3-tryout.md | 保留原URL和全部章节锚点，归并当前试用导航到首次运行；链接历史对应章节 |
| docs/archive/rc3/tryout.md | 完整保存RC3原文，仅加历史警示、修正移动后的相对Skill链接；明确克隆main不能固定RC3 |
| docs/migration-to-rebuilt-core.md | 修复活动schema链接；纠正“当前只有单Skill”误读，指向四职责resolver |
| docs/archive/pre-rebuild/README.md | 当前入口改为文档导航；rebuild标为继承基线；修复退休记录路径、当前四职责说明 |
| docs/archive/endgame-runtime-2026-06/README.md | 将v0.9主线描述限定为历史；修复旧QA场景位置，不再称当前可执行验收 |
| docs/governance/ | 本记录、原906项处置清单及有限验证结果 |

## 兼容与原件保护

- 原所有已跟踪Markdown路径仍存在。RC3旧页的标题和各章节锚点全部保留，
  原有报告 `rc3/cloud-recovery-20261017/ordinary-function-followup.md` 的入链继续可达。
- RC3原文SHA256：`d9f7c6edda6793a7325c48ee02d502c5f60bed6c18b76920890d45edc8715a53`。
  验证去除新增警示并还原唯一相对链接后，归档正文与基线原文逐字相等。
- 不移动或修改Spec中的schema镜像、hash清单、测试夹具、不可变项目对象、设计接收包
  或报告raw证据；不改相关路径的代码/测试消费者。
- 历史文档里的命令只保留作为原时点记录，不因归档而重新变成可执行建议。
  当前迁移说明/任务索引仍负责命令语义；本轮未运行完整制作或客户项目。
- 没有修改旧证据里的真实失败/未知结果，也没有通过改日期或版本把它们重标为当前PASS。

## 重复内容的裁决与待确认项

已做Markdown字节重复扫描及源码/测试/Skill/清单引用查询。
以下重复有明确身份用途或历史hash引用，本轮**保留**，不把去重扩成销毁证据：

1. pre-rebuild中的完整开发Spec单文件与spec-pack的master副本；以及v0.9集成评审
   单文件与spec-pack副本。它们被RC3历史raw verification逐路径记录hash。
   未来如需收敛为单份，应先决定历史路径/hash兼容规则；本轮不替换成跳转文件。
2. 2026-09-30设计语言原件与Workbench报告design-snapshot。分别是接收包和报告快照，
   不能合并为会随设计更新漂移的一份文件。
3. Flow Quality材料与示例项目对象目录中的同字节文件。后者是不可变对象，不能做文件级去重。
4. 老审查报告的私人路径/不可访问外部证据和历史断链：不虚构替代证据，不批量重写，
   有需要时由资料Owner补可公开材料；本轮只修改变的导航与已确认目标。
5. RC3/后续WebUI/RC5仍有开放任务或未合入候选。是否彻底迁入archive由任务关闭及
   引用核验决定；仅新增导航身份，不声明全部完成或废弃。

这些待确认项不妨碍当前使用入口清晰化；不要求全库历史链接全绿才接纳本次窄改动。

## 验证范围

- 相对链接与Markdown章节锚点检查：覆盖本轮修改/新增的Markdown，包括兼容入口。
- 归档正文等价、旧章节锚点保留、905个原跟踪路径保持、906项清单唯一性核验。
- README与PR128共同基线三方合并试算，无冲突，保留双方导航；不写入PR128分支。
- 现有 package-boundary 测试与diff whitespace检查；具体结果见
  [验证记录](history-cleanup-validation-20261020.json)。
- 未修改运行时/方法/运行合同；未跑模型、真实渲染、完整生产链、线上表单或发布验收。
  外部URL可达性和最终CI另行观察，离线链接通过不代表远端已合入。
