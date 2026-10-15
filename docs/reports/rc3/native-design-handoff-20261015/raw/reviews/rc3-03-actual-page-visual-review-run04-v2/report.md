# RC3-03 run04 SVGv2 实际非作者复评

**本轮结论：内容 PASS、保真 PASS、可读性 FAIL。F07 开放 must_fix，需本页表格垂直留白修复。** F05 物理尺寸、F06 字号仅对本轮精确新产物关闭。旧 run02 三项 PASS/F05 HOLD、run03 字号 FAIL 原件和记录保持不变。

正式 Task `405175566aaf`，operation `review-ce4a9a178d7f`，produced_against `b5b2769e8f55a43eb0cbae3311af403b714b97baea1cf624b574900192f755aa`。真实 SDK task_start 已声明 changes.v1 与 content_requirements_v1/style_recipe/style_recipe_v3；真实 accept_result 返回 accepted，Task completed，revision `cca1f3148aa24ab69ba282331e375177`。SDK 接受记录不等于其评阅结果通过：已读回确认第三项为 fail。

本评阅者为 `/root/rc3_03_actual_page_visual_review`，v2 independent_host/host_attested，identity_receipt=null。Root 已有本轮实际 followup/claim 观察；本轮 agent FINAL/completed 完成观察要在实际发生之后另存。没有人类、专业或平台签名，没有 preproduction receipt selector。

## 实际观察

本轮重新以 view_image(original) 查看原始蓝图、新 SVG 预览、新正确物理 PPT 渲染，并先保存 pretechnical-visual-judgment.json，再读技术数据。完整固定 packet 五文件与新 SVG 已读。全部17可见原子逐句可辨，限定语、4节点/3向右关系、2×3数据表行列归属、整体层级与阅读顺序保留；SVG及PPT原生文本拼接均17/17与固定正文相等，notes全文也相等。没有把Root机械PASS或旧PASS当成新视觉结论。

保留的限定包括仍待验证、只读/许可资料/来源、采用或未采用及原因、真实未知及原因、不能猜填、能补与不能补及恢复条件、启动前明确、无法确认/冲突/不适用/问题仍不确定、候选不可直接采用、继续未决、资料不等于故障解决、人员正式提交、AI不自动提交/修改/关闭、非诊断或批准。

新字号更大、表格更密，但文字没有裁断、遮盖或串行。条件句位于共同主链框内。旧F01仍修复；外框净边距至少49.25px，F02保持修复；表底736到提示顶762，计描边净空约24.75逻辑px，F03保持修复。原图1672×941及8057905生成来源不改写，F04尺寸差异保留。

| 实际图 | 尺寸 | SHA256 |
|---|---:|---|
| original_blueprint | 1672×941 | `8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c` |
| current_v2_svg_preview | 1600×900 | `989e796fef7d9e7240786fc6a0b1ff53b7761b8da88f94f6819229a8ca9a99b1` |
| current_v2_physical_ppt_render | 1601×900 | `35358c312eed62a02cf2bc25fe6cb83fb5aaa965ec5973bf3e8cd9a0e1d4a840` |

## F07：实际PPT单元格底部净空不足

固定要求位于 workorder `/resolved_design_context/recipe_parameters/spacing`：“单元格内距至少12px”。新 SVG 与新 PPT 之间观察到约3px native墨迹基线差；不据此推定一般converter缺陷。

**单位：** SVG 为1600×900逻辑像素；正确物理PPT的实际PNG为1601×900，约120dpi，纵向900px对应7.5in。原生1逻辑px=7620EMU。1280×720是物理96ppi的compiler canvas，不能混作本次截图测量单位。横向导出多1px取整不影响这些纵向结论。

| 对象 | SVG对应留白 | 实际PPT墨迹及边线 | 当前实际净空 |
|---|---|---|---|
| 三列表头 | 墨迹底y478、名义边线y492，空行13px | 墨迹底y481，边线像素y491/492 | 约9–10px |
| unknown动作/交接三行格 | 墨迹底y599、边线y614，空行14px | 墨迹底y602，边线像素y613/614 | 约10–11px |
| unsuitable三行格 | 墨迹底y721、边线y736，空行14px | 墨迹底y724，边线像素y735/736 | 约10–11px |

以墨迹到墨迹的净空度量，不能把上下两个墨迹像素也计作空白。原生XML表头边几何y=492、分行y=614、表底y=736均与SVG一致；示例末行文字框top=571.6/693.6逻辑px、height45px、bodyPr零内距。完整原生XML和字段另存，PNG蓝线像素及墨迹阈值也另存；约1px栅格不确定性不能消除表头缺口。

F07不是“文字不可读”或语义失真指控，而是明确工程下限未达。修复只需在本页重新分配表格垂直布局/基线，保持完整正文、实际18pt/30pt与其他外边距和模块间隔，再实际渲染核对≥12px。未自行改稿或PPT。

