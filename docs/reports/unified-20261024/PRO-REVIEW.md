# 用户指定 ChatGPT Pro 整体审查入口

请审查 MainQuestAI/Deck-Master 的 `codex/unified-repair-20261024`，base 为 `afcc23d1654a6ce24583677c4de9d4a80f0f89bd`。先从最终验证清单核实 head/tree；如果 PR head 已改变，应停止复用旧 SHA 的结论。

用户要求统一收口184/185/187/188及 #183 受控消费者迁移；Humanizer 明确延期。请读本目录 README、ISSUES、issue-matrix.json 和最终验证清单，然后审查完整 `base...head`，不能只审最后一笔修复提交。

重点检查：

1. 四个来源确实是最终 head 的祖先；冲突是否遗漏非冲突自动合并中的业务修复。
2. PR188 层级/阅读/真实交互，以及 adopted compose、未读结果、历史/当前关系是否保留；PR185 dependency replan/未知调用，PR187 current_work、outline、summary复用、focus回退和queued close是否一致。
3. #138原finding闭环、#186外部报告返修与精确来源、#133字段diff；禁止删除限制、自动接受候选、用新ID绕过不确定结果。
4. #183不只opt-in：核对原生/SDK/Web/Host消费者、协商与解析、完整上下文显式读取、精确重放及外部旧客户端兼容。历史hash冻结工具不能静默改写。v3工具不继承旧control授权。
5. 逐项核查52项起点及尚未知新增编号；源SHA的历史证据与最终SHA测试分开，partial不等于bug也不等于pass。
6. Q2原70项/180秒、wheel安装身份、浏览器、渲染工具、完整关键流程、CI、真实Host/视觉/CPU的缺口不得隐去；所有首败重跑保留。

输出按严重度列出可复现阻断，注明文件/行、触发条件、影响、建议修复、验证方法；区分实现错误、缺少证据、产品决策。明确是否具备合并条件，不主动合并。未经验证的缺口不能因为用户未要求延期而自行豁免。完成后由父线程协调整改和最终合并。

运行代码候选为 `b66cec184e20bbfb34a133980e9ca92bbeb7e9bf`（tree `31b45fa320d0e9f0fa6acadd0233a2c4c3f61016`）；后续 browser 测试、CI 与报告提交以 sources.json 和最终验证清单为准。审查全部 main-to-head 差异，并核对安装 wheel 的全部文件与 Git 运行文件逐字节一致性。

补充重点：

- 先读 failure-attribution.json 和 browser-failure-attribution.json。旧 12 fail / 3 error、远端 8dc30210 的 21 browser fail、各次中断与新发现的上传续接时序不能抹去。旧广测跨源码编辑导致 BUILD_ID 分裂已有隔离复现；2040ca6d 两个冻结全套通过。最终完整套件仍必须按最终清单判断，不拿定向通过替代。
- 检查 unknown legacy scope 的 optional handoff 只提供历史读取，不变成当前制作许可；试作规范文字明确不代表全稿方向或生产许可。
- 原生 popover 已关闭时，取消模态应返回可见的“项目操作”；条目被移除时仍回标题，迟到响应与 queued close 不抢新表单焦点。PR187 modal 实现保持不变。
- 连续流程负例现在提交真实视觉试作并要求 preproduction_blocked 及零文档写入；PR185 允许正文纠错不是门槛漏洞。复审不得增加授权或外部调用事实；创建时 full_deck 的既有明确模板不能被测试误称不存在。
- 上传续接的两种合法路径都必须最终得到真实预览、原请求编号、仅一条参考记录和可刷新恢复。只在按钮已消失且预览实际就绪时接受自动续接与点击竞争；不得将任意超时或失败吞掉。请专门审查该同步修正是否保留原验证价值。
- CI 的 unit、纯 render、browser 集合必须覆盖全部 4913 个测试；两个 browser+render 测试仍在具备完整工具链的 browser job，不能遗漏。Q2 70 项及 180 秒不变。

PR 创建 POST 已 Forbidden，当前提供分支/比较页及准备好的 PR-BODY.md，不假定已有 PR。用户指定的 ChatGPT Pro 尚未执行；不得把本报告或内部工具输出当作 Pro 审查。由父线程协调审查、整改、CI 和最终合并条件。

前一轮完整广测 dbd7133b 为704通过/4失败；7947b25a仅修正三处测试合并遗漏，五个完整模块77通过。另一处1280px刷新启动壳停留超过原5秒，原断言未改，完整方法模块诊断4通过且请求无错，再次完整模块也通过；原始根因仍未确定，必须结合最终全量结果审查，不能把窄验当作根因修复或豁免。另有实际PPT组装与暂停精确重放3通过，补足RP-04/RP-05相应工程证据；真实质量边界仍保留。

可用完整差异材料：证据包内 `review-main-to-code-candidate.patch`、`review-diff-identity.json`、`review-commit-graph.txt`。`acceptance-focus.json` 为30个整改归属/52项提供工程边界索引。最终报告提交可位于已验证代码SHA之后，但必须证明新增差异仅在本报告目录；任何代码/测试/CI变动都不能沿用旧验证。

本轮最终完整安装浏览器：7947b25a上708通过、0失败/错误/跳过，4336.99秒；完整源码和wheel非浏览器各4062通过/2外部Frozen A跳过。请保留前一轮刷新启动异常根因未定的风险判断，不因本次全过而把旧失败抹去。新CI、真实验收和PR创建权限状态仍以最终交付为准。
