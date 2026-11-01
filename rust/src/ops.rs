use crate::error::{Conflict, Error, Result};
use crate::model::{Brief, Deck, Page, Patch, Snapshot};
use crate::store::{self, Store};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::path::Path;

pub fn new(project: &Path, title: String) -> Result<Snapshot> {
    let deck = Deck {
        brief: Brief {
            title,
            ..Brief::default()
        },
        ..Deck::default()
    };
    Store::create(project, &deck)?.current()
}

pub fn get(project: &Path, pages: Option<&[String]>) -> Result<Value> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
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

pub fn show(project: &Path) -> Result<Value> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
    Ok(json!({
        "version": snapshot.version,
        "title": snapshot.deck.brief.title,
        "thesis": snapshot.deck.framing.thesis,
        "materials": snapshot.deck.materials.iter().map(|m| json!({"id": m.id, "name": m.name, "status": m.status})).collect::<Vec<_>>(),
        "pages": snapshot.deck.pages.iter().map(|p| json!({"id": p.id, "title": p.content.title, "purpose": p.purpose, "todo": p.todo})).collect::<Vec<_>>(),
        "artifact_status": artifact_status(&snapshot.deck)?,
        "history": store.history()?
    }))
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
    if material.status == "needs_tool" {
        return Err(Error::NeedsTool(
            "材料尚未完成解析；请安装对应工具，再次运行 material add".into(),
        ));
    }
    Ok(json!({ "id": id, "status": material.status, "path": store.file(&material.text_file)? }))
}

pub fn export_md(project: &Path) -> Result<String> {
    Ok(crate::export::markdown(
        &Store::open(project)?.current()?.deck,
    ))
}

pub fn asset_add(project: &Path, id: &str, source: &Path) -> Result<Value> {
    if id.is_empty() {
        return Err(Error::Input("素材 ID 不能为空".into()));
    }
    let mut store = Store::open(project)?;
    let ext = source.extension().and_then(|v| v.to_str()).unwrap_or("bin");
    let file = store.add_file(&std::fs::read(source)?, ext)?;
    let asset = crate::model::Asset {
        id: id.into(),
        file,
    };
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
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
    use sha2::{Digest, Sha256};
    let value = if kind == "image" {
        json!([page.content, page.layout, page.purpose, deck.style])
    } else {
        json!([
            page.content,
            page.image.as_ref().map(|i| &i.file),
            deck.style
        ])
    };
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(&value)?)))
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
    if !["image", "svg"].contains(&kind)
        || ids.is_empty()
        || ids.iter().collect::<HashSet<_>>().len() != ids.len()
    {
        return Err(Error::Input(
            "请选择 image 或 svg，并指定不重复的页面".into(),
        ));
    }
    if max_calls.is_some_and(|n| n < 1) || (kind == "svg" && max_calls.is_some()) {
        return Err(Error::Input(
            "生图调用上限必须为正整数；SVG 不设调用上限".into(),
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
    run_show(project, Some(id))
}

pub fn run_show(project: &Path, id: Option<i64>) -> Result<Value> {
    let store = Store::open(project)?;
    let deck = store.current()?.deck;
    if let Some(id) = id {
        run_record(&store.connection, id)?;
    }
    let mut query=store.connection.prepare("SELECT id,kind,status,max_calls,calls_used FROM runs WHERE (?1 IS NULL OR id=?1) ORDER BY id DESC")?;
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
    let mut runs = Vec::new();
    for (id, kind, status, max, used) in rows {
        let mut query = store.connection.prepare(
            "SELECT page_id,basis,status,result_file FROM run_pages WHERE run_id=? ORDER BY rowid",
        )?;
        let rows = query
            .query_map([id], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, Option<String>>(3)?,
                ))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        let mut pages = Vec::new();
        for (index, (page, old, state, result)) in rows.into_iter().enumerate() {
            let changed = match deck.pages.iter().find(|p| p.id == page) {
                Some(p) => basis(&kind, &deck, p)? != old,
                None => true,
            };
            let reason = if state == "unadopted" {
                if status == "cancelled" {
                    "run 已取消，结果仅保存"
                } else if changed {
                    "依据已变，结果仅保存"
                } else {
                    "结果未采用"
                }
            } else if state == "started" {
                "结果未知"
            } else {
                ""
            };
            let findings_path = result
                .as_ref()
                .map(|file| {
                    store
                        .root
                        .join("work")
                        .join(id.to_string())
                        .join(format!("readback-{file}.json"))
                })
                .filter(|path| path.is_file());
            pages.push(json!({"page_id":page,"status":state,"reason":reason,"basis_changed":changed,"result_file":result,"findings_path":findings_path,"work":store.root.join("work").join(id.to_string()).join((index+1).to_string())}));
        }
        runs.push(json!({"id":id,"kind":kind,"status":status,"max_calls":max,"calls_used":used,"pages":pages}));
    }
    Ok(json!({"runs":runs}))
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

pub fn run_result(project: &Path, id: i64, page_id: &str, source: &Path) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let (kind, _, _, _) = run_record(&store.connection, id)?;
    let (old, _, previous) = run_page(&store.connection, id, page_id)?;
    let snapshot = store.current()?;
    let data = std::fs::read(source)?;
    let temporary = tempfile::tempdir()?;
    let mut preview = None;
    let mut findings = Value::Null;
    let extension = if kind == "svg" {
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
        crate::tools::invoke("image-info", &json!({"path": bitmap}))?;
        let ext = source.extension().and_then(|e| e.to_str()).unwrap_or("");
        if !["png", "jpg", "jpeg"].contains(&ext.to_lowercase().as_str()) {
            return Err(Error::Input("生图结果必须是 PNG 或 JPEG".into()));
        }
        ext
    };
    let file = store.add_file(&data, extension)?;
    if kind == "svg" {
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
        Some(p) => basis(&kind, &snapshot.deck, p)? == old,
        None => false,
    };
    let adopted = status == "open" && eligible;
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
            page.preview = preview;
        }
        if snapshot.deck != store::current(&tx)?.deck {
            store::append(&tx, &snapshot.deck, "采用生成结果")?;
        }
    }
    // An identical result can be returned safely after the final page closed the run.
    let state = if adopted {
        "done".to_string()
    } else if previous.as_ref() == Some(&file) {
        run_page(&tx, id, page_id)?.1
    } else {
        "unadopted".to_string()
    };
    tx.execute(
        "UPDATE run_pages SET status=?,result_file=? WHERE run_id=? AND page_id=?",
        params![state, file, id, page_id],
    )?;
    tx.execute("UPDATE runs SET status='done' WHERE id=? AND status='open' AND NOT EXISTS (SELECT 1 FROM run_pages WHERE run_id=? AND status!='done')",params![id,id])?;
    tx.commit()?;
    Ok(json!({"file":file,"adopted":adopted,"findings":findings,"run":run_show(project,Some(id))?}))
}

