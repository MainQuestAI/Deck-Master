# 03｜数据、版本与状态契约

## 03.1 五对象，不新增阶段注册平台

正式草案见contracts/五份JSON Schema（Draft 2020-12）。落地后只保留安装资源中的一份schema真源；docs引用它，不维护并行同名不同形状。`examples/`的合成对象和引用可用来验合同，不是运行成绩。

| 对象 | 权威内容 | 不负责 |
| --- | --- | --- |
| Document v1 | 当前任务、资料、design_context、页顺序与每页当前对象ref、任务/检查ref、当前输出 | 不把所有维度压成一个completed |
| PagePackage v2 | 完整对外正文、备注、设计意图、业务节点边、引用、内部说明 | 不含编译批准、流程阶段、重复order |
| Artifact v1 | 文件字节、角色、依赖、来源、生成时输入、原图区域期待 | 不从hash推专业质量 |
| Task v1 | 一次Host工作、页面范围、输入依赖、结果、取消/失败 | 不规定每个用户走固定九阶段 |
| Review v1 | 实际检查对象、观察、发现、结论及当前性依赖 | 不用两个名称证明独立、不默认高分 |

JSON Schema只检查可解析格式、必要字段与枚举；跨引用、内容原子覆盖、计算等由明确语义校验承担。专业判断由实际方法与审阅承担，不靠schema计分。

## 03.2 自动项目目录

```text
<output-project>/
  .deckmaster/
    current.json                        # {format,revision_id}，唯一当前指针
    revisions/<revision_id>.json         # 不可变Document快照
    objects/<sha前2位>/<sha>.<ext>         # Page/Task/Review/Artifact JSON及二进制资源
    staging/<operation_id>/...           # 工作临时目录，不能直接成为当前产物
    write.lock                          # macOS/Linux advisory文件锁
  exports/<export_id>/...                # 用户明确导出，不反向成为上游蓝图
```

源文件默认留原位置，Document.sources记录原URI、已知原文件hash和页/段定位。`original_sha256`允许null或缺省；未知不填全零、不对URI字符串求hash，也不拿提取文本hash替代原文件hash。能实际读取的提取文本、已保存媒体分别以extract/Artifact.file记录自己的真实字节hash。既有可信测得的原文件hash可保留，文件后来不可达不抹掉它；只从旧声明拿到但无法核实的hash保留在原始导入说明中，不冒充本次测量。已产生的提取文本可存objects；大原文件无需自动复制，离线可移植包仅在用户要求且允许包含时打包。源文件不可达时已有正文/产物仍可查看、导出审阅稿；依赖原文的再创作/证据检查明确缺口，不假装原文已读。

current指针写在最后。对象路径中的sha必须匹配实际字节；JSON对象使用统一canonical编码计算，媒体直接字节计算。schema不使用全零hash作未知值；未知为null或该字段缺省。用户原路径不是content provider prompt的一部分。

## 03.3 Document语义

`pages`数组就是顺序；每项page_id唯一，引用的Page.page_id一致。删页是新Document不再引用，旧Page和旧产物保留。重排不修改稳定page_id；若可见页码或跨页引用随之变化，系统明确更新相关Page/产物。不得用目录glob把遗留页重新拼回。

`task.brief`保留原始任务与已确认决定，不能因方法迭代被自动改写成另一目标。`page_limit`只表示明确上限；用户明确要求精确页数则在brief及验证中记录精确约束，而不是补通用章节。未指定为null。

`Document.change`记录本次operation_id、变更种类、说明和read_set，用于幂等恢复；历史父链可重建操作索引，索引缓存不成为另一权威。

Document内Task/Review数组引用每个逻辑对象的最新版本；旧记录可通过历史Document读取。对象更新写新blob再换ref，不就地修改。全稿current revision变化不自动使未改页面的artifact过期。

`policy.professional_review_required_for_delivery`只有用户明确要求人类专业复核作为交付条件时为true；默认false并不声称“已获得专业认可”，它只是允许方法/工程试行导出。业务认可在view中独立展示。

### 03.3a 唯一制作配置：Document.design_context

