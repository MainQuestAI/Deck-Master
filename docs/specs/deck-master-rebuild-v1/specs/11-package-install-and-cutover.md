# 11｜包、安装、独立运行与默认入口切换

## 11.1 包结构的具体调整

将pyproject的package-dir改为src发现，仅打包deck_master；console entry为`deck_master.cli:main`。元数据移除Run OS/全部治理ready等旧定位。候选版本用明确预发布标记，正式版本号在用户批准发布时定；文档不宣布2.0已发布。

保留Python3.11/3.12验证和现有jsonschema、python-pptx、Pillow、numpy依赖作为起点；具体锁定范围以候选安装实测确定，不能凭本包放宽到未知最新版。资料PDF/DOCX/PPTX处理按04章选择已有依赖或标准XML工具，任何新增依赖说明用途并在许可证中登记。缺PDF工具只影响相应资料读取，缺renderer不阻断正文编辑。

当前旧scripts包不进入wheel，不把源码整个目录COPY到用户安装充当发行。资源包含五份schema、静态工作台、一个deck-master Skill及内部references。用importlib.resources定位，不借当前工作目录或源码checkout。

## 11.2 Skill资源唯一来源与构建实现

仓库中`skills/deck-master/`为唯一可编辑Skill源。新增一个最小setuptools build hook（`tools/build_hook.py`，由最小`setup.py`注册build_py）在正常PEP517构建时复制它到build_lib/deck_master/resources/skill；源码不维护第二套同义副本。新增`MANIFEST.in`确保sdist包含hook、Skill和资源；wheel包数据配置包括resources。

`pip install .`、从sdist构建、release构建都必须走同一hook，不能只有自定义脚本构建才有方法文件。hook不联网、不生成业务内容、不打包客户资料或字体。tools/build_release.py仅组织构建、检查wheel清单并生成发布归属清单，不引入RC治理平台。

开发第一批即通过隔离虚拟环境安装新候选包以验证src/resource边界；生产当前链接不切换。公开默认安装与文档在WP04切换。`pip install -e`作为可选开发方式不能被当成无源码依赖的安装验收。

## 11.3 最小安装布局

建议沿用可恢复的用户前缀而非重新造安装平台：

```text
<prefix>/.deck-master/
  releases/<release_id>/venv/...
  releases/<release_id>/release.json
  current -> releases/<release_id>
  previous -> releases/<previous_id>
  bin/deck-master                 # 使用current固定解释器
```

prefix可配置，默认用户HOME；不修改系统Python、不要求管理员权限。release.json记录包版本、实际来源SHA/构建资源hash、内核版本、方法版本、入口。它只说明安装内容，不说明专业首稿ready。

安装命令在新release目录完成依赖安装、导入、资源、最小真实编译/渲染工具探针后，用户授权时原子切current。失败不改现有current。rollback切回旧二进制版本，不自动让旧代码写新版Document；不支持格式时明确只读/导出或配套恢复旧项目副本。

## 11.4 真正解除外部绑定

product-capability-manifest、Skill routing、doctor、installer、README、UI统一删除新核心对PPT Master repo/SHA/bind/verify/certification的要求。Library默认完全不加载，不调用检索后假装none；无历史缓存、无库配置的环境应可工作。

通用python-pptx/渲染器仍是正常依赖，不把“不绑定PPT Master”解释为“不依赖任何库”。旧第三方Skill和用户已装PPTMaster不删除，只是不参与新核心。

旧standard/high-density不再是产品两种不同主流程；样式和密度仅参数。CLI旧profile仅在明确可映射到当前设计参数时映射，否则提示退役。不能用一个profile跑通后继续把整体产品ready绑定旧标准后端。

## 11.5 Host Skill安装与移除

仅安装deck-master主Skill到用户选择的Host路径。内部方法不是15个公开专家；不要求全部安装才能使用。安装前读取已有目标：是本安装器拥有的旧链接/未修改文件时可替换；用户修改过或来自第三方时备份并提示，不覆盖。

清理旧deck-*技能只依据本安装器实际ownership manifest/链接目标/hash；名称相同不足以授权删除。旧ppt-master、ppt-library等第三方技能保持原状。不可通过扫描整个.codex/skills递归rm完成减法。

## 11.6 doctor的输出

必须区分：安装包可用、资料格式工具可用、生图Host能力可用、编译可用、渲染可用、工作台可用、当前任务专业证据。最后一项不能由doctor自动判通过。

返回实际Python executable、模块__file__、包版本、源SHA、资源目录、字体匹配、renderer路径/版本。每步required/optional清楚；没有Host图像工具写awaiting_host，不伪装安装失败，也不自动降fixture。

## 11.7 独立安装验收与切换

在隔离HOME、无PPTMaster/Library配置、禁止访问源码checkout、无用户已有缓存下安装候选；从安装后的deck-master create运行。检查method/schema/static资源存在，真实SVG转换/PPT渲染、工作台启动、局部修改、恢复、导出都使用安装模块。

目标平台指定字体与Logo不因移动项目丢失；字体文件不随公开发行打包；缺指定系统字体如实说明。安装验收从自然语言主Skill开始观察自动view，不由测试者额外手工补命令。实际Host调用可在授权的测试会话完成，任务产物通过安装CLI接收；不能从repo临时补.py或资源。产物版本与安装release记录对应。macOS桌面编辑与Linux headless分别报告，不将一个替代另一个。

切换门槛：本包范围内正常入口链路有效、安装无旧依赖、当前UI与文件一致、已知must_fix无未解决、legacy导入/回退明确。切换是用户授权的发布/安装动作，Spec通过不自动授权执行。

## 11.8 CI怎么改

三组：①Python3.11/3.12单元、schema与边界；②真实图形/字体/渲染小样例及实际XML读回；③wheel/sdist隔离安装、资源、启动器、legacy导入与回滚。Host生图和人类业务阅稿不假装在无凭证CI执行，保留单独真实运行记录。

每组报告executed/failed/skipped/unavailable，不把跳过必测称通过。旧测试按12章行为迁移，不要求CI永远运行两个完整OS。引入新包时旧套件结果和新套件结果分列，不能用总数掩盖新链路未执行。
