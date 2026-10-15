# RC3-04 R4/R5 最终工程证据报告

软件版本仍为 `1.0.0rc3`，writer floor仍为Entry13。当前运行代码是R5 `740af2bddbc1199762c750be2f98474feaadb5a6` / tree `0ef706cca75acefaba218f714ffbc5c29f5d8aae`；父版本R4为 `02a6d44da85cf4ecde9d84d4587f648587c41597`。本次提交仅为docs/evidence，不改产品或测试。既有全卡实现/原范围映射见[R1–R3原卡映射](../entry-integration-handoff-20261015/acceptance-map.md)，本报告补上真实CI失败后的修复、回归与准确状态，不重签原卡或人类结论。

## 当前已完成和待完成

| 证据 | 准确版本与结果 | 当前边界 |
|---|---|---|
| R5 Root fixed unit | 740af2b；2369PASS /506deselect，exit0，622.60s；3944份source/head/tree/status前后完全一致 | 完整工程unit通过；原log SHA256 `b7129630d30498fcdc738b695bf00627dce36725442f6169ecca5615dc77864d` |
| Root fixed render | R4 02a6d44；71PASS /2804deselect /22warning，exit0，165.35s；source前后一致 | 保留R4原身份；不声称R5重新render通过。新exact-head CI render仍待执行 |
| R5实际安装离线UI | 同0690dd66 wheel的非editable CI-like env；9/9 checks，3个真实ZIP下载及完整digest，0external/0pageerror；3944 source+271 installed前后相同，模块全部来自site-packages；CI同款DejaVu Sans | 真实synthetic offline installed gate通过，不是实际HOME激活、人类或桌面验收 |
| R4独立code /installed behavior /installed UI | 三份有限PASS，见下文各自scope | 原报告保持02a6d44身份；C3宽catch的资产遗漏由Root宽unit暴露并由R5重新复审 |
| R5独立code | 新fixed 740af2b；单次11PASS，0skip，无must-fix | 原3资产参数、2种真实坏Task、6个强制类型/path边界；不是broad或UI |
| R5独立installed behavior | 新fixed wheel；4条实际SDK故障轨迹通过，无must-fix；source及两安装内容前后不变 | 坏icon Task、restricted、unspecified、missing asset；不是HTTP/Studio或16条Host重跑 |
| Root R5 source browser | **PENDING_RUNNING**（Root session53976） | 不读取/复制活动log，不预填总数或PASS |
| Root R5 installed full recovery | **PENDING_RUNNING**（Root session87309） | 不读取/复制活动log，不把offline9或有限SDK替代完整recovery |
| 最终docs-head新包/strict/独立docs review/实际7CI | **PENDING_FINAL_DOCS_HEAD** | Root负责新fixed build、271 package bytes对比、review和实际checks；全部通过才可merge |

并行冻结docs只减少等待，不提前merge。后续真实宽gate计数与新GitHub CI由Root外置冻结汇总、PR119实际checks及05总台账回引；本提交不含未来结果，RC3-05执行仍未开始。

## 原失败不覆盖

8223df8真实CI run38696634552的browser为90FAIL /342PASS /4ERROR；其后wheel/install、offline UI与installed recovery三step未执行，Group失败。canonical原log SHA256 `9705083903f932e1da74310b9c5bc066781d290de443dc15e18e2a251c632f89` 已在[R4原失败安全包](../r4-ci-failure-evidence-20261015/manifest.json)保留。94个事件对应93个distinct test ID，Owner分四排他域完成实际focused映射，独立code再次验证原log事件multiset与映射完全相等。映射是live L1证据，不改写原CI状态，也不替代仍运行的固定browser。

R4 Root fixed unit实际2366PASS /3FAIL；原bad asset恢复、restricted/unspecified strict dispatch三失败与后续R5修复分开保留于[R5原件](../r5-asset-boundary-evidence-20261015/manifest.json)。先前R4有限code/behavior PASS没有覆盖这一资产异常边界，不能拿有限PASS抵消真实宽失败。

