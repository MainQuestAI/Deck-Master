use crate::error::{Conflict, Error, Result};
use crate::model::{Brief, Deck, Page, Patch, Snapshot, Style};
use crate::store::{self, Store};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::path::Path;

pub fn import(source: &Path, destination: &Path) -> Result<Value> {
    crate::import::from_archive(source, destination)
}

pub fn new(project: &Path, title: String) -> Result<Snapshot> {
    let deck = Deck {
        brief: Brief {
            title,
            ..Brief::default()
        },
        style: Style {
            palette: ["#164267", "#F5F7FA", "#D97706"].map(String::from).into(),
            fonts: vec!["Noto Sans CJK SC".into()],
            ..Style::default()
        },
        ..Deck::default()
    };
    Store::create(project, &deck)?.current()
}

pub fn get(project: &Path, pages: Option<&[String]>) -> Result<Value> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
    snapshot_value(&snapshot, pages)
}

pub fn version_get(project: &Path, version: i64) -> Result<Snapshot> {
    if version <= 0 {
        return Err(Error::Input("版本编号必须是正整数".into()));
    }
    let store = Store::open(project)?;
    let deck = store::load_optional(&store.connection, version)?
        .ok_or_else(|| Error::Missing(format!("版本 {version} 不存在；请从版本历史中重新选择")))?;
    Ok(Snapshot { version, deck })
}

fn snapshot_value(snapshot: &Snapshot, pages: Option<&[String]>) -> Result<Value> {
    let mut deck = serde_json::to_value(&snapshot.deck)?;
    if let Some(ids) = pages {
        for id in ids {
            if !snapshot.deck.pages.iter().any(|p| &p.id == id) {
                return Err(Error::Input(format!(
                    "页面 {id} 不存在；请用 deck show 查看页面"
                )));
            }
        }
        deck["pages"] = serde_json::to_value(
            snapshot
                .deck
                .pages
                .iter()
                .filter(|p| ids.contains(&p.id))
                .collect::<Vec<_>>(),
        )?;
    } else {
        deck["order"] = json!(
            snapshot
                .deck
                .pages
                .iter()
                .map(|p| &p.id)
                .collect::<Vec<_>>()
        );
    }
    // A partial read omits order so an ordinary page edit cannot delete unseen pages.
    Ok(
        json!({ "version": snapshot.version, "deck": deck, "artifact_status": artifact_status(&snapshot.deck)? }),
    )
}

pub fn workspace(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    // A deferred read transaction keeps the polling response on one snapshot,
    // without reserving SQLite's writer slot.
    let tx = store.connection.transaction()?;
    let snapshot = store::current(&tx)?;
    let mut value = snapshot_value(&snapshot, None)?;
    value["default_build"] = match default_build(&tx, &snapshot.deck)? {
        Some(mut selected) => {
            selected.as_object_mut().map(|value| value.remove("file"));
            selected
        }
        None => Value::Null,
    };
    value["runs"] = json!(runs(&tx, &snapshot.deck, None)?);
    let reviews = reviews(&tx, Some("open"), None)?;
    for page in value["deck"]["pages"].as_array_mut().into_iter().flatten() {
        page["open_reviews"] = json!(page_review_count(
            &reviews,
            page["id"].as_str().unwrap_or("")
        ));
    }
    value["open_reviews_total"] = json!(reviews.len());
    value["reviews"] = json!(reviews);
    let mut query = tx.prepare("SELECT id,created_at,summary FROM versions ORDER BY id DESC")?;
    value["history"] = json!(
        query
            .query_map([], |row| Ok(store::Version {
                id: row.get(0)?,
                created_at: row.get(1)?,
                summary: row.get(2)?
            }))?
            .collect::<std::result::Result<Vec<_>, _>>()?
    );
    Ok(value)
}

pub fn project_file(project: &Path, sha: &str) -> Result<std::path::PathBuf> {
    if sha.len() != 64 || !sha.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err(Error::Input("文件 sha 必须是 64 位十六进制".into()));
    }
    let store = Store::open(project)?;
    let directory = store.root.join("files").canonicalize()?;
    let sha = sha.to_ascii_lowercase();
    let mut entries = std::fs::read_dir(&directory)?.collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        if name.split_once('.').is_some_and(|(hash, _)| hash == sha) {
            let path = store.file(name)?.canonicalize()?;
            if path.starts_with(&directory) {
                return Ok(path);
            }
            return Err(Error::Input("附件必须位于当前项目 files 目录内".into()));
        }
    }
    Err(Error::Missing(format!("附件 {sha} 不存在;请先添加附件")))
}