配置内联于当前Document，随Document快照版本化，不新建配置平台或第六种永久对象。create规范化默认值并持久化；Host、prompt、compiler和UI只能解析这个快照，不能各自补默认。默认1600×900逻辑像素、40/3×7.5英寸、zh-CN、contain；用户指定4:3等时按输入保存。原SVG viewBox原点/范围必须由解析器读取，不能硬编码缩放。

| 字段 | 真实消费者与约束 |
| --- | --- |
| canvas.width_px/height_px/slide_width_in/slide_height_in/fit | prompt布局、SVG归一化、PPT大小与UI比例；正数；fit首版只有contain；逻辑与物理比例不同要显式留白提示，不静默拉伸/裁切 |
| language | prompt文字与字体选择；Page可覆盖语言，不修改原资料语言 |
| fonts[] | font_id、family、face、weight、可选asset_id、明确fallback_font_ids；compiler解析实际字体；不存用户机器绝对路径 |
| styles[]、default_style_id | style_id、colors、typography（正文/标题font_id及字号）、layout_notes；prompt与compiler共用；不是任意JSON配置袋 |
| assets[] | asset_id、kind（logo/icon/image/font）、Artifact Ref及external_use；Artifact.role=asset，file为项目内不可变实际字节 |
| allowed_asset_ids | 本项目准许本轮外发/设计使用的资产集合；不是所有读入材料自动获准上传 |

`Page.visual_spec.style_ref`只指当前Document.styles中的style_id，不是文件路径或URL。未写时继承default_style_id。Page.design_overrides可覆盖language、已登记的body/heading font_id及allowed_asset_ids；后者只能缩小Document许可集合，不能提权。一个PPT文件使用同一物理页面大小，不支持各Page覆盖slide_size；不同源图比例按contain处理。

解析顺序：Document默认style→Page.style_ref→明确Page覆盖；未知style/font/asset ID返回明确配置问题，不回退到隐藏默认。纯素材导入不自动选用该素材。`create --design`接用户指定配置；`import asset`将显式选择的本地字节存为Artifact并登记asset_id；`design update`提交新Document。`--design`/`design update`的临时输入整体使用design_context形状；其中assets项在首次导入时允许用`file`代替`artifact`，如`{asset_id:"demo-logo",kind:"logo",file:"./logo.svg",external_use:"allowed"}`。这只是接收格式，先按配置文件目录解析file并复制真实字节、建立asset Artifact，再转换为正式Document中的artifact Ref；file与artifact不可并用。既有项目可以直接使用已登记Artifact Ref。所有assets规范化后再一次验证完整设计，不把临时路径写入权威Document。

`design update`按完整配置替换进行原子提交，不作任意深层隐式merge；原有正在被Page引用的style/font/asset被删除时拒绝并列出受影响页，或与明确的Page变更同事务提交。永久Ref只指项目内对象，移动项目不要求旧Logo路径复活。

字体二进制仅在用户提供并允许本地复制时保存为私有asset，绝不随公开发行/Spec包附带。选择系统字体时family/face是需求而非保真证据；编译记录实际匹配字体文件hash与版本为toolchain依赖。缺指定字体只影响需要该字体的生成/编译，旧预览仍可看；只能使用已声明fallback并报告实际替代，否则needs_tool。fallback实际发生后也不得声称原指定字体完全还原。

已保存资产Ref的hash始终必填且逐字节核对；来源original_sha256的未知特例不放宽这里。restricted素材不能因为出现在allowed_asset_ids就外发；unspecified须由已有任务授权明确可用，否则先澄清该项，不制造全项目问卷。字体配置可向图像工具传family与设计说明，但默认不上传字体二进制。

依赖用解析后的**当前页有效配置和实际用到资产**，不是整段Document hash。样式覆盖其他页时，仅这些页失效；修改未用style不影响成品。相同asset_id换字节、实际字体换版本、全局画布变更均使相应依赖过期。原始已生成蓝图仍是不可变历史；不按新版style回写它的生成参数。

## 03.4 PagePackage v2的显式正文

