# RC3-02 独立交付证据检查｜phase1

结论：所读取的现有公开合成包内，真实 PPTX notes 的逐页全文、空行和末尾换行与编译输入、单独口播文档、回读记录及 manifest 一致；目录和两层归档字节的 hash/size 一致。此结论仅针对下列实际文件字节。构建记录缺 implementation Git SHA/tree，不能据此宣称冻结代码 `27823c5c3e52a50201569e1d087406ddeff3832f` 或正在修改的产品代码通过。桌面备注视图、编辑保存重开和人类验收均为 NOT_RUN，未创建任何人类验收事实。

## 审查范围与方法

- Reviewer 未参与实现。此次只读现有 `/workspace/work/rc3/notes-local-acceptance` 和其构建脚本/原生文件；不运行其构建脚本、不导入产品代码、不修改产品、包、原件、他人 raw、ledger 或源码/测试，不 commit/merge。
- 已按要求读取 AGENTS.md、agent-task-index.md、agent-recovery-playbook.md、immutable RC3-02.md 和 RC3 ACCEPTANCE.md，并参考原 AC-N01–N04/CQ-06 的判据。完整原代码 RQ、原轮失败和未来修复复审不由此检查覆盖。
- 独立探针 `probe_pack.py` 只使用 Python 标准库。实际执行先 source `/workspace/work/rc3/env.sh`，随后使用绝对路径 `/workspace/work/rc3/reviews/env-02-snapshot-27823/bin/python`。
- 从 `ppt/presentation.xml` 的实际页序解析 slide relationships，再解析各 slide 的 notesSlide relationship、notes body placeholder 的每个段落，最后检查 notesSlide 对 slide 的反向关系。没有调用 Owner 的 `notes_records`，也没有把“存在 notes XML”当作全文证据。
- 原始读数、路径、hash、大小、XML 关系、备注全文与运行身份见 `phase1-package-probe.json`；stdout 见 `phase1-package-probe.log`。这是部分 L6 文件工程检查，不自动关闭完整 L6、原 AC/CQ 或全部 RC3。

## 实际文件身份

| 文件 | 实际 SHA-256 |
|---|---|
| 外层 rc3-notes-local-acceptance.zip | `b431e5ce983fc242901f23c0079fe8e32a42c143cc6404bf5e1b683c6a9c0ef2` |
| 最终公开 deck.pptx | `7446e7b505139505bd8853b2e74a19eaa77d9f386f30a4871fffdd3871c06c45` |
| 内部原生 compiled/deck.pptx | `3d33cb9ab5955dd6ad9be88d05605832a9de5770c7826bc2892a3b16ca71a8b7` |
| 内层 deck-review-9f87f7c3.zip | `2407c21a188a52ce37dc019cca1f5cdf15fe9d363afddc81e88fda99679ee4df` |
| speaker-script.json | `a529072e1c9015e718fd6be887289ff09ddc43cfbee4c4f8713129a0a769775d` |
| speaker-script.txt | `f9f6df1db1d83bb27c7cf97a615240eddfd2aad47fdd38e83936798907f77705` |
| compile-input.json | `fc9cfddd34be85deedd65d48cfbd7e31da06b15b5053c2b0d21d42ecee5c2543` |

共检查目录 25 个文件。SHA256SUMS.json 覆盖其余 24 个文件；未自列自身属于正常自引用排除，本 reviewer 单独记录其实际 hash。manifest 列举的 14 个文件 hash/size 均吻合。外层归档完整匹配目录 25 个文件；内层导出归档的 15 个文件均与相应目录字节一致。两层 ZIP 及 PPTX CRC 检查无错误；无路径逃逸项。

## 逐页结果

