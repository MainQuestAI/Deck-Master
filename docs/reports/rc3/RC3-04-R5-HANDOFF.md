# RC3-04 R5：恢复资产错误契约并收窄C3读隔离

父版本为R4 `02a6d44da85cf4ecde9d84d4587f648587c41597` / tree `8a12383ab597dbd061ad53de6f5186c5343d19d4`。本轮由Root固定unit真实失败触发，不是重试归因、测试期待放宽或把产品回归藏入fixture迁移。R4原snapshot、包和全部原失败不改。Root授权先冻结本轮最小修复，Owner统一commit后停写，所有worker持续STOP；R5 fixed/installed/独立复审及新exact-head CI均为 **PENDING_NEW_FIXED_HEAD**，RC3-05不开始。

## 原固定失败与实际原因

Root R4固定unit退出1：2366PASS /3FAIL /506deselect；source before/after一致，原log SHA256 `3a7e877c3c4545af54af3a27495d68b8201952c3e29ea1bbc9055d9b383938ff`。三条为：

- `test_service_flow.py::test_design_rejects_unreadable_asset_and_old_project_gets_recovery_hint` 先遇缺dispatch授权，未到原 `broken_asset_reference` 恢复提示。
- `test_t06_boundaries.py::test_restricted_assets_never_dispatched[restricted]` 与 `[unspecified]` 已有明确scope/grant及当前fidelity review；实际资产validator抛 `ModelError` / path=`design_context/allowed_asset_ids`，但R4-C3将它误改投为unreadable前审缺证，因而返回preproduction_blocked。

独立诊断确认两种权限下，坏设计注入前当前前审均通过；同一坏设计读取时原异常精确路径如上，R4共享投影却吞为unreadable。两次读取的完整project bytes均不变。无法诚实仅靠补一份review解决：前审本身也通过同一有效设计/资产validator，追加review仍先拒绝这些坏资产。Root据此授权修正C3过宽的产品异常边界。Owner先保留3FAIL/1PASS原样复现，再实施修复。

## 最小产品差异与测试前置

唯一产品文件为 `src/deck_master/eligibility.py::preproduction_state`。只隔离 `ModelError` 的既有精确类型路径 `blueprint/provenance/generation_request`；该路径由严格 `production.adopted_blueprint_design` 包裹不可读Task/generation lineage。其它ModelError和StoreError继续按原合同传播，不按错误消息文本猜测原因，不把资产权限、设计语义或asset I/O错误吞成前审缺证。门禁顺序、production resolver、Task扫描/原件、质量判定、budget与授权均未改。

`test_service_flow` 只为固定p1的blueprint登记实际 `dispatch.blueprint` execute授权（最多1 call、0 candidate），并在坏资产注入前完成真实L1 fidelity workorder/claim/adoption；无Provider调用、不批量授权、不取消Task。原unreadable写侧拒绝及 `broken_asset_reference` 精确断言保留，增加 `asset:logo`、`restore_or_replace_asset` 和continue前后完整project hash不变。`test_t06_boundaries` 两种权限的写侧拒绝、直接prompt拒绝、strict dispatch的原ModelError文本匹配及Document不变断言全部保留，仅增强dispatch前后全树不变检查。

## 实际focused结果及边界

- 精确三资产参数+C3 unit：4PASS，1.35s。
- 邻近资产注册/byte失效/画布组失效/effective override/独立前审/专业policy不相互替代：6PASS，0.78s。
- 三个变更Python文件Ruff与authored diffcheck通过；未运行mutable宽suite、浏览器矩阵或Host16。

C3原unit未改，且已由本轮精确4项重验，故复用这一准确正反例而不添加重复矩阵：实际confirm→dispatch icon Task，定位当前Document.tasks真实Ref并将其immutable bytes写成 `b'{broken task'`。正常前审先PASS；坏JSON被既有lineage包装路径识别后，project_info/describe只读可用、状态unreadable/satisfied=false、icons仍dispatch_unknown；直接strict resolver仍抛generation-lineage错误，produce/delivery均拒绝，原坏bytes与完整project hash不变。delivery仍是原已有decision_needed缺口，不冒称单独证明unreadable门禁。此L1故障注入不建立真实模型、原生图像、独立审稿或人类证据。

可clone的原固定失败、Owner复现/诊断/最终focused log逐字节安全副本见 [R5证据清单](r5-asset-boundary-evidence-20261015/manifest.json)。未复制Store、registry、runtimeauth/HMAC、venv、包、客户原料或浏览器session。原始及中间失败保留，raw日志空白不清洗。人类Owner/受众/计时/桌面/professional继续延期NOT_RUN；unknown费用不改为0。

## R4中断宽测试与冻结边界

R4的Root source-browser与installed recovery运行期间，root overlay曾100% /Avail0，出现Errno28。Root保留全部原件迁移自己的临时树后恢复空间，两个宽gate由Root以SIGINT中断，标记 **INFRA_INTERRUPTED_NO_BROAD_PASS**。Source-browser的partial XML实际283tests /279PASS /4FAIL；其中rc_closure missing_ref/old_basis与两条draft conflict仍待Root空间稳定后按原输入精确诊断，不能武断全部归为磁盘。Installed recovery未得到正常summary，中断teardown KeyError及原3F与后续cascade保留，不把它称为完整suite通过或据此扩大本轮产品修改。

恢复空间后Owner只核完整性，没有重跑已通过focused：既存4份相关源码哈希、origin JSON、六份逐字节副本/manifest均与空间耗尽前一致，交接UTF-8完整。R5非docs变化严格为上述1个产品文件+2个测试文件；C3故障unit、R4-C1三个JS、R4-C2内容消费、w11/w12、四Role方法、合同、版本/打包器、production严格resolver与37/13台账均逐字节复用R4，见 [源身份](r5-asset-boundary-evidence-20261015/integration-source-identity.json)。Root将建立新fixed候选，复审C3与三个原资产参数及必要受影响项，安装包其余字节仍需实际比较；本地源未变不冒称新包/安装已审。
