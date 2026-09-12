# SC-1.1 必需工程验收缺口清单

本清单是当前候选验收的待执行清单，不是代码功能缺失断言。表内 `not_run` 是初始清单状态，不表示迄今没有执行；阶段证据见 [PR31 修复验证记录](pr31-validation-progress.md)。只有同一候选 SHA 的真实命令、环境、实际结果及证据哈希经记录后才更新。已有单元测试不能自动覆盖 L2 条目。

源数据：SC1.1 64 项，其中必需 L1/L2 62 项；原 SC1 当前 91 项，其中 L1/L2 85 项。88 项 supersession 映射外新增 A-13、I-08、Q-13 三项，继续纳入工程门，不静默遗漏。合计 147 项工程记录，另 8 项 L3 保持 outcome_pending。

## SC1.1 必需 L1/L2

| ID | 级别 | 验收目标 | 映射/锚点 | 状态 |
|---|---|---|---|---|
| GOV-01 | L1 | 旧约束正式替换：默认不再要求PPT Master；旧文有superseded指向；未冲突要求保留 | 当前要求 | not_run |
| GOV-02 | L2 | 没有整库换名内置：仅本仓公共内核/必要组件；无完整上游workflow/后端项目运行依赖 | 当前要求 | not_run |
| GOV-03 | L1 | PR30基线保护：不擅merge/reset/revert或删除用户内容；明确实际基线 | 当前要求 | not_run |
| GOV-04 | L1 | 工程与效果状态分离：前者in_progress；仅全部工程闭环后可outcome_pending；superseded不当passed | 当前要求 | not_run |
| IND-01 | L2 | 隔离默认安装真编译：主要对象原生且有实际产物；未读取/安装/绑定外部产品 | 当前要求 | not_run |
| IND-02 | L2 | 不隐式克隆或调用外部产品：无git clone PPT Master、无外部svg_to_pptx命令、无哨兵访问 | 当前要求 | not_run |
| IND-03 | L2 | 默认入口一致：统一native route与revision；无backend bind提示或例外强行覆盖ready | 当前要求 | not_run |
| IND-04 | L2 | library none真入口：参数被接受；不调用库/不产生伪real selection/不使用fixture；每页生产决策真实 | 当前要求 | not_run |
| IND-05 | L1 | 宿主未知不伪报就绪：host=unknown/blocked；软件已装不等于图片工具可用 | 当前要求 | not_run |
| IND-06 | L1 | 可选依赖不污染任务：前两不被legacy阻断；旧任务缺项明确只影响其自身 | 当前要求 | not_run |
| IND-07 | L2 | 安装产物可脱离源码目录：包内引用可达；无源码绝对路径；没有缺schemas/methods | 当前要求 | not_run |
| IND-08 | L2 | 显式direct与禁止静默fallback：默认准确阻断；direct执行真实内核；不伪造图片来源 | 当前要求 | not_run |
| CNT-01 | L1 | Package状态规范：规范值通过；legacy有凭据才迁移；draft不被字符串洗白 | 当前要求 | not_run |
| CNT-02 | L2 | 消费当前真实内容：最终文字来自新Package，不使用旧preview/模板占位 | 当前要求 | not_run |
| CNT-03 | L1 | 内容锁只由公共内容产生：不从图片回填事实或证据；仅修复图片表达 | 当前要求 | not_run |
| CNT-04 | L2 | MBB单向投影：无新MBB访谈/第二主线；projection hash追随公共源 | 当前要求 | not_run |
| CNT-05 | L1 | 推荐不等于选择：不把推荐自动签成批准；已有明确选择不重复问 | 当前要求 | not_run |
| CNT-06 | L2 | 架构和数字跨视图一致：按模型/锁纠正并记录delta；PPTX和正文一致 | 当前要求 | not_run |
| CNT-07 | L2 | 原材料冷启动无循环：先实际形成方案/主线再产出非空Package；不要求空Package作前置 | 当前要求 | not_run |
| CMP-01 | L2 | 单内核提取差分：语义/几何/层序无非授权退步；不靠ZIPhash唯一判等 | 当前要求 | not_run |
| CMP-02 | L2 | 文字真正原生：文字可改，不是轮廓/图片；关键文字完整准确 | 当前要求 | not_run |
| CMP-03 | L2 | 主要形状路径原生：独立原生对象；关系/方向可追踪 | 当前要求 | not_run |
| CMP-04 | L2 | 分组与层序：分组真实、层序/几何一致；主元素不丢 | 当前要求 | not_run |
| CMP-05 | L1 | 零透明度等边界：零值不变一；验证与编译支持同一子集 | 当前要求 | not_run |
| CMP-06 | L1 | 支持矩阵与unsupported：已支持子集回归不退；不支持精确报element；不静默删/栅格化 | 当前要求 | not_run |
| CMP-07 | L2 | 坐标和非16比9源：无拉伸/错比例；文字stroke和effect坐标一致 | 当前要求 | not_run |
| CMP-08 | L1 | 资产和路径边界：输入拒绝且不访问越界；登记照片为独立对象 | 当前要求 | not_run |
| CMP-09 | L2 | 无整页套壳：伪编辑全部拒绝，主要业务图形原生页通过 | 当前要求 | not_run |
| CMP-10 | L2 | 编译与回读错误不伪完成：准确blocked/failed，无completed/客户ready；实际trace有效 | 当前要求 | not_run |
| HST-01 | L2 | 新图片真实生成：保留真实输出hash/action与可得元数据；fixture/旧参考不计fresh | 当前要求 | not_run |
| HST-02 | L1 | 不伪造服务元数据：null+证据等级可解释；不造ID/签名；无观测声明不算真实执行 | 当前要求 | not_run |
| HST-03 | L2 | 锁定内容与蓝图隔离：纠正事实/标注，保留业务限定；证据ID/路径不露出 | 当前要求 | not_run |
| HST-04 | L2 | 图片与SVG实际比较：识别失败并定向修复，不能只写pass | 当前要求 | not_run |
| HST-05 | L2 | 代表页与批量继续：仅失败页重试；无重复用户确认/无关页重做 | 当前要求 | not_run |
| HST-06 | L2 | 已有SVG编译不要求新ImageGen：按实际编译能力继续；不新生成，不伪报fresh图片 | 当前要求 | not_run |
| HST-07 | L2 | 有限图片修复：计失败/超时，达到上限停且保留成果；不换action ID重置预算 | 当前要求 | not_run |
| WF-01 | L1 | 固定route优先：按route/current解析；不因目录存在自动走错引擎 | 当前要求 | not_run |
| WF-02 | L1 | 缺语义门正确动作：派发语义审查，不无限执行render gate | 当前要求 | not_run |
| WF-03 | L2 | Agent专业动作真接线：提取/推理/写回真实调用，无只helper存在未调用；合法否定接受 | 当前要求 | not_run |
| WF-04 | L1 | 迟到及同ID冲突：旧拒绝；同内容幂等；不同输出冲突，不覆盖新版本 | 当前要求 | not_run |
| WF-05 | L1 | 第二文件中断整批一致：读者只见完整旧或完整新revision，不接受逐文件rename解释 | 当前要求 | not_run |
| WF-06 | L1 | 权限和停止有效：scope/path/permission/cancel检查实际生效；不写批准/锁定事实 | 当前要求 | not_run |
| WF-07 | L1 | 预算包含失败：预算真实消耗，不能只数committed；明确剩余 | 当前要求 | not_run |
| WF-08 | L2 | 精准失效与局部修改：前者只影响视觉/产物/最终批准；后者影响相关正文/图/阶段；无关决定保留 | 当前要求 | not_run |
| QA-01 | L1 | 语义门精确匹配：不满足语义；必须真实scope=semantic且完整覆盖 | 当前要求 | not_run |
| QA-02 | L1 | Package改而index不变：旧语义过期；不能只看indexhash | 当前要求 | not_run |
| QA-03 | L1 | 空pass和漏页拒绝：拒绝并指出缺项；不能靠声明通过 | 当前要求 | not_run |
| QA-04 | L1 | 严重问题压过summary：按finding阻断；P0不可覆盖；P1按当前政策授权 | 当前要求 | not_run |
| QA-05 | L2 | 视觉与编译证明分层：两组分别识别；不单用SSIM或内容正确替代其他门 | 当前要求 | not_run |
| QA-06 | L2 | 正式文件完整扫描：清理/阻断内部内容但不删业务限定；当前hash再验 | 当前要求 | not_run |
| QA-07 | L2 | 批准绑定实际新版：新版需对应批准；旧已批准文件保留且标历史 | 当前要求 | not_run |
| QA-08 | L2 | 修复后复审闭环：问题被实际验证解决；未修复不因新summary过门 | 当前要求 | not_run |
| MIG-01 | L2 | 旧HD可读与同核复用：旧数据保留，内核共用，无新双写主线 | 当前要求 | not_run |
| MIG-02 | L2 | 旧standard隔离：旧状态如实；不影响native，不自动安装绑定 | 当前要求 | not_run |
| MIG-03 | L1 | 迁移输入改变：拒绝过时计划，源批准文件不变 | 当前要求 | not_run |
| MIG-04 | L2 | 迁移故障回滚：旧current完整保留；无伪新seal/approval | 当前要求 | not_run |
| MIG-05 | L2 | 安装所有权与数据保护：只动自有软件/链接，不删除外部或客户数据 | 当前要求 | not_run |
| MIG-06 | L2 | 软件回滚不改新数据：新数据保留；不支持安全写则明确只读，无破坏转换 | 当前要求 | not_run |
| UAT-01 | L2 | 真实默认两页冷启动：真实默认链通过；有输出和执行证据，不用direct替代 | 当前要求 | not_run |
| UAT-02 | L2 | 真实七类页面与编辑：平均视觉≥4且各页≥3.5，内容/关系无关键错；编辑实证 | 当前要求 | not_run |
| UAT-03 | L2 | 原材料完整Solution Deck：Agent承担内容/图形/修复；无外部绑定；必要研究真实执行 | 当前要求 | not_run |
| UAT-04 | L2 | 局部修改端到端：只处理影响集，旧版保留，新版经当前检查和批准 | 当前要求 | not_run |

