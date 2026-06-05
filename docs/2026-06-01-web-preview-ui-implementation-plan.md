# Implementation Plan: Deck Master Web Preview UI

Date: 2026-06-01
Branch: `codex/web-preview-ui`
Worktree: `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-web-preview-ui`
Status: MVP IMPLEMENTED

## 结论

这一轮建议实现 Deck Master 的本地 Web 预览 MVP：用 `preview_manifest.json` 描述一次 Deck 组装草案，用本地 Web 服务读取 manifest 和页面图片，在浏览器里完成翻页、来源审查、状态标记和备注。

范围要收敛：先把「导出前可预览、可判断、可回写决策」跑通。PPTX 导出、跨项目真实编排、复杂版式编辑先不进入本轮。

## 成功标准

本轮完成后，用户应能做到：

- 启动一个本地预览服务
- 打开浏览器看到组装后的 Deck 草案
- 左侧看到页面队列
- 中间看到当前页预览图
- 右侧看到页面来源、原始路径、叙事角色、命中理由和状态
- 给页面标记 `keep` / `replace` / `needs_review` / `approved`
- 写入页面级备注
- 关闭服务后重新打开，状态和备注仍然存在
- 页面图片缺失、软链接断链、manifest 字段错误时，界面能明确展示问题

## 实现边界

### 本轮要做

- `preview_manifest.json` schema 和读取校验
- 本地 Web 服务
- 三栏 Web UI
- 页面图片安全读取
- 页面状态和备注回写到 manifest
- 一个可运行的 sample run
- 最小测试：manifest 校验、状态回写、路径安全

### 本轮不做

- 真实调用 PPT Library 搜索
- 真实调用 PPT Deck Pro Max 生成
- 导出 PPTX
- 拖拽重排
- 页面内元素级编辑
- 多人协作或远程部署

## 推荐技术路径

采用 Python 标准库本地服务 + 原生 HTML/CSS/JS。

理由：

- 和 PPT Master live preview 的本地服务思路一致，迁移成本低
- 本地运行足够稳定
- 不引入 React/Vite/Node/Flask 依赖，避免把一个内部工具做重
- 后续可直接复用 PPT Master 的服务生命周期、lock、轮询和路径安全经验

## 目录结构

建议新增：

```text
scripts/
  preview/
    server.py
    manifest.py
    static/
      index.html
      app.js
      style.css

examples/
  preview-run/
    preview_manifest.json
    links/
      page_001.svg
      page_002.svg
      page_003.svg

docs/
  schemas/
    preview_manifest.schema.json

tests/
  test_preview_manifest.py
  test_preview_server.py
```

如果这一轮只先做 smoke demo，可以先不建完整 Python package，保持 `python3 scripts/preview/server.py examples/preview-run` 的直接启动方式。

## Runtime 模型

一次预览任务对应一个 run 目录：

```text
runs/<run_id>/
  preview_manifest.json
  links/
    page_001.png
    page_002.png
  notes/
    decisions.md
```

V1 的真实状态源只有一个：`preview_manifest.json`。

服务启动时读取它，用户在 UI 中改状态或备注时写回它。这样 Agent、脚本和浏览器看到的是同一份状态。

## Manifest V1 字段

最小字段：

```json
{
  "run_id": "sample-run",
  "title": "Sample Deck Preview",
  "status": "draft",
  "updated_at": "2026-06-01T00:00:00+08:00",
  "pages": [
    {
      "page_id": "page_001",
      "order": 1,
      "title": "Problem Framing",
      "source_type": "library_slide",
      "preview_path": "links/page_001.svg",
      "source_pptx": "/absolute/path/to/source.pptx",
      "source_slide_index": 12,
      "narrative_role": "problem framing",
      "reuse_reason": "Matches inventory visibility gap",
      "confidence": 0.83,
      "decision": "needs_review",
      "notes": ""
    }
  ]
}
```

`source_type` 建议枚举：

- `library_slide`
- `generated`
- `placeholder`
- `manual`

`decision` 建议枚举：

- `needs_review`
- `keep`
- `replace`
- `approved`

## API 设计

### `GET /api/deck`

返回 deck 基本信息和页面列表。用于左侧导航。

### `GET /api/page/<page_id>`

返回单页元数据、预览资源 URL、资源是否存在、错误信息。

### `POST /api/page/<page_id>/decision`

写回页面决策状态。

请求：

```json
{
  "decision": "keep",
  "notes": "This page fits the opening narrative."
}
```

### `GET /preview/<page_id>`