| 实际 slide | 稳定 page_id | notes SHA-256 | 独立结果 |
|---|---|---|---|
| 1 | p-a | `1c46208e2f597902036ee14f8680b75eb9417ecdd10e7307bd6a108d817f3bbf` | 全文、连续空行、末尾 LF、双向关系与所有包内记录一致 |
| 2 | p-b | `f6e0594e3a7d0d3dd7d95b557753e7ccffc9ea477d5c9db31ae3ad1d82680f2f` | 全文、三处连续换行、末段、双向关系与所有包内记录一致 |
| 3 | p-c | `6e79cf6b1ba26f277f2c80d23203b1b8e935e2ee763b99ef3762ff3bc6e098cb` | 全文、限定、末段、双向关系与所有包内记录一致 |

每页恰有一个 notes body placeholder，反向关系准确指向对应 slide。speaker-script.txt 与 speaker-script.json 的有序 notes 投影字节相等。备注特有的首段/末段未混入 slide 可见文本。内部原生 PPTX 与公开净化 PPTX 的稳定页标、notes 全文、可见文本一致。

## 隐私与原件边界

- 内部原生 PPTX 实际 hash 与 manifest 的 original_sha256、internal-native-pptx.sha256.txt 一致。独立检查未修改该文件，也未执行会重新创建原件的构建流程。
- 公开 PPTX 有 47 个部分；无 docProps、comments、commentAuthors、embeddings、ActiveX/VBA 部分，无 external relationship；公开 XML/relations 及包内 JSON/TXT/HTML/SVG 中未命中本探针的本机绝对路径或认证字段模式。
- 包是公开合成三页，未包含运行 project、原始客户资料、prompt 或认证/服务状态。路径/字段扫描仅支持上述有限工程范围，不冒充真实客户资料的人工隐私审查。
- 包内“用户原注”为合成 Page notes 场景；它可以说明本组 notes 未被净化删掉，不能替代真实用户原稿、用户原文件的导入/保留验收。

## 桌面验收和明确未运行项

说明文件要求在实际交付应用记录名称/版本/OS/时间，逐页对照全文、54/120、45%、否定限定、连续空行、末段与页序，编辑 p-a 后另存副本并关闭重开，同时检查 p-b/p-c 无串页，保留原件。失败需要完整差异和截图。

回传表的 status 为 NOT_RUN，应用、版本、OS、tester、执行时间、逐页检查与编辑结果均为 null。full-notes-readback.json 的 desktop_notes_view、desktop_edit_save_reopen、human_acceptance 均为 NOT_RUN。delivery.json 的 professional_use/desktop_editing 为 not_evaluated，human_signoff=false，purpose=review；`professional.satisfied=true` 仅在 required=false 的政策场景内，不是人类认可。

本 reviewer 未运行桌面或人类检查。此包本身也未携带重排、拆合/删除、仅备注修改依赖/零新增图像调用的完整 raw；不能把静态包检查扩写为 AC-N02/N03 的动态通过结论。

## 待补项与证据边界

1. **EVID-P1-01｜缺 implementation Git 绑定。** 现有 build log、manifest、compile-input、delivery 和 readback 没有准确实现 Git SHA/tree 或实际 import source/package 安装身份。project revision `9f87f7c383724cdea2f5e0d13aae46ec` 不是代码 SHA。最终工程文档需提供独立的新 provenance/readback/reproduction 记录，绑定冻结修复代码、wheel/install/source 文件 hash；保留旧构建记录，不能倒写其构建身份。此项是证据缺项，不把它自动换算成原 ACCEPTANCE 的 F0–F3。
2. **渲染来源范围。** build-pack.py 在净化导出前渲染内部 compiled/deck.pptx，随后把这些图复制成 actual-render-*.png。本轮确认 native 与 public 可见文本及 notes 相同，但未对最终公开 PPTX 独立重渲染。已有图的真实来源应写为内部原生文件，不写成最终净化文件已重渲染；若最终文档要作后一种结论，需提供新实际渲染记录和最终文件 hash。

此阶段报告冻结在实际读取的文件 hash 上。初版 `27823…` 的代码审查缺陷及修复尚未由该报告复审；等待 root 提供新冻结代码和最终 docs/head 后继续文档/ledger audit。仅 RC3-02 范围，不能写成全部 RC3 完成。
