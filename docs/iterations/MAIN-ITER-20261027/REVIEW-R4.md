# PR #215 综合复审修复 · R4

固定 main 基线 `62dfcfc5637f0bee2358074c4458047689dd5299`；本轮审查 head `9c373d86592079d96506ca675c4d3f0f1eb8147a`。源码修复提交为 `853b56c40653655db6f63d220deb20d46ec51621`，专项检查已通过。最终 head 仍须在文档提交后冻结；该源码提交不是最终候选验收身份。

## 审查合并与明确裁决

| 审查项 | 处置 |
|---|---|
| R3 恢复文件／完整请求容量边界 | Pro 与本机结论一致，可以关闭；保留现有容量、旧核回退及实际字节边界回归。 |
| R3 三个入口模块失败恢复 | Pro 与本机结论一致，可以关闭；保留受保护整页重载和旧请求隔离，不返工。 |
| 新确认：不可导入内容仍允许保管离开 | P2，已实施并通过专项回归；最终新 head 门禁待执行。独立于已关闭的容量问题。 |
| Pro 未独立验收 R3 总包 | 证据覆盖边界。本机重核包 SHA、20,094,224字节及CRC一致；新 head 仍须重新构包。 |

用户提供的 Pro 审查原文 SHA256 为 `1903f27eaf44e1655fc98a97fb823c5bcdc43d4fc43c4b7d161ba3b2acc83fd0`，其结论绑定 `9c373d86`。原文、来源清单和本机独立反例在 R4 交付证据中分别保留；外部评审的通过结论不替代未覆盖反例的处置。

两次真实 Chromium 反例均通过实际文本框输入 `/help`，在保存断线与持续 quota 下下载995字节恢复文件、确认保管并关闭成功；同项目产品导入返回422，字段为 `draft/content/text`。两稿、原待核实请求及摘要仍在文件中，不能描述为已证明字节删除。根因是下载资格只检查容量与摘要，而导入还执行现有 `_portable` 内容限制。

老板已明确选择：**保留后端限制，补齐前端检查**。本轮不放宽路径形态自由文本、不新增HTTP API、Schema或能力字段，也不修改普通保存规则。

## 已实施内容

- 当前 `draft` 和完整 `pending_save` 下载快照都经过小型本地检查，包括嵌套对象、数组和payload；检查在摘要、下载和授予保管资格之前完成。
- 保留后端八项禁用键、大小写及前缀语义。Windows样式检查仅迭代前四个Unicode字符，避免UTF-16截断差异；没有新增深度阈值、API、Schema或后端政策。
- 拒绝内容不会触发下载，旧下载／保管资格清空，明确提示当前内容不能通过导入；两稿、原请求、身份和保存状态保持。离线与quota下无需HTTP预检。
- 新回归通过实际文本框覆盖两稿／仅当前／仅pending三类反例；补充资格撤销、真实journal冲突造成的pending变化、readonly缓冲、离线、关闭／Escape／前后退／焦点／beforeunload。结构向量比较后端与JS，未用修改编辑器对象替代真实正文输入。
- 健康中文／emoji及允许的近似路径文本完成实际下载、确认和产品导入，核对两稿、摘要、原请求及零自动重发。新测试文件已纳入正式installed入口。

## 专项结果与保留失败

以下是本轮实际执行的源码检查，不代替最终head门禁；命令省略本机解释器绝对路径和日志输出路径。

| 检查 | 命令／证据 | 实际结果 |
|---|---|---|
| 产品RED | `python -m pytest -q tests/rebuild/test_main_iteration_portable_browser.py -k test_unimportable_content_never_grants_recovery_custody --require-browser`；`portable-red-v2.xml`／`.log` | 旧产品9c373d86下3项均因实际下载了不可导入文件而失败。 |
| 新专项GREEN | `python -m pytest -q tests/rebuild/test_main_iteration_portable_browser.py --require-browser`；`portable-green-v3.xml`／`.log` | 12 passed、0 skipped，24.06s。 |
| 原相邻回归 | `python -m pytest -q tests/rebuild/test_main_iteration_browser.py tests/rebuild/test_main_iteration_entry_recovery_browser.py tests/rebuild/test_main_iteration_recovery.py --require-browser`；`adjacent.xml`／`.log` | 50 passed、0 skipped，114.68s。 |
| 静态检查 | Ruff、Node22及Node24语法检查、`git diff --check` | 通过。 |

首轮 `portable-red.xml` 的3项失败是事件回调fixture把内置 `append` 直接交给Playwright所致，不作为产品RED；改为普通lambda后才得到上表正式RED。首轮 `portable-green.xml` 为8通过、3个fixture失败：readonly reload后观察钩子未重建、两个往返场景使用隐式browser context。修正观察及显式context后，`portable-green-v2.xml` 11项通过；新增真实pending冲突验证后，最终v3为12项通过。所有失败原件保留，未删除断言或放宽超时。

源码修复提交下收集为830项browser、5391项总测试；Mac unit预期4416通过加6项既有跳过、render预期138通过加1项Frozen A跳过、installed预期726项。以上是收集／预期数量，最终运行结果仍须逐项核对，不预填PASS。

## 最终候选与边界

新head冻结后重新构建wheel/sdist并在仓库外安装，执行原Ruff、四组Python3.11/3.12×Node22/24、真实render、required browser、installed／离线UI、native／LibreOffice及实际双110万输入恢复。测试数量以冻结清单为准，既有跳过边界不变。只有本地与新push／PR各七项CI均通过、新反例关闭后才封包；旧R3 sealer和旧head结果不得作为新候选验收。

R3已通过的本机及两路CI（push `40538823069`、PR `40538841970`）属于前序证据。旧包 `Deck-Master-main-iteration-cards-20261027-review-r3.zip` SHA256 `3be548cd4e0a2df03b596fd908a7099cace7db2f247ec23fe14afece74770bef` 保留。`073d` 的Q2 180秒超时及两版本各十轮对照继续保留，远端原因未证明；不修改时限、断言、隔离或持久化语义。

全部25卡绑定同一新候选。预算保留62df／6e9／073d到新head，另列9c373d86到新head增量，区分运行源码、合同、测试、docs、工作树字节及归档成本。F13不实施；12项历史来源缺口、Frozen A、实际Host、客户／专业验收边界保持。PR继续Draft，不合并、不发布、不启动客户生产或新增付费模型批次。
