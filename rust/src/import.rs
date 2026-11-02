use crate::error::{Error, Result};
use crate::model::{Artifact, Asset, Brief, Content, Deck, Framing, Material, Page, Style};
use crate::store::{self, Store};
use serde::Deserialize;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::{Component, Path, PathBuf};

const FORMAT: &str = "legacy-export.v1";

#[derive(Debug, Deserialize)]
struct Archive {
    format: String,
    #[serde(default)]
    brief: Brief,
    #[serde(default)]
    materials: Vec<MaterialSpec>,
    #[serde(default)]
    framing: Framing,
    #[serde(default)]
    style: Style,
    #[serde(default)]
    pages: Vec<Value>,
    last_export: Option<FileRef>,
    #[serde(default)]
    reviews: Vec<Value>,
    #[serde(default)]
    authorizations: Vec<Value>,
    #[serde(default)]
    open_calls: Vec<Value>,
    #[serde(default)]
    unmapped: Vec<Value>,
}

#[derive(Debug, Deserialize, Default)]
struct MaterialSpec {
    id: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    file: String,
    #[serde(default)]
    text_file: String,
    #[serde(default)]
    status: String,
}

#[derive(Debug, Deserialize)]
struct FileRef {
    file: String,
}

#[derive(Debug, Deserialize)]
struct PageSpec {
    id: String,
    #[serde(default)]
    purpose: String,
    #[serde(default)]
    layout: String,
    #[serde(default)]
    content: Content,
    #[serde(default)]
    notes: String,
    #[serde(default)]
    todo: Vec<String>,
    #[serde(default)]
    refs: Vec<String>,
    image: Option<FileRef>,
    svg: Option<FileRef>,
    preview: Option<String>,
}

pub fn from_archive(source: &Path, destination: &Path) -> Result<Value> {
    if destination.exists() {
        return Err(Error::Input(
            "目标已存在；请指定新目录，导入不会覆盖".into(),
        ));
    }
    let manifest_path = source.join("manifest.json");
    let archive: Archive =
        serde_json::from_slice(&std::fs::read(&manifest_path).map_err(|e| {
            Error::Input(format!(
                "无法读取档案 {manifest}：{e}；请指定 legacy-export 的输出目录",
                manifest = manifest_path.display()
            ))
        })?)?;
    if archive.format != FORMAT {
        return Err(Error::Input(format!(
            "档案格式为 {}，当前只接受 {FORMAT}",
            archive.format
        )));
    }
    // Build beside the destination and rename into place. A failure before the
    // rename drops the temporary directory, so a half-written project is not left
    // at the path the caller asked for.
    let parent = destination
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(parent)?;
    let staging = tempfile::Builder::new()
        .prefix(".deck-import-")
        .tempdir_in(parent)?;
    let report = import_staged(source, staging.path(), archive)?;
    let kept = staging.keep();
    if let Err(error) = std::fs::rename(&kept, destination) {
        let _ = std::fs::remove_dir_all(&kept);
        return Err(error.into());
    }
    Ok(report)
}