pub fn show(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let tx = store.connection.transaction()?;
    let snapshot = store::current(&tx)?;
    let reviews = reviews(&tx, Some("open"), None)?;
    let mut query = tx.prepare("SELECT id,created_at,summary FROM versions ORDER BY id DESC")?;
    let history = query
        .query_map([], |row| {
            Ok(store::Version {
                id: row.get(0)?,
                created_at: row.get(1)?,
                summary: row.get(2)?,
            })
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    Ok(json!({
        "version": snapshot.version,
        "title": snapshot.deck.brief.title,
        "thesis": snapshot.deck.framing.thesis,
        "materials": snapshot.deck.materials.iter().map(|m| json!({"id": m.id, "name": m.name, "status": m.status})).collect::<Vec<_>>(),
        "pages": snapshot.deck.pages.iter().map(|p| json!({"id": p.id, "title": p.content.title, "purpose": p.purpose, "todo": p.todo, "open_reviews": page_review_count(&reviews, &p.id)})).collect::<Vec<_>>(),
        "open_reviews_total": reviews.len(),
        "artifact_status": artifact_status(&snapshot.deck)?,
        "history": history
    }))
}

#[derive(Debug, Serialize)]
pub struct Review {
    pub id: i64,
    pub version_id: i64,
    pub page_id: Option<String>,
    pub reviewer: String,
    pub method: String,
    pub text: String,
    pub status: String,
    pub created_at: String,
    pub resolved_at: Option<String>,
}

fn review_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Review> {
    Ok(Review {
        id: row.get(0)?,
        version_id: row.get(1)?,
        page_id: row.get(2)?,
        reviewer: row.get(3)?,
        method: row.get(4)?,
        text: row.get(5)?,
        status: row.get(6)?,
        created_at: row.get(7)?,
        resolved_at: row.get(8)?,
    })
}

fn reviews(
    connection: &rusqlite::Connection,
    status: Option<&str>,
    page: Option<&str>,
) -> Result<Vec<Review>> {
    use rusqlite::params;
    if status.is_some_and(|s| !["open", "resolved"].contains(&s)) {
        return Err(Error::Input("意见状态只接受 open 或 resolved".into()));
    }
    let mut query = connection.prepare(
        "SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at
         FROM reviews WHERE (?1 IS NULL OR status=?1) AND (?2 IS NULL OR page_id=?2) ORDER BY id",
    )?;
    Ok(query
        .query_map(params![status, page], review_row)?
        .collect::<std::result::Result<_, _>>()?)
}

fn review(connection: &rusqlite::Connection, id: i64) -> Result<Review> {
    use rusqlite::OptionalExtension;
    connection.query_row(
        "SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at FROM reviews WHERE id=?",
        [id], review_row,
    ).optional()?.ok_or_else(|| Error::Missing(format!("意见 {id} 不存在;请用 deck review list 查看")))
}

fn page_review_count(reviews: &[Review], page: &str) -> usize {
    reviews
        .iter()
        .filter(|r| r.page_id.as_deref() == Some(page))
        .count()
}

pub fn review_add(
    project: &Path,
    page: Option<&str>,
    text: &str,
    reviewer: &str,
    method: &str,
) -> Result<Review> {
    use rusqlite::params;
    if text.trim().is_empty() {
        return Err(Error::Input("意见内容不能为空".into()));
    }
    if !["self_check", "other_model", "human"].contains(&method) {
        return Err(Error::Input(
            "意见方法只接受 self_check、other_model 或 human".into(),
        ));
    }
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    let snapshot = store::current(&tx)?;
    if let Some(page) = page
        && !snapshot.deck.pages.iter().any(|p| p.id == page)
    {
        return Err(Error::Input(format!(
            "页面 {page} 不存在；请用 deck show 查看页面"
        )));
    }
    tx.execute(
        "INSERT INTO reviews(version_id,page_id,reviewer,method,text) VALUES (?,?,?,?,?)",
        params![snapshot.version, page, reviewer, method, text],
    )?;
    let value = review(&tx, tx.last_insert_rowid())?;
    tx.commit()?;
    Ok(value)
}

pub fn review_list(project: &Path, status: Option<&str>, page: Option<&str>) -> Result<Value> {
    let store = Store::open(project)?;
    Ok(json!({"reviews": reviews(&store.connection, status, page)?}))
}

pub fn review_resolve(project: &Path, id: i64) -> Result<Review> {
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    tx.execute("UPDATE reviews SET status='resolved',resolved_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='open'", [id])?;
    let value = review(&tx, id)?;
    tx.commit()?;
    Ok(value)
}

fn merge<T: PartialEq + Clone + Serialize>(
    unit: &str,
    base: &T,
    submitted: &T,
    current: &mut T,
    conflicts: &mut Vec<Conflict>,
) -> Result<()> {
    if submitted == base || submitted == current {
        return Ok(());
    }
    if current == base {
        *current = submitted.clone();
    } else {
        conflicts.push(Conflict {
            unit: unit.into(),
            current: serde_json::to_value(current)?,
        });
    }
    Ok(())
}

pub fn put(project: &Path, version: i64, patch: Patch) -> Result<Snapshot> {
    let mut store = Store::open(project)?;
    let root = store.root.clone();
    let tx = store.transaction()?;
    let base = store::load(&tx, version)?;
    let current = store::current(&tx)?;
    let mut deck = current.deck.clone();
    let mut conflicts = Vec::new();
    if let Some(value) = patch.brief {
        merge(
            "brief",
            &base.brief,
            &value,
            &mut deck.brief,
            &mut conflicts,
        )?;
    }
    if let Some(value) = patch.framing {
        merge(
            "framing",
            &base.framing,
            &value,
            &mut deck.framing,
            &mut conflicts,
        )?;
    }
    if let Some(value) = patch.style {
        merge(
            "style",
            &base.style,
            &value,
            &mut deck.style,
            &mut conflicts,
        )?;
        for asset in &deck.style.assets {
            if !current.deck.style.assets.contains(asset) {
                crate::store::file_path(&root, &asset.file)?;
            }
        }
    }

    let base_order: Vec<_> = base.pages.iter().map(|p| p.id.clone()).collect();
    let current_order: Vec<_> = current.deck.pages.iter().map(|p| p.id.clone()).collect();
    let mut order = current_order.clone();
    let submitted_order = patch.order.as_ref().unwrap_or(&base_order);
    if let Some(value) = &patch.order {
        let mut ids = HashSet::new();
        if value.iter().any(|id| id.is_empty() || !ids.insert(id)) {
            return Err(Error::Input(
                "order 包含空或重复页面 ID；请给每页一个不同的 ID".into(),
            ));
        }
        merge("order", &base_order, value, &mut order, &mut conflicts)?;
        for page in &base.pages {
            if !value.contains(&page.id)
                && current
                    .deck
                    .pages
                    .iter()
                    .find(|p| p.id == page.id)
                    .is_some_and(|p| p.author() != page.author())
            {
                conflicts.push(Conflict {
                    unit: "order".into(),
                    current: json!(current_order),
                });
                break;
            }
        }
    }
    let mut pages: HashMap<String, Page> = current
        .deck
        .pages
        .iter()
        .cloned()
        .map(|p| (p.id.clone(), p))
        .collect();
    let mut submitted_ids = HashSet::new();
    for change in patch.pages.unwrap_or_default() {
        if change.id.is_empty() || !submitted_ids.insert(change.id.clone()) {
            return Err(Error::Input(
                "pages 包含空或重复页面 ID；请给每页一个不同的 ID".into(),
            ));
        }
        let before = base.pages.iter().find(|p| p.id == change.id);
        if before.is_none() && (patch.order.is_none() || !submitted_order.contains(&change.id)) {
            return Err(Error::Input(
                "新增页面时必须同时提交包含该页的 order".into(),
            ));
        }
        let mut submitted = before.cloned().unwrap_or_else(|| Page {
            id: change.id.clone(),
            ..Page::default()
        });
        change.apply(&mut submitted);
        submitted.content.normalize_ids()?;
        if let Some(now) = pages.get_mut(&change.id) {
            let b = before.map(Page::author);
            let mut c = Some(now.author());
            merge(
                &format!("pages/{}", change.id),
                &b,
                &Some(submitted.author()),
                &mut c,
                &mut conflicts,
            )?;
            if let Some(author) = c {
                author.apply(now);
            }
        } else if before.is_none() {
            pages.insert(change.id, submitted);
        } else if before.is_some_and(|p| p.author() != submitted.author()) {
            conflicts.push(Conflict {
                unit: format!("pages/{}", change.id),
                current: Value::Null,
            });
        }
    }
    for id in submitted_order {
        if !base_order.contains(id) && !submitted_ids.contains(id) {
            return Err(Error::Input(format!(
                "order 的新页面 {id} 缺少 pages 内容；请同时提交"
            )));
        }
    }
    if patch.order.is_some()
        && base_order
            .iter()
            .any(|id| !submitted_order.contains(id) && !submitted_ids.contains(id))
    {
        return Err(Error::Input(
            "删除页面时必须同时在 pages 中提交该页和删除后的 order".into(),
        ));
    }
    if !conflicts.is_empty() {
        return Err(Error::Conflict(serde_json::to_string(&conflicts)?));
    }
    deck.pages = order
        .iter()
        .map(|id| {
            pages.remove(id).ok_or_else(|| {
                Error::Input(format!("order 中的页面 {id} 没有内容；请同时提交 pages"))
            })
        })
        .collect::<Result<_>>()?;
    let result_version = if deck == current.deck {
        current.version
    } else {
        store::append(&tx, &deck, "保存作品")?
    };
    tx.commit()?;
    Ok(Snapshot {
        version: result_version,
        deck,
    })
}

pub fn restore(project: &Path, version: i64) -> Result<Snapshot> {
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    let deck = store::load(&tx, version)?;
    let version = store::append(&tx, &deck, &format!("恢复自版本 {version}"))?;
    tx.commit()?;
    Ok(Snapshot { version, deck })
}

pub fn material_add(project: &Path, source: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let name = source
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| Error::Input("材料需要有效文件名".into()))?;
    let data = std::fs::read(source)?;
    let extension = source
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("bin")
        .to_lowercase();
    let file = store.add_file(&data, &extension)?;
    // Parse the immutable copy, not a source the author may still be editing.
    let extraction = crate::tools::read_source(&store.file(&file)?)?;
    let text_file = store.add_file(extraction.text.as_bytes(), "txt")?;
    let tx = store.transaction()?;
    let current = store::current(&tx)?;
    let mut deck = current.deck;
    let existing = deck.materials.iter().position(|m| m.file == file);
    let mut material = if let Some(index) = existing {
        deck.materials[index].clone()
    } else {
        let mut number = 1;
        while deck.materials.iter().any(|m| m.id == format!("m{number}")) {
            number += 1;
        }
        crate::model::Material {
            id: format!("m{number}"),
            name: name.into(),
            file,
            text_file: String::new(),
            status: String::new(),
        }
    };
    if extraction.status == "needs_tool" && material.status == "read" {
        return Err(Error::NeedsTool(format!(
            "材料 {} 本次未能重新解析：{}；已保留已有成功解析结果，可继续使用 material text；如需重新解析，请安装对应工具后重试 material add",
            material.id, extraction.detail
        )));
    }
    material.text_file = text_file;
    material.status = if extraction.status == "needs_tool" {
        "needs_tool"
    } else {
        "read"
    }
    .into();
    let changed = if let Some(index) = existing {
        let changed = deck.materials[index] != material;
        deck.materials[index] = material.clone();
        changed
    } else {
        deck.materials.push(material.clone());
        true
    };
    let version = if changed {
        store::append(&tx, &deck, "添加材料")?
    } else {
        current.version
    };
    tx.commit()?;
    if extraction.status == "needs_tool" {
        return Err(Error::NeedsTool(format!(
            "原件已保存为 {}，解析未完成：{}；请安装对应工具后重试 material add",
            material.id, extraction.detail
        )));
    }
    Ok(json!({ "version": version, "material": material, "extraction": extraction }))
}

pub fn material_text(project: &Path, id: &str) -> Result<Value> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
    let material = snapshot
        .deck
        .materials
        .iter()
        .find(|m| m.id == id)
        .ok_or_else(|| Error::Input(format!("材料 {id} 不存在；请用 deck show 查看材料")))?;
    let original = if material.file.is_empty() {
        None
    } else {
        match store.file(&material.file) {
            Ok(path) => Some(path),
            Err(Error::Missing(_)) => None,
            Err(error) => return Err(error),
        }
    };
    if material.status == "needs_tool" {
        return Err(Error::NeedsTool(format!(
            "材料尚未完成解析；原件：{}；请安装对应工具，再次运行 material add",
            original
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "不可用".into())
        )));
    }
    Ok(
        json!({ "id": id, "status": material.status, "path": store.file(&material.text_file)?, "original_path": original }),
    )
}

