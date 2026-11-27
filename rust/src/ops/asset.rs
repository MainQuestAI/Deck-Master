use crate::error::{Error, Result};
use crate::model::Artifact;
use crate::ops::basis::basis;
use crate::ops::run::file_url;
use crate::store::{self, Store};
use serde_json::{Value, json};
use std::collections::HashSet;
use std::path::Path;

pub fn asset_add(
    project: &Path,
    id: &str,
    input: &Path,
    pages: &[String],
    source: &str,
    license: &str,
) -> Result<Value> {
    if id.is_empty() {
        return Err(Error::Input("素材 ID 不能为空".into()));
    }
    let mut store = Store::open(project)?;
    let root = store.root.clone();
    let has_page_scope = !pages.is_empty();
    let mut seen = HashSet::new();
    let pages: Vec<String> = pages
        .iter()
        .flat_map(|value| value.split(','))
        .map(str::trim)
        .filter(|page| !page.is_empty() && seen.insert((*page).to_owned()))
        .map(str::to_owned)
        .collect();
    if has_page_scope && pages.is_empty() {
        return Err(Error::Input(
            "--page 未包含有效页面 ID；请指定页面，公共素材请省略 --page".into(),
        ));
    }
    // Reject unknown pages before copying files or invoking the SVG renderer.
    let snapshot = store.current()?;
    for page in &pages {
        if !snapshot.deck.pages.iter().any(|p| &p.id == page) {
            return Err(Error::Input(format!(
                "页面 {page} 不存在；请用 deck show 查看页面"
            )));
        }
    }
    let ext = input.extension().and_then(|v| v.to_str()).unwrap_or("bin");
    let is_svg = ext.eq_ignore_ascii_case("svg");
    let temporary = tempfile::tempdir()?;
    let output_path = temporary.path().join("normalized");
    let info = crate::tools::invoke(
        "normalize-image",
        &json!({
            "path": input.canonicalize()?,
            "output": output_path,
            "svg": is_svg,
        }),
    )?;
    let (data, ext) = if info["normalized"].as_bool() == Some(true) {
        let out_ext = match info["format"].as_str() {
            Some("PNG") => "png",
            Some("JPEG") => "jpg",
            _ => {
                return Err(Error::Tool(
                    "normalize-image 未返回 PNG 或 JPEG 格式".into(),
                ));
            }
        };
        (std::fs::read(&output_path)?, out_ext)
    } else {
        (std::fs::read(input)?, ext)
    };
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
    for page in &pages {
        if !snapshot.deck.pages.iter().any(|p| &p.id == page) {
            return Err(Error::Input(format!(
                "页面 {page} 不存在；请用 deck show 查看页面"
            )));
        }
    }
    let file = store::add_file(&root, &data, ext)?;
    let asset = crate::model::Asset {
        id: id.into(),
        file,
        pages,
        source: source.into(),
        license: license.into(),
    };
    if let Some(old) = snapshot.deck.style.assets.iter_mut().find(|a| a.id == id) {
        *old = asset.clone();
    } else {
        snapshot.deck.style.assets.push(asset.clone());
    }
    let asset_changed = snapshot.deck != store::current(&tx)?.deck;
    if asset_changed {
        snapshot.version = store::append(&tx, &mut snapshot.deck, "选择素材")?;
    }
    tx.commit()?;
    Ok(json!({"version": snapshot.version, "asset": asset}))
}

pub fn style_theme_set(project: &Path, input: &Path) -> Result<Value> {
    let canonical = input
        .canonicalize()
        .map_err(|_| Error::Input(format!("母版模板文件不存在：{}", input.display())))?;
    let is_pptx = canonical
        .extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("pptx"));
    if !is_pptx {
        return Err(Error::Input("母版主题只支持 .pptx 文件".into()));
    }
    let mut store = Store::open(project)?;
    let root = store.root.clone();
    let temporary = tempfile::tempdir()?;
    let output_path = temporary.path().join("theme.pptx");
    let info = crate::tools::invoke(
        "sanitize-template",
        &json!({
            "path": canonical,
            "output": output_path,
        }),
    )?;
    let cleaned = std::fs::read(&output_path)?;
    let file = store::add_file(&root, &cleaned, "pptx")?;
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
    let changed = snapshot.deck.style.theme.as_deref() != Some(file.as_str());
    snapshot.deck.style.theme = Some(file.clone());
    if changed {
        snapshot.version = store::append(&tx, &mut snapshot.deck, "设置母版主题")?;
    }
    tx.commit()?;
    Ok(json!({
        "version": snapshot.version,
        "theme": file,
        "layouts": info["layouts"],
    }))
}

pub fn style_theme_clear(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
    if snapshot.deck.style.theme.is_some() {
        snapshot.deck.style.theme = None;
        snapshot.version = store::append(&tx, &mut snapshot.deck, "清除母版主题")?;
    }
    tx.commit()?;
    Ok(json!({
        "version": snapshot.version,
        "theme": Value::Null,
    }))
}

pub fn page_image_upload(
    project: &Path,
    page_id: &str,
    bytes: &[u8],
    content_type: &str,
) -> Result<Value> {
    if bytes.is_empty() {
        return Err(Error::Input("上传的图片文件为空".into()));
    }
    let input_ext = match content_type.to_ascii_lowercase().as_str() {
        "image/png" => "png",
        "image/jpeg" | "image/jpg" => "jpg",
        _ => return Err(Error::Input("原图上传只支持 PNG 或 JPEG 图片".into())),
    };
    let mut store = Store::open(project)?;
    let root = store.root.clone();
    let initial = store.current()?;
    if initial.deck.page(page_id).is_none() {
        return Err(Error::Missing(format!("页面 {page_id} 不存在")));
    }

    let temporary = tempfile::tempdir()?;
    let input_path = temporary.path().join(format!("upload.{input_ext}"));
    let output_path = temporary.path().join("normalized");
    std::fs::write(&input_path, bytes)?;
    let info = crate::tools::invoke(
        "normalize-image",
        &json!({
            "path": input_path.canonicalize()?,
            "output": output_path,
            "svg": false,
        }),
    )?;
    let out_ext = match info["format"].as_str() {
        Some("PNG") => "png",
        Some("JPEG") => "jpg",
        _ => return Err(Error::Input("原图上传只支持 PNG 或 JPEG 图片".into())),
    };
    let data = if info["normalized"].as_bool() == Some(true) {
        std::fs::read(&output_path)?
    } else {
        bytes.to_vec()
    };

    // Re-read the latest deck inside the write transaction and touch only page.image,
    // so concurrent text/notes edits on this or other pages are never overwritten.
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
    let page_index = snapshot
        .deck
        .pages
        .iter()
        .position(|p| p.id == page_id)
        .ok_or_else(|| Error::Missing(format!("页面 {page_id} 不存在")))?;
    let image_basis = basis("image", &snapshot.deck, &snapshot.deck.pages[page_index])?;
    let file = store::add_file(&root, &data, out_ext)?;
    let artifact = Artifact {
        file: file.clone(),
        basis: image_basis,
    };
    let changed = snapshot.deck.pages[page_index].image.as_ref() != Some(&artifact);
    snapshot.deck.pages[page_index].image = Some(artifact.clone());
    if changed {
        snapshot.version = store::append(&tx, &mut snapshot.deck, "上传页面原图")?;
    }
    tx.commit()?;
    Ok(json!({
        "version": snapshot.version,
        "page_id": page_id,
        "image": artifact,
        "image_url": file_url(&file),
        "width": info["width"],
        "height": info["height"],
    }))
}
