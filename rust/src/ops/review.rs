use crate::error::{Error, Result};
use crate::model::{Deck, ReviewMethod};
use crate::store::{self, Store};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::path::Path;

fn blank_text(value: &str) -> bool {
    value.trim().is_empty()
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
    pub record_kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snapshot: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checks: Option<Value>,
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
        record_kind: row.get(9)?,
        snapshot: review_json(row, 10)?,
        checks: review_json(row, 11)?,
    })
}

fn review_json(row: &rusqlite::Row<'_>, index: usize) -> rusqlite::Result<Option<Value>> {
    let text: Option<String> = row.get(index)?;
    text.map(|text| {
        serde_json::from_str(&text).map_err(|error| {
            rusqlite::Error::FromSqlConversionFailure(
                index,
                rusqlite::types::Type::Text,
                Box::new(error),
            )
        })
    })
    .transpose()
}

fn review_columns(connection: &rusqlite::Connection) -> Result<&'static str> {
    Ok(if store::reviews_have_record_kind(connection)? {
        "record_kind,snapshot_json,checks_json"
    } else {
        "'comment',NULL,NULL"
    })
}

pub(super) fn reviews(
    connection: &rusqlite::Connection,
    status: Option<&str>,
    page: Option<&str>,
) -> Result<Vec<Review>> {
    review_records(connection, status, page, "comment")
}

fn review_records(
    connection: &rusqlite::Connection,
    status: Option<&str>,
    page: Option<&str>,
    record: &str,
) -> Result<Vec<Review>> {
    use rusqlite::params;
    if status.is_some_and(|s| !["open", "resolved"].contains(&s)) {
        return Err(Error::Input("意见状态只接受 open 或 resolved".into()));
    }
    if !["comment", "content_review", "all"].contains(&record) {
        return Err(Error::Input(
            "记录类型只接受 comment、content_review 或 all".into(),
        ));
    }
    let filter = if record == "all" {
        String::new()
    } else if store::reviews_have_record_kind(connection)? {
        format!(" AND record_kind='{record}'")
    } else if record == "content_review" {
        " AND 0".into()
    } else {
        String::new()
    };
    let columns = review_columns(connection)?;
    let mut query = connection.prepare(&format!(
        "SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at,{columns}
         FROM reviews WHERE (?1 IS NULL OR status=?1) AND (?2 IS NULL OR page_id=?2){filter} ORDER BY id"
    ))?;
    Ok(query
        .query_map(params![status, page], review_row)?
        .collect::<std::result::Result<_, _>>()?)
}

fn review(connection: &rusqlite::Connection, id: i64) -> Result<Review> {
    use rusqlite::OptionalExtension;
    let columns = review_columns(connection)?;
    connection.query_row(
        &format!("SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at,{columns} FROM reviews WHERE id=?"),
        [id], review_row,
    ).optional()?.ok_or_else(|| Error::Missing(format!("意见 {id} 不存在;请用 deck review list --record all 查看")))
}

pub(super) fn page_review_count(reviews: &[Review], page: &str) -> usize {
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
    review_method(method)?;
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
    review_list_records(project, status, page, "comment")
}

pub fn review_list_records(
    project: &Path,
    status: Option<&str>,
    page: Option<&str>,
    record: &str,
) -> Result<Value> {
    let store = Store::open(project)?;
    Ok(json!({"reviews": review_records(&store.connection, status, page, record)?}))
}

pub fn review_get(project: &Path, id: i64) -> Result<Review> {
    let store = Store::open(project)?;
    review(&store.connection, id)
}

pub fn review_resolve(project: &Path, id: i64) -> Result<Review> {
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    tx.execute("UPDATE reviews SET status='resolved',resolved_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='open'", [id])?;
    let value = review(&tx, id)?;
    tx.commit()?;
    Ok(value)
}

const CONTENT_CHECK_IDS: &[&str] = &[
    "storyline_coherence",
    "evidence_supports_claim",
    "anticipated_objections",
    "overdefense",
    "no_internal_notes",
    "final_pages_viewed",
];

fn frame_value(deck: &Deck) -> Value {
    json!({
        "audience": deck.brief.audience,
        "decision": deck.brief.decision,
        "concerns": deck.brief.concerns,
        "narrator": {"role": deck.brief.narrator.role, "tone": deck.brief.narrator.tone},
        "storyline": deck.framing.storyline,
    })
}

fn review_snapshot(version: i64, deck: &Deck) -> Result<String> {
    let snapshot = json!({
        "version_id": version,
        "pages": deck.pages.iter().map(|page| json!({
            "id": page.id,
            "preview": page.preview,
        })).collect::<Vec<_>>(),
        "framing": frame_value(deck),
    });
    Ok(serde_json::to_string(&snapshot)?)
}

