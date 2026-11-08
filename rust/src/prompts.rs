use crate::error::Result;
use crate::model::{Block, Deck, Page};
use crate::store::Store;
use serde_json::json;
use std::fmt::Write as _;
use std::path::Path;

const IMAGE_GUIDANCE: &str = "让读者从主视觉看出上述信息关系。正文块的分组用于组织内容，版式由阅读任务决定。比较和查阅可用表格，流程用明确的方向和分支，分工可用分区或泳道。
逐字呈现可见文字，保留事实、数字、单位和限定。正文区的 Markdown 标记和“标签”“补充”“脚注”分组名用于说明结构。页面只显示实际文字。
让主要文字、连线和业务对象可以分开重建。照片、标志和复杂插画可放在边界清晰的区域。
不要为了方便转 SVG 先画成扁平色块；不要把整页当成最后必须压成零张图，pictures=0 不是目标，也不是失败。";

fn image_prompt(deck: &Deck, page: &Page, context: &str) -> String {
    let mut prompt = format!("生成一张演示文稿页面原图。\n{context}\n{IMAGE_GUIDANCE}\n");
    for (name, values) in [("色板", &deck.style.palette), ("字体", &deck.style.fonts)] {
        if !values.is_empty() {
            let _ = writeln!(prompt, "{name}　{}", values.join("、"));
        }
    }
    prompt.push_str("只使用 attachments.json 中已随附的文件，素材 ID 不能代替附件。\n");
    if deck
        .style
        .assets
        .iter()
        .any(|asset| asset.is_effective_for(&page.id))
    {
        prompt.push_str("使用随附的素材文件表达对应的图片或标志。\n");
    }
    if page.image.is_some() {
        prompt.push_str("最后一份附件是上一版原图，作为改版参考。\n");
    }

    let mut units = String::new();
    for (block_index, block) in page.content.body_blocks.iter().enumerate() {
        if let Block::Table { columns, rows, .. } = block {
            for (row_index, row) in rows.iter().enumerate() {
                for (column_index, column) in columns.iter().enumerate() {
                    if let Some(unit) = row
                        .cells
                        .iter()
                        .find(|cell| cell.column_id == column.id)
                        .and_then(|cell| cell.unit.as_deref())
                        .filter(|unit| !unit.is_empty())
                    {
                        let _ = writeln!(
                            units,
                            "- 正文块 {} 的表格，第 {} 行第 {} 列，单位 {unit}",
                            block_index + 1,
                            row_index + 1,
                            column_index + 1
                        );
                    }
                }
            }
        }
    }
    if !units.is_empty() {
        let _ = write!(prompt, "\n## 表格单位（用于理解显示文字）\n{units}");
    }

    let _ = write!(prompt, "\n## 可见文字\n\n# {}\n\n", page.content.title);
    crate::export::page_content(&mut prompt, &page.content);
    prompt
}