pub fn export_md(project: &Path) -> Result<String> {
    Ok(export_markdown(project)?.0)
}

pub fn export_markdown(project: &Path) -> Result<(String, Value)> {
    let deck = Store::open(project)?.current()?.deck;
    Ok((crate::export::markdown(&deck), artifact_status(&deck)?))
}

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
    let store = Store::open(project)?;
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
    let (data, ext) = if ext.eq_ignore_ascii_case("svg") {
        let output = std::process::Command::new("rsvg-convert")
            .arg("--format=png")
            .arg(input.canonicalize()?)
            .output()
            .map_err(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    Error::NeedsTool(
                        "SVG 素材需要 rsvg-convert；请安装 librsvg 后重新添加，或先转成 PNG/JPEG"
                            .into(),
                    )
                } else {
                    Error::Tool(format!("无法运行 rsvg-convert：{error}"))
                }
            })?;
        if !output.status.success() || !output.stdout.starts_with(b"\x89PNG\r\n\x1a\n") {
            return Err(Error::Tool(format!(
                "SVG 素材转 PNG 失败；请检查 SVG 后重新添加：{}",
                String::from_utf8_lossy(&output.stderr).trim()
            )));
        }
        (output.stdout, "png")
    } else {
        (std::fs::read(input)?, ext)
    };
    // Share the connection borrow so content can be persisted after the page recheck.
    let tx = rusqlite::Transaction::new_unchecked(
        &store.connection,
        rusqlite::TransactionBehavior::Immediate,
    )?;
    let mut snapshot = store::current(&tx)?;
    for page in &pages {
        if !snapshot.deck.pages.iter().any(|p| &p.id == page) {
            return Err(Error::Input(format!(
                "页面 {page} 不存在；请用 deck show 查看页面"
            )));
        }
    }
    let file = store.add_file(&data, ext)?;
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
    if snapshot.deck != store::current(&tx)?.deck {
        snapshot.version = store::append(&tx, &snapshot.deck, "选择素材")?;
    }
    tx.commit()?;
    Ok(json!({"version": snapshot.version, "asset": asset}))
}

pub fn basis(kind: &str, deck: &Deck, page: &Page) -> Result<String> {
    calculate_basis(kind, deck, page, false)
}

