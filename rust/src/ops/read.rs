use crate::error::{Error, Result};
use crate::model::{Brief, Deck, Snapshot, Style};
use crate::ops::build::{artifact_status, default_build};
use crate::ops::review::{page_review_count, reviews};
use crate::ops::run::runs;
use crate::store::{self, Store};
use serde_json::{Value, json};
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
    let outlined: Vec<_> = snapshot
        .deck
        .pages
        .iter()
        .filter(|page| pages.is_none_or(|ids| ids.iter().any(|id| id == &page.id)))
        .cloned()
        .collect();
    Ok(json!({
        "version": snapshot.version,
        "deck": deck,
        "artifact_status": artifact_status(&snapshot.deck)?,
        "writing_brief": crate::model::writing_brief(&snapshot.deck),
        "outline": crate::model::outline(&outlined),
        "gap_list": crate::model::gap_list(&outlined),
    }))
}

pub fn workspace(project: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    // A deferred read transaction keeps the polling response on one snapshot,
    // without reserving SQLite's writer slot.
    let tx = store.read_transaction()?;
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
    value["history"] = json!(store::history(&tx)?);
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
    let tx = store.read_transaction()?;
    let snapshot = store::current(&tx)?;
    let reviews = reviews(&tx, Some("open"), None)?;
    let history = store::history(&tx)?;
    Ok(json!({
        "version": snapshot.version,
        "title": snapshot.deck.brief.title,
        "thesis": snapshot.deck.framing.thesis,
        "materials": snapshot.deck.materials.iter().map(|m| json!({"id": m.id, "name": m.name, "status": m.status})).collect::<Vec<_>>(),
        "pages": snapshot.deck.pages.iter().map(|p| json!({"id": p.id, "title": p.content.title, "purpose": p.purpose, "todo": p.todo, "open_reviews": page_review_count(&reviews, &p.id)})).collect::<Vec<_>>(),
        "open_reviews_total": reviews.len(),
        "artifact_status": artifact_status(&snapshot.deck)?,
        "writing_brief": crate::model::writing_brief(&snapshot.deck),
        "outline": crate::model::outline(&snapshot.deck.pages),
        "gap_list": crate::model::gap_list(&snapshot.deck.pages),
        "history": history
    }))
}
