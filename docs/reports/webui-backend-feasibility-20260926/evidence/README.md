# 核验证据说明

本目录属于 2026-09-26 的后端能力核验，目标是判断 v3 前端功能是否有真实后端支撑。不是 v3 生产验收或真实 Host 使用报告。

## 来源

- [audit-baseline.json](audit-baseline.json)：执行提交、远端 main、两者同一 Git tree、测试解释器和设计基线。远端先经 `git ls-remote origin refs/heads/main` 核实，再下载精确提交供只读比较，未切换分支。
- [opendesign-read-snapshot.json](opendesign-read-snapshot.json)：只读 MCP 获取当前设计的 6 个活动文件。保存摘要与动作标识变化，不复制/改写用户前端。`original-v2/` 备份不作为当前设计。
- [backend-tests-loopback.xml](backend-tests-loopback.xml) / [最终日志](backend-tests-loopback.log)：214 passed，全部选中测试均运行，无 skip。包含模拟 Host 结果、临时项目、真实本地 HTTP 及部分故障注入。
- [首次 XML](backend-tests.xml) / [首次日志](backend-tests.log)：受限沙箱禁止绑定 loopback 端口，197 passed、11 failed、6 errors。此轮用于识别环境限制；获得本机端口权限后同组重跑，不把它计为产品缺陷。
- [backend-probes.json](backend-probes.json) / [日志](backend-probes.log)：17 项实名观察，其中已存在的能力和预期缺口都使用 verified 表示“该观察已复现”。不能读作“所有这些产品功能已通过”。
- [matrix-summary.json](matrix-summary.json)：38 项能力的实施性质统计，不是完成率。

## 测试命令

在仓库根目录，使用当前 `.venv`，强制从 `src/` 导入；需允许本机回环端口。以下命令使用独立临时目录；若复跑，换一个新的 `--basetemp` 路径。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/rebuild/test_web.py \
  tests/rebuild/test_workbench_e2e.py \
  tests/rebuild/test_tasks.py \
  tests/rebuild/test_production.py \
  tests/rebuild/test_store_transactions.py \
  tests/rebuild/test_export.py \
  tests/rebuild/test_flow_quality.py \
  tests/rebuild/test_review_round4.py \
  tests/rebuild/test_service_flow.py \
  tests/rebuild/test_page_visual_gate.py \
  tests/rebuild/test_contracts.py \
  --junitxml=/tmp/deck-master-backend-audit.xml \
  --basetemp=/tmp/deck-master-backend-audit-rerun

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  docs/reports/webui-backend-feasibility-20260926/probe_backend.py \
  --out /tmp/deck-master-backend-probes.json
