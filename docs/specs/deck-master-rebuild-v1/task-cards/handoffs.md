# 阶段交接与验证

卡内126项是负责人的实施步骤，默认顺序实施，不是126张独立可派发卡。下列早期交接允许整卡未关闭时推进；只交出具体能力及未完范围，不新增运行状态、批准节点或产品对象。共享文件所有权沿用README，消费者通过接口接线，不复制上游实现。

| 交接 | 必要输入 | 可交付范围与接收者 | 验证与后续责任 |
| --- | --- | --- | --- |
| T01 → T02/T08 | T01.01–03的固定SHA、路径清单和提取边界 | T02可建包，T08可读固定来源；T01.05另交制作输入 | 真实git清单；不等事故图准备才开始纯解析 |
| T02.min → T03/T04/T05 | T02.01–04五对象、基本原子current、幂等/调用字段 | 基本读写接口及合法/非法样本，T02.05记录未完故障边界 | 五schema、坏引用、原子提交失败恢复；完整故障矩阵仍归T02 |
| T03.min → T04/T06 | T02.min；T03.01–04 TXT/JSON/已知Page完整投影 | 完整Page与有效design_context | 原文尾部约束、嵌套正文不丢；其他资料格式在T03.05 |
| T04核心 → T05/T13 | T03.min；T04.01–04 | create/accept/continue与五信封基本往返 | 重交不重复、旧输入不覆盖；此时不承诺自动工作台 |
| T05视图 → T04.05/T10 | T02.min、T04核心；T05.01–03 | 实际Document只读视图、本地服务和打开入口 | T04.05负责宿主自动打开接线；T05.05记录视图交接。T05.04隔离包可后续补齐，但T10关闭K01前必须完成 |
| T13.min → T06 | T02.min、T04核心；T13.01–03 | begin/settle/未知保护和用户停止 | 取消在途不退额，停止后不能请求新调用；不依赖T12完整恢复。T13.06在T12后补恢复/重试/冲突 |
| T06/T07 → T08/T10 | T01.05材料与Page、T03.min、T04核心、T13.min | T06.01–05完整prompt与真实工具结果；T07.01–05保留原图、实际阅图、编辑后Page及独立期待 | 不能用marker代替实际看图；样本登记见inputs.md；整卡其余反例仍按原AC |
| T08 → T09 | T01边界、T02.min；T08.01–05 | 纯接口、SVG解析/IR、定位诊断；图标和连接不丢 | 正常SVG及不支持/危险输入。T08不声称产PPT，不实现T09绘制 |
| T09 → T10.min | T08接口；T09绘制中覆盖该样本所需的全部实际元素 | 样本SVG到原生形状文字的实际编译结果，逐项列未覆盖特性 | 目标页所需特性不可删除以缩小范围；通用声明子集全部测试在整卡关闭前补齐 |
| T10.min → T12.min | T05视图、T07原图/期待、T09实际绘制；T10.01–03 | 第一张真实PPT、两段渲染读回、三方对照和具体问题 | T10完整完成须T05隔离包+T09全部范围；AC-K01此时关闭。缺renderer不能声称闭环完成 |
| T12.min → 后续 | T10.min、T02/T04基础事务；T12.01 | 轻微文本修改可复用蓝图；重大图示修改可重生目标页 | 两者均保住无关页且保留历史；完整T12等待T11统一复核和恢复矩阵 |
| T23.04 → T25 | T20/T21当前候选、实际已取得反馈 | 单独交已验/未验/失败记录；不依赖T23.01–03完成 | T25依赖T22/T24整卡+此记录；缺人类反馈时T23与V04/K12保持待验。用户明确要求专业批准时遵循其要求 |

## 阶段命令和测试责任

以下测试是**待实现的具名用例**，由对应卡建立；现在不存在不代表可以跳过。实施时记录实际解释器绝对路径。环境先用 `uv venv --python 3.12 /tmp/deck-rebuild-dev`，再用该解释器 `-m pip install -e '.[dev]'`；若uv环境不带pip，使用 `uv pip install --python /tmp/deck-rebuild-dev/bin/python -e '.[dev]'`。不替换用户已安装版本。无uv时用本机已确认的Python3.12 `-m venv`；依赖安装失败记录具体原因。

| 阶段/主责 | 命令（从仓库根执行） | 必须实际证明 |
| --- | --- | --- |
| T01 | `python3 docs/specs/deck-master-rebuild-v1/tools/materialize_inventory.py --repo . --ref 2a866cf138f6359f853db35e0a926ad79391b691 --out /tmp/deck-rebuild-inventory` | 固定来源清单可生成，所有跟踪文件有处置去向；未知项显式列出。此时不运行尚不存在的包测试 |
| T02.01 | `<候选Python> -m pytest -q tests/rebuild/test_contracts.py::test_five_valid_objects tests/rebuild/test_contracts.py::test_invalid_references` | 五schema合法对象；坏引用、重复页、跨项目引用给路径。T02负责新增此文件，配合既定store测试 |
| T02.min | `<候选Python> -m pytest -q tests/rebuild/test_store_transactions.py::test_atomic_current_failure` | 写入中断保留完整旧或新版，不混合 |
| T04核心 | `<候选Python> -m pytest -q tests/rebuild/test_tasks.py::test_envelope_roundtrip tests/rebuild/test_tasks.py::test_stale_result_keeps_current` | 五信封往返、旧输入不覆盖；T04.05另记录真实宿主自动打开，不靠mock判UI通过 |
| T08 | `<候选Python> -m pytest -q tests/rebuild/test_svg_parser.py::test_svg_to_ir tests/rebuild/test_svg_parser.py::test_unsupported_and_unsafe` | 解析完整与明确错误；不提前调用依赖T09的PPT输出测试 |
| T12.min | `<候选Python> -m pytest -q tests/rebuild/test_tasks.py::test_local_edit_preserves_other_pages` | 轻微文本与重大图示两参数，后者允许目标页生图；另执行真实单页修改并看图 |
| T13.min | `<候选Python> -m pytest -q tests/rebuild/test_tasks.py::test_call_begin_settle tests/rebuild/test_tasks.py::test_cancel_unknown_and_stop` | 正常结算、未知不退额、停止不重发；完整恢复用例等T12后运行 |
| T10完整 | `<候选Python> -m pytest -q tests/rebuild/test_compiler_api.py` | 隔离安装实际产PPT，不读取旧OS；真实图像对照另留证 |

其他卡使用各自AC表的拟建测试模块，整卡实现后运行。早期切片只运行对应已实现行为；不得用全模块失败倒逼提前造下游，也不得靠skip或空实现获得完成结论。
