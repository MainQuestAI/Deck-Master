# 12｜旧run、旧流程、旧合同与历史文档退役

## 12.1 只读兼容，而非继续维护第二个产品

新核心能做的兼容：inspect旧目录、读取已知JSON/媒体、把真实正文和可识别资源复制导入新项目；不会调用旧OS自动继续、重签旧审阅或继承旧completed。需要原样继续旧run时，用户明确使用固定旧版安装；两种写入者不能同时操作同一目录。

禁止就地迁移原run。import legacy的out必须是新目录或明确新项目，源目录与其子目录不能作为目标。所有读取只针对允许格式和登记路径，不执行运行目录.py/.sh、不加载pickle、不执行宏/Office自动化。未知版本显示可看原件和无法映射部分，不猜测。

## 12.2 字段迁移表

| 旧内容 | 新落点 | 必须保留/不得推断 |
| --- | --- | --- |
| PagePackage v1 customer_visible | Page v2显式正文块 | 完整副标题、items、表格、labels、footnotes；未知结构返回待规范化 |
| narrative_plan beats/order | Document.pages顺序 | 显式页集合；重复/缺ID冲突不能静默去重 |
| speaker_notes/internal_only | 对应分离字段 | 正常业务备注保留、制作指令不变正文 |
| source/context manifest | Document.sources与source_extract | 原位置/hash/来源说明；没原文就未知，不能用页面正文补证据 |
| original blueprint/prompt | Artifact及provenance | 原生成输入与文件字节；无法核实调用标unknown |
| SVG/PPT/预览 | Artifact legacy_import | 可查看可诊断，不默认通过新当前检查 |
| review/status/approval | 历史说明/参考对象 | 不转成新pass/human-approved；current重新按实际输入检查 |
| MBB/Scene/trace | 辅助解释或诊断附件 | 不作为新内容权威，不自动生成业务事实 |
| 旧Library记录 | 来源线索（明确要求时） | 不重新跑库平台，不承诺原整页混编可继续 |

v1→v2转换分两步：程序转换已知结构并列出未映射路径；Host依据原文完成有歧义正文规范化，再接收成新Page。这个动作属于实际内容迁移，不要求用户逐个填治理字段。未映射信息不能静默丢弃后报告成功。

## 12.3 导入与回退验收

对原目录计算关键文件hash及写入检查；inspect/import前后不变。新项目所有ref应可解析，源断开不影响已复制媒体查看。original_sha256=null/缺省均为合法未知；extract和媒体file的真实hash仍逐字节核对。补回候选原文时，已知hash不符必须新来源版本；未知hash不能声称候选就是旧原文。导入后的语义/视觉状态是未检查或legacy-unverified；实际跑新检查后才能变当前通过。

新版导入失败删除的只能是本次未激活staging；不能回滚时删原run或整个用户output。历史已产出的PPT应保留独立可下载，而不是“无法导入就没有文件”。跨目录移动测试分源资料移动和项目整体移动两种。

## 12.4 合同与代码归档

旧58份docs/contracts在WP05移入`docs/archive/pre-rebuild/contracts/`，保留原字节与版本；新运行时只使用五份schema。legacy若需要识别旧结构用有限读取器或只带必要旧schema，不能import旧engine以获取assert_valid。

旧scripts在替代与调用迁移完成后按177行台账删除；Git保留历史固定引用。原有旧tests的有价值行为迁到tests/rebuild；旧错误产品假设删除；旧完整测试仍可在固定旧版本运行，不为了当前CI绿而随意skip。

旧docs历史不一刀切删除。活动入口改为新Spec和新指南，历史设计文档加索引说明“已被替代”；准确保存当时事实和错误完成声明的更正，不重写原始测试日志或回填通过。

## 12.5 活动文档清单

README、AGENTS、CLAUDE、DESIGN、ROADMAP、CONTRIBUTING、quick-start、user-guide、agent-guide、recovery-playbook、task-index、known-limitations、troubleshooting，以及单Skill与其references必须一致。实际路径存在与引用关系需要Codex核验：存在则改，缺失则按目标新建，不能把计划路径冒充现状。

旧SC-1/P2–P5/Skill OS/RC方案不自动延续为新范围，特别是：用户时间下降30%、所有Skill齐备、PPTMaster认证、固定风险/CTA、团队商机审批、结果自己做蓝图等都不能因历史文档继续被宿主读取而复活。

## 12.6 何时可以删，何时不能删

可删条件不是“新目录已经存在”，而是：目标行为和正反例已通过；默认入口/安装已不引用；旧run读取与必要回退明确；static+runtime资源引用检查没有残留；许可证和历史来源保留。每个旧文件在台账标迁移证据/目标测试，不要求逐行签章。

没有新行为替代的有效取消/事务/内容完整性测试不能删。只检查错误门禁的测试不必为了保留而扭曲新实现。客户资料、模型输出原件、旧run、第三方安装资源不在仓库删除清单，永不通过本轮自动清理。

## 12.7 不把历史保护变成新负担

保留Git历史、必要旧格式读入、用户原文件即可，不要求新用户安装旧release、复制旧schema、运行legacy问卷后才能创建新Deck。新文档不通过数十条“兼容前置”重新制造旧流程。

## 12.8 旧设计资料导入

能够明确读取的画布、样式、字体名称和Logo等映射到design_context；实际保存媒体拷为asset Artifact并保留来源身份。旧style_ref只是未知路径/名称时列明未解析项，不让Host/compiler/UI各用不同默认。原信息确实没有时以可见的导入假设保存默认，并等待需要它的动作确认；查看旧PPT不以新设计配置全部补齐为前置。

不会把旧图片/历史PPT自动升级成Office原生图表/表格。导入Artifact.editability=unknown直到实际核查；先支持既有媒体可查看、正文可继续编辑，证据缺口按具体任务展示。
