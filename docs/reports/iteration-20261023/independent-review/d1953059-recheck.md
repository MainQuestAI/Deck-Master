# d1953059 最终候选独立只读复核

结论：原 R1–R6 的已验证修复保持，旧 write_only 完成标题兼容项已通过源码和安装复跑；但补查发现一个确认的 P2 主动作导航缺陷，暂不能宣称本次用户阅读出口全部完成。固定 d195 检查已结束，可以修复后提交新固定身份复核。

## 固定身份与差异

源码 HEAD `d1953059bfd3553f2b66eada4e82754d39077428`，tree `60ed0d4b3458b5a6069716693cbd954e96e26190`，工作树干净。与 `568f0dda1fd0d03c7be6ac999d53d66a4da16b87` 比较，产品代码仅 current_work.py 的完成标题按 plan_only/write_only/speech_only/content_full 恢复名称；另两文件是报告与修复说明。没有更改旧测试断言，R1–R6 相关其余代码未变。

`/workspace/handoff/review-final-release/release.json` 的 source_sha=d195、source_dirty=false；wheel SHA256 为 `6a0736556416d78e525becf27b7be472faec6a543db163540455e082112e91b7`。独立核对 manifest、wheel 与安装文件字节，285 个源码包文件匹配。以 `/workspace/deck-installed/bin/python -I` 执行的实际 deck_master 模块全部来自 site-packages，非源码影子导入。证据 installed.log。

## 确认缺陷

### R7 / P2：「阅读本次交付」未导航至交付文件

位置：`src/deck_master/current_work.py:111` 仅返回 surface=runs；`src/deck_master/resources/static/v2/current-work.js:18` 仅执行 app.go({surface:next.surface})；`src/deck_master/resources/static/v2/views.js:103` 在无 runs_area 时默认 tasks。

触发：已有具备交付资格的完整 deck，从默认 overview 点击「阅读本次交付」。使用现有 `_passing_deck` 夹具与真实 HTTP/Chromium，在 `/studio/`、`/v2/` 分别独立复现。

实际：两端 URL 只变为 surface=runs，没有 area=files；`#runs-tasks` 可见，`#runs-files` 隐藏。任务与交付的子区中存在文件按钮，用户必须自行再切换。证据：test_navigation.py、navigation.log、navigation-tmp/test_read_delivery_opens_files0/navigation.json 与 files1/navigation.json。两条交付断言均失败。这不是 delivery_eligibility 判错，不是文件丢失或授权绕过，而是新完成主动作没有完成其承诺的阅读导航；保留旧 runs 子区还可能让结果取决于之前浏览位置。

建议：由后端统一 next 返回明确导航对象（包含 runs/files、清除不适用的旧 task 等路由身份），组件消费该对象；覆盖首次进入与已记忆其他子区两端测试。不要在前端重新推导交付资格。

### 内容主动作补查：稿件仍可读，但不是直接呈现

write_only 完成后的「阅读本次内容」在 studio 默认进入 content/方案概览；该导入稿夹具没有完整 Plan，屏幕显示“尚未记录完整内容计划”，而非正文。随后点击「逐页编辑与顺序」及「打开内容页 先核对实际稿件」，可以进入页面内容并看到正文“先核对真实稿件，再确认范围与下一步。”（content-path.log，1 passed）。所以不报告“稿件不可达”，但直接阅读完成稿的动作语义仍不充分；建议与 R7 同时显式定义按 content_intent、scope 和现存产物的阅读目的地。不能让 write_only/speech_only 入口只停在可能为空的方案概览。本轮未把该 studio 路径实证扩展成所有内容类型/所有前端都失败的结论。

初始 test_navigation.py 的第三条期望点击后立即出现页面内容，因此失败；原因是页面区域不存在，不是将标题“实际稿件”误写为正文“真实稿件”。初始失败日志保留，补充 test_content_path.py 才证明完整可达路径。

## 保持成立的修复与实际复跑

沿用同一 reviewer 的 `/workspace/reviewer-568f/report.md` 独立证据，并验证有关实现没有变化：

- R1：完整冻结 Plan 范围，dispatch/direct/start/accept 共用 guard；start/accept 后收窄 scope 被拒绝。
- R2：outline 严格 Narrative/Plan 版本失效，不沿用稿件语义等价。
- R3：原 ready checkpoint 优先恢复，即使另有 awaiting Task 也不再次执行；合成 session 计数一次。
- R4：交付状态复用同快照纯读权威事实；没有无参数重读或项目字节变化。这里的状态修复成立，但本轮 R7 是其阅读出口额外遗漏。
- R5：两端控制刷新只重绑 current_work；编辑器同一 DOM、未提交草稿、固定 revision 和 Page refs 保持。
- R6：正常完成与恢复共用 outline subject gate，恢复不再错误返回 manuscript gate。

本轮 source.log：4 passed；installed.log：同四项 4 passed。包含原旧 write_only 完成标题测试、完整交付纯读测试、studio/v2 固定产物控制刷新测试。补查真实浏览器交付两项确认失败，内容后续可达一项通过。没有以已有 happy-path 代替新增导航反例。

作者 final-review-source.log、final-review-installed.log 在本报告检查时均尚未显示最终 pytest 汇总（已到 84% 之后），本报告不把它们计为通过；应由作者最终核验完整日志及退出码。

## 审查边界

本轮为同一原生子代理工程复核，不是外部独立环境审稿或真实内容模型审稿。权威 DOCX 在初轮已完整读取 1213 行，本轮沿该规范与原报告，仅复核固定差异、身份和受影响行为，没有重跑全量或重新读取未变方案。没有修改仓库、提交、安装环境或权限配置；临时反例及报告在 reviewer-d195 下。

真实 native initialize、真实 Host 自动交接/审稿修复闭环、视觉像素能力、匿名好坏稿与方法 A/B/C 效果、真人理解观察仍 not_run；既有 CODEX_HOME 初始化限制未重试。机制、合成 session 和浏览器结果不能替代这些效果验收。撤回/并发/历史组合没有穷举。无待审批动作、无被拒绝操作、无不确定外部写入。