fn calculate_basis(kind: &str, deck: &Deck, page: &Page, legacy: bool) -> Result<String> {
    use sha2::{Digest, Sha256};
    let mut style = deck.style.clone();
    style
        .assets
        .retain(|asset| asset.is_effective_for(&page.id));
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

fn current_basis_for(kind: &str, saved: &str, deck: &Deck, page: &Page) -> Result<String> {
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

fn image_is_stale(deck: &Deck, page: &Page) -> Result<bool> {
    match &page.image {
        Some(image) => Ok(image.basis != basis("image", deck, page)?),
        None => Ok(false),
    }
}

fn run_record(
    connection: &rusqlite::Connection,
    id: i64,
) -> Result<(String, String, Option<i64>, i64)> {
    use rusqlite::OptionalExtension;
    connection
        .query_row(
            "SELECT kind,status,max_calls,calls_used FROM runs WHERE id=?",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )
        .optional()?
        .ok_or_else(|| Error::Input(format!("run {id} 不存在；请用 deck run show 查看")))
}

fn run_page(
    connection: &rusqlite::Connection,
    id: i64,
    page: &str,
) -> Result<(String, String, Option<String>)> {
    use rusqlite::{OptionalExtension, params};
    connection
        .query_row(
            "SELECT basis,status,result_file FROM run_pages WHERE run_id=? AND page_id=?",
            params![id, page],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        )
        .optional()?
        .ok_or_else(|| Error::Input(format!("此 run 不包含页面 {page}；请用 deck run show 查看")))
}

pub fn run_start(
    project: &Path,
    kind: &str,
    ids: &[String],
    max_calls: Option<i64>,
) -> Result<Value> {
    use rusqlite::{OptionalExtension, params};
    if !["image", "svg", "native"].contains(&kind)
        || ids.is_empty()
        || ids.iter().collect::<HashSet<_>>().len() != ids.len()
    {
        return Err(Error::Input(
            "请选择 image、svg 或 native，并指定不重复的页面".into(),
        ));
    }
    if max_calls.is_some_and(|n| n < 1) || (kind != "image" && max_calls.is_some()) {
        return Err(Error::Input(
            "生图调用上限必须为正整数；SVG 和 native 不设调用上限".into(),
        ));
    }
    let mut store = Store::open(project)?;
    let snapshot = store.current()?;
    for id in ids {
        if !snapshot.deck.pages.iter().any(|p| &p.id == id) {
            return Err(Error::Input(format!("页面 {id} 不存在")));
        }
    }
    let root = store.root.clone();
    let tx = store.transaction()?;
    let open: Option<i64> = tx
        .query_row(
            "SELECT id FROM runs WHERE kind=? AND status='open'",
            [kind],
            |r| r.get(0),
        )
        .optional()?;
    if let Some(id) = open {
        return Err(Error::Input(format!(
            "同类 run {id} 尚未结束；继续交回或先取消"
        )));
    }
    let deck = store::current(&tx)?.deck;
    tx.execute(
        "INSERT INTO runs(kind,status,max_calls) VALUES (?,'open',?)",
        params![
            kind,
            if kind == "image" {
                Some(max_calls.unwrap_or(ids.len() as i64 * 2))
            } else {
                None
            }
        ],
    )?;
    let id = tx.last_insert_rowid();
    for page_id in ids {
        let page = deck
            .pages
            .iter()
            .find(|p| &p.id == page_id)
            .ok_or_else(|| Error::Input(format!("页面 {page_id} 已删除；请重新开始")))?;
        tx.execute(
            "INSERT INTO run_pages(run_id,page_id,basis,status) VALUES (?,?,?,'pending')",
            params![id, page_id, basis(kind, &deck, page)?],
        )?;
    }
    tx.commit()?;
    // Page IDs are data, so work paths use an ordinal rather than the author's ID.
    for (index, page_id) in ids.iter().enumerate() {
        let page = deck
            .pages
            .iter()
            .find(|p| &p.id == page_id)
            .ok_or_else(|| Error::Input("页面不存在".into()))?;
        if let Err(error) = crate::prompts::write(
            &store,
            &deck,
            page,
            kind,
            &root
                .join("work")
                .join(id.to_string())
                .join((index + 1).to_string()),
        ) {
            store
                .connection
                .execute("UPDATE runs SET status='cancelled' WHERE id=?", [id])?;
            return Err(error);
        }
    }
    run_show(project, Some(id))
}

pub fn run_call(project: &Path, id: i64, page: &str, retry: bool) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    let (kind, status, max, used) = run_record(&tx, id)?;
    let (_, state, _) = run_page(&tx, id, page)?;
    if kind != "image" || status != "open" {
        return Err(Error::Input("此 run 不能调用生图；请查看状态".into()));
    }
    if max.is_some_and(|max| used >= max) {
        return Err(Error::Input("已达生图调用上限；请停止调用".into()));
    }
    if state == "started" && !retry {
        return Err(Error::Input(
            "上次调用结果未知；请先确认结果，决定重试时显式加 --retry".into(),
        ));
    }
    tx.execute("UPDATE runs SET calls_used=calls_used+1 WHERE id=?", [id])?;
    tx.execute(
        "UPDATE run_pages SET status='started' WHERE run_id=? AND page_id=?",
        params![id, page],
    )?;
    tx.commit()?;
    run_show(project, Some(id))
}

pub fn run_cancel(project: &Path, id: i64) -> Result<Value> {
    let store = Store::open(project)?;
    run_record(&store.connection, id)?;
    store.connection.execute(
        "UPDATE runs SET status='cancelled' WHERE id=? AND status='open'",
        [id],
    )?;
    let deck = store.current()?.deck;
    Ok(json!({"runs": runs(&store.connection, &deck, Some(id))?}))
}

pub fn run_show(project: &Path, id: Option<i64>) -> Result<Value> {
    let store = Store::open(project)?;
    let deck = store.current()?.deck;
    let mut runs = runs(&store.connection, &deck, id)?;
    // Local work paths are a CLI convenience, not part of the browser API.
    for run in &mut runs {
        let Some(id) = run["id"].as_i64() else {
            continue;
        };
        if let Some(pages) = run["pages"].as_array_mut() {
            for (index, page) in pages.iter_mut().enumerate() {
                let findings = page["result_file"]
                    .as_str()
                    .map(|file| {
                        store
                            .root
                            .join("work")
                            .join(id.to_string())
                            .join(format!("readback-{file}.json"))
                    })
                    .filter(|p| p.is_file());
                page["findings_path"] = json!(findings);
                page["work"] = json!(
                    store
                        .root
                        .join("work")
                        .join(id.to_string())
                        .join((index + 1).to_string())
                );
            }
        }
    }
    Ok(json!({"runs": runs}))
}

fn file_url(file: &str) -> String {
    format!("/api/files/{}", file.split('.').next().unwrap_or(""))
}

fn runs(connection: &rusqlite::Connection, deck: &Deck, id: Option<i64>) -> Result<Vec<Value>> {
    if let Some(id) = id {
        run_record(connection, id)?;
    }
    let mut query=connection.prepare("SELECT id,kind,status,max_calls,calls_used FROM runs WHERE (?1 IS NULL OR id=?1) ORDER BY id DESC")?;
    let rows = query
        .query_map([id], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, Option<i64>>(3)?,
                r.get::<_, i64>(4)?,
            ))
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    let current_pages: HashMap<_, _> = deck
        .pages
        .iter()
        .map(|page| (page.id.as_str(), page))
        .collect();
    // Reuse each page/kind basis only during this read; later polls read a fresh deck.
    let mut current_bases = HashMap::new();
    let mut runs = Vec::new();
    for (id, kind, status, max, used) in rows {
        let mut query = connection.prepare(
            "SELECT page_id,basis,status,result_file,preview_file FROM run_pages WHERE run_id=? ORDER BY rowid",
        )?;
        let rows = query
            .query_map([id], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, Option<String>>(3)?,
                    r.get::<_, Option<String>>(4)?,
                ))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        let mut pages = Vec::new();
        for (page, old, state, result, preview) in rows {
            let current_page = current_pages.get(page.as_str());
            let mut current_basis = None;
            let changed = match current_page {
                Some(p) => {
                    let algorithm = if kind == "image" {
                        "image"
                    } else if old.starts_with("svg-v2:") {
                        "svg-v2"
                    } else {
                        "svg-legacy"
                    };
                    let key = (algorithm, p.id.as_str());
                    let current = match current_bases.entry(key) {
                        std::collections::hash_map::Entry::Occupied(entry) => entry.into_mut(),
                        std::collections::hash_map::Entry::Vacant(entry) => {
                            entry.insert(current_basis_for(&kind, &old, deck, p)?)
                        }
                    };
                    current_basis = Some(current.clone());
                    // Derive image staleness without changing stored SVG hash inputs.
                    *current != old
                }
                None => true,
            };
            let reason = if state == "unadopted" {
                if status == "cancelled" {
                    "run 已取消，结果仅保存"
                } else if changed {
                    "依据已变，结果仅保存"
                } else {
                    "结果仅保存，请比较后手动采用"
                }
            } else if state == "started" {
                "结果未知"
            } else {
                ""
            };
            let current_image = current_page
                .and_then(|p| p.image.as_ref())
                .map(|image| file_url(&image.file));
            let result_url = result.as_deref().map(file_url);
            pages.push(json!({"page_id":page,"status":state,"reason":reason,"basis_changed":changed,"basis_incomplete":kind == "svg" && !old.starts_with("svg-v2:"),"current_basis":current_basis,"result_file":result,"result_url":result_url,"result_preview":preview,"current_image_url":current_image}));
        }
        runs.push(json!({"id":id,"kind":kind,"status":status,"max_calls":max,"calls_used":used,"pages":pages}));
    }
    Ok(runs)
}

