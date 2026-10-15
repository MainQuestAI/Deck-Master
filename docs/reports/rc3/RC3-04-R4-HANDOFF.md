# RC3-04 R4：最终CI browser失败后的修复交接

本轮以未合并的 PR119 HEAD `8223df80be654c9a89a44cd97cf770fa01bf4383` / tree `7b96dbcc1784160a5e045e3198e51f93c0542504` 为父版本。旧snapshot、包、失败与审查原件不改。四个排他worker均已最终停写/停止执行，Owner统一commit并另交exact HEAD/tree/parent/clean。RC3-05不开始，新的CI为 **PENDING_NEW_FIXED_HEAD**，不是旧失败的重试PASS或整卡验收。

## 原final-head CI真实失败

run `38696634552` / browser job `116294607252` 实际checkout PR merge SHA `749b022e016a058f80fd516117c8d324227fab4f`，绑定head8223/base634d75。browser step9结果为 **90FAIL /342PASS /4ERROR /2433deselect /2408.20s**。其后的wheel build/install、offline installed UI、installed recovery三step未运行；Group failure。四个unit job为2360PASS+2SKIP，render70PASS+1SKIP，不改写成全7CI PASS，也不拿R3本地2362/71替代这个CI结果。

ci_guard正式冻结报告 SHA256 `1168dbfc01b688aa48db1fe7c2a77bf780e17e8f85534b6b7522bd2a84886aa4`，JSON SHA256 `ea409cc2aa89f2b533eddc6d39176db5208625215a68ad7f3a4eb8710681b101`。canonical browser原log为1241304 bytes / SHA256 `9705083903f932e1da74310b9c5bc066781d290de443dc15e18e2a251c632f89`；Root首copy多一个LF的原件和correction仍保留，不将它冒称canonical。可clone的安全副本/报告/94事件库存见 [R4 CI失败原件清单](r4-ci-failure-evidence-20261015/manifest.json)，五份逐字节副本，共1303721 bytes，manifest SHA256 `d8cefea51e1289b4c1226b1d78a03b1b36f37ea3017db4c3fd23e0fe289b1368`。未复制API凭据、Store、registry、HMAC、venv、客户材料或安装包。

## 排他分工与原事件映射

`/workspace/work/rc3/reviews/rc3-04-owner-r4/ci-browser-failure-inventory.json` SHA256 `f5b759226bd648f8c12ceb45318b820494c978568fcc6cd9e90f80ccb8976585` 按完整test ID和outcome唯一分配94事件。batch lost-response有同一test的FAIL与teardown ERROR，仍分别保留，不充作两个独立业务场景。

逐事件的原outcome/摘要、排他Owner、最终实际focused观察与冻结handoff/hash见 [94事件修复映射](r4-focused-evidence-20261015/original94-r4-mapping.json)，SHA256 `1ab50c6d4a3c21a9386287e41acd29ca9981b2a6a02443bcfeed10de2d5c219d`。94事件对应93个distinct test ID；全部有本域实际通过观察，正式fixed/installed/CI关闭仍待Root新候选验证。

| 域 | 原事件/文件 | 处理与最终focused |
|---|---|---|
| A adapter_external | 28 /9 browser文件 | 原28/28实际重现；九文件86/86 PASS、0skip；artifact纯落点变更仅受影响3参数3/3 PASS。184个原Assert AST保留。handoff SHA256 `23744a158df69d40aae7f61745fdbf60e6b51a7df3ee9408fc6a58ad2774e1b7`，本域STOP |
| B skills_install | 27 /7 browser文件 | round1 76PASS/5FAIL，精确5参数补验5PASS，再纯artifact默认落点2PASS；合并81 distinct、0skip，非单次81重跑。原27全部映射实际通过。handoff SHA256 `58a181d3503086e911058d1116e34d385ee9b109bb236e230b33d5eebd095a59`，本域STOP |
| C studio_browser | 23 /8 browser文件 | 原23+其余19均实际Chromium通过，42 distinct、0skip；补真实v2章节/范围控制fresh6通过。早期两轮仅mutable，最终6源前后稳定。handoff SHA256 `ab66144227692047d50745ae9cc05b8f8319eb37aaf4ae402185061d9b501b31` |
| Classic | 16 /4 browser文件 | 包含range3 setup ERROR与batch teardown ERROR。稳定核心下23/23通过；另2函数4参数仅artifact落点后复验4/4。handoff SHA256 `91828d4b7ef92b33c7a5d1d8de2f4957b92f7891eaf438af5e5dc6dbf6c4e57c` |

非browser共享factory、Runtime及Git始终只有Owner编辑。没有autouse授权、产品旧writer开关、fixture/native/professional fallback、删断言、动态skip、放宽selector/几何/timeout或隐式全页scope。每个域先核原traceback和业务断言，再补实际具名Request/方向/明确grant/真实协议与capability claim。gallery读失败没有通过把新v2稿改回v1规避。