沿用v1的customer_visible/internal_only概念，使用v2明确字段与跨版本转换。body_blocks首轮支持paragraph、bullets（嵌套items）、table；表格cells使用display_text保持小数、千分位、百分号和单位，value用于可复算但不能取代展示文字。0、0.0、空字符串、null语义不同，不用`x or fallback`处理数字/透明度。

标题、副标题、所有正文条目、表头/单元格、labels、footnotes、callouts都是可见文字。节点target/id、证据ID、layout metadata不自动成为正文。备注是用户可编辑业务备注，与内部指令分开；允许被明确检查的正常业务备注，不默认全部删除。

`visible_atoms(page)`返回稳定atom_id、JSON Pointer、显示文字和业务必要性。atom_id基于block/item/cell稳定ID而非数组位置；JSON Pointer仅作定位。规范化输出的label_ref/responsibility_refs使用atom ID，不再留下依赖数组下标的正文关系；旧Pointer仅允许在导入当前旧Page时一次性解析并改写。具体规则见03.10及完整往返例。所有非空对外正文默认应保留。允许改写/合并时在内容编辑阶段产生新Page，不让渲染阶段悄悄截断。一个atom可由多段SVG文字实现，但应能重组其内容；不能为凑引用加入微字、透明文字或重复节点名字。

无法识别的旧body对象不能直接忽略；legacy转换返回需要规范化的路径，Host决定映射成哪种正文块。无需为覆盖任意旧JSON建立开放类型注册系统。

## 03.5 设计关系与视觉期待

visual_spec.intent是设计任务，layout_hint是参考，不是固定坐标模板。nodes有稳定ID、正文label_ref、existing/proposed等状态，edges有实际from/to、方向、关系及可选可见label_ref。技术说明只读/回写、建设中/已有等必须与正文一致。

结构边的`relationship`是语义说明，不自动要求在画面重复印字；有label_ref才必须显示标签。已有节点名不必在每条边再印一次。关系可以用拓扑、分组、方向等表达，检查应验证关系而不是简单比文字。

原图视觉期待在blueprint Artifact.reference_regions中，来自实际阅图而非SVG输出。bbox为归一化x/y/w/h四数，程序校验长度、正面积和范围。区域重要性分essential/supporting/decorative，只对当前图的真实区域登记；原图未识别不能记无图标满覆盖。

## 03.6 Artifact版本、来源与双向编辑

Artifact.file是实际文件Ref；derived_from描述已知数据依赖。`provenance.generated_from_page`记录图当时对应的Page版本；`submitted_prompt`只保存实际提交内容，Host工具不可提供时为null并注明不可核实，不能根据当前Page倒填旧prompt。

蓝图新增文案被编辑接受后，新Page可以继续引用原图；SVG同时引用“原图Artifact”和“编辑后Page”。这不是来源冲突。若文字变化使原布局不再适用，生产任务应重排相应区域或明确重新设计，不为两个词修改强迫重生整张图。

禁止已知本页svg_preview/ppt_preview及其派生产物被标为该结果的原始独立blueprint。按角色/已知依赖方向检查，不能只检查两个文件hash不同。用户明确要求从成品开始新设计时，建立新设计任务和新的起点，历史还原验收不回填通过。

## 03.7 依赖指纹分层

| 指纹 | 组成 | 变化后的动作 |
| --- | --- | --- |
| 内容/证据 | 当前任务中相关条件、Page正文与节点关系、实际来源版本 | 重新判断受影响内容和审阅 |
| 视觉制作 | Page展示文字、design、选定原图、资产与样式 | 使相应SVG/页面预览过期 |
| 编译/渲染 | 有序SVG、实际资产、画布、字体和编译/渲染版本 | 重编译/渲染，不重新写正文或生图 |
| 检查 | 被检查Artifact与适用方法/规则版本、必要来源 | 只使该检查失效 |
| 管理记录 | 反馈说明、预算记录、操作者、日志时间 | 不改变前四项，除非修改了真实制作参数 |

依赖种类可在现有字段内表达，不再建通用图谱平台。全局实际输入如主题风格改变可以影响多页；不能为了局部缓存忽略它。未知依赖不能假装没有，先保守重新检查，再在已识别格式内缩小范围。