fn page_job(store: &Store, deck: &Deck, page: &Page, svg: &Path) -> Result<Value> {
    let mut assets = serde_json::Map::new();
    for asset in &deck.style.assets {
        assets.insert(
            asset.id.clone(),
            json!(store.file(&asset.file)?.canonicalize()?),
        );
    }
    Ok(
        json!({"pages":[{"id":page.id,"content":page.content,"notes":page.notes,"svg":svg.canonicalize()?}],"canvas":deck.style.canvas,"fonts":deck.style.fonts,"assets":assets}),
    )
}

#[derive(serde::Serialize, serde::Deserialize)]
struct NativeAsset {
    id: String,
    file: String,
    sha256: String,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct NativePack {
    plan: Value,
    assets: Vec<NativeAsset>,
    render_png: String,
    note: String,
}

fn native_plan_path(store: &Store, pack: &NativePack, path: &Path) -> Result<()> {
    let mut plan = pack.plan.clone();
    for op in plan["ops"].as_array_mut().into_iter().flatten() {
        if op["op"] == "image" {
            let file = op["file"]
                .as_str()
                .ok_or_else(|| Error::Input("image 缺少素材文件".into()))?;
            op["file"] = json!(store.file(file)?.canonicalize()?);
        }
    }
    std::fs::write(path, serde_json::to_vec(&plan)?)?;
    Ok(())
}

fn native_result(
    store: &Store,
    id: i64,
    page: &Page,
    source: &Path,
    data: &[u8],
    temporary: &Path,
) -> Result<(Vec<u8>, String, Value, Value)> {
    use sha2::{Digest, Sha256};
    let mut plan: Value = serde_json::from_slice(data)?;
    let path = temporary.join("plan.json");
    let mut input = serde_json::to_value(page)?;
    input["plan"] = json!(path);
    let mut assets = Vec::new();
    for op in plan["ops"].as_array_mut().into_iter().flatten() {
        if op["op"] == "image" {
            let name = op["file"]
                .as_str()
                .ok_or_else(|| Error::Input("image 缺少素材文件".into()))?;
            let asset = source.parent().unwrap_or(Path::new(".")).join(name);
            let bytes = std::fs::read(&asset)?;
            let file = store.add_file(
                &bytes,
                asset.extension().and_then(|s| s.to_str()).unwrap_or("bin"),
            )?;
            assets.push(NativeAsset {
                id: name.into(),
                file: file.clone(),
                sha256: format!("{:x}", Sha256::digest(&bytes)),
            });
            op["file"] = json!(file);
        }
    }
    let mut pack = NativePack {
        plan,
        assets,
        render_png: String::new(),
        note: String::new(),
    };
    native_plan_path(store, &pack, &path)?;
    let image = page
        .image
        .as_ref()
        .ok_or_else(|| Error::Input("本页没有已采用的原图；请先交回并采用原图".into()))?;
    input["source_image"] = json!(store.file(&image.file)?.canonicalize()?);
    let work = store.root.canonicalize()?.join("work").join(id.to_string());
    std::fs::create_dir_all(&work)?;
    // Each check keeps its own comparison, including concurrent or repeated results.
    let directory = tempfile::Builder::new()
        .prefix("native-")
        .tempdir_in(work)?
        .keep();
    let output = crate::tools::invoke(
        "render",
        &json!({
            "page": input,
            "output": directory,
        }),
    )?;
    let preview = output["render_png"]
        .as_str()
        .ok_or_else(|| Error::Tool("render 缺少预览路径".into()))?;
    pack.render_png = store.add_file(&std::fs::read(preview)?, "png")?;
    Ok((
        serde_json::to_vec(&pack)?,
        pack.render_png,
        output["findings"].clone(),
        output["side_by_side"].clone(),
    ))
}

pub fn run_result(project: &Path, id: i64, page_id: &str, source: &Path) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let (kind, _, _, _) = run_record(&store.connection, id)?;
    let (old, _, _) = run_page(&store.connection, id, page_id)?;
    let snapshot = store.current()?;
    let checked_version = snapshot.version;
    let mut data = std::fs::read(source)?;
    if kind == "svg" {
        use sha2::{Digest, Sha256};
        let identity = format!("{:x}.svg", Sha256::digest(&data));
        let (_, state, previous) = run_page(&store.connection, id, page_id)?;
        if state == "done" && previous.as_deref() == Some(identity.as_str()) {
            let path = store
                .root
                .join("work")
                .join(id.to_string())
                .join(format!("readback-{identity}.json"));
            let findings: Value = match std::fs::read(&path) {
                Ok(bytes) => serde_json::from_slice(&bytes)?,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => Value::Null,
                Err(error) => return Err(error.into()),
            };
            return Ok(
                json!({"file":identity,"adopted":false,"reused":true,"findings":findings,"run":run_show(project,Some(id))?}),
            );
        }
    }
    let temporary = tempfile::tempdir()?;
    let mut preview = None;
    let mut findings = Value::Null;
    let mut side_by_side = Value::Null;
    let extension = if kind == "native" {
        let page = snapshot
            .deck
            .pages
            .iter()
            .find(|p| p.id == page_id)
            .ok_or_else(|| Error::Input("页面已删除；请保留原文件".into()))?;
        let (packed, png, checked, comparison) =
            native_result(&store, id, page, source, &data, temporary.path())?;
        data = packed;
        preview = Some(png);
        findings = checked;
        side_by_side = comparison;
        "native.json"
    } else if kind == "svg" {
        // Compile the exact bytes later saved, even if the Host rewrites its source.
        let path = temporary.path().join("page.svg");
        std::fs::write(&path, &data)?;
        let page = snapshot
            .deck
            .pages
            .iter()
            .find(|p| p.id == page_id)
            .ok_or_else(|| Error::Input("页面已删除；SVG 无法回读，请保留原文件".into()))?;
        let mut job = page_job(&store, &snapshot.deck, page, &path)?;
        job["output"] = json!(temporary.path().join("check"));
        let output = crate::tools::invoke("check-page", &job)?;
        let path = output["preview"]
            .as_str()
            .ok_or_else(|| Error::Tool("check-page 缺少预览路径".into()))?;
        preview = Some(store.add_file(&std::fs::read(path)?, "png")?);
        findings = output["findings"].clone();
        "svg"
    } else {
        // Decode the exact saved bytes, not a mutable Host file.
        let bitmap = temporary.path().join("image");
        std::fs::write(&bitmap, &data)?;
        let info = crate::tools::invoke("image-info", &json!({"path": bitmap}))?;
        match info["format"].as_str() {
            Some("PNG") => "png",
            Some("JPEG") => "jpg",
            _ => return Err(Error::Tool("image-info 未返回 PNG 或 JPEG 格式".into())),
        }
    };
    let file = store.add_file(&data, extension)?;
    if matches!(kind.as_str(), "svg" | "native") {
        let directory = store.root.join("work").join(id.to_string());
        std::fs::create_dir_all(&directory)?;
        std::fs::write(
            directory.join(format!("readback-{file}.json")),
            serde_json::to_vec_pretty(&findings)?,
        )?;
    }
    let tx = store.transaction()?;
    let (_, status, _, _) = run_record(&tx, id)?;
    let mut snapshot = store::current(&tx)?;
    let eligible = match snapshot.deck.pages.iter().find(|p| p.id == page_id) {
        Some(p) => {
            (kind != "svg" || old.starts_with("svg-v2:")) && basis(&kind, &snapshot.deck, p)? == old
        }
        None => false,
    };
    let (_, current_state, previous) = run_page(&tx, id, page_id)?;
    // Only the first result may write the page automatically. Later files can
    // arrive out of order while another page keeps this run open.
    let adopted = kind != "native" && status == "open" && eligible && previous.is_none();
    if adopted {
        let page = snapshot
            .deck
            .pages
            .iter_mut()
            .find(|p| p.id == page_id)
            .ok_or_else(|| Error::Input("页面不存在".into()))?;
        let artifact = Some(crate::model::Artifact {
            file: file.clone(),
            basis: old,
        });
        if kind == "image" {
            page.image = artifact;
        } else {
            page.svg = artifact;
            page.preview = preview.clone();
        }
        if snapshot.deck != store::current(&tx)?.deck {
            store::append(&tx, &snapshot.deck, "采用生成结果")?;
        }
    }
    // An identical result can be returned safely after the final page closed the run.
    let state = if adopted {
        "done".to_string()
    } else if previous.as_ref() == Some(&file) && current_state != "started" {
        current_state
    } else {
        "unadopted".to_string()
    };
    // Persist the check-page PNG for candidates that are not written onto the page.
    // Later reads return this name and do not render again.
    tx.execute(
        "UPDATE run_pages SET status=?,result_file=?,preview_file=? WHERE run_id=? AND page_id=?",
        params![state, file, preview, id, page_id],
    )?;
    tx.execute("UPDATE runs SET status='done' WHERE id=? AND status='open' AND NOT EXISTS (SELECT 1 FROM run_pages WHERE run_id=? AND status!='done')",params![id,id])?;
    tx.commit()?;
    Ok(
        json!({"file":file,"adopted":adopted,"checked_version":checked_version,"findings":findings,"side_by_side":side_by_side,"run":run_show(project,Some(id))?}),
    )
}

