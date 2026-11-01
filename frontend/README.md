# Deck Master WebUI

沿用 #250 的 React 18 + Vite 6 界面与视觉规则，S4 默认连接 `deck serve` 的当前作品，不提供演示模式。

## 本地构建与安装

```bash
cd frontend
npm ci
npm test
npm run build
cd ../rust
cargo build
# 或 cargo install --path .
```

Vite 输出至 `rust/web-dist/`，`build.rs` 将该目录全部嵌入二进制，安装后无需依赖磁盘上的前端目录。生成的 `assets/deck.js` 与 `assets/deck.css` 不入库。固定入口 `index.html` 入库并由构建保留；它同时是未构建时的提示页和已构建界面的入口，因此未运行 npm 时 Cargo 仍能编译。此时只能显示构建提示，完整分发必须先构建前端。入口文件名固定，服务端既有的 `Cache-Control: no-store` 防止旧资源缓存。

## 开发期联调

先用 `deck serve <project>` 启动服务，复制其打印的地址：

```bash
DECK_SERVE_URL=http://127.0.0.1:打印的端口 npm run dev
```

开发服务器仅监听本机，`/api` 代理改写 Host 与 Origin 为目标服务地址，不改变后端检查。不加载 `.env`，地址只读进程环境变量。开发期入口为 `frontend/index.html`，生产入口为 `rust/web-dist/index.html`。

## S4 范围

- 总览和整稿画廊：真实页序、正文、原图、编译预览及过期状态；空作品可新增第一页并进入制作。
- 单页正文与讲稿：保留段落、嵌套要点、表格、标签、强调、脚注的结构与标识；按字段编辑显示文字，不丢弃未编辑字段。草稿保留在当前浏览器会话内存中，收起抽屉或轮询不会清空。刷新页面会丢失未保存输入。
- 保存发送裸 patch；409 展示冲突和当前内容，保留输入，作者比较后可明确基于当前版本再次保存。不自动重发。
- 任务状态每 1.5 秒随作品轮询刷新，即使版本未变；停止只调用接口，不读取或写入浏览器存储。
- 构建与 Markdown/PPTX 下载：显示当前缺失/过期页，以及 `X-Deck-Status` 给出的构建变化提示；不设置导出门禁。版本历史可恢复为新版本。
- 当前 API 没有启动生图或 SVG 任务的接口，制作入口进入正文与讲稿编辑，产物任务仍由 Host 经 CLI 启动、交回，界面显示实际状态。

隐藏：S00 项目矩阵、S04 风格阶段与规范检测、S06 身份切换、S05 导出门禁、S5 页上意见/单页重做/候选比较及相关演示抽屉。未联调的原型源文件保留但不挂载；`constants/data.js` 没有进入运行时依赖图。快捷指挥台与其演示命令一并隐藏。

## 检查

```bash
npm test
npm ci && npm run build
```

纯逻辑测试使用 Node 内置 `node --test`，无新增依赖。浏览器联调使用仓库外临时合成项目；不将截图、运行日志或作品提交入库。
