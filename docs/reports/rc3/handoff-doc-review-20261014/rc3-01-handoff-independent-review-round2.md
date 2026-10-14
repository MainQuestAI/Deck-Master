# RC3-01 最终文档与证据独立复审：第二轮

结论：**PASS（文档/证据工程 delta 范围）**。F-DOC-01 六处哈希算法误标已修复；第一轮其他已核验范围保持成立。没有剩余阻塞 finding。当前最终文档 head 的七项CI仍待root提交推送后核验，本报告不替代CI、E1效果或RC3完整交付结论。

审查者：`/root/rc3_01_handoff_review`。固定产品core HEAD `cc6150da513ce38060b0a8ad045ea5159a56cae6`；文档工作树尚未commit。未参与产品/受审文档实现，仅写这两份独立报告。第一轮 REQUEST_CHANGES 原件 `rc3-01-handoff-independent-review.md` 保持不改，SHA `7cb1d9c734344417d2a202779392b49eb86fb601851776e4a0aed2aed1c866ed`。

## F-DOC-01 关闭依据

逐一实际读取AC-B02、M01–M05的六个 `input_hashes[0]`。现在每项ref均明确为 `B supplemental installation manifest (candidate-01-s01-b/manifest.json)`，sha256为64位 `475e9c6355cde08f157446061b78782dff4135718f53da710a30f55707a12d63`。该值等于当前实际B安装manifest原字节SHA-256，HANDOFF也保留正确40位source commit与tree身份；没有把commit伪装成字节摘要。

递归检查最终ledger所有 `sha256` 字段均为64位小写hex。最终ledger SHA `2fbf0c17359436dc4b00b1578d3084891c78797c7f4d3be9e8853a6427abe780`。修复仅六项ref与hash，wheel、output snapshots、状态和限定叙述不变。相对固定HEAD，仍仅本卡7 AC/3 CQ变化；其余30 AC/10 CQ及所有global字段逐项一致，release_conclusion=NOT_RUN。本卡7 AC的signed_by保持null。

第一轮一句“AC signed_by全部原null保持”范围过宽，是审查报告措辞错误，不是产品改动：原AC-B01已有 `Codex / RC3 integration (engineering evidence)`，实际未变；null结论仅适用于本卡七条。这里据实更正，不修改第一轮已冻结原报告，也不把该纠正伪装成owner产品修复。

## 原件及工程出口重验

再次逐文件读取153份 source/公开copy/manifest hash：115 native原件6,479,571 bytes与38 anchor原件912,285 bytes全部相同，两manifest SHA分别仍为 `dd3c276256a8eed0059f1f572643805043f3689c5b4eb7df6ff767432c89a0aa` / `f0be87351a3c8a38823b9a25820e5deea0105a3b2424a0c3e5d23b865dcdecec`。未重写原稿、原拒绝、原review、原失败或历史空白。当前METHODS SHA `b9b4de1679a5a390d4e447d3129457c8f85a019f632448f5435ab1b3d7ffaf63`、HANDOFF SHA `1874e4b8d89d4f40359967c071986fbcb2822774177a0a4db3fe0f7bf84fa517`保持，导航链接仍有效。

四fresh真实completed与正式SDK accepted，三个合格owner工程快照，B Q1/Q2内容gate pass，Q1-A新F2/missing page_copy/无owner/无第二反馈仍准确。两隔离安装source/tree/wheel及244/245源码包安装字节、四共通core、新旧各臂Skill字节一致的第一轮实核未被此次纯ledger修正影响。两轮S01 REQUEST_CHANGES、最后PASS、162targeted和1742+离线5覆盖、adapter工程PASS及原冻结E1/污染/机械纠正限制全部保留。

允许root将受审文档及这些公开合成原字节纳入最终PR，然后验证精确新head的七项CI。后序卡可采用B的两份当前完整稿作为固定内容输入；视觉扩展授权、人类Owner/受众、实际计时、桌面文件验收和剩余原AC/CQ仍按原规划待执行。此次未新增图像/输出授权、未激活真实HOME、未宣称整套RC3 ready。