## 03.8 状态派生规则

ProjectView展示四维：content、production、checks、professional_use。例：`content=ready_for_review, production=rendered, checks=needs_revision, professional_use=not_evaluated`。这种状态允许查看和请求修改，但不能输出“已验收通过”。

Task.kind分Host任务（compose/blueprint/reconstruct/review/repair）和本地确定性动作（compile/render/check）。这是同一Task结构的执行区分，不增加用户阶段或通用调度平台。本地动作queued→running→completed/failed，Host任务awaiting_host→running→completed/failed；cancelled/superseded为不可再提交的终态。completed必须由实际结果校验和原子采用产生，不能接受Host自填的完成字段。

Task.call_allowances是项目事务分配的外部调用名额，不由Host结果覆盖；usage仅调用后观察。取消、重试、项目恢复均保留已消耗和未知调用事实，见08.6。

Task状态是执行事实。没有Host接手就是awaiting_host，点击按钮只创建任务不变running。Artifact存在但相关输入变化，view标stale并仍可查看旧版。Review.status=pass但依赖不匹配，view显示历史通过/当前未检查；不得改写旧Review自身的结论。

整套完成必须以当前页集合全部有预期产物、必要检查当前且无must_fix/未裁决必需问题为依据。局部文件已生成不等于整稿完成。没有人类专业阅稿始终不显示human-approved。

## 03.9 必须实施的跨对象校验

同run/同project引用、唯一页ID与顺序、节点边端点存在、label_ref指向可见正文、表列ID/cell匹配、citation源存在、对象hash一致、图片/PPT实际可读、取消/旧输入提交拒绝，以及未来未知schema不写入旧数据。格式错误返回明确路径，不通过丢弃字段来完成导入。

Current pointer写入事务和文件锁规范见08章。程序不把源引用存在解释为语义证据充分，不把所有非空字段列成必须引用历史事实。

## 03.10 稳定可见atom ID规则

采用`atom:<page_id>:<类别>:<稳定ID>:<字段>`，不取正文hash、数组下标、显示顺序。固定标题为`atom:p09:title`，副标题为`atom:p09:subtitle`；块标题/正文为`atom:p09:block:service:heading`或`...:text`；所有层级条目在页内item ID唯一，正文为`atom:p09:item:version:text`；表头为`atom:p09:column:sample:count:label`，单元格为`atom:p09:cell:sample:need:count:display_text`；脚注/标签/callout按其id组成。

已有ID全部保留。缺ID时规范化器一次分配UUID/稳定持久标识并把规范化Page与映射返回Host；同operation重试复用同一结果，不按运行时重新发号。重排、修改文字、将同一条目移到另一嵌套位置不变item ID；复制新条目必须新ID；删除后不能给无关内容复用ID。拆分/合并产生新ID并在本次编辑说明中列old→new映射，相关node/citation/绑定由Host显式更新；不要构建长期ID映射平台。

显示文字、JSON Pointer和ID分开。节点只引用明确的atom，不引用整个items集合要求渲染器再自行猜测。程序可为目标词提供候选匹配，但不能因文字相同就自动把两个业务对象当同一身份。完整新增、重排、改字往返例见`examples/roundtrips/atom-identity.json`。

## 03.11 v1.1跨对象补充校验

design_context中的style/font/asset唯一，所有引用存在；Page许可集合是Document许可子集；字体fallback无环；asset角色和真实字节匹配；全稿单一物理画布。项目移动后只能从对象Ref或重新解析并验证的系统字体加载，不读取旧绝对路径。

来源hash未知不阻止读取已存提取文本/媒体；依赖身份可用已保存extract或注册信息的canonical hash，但必须标为该对象/声明的hash，不能称原文件hash。具体事实的证据强度仍由实际资料和审阅决定。

Review.fixed必须是针对新产物的真实复查版本，replaces连接旧Review，不能只改一个字段；Task额度分配、begin和settle按08.6在同一项目事务内处理。JSON Schema通过只证明格式，不证明上述跨对象条件或业务检查已经成立。
