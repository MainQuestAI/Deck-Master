# RC3-04 R5 独立固定代码复核

**PASS_LIMITED_FIXED_CODE_REVIEW，无 must-fix。** 只覆盖 R5 错误分类修复、原三资产场景与下列有限负对照，不替代 Root 宽回归、安装、UI/行为复审或新 CI。R4 的有限复核未覆盖资产错误被误转为前审缺证的负对照；问题由 Root 固定宽回归真实暴露，本次补查，原报告与失败不改写。

## 身份与改动范围

- HEAD `740af2bddbc1199762c750be2f98474feaadb5a6`，tree `0ef706cca75acefaba218f714ffbc5c29f5d8aae`，parent `02a6d44da85cf4ecde9d84d4587f648587c41597`。
- fixed source `/workspace/work/rc3/reviews/rc3-04-r5-code-snapshot-740af2b`；absolute Python `/workspace/work/rc3/reviews/env-04-r5-740af2b/bin/python`。实际 deck_master/eligibility/production/content_review origins 全部来自该 snapshot，版本 `1.0.0rc3`。
- 只有 3 个非 docs 差异：1 产品 `eligibility.py`、2 测试 `test_service_flow.py`/`test_t06_boundaries.py`；9 个新增 docs 为 handoff、manifest、派生源身份与6份安全原件。
- 最初仅静态读取 live HEAD；Root GO 后才在新 fixed snapshot/env 运行有限 SDK。没有更改 live/source/install/Git、旧报告或人类/桌面延期安排。

## 精确错误路径为何保留坏 Task 恢复而不宽吞资产错误

`eligibility.preproduction_state` 现在仅 catch `ModelError`，且严格比较 `.path == 'blueprint/provenance/generation_request'`；不匹配时原样 raise。raw StoreError 和 RuntimeError 不在 catch 类型内。不根据 error detail/message 文本猜分类。

唯一已有精确 path 生产者为未改动的 `production.adopted_blueprint_design:207`：它在223–291行严格读取 Task/Request/Attempt/blueprint lineage。原 ModelError 保留自己的 path；其它 StoreError/OSError/ValueError/KeyError/TypeError 包为此 path 的 ModelError。

原故障将当前真实 icon Task immutable bytes 写坏；`Store.read_object_json` 先验证 Ref/digest，所以原故障首先触发 **digest mismatch StoreError**，不是跳过 hash 后直接 JSON decode。本次另加合法hash但malformed JSON Ref 的真实故障，对照实际 JSON decoder 的 StoreError，两者都被严格 production reader 包为准确 lineage path。

该 path 代表完整 generation-lineage 错误族，也含原所有权/Request/Attempt 等错误，不专属于坏 Task。只读投影将其明确显示 unreadable/satisfied=false/全部required units缺口；直接 strict rendering resolver 仍抛原错误，未跳过坏 Task、修原件或把缺证当pass。

资产权限 ModelError 的实际 path 为 `design_context/allowed_asset_ids`，既有 production wrapper 对 ModelError 原样 re-raise，R5投影边界也原样传播。raw asset StoreError 不再被 eligibility 吞掉。精确承诺是此边界收到的异常类型/path；如果既有 producer 已将其它读取问题归为 lineage，不能泛称它永远不会显示lineage缺证。

函数 try body 和正常返回分支未变；去除 exception handler 后整个函数 AST 与 R4 相同。其它 eligibility 顶层 AST 全部相同，没有调换门禁顺序或改变生产、调用、权限、质量/预算判定。

## 原资产断言与明确前置

`test_service_flow` 仅为固定 p1/blueprint 登记实际 `dispatch.blueprint` execute scope/grant（最多1 call、0 candidate，明确L1、未调Provider），坏资产注入前完成真实 fidelity workorder/claim/adoption。旧 unreadable 写入拒绝、revision不变、continue needs_input、`broken_asset_reference` 全保留；新增 `asset:logo`、`restore_or_replace_asset` 和完整project snapshot不变。

`test_t06_boundaries` 继承已有具名request/grant/fidelity前置，本轮不改它的预算/许可。restricted和unspecified两参数的设计写入、直接prompt、故障旧设计strict dispatch三层原拒绝仍保留，原ModelError文本匹配及Document不变均保留，只加dispatch前后全树不变。

两文件所有156条旧 plain-assert AST 保留，现160条：service_flow 114→117、t06 42→43，无删除/替换。没有新增autouse、skip、伪native/professional PASS或放行开关。

## 本次实际有限执行

**单次 11 PASS /0 FAIL /0 ERROR /0 SKIP，1.89s**，原始 `finite-boundaries.log`/XML 保留；未跑宽suite或UI：

- 原三个资产参数：unreadable asset恢复1、restricted/unspecified2，全通过，原业务断言未弱化。
- 两个 reviewer实际坏Task对照：immutable bytes损坏的digest mismatch，以及合法hash的新malformed JSON Ref。真实lineage包装路径准确；public describe/project_info可读、satisfied=false；strict rendering resolver继续拒绝；这些读取不改坏bytes和整个project snapshot。第二个是明确L1 fault injection，不是合法生产记录或模型结果。
- 六个强制边界负对照（不是实际资产观察）：其它path的权限/设计ModelError、仅共享目标path前缀的ModelError、asset StoreError、同样精确path但类型为StoreError、RuntimeError。覆盖status/qualify阶段，错误原实例全部传播；相同detail文字不能误触发隔离。

执行始终offline flags、新absolute专属Python、`-I -B`、短外置TMPDIR、独立basetemp、禁cacheprovider。没有模型/图像/provider调用、费用或人类/桌面声称。本轮11项探针首轮通过。

## 源码、文档原件与复用边界

739份其余tracked非docs与parent逐字节相同：R4-C1三JS、C2内容消费、production/generation/调用/权限/方法/contracts/版本/打包、w11/w12、原C3 unit、ledger等未改。复用只限准确未改依赖，不将源未改冒称新包/安装已验。

6份copy/28682bytes与声明SHA/size及外置原件逐字节相同；派生identity的当前/parent SHA也逐项核实。R4原unit 2366PASS/3FAIL保留，磁盘中断browser/recovery不补盖broad PASS；未复制Store/registry/key/HMAC/venv/包/客户材料。

完整fixed source3944 tracked bytes/mode、HEAD/tree/status、Python/version/origins前后不变，另核最初live静态阶段及冻结的R4/preflight原件，详见 `source-unchanged.json`。公共grammar解释的外置addendum与本代码结论分开；原报告不覆盖。

现已冻结并STOP。整卡仍须由Root完成正式候选回归、安装、其它复审及exact-head CI；本有限PASS不宣布RC3-04/05完成。
