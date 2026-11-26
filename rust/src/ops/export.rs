use crate::error::{Error, Result};
use crate::ops::build::{artifact_status, default_build, stale_image_warnings};
use crate::ops::native::{plan_refs, readable_native_plan, with_shared_layout};
use crate::ops::review::content_review_status;
use crate::store::{self, Store};
use serde_json::{Value, json};
use std::path::Path;

pub fn export_md(project: &Path) -> Result<String> {
    Ok(export_markdown(project)?.0)
}

pub fn export_markdown(project: &Path) -> Result<(String, Value)> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
    let deck = snapshot.deck;
    let mut status = artifact_status(&deck)?;
    status["content_review"] = content_review_status(&store.connection, snapshot.version, &deck)?;
    Ok((crate::export::markdown(&deck), status))
}

pub fn export_pptx(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let tx = store.connection.transaction()?;
    let current = store::current(&tx)?;
    let deck = current.deck;
    let mut selected = default_build(&tx, &deck)?
        .ok_or_else(|| Error::Input("尚无构建；请先运行 deck build".into()))?;
    let file = selected["file"]
        .as_str()
        .ok_or_else(|| Error::Tool("构建缺少文件引用".into()))?;
    selected["path"] = json!(store::file_path(&store.root, file)?);
    selected.as_object_mut().map(|value| value.remove("file"));
    let status = artifact_status(&deck)?;
    selected["missing_pages"] = status["missing_pages"].clone();
    selected["stale_pages"] = status["stale_pages"].clone();
    selected["stale_images"] = status["stale_images"].clone();
    let mut plans = Vec::new();
    for page in &deck.pages {
        let Some(artifact) = &page.native else {
            continue;
        };
        // The selected PPTX is already built. A missing pack only drops this advisory warning.
        let Some(plan) = readable_native_plan(&store.root, &artifact.file) else {
            continue;
        };
        plans.push((page.id.clone(), plan));
    }
    selected["warnings"] = with_shared_layout(
        stale_image_warnings(&status["stale_images"]),
        &plan_refs(&plans),
    );
    selected["incomplete_basis_pages"] = status["incomplete_basis_pages"].clone();
    let source_version = selected["version_id"]
        .as_i64()
        .ok_or_else(|| Error::Tool("构建缺少来源版本".into()))?;
    let source = store::load(&tx, source_version)?;
    selected["content_review"] = content_review_status(&tx, source_version, &source)?;
    selected["current_content_review"] = content_review_status(&tx, current.version, &deck)?;
    Ok(selected)
}

pub fn doctor(fonts: &[String]) -> Result<Value> {
    crate::tools::invoke("doctor", &json!({"fonts":fonts}))
}
