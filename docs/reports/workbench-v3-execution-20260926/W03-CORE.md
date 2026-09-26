# W03：独立入口、服务与个人草稿核心

基线 main `13aaf3690c6cde67e405576f5020abdd5311b909`，前置 ContentPlan [PR #44](https://github.com/MainQuestAI/Deck-Master/pull/44) 已合并。本切片只交共享核心、CLI/HTTP 和合成样例工厂；新界面随后单独接线。W03 未整卡验收，W02 的新 UI 兼容矩阵仍待浏览器联测。

## 行为与兼容

`deck-master workbench` 可在没有项目时启动独立 launcher。`--project` 显式打开并注册项目；`--registry` 指定独立注册表，默认在用户配置目录。支持 `--port 0`、`--no-open`、`--ui legacy` 和只停止所选服务的 `--stop`。新命令默认地址为 `/v2/`；当前核心切片没有新界面资源时返回 `core_ready_ui_unavailable`、退出 3，不打开空白页。旧 `view --open` 仍返回 `/`。

注册表仅保存用户显式选择的 canonical path 和基本展示信息；读取列表不扫描目录，阅读位置从项目 UI-state 读取，移除入口不删除项目。新建要求名称、用途、受众和新目录，先在同一父目录准备完整项目，再发布 `.deckmaster`。注册失败保留完整项目及恢复路径；输入错误或准备失败不发布半成项目。中文目录名得到有效内部 project_id，展示名保留中文。

新建复用 `service.create(..., project_format='workbench.v3')`，只登记一个 compose 任务。空材料保持事实缺口。补材料调用原 `inputs_update`，旧 compose 失效；交接只读取最新 eligible compose，反复交接不写版本、不追加任务、不执行模型。Host 仍走 CLI 和唯一 Deck Master Skill。

macOS 目录选择使用固定原生脚本，取消不注册项目；其它环境或原生选择不可用时返回手填路径状态。这里只验证了取消/不支持的服务行为，原生选择器的用户点击尚未列为验收。

## 服务生命周期

launcher 与项目分别使用 detached 进程。端口由绑定 `127.0.0.1:0` 直接分配；显式冲突报错，不抢占已有服务。启动锁串行化并发启动；服务健康后才原子发布运行元文件。注册表与运行元文件分开；项目沿用 `.deckmaster/view.json`。

复用核对 role、canonical path identity、instance_id、PID、port、协议、包版本和进程启动时捕获的代码摘要。健康请求直连 loopback，不跟随重定向或代理。旧 PID、不同服务、旧代码或损坏元文件不视为可复用。正常退出仅清除匹配自身实例的元文件；旧实例清理不会误删新实例。停止 launcher 不影响项目，停止项目不改注册表或业务数据。不会向未核实的 PID 发停止信号。

所有 GET 保留实例 Host 校验；所有 POST 共用 Origin、实例 token、Host 与 2,000,000 字节上限。token 不存入注册表、运行元文件或恢复文件；Host 没有绕 Origin 的 HTTP 通道。JSON 不缓存，旧对象白名单、hash 验证及 SVG sandbox 策略保留。

## 草稿与恢复

`ui-draft`、`ui-draft-record`、`ui-draft-recovery`、`ui-position` 的活动 schema 在包资源内，规格目录只有一致镜像。草稿存于 `.deckmaster/workbench/drafts/`，使用独立锁、updated_sequence、digest、ETag。与核心共用原子文件工具，文件与替换后的目录均 fsync 后再 ACK；不生成 Document revision，也不改变 content_identity、候选基准或调用事实。

项目的逻辑身份由最初的 revision UUID 与 project_id 得到。同名项目及同 page_id 不串稿，移动同一个项目仍可显式导入恢复副本。草稿引用必须属于该项目已提交历史、对应页和层，实际对象字节必须匹配 hash；换目标/基准必须新 draft_id。丢失 ACK 后，相同内容重试返回原 ETag/sequence；不同内容用旧 ETag 提交得到冲突，不覆盖已保存副本。

pending payload 单独保存其 operation_id 和 digest；后写草稿不会替换待核实请求，也不表示请求已业务提交。恢复文件校验版本、大小、hash、项目与基准；冲突保存为独立草稿，不提交业务、不采用产物、不重放模型。文件只携带数据，不带服务 token；结构中的凭据、本机绝对路径和执行元数据会拒绝，用户文本不会被静默删改，界面后续须标明可能含内部提示词。

真实服务换端口后只返回项目已经持久化的草稿；未发送副本须显式导入恢复文件。历史恢复不回滚个人草稿。单个损坏草稿局部报错，不隐藏其它草稿。浏览器临时缓冲、debounce、ACK 状态、下载/导入 UI 和冲突保留界面尚待前端切片。

## API 与可运行证据

| 场景 | 核心接口 |
| --- | --- |
| launcher 注册表 | GET `/api/projects`；POST `/api/projects/register`、`remove`、`create`、`open`、`sample` |
| 本地目录 | POST `/api/directories/pick`，无任意脚本参数 |
| 项目与输入 | GET `/api/project`、`/api/inputs`；POST `/api/inputs/update` |
| 整理内容交接 | GET `/api/compose/handoff`，不创建重复任务 |
| 草稿 | GET `/api/drafts`、`/api/drafts/{id}`；POST `/api/drafts/save`、`import`、`recovery` |
| 阅读位置 | GET/POST `/api/ui-state`，独立于 Document 和 registry |

[隔离验证脚本](../../../examples/workbench/w03_first_run.py)从实际 CLI 回包取地址；新目录、注册表与项目全部放在显式输出目录。它覆盖新建、补材料、反复交接、ACK 重放、真实不同端口恢复、未同步反例、显式文件导入、独立停止与重启。

```sh
PYTHONPATH=src python examples/workbench/w03_first_run.py --out /tmp/w03-core-example
PYTHONPATH=src python -m pytest -q tests/rebuild/test_workbench_services.py tests/rebuild/test_ui_journal.py
```

[原始检查](w03/core/checks.json)与逐步输入/输出已归档；本机路径换为逻辑标签，不保存 token。源码检查期间首轮全核心回归为 681 passed / 4 failed / 29 deselected，4 个失败均在安装检查。修复后相关检查为 61 passed / 3 deselected；共享事务、任务回执、schema 与包边界再检查 35 passed。此前新服务、journal、旧工作台及固定版读取组合为 68 passed。Ruff、diff 检查通过。

安装测试修复两点：wheel RECORD 的随机 base64 摘要可能碰巧符合 key 字符模式，现在只对已逐项核实的 checksum 字段免误报，所有实际文件和名称仍扫描，错误 checksum 仍拒绝；隔离 pip 不再继承源码 PYTHONPATH，且 stdlib-distutils workaround 仅用于 venv bootstrap，避免 3.12 sdist 后端缺失。没有降低生产校验，也没有改真实 HOME 安装。

`samples.create_sample` 是显式合成工厂，稳定内容、页 ID 和图像，保留正常 Page/Artifact/ContentPlan 读取契约；无模型调用、无专业通过记录。样例图和项目均标 synthetic，Web 业务写入拒绝，只允许个人阅读位置。不会在正常项目或生产失败时自动回退到样例。新增 core/HTTP 测试不等于新版 UI 浏览器、真实 Host 或用户验收。

## 留给本卡前端切片

保留用户 OpenDesign 最新视觉，接独立启动页、五区壳、页面/层/版本深链、回访和草稿恢复。随后在 1280×800、1440×900 及窄屏验证键盘、状态、旧基准与历史只读提示，并补 W02 新 UI/旧核心组合。W12 仍负责最终完整离线包验收；本轮没有默认入口切换、真实 HOME 迁移或发布。
