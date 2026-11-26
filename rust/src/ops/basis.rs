use crate::error::{Error, Result};
use crate::model::{Deck, Page};
use serde_json::json;

pub fn basis(kind: &str, deck: &Deck, page: &Page) -> Result<String> {
    calculate_basis(kind, deck, page, false)
}

pub(super) fn calculate_basis(
    kind: &str,
    deck: &Deck,
    page: &Page,
    legacy: bool,
) -> Result<String> {
    use sha2::{Digest, Sha256};
    let mut style = deck.style.clone();
    // Only {id, file} affect page visuals; metadata (pages/source/license) must not invalidate already-bound pages.
    style.assets = style
        .assets
        .into_iter()
        .filter(|asset| asset.is_effective_for(&page.id))
        .map(|asset| crate::model::Asset {
            id: asset.id,
            file: asset.file,
            pages: Vec::new(),
            source: String::new(),
            license: String::new(),
        })
        .collect();
    let value = if kind == "image" {
        json!([page.content, page.layout, page.purpose, style])
    } else if legacy {
        json!([page.content, page.image.as_ref().map(|i| &i.file), style])
    } else {
        json!([
            page.content,
            page.purpose,
            page.layout,
            page.image.as_ref().map(|i| &i.file),
            style
        ])
    };
    let hash = format!("{:x}", Sha256::digest(serde_json::to_vec(&value)?));
    Ok(if matches!(kind, "svg" | "native") && !legacy {
        format!("svg-v2:{hash}")
    } else {
        hash
    })
}

pub(super) fn current_basis_for(
    kind: &str,
    saved: &str,
    deck: &Deck,
    page: &Page,
) -> Result<String> {
    let valid_hash =
        |value: &str| value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit());
    if kind == "image" {
        return basis(kind, deck, page);
    }
    if saved.strip_prefix("svg-v2:").is_some_and(valid_hash) {
        return basis(kind, deck, page);
    }
    if saved == "imported" || valid_hash(saved) {
        return calculate_basis(kind, deck, page, true);
    }
    Err(Error::Input(
        "无法识别 SVG 制作依据；请保留原件并重新准备任务".into(),
    ))
}

pub(super) fn image_is_stale(deck: &Deck, page: &Page) -> Result<bool> {
    match &page.image {
        Some(image) => Ok(image.basis != basis("image", deck, page)?),
        None => Ok(false),
    }
}