pub fn write(store: &Store, deck: &Deck, page: &Page, kind: &str, directory: &Path) -> Result<()> {
    std::fs::create_dir_all(directory)?;
    std::fs::write(
        directory.join("content.json"),
        serde_json::to_vec_pretty(&page.content)?,
    )?;
    std::fs::write(
        directory.join("style.json"),
        serde_json::to_vec_pretty(&deck.style)?,
    )?;
    let mut attachments = Vec::new();
    for asset in deck
        .style
        .assets
        .iter()
        .filter(|asset| asset.is_effective_for(&page.id))
    {
        let name = format!("asset-{}", asset.file);
        std::fs::copy(store.file(&asset.file)?, directory.join(&name))?;
        attachments.push(json!({"id": asset.id, "file": name}));
    }
    if let Some(image) = &page.image {
        let name = format!("original-{}", image.file);
        std::fs::copy(store.file(&image.file)?, directory.join(&name))?;
        attachments.push(json!({"role": "original", "file": name}));
    }
    std::fs::write(
        directory.join("attachments.json"),
        serde_json::to_vec_pretty(&attachments)?,
    )?;
    let context = format!(
        "画布 {}×{} px，物理尺寸 {}×{} in。\n本页目的：{}\n信息关系：{}\n",
        deck.style.canvas.width_px,
        deck.style.canvas.height_px,
        deck.style.canvas.slide_width_in,
        deck.style.canvas.slide_height_in,
        page.purpose,
        page.layout
    );
    let text = if kind == "svg" {
        let atoms = crate::tools::invoke("atoms", &json!({"page": page}))?;
        std::fs::write(
            directory.join("atoms.json"),
            serde_json::to_vec_pretty(&atoms)?,
        )?;
        std::fs::write(
            directory.join("svg-subset.md"),
            include_str!("../../deck-skill/references/svg-subset.md"),
        )?;
        std::fs::write(
            directory.join("reconstruction.md"),
            include_str!("../../deck-skill/references/reconstruction.md"),
        )?;
        format!(
            "{context}正文取 content.json，逐字上屏，不增删事实、数字或单位。不编造数字、日期或客户数据；页面文案不含缺口说明；缺口在 todo，不上屏，不放页脚。\n风格取 style.json。只使用 attachments.json 中已随附的原图和素材文件，素材 ID 不能代替附件。\n主要文字、节点、连线、分区、表格和标签必须成为可编辑对象；插画、质感、人物、复杂曲线可保留为有边界的图，照片和标志也须有清楚的边界，图片不能承载唯一正文。\n禁止把整页原图或蓝图当背景；禁止为了方便转 SVG 先压成扁平色块；禁止为了零张图（pictures=0）把流线或空间关系改成普通矩形或默认流程图。pictures=0 不是目标，也不是失败；对象计数、图片数不能代表质量。\n流程图、架构图、路径图只用于还原阶段的空间锚点和标签避让，不是规划菜单，也不替代构图句。\n\n按附件原图的对象、布局、层级和关系重建 SVG，不把 content.json 的正文块套进默认卡片、默认表或默认清单。分区说明、步骤说明、模块标题或带「→」的句子不能代替上屏控件或路径节点。\n界面原型内部按原图分区画出点名的上屏内容与对应控件，不留空白线框；只有框架和关键字不等于完成还原。分区说明可完整放在原型外侧作标注并绑定原 atom，内部仍须分别重画点名的控件与可编辑文字，不要求拆改 atom。句子型正文保持完整句子，多个入口、按钮和步骤节点仍须是多个可见对象。\n头像、图标宫格、商品图、内容图、状态栏等非纯文字对象用 SVG 子集重画，或裁成有边界的局部 PNG/JPEG，按现有 deck asset add 登记后用 image 引用素材 ID；需要新裁图时，先登记，再重新准备 SVG 任务取得新附件。关键文字仍须可编辑，生成或截取的界面标明示意属性，不能冒充真实产品截图。\n顾客旅程保留步骤空间顺序与人物、动作、场景层，不能只收成同尺寸模块卡片，除非原图本身如此；有方向的步骤保留节点边界、连线端点、方向、分支和回流，不收成箭头句或没有空间方向的两列清单，除非原图本身就是逐行核对的查阅清单。\n错漏文字、局部排版和依据明确的连线可沿用原图，依据正式正文和信息关系直接修 SVG；业务关系有歧义先问内容，主结构需要重排时先更新蓝图再重建。正文取 content.json，文字元素本身绑定 atoms.json 的 data-atom-id。对应 content.labels（含 children）中标签的节点必须写 data-node-ref，值为该标签 id；有向连线必须写 data-edge-ref。先读 svg-subset.md 和 reconstruction.md。\n字号 pt = font-size × 元素及祖先 transform 缩放 × k × 0.75；k = min(slide_width_in × 96 / width_px, slide_height_in × 96 / height_px)。低于 6pt 不可读。\n交回预览后，Host 必须实际打开预览 PNG 与原图，已有原图／编译预览对照功能时使用它。逐项核对界面身份／资产、分入口、内容区可视物、服务或操作入口是否仍在屏内；旅程步骤空间顺序与动作／场景层是否还在；路径节点、端点、方向、分支、回流、层级、侧栏与阅读顺序是否保留。写清哪些对象缺失或变成说明文字、默认卡片或清单。文字回读、字符串齐全、对象计数、图片数或机械 findings 通过均不能代替对照原图；回读不代替视觉比对。只证明文字覆盖、未比对对象与关系时，记重建未完成，按原图修正后重交；visual_review、desktop_editing 仍为 not_evaluated，不改成自动通过。\n"
        )
    } else {
        image_prompt(deck, page, &context)
    };
    std::fs::write(directory.join("task.md"), text)?;
    Ok(())
}