pub fn run_adopt(project: &Path, id: i64, page_id: &str) -> Result<Value> {
    run_adopt_candidate(project, id, page_id, None)
}

pub fn run_adopt_candidate(
    project: &Path,
    id: i64,
    page_id: &str,
    expected_file: Option<&str>,
) -> Result<Value> {
    run_adopt_with_options(project, id, page_id, expected_file, None)
}

pub fn run_adopt_with_note(
    project: &Path,
    id: i64,
    page_id: &str,
    note: Option<&str>,
) -> Result<Value> {
    run_adopt_with_options(project, id, page_id, None, note)
}

fn run_adopt_with_options(
    project: &Path,
    id: i64,
    page_id: &str,
    expected_file: Option<&str>,
    note: Option<&str>,
) -> Result<Value> {
    use rusqlite::params;
    let store = Store::open(project)?;
    let (kind, _, _, _) = run_record(&store.connection, id)?;
    let note = if kind == "native" {
        Some(
            note.map(str::trim)
                .filter(|text| !text.is_empty())
                .ok_or_else(|| {
                    Error::Input("采用 native 结果必须用 --note 填写非空的本页对照结论".into())
                })?,
        )
    } else {
        None
    };
    let (old, _, file) = run_page(&store.connection, id, page_id)?;
    let file = file.ok_or_else(|| Error::Input("此页尚无结果；请先交回文件".into()))?;
    if expected_file.is_some_and(|expected| expected != file) {
        return Err(Error::Conflict(
            "候选已更新；请读取当前候选后重新采用".into(),
        ));
    }
    store.file(&file)?;
    let mut preview = None;
    if kind == "svg" {
        let snapshot = store.current()?;
        let page = snapshot
            .deck
            .pages
            .iter()
            .find(|p| p.id == page_id)
            .ok_or_else(|| Error::Input("页面已删除".into()))?;
        let temp = tempfile::tempdir()?;
        let mut job = page_job(&store, &snapshot.deck, page, &store.file(&file)?)?;
        job["output"] = json!(temp.path().join("check"));
        let output = crate::tools::invoke("check-page", &job)?;
        preview = Some(
            store.add_file(
                &std::fs::read(
                    output["preview"]
                        .as_str()
                        .ok_or_else(|| Error::Tool("缺少预览路径".into()))?,
                )?,
                "png",
            )?,
        );
    }
    let adopted_file = if let Some(note) = note {
        let mut pack: NativePack = serde_json::from_slice(&std::fs::read(store.file(&file)?)?)?;
        pack.note = note.into();
        store.file(&pack.render_png)?;
        preview = Some(pack.render_png.clone());
        store.add_file(&serde_json::to_vec(&pack)?, "native.json")?
    } else {
        file.clone()
    };
    let tx = rusqlite::Transaction::new_unchecked(
        &store.connection,
        rusqlite::TransactionBehavior::Immediate,
    )?;
    if run_page(&tx, id, page_id)?.2.as_deref() != Some(file.as_str()) {
        return Err(Error::Conflict(
            "候选已更新；请读取当前候选后重新采用".into(),
        ));
    }
    let mut snapshot = store::current(&tx)?;
    let page = snapshot
        .deck
        .pages
        .iter_mut()
        .find(|p| p.id == page_id)
        .ok_or_else(|| Error::Input("页面已删除；不能采用".into()))?;
    let artifact = Some(crate::model::Artifact {
        file: adopted_file.clone(),
        basis: old,
    });
    if kind == "image" {
        page.image = artifact;
    } else if kind == "native" {
        page.native = artifact;
        page.preview = preview.clone();
    } else {
        page.svg = artifact;
        page.preview = preview.clone();
    }
    if snapshot.deck != store::current(&tx)?.deck {
        store::append(&tx, &snapshot.deck, "手动采用生成结果")?;
    }
    if kind == "native" {
        tx.execute(
            "UPDATE run_pages SET result_file=? WHERE run_id=? AND page_id=?",
            params![adopted_file, id, page_id],
        )?;
    }
    tx.execute(
        "UPDATE run_pages SET status='done' WHERE run_id=? AND page_id=?",
        params![id, page_id],
    )?;
    tx.execute("UPDATE runs SET status='done' WHERE id=? AND status='open' AND NOT EXISTS (SELECT 1 FROM run_pages WHERE run_id=? AND status!='done')",params![id,id])?;
    tx.commit()?;
    run_show(project, Some(id))
}

