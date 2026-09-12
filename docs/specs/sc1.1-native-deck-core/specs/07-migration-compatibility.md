# 07｜旧 Run、安装目录与审批的无损迁移

## 7.1 新旧分流

| 对象 | 默认动作 | 可选继续方式 |
|---|---|---|
| 新 Run | 固定native+image_blueprint | 用户显式direct_svg；不存在隐式外部fallback |
| 旧高密度Run/已批准SVG | 只读旧schema/路径及批准文件，能力内核复用 | legacy-HD adapter继续旧路径；显式迁移native |
| 旧标准PPT Master Run | 展示旧engine，不触发绑定安装 | 明确继续legacy或迁移；只有legacy需要其绑定 |
| 无法判定旧profile | 只读且提示migration_required | 给证据和计划，不猜测覆盖 |
| 用户已有PPT Master目录/全局Skill | 不探测用于默认生产，不删除、不占有 | 用户单独使用；迁移计划显式列明所有权 |
| 已批准客户产物 | 文件和hash/approval保持 | 迁移后生成新revision并重新批准 |
| 历史库/客户源材料 | 原位置受授权策略管理 | 不因软件升级/卸载删除 |

兼容不是继续把 legacy 后端标为全局required。旧目录名中有ppt-master或HD不意味着新Run应使用它。只读diagnosis/export历史文件不得执行旧backend副作用。

## 7.2 dry-run → apply → verify

迁移计划列出源Run/schema/指纹、目标route、字段与路径映射、缺失证据、保留对象、将失效的gate/approval、新revision位置和回滚方法。计划哈希绑定源版本；执行时输入变更则拒绝旧计划。

apply在副本/新revision中执行，不改源归档。全部合同和原生构建通过后才更新current，失败保持原版本。migration不继承已过期报告，不重新签旧provider来源，不把模板/自证的旧证据变supported。歧义source/evidence引用先报告，不猜测。

## 7.3 Page Package 与 MBB 映射

Canonical Page Package status使用已发布schema的`ready_for_build`；SC-1 生产写方/消费者的`ready`差异必须由单一adapter解释。旧ready只在package结构完整、对应批准/来源证据有效时转换；没有证据不能通过状态改名升级为生产就绪。[R03][R09]

公共Narrative→Content Lock→MBB projection保持page/claim/component ID映射，旧MBB用户选择只有在输入候选集合/内容仍一致时可作为引用；推荐候选并不自动成为用户批准。迁移说明列出不再执行的重复MBB动作。

HD新旧错误码可兼容映射，但同一错误只由一个核心解析器和校验器判定。旧Scene/锁定版本继续可读；必须升级时使用显式adapter，不能静默丢字段。

## 7.4 发布、回滚与安装所有权

新release移除默认外部后端required链接和发现逻辑；旧managed backend保留数据标识，可独立清理但不自动删除。manifest中legacy entries标optional/compatibility并从默认required分离。不能把第三方已有real dir替换成Deck Master链接。

激活新release前运行真实内置compiler+render smoke；来源指纹或依赖检查不满足不切current。release回滚只回软件；新schema数据不逆向改写。旧程序不能安全写新数据时只读并给明确信息，不能覆盖新数据。

## 7.5 原 SC-1 验收处理

本包替换：A-03从“托管PPT Master”改“内置原生真构建”；A-08从“标准无需ImageGen”改“显式direct_svg无需ImageGen”；P-03从两产品后端一致改为同内核两authoring方式内容一致。其余涉及后端身份的条件按映射表替换。

保留：真实Library、研究、材料深读、语义质量、用户投入和三类真实方案配对目标。不是只保留一个短smoke就宣布SC-1全部accepted。原88项都有retain/replace/clarify映射；执行结果另填，禁止把superseded当passed。
