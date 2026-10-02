# U06：最终候选与真实材料验收

2026-10-02。U00–U05 已依次合入 PR83–89，主线基线 `b61c4c9b9ea1ddddb5a9e87499c1bc0808d49df0`。本轮继续修复 U06：生产启动路径的 250 ms 刷新门已通过，真实材料已到位并完成 30 页正文与两轮网页编辑。完整原生制作及本机人工项仍未通过，U06 不标记关闭。

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

当前 `continue` 正确返回 `awaiting_host`，等待第一页 `generation.v1` 蓝图。云端没有当前用户的 Codex Desktop `sessions` 原生事件库；现有 `codex-session-image.v1` 采集器必须从该库核对真实调用及输出，不能用自写记录替代。尚未发生原生模型调用，不能登记 consumed、生成候选或补造质量通过。

## 剩余项与处理顺序

1. 在可读取真实 Codex Desktop 调用记录的环境，用已准备项目继续第一页蓝图，再完成 SVG/PPT、两轮实际制作变更与候选采用、质量记录；原始材料无需重新索取。
2. 实际 HOME 迁移、macOS 原生目录选择、真人 30 秒理解观察分别由对应本机与真人产生证据。

新增能力缺口的优化建议：HTML 原生导入应保留原文件 hash、可见文本/表格/定位与缺失图片说明，不执行脚本、不自动拉取外部资源；若要求云端原生制作，需新增能绑定真实工具调用与输出的可信采集适配器，不能降低现有原生证据门。这些能力没有在本轮被假定已经实现。

## 分支与 worktree

已清理 8 个已合并本地分支、7 个已合并远程分支；删除前核对 main 祖先并保留 `refs/archive/cleanup-20261002/` 恢复引用，远程删除绑定原 SHA。只有活动 U06 本地分支和一个 worktree；PR34/40/66 与其他未合并独立分支保留。[原清理证据](evidence/u06/branch-cleanup.json)。未删除用户材料、项目或历史产物。