fn build_digest(deck: &Deck) -> Result<String> {
    use sha2::{Digest, Sha256};
    let native = deck.pages.iter().any(|p| p.native.is_some());
    let pages: Vec<_> = deck
        .pages
        .iter()
        .map(|p| {
            if native {
                Ok(json!([p.id, p.native, basis("native", deck, p)?, p.notes]))
            } else {
                Ok(json!([p.id, p.svg.as_ref().map(|s| &s.file), p.notes]))
            }
        })
        .collect::<Result<_>>()?;
    let assets: std::collections::BTreeMap<_, _> = deck
        .style
        .assets
        .iter()
        .map(|asset| (&asset.id, &asset.file))
        .collect();
    let inputs =
        json!({"pages":pages,"canvas":deck.style.canvas,"fonts":deck.style.fonts,"assets":assets});
    Ok(format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&inputs)?)
    ))
}

pub fn artifact_status(deck: &Deck) -> Result<Value> {
    artifact_status_for(deck, deck.pages.iter().any(|p| p.native.is_some()))
}

fn stale_image_warnings(stale_images: &Value) -> Value {
    json!(
        stale_images
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|page_id| page_id.as_str())
            .map(|page_id| json!({"level":"warning","code":"stale_image","page_id":page_id}))
            .collect::<Vec<_>>()
    )
}

fn artifact_status_for(deck: &Deck, native: bool) -> Result<Value> {
    let missing: Vec<_> = deck
        .pages
        .iter()
        .filter(|p| {
            if native {
                p.native.is_none()
            } else {
                p.svg.is_none()
            }
        })
        .map(|p| &p.id)
        .collect();
    let mut stale = Vec::new();
    let mut stale_images = Vec::new();
    let mut incomplete_basis_pages = Vec::new();
    for page in &deck.pages {
        let artifact = if native { &page.native } else { &page.svg };
        if artifact
            .as_ref()
            .is_some_and(|svg| !svg.basis.starts_with("svg-v2:"))
        {
            incomplete_basis_pages.push(&page.id);
        }
        let image_stale = image_is_stale(deck, page)?;
        if image_stale {
            stale_images.push(&page.id);
        }
        if let Some(svg) = artifact
            && (svg.basis != current_basis_for("svg", &svg.basis, deck, page)?)
        {
            stale.push(&page.id);
        }
    }
    Ok(
        json!({"missing_pages":missing,"stale_pages":stale,"stale_images":stale_images,"incomplete_basis_pages":incomplete_basis_pages}),
    )
}

pub fn build(project: &Path) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let snapshot = store.current()?;
    let native = snapshot.deck.pages.iter().any(|p| p.native.is_some());
    let status = artifact_status_for(&snapshot.deck, native)?;
    let temporary = tempfile::tempdir()?;
    let mut pages = Vec::new();
    let mut job = Value::Null;
    for (index, page) in snapshot.deck.pages.iter().enumerate() {
        if native {
            if let Some(artifact) = &page.native {
                let pack: NativePack =
                    serde_json::from_slice(&std::fs::read(store.file(&artifact.file)?)?)?;
                let plan = temporary.path().join(format!("{index}.json"));
                native_plan_path(&store, &pack, &plan)?;
                pages.push(
                    json!({"id":page.id,"content":page.content,"notes":page.notes,"plan":plan}),
                );
            }
        } else if let Some(svg) = &page.svg {
            let input = page_job(&store, &snapshot.deck, page, &store.file(&svg.file)?)?;
            pages.push(input["pages"][0].clone());
            job = input;
        }
    }
    if pages.is_empty() {
        let missing = snapshot
            .deck
            .pages
            .iter()
            .map(|page| page.id.as_str())
            .collect::<Vec<_>>()
            .join(",");
        return Err(Error::Input(format!("没有已采用的页面；缺页：{missing}")));
    }
    let output = if native {
        crate::tools::invoke("assemble", &json!({"work":temporary.path(),"pages":pages}))?
    } else {
        job["pages"] = json!(pages);
        job["output"] = json!(temporary.path().join("build"));
        crate::tools::invoke("build", &job)?
    };
    let path = output["pptx"]
        .as_str()
        .ok_or_else(|| Error::Tool("build 缺少 PPTX 路径".into()))?;
    let file = store.add_file(&std::fs::read(path)?, "pptx")?;
    let tx = store.transaction()?;
    tx.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?,?,?,?)",params![snapshot.version,build_digest(&snapshot.deck)?,file,serde_json::to_string(&output["findings"])?,serde_json::to_string(&status["missing_pages"])?])?;
    let id = tx.last_insert_rowid();
    tx.commit()?;
    Ok(
        json!({"id":id,"path":store.file(&file)?,"findings":output["findings"],"missing_pages":status["missing_pages"],"stale_pages":status["stale_pages"],"stale_images":status["stale_images"],"warnings":stale_image_warnings(&status["stale_images"])}),
    )
}

// Selection and its metadata share the caller's read transaction.
fn default_build(connection: &rusqlite::Connection, deck: &Deck) -> Result<Option<Value>> {
    use rusqlite::OptionalExtension;
    let digest = build_digest(deck)?;
    let row = connection.query_row(
        "SELECT id,version_id,input_digest,pptx_file,missing_pages,created_at FROM builds ORDER BY (input_digest=?1) DESC,id DESC LIMIT 1",
        [&digest],
        |r| Ok((r.get::<_,i64>(0)?,r.get::<_,i64>(1)?,r.get::<_,String>(2)?,r.get::<_,String>(3)?,r.get::<_,String>(4)?,r.get::<_,String>(5)?)),
    ).optional()?;
    row.map(|(id,version_id,input,file,missing,created)| {
        let changed = input != digest;
        Ok(json!({"id":id,"version_id":version_id,"file":file,"created_at":created,
            "input_changed":changed,
            "warning":if changed {"当前构建输入没有匹配的成品；下载的是最近可用历史成品，请按需重新构建"} else {""},
            "build_missing_pages":serde_json::from_str::<Value>(&missing)?}))
    }).transpose()
}

