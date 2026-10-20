# WU08 欠项与 Draft 创建结果澄清

本次接续没有重试创建 Draft PR、没有换 API/执行环境；只有一次同通道按分支只读查询。产品代码未修改，增加四项真实浏览器验证，AC18 与 AC20 已根据结果关闭。

## Forbidden 的准确含义

原创建命令已经由执行工具运行，返回 **exit 1**，原错误摘要：

```text
Post "https://api.github.com/graphql": Forbidden
```

这是 HTTP/API 访问错误，不是工具审批明确 DENIED。原账本的 DENIED 是不准确的分类简称，已改为 `API_ACCESS_ERROR`，同时保留原记录。没有凭据、token 或审批拒绝信息被输出。仅凭错误无法区分拒绝来自 GitHub 还是代理访问层。

同一 `gh` 通道运行以下只读查询，也得到同一错误和 exit 1：

```text
gh pr list --state all --head codex/webui-content-methods-impl-20261020 --json number,url,state,isDraft,headRefName,headRefOid,baseRefName
```

没有 PR URL/编号或 mutation 成功回执；无法凭上述错误排除远端已创建，因此远端结果为 **UNCERTAIN / 未确认**，不是“已确认没有 PR”。已停止查询/创建，不换通道绕过。父线程独立只读核对后再决定接续，避免重复 PR。

## 本次新增证据

`tests/rebuild/test_webui_content_insight_browser.py -k 'adoption_lost or adoption_concurrent or fixed_current'`：**4 passed, 8 deselected in 8.91s**。测试定义提交 `9c493c6e`；产品代码与已构建安装的 `3c6d4a41` 相同，未把新测试算作重新构建。

- AC18：current+candidate、current+historical 的两份真实 Ref 固定比较；后台指针/版本变化后刷新仍保留左右稿；比较中无写入按钮。已有服务检查覆盖不同主线对应不同 Plan。
- AC20：采用成功但 ACK 丢失后刷新，按原 UUID lookup 恢复，不再次 POST；两步之间并发修订时原 base/payload/决定保留，必须明确读取当前准入并以新 UUID 请求，未重复决定。决定 ACK 丢失已由前一组覆盖。

这是 synthetic Runtime + 实际浏览器工程证据，不是独立专业认可。

## WU08 自有 AC

| AC | 当前结果 | 尚需动作 | 谁可完成 |
|---|---|---|---|
| AC45 | NOT_RUN，部分覆盖 | 经营诊断、方案比较、教学三类完整 Runtime/浏览器链路；目前仅教学实际 Host plan_only，另有合成工程项目 | 云端可继续自动化及实际 Host 执行；成稿质量须另列独立专业审阅 |
| AC46 | NOT_RUN，部分覆盖 | 新主线/比较/方法/审阅交接的全部键盘路径、焦点恢复与长内容审计；三视口无横溢已通过 | 云端浏览器自动化可继续；用户体验评价不能由此替代 |
| AC47 | PASS | 已有准确实现 SHA wheel/sdist、隔离 managed 安装及三视口/采用路径；若产品代码变更需新包 | 云端自动化；不需用户批准安装到真实 HOME |
| AC48 | NOT_RUN，部分覆盖 | 显式验证移除新 UI、安装回退、旧版本/旧任务及 writer 拒写不变；现有回归不能代替完整回退实验 | 云端隔离目录自动化可继续，不动真实 HOME |
| AC49 | NOT_RUN，部分覆盖 | 新 PR 确认和其准确 head 的 required CI；本地日志与包绑定已保存 | GitHub 授权访问恢复/父线程只读核对后继续；不能用 PR127 CI 代填 |
| AC50 | PASS（仅分层回执） | 结果、限制已诚实分层记录；不代表 professional_review/human_acceptance 通过 | 独立专业审阅者及用户仍需实际执行相应验收 |

## WU08 集成验收仍承接的前置欠项

下列共 23 项，加上自有 AC45/46/48/49，共 **27 项未闭合**。都是“已有部分证据但完整 AC 尚未验证”，不是断言产品全部失败。逐项详述仍以 execution-ledger.json 为准。

| 所属卡 | 未闭合 AC | 可继续的自动化 |
|---|---|---|
| WU01 | AC06、AC07、AC09、AC10 | 跨项目/版本非法引用矩阵；固定分页遇并发；旧无 manifest/v2 扩展组合；XSS 与迟到响应 |
| WU02 | AC11、AC12、AC13、AC14 | 老 Task 无清单空态、历史 metadata、缺文件/hash 漂移恢复、未知调用期间不派发 |
| WU03 | AC17、AC22 | Narrative alternatives/条件的多结构渲染；write_only/speech_only 新入口只读限制 |
| WU04 | AC23、AC25 | 条目/表格单元与键盘选择；失效 atom、无映射、损坏来源的完整 UI 矩阵 |
| WU05 | AC28、AC29、AC30、AC31、AC33 | v2 impact/resolution 全状态；整稿/失效位置；交接草稿→原 plan/commit 精确范围；分层与 review_only；stale/scope/断线恢复 |
| WU06 | AC35、AC36、AC37 | 用途提示保留输入；多冻结设计任务投影；空间不足仍保留语义并只提出内容交接 |
| WU07 | AC40、AC42、AC43 | 角色/阶段切换再校验；过大正文/各预览变体；刷新准备稿、目录/字节/revision 漂移时禁止旧复制 |

## 不能自行勾选的认可

- **human_acceptance：NOT_RUN。** 必须由实际用户/指定人类体验工作台并给出反馈；自动化、截图或代理自查不能代替。
- **professional_review：NOT_RUN。** 需要符合项目独立性要求的专业审阅者。可以是获授权且独立的模型/Host 或合格人类，未必必须人类；当前实现/内容作者不能把自评冒充独立审阅。
- **实际 Host 三场景：部分完成。** 可以在当前云端继续执行真实协议，但必须与 fixture、工程测试、独立质量认可分开记录。
- **GitHub 访问：受阻。** 原错误和只读错误均已保留；当前任务不再重试，不要求用户重复授予已有的创建授权，也不绕过访问限制。