R4 source-browser与installed recovery运行时overlay磁盘耗尽，出现Errno28，Root以SIGINT中断，状态为 **INFRA_INTERRUPTED_NO_BROAD_PASS**。原partial XML为283tests /279PASS /4FAIL；installed recovery未得正常summary，原早期失败、后续cascade与中断teardown错误保留。空间恢复后在同一未改R4上，仅原4个source-browser参数实际4PASS；这项精确诊断不是完整browser/recovery通过，也不把全部旧失败武断归因磁盘。raw XML、partial log、interruption记录及4PASS log/XML均有本目录安全副本。

Root的storage-relocation.jsonl保留9条原临时树搬迁记录，另保留R5 unit临时树归档记录。目录被逐字节保留为archive；没有删除Store/证据，R5归档还记录mode/mtime/links/FIFO及原路径symlink。只复制搬迁记录，不复制归档目录。所有原件保持原版本和状态。

## R4产品和测试修复的准确范围

- **C1：三个真实v2 Plan消费者。** gallery和overview按实际page_ids分章；content-sources完整clone v2 input，仅修改实际章名、对应role目标和source_links，保留其余role、顺序、budget/time/speech/issues/tradeoff/mapping。legacy goal→page及v1保存分支保留。v2不存在的旧summary/未决事项字段只读保留，空来源提示指向实际可执行操作，不伪造v1字段或新rich issues编辑器。
- **C2：独立理由回执。** v2无正文变更时保留authored unchanged_reason，与impact_summary分开；未提供时summary fallback不变。显式非法理由拒绝，proposal-only及terminal replay保真。普通Task/采用事务事实正常创建；理由不产生独立核实业务/来源事实、授权或费用事实。首尾空白按原约定trim，内部空格/换行/Unicode保留，不声称首尾逐字不变。
- **C3：故障读取隔离。** R4先以宽ModelError/StoreError catch实现坏Task项目只读可用，同时令缺证保持unsatisfied；该宽度错误吞掉资产语义/I/O错误，由R5收窄。最终语义以下节新R5为准，不整体复用R4针对宽catch的17项探针结论。
- **Fixture/验证迁移。** 具名scope、真实方向/授权、实际Task协议/capability claim和必要L1 fidelity前置；不提供全局autouse授权或旧writer开关。24个browser文件没有删除test函数，独立AST审计明确5条同义迁移：历史选项2条改实际精确文案并增强A/B option/URL身份，旧v1计划字段3条改实际v2章/role字段并增强未编辑约束不变。原几何、timeout、scope、CAS、恢复、late/replay与原件断言保留。
- **w11/w12与证据落点。** 固定p1 output明确0call/0candidate交付授权/decision；w12真实展开完整性modal后验证同一实际下载digest，未删hash/notes/privacy断言。截图/Journal默认移tmp_path或明确外置env；旧诊断整体搬迁保留bytes/mode/mtime，不隐瞒产品写入。

各Owner原失败及focused完整日志继续由[R4交接](../RC3-04-R4-HANDOFF.md)和安全manifest逐项定位。A86、B合并81、C42、Classic23是各域实际观察，B不是一次81重跑；artifact子集复验不扩增原94场景或冒称新全量矩阵。

## R5最终异常边界与独立复审

R5唯一产品差异为 `eligibility.preproduction_state` 的catch：仅隔离类型为ModelError且`.path`精确为 `blueprint/provenance/generation_request` 的既有错误族。其它ModelError、StoreError、RuntimeError原样传播，不根据detail文本猜测。production reader、门禁顺序、授权/预算/费用和Task扫描均未改；该lineage path也可能表示所有权/Request/Attempt错误，不专属于坏Task。

