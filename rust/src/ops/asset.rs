use crate::error::{Error, Result};
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
