# SVG 重建与预览比对

仅使用 compiler/svg.py 接受的子集。数值（包括 font-size）不带单位；根元素使用从 0 0 开始的正数 viewBox。

元素：svg、g、defs、use、rect、circle、ellipse、line、polyline、polygon、path、text、tspan、image、linearGradient、radialGradient、stop。path 支持 M/L/H/V/C/S/Q/T/A/Z。

不要重复引用 defs 中带 id 的组，以免多个实例合并成同一个 PPT 组并改变叠放顺序。

通用属性：id、transform、fill、stroke、stroke-width、fill-opacity、stroke-opacity、opacity、stroke-linecap、stroke-linejoin、stroke-miterlimit、font-family、font-size、font-weight、text-anchor、letter-spacing，以及编译器的 data-atom-id、data-node-ref、data-edge-ref、data-table-id、data-row-id、data-column-id、data-cell-id。几何属性按元素使用 x/y/width/height/rx/ry/cx/cy/r/x1/y1/x2/y2/points/d，text 使用 x/y，tspan 使用 x/y/dx/dy。实际支持以解析器报错为准。

未列出的属性（包括 class）以及 filter、mask、clip-path 会报错。style 只接受解析器列出的颜色、字体、透明度、描边与字距项，不接受布局 CSS。g 只向下继承颜色与字体；data-atom-id 必须写在文字元素本身。文字不支持非等比缩放；带描边的非等比变换应改为显式轮廓。image 的 href 只能用 assets 中的素材 ID，文件只支持 PNG/JPEG；不能引用任意文件、网络 URL 或内嵌 data URL。

正文按 atoms.json 绑定，不把整页原图嵌入 SVG。一个要点使用一个 text，保留完整句子，不在词中间硬折行。用 `data-text-width`、`data-text-height` 指定可编辑文本框的像素宽高，编译后自动换行；该模式下 tspan 文字合并为同一段，不保留人工折行。真正的项目符号用 `data-bullet="true"`，不要把圆点写进正文。未指定边界的旧 SVG 仍按原坐标编译。

```xml
<svg viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#ffffff"/>
  <text x="64" y="88" font-family="Noto Sans CJK SC" font-size="36"
        fill="#16324f" data-atom-id="atom:p1:title">方案主张</text>
  <line x1="200" y1="300" x2="600" y2="300" stroke="#16324f" stroke-width="3"/>
</svg>
```

连线先定义清楚起点与终点所代表的对象；折线先离开起点边界，再进入终点边界。检查每条线是否真正到达对象、箭头是否对应业务方向、分支是否回到正确对象。文字框不能遮住端点。

Host 用 check-page 返回的 PNG 与原图比对：逐项核对端点、方向、分支、层级、侧栏和阅读顺序。字数齐全不能证明关系正确。故意移动一个端点后，须在预览中定位该处再修正；不要把文字回读通过当作关系检查完成。


## 常见关系的构造样例

箭头用显式三角形，不用 marker-end。线段先画在节点下方，节点填充遮住穿过内部的线；可见线段应接到节点边界。下面的方向是左到右，三角形尖端在右侧节点边界。

```xml
<line x1="200" y1="300" x2="600" y2="300" stroke="#16324f" stroke-width="3"/>
<rect x="100" y="260" width="200" height="80" fill="#e8f2f6"/>
<rect x="500" y="260" width="200" height="80" fill="#e8f2f6"/>
<path d="M 488 294 L 500 300 L 488 306 Z" fill="#16324f"/>
```

表格保持列边界与行边界，文字不可越过自己的单元格。外框绑定表格块 ID，列标题与单元格文字绑定相应 atom，不用相同内容代替不同位置的文字。示例表格在正文中应为两列一行；这里省略文字以突出边界。

```xml
<rect x="64" y="180" width="1152" height="240" fill="none"
      stroke="#9aabb9" data-table-id="table1"/>
<line x1="400" y1="180" x2="400" y2="420" stroke="#9aabb9"/>
<line x1="64" y1="260" x2="1216" y2="260" stroke="#9aabb9"/>
```

原图有侧栏时，保留侧栏与主流程之间的层级，不把侧栏里的限定移入讲稿。主流程按原图阅读方向分配空间；反馈线走节点之外，明确回到哪个节点，不能只画一个装饰性环形箭头。长正文先按标点换行，再确定字号和节点边界；不要用整体缩放把文字压到不可读。


原生回读需要完整的表格网格：分隔线必须用 line 元素，纵线贯穿表头与所有数据行，横线贯穿全表宽度；不要用 path 代替分隔线或重复画同一条线。所有线都须与外框相接。缺网格时会报告无法证明单元格归属，不能当作通过。标点不得被挤到下一行行首；英文产品名保持完整，先调整换行再缩小字号。

原图偶尔会重复标题或增加装饰标签，重建以 content 为正文依据。保留业务关系与阅读顺序，不把图像生成的额外文字写成新事实。


## 可编辑对象

标题绑定 `atom:<page>:title` 后写成标题占位符，可在大纲中读取。卡片或模块放进带可读 id 的 g，编译后保持成组；模块内不要再嵌套模块。形状名称由 SVG 的 id 或 data-group 与角色组成，例如“标题”“卡片-要点1-正文”“表格-评分项”，导出后仍保留。讲稿由作品 notes 传入，只写这页如何讲述与过渡；方法依据另存作品目录。正文直接写“535类”“CDP、VOC”。

比较或查阅表格的外框加 `data-native-table="true"` 和可读 id，外框、全部分隔线与单元格文字均绑定相同的 `data-table-id`；每行、每列保留完整直线网格。单元格内的多个 text 按位置组成段落；有 data-text-width 的 text 保留 tspan 局部字重与颜色。编译后生成真正的 PPT 表格，首行标为表头。原生表格直接回读单元格文字，不套用旧线针对分离形状的网格检查；改字后的折行与空间须看真实预览。正文最小 12pt；留出改字和换字体后的自动换行空间。
