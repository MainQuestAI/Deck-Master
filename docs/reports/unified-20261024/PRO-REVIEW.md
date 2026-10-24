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
