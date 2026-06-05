# Requirement: Deck Master Web Preview UI

Date: 2026-05-28
Status: RECORDED
Source: Boss request
Reference: `/Users/dingcheng/.codex/skills/.backups/ppt-master-repo-668131f0/skills/ppt-master`

## 需求结论

Deck Master 需要一个 Web UI，用来预览 PPT 生成和组装效果。它的核心价值是让用户在导出最终成果前，先看到每一页如何被组合、引用和排序。

这个 UI 的优先级是「预览与审查」。导出 PPTX 可以保留为后续动作，不能成为唯一验收方式。

## 背景

Deck Master 未来会作为编排层，整合：

- PPT Library：从历史 PPT 中搜索可复用 slide
- PPT Deck Pro Max：生成新页面或补齐叙事缺口
- Deck Master：决定本次 Deck 的叙事结构、页面来源、组装顺序和最终交付形态

如果 Deck Master 直接输出一个 PPTX，用户只能在终态文件里审查效果，反馈链路偏重。更合理的方式是先提供一个浏览器预览界面，让用户在组装阶段就能判断：

- 哪些页面来自历史 PPT
- 哪些页面来自新生成
- 页面顺序是否匹配叙事弧线
- 复用页和新生成页之间是否连贯
- 哪些页面需要替换、重排、重写或重新生成

## 目标

V1 目标是提供一个本地 Web UI，展示「组装后的 Deck 草案」。它应支持：

- 按页浏览组装结果
- 看到每页的来源信息
- 预览原始图片、PPT 截图或生成后的页面图
- 支持从原始资产路径读取，避免复制出一份重资产结果
- 支持通过软链接或 manifest 引用原始资源
- 支持后续接入用户标注、页面替换、重排和确认

## 非目标

本需求当前只做记录，不进入实现。

V1 不要求：

- 直接实现完整 PPTX 导出
- 实现复杂在线编辑器
- 实现多人协作、权限、云端部署
- 修改历史 PPT 原文件
- 做 PowerPoint 级别的版式编辑

## 参考对象：PPT Master Live Preview

PPT Master 的 Web UI 入口来自 `workflows/live-preview.md` 和 `scripts/svg_editor/server.py`。

它的机制可以拆成 6 层：

1. **项目目录作为运行时根目录**
   - 服务启动时传入 `<project_path>`
   - 默认读取 `<project_path>/svg_output/`
   - 同时服务 `<project_path>/images/` 和 `<project_path>/assets/`

2. **本地轻服务**
   - 使用 Flask 启动本地服务
   - 默认端口 `5050`
   - 浏览器打开 `http://localhost:5050`
   - 支持 `--live` 模式，允许 `svg_output/` 先为空，生成过程中页面逐步出现

3. **页面列表 API**
   - `/api/slides` 扫描 `svg_output/*.svg`
   - 返回页面名、标注数量、解析状态、修改时间
   - 前端根据列表生成左侧 slide 导航

4. **单页内容 API**
   - `/api/slide/<name>` 读取单个 SVG
   - 为 SVG 元素补临时 id
   - 解析已有标注
   - 内联图标占位符，保证浏览器预览效果接近最终页
   - 返回 SVG 内容给前端直接渲染

5. **浏览器交互层**
   - 三栏布局：左侧页面列表，中间画布，右侧标注面板
   - 支持上一页、下一页、首页、末页
   - 支持点击元素、框选元素、添加标注
   - 支持键盘导航
   - live 模式下每 2 秒轮询一次页面列表

6. **标注回写机制**
   - 前端把用户标注写回 SVG 元素属性
   - 标注存为 `data-edit-target` 和 `data-edit-annotation`
   - Agent 后续通过 `check_annotations.py` 读取标注，再修改 SVG 或重新导出

## Deck Master 可借鉴的逻辑

Deck Master 不必照搬 SVG 编辑器，但可以复用它的产品逻辑：

| PPT Master 逻辑 | Deck Master 适配 |
|---|---|
| `project_path` 作为预览根目录 | `deck_run_path` 作为一次组装任务根目录 |
| `svg_output/*.svg` 作为页面源 | `preview_manifest.json` 描述页面来源和顺序 |
| `/api/slides` 扫描本地页面 | `/api/deck` 返回组装后的页面队列 |
| `/api/slide/<name>` 返回 SVG | `/api/page/<id>` 返回截图、原始路径、来源元数据 |
| `images/` 和 `assets/` 直出 | 历史 slide 截图、生成页图片、原始 PPT 截图通过软链接或只读路径直出 |
| 浏览器内点击标注 | 后续可扩展为「替换此页」「重排」「重写标题」「重新生成」 |
| `.live_preview.lock` 防重复服务 | 每个 Deck run 保持单实例预览 |
| live 轮询新 SVG | 轮询组装状态和新生成页面 |

