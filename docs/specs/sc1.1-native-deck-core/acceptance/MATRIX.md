# SC-1.1 Native Deck Core 验收矩阵

共64项；全部初始not_run。L1允许显式fixtures；L2必须真实工具；L3为真实客户效果。产品测试、环境与证据需要Codex核验。

| ID | 目标 | 层级 | 输入/动作 | 必须结果 |
|---|---|---|---|---|
| GOV-01 | 旧约束正式替换 | L1 | 原SC1 D04及多处Agent/验收指引；比对所有执行入口 | 默认不再要求PPT Master；旧文有superseded指向；未冲突要求保留 |
| GOV-02 | 没有整库换名内置 | L2 | 默认release安装树；核对依赖闭包和运行调用轨迹 | 仅本仓公共内核/必要组件；无完整上游workflow/后端项目运行依赖 |
| GOV-03 | PR30基线保护 | L1 | PR30仍open或已有后继、用户未提交修改；建立增量工作分支和差异图 | 不擅merge/reset/revert或删除用户内容；明确实际基线 |
| GOV-04 | 工程与效果状态分离 | L1 | 存在未执行L2与仅缺L3两种情况；生成交付总结 | 前者in_progress；仅全部工程闭环后可outcome_pending；superseded不当passed |
| IND-01 | 隔离默认安装真编译 | L2 | 新HOME，无外部PPT Master/Skill/binding/PATH fallback；安装release并真实native compile/render | 主要对象原生且有实际产物；未读取/安装/绑定外部产品 |
| IND-02 | 不隐式克隆或调用外部产品 | L2 | 默认任务已授权宿主工具，外部后端路径设为哨兵；运行默认链并记录文件/进程访问 | 无git clone PPT Master、无外部svg_to_pptx命令、无哨兵访问 |
| IND-03 | 默认入口一致 | L2 | 同一新Run；分别CLI、主Skill、next-step、doctor、Review Desk、final-readiness | 统一native route与revision；无backend bind提示或例外强行覆盖ready |
| IND-04 | library none真入口 | L2 | 没有ppt-lib和索引；CLI autoplan --library-mode none并resume/autopilot | 参数被接受；不调用库/不产生伪real selection/不使用fixture；每页生产决策真实 |
| IND-05 | 宿主未知不伪报就绪 | L1 | 只存在Skill声明，没有真实工具检测；查询image_blueprint task readiness | host=unknown/blocked；软件已装不等于图片工具可用 |
| IND-06 | 可选依赖不污染任务 | L1 | native必要依赖齐，legacy/backend/library缺失；查询编译、无库新建和旧Run继续三任务 | 前两不被legacy阻断；旧任务缺项明确只影响其自身 |
| IND-07 | 安装产物可脱离源码目录 | L2 | release已安装，原checkout隔离；从installed launcher运行编译/图形方法/schema检查 | 包内引用可达；无源码绝对路径；没有缺schemas/methods |
| IND-08 | 显式direct与禁止静默fallback | L2 | ImageGen缺失，有SVG能力；分别默认image与已授权direct_svg | 默认准确阻断；direct执行真实内核；不伪造图片来源 |
| CNT-01 | Package状态规范 | L1 | ready_for_build、legacy ready、draft三组；按producer→build真实接口验证 | 规范值通过；legacy有凭据才迁移；draft不被字符串洗白 |
| CNT-02 | 消费当前真实内容 | L2 | Package正文改变、旧preview未变；默认native build并回读 | 最终文字来自新Package，不使用旧preview/模板占位 |
| CNT-03 | 内容锁只由公共内容产生 | L1 | 批准Narrative/Package与图片中错误文字；建立锁并重建SVG | 不从图片回填事实或证据；仅修复图片表达 |
| CNT-04 | MBB单向投影 | L2 | 已有有效公共主线和用户选择；进入默认Builder及兼容HD | 无新MBB访谈/第二主线；projection hash追随公共源 |
| CNT-05 | 推荐不等于选择 | L1 | 有recommended candidate但无必要用户选择；推进须用户裁决的叙事取舍 | 不把推荐自动签成批准；已有明确选择不重复问 |
| CNT-06 | 架构和数字跨视图一致 | L2 | 蓝图边方向错误、单位与锁不一致；Agent重建+回读+内容检查 | 按模型/锁纠正并记录delta；PPTX和正文一致 |
| CNT-07 | 原材料冷启动无循环 | L2 | 仅已有原材料/目标/授权，无逐页稿/Package；主入口运行至页面生产 | 先实际形成方案/主线再产出非空Package；不要求空Package作前置 |
| CMP-01 | 单内核提取差分 | L2 | 相同七类SVG/Scene/Lock/assets；提取前后编译比较对象/视觉 | 语义/几何/层序无非授权退步；不靠ZIPhash唯一判等 |
| CMP-02 | 文字真正原生 | L2 | 中文长文本、英文、数字和单位；编译/桌面编辑一个文字框/保存再开 | 文字可改，不是轮廓/图片；关键文字完整准确 |
| CMP-03 | 主要形状路径原生 | L2 | 架构节点、箭头、曲线、图例；编译并编辑节点与路径 | 独立原生对象；关系/方向可追踪 |
| CMP-04 | 分组与层序 | L2 | 嵌套分组/遮挡/透明叠层；编译回读并修改group | 分组真实、层序/几何一致；主元素不丢 |
| CMP-05 | 零透明度等边界 | L1 | opacity=0、gradient stop alpha=0和正常渐变；共享parser→compiler→paint inventory | 零值不变一；验证与编译支持同一子集 |
| CMP-06 | 支持矩阵与unsupported | L1 | 支持的path/transform/use与脚本/外链/非法滤镜；校验和编译 | 已支持子集回归不退；不支持精确报element；不静默删/栅格化 |
| CMP-07 | 坐标和非16比9源 | L2 | 不同viewBox和旧1672x941样例；统一contain映射到16:9 | 无拉伸/错比例；文字stroke和effect坐标一致 |
| CMP-08 | 资产和路径边界 | L1 | 未登记图、跨Run、../、absolute、symlink逃逸；导入编译请求 | 输入拒绝且不访问越界；登记照片为独立对象 |
| CMP-09 | 无整页套壳 | L2 | 整页PNG、SVG图嵌入、分块拼图、隐藏字层和正常原生页；对象检查和实际编辑 | 伪编辑全部拒绝，主要业务图形原生页通过 |
| CMP-10 | 编译与回读错误不伪完成 | L2 | 字体/renderer缺失、对象漏失、PPTX渲染失败；真实构建与失败注入 | 准确blocked/failed，无completed/客户ready；实际trace有效 |
| HST-01 | 新图片真实生成 | L2 | 批准内容与具备图片工具的宿主；实际生成蓝图再读取 | 保留真实输出hash/action与可得元数据；fixture/旧参考不计fresh |
| HST-02 | 不伪造服务元数据 | L1 | 宿主无request_id或nonce回显；接受host观测产物 | null+证据等级可解释；不造ID/签名；无观测声明不算真实执行 |
| HST-03 | 锁定内容与蓝图隔离 | L2 | 图片错字/漏限定/含内部标注；蓝图审查与SVG重建 | 纠正事实/标注，保留业务限定；证据ID/路径不露出 |
| HST-04 | 图片与SVG实际比较 | L2 | 有实际蓝图和一次布局失败SVG；渲染全页与关键局部比较 | 识别失败并定向修复，不能只写pass |
| HST-05 | 代表页与批量继续 | L2 | 锁定风格，代表页通过，其余页部分失败；处理pending/rework | 仅失败页重试；无重复用户确认/无关页重做 |
| HST-06 | 已有SVG编译不要求新ImageGen | L2 | 已批准SVG/内容，当前图片工具不可用；执行compile_approved_svg | 按实际编译能力继续；不新生成，不伪报fresh图片 |
| HST-07 | 有限图片修复 | L2 | 同一页ImageGen/重建连续失败；执行3次尝试后继续 | 计失败/超时，达到上限停且保留成果；不换action ID重置预算 |
| WF-01 | 固定route优先 | L1 | 新native Run残留旧HD目录，旧Run已有manifest；status/next-step | 按route/current解析；不因目录存在自动走错引擎 |
| WF-02 | 缺语义门正确动作 | L1 | render/delivery/safety已过，semantic缺失；next-step→执行→import→resume | 派发语义审查，不无限执行render gate |
| WF-03 | Agent专业动作真接线 | L2 | 材料中已有答案、缺专业主张，工具授权齐；autopilot连续执行 | 提取/推理/写回真实调用，无只helper存在未调用；合法否定接受 |
| WF-04 | 迟到及同ID冲突 | L1 | 旧revision action晚到、同ID同hash和异hash；并发接受结果 | 旧拒绝；同内容幂等；不同输出冲突，不覆盖新版本 |
| WF-05 | 第二文件中断整批一致 | L1 | 一次动作含SVG/Scene/manifest；第2文件/marker/激活处故障及重启 | 读者只见完整旧或完整新revision，不接受逐文件rename解释 |
| WF-06 | 权限和停止有效 | L1 | 只授权P001，尝试改其他页或停止后回传；action acceptance | scope/path/permission/cancel检查实际生效；不写批准/锁定事实 |
| WF-07 | 预算包含失败 | L1 | 同finding有failed/timeout/dispatched未commit尝试；重试或换action ID | 预算真实消耗，不能只数committed；明确剩余 |
| WF-08 | 精准失效与局部修改 | L2 | 单页配色变更及跨页组件变更两组；impact→repair→build | 前者只影响视觉/产物/最终批准；后者影响相关正文/图/阶段；无关决定保留 |
| QA-01 | 语义门精确匹配 | L1 | 只有external_visual/evidence的pass；计算semantic required gate | 不满足语义；必须真实scope=semantic且完整覆盖 |
| QA-02 | Package改而index不变 | L1 | 已审查后直接改变一个Package正文；gate freshness/final-readiness | 旧语义过期；不能只看indexhash |
| QA-03 | 空pass和漏页拒绝 | L1 | 仅reviewer/pass或缺六维/页覆盖；导入review v2 | 拒绝并指出缺项；不能靠声明通过 |
| QA-04 | 严重问题压过summary | L1 | summary pass且存在P0/P1；aggregate gates与override | 按finding阻断；P0不可覆盖；P1按当前政策授权 |
| QA-05 | 视觉与编译证明分层 | L2 | 高像素相似但箭头反向，另一组SVG→PPTX误差超限；完整visual/readback评估 | 两组分别识别；不单用SSIM或内容正确替代其他门 |
| QA-06 | 正式文件完整扫描 | L2 | notes/隐藏页/alt text/metadata有内部路径，正文有必要业务限定；客户投影与导出检查 | 清理/阻断内部内容但不删业务限定；当前hash再验 |
| QA-07 | 批准绑定实际新版 | L2 | 批准后改字/页序/重编译；导出新版及旧版 | 新版需对应批准；旧已批准文件保留且标历史 |
| QA-08 | 修复后复审闭环 | L2 | 已定位具体对象finding且Agent可修复；自动定向修订/渲染/复审 | 问题被实际验证解决；未修复不因新summary过门 |
| MIG-01 | 旧HD可读与同核复用 | L2 | 旧HD产物/批准SVG和旧路径；只读/兼容继续/显式迁移 | 旧数据保留，内核共用，无新双写主线 |
| MIG-02 | 旧standard隔离 | L2 | 旧PPT Master Run无backend，新native Run依赖齐；分别diagnose/继续/新建 | 旧状态如实；不影响native，不自动安装绑定 |
| MIG-03 | 迁移输入改变 | L1 | dry-run后源文件改变；apply旧计划 | 拒绝过时计划，源批准文件不变 |
| MIG-04 | 迁移故障回滚 | L2 | 新revision任一编译/校验失败；迁移/激活 | 旧current完整保留；无伪新seal/approval |
| MIG-05 | 安装所有权与数据保护 | L2 | 独立ppt-* real dir、资产与索引存在；安装升级卸载 | 只动自有软件/链接，不删除外部或客户数据 |
| MIG-06 | 软件回滚不改新数据 | L2 | 新格式Run已生成后回滚软件；旧程序读取/尝试写 | 新数据保留；不支持安全写则明确只读，无破坏转换 |
| UAT-01 | 真实默认两页冷启动 | L2 | 干净安装与合成批准内容/真实宿主，无外部后端；image→SVG→PPTX→回读 | 真实默认链通过；有输出和执行证据，不用direct替代 |
| UAT-02 | 真实七类页面与编辑 | L2 | 七类样页含架构/表格/数据/高密中文；真实宿主重建、编译、桌面编辑 | 平均视觉≥4且各页≥3.5，内容/关系无关键错；编辑实证 |
| UAT-03 | 原材料完整Solution Deck | L2 | 仅原材料/目标/授权，无逐页稿，无历史库；默认8—12页全链到批准导出 | Agent承担内容/图形/修复；无外部绑定；必要研究真实执行 |
| UAT-04 | 局部修改端到端 | L2 | UAT已批准deck；请求单页修订及关系变更，再导出 | 只处理影响集，旧版保留，新版经当前检查和批准 |
| UAT-05 | 继承真实客户配对 | L3 | 原SC1三类授权客户素材与可比baseline；每类两次配对/冻结首稿/记录主动投入 | 按SC1投入/可保留页/六维阈值验收；失败全记录；不可比标N/A |
| UAT-06 | 结果与证据不洗白 | L3 | 工程完成但真实对照缺失/基线被阻断；聚合/最终发布报告 | outcome_pending；不当0分或无限提升；私有证据脱敏且完整 |
