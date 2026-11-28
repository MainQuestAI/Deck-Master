use crate::error::{Error, Result};
use crate::model::{Canvas, Content, Deck, Page, Style};
use serde::Serialize;
use serde_json::json;
use sha2::{Digest, Sha256};

pub const IMAGE_BASIS_PREFIX: &str = "img-v2:";
pub const RENDER_BASIS_PREFIX: &str = "svg-v3:";
pub const LEGACY_SVG_V2_PREFIX: &str = "svg-v2:";

#[derive(Serialize)]
struct AssetBasisRef<'a> {
    id: &'a str,
    file: &'a str,
}

#[derive(Serialize)]
struct StyleBasis<'a> {
    canvas: &'a Canvas,
    palette: &'a [String],
    fonts: &'a [String],
    assets: Vec<AssetBasisRef<'a>>,
}

impl<'a> StyleBasis<'a> {
    fn for_page(style: &'a Style, page_id: &str) -> Self {
        let mut assets: Vec<_> = style
            .assets
            .iter()
            .filter(|asset| asset.is_effective_for(page_id))
            .map(|asset| AssetBasisRef {
                id: asset.id.as_str(),
                file: asset.file.as_str(),
            })
            .collect();
        assets.sort_by(|left, right| (left.id, left.file).cmp(&(right.id, right.file)));
        Self {
            canvas: &style.canvas,
            palette: &style.palette,
            fonts: &style.fonts,
            assets,
        }
    }
}

#[derive(Serialize)]
struct ImageBasisInput<'a> {
    content: &'a Content,
    layout: &'a str,
    purpose: &'a str,
    style: StyleBasis<'a>,
}

#[derive(Serialize)]
struct RenderBasisInput<'a> {
    content: &'a Content,
    purpose: &'a str,
    layout: &'a str,
    image_file: Option<&'a str>,
    style: StyleBasis<'a>,
}

// sha2 0.11 dropped LowerHex on digest output. Keep the 0.10 "{:x}" form:
// lowercase, two digits per byte, leading zeros preserved.
pub(crate) fn lower_hex(bytes: impl AsRef<[u8]>) -> String {
    bytes
        .as_ref()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn sha256_hex<T: Serialize>(input: &T) -> Result<String> {
    Ok(lower_hex(Sha256::digest(serde_json::to_vec(input)?)))
}

fn valid_hex_hash(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit())
}

pub(super) fn is_complete_render_basis(saved: &str) -> bool {
    saved
        .strip_prefix(RENDER_BASIS_PREFIX)
        .is_some_and(valid_hex_hash)
        || saved
            .strip_prefix(LEGACY_SVG_V2_PREFIX)
            .is_some_and(valid_hex_hash)
}

pub(super) fn basis_cache_algorithm(kind: &str, saved: &str) -> Option<&'static str> {
    if kind == "image" {
        if saved
            .strip_prefix(IMAGE_BASIS_PREFIX)
            .is_some_and(valid_hex_hash)
        {
            Some("img-v2")
        } else if saved == "imported" || valid_hex_hash(saved) {
            Some("img-legacy")
        } else {
            None
        }
    } else if saved
        .strip_prefix(RENDER_BASIS_PREFIX)
        .is_some_and(valid_hex_hash)
    {
        Some("svg-v3")
    } else if saved
        .strip_prefix(LEGACY_SVG_V2_PREFIX)
        .is_some_and(valid_hex_hash)
    {
        Some("svg-v2")
    } else if saved == "imported" || valid_hex_hash(saved) {
        Some("svg-legacy")
    } else {
        None
    }
}

pub fn basis(kind: &str, deck: &Deck, page: &Page) -> Result<String> {
    let style = StyleBasis::for_page(&deck.style, &page.id);
    if kind == "image" {
        let input = ImageBasisInput {
            content: &page.content,
            layout: &page.layout,
            purpose: &page.purpose,
            style,
        };
        Ok(format!("{IMAGE_BASIS_PREFIX}{}", sha256_hex(&input)?))
    } else {
        let input = RenderBasisInput {
            content: &page.content,
            purpose: &page.purpose,
            layout: &page.layout,
            image_file: page.image.as_ref().map(|image| image.file.as_str()),
            style,
        };
        Ok(format!("{RENDER_BASIS_PREFIX}{}", sha256_hex(&input)?))
    }
}

fn legacy_projected_style(deck: &Deck, page_id: &str) -> Style {
    let mut style = deck.style.clone();
    style.assets = style
        .assets
        .into_iter()
        .filter(|asset| asset.is_effective_for(page_id))
        .map(|asset| crate::model::Asset {
            id: asset.id,
            file: asset.file,
            pages: Vec::new(),
            source: String::new(),
            license: String::new(),
        })
        .collect();
    style
}