## 推荐的 Deck Master 预览数据模型

一次 Deck Master 组装任务可以生成一个运行目录：

```text
runs/<run_id>/
  preview_manifest.json
  links/
    page_001.png -> /absolute/path/to/source-slide-screenshot.png
    page_002.png -> /absolute/path/to/generated-page.png
  notes/
    decisions.md
```

`preview_manifest.json` 建议结构：

```json
{
  "run_id": "2026-05-28-client-retail-digital",
  "title": "Retail Digital Transformation Draft",
  "status": "draft",
  "pages": [
    {
      "page_id": "page_001",
      "order": 1,
      "source_type": "library_slide",
      "preview_path": "links/page_001.png",
      "source_pptx": "/absolute/path/to/history.pptx",
      "source_slide_index": 12,
      "narrative_role": "problem framing",
      "reuse_reason": "matches omnichannel inventory visibility gap",
      "confidence": 0.83
    },
    {
      "page_id": "page_002",
      "order": 2,
      "source_type": "generated",
      "preview_path": "links/page_002.png",
      "source_project": "/absolute/path/to/deck-pro-max-project",
      "narrative_role": "target architecture"
    }
  ]
}
```

## Web UI V1 建议

页面结构建议采用 PPT Master 的三栏模式：

- 左侧：页面缩略列表，显示页码、来源类型、状态
- 中间：当前页大图预览
- 右侧：页面元数据和操作区

右侧 V1 只需要显示：

- 来源：历史 PPT / 新生成 / 手工占位
- 原始文件路径
- 原始页码
- 命中理由或生成理由
- 在叙事弧线中的角色
- 相似度或置信度
- 当前状态：候选 / 已选 / 待替换 / 已确认

V1 操作可先收敛到：

- 上一页 / 下一页
- 标记「保留」
- 标记「替换」
- 写一条页面级备注

## Runtime-first 约束

Deck Master 属于 Agent 编排层，预览 UI 需要保留运行时状态，不能只生成静态 HTML。

V1 至少要明确：

- **状态存储**：`runs/<run_id>/preview_manifest.json`
- **恢复方式**：重新启动预览服务时读取同一个 manifest
- **工具结果回写**：PPT Library 搜索结果和 Deck Pro Max 生成结果写入 manifest
- **人工审批点**：用户在 Web UI 中确认保留、替换、重排或备注
- **错误重试**：页面图片缺失、软链接断链、生成失败都要在 UI 中展示
- **执行轨迹**：每页记录来源、理由、时间和生成/搜索工具
- **效果评测**：后续可统计用户保留率、替换率、页面来源命中率
- **版本治理**：每次组装生成独立 `run_id`，历史 run 可回看

## 关键风险

1. **软链接断链**
   - 历史 PPT 或截图移动后，预览可能失效
   - manifest 应保留原始绝对路径和当前链接状态

2. **图片与 PPTX 源不一致**
   - 截图只能代表视觉效果，不能保证可编辑性
   - UI 上需要标明页面来源和可编辑能力

3. **复用页和新生成页风格不连续**
   - 预览 UI 的价值就在于提前暴露这个问题
   - 后续可增加风格一致性检查

4. **直接复制资产导致库膨胀**
   - V1 优先软链接或 manifest 引用
   - 只有导出最终包时再考虑复制必要资产

5. **把预览 UI 做成复杂编辑器**
   - 当前阶段只需审查和轻量决策
   - 复杂版式编辑继续交给 PowerPoint 或生成层

## 建议实施顺序

1. 定义 `preview_manifest.json` schema
2. 做一个只读 Web UI，能读取 manifest 并显示页面队列
3. 支持软链接资源目录 `links/`
4. 支持页面级状态和备注回写
5. 接入 PPT Library 搜索结果
6. 接入 PPT Deck Pro Max 新生成页面
7. 增加导出前确认流程

## 成功标准

- 用户可以在浏览器里完整翻看一次组装后的 Deck 草案
- 每页都能看到来源、理由和原始路径
- 预览不依赖先导出 PPTX
- 断链、缺图、生成失败能在 UI 中明确显示
- 用户可以对页面做保留、替换、备注等轻量决策
- 预览状态可以关闭后恢复
