# RC3-02 文档草稿预检｜phase2

结论：本轮已独立核对现有 ca035 隔离安装再验证的代码来源、实际文件字节、notes 关系/全文以及最终公开文件渲染原件。活动文档仍标第三轮 review PENDING、专业 AC/CQ BLOCKED、桌面/人类 NOT_RUN；没有把历史混合测试或旧包构建倒签到当前版本。此次是草稿预检，不能作为代码 PASS、最终文档 PASS、原 AC/CQ 关闭或全部 RC3 完成。

## 固定读数与范围

最初实际读取的 45 份文档字节保存在 `read-docs/`，原路径/hash/size 见 `probe.json` 的 doc_inventory。其中 NOTES 为 `c643bd05e45ed46f97a040d24a445828c5d403bb9e445bf5726105715a311d12`，manifest 为 `6a27d917acb4c85de0b6333d792200ee7764fcaba5a015f0fadff1f52091bd28`，ledger 为 `069990f712d8e164a693be903b8ae6eee711b33202ff2b38aa0180c76889a826`。manifest 的 42 项复制文件及对应原件实际 hash/size 均匹配。

Owner 收到预检反馈后继续修改活动草稿。本 reviewer 另存三个新活动文档与特定补件到 `post-feedback-docs/`，具体新 hash/时间和 134 项原件/副本 hash 检查见该目录 observation.json。这是第二组实际观察，不覆盖第一组，不伪装成一个固定 Git 文档提交。

本 reviewer 不审读 live 产品源码以冒充固定代码、不运行 Owner 的再验证脚本、不重跑 broad suite、不改 Owner 文档/ledger/raw，不 commit/merge。新增 reviewer 文件均在独占目录。Python 使用被指定的 ca035 candidate 绝对解释器；源码/wheel/install 验证以字节读取和 Git 对象比较完成，额外模块来源观察使用 `-I -B`，未编译或修改项目。

## 独立 ca035 来源检查

| 身份 | 实际结果 |
|---|---|
| Git commit / tree | `ca0351d2397ba154e9f77363bd0f325629eb0ebd` / `05191deede70f26e661b28f4221c3c0d00ef2ecf`，从固定 snapshot 的 Git 对象核对 |
| 安装 manifest | `1085ec1051ca8d66e73d7fdacc51e3593425a05e2b7138a29d51afdd7b34925f` |
| 实际 wheel | `17a3bb5c40bdec788548fe17a3906e40524b41378f27d6ac77bc9c65bd543182` |
| source / wheel / installed | 246 份 package 文件逐字一致；源码记录逐文件与固定 Git committed bytes 相同 |
| 新 revalidation.json | `8e9d98d4d19ca305c4c473462750e46980fdd9beb5dc90194fccc4adb7a76e61` |
| actual-execution.log | `0f5fb6ebdd317eb072c359f8b4ee31df7456d828f168fee9fc00da15157fabc2` |
| controller-index.json | `0da55f60fd483a18e3aba884ffc18619992e95a8bd1abe738e2f04a0ca7b0b97` |

所有 controller 索引的现有 raw 文件 hash/size 均吻合。报告中的 7 个模块路径/hash 当前实际吻合；reviewer 新进程实际导入同样 7 个模块均来自 ca035 隔离 prefix，isolated_flag=1、dont_write_bytecode=true，读数见 independent-import-observation.json。没有借用活动 worktree 模块。

manifest 记录 activation=none、actual_home_modified=false；本 reviewer 未激活或操作实际 HOME。此处没有额外制造 HOME 的历史前后证明。

## 独立文件和渲染检查