原始像素crop（无缩放、无标注、原图未覆盖）及其sourceSHA、精确box保存在 F07-raw-pixel-crop-manifest.json；本轮还实际查看了SVG/PPT表头和unknown末行四张crop。相关文件为 F07-precise-measurement.json、actual-header-cell-clearance.json、actual-cell-clearance-followup.json、read-only-raster-spacing-check.json。

## F05/F06新产物关闭及失败历史

新SVG SHA `82d3430688b9c4ff2fb89cedb99cabfd643fbb39cb03d274b65a60a2de245ded`；新PPTX SHA `4c951dde9044506ad7cade8e06de13c50ed25e5173210265cd2b7c61d2c38ef6`；新render SHA `35358c312eed62a02cf2bc25fe6cb83fb5aaa965ec5973bf3e8cd9a0e1d4a840`。

本人直接读取PPTX XML：cx=12192000、cy=6858000EMU，精确13.333333333333334×7.5in，F05物理尺寸对该artifact fixed。type仍为screen4x3，作为A02 metadata advisory如实保留；实际cx/cy为16:9且未见拉伸，不扩写未知桌面影响。

本人按两个明确heading atom（title、exceptions-heading）识别角色，不根据大小或加粗反推：36个可见run中2个heading均30pt，其余34个body均18pt；60个原生shape、0picture/0media，F06对新artifact fixed。

旧run02 PPTX c9317900…仍为15240000×8572500EMU；旧run03正确物理PPTX 8affb895…的35个run为14.4/24pt，全部低于各自角色门槛。本人读取旧实物确认了两段历史；不回写旧记录。

归因证据：Root correction文件 SHA `3319dd39cb73501370f2793dab415a4704ed22da3cb857c905ad1d486c789e9b`；本人只读安装pipeline.py第378行，实际使用slide_width_in*96与slide_height_in*96。Root初始pixel-only helper调用及“18pt=24px”作者指令遗漏0.8contain缩放，已据实际来源修正；没有据此声称正式pipeline源码存在该单位缺陷。

## 精确正式绑定

| Subject | 不可变对象引用 |
|---|---|
| Page | `.deckmaster/objects/cd/cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b.json` |
| Blueprint | `.deckmaster/objects/dc/dc12785b9efa870484a4eb578eef8859880b6d3769c363fa928fe302ff577526.json` |
| SVGv2 | `.deckmaster/objects/b8/b8179a2a1342e1cdfb165dc41020349705383ce90caf6b7e09a6a2a20f0968f2.json` |
| SVG preview | `.deckmaster/objects/05/05c36c91d4feffd1acbe35811012eb3ae5e6fff826cfc88d8c8cfe08b7350611.json` |

| Dependency | SHA256 |
|---|---|
| content:page:p04 | `cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b` |
| blueprint:p04 | `8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c` |
| artifact:svg:p04 | `82d3430688b9c4ff2fb89cedb99cabfd643fbb39cb03d274b65a60a2de245ded` |
| style:p04 | `aea8ea4b43ab242f7f75a4bef462309c4e6df9795a535dd663ed208f76b74068` |

无allowed assets。已逐字节核对实际查看的原图、新SVG、新预览与当前stored artifact file一致。旧Task inputs_current=false，本轮记录通过replaces连接同一逻辑评阅的旧不可变记录，所有观察与subjects均为本轮新实物；没有拿旧结果对新subject放行。

## SDK与证据

三项accepted review对象按content/fidelity/readability顺序为：

- `e16ca878b58e4c734812352717a03559026ed3f4890c56e2a2810e6dae76fe8b`
- `19db11bb1197054acbbff65b587cb780c8c4879154352d1eac82a0e9ef7fea3d`
- `eda62a8962c5ad9fae874835b899112fbe072ea152770fdce4d616a02efade04`

raw claim/accept request/response、payload、实际接收读回、assessment、当前subjects/deps、读入哈希、独立逐run物理/字体检查、17原子核对、F05/F06精确closure、F07坐标/原始crop均在本目录。所有Page entries、Narrative、Plan、outputs接收前后不变；旧report与assessment的原SHA也另存核对。没有SDK拒绝、generation调用、自动修稿或源码修改。

capabilities仍为providers=[]、independent_review_receipts=false、human_review_receipts=false、review_channel_status=needs_reviewer；Host层来源不冒充严格平台或人类receipt。本地PPTX/渲染是明确hash的补充实物，工作单ppt_preview和outputs仍为空，不伪装正式输出交付。

**未运行/未关闭：** 人类/专业、Owner、真实受众理解、现场投影、PowerPoint桌面、公平E2/E3、其他七页、完整八页及整体RC3验收。A01异常表需完整阅读的限制保留。当前仅收敛到复现的F07；待Root新产物后才能进行新的针对性复测。