pub fn run_adopt(project: &Path, id: i64, page_id: &str) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let (kind, _, _, _) = run_record(&store.connection, id)?;
    let (old, _, file) = run_page(&store.connection, id, page_id)?;
    let file = file.ok_or_else(|| Error::Input("此页尚无结果；请先交回文件".into()))?;
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
    let tx = store.transaction()?;
    let mut snapshot = store::current(&tx)?;
    let page = snapshot
        .deck
        .pages
        .iter_mut()
        .find(|p| p.id == page_id)
        .ok_or_else(|| Error::Input("页面已删除；不能采用".into()))?;
    let artifact = Some(crate::model::Artifact { file, basis: old });
    if kind == "image" {
        page.image = artifact;
    } else {
        page.svg = artifact;
        page.preview = preview;
    }
    if snapshot.deck != store::current(&tx)?.deck {
        store::append(&tx, &snapshot.deck, "手动采用生成结果")?;
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
    let inputs: Vec<_> = deck
        .pages
        .iter()
        .map(|p| json!([p.id, p.svg.as_ref().map(|s| &s.file), p.notes]))
        .collect();
    Ok(format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&inputs)?)
    ))
}

pub fn artifact_status(deck: &Deck) -> Result<Value> {
    let missing: Vec<_> = deck
        .pages
        .iter()
        .filter(|p| p.svg.is_none())
        .map(|p| &p.id)
        .collect();
    let mut stale = Vec::new();
    let mut stale_images = Vec::new();
    for page in &deck.pages {
        if let Some(image) = &page.image
            && image.basis != basis("image", deck, page)?
        {
            stale_images.push(&page.id);
        }
        if let Some(svg) = &page.svg
            && svg.basis != basis("svg", deck, page)?
        {
            stale.push(&page.id);
        }
    }
    Ok(json!({"missing_pages":missing,"stale_pages":stale,"stale_images":stale_images}))
}

pub fn build(project: &Path) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let snapshot = store.current()?;
    let mut pages = Vec::new();
    let mut job = Value::Null;
    for page in &snapshot.deck.pages {
        if let Some(svg) = &page.svg {
            let input = page_job(&store, &snapshot.deck, page, &store.file(&svg.file)?)?;
            pages.push(input["pages"][0].clone());
            job = input;
        }
    }
    if pages.is_empty() {
        return Err(Error::Input(
            "没有可构建的 SVG；请先完成至少一页 SVG".into(),
        ));
    }
    let temporary = tempfile::tempdir()?;
    job["pages"] = json!(pages);
    job["output"] = json!(temporary.path().join("build"));
    let output = crate::tools::invoke("build", &job)?;
    let path = output["pptx"]
        .as_str()
        .ok_or_else(|| Error::Tool("build 缺少 PPTX 路径".into()))?;
    let file = store.add_file(&std::fs::read(path)?, "pptx")?;
    let status = artifact_status(&snapshot.deck)?;
    let tx = store.transaction()?;
    tx.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?,?,?,?)",params![snapshot.version,build_digest(&snapshot.deck)?,file,serde_json::to_string(&output["findings"])?,serde_json::to_string(&status["missing_pages"])?])?;
    let id = tx.last_insert_rowid();
    tx.commit()?;
    Ok(
        json!({"id":id,"path":store.file(&file)?,"findings":output["findings"],"missing_pages":status["missing_pages"],"stale_pages":status["stale_pages"]}),
    )
}

pub fn export_pptx(project: &Path) -> Result<Value> {
    use rusqlite::OptionalExtension;
    let store = Store::open(project)?;
    let deck = store.current()?.deck;
    let build: Option<(i64, String, String, String)> = store
        .connection
        .query_row(
            "SELECT id,input_digest,pptx_file,missing_pages FROM builds ORDER BY id DESC LIMIT 1",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )
        .optional()?;
    let (id, digest, file, missing) =
        build.ok_or_else(|| Error::Input("尚无构建；请先运行 deck build".into()))?;
    let status = artifact_status(&deck)?;
    let changed = digest != build_digest(&deck)?;
    Ok(
        json!({"id":id,"path":store.file(&file)?,"input_changed":changed,"warning":if changed {"当前 SVG 或讲稿已变化；下载的是最近构建，请按需重新 build"} else {""},"missing_pages":status["missing_pages"],"stale_pages":status["stale_pages"],"build_missing_pages":serde_json::from_str::<Value>(&missing)?}),
    )
}

pub fn doctor(fonts: &[String]) -> Result<Value> {
    crate::tools::invoke("doctor", &json!({"fonts":fonts}))
}