pub fn build_detail(project: &Path, id: i64) -> Result<Value> {
    use rusqlite::OptionalExtension;
    let mut store = Store::open(project)?;
    let tx = store.connection.transaction()?;
    let current = store::current(&tx)?;
    let row = tx.query_row(
        "SELECT version_id,input_digest,pptx_file,findings_json,missing_pages,created_at FROM builds WHERE id=?",
        [id], |r| Ok((r.get::<_,i64>(0)?,r.get::<_,String>(1)?,r.get::<_,String>(2)?,r.get::<_,String>(3)?,r.get::<_,String>(4)?,r.get::<_,String>(5)?)),
    ).optional()?.ok_or_else(|| Error::Missing(format!("构建 {id} 不存在")))?;
    let (version_id, digest, file, findings, missing, created_at) = row;
    let findings: Value = serde_json::from_str(&findings)?;
    let source = store::load(&tx, version_id)?;
    let imported = digest == "imported";
    if !imported
        && (!findings.is_object()
            || !findings["findings"].is_array()
            || !matches!(findings["status"].as_str(), Some("pass" | "fail")))
    {
        return Err(Error::Tool(
            "构建回读结果不可读取；请保留原始产物并按需重新构建".into(),
        ));
    }
    let mut pages = Vec::new();
    let mut content_matches = true;
    let native = source.pages.iter().any(|p| p.native.is_some());
    for (index, page) in source.pages.iter().enumerate() {
        if if native {
            page.native.is_none()
        } else {
            page.svg.is_none()
        } {
            continue;
        }
        content_matches &= current
            .deck
            .pages
            .iter()
            .any(|now| now.id == page.id && now.content == page.content);
        pages.push(json!({"page_id":page.id,"title":page.content.title,"source_order":index+1,"pptx_slide":pages.len()+1}));
    }
    let input_changed = digest != build_digest(&current.deck)?;
    Ok(
        json!({"id":id,"version_id":version_id,"created_at":created_at,"pptx_url":file_url(&file),
        "findings":findings,"pages":pages,"build_missing_pages":serde_json::from_str::<Value>(&missing)?,
        "current_version":current.version,"input_changed":input_changed,"readback_available":!imported,
        "readback_matches_current":if imported {Value::Null} else {json!(!input_changed && content_matches)}}),
    )
}

pub fn export_pptx(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let tx = store.connection.transaction()?;
    let deck = store::current(&tx)?.deck;
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
    selected["warnings"] = stale_image_warnings(&status["stale_images"]);
    selected["incomplete_basis_pages"] = status["incomplete_basis_pages"].clone();
    Ok(selected)
}

pub fn doctor(fonts: &[String]) -> Result<Value> {
    crate::tools::invoke("doctor", &json!({"fonts":fonts}))
}

#[cfg(test)]
mod build_selection_tests {
    use super::*;

    #[test]
    fn legacy_basis_survives_format_upgrade_and_does_not_claim_purpose_coverage() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let mut deck = Deck::default();
        deck.pages.push(Page {
            id: "p1".into(),
            ..Page::default()
        });
        let legacy = calculate_basis("svg", &deck, &deck.pages[0], true).unwrap();
        deck.pages[0].svg = Some(crate::model::Artifact {
            file: "historical.svg".into(),
            basis: legacy.clone(),
        });
        let tx = store.transaction().unwrap();
        store::append(&tx, &deck, "Legacy fixture").unwrap();
        tx.commit().unwrap();
        store
            .connection
            .pragma_update(None, "user_version", 4)
            .unwrap();
        drop(store);
        let upgraded = Store::open(temp.path()).unwrap();
        assert_eq!(
            upgraded
                .connection
                .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
                .unwrap(),
            store::FORMAT_VERSION
        );
        assert_eq!(
            upgraded.current().unwrap().deck.pages[0]
                .svg
                .as_ref()
                .unwrap()
                .basis,
            legacy
        );
        let old_v2 = basis("svg", &deck, &deck.pages[0]).unwrap();
        deck.pages[0].purpose = "Changed purpose".into();
        assert_eq!(
            current_basis_for("svg", &legacy, &deck, &deck.pages[0]).unwrap(),
            legacy
        );
        assert_ne!(basis("svg", &deck, &deck.pages[0]).unwrap(), old_v2);
        let status = artifact_status(&deck).unwrap();
        assert_eq!(status["stale_pages"], json!([]));
        assert_eq!(status["incomplete_basis_pages"], json!(["p1"]));
    }

    #[test]
    fn persisted_readback_compares_content_and_preserves_import_and_corruption_identity() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let file = store.add_file(b"synthetic SVG", "svg").unwrap();
        let mut deck = Deck::default();
        deck.pages.push(Page {
            id: "p1".into(),
            ..Page::default()
        });
        deck.pages[0].svg = Some(crate::model::Artifact {
            file,
            basis: basis("svg", &deck, &deck.pages[0]).unwrap(),
        });
        let tx = store.transaction().unwrap();
        let source = store::append(&tx, &deck, "Source").unwrap();
        tx.commit().unwrap();
        let report = json!({"status":"pass","findings":[],"visual_review":"not_evaluated","desktop_editing":"not_evaluated"});
        store.connection.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?, 'synthetic.pptx',?, '[]')",rusqlite::params![source,build_digest(&deck).unwrap(),report.to_string()]).unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["readback_matches_current"], true);
        assert_eq!(detail["pages"][0]["pptx_slide"], 1);
        deck.pages[0].content.title = "Changed text".into();
        let tx = store.transaction().unwrap();
        store::append(&tx, &deck, "Content only").unwrap();
        tx.commit().unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["input_changed"], false);
        assert_eq!(detail["readback_matches_current"], false);
        store
            .connection
            .execute("UPDATE builds SET findings_json='broken' WHERE id=1", [])
            .unwrap();
        assert!(build_detail(temp.path(), 1).is_err());
        assert_eq!(workspace(temp.path()).unwrap()["default_build"]["id"], 1);
        store
            .connection
            .execute(
                "UPDATE builds SET input_digest='imported',findings_json='[]' WHERE id=1",
                [],
            )
            .unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["readback_available"], false);
        assert!(detail["readback_matches_current"].is_null());
        assert!(matches!(
            build_detail(temp.path(), 99),
            Err(Error::Missing(_))
        ));
    }

    #[test]
    fn matching_build_wins_over_later_completion_and_restore_can_select_older_id() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let mut older = Deck::default();
        older.pages.push(Page {
            id: "p1".into(),
            notes: "old".into(),
            ..Page::default()
        });
        let mut current = older.clone();
        current.pages[0].notes = "new".into();
        let old_file = store.add_file(b"old build", "pptx").unwrap();
        let current_file = store.add_file(b"current build", "pptx").unwrap();
        for (deck, file) in [
            (&older, &old_file),
            (&current, &current_file),
            (&older, &old_file),
        ] {
            store.connection.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (1,?,?, '{}','[]')", rusqlite::params![build_digest(deck).unwrap(), file]).unwrap();
        }
        assert_eq!(
            default_build(&store.connection, &current).unwrap().unwrap()["id"],
            2
        );
        assert_eq!(
            default_build(&store.connection, &older).unwrap().unwrap()["id"],
            3
        );
        let tx = store.transaction().unwrap();
        store::append(&tx, &current, "Current inputs").unwrap();
        tx.commit().unwrap();
        let export = export_pptx(temp.path()).unwrap();
        assert_eq!(export["id"], 2);
        assert_eq!(export["input_changed"], false);
        assert_eq!(
            std::fs::read(export["path"].as_str().unwrap()).unwrap(),
            b"current build"
        );
        current.pages[0].notes = "unbuilt".into();
        let fallback = default_build(&store.connection, &current).unwrap().unwrap();
        assert_eq!(fallback["id"], 3);
        assert_eq!(fallback["input_changed"], true);
        std::fs::remove_file(store.file(&current_file).unwrap()).unwrap();
        assert!(matches!(export_pptx(temp.path()), Err(Error::Missing(_))));
    }
}
