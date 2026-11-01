use crate::error::Result;
use crate::model::{Deck, Page};
use crate::store::Store;
use serde_json::json;
use std::path::Path;

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
    for asset in &deck.style.assets {
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
    let common = format!(
        "画布 {}×{} px，物理尺寸 {}×{} in。\n本页目的：{}\n信息关系：{}\n正文取 content.json，逐字上屏，不增删事实、数字或单位。不编造数字、日期或客户数据；缺口照常写明。\n风格取 style.json；attachments.json 列出的素材文件必须作为 ImageGen 附件传入，不用文字描述代替。\n比较或查阅用表格，时序用步骤，流程用连线与分支，分工用泳道或分区。\n文字、连线、主要业务对象须可拆成可编辑元素；照片、logo、复杂插画只占有边界的位图区域，不承载正文。\n",
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
        format!(
            "{common}\n按附件原图的布局、层级和关系重建 SVG。正文取 content.json，文字元素本身绑定 atoms.json 的 data-atom-id。先读 svg-subset.md。\n字号 pt = font-size × 元素及祖先 transform 缩放 × k × 0.75；k = min(slide_width_in × 96 / width_px, slide_height_in × 96 / height_px)。低于 6pt 不可读。\n交回预览后，Host 必须对照原图逐项检查端点、方向、分支、层级、侧栏与阅读顺序；回读不代替视觉比对。有问题修正后重交。\n"
        )
    } else {
        common
    };
    std::fs::write(directory.join("task.md"), text)?;
    Ok(())
}