pub(super) fn calculate_legacy_basis(
    kind: &str,
    deck: &Deck,
    page: &Page,
    svg_v2: bool,
) -> Result<String> {
    let style = legacy_projected_style(deck, &page.id);
    let value = if kind == "image" {
        json!([page.content, page.layout, page.purpose, style])
    } else if svg_v2 {
        json!([
            page.content,
            page.purpose,
            page.layout,
            page.image.as_ref().map(|i| &i.file),
            style
        ])
    } else {
        json!([page.content, page.image.as_ref().map(|i| &i.file), style])
    };
    let hash = sha256_hex(&value)?;
    Ok(if matches!(kind, "svg" | "native") && svg_v2 {
        format!("{LEGACY_SVG_V2_PREFIX}{hash}")
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
    match basis_cache_algorithm(kind, saved) {
        Some("img-v2") => basis("image", deck, page),
        Some("img-legacy") => calculate_legacy_basis("image", deck, page, false),
        Some("svg-v3") => basis(kind, deck, page),
        Some("svg-v2") => calculate_legacy_basis(kind, deck, page, true),
        Some("svg-legacy") => calculate_legacy_basis(kind, deck, page, false),
        _ => {
            if kind == "image" {
                Err(Error::Input(
                    "无法识别图片制作依据；请保留原件并重新准备任务".into(),
                ))
            } else {
                Err(Error::Input(
                    "无法识别 SVG 制作依据；请保留原件并重新准备任务".into(),
                ))
            }
        }
    }
}

pub(super) fn image_is_stale(deck: &Deck, page: &Page) -> Result<bool> {
    match &page.image {
        Some(image) => match current_basis_for("image", &image.basis, deck, page) {
            Ok(current) => Ok(image.basis != current),
            Err(_) => Ok(true),
        },
        None => Ok(false),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Artifact, Asset, Block, Content, Deck, Page};
    use std::collections::BTreeSet;

    fn sample_deck() -> Deck {
        let mut deck = Deck::default();
        deck.style.palette = vec!["#FFFFFF".into(), "#14213D".into()];
        deck.style.fonts = vec!["Noto Sans CJK SC".into()];
        deck.style.assets = vec![
            Asset {
                id: "b-chart".into(),
                file: "bbbb.png".into(),
                pages: vec!["p1".into()],
                source: "internal".into(),
                license: "CC0".into(),
            },
            Asset {
                id: "a-logo".into(),
                file: "aaaa.png".into(),
                pages: vec![],
                source: "brand".into(),
                license: "MIT".into(),
            },
        ];
        deck.pages.push(Page {
            id: "p1".into(),
            purpose: "说明交付链路".into(),
            layout: "左图右文".into(),
            content: Content {
                title: "黄金契约页".into(),
                subtitle: "固定摘要".into(),
                body_blocks: vec![Block::Paragraph {
                    id: "a1".into(),
                    text: "正文第一段".into(),
                }],
                ..Content::default()
            },
            image: Some(Artifact {
                file: "orig.png".into(),
                basis: "imported".into(),
            }),
            ..Page::default()
        });
        deck
    }

    #[test]
    fn basis_hashes_are_pinned_and_order_independent_for_assets() {
        let deck = sample_deck();
        let img_basis = basis("image", &deck, &deck.pages[0]).unwrap();
        let svg_basis = basis("svg", &deck, &deck.pages[0]).unwrap();
        let native_basis = basis("native", &deck, &deck.pages[0]).unwrap();
        assert_eq!(svg_basis, native_basis);

        // Pin exact golden hashes so schema changes to Deck/Page cannot silently shift basis output.
        assert_eq!(
            img_basis,
            "img-v2:f3b2ef08d2dbf8604e393a7025927699192111c523628f970b4fd87deb5cdbbd"
        );
        assert_eq!(
            svg_basis,
            "svg-v3:5ada515af66d09ddb51ed2379d74466bcca7985e6ce1995c96ef067f8eaa0154"
        );

        let mut reordered = deck.clone();
        reordered.style.assets.reverse();
        assert_eq!(
            basis("image", &reordered, &reordered.pages[0]).unwrap(),
            img_basis
        );
        assert_eq!(
            basis("svg", &reordered, &reordered.pages[0]).unwrap(),
            svg_basis
        );
    }

    #[test]
    fn deck_and_page_serialized_key_sets_match_contract() {
        let deck = sample_deck();
        let deck_obj = serde_json::to_value(&deck).unwrap();
        let deck_keys: BTreeSet<_> = deck_obj
            .as_object()
            .unwrap()
            .keys()
            .map(String::as_str)
            .collect();
        assert_eq!(
            deck_keys,
            BTreeSet::from(["brief", "framing", "materials", "pages", "style"])
        );
        let page_keys: BTreeSet<_> = deck_obj["pages"][0]
            .as_object()
            .unwrap()
            .keys()
            .map(String::as_str)
            .collect();
        assert_eq!(
            page_keys,
            BTreeSet::from([
                "argument", "content", "id", "image", "kind", "layout", "native", "notes",
                "preview", "purpose", "refs", "svg", "todo"
            ])
        );
    }
}
