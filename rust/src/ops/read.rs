use crate::error::{Error, Result};
use crate::model::{Brief, Deck, Snapshot, Style};
use crate::ops::build::{artifact_status, default_build};
use crate::ops::review::{page_review_count, reviews};
use crate::ops::run::runs_paged;
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

#[derive(Debug, Clone, Copy)]
pub struct WorkspaceQuery {
    pub runs_limit: usize,
    pub history_limit: usize,
}

impl Default for WorkspaceQuery {
    fn default() -> Self {
        Self {
            runs_limit: 20,
            history_limit: 50,
        }
    }
}

fn etag_matches(header_value: &str, current: &str) -> bool {
    header_value.split(',').any(|token| {
        let token = token.trim();
        token == "*" || token == current || token.strip_prefix("W/") == Some(current)
    })
}

pub fn workspace_with_etag(
    project: &Path,
    query: WorkspaceQuery,
    if_none_match: Option<&str>,
) -> Result<(String, Option<Value>)> {
    let mut store = Store::open(project)?;
    // A deferred read transaction keeps the polling response on one snapshot,
    // without reserving SQLite's writer slot.
    let tx = store.read_transaction()?;
    let etag = store::workspace_etag(&tx, query.runs_limit, query.history_limit)?;
    if if_none_match.is_some_and(|tag| etag_matches(tag, &etag)) {
        return Ok((etag, None));
    }
    let snapshot = store::current(&tx)?;
    let mut value = snapshot_value(&snapshot, None)?;
    value["default_build"] = match default_build(&tx, &snapshot.deck)? {
        Some(mut selected) => {
            selected.as_object_mut().map(|value| value.remove("file"));
            selected
        }
        None => Value::Null,
    };
    let (paged_runs, runs_total, runs_has_more) =
        runs_paged(&tx, &snapshot.deck, query.runs_limit)?;
    value["runs"] = json!(paged_runs);
    value["runs_total"] = json!(runs_total);
    value["runs_has_more"] = json!(runs_has_more);
    let reviews = reviews(&tx, Some("open"), None)?;
    for page in value["deck"]["pages"].as_array_mut().into_iter().flatten() {
        page["open_reviews"] = json!(page_review_count(
            &reviews,
            page["id"].as_str().unwrap_or("")
        ));
    }
    value["open_reviews_total"] = json!(reviews.len());
    value["reviews"] = json!(reviews);
    let (history, history_total) = store::history_page(&tx, query.history_limit)?;
    value["history_has_more"] = json!(history.len() < history_total);
    value["history_total"] = json!(history_total);
    value["history"] = json!(history);
    Ok((etag, Some(value)))
}

pub fn workspace(project: &Path) -> Result<Value> {
    let (_, value) = workspace_with_etag(project, WorkspaceQuery::default(), None)?;
    value.ok_or_else(|| Error::Tool("工作区快照意外为空".into()))
}

const KNOWN_FILE_EXTENSIONS: &[&str] = &[
    "png",
    "jpg",
    "jpeg",
    "svg",
    "pptx",
    "pdf",
    "txt",
    "md",
    "json",
    "native.json",
    "webp",
    "gif",
    "docx",
    "bin",
];

fn verify_in_files_dir(store: &Store, directory: &Path, name: &str) -> Result<std::path::PathBuf> {
    let path = store.file(name)?.canonicalize()?;
    if path.starts_with(directory) {
        Ok(path)
    } else {
        Err(Error::Input("附件必须位于当前项目 files 目录内".into()))
    }
}

pub fn project_file(project: &Path, sha: &str) -> Result<std::path::PathBuf> {
    if sha.len() != 64 || !sha.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err(Error::Input("文件 sha 必须是 64 位十六进制".into()));
    }
    let store = Store::open(project)?;
    let directory = store.root.join("files").canonicalize()?;
    let sha = sha.to_ascii_lowercase();
    // Fast path: probe common known extensions directly to avoid scanning .deck/files/.
    for ext in KNOWN_FILE_EXTENSIONS {
        let name = format!("{sha}.{ext}");
        let candidate = directory.join(&name);
        if candidate.is_file() {
            return verify_in_files_dir(&store, &directory, &name);
        }
    }
    // Fallback for uncommon extensions (e.g. uploaded .csv/.xlsx source files).
    let mut entries = std::fs::read_dir(&directory)?.collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        if name.split_once('.').is_some_and(|(hash, _)| hash == sha) {
            return verify_in_files_dir(&store, &directory, name);
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