原C3 unit直接损坏Task bytes，实际先触发Ref digest mismatch StoreError，并非绕过hash直接JSON decode。R5独立code另加合法hash但malformed JSON Ref的明确L1故障；两者均由未改动的严格production reader包为上述lineage ModelError。只读project_info/describe成功、unreadable/satisfied=false、全部缺口保留；直接strict resolver仍拒绝，原坏bytes和全树不变。六个强制类型/path对照证明相同detail文字、仅共享path前缀或同path但StoreError类型均不会误吞。

R5资产正反例恢复原契约：restricted/unspecified在写设计、strict blueprint dispatch和continue均给原ModelError /design_context/allowed_asset_ids；missing artifact在preproduction/strict dispatch给StoreError /asset:logo，continue给broken_asset_reference、restore_or_replace_asset。合法scope与当前L1 fidelity前置明确；权限最多1call/0candidate，实际调用未开始。真实SDK拒绝前后完整project/Current/Document相同，不新增Task、bundle或隐式授权刷新。C3 delivery原decision_needed先挡的证据保持原标签，未升级为独立证明unreadable delivery判据。

R5两测试文件所有156条旧plain assert AST保留，新增4条身份/不变性断言；没有为了通过把精确错误改为任意block。新fixed unit全通过，以及独立新code11项和installed behavior4轨迹共同覆盖此delta。新报告均有限PASS、无must-fix，仍不代替broad/CI或人类结论。

## 包、方法与复用身份

实际R5候选 `candidate-04-r5-740af2b`：manifest SHA256 `fb6271c4bf24c4c4662183d44127bdd8651c86718cde7c967d5e0c431bf7cae5`，wheel SHA256 `0690dd667da48d4fe47fc2202489f73a9e029900a010163b72ef2ae2e4ddc48e`。Root严格审计 SHA256 `e6e5867ff56aa3dd6660786846709c064120214ffeacccd6f9cae688e375a722`，为270 canonical+1明确generated、四Role完整字节/metadata/release.files/RECORD验证；只表示 **PASS_BYTES_ONLY**，不是方法应用或专业验收。manifest内旧basic collector的263是子集计数，不替代此严格完整inventory。

Root实际wheel成员比较271项中270项逐字相同，仅eligibility.py变化；另独立installed行为比较同样确认，pyc安装差异另列，未说两套安装整体相同。该字节事实支持R4-C1/C2/UI的准确复用，不表示R5重跑这些原检查。R4三路报告分别为code `da8830a8…`、behavior `e2e97076…`、UI `20bba4bf…`；R5新code `cf7da483…`、behavior `51e915d6…`，完整SHA/size均在本目录manifest中。

四Skill/五份共享方法与合同保持当前声明的资源清单，16组合仍是[R3新1+R2复用15](../entry-integration-handoff-20261015/role-entry-paths.json)，同一个实际Host，无16个独立模型或新R5 Host16声明。RC3-03单p04 native证据仍保持其原有限范围。最终docs-head Root将重新build/strict并实际比较全部271 package bytes；此未来步骤不预称通过，wheel容器/元数据hash也不猜成0690dd66。

## 安全副本与原人类延期

[Manifest](manifest.json)明确列出42份冻结原件（502976 bytes），SHA/size/来源逐项相同；10份较大原manifest/identity/XML仅索引，无整838/162目录复制。R5两个活动宽gate日志明确排除。本目录Markdown和status JSON为Owner派生导航，不是Runtime决定、用户批准或新执行回执；没有脱敏后冒称原件。

唯一[37AC/13CQ台账](../evidence-ledger.json)全部字节与R5父提交相同，SHA256 `daceae45c257431938479e29104aa3381a395c880b719613fee97e3a23004272`；其原状态、Owner、signers、人类延期均不重写。真实Owner/听众/计时/专业签署/目标桌面仍 **NOT_RUN_DEFERRED**；05效果/controller执行与公平E1/E2/E3均 **NOT_RUN**，未知token/费用保持未知。软件测试或Role改名不生成独立模型/专业/人类证据。Root实际本地gate与新exact-head7CI全部通过并完成文档复核后才可merge，当前不提前进入下一卡。