- 新最终公开 PPTX 实际 SHA 为 `7446e7b505139505bd8853b2e74a19eaa77d9f386f30a4871fffdd3871c06c45`，与旧包逐字一致。reviewer 再次从 presentation 页序到 slide→notes→slide 双向关系独立回读，p-a/p-b/p-c 全文、空行、末尾 LF 与记录一致。
- 新 native 原件与旧 native 原件完整部分集合/每个 uncompressed part 字节一致。独立比较两个 ZIP 的全部不同字节，204 个差异均位于 local/central directory 时间戳字段，没有其他差异位置；记录见 native-zip-byte-difference.json。新 native 原始 hash 与最终 public hash保持区分。
- 新 raw final-public-render 三张 PNG 实际文件 hash、1601×900 尺寸及 RGBA 像素 hash 均与记录一致。revalidate.py 的实际读取脚本在 public_path 写入后调用 readback 和 `render_deck(public_path, .../final-public-actual-render)`；renderer_input 记录绑定该 final public PPTX。没有用旧 native 渲染原件充作新最终 public 渲染。
- reviewer 没有自行重跑 renderer，结论是独立核对现有实际执行链、原件及字节记录；不是新的视觉设计审查或桌面备注视图验证。
- phase1 的目录 25 文件及其 5 个外部构建/原生/归档记录目前仍与 phase1 原始 hash一致。旧包原件、原构建未冻结状态、旧 `0b0ed` 再验证均未被本 reviewer 覆写。

## 文档/台账边界

初始和补件观察的 ledger 都保持 37 AC、13 CQ，各 ID唯一且与 immutable 模板集合相同。与 ca035 代码 snapshot 的既有 ledger 相比，只改变 AC-N01–N04 和 CQ-06；全部原 capability_owner/execution_card 符合模板。四项 N 均由 T06/RC3-02 汇总、status=BLOCKED、signed_by=null，CQ-06 为 BLOCKED，release_conclusion=NOT_RUN。补件观察没有再修改 ledger。

NOTES/manifest 明确保留：

- `27823…` 两组独立 REQUEST_CHANGES 与反例；`0b0ed…` 第二轮失败、安装与原件。
- 1846/456 测试记录为 MIXED_LIVE_SOURCE、exact_head=false，不能绑定 `0b0ed` 或 `ca035`。历史 `0b0ed` 53 项 render 与当前 fixed snapshot 53 项 render 是不同原件。
- 合成权限、Review/native observation/费用只是 L1；固定实际 PPTX、回读、headless LO/PDF/PNG只支撑适用文件工程范围。
- 真实 Owner/受众、计时、professional approval、桌面 notes-view 和 edit-save-reopen仍 NOT_RUN；none/原注为合成场景，不伪造人类或原客户文件认可。
- 新 N08 首次前审缺 speech 或 page_copy/progression 时 pipeline 编译实际发生的观察被明确保留；后来正式补适用合成 L1 review 的状态与首次状态分开。文档称这是待处理的原生产准入集成边界，不能用文件工程观察把它写成 guard 已拒绝或全交付通过。本 reviewer 没有对该代码行为给 PASS或缺陷关闭判定。

## 预检问题与后续

**DOC-PF-01｜历史 `0b0ed` 再验证引用缺项，已在补件观察中关闭。** 最初 NOTES 叙述历史 final-public 再验证，但所读 manifest 没有准确定位其 controller / isolated-wheel-r4 revalidation。已通知 root/Owner。Owner 后续将四份历史原件按原路径/hash/bytes纳入 `historical-0b0ed-revalidation/`，NOTES明确链接 `cd002fabee44cc0caa13f575b2a546bff57210f8805c11db1c5a685c6a3a997a` 和历史 controller hash，并明确只归历史、不倒签旧构建或当前 source。reviewer 核对补件复制/raw均吻合；另外已独立核 0b0ed 的246 source记录与历史 Git对象、7模块hash及核心PPTX/渲染原件hash，见 historical-and-originals-probe.json。

**最终文档审查仍 pending。** 补件草稿已加入 fixed ca035 unit1851/render53、N08两轨与 current installed再验证原件，但当前 code/reg round3尚未出最终结论；Owner也尚未冻结最终 docs commit。因此这里不颁发最终文档 PASS。root提供新准确 final docs SHA/tree后，需要重新核对其准确内容、影响与 evidence refs/ledger，再完成终审。现有预检原件保持独立不改。