fn load_checks(path: &Path) -> Result<Value> {
    let value: Value = serde_json::from_slice(&std::fs::read(path)?)?;
    let Some(items) = value.as_array() else {
        return Err(Error::Input("出稿审稿的 checks 必须是 JSON 数组".into()));
    };
    let mut seen = HashSet::new();
    for item in items {
        let Some(id) = item.get("id").and_then(Value::as_str) else {
            continue;
        };
        if !CONTENT_CHECK_IDS.contains(&id) {
            continue;
        }
        match item.get("conclusion").and_then(Value::as_str) {
            Some(conclusion) if !blank_text(conclusion) => {}
            _ => {
                return Err(Error::Input(format!(
                    "出稿审稿的 checks 里 {id} 缺少结论文本"
                )));
            }
        }
        match item.get("pages").and_then(Value::as_array) {
            Some(pages) if pages.iter().all(Value::is_string) => {}
            _ => {
                return Err(Error::Input(format!(
                    "出稿审稿的 checks 里 {id} 的 pages 必须是字符串数组"
                )));
            }
        }
        seen.insert(id);
    }
    let missing: Vec<&str> = CONTENT_CHECK_IDS
        .iter()
        .copied()
        .filter(|id| !seen.contains(id))
        .collect();
    if !missing.is_empty() {
        return Err(Error::Input(format!(
            "出稿审稿的 checks 缺少：{}",
            missing.join("、")
        )));
    }
    Ok(value)
}

fn review_method(method: &str) -> Result<()> {
    ReviewMethod::parse(method).map(|_| ())
}

pub fn review_add_content(
    project: &Path,
    text: &str,
    reviewer: &str,
    method: &str,
    checks_path: &Path,
) -> Result<Review> {
    use rusqlite::params;
    review_method(method)?;
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    let version = store::user_version(&tx)?;
    if version < store::FORMAT_VERSION {
        return Err(Error::Input(format!(
            "当前项目仍是格式 {version}，不能记录出稿审稿。请先用 deck put 补全字段，项目升级后再执行 review add --record content_review"
        )));
    }
    let checks = load_checks(checks_path)?;
    let snapshot = store::current(&tx)?;
    let snapshot_json = review_snapshot(snapshot.version, &snapshot.deck)?;
    tx.execute(
        "INSERT INTO reviews(version_id,page_id,reviewer,method,text,record_kind,snapshot_json,checks_json) VALUES (?,NULL,?,?,?,'content_review',?,?)",
        params![
            snapshot.version,
            reviewer,
            method,
            text,
            snapshot_json,
            serde_json::to_string(&checks)?,
        ],
    )?;
    let value = review(&tx, tx.last_insert_rowid())?;
    tx.commit()?;
    Ok(value)
}

fn unreviewed_status() -> Value {
    json!({
        "status": "unreviewed",
        "methods": [],
        "version_id": Value::Null,
        "unreviewed_pages": [],
    })
}

fn stale_unreadable(method: &str) -> Value {
    json!({
        "status": "stale",
        "methods": [method],
        "version_id": Value::Null,
        "unreviewed_pages": [],
    })
}

// Called only when the key is present, so null stays a value instead of "missing".
fn present_framing<'de, D>(deserializer: D) -> std::result::Result<Option<Value>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Ok(Some(Value::deserialize(deserializer)?))
}

#[derive(Deserialize)]
struct ContentReviewSnapshot {
    version_id: i64,
    #[serde(default, deserialize_with = "present_framing")]
    framing: Option<Value>,
}

pub(super) fn content_review_status(
    connection: &rusqlite::Connection,
    version: i64,
    deck: &Deck,
) -> Result<Value> {
    use rusqlite::OptionalExtension;
    if !store::reviews_have_record_kind(connection)? {
        return Ok(unreviewed_status());
    }
    let row: Option<(String, Option<String>)> = connection
        .query_row(
            "SELECT method, snapshot_json FROM reviews WHERE record_kind='content_review' AND version_id<=? ORDER BY id DESC LIMIT 1",
            [version],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    let Some((method, snapshot_json)) = row else {
        return Ok(unreviewed_status());
    };
    let Some(snapshot_json) = snapshot_json else {
        return Ok(stale_unreadable(&method));
    };
    let Ok(snapshot) = serde_json::from_str::<ContentReviewSnapshot>(&snapshot_json) else {
        return Ok(stale_unreadable(&method));
    };
    let recorded_deck = match store::load_optional(connection, snapshot.version_id) {
        Ok(Some(deck)) => deck,
        Ok(None) | Err(Error::Json(_)) => return Ok(stale_unreadable(&method)),
        Err(error) => return Err(error),
    };
    let recorded: HashMap<_, _> = recorded_deck
        .pages
        .iter()
        .map(|page| (&page.id, page))
        .collect();
    let order_differs = !deck
        .pages
        .iter()
        .map(|page| &page.id)
        .eq(recorded_deck.pages.iter().map(|page| &page.id));
    let mut unreviewed_pages = Vec::new();
    for page in &deck.pages {
        if recorded
            .get(&page.id)
            .is_none_or(|prior| prior.author_fields_changed(page))
        {
            unreviewed_pages.push(page.id.clone());
        }
    }
    // Old records without framing can use their immutable source version.
    let frame_differs = match &snapshot.framing {
        None => frame_value(&recorded_deck) != frame_value(deck),
        Some(value) => value != &frame_value(deck),
    };
    let status = if unreviewed_pages.is_empty() && !frame_differs && !order_differs {
        "reviewed"
    } else {
        "stale"
    };
    Ok(json!({
        "status": status,
        "methods": [method],
        "version_id": snapshot.version_id,
        "unreviewed_pages": unreviewed_pages,
    }))
}
