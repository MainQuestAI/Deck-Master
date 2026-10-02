# U06：最终候选与真实材料验收

2026-10-02。U00–U05 已依次合入 PR83–89，主线基线 `b61c4c9b9ea1ddddb5a9e87499c1bc0808d49df0`。本机已完成 30 页真实原生生图、采集、SVG、整稿 PPT 和逐页实际渲染检查；三用途导出及 PPTX handoff-check 通过工程门。新增入口连接修复的安装包已通过同包全量、压力与回退复验。两轮制作候选均已准备，尚待用户选定采用；macOS 原生目录选择和真人观察未通过，U06 保持 open。

用户反馈更新（2026-10-02）：用户确认 30 页的基本内容密度与内容质量够用，整体内容达到验收节点；部分图标精细度需优化，但明确不构成当前程序运行的阻碍。已将内容认可与非阻塞图标改进分别保存为当前真实项目的版本绑定意见，回读确认 Page、产物、候选与任务不变，continue 仍为 ready_for_export。此反馈记录内容验收范围，不代替两轮候选采用或本机人工测试的事实。图标改进见[非阻塞后续建议](ICON-QUALITY-FOLLOWUP.md)，尚未实施。

## 冻结候选

源提交 `64f6063bab1469daea347777ad3c2b86be450d6f`，release `64f6063bab14-a29d0d9c016f`。

