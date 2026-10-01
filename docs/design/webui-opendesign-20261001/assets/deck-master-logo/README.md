# Deck Master · Master Frame C · 细化稿 v1

用户已确认选择 C 并继续细化；本包是该方向的首轮细化资产，尚未获得用户对细化稿本身的最终批准。

保留几何 M、对角定位框、上下字标和冷灰配色。定位角从母版 18 单位增厚到 24 单位，M 竖笔从 24 单位增厚到 28 单位，并使外框上下对称。缩短图标和字标的间距，主字标采用 IBM Plex Mono Regular，已转轮廓。新增横向组合，供应用导航栏与横向页眉使用。

## 直接使用

- 主品牌组合：`logo-stacked-dark.svg` 或 `logo-stacked-light.svg`。
- 横向页眉：`logo-horizontal-dark.svg` 或 `logo-horizontal-light.svg`。
- 独立图标：`icon-dark.svg`、`icon-light.svg`、`icon-mono.svg`。
- 小尺寸：使用对应 `icon-16-*`、`icon-24-*`、`icon-32-*`，不要缩放母版替代。这三个尺寸单独调整定位角和笔画，水平及垂直边对齐整数像素。
- 网站图标：`favicon.svg` 会按浏览器的深浅主题切换前景色。
- 应用图标：`app-icon.svg / .png` 为 512px 冷墨方形底图，由目标平台施加图标遮罩。

`dark` 表示供深色背景使用的冷白前景；`light` 表示供浅色背景使用的冷墨前景。除应用图标和展示图，文件背景均透明。`mono` 使用 `currentColor`，适合 inline SVG 继承容器颜色。

## 颜色与字形

- 冷墨：`#161B22`。
- 冷白：`#E6E9EE`。
- 单色使用，不增加渐变、阴影、光晕或彩色外框。
- 正式字标已是路径，显示时无需安装字体。
- 保持 SVG 宽高比；常规图标周围留出至少半个 M 竖笔宽的空白。16–32px 专用图标使用其文件内置留白。

已完成 SVG XML 与字标轮廓检查、深浅底渲染检查、原尺寸图标视觉检查、下载包完整性检查。尚未接入项目 UI。

`source/` 包含再生脚本、字体与许可；`MANIFEST.json` 记录资产的 SHA-256。使用 IBM Plex Mono 字体继续编辑时遵循随包附带的 SIL OFL 1.1 许可。