fn import_staged(source: &Path, destination: &Path, archive: Archive) -> Result<Value> {
    let mut unmapped = archive.unmapped;
    let mut deck = Deck {
        brief: archive.brief,
        framing: archive.framing,
        style: archive.style,
        ..Deck::default()
    };
    let mut store = Store::create(destination, &Deck::default())?;
    let mut files = HashMap::new();
    let mut materials = Vec::new();
    for spec in archive.materials {
        if spec.id.is_empty() {
            unmapped.push(json!({
                "kind": "material",
                "id": "",
                "reason": "材料缺少 id，未导入"
            }));
            continue;
        }
        let file = ingest(&store, source, &spec.file, &mut files)?;
        let text_file = ingest(&store, source, &spec.text_file, &mut files)?;
        let status = if !spec.status.is_empty() {
            spec.status
        } else if text_file.is_empty() {
            "needs_tool".into()
        } else {
            "read".into()
        };
        materials.push(Material {
            id: spec.id,
            name: spec.name,
            file,
            text_file,
            status,
        });
    }
    deck.materials = materials;
    let mut assets = Vec::new();
    for asset in deck.style.assets.drain(..) {
        if asset.file.is_empty() {
            return Err(Error::Input(format!(
                "素材 {} 缺少文件名；文件必须位于 files/ 下",
                asset.id
            )));
        }
        let file = ingest(&store, source, &asset.file, &mut files)?;
        assets.push(Asset { id: asset.id, file });
    }
    deck.style.assets = assets;
    let mut pages = Vec::new();
    for value in archive.pages {
        let id = value
            .get("id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let spec: PageSpec = match serde_json::from_value(value) {
            Ok(spec) => spec,
            Err(error) => {
                unmapped.push(json!({
                    "kind": "page",
                    "id": id,
                    "reason": format!("页无法映射：{error}")
                }));
                continue;
            }
        };
        if spec.id.is_empty() {
            unmapped.push(json!({
                "kind": "page",
                "id": "",
                "reason": "页面缺少 id，未导入"
            }));
            continue;
        }
        let mut page = Page {
            id: spec.id,
            purpose: spec.purpose,
            layout: spec.layout,
            content: spec.content,
            notes: spec.notes,
            todo: spec.todo,
            refs: spec.refs,
            image: None,
            svg: None,
            preview: None,
        };
        page.content.normalize_ids()?;
        page.image = artifact(&store, source, spec.image, &mut files, "原图")?;
        page.svg = artifact(&store, source, spec.svg, &mut files, "SVG")?;
        if let Some(name) = spec.preview {
            if name.is_empty() {
                return Err(Error::Input(
                    "预览文件名为空；文件必须位于 files/ 下".into(),
                ));
            }
            page.preview = Some(ingest(&store, source, &name, &mut files)?);
        }
        pages.push(page);
    }
    deck.pages = pages;
    let last_export = match archive.last_export {
        Some(FileRef { file }) if file.is_empty() => {
            return Err(Error::Input(
                "最近一次导出的文件名为空；文件必须位于 files/ 下".into(),
            ));
        }
        Some(FileRef { file }) => Some(ingest(&store, source, &file, &mut files)?),
        None => None,
    };
    for review in &archive.reviews {
        unmapped.push(json!({
            "kind": "review",
            "id": review.get("review_id").and_then(Value::as_str).unwrap_or(""),
            "reason": "旧审阅记录仅供查阅，不写入新作品意见"
        }));
    }
    for authorization in &archive.authorizations {
        unmapped.push(json!({
            "kind": "authorization",
            "id": authorization.get("authorization_id").and_then(Value::as_str).unwrap_or(""),
            "reason": "旧授权记录仅供查阅，不恢复"
        }));
    }
    let tx = store.transaction()?;
    let version = store::append(&tx, &deck, "从旧项目导入")?;
    if let Some(file) = &last_export {
        tx.execute(
            "INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?,?,?,?)",
            rusqlite::params![
                version,
                "imported",
                file,
                "[]",
                serde_json::to_string(
                    &deck
                        .pages
                        .iter()
                        .filter(|page| page.svg.is_none())
                        .map(|page| &page.id)
                        .collect::<Vec<_>>()
                )?
            ],
        )?;
    }
    tx.commit()?;
    Ok(json!({
        "version": version,
        "pages": deck.pages.len(),
        "materials": deck.materials.len(),
        "last_export": last_export.is_some(),
        "unmapped": unmapped,
        "open_calls": archive.open_calls,
    }))
}

fn artifact(
    store: &Store,
    source: &Path,
    spec: Option<FileRef>,
    files: &mut HashMap<String, String>,
    label: &str,
) -> Result<Option<Artifact>> {
    let Some(FileRef { file }) = spec else {
        return Ok(None);
    };
    if file.is_empty() {
        return Err(Error::Input(format!(
            "{label}的文件名为空；文件必须位于 files/ 下"
        )));
    }
    let name = ingest(store, source, &file, files)?;
    Ok(Some(Artifact {
        file: name,
        basis: "imported".into(),
    }))
}

fn ingest(
    store: &Store,
    source: &Path,
    name: &str,
    files: &mut HashMap<String, String>,
) -> Result<String> {
    if name.is_empty() {
        return Ok(String::new());
    }
    if let Some(existing) = files.get(name) {
        return Ok(existing.clone());
    }
    let path = named_file(source, name)?;
    let data = std::fs::read(&path)?;
    let ext = path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("bin");
    let stored = store.add_file(&data, ext)?;
    files.insert(name.into(), stored.clone());
    Ok(stored)
}

fn named_file(root: &Path, name: &str) -> Result<PathBuf> {
    let normal = matches!(
        Path::new(name).components().collect::<Vec<_>>().as_slice(),
        [Component::Normal(_)]
    );
    if name.is_empty() || !normal {
        return Err(Error::Input(format!(
            "档案文件名无效：{name}；文件必须位于 files/ 下"
        )));
    }
    let files = root
        .join("files")
        .canonicalize()
        .map_err(|_| Error::Input("档案缺少 files 目录；请指定 legacy-export 的输出目录".into()))?;
    let canonical = files
        .join(name)
        .canonicalize()
        .map_err(|_| Error::Input(format!("档案缺少文件 {name}；请检查 legacy-export 输出")))?;
    if !canonical.starts_with(&files) {
        return Err(Error::Input(format!("档案文件必须位于 files/ 内：{name}")));
    }
    Ok(canonical)
}