- wheel SHA-256：`a29d0d9c016f07786faa6d29e96edc68aa38de66bd79294439525ce2c773887d`。
- sdist SHA-256：`87e5f5e28bfb9dbf08e05f55826d7920794fbe9334ff8be9661d99f902ee860d`。
- 45 个 v2 静态资源；sdist 重建运行时代码/资源与 wheel 一致。使用隔离前缀，未注册真实 Host、未替换用户默认安装。
- 固定源码通过 1024 单元、30 必跑浏览器、31 真实渲染；安装包另通过 30 浏览器及 24 步 CLI/HTTP/装配/恢复/导出验证。
- 源提交的 [CI run 36959060140](https://github.com/MainQuestAI/Deck-Master/actions/runs/36959060140) 七组全部成功，覆盖 Python 3.11/3.12 × Node 22/24、浏览器及渲染。

## 刷新修复与测量范围

原包将 1500 个候选及 1500 个冻结请求的完整对象挤入页面/任务缓存，已经通过独立轻量元数据缓存修复。本轮继续减少重复工作：

1. 同一请求使用不跟随符号链接的目录句柄读取对象状态，结束时释放。每个对象仍检查设备、inode、长度、mtime、ctime；低文件描述符上限环境回到逐路径检查。
2. 最多保留四个已编码总览。每次先读取并核对实际 Document，再逐个检查此前读取对象的文件签名；变化或读失败即重建。运行任务跨过 30 分钟时单独失效，不以缓存掩盖超时。
3. HTTP 直接发送已验证的 JSON 字节，避免缓存命中后解码再编码。Python 调用仍返回独立对象；外部修改返回值不会污染缓存。
4. 小 JSON 只缓存已核验的不可变字节，有大小和数量上限，每次重新检查路径与文件身份。后台任务替换优先匹配已读取的内容寻址对象，同一工作单响应复用相同派发快照；非规范历史对象保留原查找路径。

回归覆盖热缓存后损坏/修复、恢复旧 mtime 的同长度篡改、符号链接祖先、目录替换、异常释放句柄、返回对象隔离、实时超时与固定历史。未修改取消/迟到、版本冲突或提交收据规则。

**测量方式修正有单独记录，不能直接把不同方式的数字当成纯代码加速比。** 正式 CLI 的 `view --open` 本来就使用独立 Web 服务进程；旧压力脚本把 Web 与后台 Host 更新放在同一 Python 进程，产生额外 GIL 争用。本轮默认通过同一 `ensure_service` 启动真实独立服务，记录 PID/build_id；100 次请求、5 次暖身、后台实际领取/取消、完整 JSON 接收解析、250 ms 门槛和失败退出码全部保留。`--server-mode in-process` 仍可运行附加嵌入压力；最终安装包另测 100 次，p95 330.66 ms，**未通过且未冒称通过**。冻结前诊断 442.2 ms 也保留。正式 CLI 的独立服务路径结论不扩展为同进程嵌入性能承诺。

前份已标中止的 `26703ed` 长跑在 SIGINT 后留下活动进程，本轮按确切命令和进程组识别并终止；原始中间样本保留，不计为通过。之后的新包正式采样使用原工厂状态的新副本，无该残留进程。一次源码测试在运行期间遇到代码版本变化，独立服务构建身份不匹配而失败；冻结后全量复验通过，不扩大启动超时或删除断言。

## 同包结果

| 项目 | 结果 |
|---|---|
| 包、安装、浏览器、渲染 | 通过；45 个 UI 资源、1024/30/31 源码验证及安装包 30 浏览器 |
| 安装 CLI/HTTP 与导出 | 通过；24 步完整验证，三用途导出、固定历史下载及真实装配/恢复 |
| 300×5×3 summary | 通过；生产独立服务，100 次请求，p50 73.49 ms / p95 199.18 ms / p99 241.61 ms；12 次后台真实领取/取消，0 错误 |
| 六次暖首屏 | 通过；0.958–1.102 s，桌面两尺寸各三次；计时截止可见图片与选择反馈，随后另验保存 ACK |
| 20 分钟正式长跑 | 通过；1200.004 s，中段/末段各 30 样本，heap median 增幅 0.68%（上限 20%）；图像池 6/2/60/4 门内，0 前端错误，60 次实际后台领取/取消 |
| 隔离完整回退 | 通过；旧包 22fc972→本候选→停止服务→回退旧包读取→恢复候选；109 个对象、4 个候选及业务指针不变 |

样本仍是明确合成的 `w01-pressure.v1`，seed 20260930：300 页、1500 候选、4500 Attempt。原 manifest SHA-256 `0bf7f6c8584c1790eb4516d23c57d34e8cad1606b5e75ecc2f10f03ae3b56302`，原工厂 revision `df7cf8f1e30748d88eb5afeb8b8b7e00`，20113 个对象。各正式组在新副本测试，不修改原件，不重新生成候选/尝试以补齐失败数据。零模型调用，不能代替真实专业制作。

[包与 CI](evidence/u06-optimized/release-proof.json) · [单元](evidence/u06-optimized/unit.log) · [浏览器](evidence/u06-optimized/browser.log) · [渲染](evidence/u06-optimized/render.log) · [安装](evidence/u06-optimized/installed-checks.json) · [三用途下载](evidence/u06-optimized/offline-checks.json) · [100 次原始采样](evidence/u06-optimized/summary-measurements.json) · [六次首屏](evidence/u06-optimized/warm-checks.json) · [回退](evidence/u06-optimized/rollback-checks.json) · [最终包同进程未通过](evidence/u06-optimized/inprocess-final-measurements.json) · [冻结前诊断](evidence/u06-optimized/inprocess-diagnostic.json) · [残留进程处理](evidence/u06-optimized/orphan-cleanup.json)。

[完整 20 分钟结论](evidence/u06-optimized/long-checks.json) · [120 次采样](evidence/u06-optimized/long-samples.jsonl) · [最后窗口](evidence/u06-optimized/long-final-window.png) · [原始样本保留](evidence/u06-optimized/original-fixture-preserved.json)。

旧候选 `3a6d41b` 的全部证据仍在 [evidence/u06](evidence/u06/release-proof.json)，包括旧速度失败和旧 20 分钟结果；不覆盖或混充新候选证据。旧包拒绝未来 writer 的[合成负向检查](evidence/u06/old-writer-guard.json)仅证明拒绝不兼容格式，不冒称已验证真实 HOME 迁移。

## 用户材料与真实层边界

用户已提供并明确选定真实 HTML 报告。原件保留并记录 SHA-256；当前导入器不原生支持 HTML，因此显式提取可见文字为 UTF-8 文本，保留原文顺序、行定位和派生对应关系。24 个 section、177 个标题；一张重复引用的人物照片未随文件提供，不补造。原文、项目、正文、截图及私密导出均留在工作区，未提交仓库。

本候选已实际完成：

- 30 页有来源定位的正文和六章 ContentPlan，经 `compose.v1` 工作单真实领取/采用；原报告的建议目标、待确认事实与后续扩展仍区分表达。
- 总览/内容面 × 桌面/窄屏四组真实浏览器检查，无整页溢出、无前端异常；浏览前后业务指针一致。
- 两轮实际网页正文编辑：第 24 页补齐指标基线与测量窗口，第 26 页补齐五个工作日报价与费用分类。每轮只改目标页，其余 29 页、原对象、材料和任务不变；核心收据已提交，重开后正文一致。
- 导出不完整正文阅读包与内部工程恢复包，并在独立目录恢复核对 30 页及内嵌原始来源可读、指针不变；没有冒称 PPT、图稿、实际 HOME 迁移或 delivery 已通过。

[材料与 UI 脱敏结论](evidence/u06-optimized/real-material-checks.json) · [两轮手工正文编辑](evidence/u06-optimized/real-manual-edit-checks.json)。这些是真实材料上的正文与 UI 证据，**不是两轮原生 Host 生图/候选采用/质量验收**。

云端交接时 `continue` 正确返回 `awaiting_host`，等待第一页 `generation.v1` 蓝图。云端没有当前用户的 Codex Desktop `sessions` 原生事件库；现有 `codex-session-image.v1` 采集器必须从该库核对真实调用及输出，不能用自写记录替代。该云端阶段尚未发生原生模型调用，未登记 consumed 或补造质量通过；后续本机进展见下节。

## 剩余项与处理顺序

1. 在可读取真实 Codex Desktop 调用记录的环境，用已准备项目继续第一页蓝图，再完成 SVG/PPT、两轮实际制作变更与候选采用、质量记录；原始材料无需重新索取。
2. 实际 HOME 迁移、macOS 原生目录选择、真人 30 秒理解观察分别由对应本机与真人产生证据。

新增能力缺口的优化建议：HTML 原生导入应保留原文件 hash、可见文本/表格/定位与缺失图片说明，不执行脚本、不自动拉取外部资源；若要求云端原生制作，需新增能绑定真实工具调用与输出的可信采集适配器，不能降低现有原生证据门。这些能力没有在本轮被假定已经实现。

## 分支与 worktree

已清理 8 个已合并本地分支、7 个已合并远程分支；删除前核对 main 祖先并保留 `refs/archive/cleanup-20261002/` 恢复引用，远程删除绑定原 SHA。只有活动 U06 本地分支和一个 worktree；PR34/40/66 与其他未合并独立分支保留。[原清理证据](evidence/u06/branch-cleanup.json)。未删除用户材料、项目或历史产物。

## 前次本机接续记录（2026-10-02，6/30，历史快照）

交接包六个文件及内部工程 ZIP 校验通过；恢复到仓库外新目录，保留隐藏工程对象和30页历史。PR90 head `e83cf790` 与交接一致；运行时仍为冻结候选 `64f6063bab14-a29d0d9c016f`，本次没有改核心代码。

实际使用 Homebrew Python 3.12 创建安装候选，候选真实编译/渲染探针通过，再对真实 HOME 激活。compose/compile/render/view 均 ready，CLI 模块与公开 Skill 指向同一发布版。原 legacy companion 已备份，19个准确匹配旧链接被迁移，第三方条目保留。此前没有可回退的 managed release（previous=null），因此这里只确认实际迁移与激活，不把旧目录备份称为完整二进制回退验收。PATH 的 uv Python 3.12 虚拟环境创建曾因 `/install` 标准库定位失败；未改该全局 Python。

- p01–p06 各完成一次真实 ImageGen、冻结请求、Attempt、原生采集、consumed 结算及采用；六条记录均为 `tool_observed`，输入比较 `match`，原生图片字节与采用蓝图一致。费用/token 为 not_reported，model/seed 未擅自推断。
- 六页均完成原生 SVG、正式解析/字体检查、实际 SVG 渲染与 page_visual 三维 Host 自审。p04图标缺失、p06窄栏溢出真实记录为 must_fix，使用新SVG、新预览及 replaces 关闭；不能把两次返修当成 U06 所需的两轮候选制作/采用验收。
- 明确视觉/内容修正：p01装饰照片改为可编辑山形轮廓；p04删除两个没有业务内容的生成空框，保留四渠道六个编号；p06按报告L39纠正六步分组。原始生图不改写。这些为 Host 自审，不是独立或客户认可。
- p01额外通过同一安装核心的单页真实 PPT 编译、LibreOffice 渲染和文字回读，实际打开渲染检查；原生文字/形状可编辑，无整页图片。这是独立单页诊断，不写入项目整套 PPT 输出，也不冒称已完成30页交付。

[本机脱敏核对结果](evidence/u06-local/progress.json)。原材料、提示词、原始图片、SVG、项目、调用原生日志及单页诊断文件均留本机私密目录，未提交仓库。

下一工作单是 p07 blueprint，额度仍 reserved，尚未 begin；不存在未结算的本轮生图。p07–p30、两轮实际制作候选/采用、整套PPT最终六维审查、macOS目录选择、真人30秒观察及delivery/handoff-check仍未完成。真人观察已向用户提出，尚未收到结果；这不构成其余页面制作的技术阻碍。U06继续open。

## 最新本机结果（2026-10-02，30/30，U06 open）

真实项目始终使用 `64f6063bab14-a29d0d9c016f`，与公开 Host Skill 一致；原件、调用事件库、图片、工程历史和生产产物均留在仓库外。p01–p30 逐页按真实工作单完成，一共 30 次真实 ImageGen：原生采集均为 `tool_observed`、冻结输入比较均为 `match`、Attempt 均 consumed，原始图片 hash 与采用蓝图完全一致。未手写调用记录，费用/token 仍为 not_reported，model/seed 未推断。

30 页原生 SVG、字体/解析、实际预览和三维 page_visual 自审已完成；11 个真实 must_fix 通过新 SVG、新预览及 replaces 关闭。保留原始生成图，修正生成错误、编号/百分比换行、图标和箭头；不把返修计作候选采用回合。全套 PPT 已实际编译并逐页打开 LibreOffice 渲染：1687 个原生形状、0 张栅格图片，正文/标签回读无缺失，私密路径/执行标识检查无命中。最终六维记录为 `host_self`、`independence_confirmed=false`，不冒称独立专业或客户验收。

`continue` 当前返回 `ready_for_export`、无待执行 Host 任务。review、engineering、delivery 三用途导出成功；review/delivery 的实际导出 PPTX 均经 `handoff-check --file <PPTX>` 返回 verified，30 页、render/review pass、gaps=[]、evidence_level=engineering。工程门允许导出不等于 U06 人工项或客户交付认可。该 CLI 没有交接说明中提及的 final-readiness 命令，采用现行 continue 与 handoff-check，不以不存在的命令推断通过。

实际整稿 engineering ZIP 已在新目录解压恢复，1123 个不可变对象逐个核对 SHA-256；30 页的 Page/原图/SVG/预览及整稿输出与原项目一致，原项目指针不变。

两轮实际制作试作已完成：p06 调整窄栏换行，p29 调整字号/换行消除单字尾行，均保留正文和图形内容。各自真实 task/changes/candidate 返回 candidate_ready，当前 Page 和整稿槽保持不变，试作没有额外模型调用。已向用户展示两处候选并请求选择；尚未 adopt，后续采用、实际预览、逐页质量及重新装配仍待完成。不能把“候选已返回”写成“两轮采用已验收”。

实际总览仍显示 27 页原图依据变化：26 页在 SVG 重建时增加可见标签，p06 另按来源修正六步正文；原图 generated_from_page 绑定保留。30 页 SVG 的显式 dependencies 为空，总览保守显示待核实；derived_from、原图、SVG 及实际 PPT 对照已检查。最终质量/导出工程门通过与这些历史依据提示分别记录，不冒称总览全部层均 current。

macOS 原生目录选择实际点击“浏览文件夹”后返回 local action failed，未获得成功选择目录的证据。真人 30 秒理解观察已打开当前真实项目并再次请求反馈，尚未收到结果。实际 HOME 迁移沿用前次真实完成记录；其 previous=null，不能把旧 companion 备份称为完整 HOME 二进制回退。

[30 页本机脱敏证据及准确剩余项](evidence/u06-local/progress.json)。

## 新连接修复包的同包复验

冻结源码 `d39a6361cc68ab259976b93fbca880e308deaf9d`，release `d39a6361cc68-3fbdf9d15304`。wheel SHA-256 `3fbdf9d15304508660cc62ee768a79d7c438c72766898f63aee93d2cf9ae9a5a`；sdist SHA-256 `09371f5f03f66770d4aec37c4a1dc5b66cd89d5894872f5a94a8e29b6028a64d`。干净 git archive 构建，45 个 UI 资源、sdist/wheel 运行时一致，在隔离非 editable 环境复验；未替换真实生产项目绑定运行时。

连续更新与刷新时，Python 3.11/3.12 默认五个排队连接不足以容纳图片请求与入口脚本的重叠，实际出现 ERR_CONNECTION_RESET。独立 TCP 回归在暂停 accept 的情况下排入 12 个真实连接；标准 ThreadingHTTPServer 负向对照出现六个连接错误，保留失败。修复只为共享 loopback server 增加 backlog，不改变图像池、CAS、取消迟到、质量或速度门；修复安装包 20 次新浏览器上下文更新/重开均成功、入口脚本零 reset。合法取消缩略图请求仍单独记录。

| 验证 | 新包结果 |
|---|---|
| 本地源码全量 | Python 3.12：1025 单元、30 必跑浏览器、31 真实渲染通过 |
| 隔离安装验收 | 安装包 30 浏览器及 24 步 CLI/HTTP/装配/恢复/三用途导出通过 |
| 100 次生产独立服务摘要 | p50 31.68 ms / p95 78.01 ms / p99 81.52 ms；7 次实际后台领取/取消，250 ms 门通过 |
| 附加同进程嵌入复测 | 本机同包 100 次，p50 33.85 ms / p95 246.19 ms / p99 269.14 ms，按 p95≤250 ms 门通过；旧 330.66 ms 失败保留，环境不同不作纯代码提速比较 |
| 六次暖首屏 | 两尺寸各三次，0.356–0.403 s，原 2 s 门通过 |
| 正式 20 分钟压力 | 1200.003 s；中段/末段各 30 样本；heap median 增幅 0.568% ≤20%；图像池 6/2/60/4 门内、0 前端错误、60 次后台实际领取/取消 |
| 隔离完整回退 | 已验 64f6063→d39a636→停止服务→回退读取→恢复 d39a636；109 个对象、4 个候选及业务指针不变，真实 HOME 未受该演练影响 |

压力组均来自原合成工厂 checkpoint 的新副本：300 页、1500 候选、4500 Attempt，0 模型调用；保留 manifest、候选、Attempt 和对象字节，没有重新生成补齐失败。旧同进程嵌入 p95 330.66 ms 未通过仍保留；本机新包另行按原 100 次/p95 门复测通过，两次环境不同，不将变化解释为连接修复的纯代码性能收益。额外调用旧 w04_gallery 驱动曾等待已退休的 gallery-card 而超时；采用冻结包内现行 w04_pressure 对同样六次暖首屏与原门槛验证。首次并行 sdist 构建出现五个 setup error，随后隔离安装组和完整 1025 单元复验通过；不隐藏初次失败。

[新包摘要](evidence/u06-local-fixed/release-proof.json) · [单元](evidence/u06-local-fixed/unit.log) · [浏览器](evidence/u06-local-fixed/browser.log) · [渲染](evidence/u06-local-fixed/render.log) · [安装](evidence/u06-local-fixed/installed-checks.json) · [入口重开](evidence/u06-local-fixed/reload-checks.json) · [TCP 负向对照](evidence/u06-local-fixed/backlog-baseline-negative.log) · [100 次采样](evidence/u06-local-fixed/summary-measurements.json) · [六次首屏](evidence/u06-local-fixed/warm-checks.json) · [正式长跑](evidence/u06-local-fixed/long-checks.json) · [原始长跑采样](evidence/u06-local-fixed/long-samples.jsonl) · [回退](evidence/u06-local-fixed/rollback-checks.json) · [保留的失败](evidence/u06-local-fixed/retained-failures.json)。

[附加同进程原始复测](evidence/u06-local-fixed/inprocess-measurements.json)。文档/证据提交 `3309499` 的 [CI run 36980776615](https://github.com/MainQuestAI/Deck-Master/actions/runs/36980776615) 七组通过，覆盖 Python 3.11/3.12 × Node 22/24、必跑浏览器/安装包 UI、真实渲染及汇总；相对冻结源码 d39a636 只有文档/证据变更。后续 head 的 CI 以 PR Checks 为准。