返回页面预览图片或 SVG。只允许读取 run 目录内的相对路径或经过 manifest 明确声明的安全路径。

## UI 设计

采用三栏布局，参考 PPT Master，但针对 Deck Master 做轻量化。

### 左侧：页面队列

显示：

- 页码
- 页面标题
- 来源类型
- 决策状态
- 错误标记

### 中间：页面预览

显示：

- 当前页大图
- 缺图状态
- 断链提示
- 上一页 / 下一页 / 首页 / 末页

### 右侧：页面信息与决策

显示：

- 来源类型
- 原始 PPT 路径
- 原始页码
- 叙事角色
- 复用或生成理由
- 置信度
- 当前决策
- 备注输入框

操作：

- 标记保留
- 标记替换
- 标记已确认
- 保存备注

## 视觉方向

这是内部生产工具，视觉风格应偏「审查台 / 控制台」：

- 信息密度中高
- 重点突出当前页预览
- 颜色克制，避免营销页风格
- 页面状态使用清晰标签
- 按钮以操作语义为主，不做装饰性表达

初始配色建议：

- 背景：深灰黑或低饱和灰
- 主文字：近白
- 次级文字：灰
- `keep`：绿色
- `replace`：红色或橙色
- `approved`：蓝色
- `needs_review`：黄色

## 实现顺序

1. 建 `scripts/preview/manifest.py`
   - 读取 manifest
   - 校验必填字段
   - 按 `order` 排序页面
   - 支持更新单页 decision / notes

2. 建 sample run
   - 3 页示例
   - 使用简单 SVG 作为预览图
   - 覆盖 `library_slide`、`generated`、`placeholder`

3. 建 `scripts/preview/server.py`
   - 启动本地 HTTP 服务
   - 实现 `/api/deck`
   - 实现 `/api/page/<page_id>`
   - 实现 `/api/page/<page_id>/decision`
   - 实现 `/preview/<page_id>`

4. 建 Web UI
   - 三栏布局
   - 页面列表
   - 当前页预览
   - 右侧元数据与决策表单
   - 键盘翻页

5. 加安全和错误处理
   - run 目录路径穿越防护
   - 图片缺失展示
   - manifest JSON 格式错误展示
   - page_id 不存在返回明确错误

6. 加测试
   - manifest 读取和排序
   - decision / notes 写回
   - 非法路径拒绝
   - API smoke test

7. 本地验收
   - 启动服务
   - 浏览器打开 UI
   - 改一页状态和备注
   - 重启服务确认状态保留

## 已实现结果

本轮已完成：

- `scripts/preview/manifest.py`：读取、校验、排序、回写 `preview_manifest.json`
- `scripts/preview/server.py`：本地预览服务，提供 `/api/deck`、`/api/page/<page_id>`、`/api/page/<page_id>/decision`、`/preview/<page_id>`
- `scripts/preview/static/`：三栏 Web UI，支持页面队列、当前页预览、元数据审查、决策和备注保存
- `examples/preview-run/`：3 页样例 run，覆盖历史复用页、新生成页和占位页
- `docs/schemas/preview_manifest.schema.json`：manifest V1 schema
- `tests/`：manifest 与服务 API 的标准库单元测试

## 验收命令

启动：

```bash
python3 scripts/preview/server.py examples/preview-run
```

打开：

```text
http://localhost:5050
```

测试：

```bash
python3 -m unittest discover -s tests -v
```

本轮已验证：18 个测试通过；本地服务 smoke test 已确认 `/api/deck`、`/preview/page_001`、编排 run 读取、外部工具适配、反馈统计和页面决策回写可用。

## 风险与处理

| 风险 | 处理 |
|---|---|
| 软链接断链 | `/api/page/<page_id>` 返回 `asset_exists=false`，UI 显示缺图 |
| manifest 被多个进程同时写 | V1 先不支持并发写；写入采用读改写，后续再加文件锁 |
| 图片来源在 run 目录外 | V1 优先使用 `links/` 内资源；外部绝对路径只展示文本，不直接开放读取 |
| UI 过度复杂 | V1 只做页面级状态和备注 |
| 未来接入真实工具时字段不够 | 通过 `metadata` 字段保留扩展空间 |

## 下一步

下一阶段重点是接入真实外部工具数据：

- PPT Library 输出历史页截图、来源路径、命中理由和置信度
- PPT Deck Pro Max 输出生成页预览图、生成理由和项目路径
- Deck Master 把真实候选页输入 `scripts/orchestrate/build_run.py`
- 导出前确认流程把 `approved` 页面队列传给后续 PPTX 生成或人工组装步骤