B的五个末端失败单独保留：管理修订需显式“显示全部历史记录”，每次route重挂载后重新选择；两个历史选项的旧文案断言更新为实际精确文案，并增强option value=A/B、URL revision与原source/current/export/restore/CAS身份检查；两条style导航将该测试专用grant置于第一次载入前，控件不强制enable。既有plain assert均保留，无几何或门禁断言删除。B round0 63PASS/18FAIL为混合live诊断，原round1五失败、选项文本/请求/截图不删。

## 三项真实产品修复

### R4-C1：v2 Plan的真实UI消费者仍按旧目标身份读取

实际gallery30中 `/api/project`、`/api/gallery`、`/api/content-plan`、`/api/drafts`均成功，125项资源已完成，无pending请求；URL正确为gallery，旧工作面却保持不变。异常被Project.loadRoute捕获，不触发pageerror。仅诊断wrapper记录并原样rethrow得到 `TypeError ... undefined (reading 'map') at gallery.js:32`。实际v2章节只有 `page_ids`，旧代码调用 `chapter.goal_ids.map`。

`gallery.js`现按真实page_ids建立v2章节，旧v1保留goal→page映射。`overview.js`矩阵也用实际v2 page_ids归属，不把所有goal_id=null混为同一目标。`content-sources.js`大纲按实际page_ids显示章范围、页选择与来源；完整outline编辑clone当前v2 input，仅修改用户实际编辑的章名、role intended_takeaway和source_links，保留其余角色、页序、budget、time、speech、issues、tradeoff及映射。没有伪造goal身份或改schema。

v2不存在旧input_summary/role unresolved_facts字段，界面不再假装把这些字段保存为v1。当前可编辑的是实际章节、页面目标和来源；已记录未决事项只读保留。v2空来源提示也改为核对本页来源/已记录未决事项并登记材料后关联，不再指示编辑只读字段；legacy原提示保留。该一行文案后fresh实际outline/preview/cancel/commit单case 1/1通过（13.44s）。旧草稿整合说明若存在，仍只读展示并明确尚未写入当前计划；旧v1序列化/编辑分支保留。原当前v2测试用真实章节/目标文本持久化、取消/CAS及所有未编辑约束等值承接原业务断言。legacy分支未宣称单独新增browser全矩阵。

C原23与其它19真实browser检查、真实三章各8页的精确范围/指定页、30页章节筛选与原keyboard断言通过。新章节检查首次误把mixed24当单章导致5FAIL/1PASS，原log保留；后按实际三章各8页修正测试事实后fresh6PASS，不归产品缺陷。Classic实际v2 outline编辑/取消/commit、source版本定位与stale拒绝、大纲导航均通过。

### R4-C2：v2无正文变化回执丢失不同于影响摘要的原始理由

原actual browser的输入判断弹窗同时核对Host影响摘要与正文不变依据。共享L1 envelope helper只写diff.summary；v2 adopter也将summary同时当unchanged_reason且回执不提供原独立理由。不是通过删除弹窗断言解决。

`test_content_ops.v2_revision_envelope`明确转交原authored unchanged_reason。`content_production._accept_input_revision`仅在没有实际Page变化/删除时接受非空字符串理由并将其保真放入真实采用/提案回执；未提供时沿用原summary fallback。原diff schema本来开放object，没有新增schema；v1接受/回放逻辑不改。理由只是Host解释，不产生已核实来源、阅读/批准、授权或费用事实。原来源/映射校验继续逐层检查。

新正式SDK正例区分summary与reason，保留Page/output，精确重放返回already_applied、相同revision/refs/reason且全树不变；None/空串/空白/dict/list五反例拒绝且无写。首次新测试误期待terminal replay返回accepted而非既定already_applied，作者失败原log保留后校正真实协议断言。源映射旧正负与C2/C3合并21/21通过，Classic原popup两条不同原话实际保留。

### R4-C3：损坏Task不应使整个只读项目入口不可用

原rollup browser故意将真实已派发icon Task对象写为坏bytes。`icons.listing`正确为dispatch_unknown，但collaboration.describe→preproduction_state→review digests→adopted_blueprint_design在扫描坏Task时抛ModelError，连/api/project都不可读。A的原坏bytes/Task/current和诊断stack保留，不通过修坏对象或扩大grant解决。

只在共享 `eligibility.preproduction_state` 读边界捕获预期ModelError/StoreError，返回明确unreadable、satisfied=false、全部所需unit缺口和保留原件恢复提示。production lineage resolver不改，不跳坏Task，不把现代缺失provenance当legacy fallback；03F9依然严格。正常quality要求不变，没有把缺少证明当已通过。

