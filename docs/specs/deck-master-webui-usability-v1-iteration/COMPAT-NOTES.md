# 兼容、环境与既有验收边界

## 1. 本机测试命令（必要）

本机设置了 `HTTP_PROXY`/`HTTPS_PROXY=http://127.0.0.1:7890`，系统级代理同样开启。
macOS 上 `urllib` 检测到 env 代理后走 env bypass 逻辑，因此**伪造 Host 头的负例请求会被代理拦截**，
服务端的 403 变成代理返回的 502/HTML。这不是代码缺陷（`no_proxy='*'` 后
`test_gallery_core`、`test_workbench_reads` 的 host 负例均通过）。所有 pytest 命令统一前置：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy no_proxy='*' NO_PROXY='*'
```

- 非浏览器全量：`pytest -q tests/rebuild -m "not render and not browser"`
- 浏览器层：`pytest -q tests/rebuild -m browser --require-browser`
- 渲染层：`pytest -q tests/rebuild -m render`
- 静态：`ruff check src/deck_master tests/rebuild`

环境：Python 3.12.12（`/opt/homebrew/bin/python3.12` 建的 worktree 内 `.venv`）、Node v22.22.3、
Playwright 1.63.0（chromium 复用本机缓存）。Python 3.12 的 venv 默认不含 setuptools，
构建 wheel/sdist 的 `tests/rebuild/test_install.py` 需要先 `pip install setuptools wheel`。

## 2. #98 既有验收与本增量的边界

| #98 文档原结论 | 与后续排查的关系 | 本轮处理 |
|---|---|---|
| FINAL-VALIDATION 的六项 UX、90 项浏览器、范围内无未关闭 P1/P2 | 冻结版本、指定用例下的历史记录；后续连续第二意见、范围、首屏及任务导航反例表明其不能代表完整连续工作可用 | 保留历史通过事实；涉及 F/U 的广义可用性结论重新打开，按 C01–C08 修复、C09 复验 |
| PACKAGE-VALIDATION 的构建摘要、隔离安装、离线资产 | 可用性问题不否定这些构建/安装事实 | 原证据保留；产品修订后最终包重新核验，不沿用旧包通过代替 |
| FINAL-VALIDATION 记录的真实 Host、30 页编译与三用途导出 | 两份审计「未执行真实 Host」仅指各自轮次，不否定 #98 已有真实运行记录 | 按原工程/版本/任务范围保留；意见→trial→采用→下游恢复需新的针对性证据 |
| 用户视觉确认、真实 HOME 安装与 RC 发布 | 原文已明确视觉确认待完成、未做真实 HOME 安装 | 继续独立列项，不从工程通过推导用户认可或已发布 |

F 系列 10 项与 U 系列 15 项是两套编号，共 25 个原始条目，存在重叠、推断与产品决策项，
不能表述为 25 个独立且已复现缺陷。

## 3. 变更生效的技术边界（静态核验，`7662a11`）

**触发扩展路径的三个键。** `changes.py:67` 的 `extended` 由 `mode`、`references` 或任一 target 的
`stage` 三者任一出现即为真；`extended` 为真时 action 会携带 `mode`（默认 `auto`），进而命中
`commit()` 的 `require_writer(..., 'candidates.v1')`，并对 svg 层追加原图存在性校验。
C04 实施时只在需要时引入 `stage`。

**writer 边界不是 trial 独有代价。** `bump_revision()` 对 `workbench.v3` 的正常写入一律要求
`workbench-quality.v1`（`WRITER_RANK` 第 10 级，高于 `candidates.v1` 的第 4 级），
auto/trial 提交均经过它；`require_writer()` 取现有与所需等级的较高者，不降级。

**trial 的按图层支持（静态结论，不代表真实 Host 已全路径验证）：**

| 用户所看图层 | 实际修改对象 | 现有 trial 路径及前置条件 |
|---|---|---|
| 正文 `content` | Page | 支持内容候选，但协议 `intent.strip()` 必须为 `content`；计划 stage 为 `repair`，任务阶段映射为 `content`；制作工具需声明 `candidate_result` 与 `content_candidate` |
| 原图、预备提示词、实际提示词 | blueprint 原图 | 走 blueprint 候选；不直接改写已提交提示词原文 |
| SVG、PPT | SVG | 走 reconstruct 或 repair 候选；显式 trial 属扩展路径，要求当前原图存在且可读；PPT 入口修改的是 SVG，下游再编译 |

## 4. 其它已确认事实

- `annotation_service.list_annotations(project, *, revision=None)` 已支持固定快照读取，但
  `GET /api/annotations` 目前显式拒绝任何 query（`web.py:361-369`）——C03 接出现有能力而非新建。
- `candidates.listing` / `candidates.show` 已支持 `?revision=`；`/api/history` 支持
  `revision/page_id/layer/limit/cursor/related_only`。
- `changes.py:112-124` 已按底稿引用拒绝过期意见（page_ref / artifact_ref / content_plan_ref），
  C03 不得用「base_revision 等于当前 revision」的粗暴过滤替代它。
- 草稿身份= `project_identity + canonical(target) + base_ref.sha256 + base_revision`；
  CAS 通过请求体的 `expected_etag` 实现（非 HTTP 头）。