```

脚本 `probe_backend.py` 对真实服务发同源 HTTP 请求，临时 token 仅在内存使用，不写证据。脚本中的 Host 回包、PNG 和导出用 PPTX 都是合成测试输入；没有调用图像工具、模型、真实 Codex 执行或渲染器。超时采用旧时间戳夹具，未等待现实 30 分钟。异常回执测试通过进程内 mock 注入一次写失败，未改生产源码。

## 代码证据索引

下列行号对应测试源码 `3e1c706`；它与核实的远端 main `d1c7c4` 内容一致。以后源码变化时应按函数重新定位，不能把本报告视为永久现状。

| 索引 | 文件与位置 | 支持的判断 |
|---|---|---|
| E01 | [web.py](../../../../src/deck_master/web.py)，POST 行109，view 行166，pages 行169，tasks 行185，file 行204 | 当前路由、字段消费、版本参数缺失、下载边界 |
| E02 | [view.py](../../../../src/deck_master/view.py)，project_view 行20 | 当前/指定历史的核心投影与现有字段 |
| E03 | [service.py](../../../../src/deck_master/service.py)，create 行88，continue 行592/662，open_host_task 行892，task_start 行1624 | 创建、单项目自动调度、修复任务、接手/取消 |
| E04 | [service.py](../../../../src/deck_master/service.py)，task_summary 行394，inputs_show 行941，inputs_update 行1115 | 可复用任务上下文、材料与任务要求更新 |
| E05 | [production.py](../../../../src/deck_master/production.py)，resolve_design 行32，project_prompt 行81；[service.py](../../../../src/deck_master/service.py) open_blueprint_task 行512 | 样式/素材约束、预备prompt与派发时冻结输入 |
| E06 | [tasks.py](../../../../src/deck_master/tasks.py)，task_inputs_current 行306，_build_artifact 行370，content_update 行665/733，accept_result 行828，提交/回执行1155 | 按页新鲜度、实际prompt可选、局部内容变更、直接采用、回执窗口、取消晚到 |
| E07 | [editing.py](../../../../src/deck_master/editing.py)，edit_page 行251，export_project 行282，history 行375，restore 行384 | 正文编辑、导出、历史与恢复 |
| E08 | [store.py](../../../../src/deck_master/store.py)，load_document 行193，commit_change 行225，_commit_locked 行251 | 不可变历史读取、原子指针/CAS，不能单独证明业务回执原子 |
| E09 | [pipeline.py](../../../../src/deck_master/pipeline.py)，artifact 行55，逐页预览行106，produce 行289，预览写入行315；[compiler/native.py](../../../../src/deck_master/compiler/native.py) | 逐页SVG预览、整稿PPT编译/渲染、可编辑能力边界 |
| E10 | [活动契约目录](../../../../src/deck_master/resources/contracts/)，document/task/artifact/page.v2/review；[content.py](../../../../src/deck_master/content.py) | 当前五类模型、字段有无、引用/选区与用户意见不是同一对象 |
| E11 | [现有前端](../../../../src/deck_master/resources/static/app.js)，行5/44/99；[web.py](../../../../src/deck_master/web.py) 行229/264 | 内存草稿、单项目服务、尚无新入口与项目journal |

## 探测编号

| 探测 | 要检验的命题 | 实测 |
|---|---|---|
| P01 | 24页核心读/历史与编辑重放 | 支持 |
| P02 | HTTP确实读取revision指定版本 | 不支持，忽略参数而返回当前 |
| P03 | summary、v2入口、projects、inputs、operation查询路径 | 均404；其中若干是v3建议路径 |
| P04 | 现view包含任务事实与sources | 缺失，核心Document却已有 |
| P05 | 反馈保存选区/所看产物/客户端操作身份 | 选区未存，客户端ID未参与操作身份 |
| P06 | 现feedback接收批量形状 | 400，未增生任务 |
| P07 | 领取后的状态/接手身份可完整呈现 | 核心running成立，HTTP字段不完整 |
| P08 | 旧running任务自动成为可恢复超时状态 | 未转换 |
| P09a | 只有正文时可以导出review | 当前被no current PPT拒绝 |
| P09 | 三用途/指定版本/导出文件下载 | review含工程对象，engineering和revision不支持，导出目录文件拒绝 |
| P10 | 不同页逆序结果及候选独立采用 | 逆序接受，但接收即更新当前，未提供候选采用环节 |
| P11 | 取消后的晚到内容不会覆盖 | 支持 |
| P12 | Task已保存派发时预备请求 | 支持 |
| P13 | 必须有实际prompt；全稿原图优先 | 实际prompt可缺；下一任务仍是本页重建 |
| P14 | 改受众先存事实并派发协调工作 | 支持，正文当时未被直接替换 |
| P15 | 完成Task持久result_refs能追溯结果 | 本例回包有引用，持久字段为空 |
| P16 | 当前已提交、回执失败后能重放原结果 | 重试报冲突，实际结果已在当前稿 |

17 项按编号计数（包含 P09a），没有把缺失功能的预期拒绝写成生产通过。P15 因与蓝图接收相邻，在 JSON 中早于 P13 出现；编号含义固定，不靠数组位置识别。
