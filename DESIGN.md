# Deck Master Web UI 设计基线 · 2026-09-30

用户本轮已明确采用OpenDesign项目 **Deck Master · 全链路生成工作台 v3** 的现行设计；此文件替代旧Review Desk视觉及三栏布局约束。旧文档仅存于 [历史归档](docs/design/archive/DESIGN-review-desk-v1.md)。

## 产品职责

Web UI是Deck Master本机生成链路工作台：连接材料、内容整合/大纲、逐页稿、准备和实际提示词、原图、SVG、PPT、任务、候选与交付。用户可在开始时建项目/组织输入，在20–30页制作中连续看整稿和跨页风格，在结果返回时比较、采用或保留，在结束时检查与导出。不用Web仍可经CLI/制作工具工作；用了Web能减少逐文件切换，并保持所看页面、层、版本、意见和结果相对应。

## 设计源与优先级

1. [收讫设计体系](docs/design/webui-opendesign-20260930/design-system.html)及[产品语言](docs/design/webui-opendesign-20260930/product-ui-language.md)。应用产品覆盖，不只截取OpenAI基础token。
2. [当前index原型](docs/design/webui-opendesign-20260930/index.html)及[状态规范](docs/design/webui-opendesign-20260930/states.html)。样本动作不等于已有服务。
3. [生产适配决策](docs/specs/deck-master-webui-v4-20260930/DESIGN-ADAPTATION.md)、[A实现Spec](docs/specs/deck-master-webui-v4-20260930/A-UI-SPEC.md)与[B能力Spec](docs/specs/deck-master-webui-v4-20260930/B-CAPABILITIES-SPEC.md)。

## 视觉规则

浅色本机工具界面：白底、浅灰面、黑色主按钮、语义状态色和文字共同表达；使用产品无衬线字体，代码/身份按需等宽。现有OpenAI基础token的衬线display/绿色accent不自动用于产品标题/主按钮。字体仅使用合法随包资产或系统回退，无CDN；不为复刻采购或嵌入未经授权的字体。24单位SVG图标、1.75线宽；圆角、间距、按钮44px、表格16px横向留白按收讫规范。不得继续强制旧冷墨色/琥珀铜/Satoshi或固定三栏Review Desk布局。

## 布局与交互

项目入口 + 五工作面：制作总览、内容与来源、整稿画廊、风格校准、任务与交付；复用共享单页制作链。第一眼呈现当前事实、待办和下一动作。信息以业务对象为主，内部id/hash/命令放入必要详情。

普通表格保留Tab顺序，不冒充键盘grid；数字右对齐、对象左对齐、动作在末列，排序声明aria-sort。批量全选只含当前筛选中可操作对象；改变筛选清空批量选择，固定比较引用独立保存。候选同页同层，基准左/候选右，画布等比完整、正文用文本差异；窄屏先基准再候选。

状态表达真实事实：保存≠提交，复制≠接手，返回≠采用，采用≠检查通过，检查通过≠已发布。没有真实观察不展示风格偏离或生成成功。提供读/改/标注互斥、完整键盘替代、草稿保护及明确错误恢复。固定历史/比较不随后台结果漂移。

## 验证

设计样本、核心测试、真实浏览器、真实制作工具与最终安装验收分别记录。主验收视口1280×800和1440×900，窄屏按规范降级。状态参考页及模拟按钮不进入正式导航。默认切换与回退遵循现行发布门槛。