## SC1 必需 L1/L2

| ID | 级别 | 验收目标 | 映射/锚点 | 状态 |
|---|---|---|---|---|
| A-01 | L2 | 隔离全新安装：完整套件与托管后端可诊断；无隐式旧目录读取 | clarify IND-01 | not_run |
| A-02 | L2 | 锁定版本可重现：实际组件版本/分发哈希一致，禁止浮动分支替代 | clarify IND-07 | not_run |
| A-03 | L2 | 标准真实 build/render：有效PPTX、预期文字/页数、主要对象可编辑且可视渲染正确 | replace UAT-01 | not_run |
| A-04 | L2 | 不信任环境 ready 覆盖：不能仅凭环境变量变成真实验证通过 | clarify IND-05 | not_run |
| A-05 | L2 | 托管 Library 真检索：使用锁定程序并返回与查询对应的真实结果 | retain  | not_run |
| A-06 | L2 | 索引数据隔离：原始资料和索引保持；卸载不删除用户数据 | retain  | not_run |
| A-07 | L2 | 无历史库真实新建：无检索调用/虚假 selection/fixture；每页有真实生产决定 | clarify IND-04 | not_run |
| A-08 | L2 | 标准不强依赖 ImageGen：本次不被无关高密度依赖阻断 | replace IND-08 | not_run |
| A-09 | L2 | 必需能力缺失不伪报：task_ready=false，准确指出缺项与恢复动作 | clarify IND-05 | not_run |
| A-10 | L2 | 故障与无命中区分：故障不伪装为无命中；合法无命中按授权新建 | retain  | not_run |
| A-11 | L2 | 组件来源与再分发：未验证来源/缺关键方法不计内化完成 | clarify GOV-02 | not_run |
| A-12 | L2 | 兼容入口不依赖旧方法：所有引用可读，实际方法可执行，不跳到外部缺失Skill | clarify IND-07 | not_run |
| A-13 | L1 | 分层就绪状态可读：分层展示安装完整、组件可用、本次任务就绪与缺项；当前版本状态可读且不互相矛盾 | 未映射  | not_run |
| I-01 | L1 | 后置关键约束：末尾约束被定位并影响方案，不仅扩大截取长度 | retain  | not_run |
| I-02 | L1 | 混合资料接入：全部相关范围有记录，同一Context接入；真实宿主补L2验证 | retain  | not_run |
| I-03 | L1 | 部分读取不可假完成：状态partial/failed，关键缺口阻断且不标完整 | retain  | not_run |
| I-04 | L1 | 幂等导入：不复制事实/证据，不改变有效批准状态 | retain  | not_run |
| I-05 | L1 | 证据ID消歧：新版键正确；歧义旧ID不猜测对应 | retain  | not_run |
| I-06 | L1 | 精确定位与内容匹配：识别不匹配，不给supported | retain  | not_run |
| I-07 | L1 | 冲突不静默覆盖：记录冲突和选择依据；关键未知才请用户裁决 | retain  | not_run |
| I-08 | L1 | 高风险假设不冒充客户事实：该判断保留假设/未支持状态与重检条件，不得标为客户事实或 supported | 未映射  | not_run |
| R-01 | L2 | 定向真实研究：来源进入Context，说明影响哪项判断 | retain  | not_run |
| R-02 | L2 | 查询授权与脱敏：仅发送批准公共投影，不外发原始客户内容 | retain  | not_run |
| R-03 | L2 | 反证和适用边界：保留条件与反证检查，不泛化为所有场景 | retain  | not_run |
| R-04 | L2 | 无结果终态：inconclusive；不凑数据或虚构引用 | retain  | not_run |
| R-05 | L2 | 无工具/无网终态：capability_unavailable且不报已执行；关键缺口不被忽略 | retain  | not_run |
| R-06 | L2 | 研究预算与重启：有限恢复/准确停止；不无限研究也不重做已完成内容 | retain  | not_run |
| S-01 | L1 | 无risk标记不自证：unreviewed/insufficient，不计有充分支持 | retain  | not_run |
| S-02 | L1 | 目标不冒充根因：形成待分析任务，不以字符串前缀当专业判断完成 | retain  | not_run |
| S-03 | L1 | 同数字不同口径：不因同数字出现而通过；推导必须口径一致 | retain  | not_run |
| S-04 | L1 | 页面不得自证：不把生成内容回填成原始source支持 | retain  | not_run |
| S-05 | L1 | 问题机制验收连通：缺具体机制/验收的能力不通过 | retain  | not_run |
| S-06 | L1 | 现有与拟建区分：现有需证据；拟建需需求理由，不能写成已存在 | retain  | not_run |
| S-07 | L1 | 方案备选有实质差异：机制/范围/取舍有差异，不只是标题变化；L2/L3人工核验 | retain  | not_run |
| S-08 | L1 | 单一可行路径：说明唯一可行原因，不为凑数制造备选 | retain  | not_run |
| N-01 | L2 | 公共主线非模板拼贴：核心判断与机制随材料改变，不止替换名词 | retain  | not_run |
| N-02 | L2 | 无PagePackage循环依赖：不要求先制造空的最终PagePackage | retain  | not_run |
| N-03 | L2 | 已选主线不重复问：复用相同决定，无重复主线访谈 | clarify CNT-04 | not_run |
| N-04 | L2 | MBB兼容单一写源：MBB派生更新，不形成两套独立权威 | clarify CNT-04 | not_run |
| N-05 | L2 | 旧高密度Run可读：保持旧真相并明确迁移；不伪造新seal | clarify MIG-01 | not_run |
| P-01 | L2 | 标准真实消费Package：最终文件反映当前Package，不读旧preview冒充 | replace CNT-02 | not_run |
| P-02 | L2 | 无Placeholder完整生产：每页有实质内容；无制作说明充当正文、无漏页 | retain  | not_run |
| P-03 | L2 | 两个Builder内容一致：P0/P1文字/数字/限定一致；视觉方法可不同 | replace CNT-02 | not_run |
| P-04 | L2 | 高密度保护不降级：保留原门禁；不能把native路径伪造为ImageGen | clarify HST-01 | not_run |
| P-05 | L2 | 可编辑性真实检查：原生对象通过；套壳/隐藏文字层不通过 | retain  | not_run |
| P-06 | L2 | 客户文件全内容扫描：检测/清除内部内容，同时保留必要业务限定 | retain  | not_run |
| D-01 | L2 | 四类视图表达：模型引用、边界与表达一致，主要对象可编辑 | retain  | not_run |
| D-02 | L2 | 孤儿节点：明确指出node/model_ref不匹配 | retain  | not_run |
| D-03 | L2 | 关系方向：方向不符阻断，不能仅像素合格 | retain  | not_run |
| D-04 | L2 | 节点聚合映射：保留被聚合对象和理由；边关系可追溯 | retain  | not_run |
| D-05 | L2 | 模型改变的影响集：所有相关正文/图/阶段受影响；无关页不乱改 | retain  | not_run |
| D-06 | L2 | 图表口径一致：识别差异；不以图形渲染成功当正确 | retain  | not_run |
| W-01 | L1 | 复用材料已给答案：不重新问；记录具体来源和当前依赖 | retain  | not_run |
| W-02 | L1 | Agent拥有专业问题：派发Agent实质工作，不要求用户先写答案 | retain  | not_run |
| W-03 | L1 | 真实决定不能代填：拒绝Agent冒充用户授权 | retain  | not_run |
| W-04 | L1 | 布尔否定有效：接受合法否定；不套用全局模糊token拒绝 | retain  | not_run |
| W-05 | L1 | 决定精准失效：业务目标/已选主线不被无谓失效 | retain  | not_run |
| W-06 | L1 | 阶段内继续执行：宿主执行/接受/继续，不停在无意义继续点 | retain  | not_run |
| W-07 | L1 | 迟到结果拒绝：SC_ACTION_STALE；旧结果不覆盖新版本 | retain  | not_run |
| W-08 | L1 | 幂等与冲突：前者幂等，后者冲突可追溯，不静默覆盖 | retain  | not_run |
| W-09 | L1 | 跨文件中断恢复：仅旧完整版本或新完整提交可见，无半完成状态 | retain  | not_run |
| W-10 | L1 | 局部权限与停止：不越权推进；列出影响与待批准范围 | retain  | not_run |
| Q-01 | L1 | 空pass不代表审查：拒绝，指出缺失维度/页面/输入 | retain  | not_run |
| Q-02 | L1 | 审查覆盖完整：不满足正式内容审查 | retain  | not_run |
| Q-03 | L1 | 独立性不是改名：不计独立审查；真实上下文轨迹另作L2 | retain  | not_run |
| Q-04 | L1 | 当前输入绑定：旧审查失效，不接受新的pass声明顶替 | retain  | not_run |
| Q-05 | L1 | 发现结果压过summary：仍为阻断；不能直接接受summary | retain  | not_run |
| Q-06 | L1 | 具体返修动作：包含对象/输入/范围/目标/重验，不只是增强说服力 | retain  | not_run |
| Q-07 | L1 | 修复预算耗尽：准确报告未解项，不无限重试也不自动过门 | retain  | not_run |
| Q-08 | L1 | 修订后定向复审：相关内容与产物重验；无关内容不全量重做 | retain  | not_run |
| Q-09 | L1 | 正式必需门一致：统一要求当前语义/证据/工程门 | clarify QA-01 | not_run |
| Q-10 | L1 | 模式降级不可绕过：拒绝非授权迁移，保留创建时模式与策略 | retain  | not_run |
| Q-11 | L1 | 批准绑定当前版本：旧批准无效；旧已批准文件历史仍保留 | retain  | not_run |
| Q-12 | L1 | P0与P1处理：P0不可豁免；P1按当前版本显式政策且可见 | retain  | not_run |
| Q-13 | L1 | 无来源支持的数字被发现：该数字被列为 finding 并阻断交付；数字出现不等于主张获得支持 | 未映射  | not_run |
| L-01 | L1 | 通过率口径：acceptance_rate=0.09，交付数独立 | retain  | not_run |
| L-02 | L1 | 重复事件去重：按最终审阅决定计一次，导出不抬接受率 | retain  | not_run |
| L-03 | L1 | 旧事件不猜测：单列legacy_unknown，不制造精准统计 | retain  | not_run |
| L-04 | L1 | 经验适用边界：有范围和来源；无反馈不伪造模式，不传播客户事实 | retain  | not_run |
| M-01 | L2 | 外部目录不被占有：不覆盖；清楚列出拟操作/所有权/回滚 | retain  | not_run |
| M-02 | L2 | 只卸载自有入口：只移除自有链接/软件，保留外部与数据 | retain  | not_run |
| M-03 | L2 | 升级失败原子回退：旧current不变；失败版本不报已安装就绪 | retain  | not_run |
| M-04 | L2 | 旧Run无损映射：原始记录保留；歧义不猜；不静默丢字段 | retain  | not_run |
| M-05 | L2 | 新策略不洗白旧结果：补齐当前门与批准，不只改schema_version | retain  | not_run |
| M-06 | L2 | 软件回滚与数据分离：保留新数据；旧程序不能安全读写时明确拒绝 | retain  | not_run |

## L3 与人工批准

L3：SC1.1:UAT-05, SC1.1:UAT-06, SC1:E-01, SC1:E-02, SC1:E-03, SC1:E-04, SC1:E-05, SC1:E-06。本轮不以合成案例替代真实客户配对。

UAT-02 的人工视觉复核、UAT-03/04 的最终文件批准仍需用户实际完成；工具和 Agent 不代签。
