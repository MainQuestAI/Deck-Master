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
    Ok(json!({ "version": snapshot.version, "deck": deck }))
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