实际project_info/describe可读、原dispatch_unknown警告/零POST/损伤原件不变browser通过。正式SDK同损坏项目produce以preproduction_blocked拒绝，delivery以其真实已有decision_needed缺口拒绝；不把后者冒称新unreadable判据的独立测试。每次公开拒绝后全树/当前/费用不变；直接render-design resolver仍抛原lineage错误。正常前审与当前native lineage/资格/content_ops affected80/80通过。独立新fixed复审仍由Root负责。

## 先前未运行的installed UI wrapper

Root对固定8223实际隔离安装补查w12，原首setup工具环境错误单独保留；纠正环境后已真实完成PPT编译/渲染/两视口/首review下载，随后原测试误在未展开的row查完整hash失败。w12现在真实点击“查看文件与哈希”打开完整性modal后核对实际下载digest，原ZIP每文件hash、notes、privacy与安装资源字节断言不删。

Owner推进所有purpose后，又实际暴露w11 fixture缺明确delivery_acceptance。现只为固定p1 output登记明确L1 host-attested consent与output-only export.delivery授权，0call/0candidate；工程/host_self记录本身不代替授权，更不代替真实人类。policy与production gate不放宽。fresh w12完整9项实际Chromium诊断通过，三purpose真实ZIP/digest、notes/privacy、资源/路由/无外网均保留。此次用专属开发Python，**不是已安装正式PASS**；Root新fixed build/install后重跑正式wrapper。两轮原失败log保留。

## 测试证据落点与当前边界

本轮发现若干浏览器测试硬编码向checkout/output写诊断。只将落点改各自tmp_path/明确外置env，不隐藏产品写入或放宽pure-source断言。Classic原两目录6files用os.rename完整移外置，SHA/mode/mtime不变，relocation manifest SHA256 `6e656fd3c3b7ef83e19757721385fa6930eb04837a7d05c2e2a436a9be9a1e65`；受影响4参数复验通过。C追加三个原CI已PASS文件的3函数6参数仅路径变更，assert/expect AST完全相同，实际6/6通过；checkout既有100文件前后不变，handoff SHA256 `40a139c7ab40dd45bc14dbaf321181ba2f84e78a53c85e39100cdacc7d98831c`。A原breakdown目录3PNG同样整体rename至外置保全，SHA/mode/mtime（含目录）一致，此前是否已存在未知；只改落点后实际3/3通过，九文件全量不因落点修改重复执行。这些artifact复验不增加94原失败的关闭数量；原件未删除或覆盖。

B两处全局默认checkout目录也改为其项目tmp_path/evidence，显式外置env保留；只对deep/version-area和UX08/content实际复验2/2。无env时截图及actual content commit200 Journal均位于各自临时目录；未藉此隐藏产品写入。

Owner focused原失败与最终log，以及各域冻结交接JSON的安全逐字节副本，见 [focused证据清单](r4-focused-evidence-20261015/manifest.json)。Owner合并C2/C3及来源校验为21PASS（5.58s），当前lineage/资格/content_ops为80PASS（25.41s）；w12三purpose完整9项与C1提示后1项真实browser结果分别保留。首轮新测试的replay状态误期待、delivery先遇已有decision缺口以及w11缺明确delivery consent都保留失败log；不删除旧失败或把补充测试作者错误归入原CI产品缺陷。最终只对全部31个变更Python文件执行Ruff，不在mutable树运行宽suite。

本轮非docs源共34文件：5个产品文件（2 Python、3 JS）、2个w11/w12示例fixture/验证、24个browser测试、1个共享envelope helper、2个新unit文件。准确父版本/当前SHA及逐组未变证明见 [源身份](r4-focused-evidence-20261015/integration-source-identity.json)，SHA256 `81b8ae273013e30d3f60cc9026d112100690f9deda8fb96a9ec769483fb6ad6f`。四Role方法、活动contracts、版本/build hook、严格production resolver以及37AC/13CQ ledger全部与8223逐字节相同；没有另扩schema或迁移协议。小型focused证据为13份逐字节报告/log副本（112999 bytes）及2份明确标注Owner派生的映射/源清单，manifest SHA256 `305bfcd3cd76fa242c7ccf2ffa5f38358c1e8bbc716cf2f274f2a7ac7659f018`；未复制浏览器session、Store、授权key或原带token包。raw日志保留原空白，不为diff格式清洗证据。

所有结果为offline wheelhouse、短TMPDIR、独立basetemp、实际Chromium和专属absolutePython的live focused证据，不是clean fixed R4 broad/CI。Root将在统一commit后建立新snapshot/env/build/install、严格字节审计、fixed unit/render/browser与installed UI/recovery、独立code/behavior/UI受影响复审；新exact-head7CI通过后才决定merge。方法/活动合同、物理转换、原始对象与原人类延期安排不改。版本仍1.0.0rc3/Entry13；无真实HOME切换，无新provider/native/human/desktop/公平效果声称，未知token/费用保持未知。
