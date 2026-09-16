# 02｜逐文件施工、跨分支提取与删除操作

## 02.1 三类表必须一起执行

`inventory/new-files.csv`规定新建/重写目标、职责和测试；`old-files.csv`覆盖B0全部177个scripts文件；`root-and-config.csv`覆盖入口、包、文档和CI。旧58个contracts与122个顶层test分别有台账。剩余文档、fixture、样例与根文件由 `path-rules.json`及只读清单工具展开，未知文件显式REVIEW。

对CSV的完成登记可以加一列执行结果，也可以在PR说明引用ID；不创建新的运行时治理对象。未获得实施授权前，不创建项目分支、不改源文件、不执行删除。

## 02.2 新建的操作顺序

1. 创建src包与最小`__main__`、models、store、service、view、cli；先用合成对象接收/查看/恢复，不把所有产品旧文件复制进来。
2. 将本包五份schema安装到resources/contracts；实现类型/语义校验和引用解析。示例数据仅作合同测试。
3. 提取content/sources和实际宿主任务协议，同时创建真实内容方法reference；从第一批就让Host完整稿能通过正常入口进入。
4. 编译器在独立包中逐模块提取，先纯API调用；依赖检查禁止import旧运行时。将已知坏样例逐项修复后再接production。
5. 实现production/review/工作台/导出和局部修改；把指针、页面集合、任务结果接到同一个view。
6. 更新安装、CLI入口、Skill与文档，执行独立安装后切换默认；最后物理删除旧运行代码。

新路径均是拟建，不是已存在事实。Codex不得因为目标文件不存在就转而继续往旧文件加profile分支。

## 02.3 跨分支取用表

| 能力 | 首选参考 | 具体取用 | 明确不带入 |
| --- | --- | --- | --- |
| 完整稿接收/页集合 | B0 runtime/orchestration.py、production/page_package.py | 预校验、稳定身份、增删重排、失败恢复测试 | sourcing/preview必需、全目录复制 |
| 可见内容与设计 | B0 high_density/content.py、blueprint.py | PagePackage直投影、正文叶子、设计prompt；修错接字段 | MBB二次主线、词元证据阈值、密度分 |
| SVG几何/画笔 | B0 svg_native.py/svg_paint.py 与 K0 native_pptx 对应实现 | 对照有效函数和测试，保留B0最近圆角/描边修复 | 审阅回执、run路径/审批依赖 |
| 可编辑文字/多行 | K0 native_pptx/pptx.py及text相关代码；与B0 pptx.py比较 | 实际文本基线、分组、画笔改进，修800/900等 | 不经输入校验的静默fallback |
| 独立API/渲染/readback | K0 native_pptx/api.py、render.py、readback.py | 显式请求、错误定位、真实工具运行 | 旧Scene/Lock批准作为编译必需；HOME探测 |
| 取消/原子/晚到保护 | K0 workflow/actions.py、build/native_tasks.py（函数实际需要Codex核验） | 保护行为与反例，按小文件事务重实现 | 固定尝试次数授权平台、任务全局治理 |
| 工作台 | B0 preview/static与server相关代码 | 页面导航、对照、样式的有效部分 | preview_manifest真相源、团队/审批看板 |
| 安装/回滚 | B0 skills/installer.py与K0安装回归 | 隔离release tree、启动器、原子激活行为 | 15Skill完整性、PPTMaster认证、RC文件当使用前置 |

每项提取记录源SHA/源函数/目标函数/保留测试/行为差异。只需普通Markdown表，不做新运行时“提取登记服务”。源模块现状和具体可用函数需要Codex核验；不可假设K0已合并入B0。不得整体merge或cherry-pick带入大量治理变更；逐功能移植并保留许可证归属。

## 02.4 删除不是一次rm

### S1：停止新调用
在WP04切换时，默认CLI、Skill、UI、installer、doctor与文档不再导向旧OS；新包依赖边界已在WP01建立。旧run通过显式legacy读取或固定旧安装操作。新run不生成旧问卷、approval/handoff、sourcing或preview占位文件。

### S2：停止随包安装
新wheel/release tree只包含src/deck_master及实际resources、单Skill与合法依赖。旧scripts、product_capabilities、旧Skill和历史contracts不进入新发行包。必须用安装后的模块路径和wheel内容证明，不仅靠pyproject过滤文字。

### S3：物理删除仓库旧源码
WP05逐行对照台账；有效行为已移植且新测试覆盖；新默认与独立安装已通过；旧输入有规定的只读导入/固定旧版回退；静态import、CLI、资源、文档执行命令、CI与运行探针均无默认引用后，删除旧源文件。保留Git历史与发布旧版定位。无实际使用者的旧兼容shim在同批或已注明的下一次破坏性版本删除，不无限期保留。

`EXTRACT_THEN_DELETE`不授权删除目标新文件；`ARCHIVE`表示保留原字节并更改活动索引。凡有未知消费者，先定位具体调用；不能以“可能有人用”为由无期限保留整个OS，也不能凭未命中grep证明绝对无动态消费者。

## 02.5 每类旧代码的明确裁决

- planning/conversation规则Brief与轮询配claim：停止生产执行，示例需要时迁入明确demo；不作为正常失败fallback。
- workflow/team/advisory/learning等旧平台：不迁入新运行时；保留有用方法文本和历史数据解释，不保留原队列/审批语义。
- library/sourcing/adapters：本轮不重建库平台；旧PPT按来源读取；手动历史库需求留固定旧工具，不影响新核心。
- runtime/preview/generation：提取文件/Host交回/预览工具后旧状态逻辑退役。新结构无需通过补旧文件让旧状态器“满意”。
- high_density：逐函数拆，不整个删除后重写；也不整个import到新包。绘制内核、视觉测量、来源审阅必须分离。
- quality：真实文件、可见正文、引用和隐私检查保留；默认评分、空集合满分、风格模板、风险数量不是专业检查。

## 02.6 配置与文档是否全覆盖

除台账中根文件外，Codex用 `tools/materialize_inventory.py`对本地固定SHA展开全部跟踪文件：每个文件得到exact/prefix/REVIEW处置。docs中的旧操作指南允许新建更正索引并保留历史原文；默认README、Skill及可执行示例不能继续指向旧链。

本包对部分活动docs路径提出目标：本地存在则重写，不存在则新建并在台账标NEW；不得把拟建路径说成已核对的旧文件。仓库当前路径清单和精确引用更新需要Codex核验。

## 02.7 测试如何删除

原测试不是按文件名直接整删。先列出函数级断言：可靠性/转换/内容保持→迁入新测试；旧产品已退出的固定阶段和错误门禁→附替代行为后删除；第三方兼容→留固定旧版，不在新核心跑。任何新测试失败不能用删测试、skip整目录或放宽到无意义值解决。

同一阶段既有旧测试失败且属于已明确退出行为，可以据台账解释，不必强行维持旧预期；但新核心的正反例与独立安装必须实际通过。发布说明分别列旧基线、新测试结果，不将未运行旧套件说成“全量回归通过”。

## 02.8 不可触碰范围

不得自动删除 `/Users/...` 等用户资料、`.codex`/`.claude`会话、客户run、历史PPT、第三方Skill、字体文件、旧已发布工件。不得执行`git clean -fdx`清理用户工作树。旧安装清理只针对本安装器记录为自己拥有且未修改的资源；同名ppt-master来自其他项目时不处理。
