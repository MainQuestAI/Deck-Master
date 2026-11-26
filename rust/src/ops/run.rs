use crate::error::{Error, Result};
use crate::model::{Argument, Deck, Evidence, Page, RunKind};
use crate::ops::basis::{basis, current_basis_for};
use crate::ops::native::{
    NativePack, append_findings_warnings, is_confirmation_only, native_result,
    note_unspecific_warning, plan_refs, result_plans, shared_layout_warnings,
};
use crate::store::{self, Store};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::path::Path;

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

fn blank_text(value: &str) -> bool {
    value.trim().is_empty()
}

fn start_example(deck: &Deck, missing: &[String]) -> Result<String> {
    // put replaces brief and framing as whole units, so a frame snippet carries
    // every current field and fills only the ones the gate treats as empty.
    // Blank kind is filled with explanation: a judgment sample without evidence
    // would fail the next gate, so one copied put can start the run.
    let frame_missing = missing.iter().any(|field| !field.starts_with("pages["));
    let mut payload = serde_json::Map::new();
    if frame_missing {
        let mut brief = deck.brief.clone();
        let mut framing = deck.framing.clone();
        if blank_text(&brief.audience) {
            brief.audience = "管理层".into();
        }
        if blank_text(&brief.decision) {
            brief.decision = "本周需拍板的事项".into();
        }
        if brief.concerns.iter().all(|item| blank_text(item)) {
            brief.concerns = vec!["关注点一".into(), "关注点二".into()];
        }
        if blank_text(&brief.narrator.role) {
            brief.narrator.role = "资深顾问".into();
        }
        if blank_text(&brief.narrator.tone) {
            brief.narrator.tone = "结论先行，语气肯定".into();
        }
        if framing.storyline.iter().all(|item| blank_text(item)) {
            framing.storyline = vec!["第一句主线".into(), "第二句主线".into()];
        }
        payload.insert("brief".into(), serde_json::to_value(brief)?);
        payload.insert("framing".into(), serde_json::to_value(framing)?);
    }
    let pages: Vec<Value> = deck
        .pages
        .iter()
        .filter(|page| {
            missing
                .iter()
                .any(|field| field == &format!("pages[{}].kind", page.id))
        })
        .map(|page| json!({"id": page.id, "kind": "explanation"}))
        .collect();
    if !pages.is_empty() {
        payload.insert("pages".into(), json!(pages));
    }
    Ok(serde_json::to_string_pretty(&Value::Object(payload))?)
}

fn frame_gate_message(deck: &Deck, version: i64, missing: &[String]) -> Result<String> {
    // Design §5.3. Error::Input adds the "输入有误：" prefix.
    // Blank kind is listed with the frame so one message matches that sample.
    let listed = missing
        .iter()
        .map(|field| format!("- {field}"))
        .collect::<Vec<_>>()
        .join("\n");
    Ok(format!(
        "无法开始生成。当前作品缺少以下字段：\n{listed}\n请先用 deck put 补全后再执行 run start。示例（--base 换成 deck show 中的当前版本号）：\n\n  deck put --base {version} payload.json\n\npayload.json 最小片段：\n{}",
        start_example(deck, missing)?
    ))
}

fn sample_argument() -> Argument {
    Argument {
        reasons: vec!["理由一".into(), "理由二".into()],
        evidence: vec![Evidence {
            text: "出处或待补说明".into(),
            r#ref: None,
            gap: Some("待补：需补充口径".into()),
        }],
        reasoning: String::new(),
        rebuttal: String::new(),
    }
}

fn repair_argument(argument: Option<&Argument>) -> Argument {
    let Some(argument) = argument else {
        return sample_argument();
    };
    if argument.evidence.is_empty() {
        let mut sample = sample_argument();
        if argument.reasons.iter().any(|item| !blank_text(item)) {
            sample.reasons = argument.reasons.clone();
        }
        if !blank_text(&argument.reasoning) {
            sample.reasoning = argument.reasoning.clone();
        }
        if !blank_text(&argument.rebuttal) {
            sample.rebuttal = argument.rebuttal.clone();
        }
        return sample;
    }
    let mut repaired = argument.clone();
    for item in &mut repaired.evidence {
        if item.has_ref() || item.has_gap() {
            continue;
        }
        if blank_text(&item.text) {
            item.text = "出处或待补说明".into();
        }
        item.r#ref = None;
        item.gap = Some("待补：需补充口径".into());
    }
    repaired
}

fn judgment_incomplete(page: &Page) -> bool {
    if page.kind != "judgment" {
        return false;
    }
    match &page.argument {
        None => true,
        Some(argument) if argument.evidence.is_empty() => true,
        Some(argument) => argument
            .evidence
            .iter()
            .any(|item| !item.has_ref() && !item.has_gap()),
    }
}

fn incomplete_judgment_lines(targets: &[&Page]) -> Vec<String> {
    let mut lines = Vec::new();
    for page in targets {
        if page.kind != "judgment" {
            continue;
        }
        let Some(argument) = page
            .argument
            .as_ref()
            .filter(|argument| !argument.evidence.is_empty())
        else {
            lines.push(format!(
                "- pages[{}].argument.evidence 为空，请至少提供一条带 ref 或 gap 的证据",
                page.id
            ));
            continue;
        };
        for (index, item) in argument.evidence.iter().enumerate() {
            if !item.has_ref() && !item.has_gap() {
                lines.push(format!(
                    "- pages[{}].argument.evidence[{index}] 既没有 ref 也没有 gap",
                    page.id
                ));
            }
        }
    }
    lines
}

fn evidence_example(targets: &[&Page]) -> Result<String> {
    let pages: Vec<Value> = targets
        .iter()
        .filter(|page| judgment_incomplete(page))
        .map(|page| {
            json!({
                "id": page.id,
                "kind": "judgment",
                "argument": repair_argument(page.argument.as_ref()),
            })
        })
        .collect();
    Ok(serde_json::to_string_pretty(&json!({"pages": pages}))?)
}

fn evidence_gate_message(version: i64, lines: &[String], snippet: &str) -> String {
    // Design §5.3 second sample. Error::Input adds the "输入有误：" prefix.
    format!(
        "无法开始生成。判断页证据不完整：\n{}\n请用 deck put 补全，例如：\n\n  deck put --base {version} payload.json\n\n{snippet}",
        lines.join("\n")
    )
}

pub fn run_start(
    project: &Path,
    kind: &str,
    ids: &[String],
    max_calls: Option<i64>,
) -> Result<Value> {
    use rusqlite::{OptionalExtension, params};
    let parsed_kind = RunKind::parse(kind)
        .map_err(|_| Error::Input("请选择 image、svg 或 native，并指定不重复的页面".into()))?;
    if ids.is_empty() || ids.iter().collect::<HashSet<_>>().len() != ids.len() {
        return Err(Error::Input(
            "请选择 image、svg 或 native，并指定不重复的页面".into(),
        ));
    }
    if max_calls.is_some_and(|n| n < 1) || (parsed_kind != RunKind::Image && max_calls.is_some()) {
        return Err(Error::Input(
            "生图调用上限必须为正整数；SVG 和 native 不设调用上限".into(),
        ));
    }
    let mut store = Store::open(project)?;
    let snapshot = store.current()?;
    for id in ids {
        if snapshot.deck.page(id).is_none() {
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
    let current = store::current(&tx)?;
    let version = current.version;
    let deck = current.deck;
    let targets: Vec<&Page> = deck
        .pages
        .iter()
        .filter(|page| ids.iter().any(|id| id == &page.id))
        .collect();
    // §4.1 checks the frame before kind. §5.3 lists blank kind in that same
    // missing-field error. Illegal kind is a different sentence, after both.
    let mut missing: Vec<String> = crate::model::missing_frame_fields(&deck)
        .into_iter()
        .map(str::to_string)
        .collect();
    for page in &targets {
        if blank_text(&page.kind) {
            missing.push(format!("pages[{}].kind", page.id));
        }
    }
    if !missing.is_empty() {
        return Err(Error::Input(frame_gate_message(&deck, version, &missing)?));
    }
    for page in &targets {
        crate::model::validate_kind(&page.id, &page.kind)?;
        if page.kind == "judgment"
            && let Some(argument) = &page.argument
        {
            crate::model::validate_argument(&page.id, argument)?;
        }
    }
    let incomplete = incomplete_judgment_lines(&targets);
    if !incomplete.is_empty() {
        return Err(Error::Input(evidence_gate_message(
            version,
            &incomplete,
            &evidence_example(&targets)?,
        )));
    }
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
    let mut store = Store::open(project)?;
    let tx = store.transaction()?;
    run_record(&tx, id)?;
    tx.execute(
        "UPDATE runs SET status='cancelled' WHERE id=? AND status='open'",
        [id],
    )?;
    let deck = store::current(&tx)?.deck;
    let list = runs(&tx, &deck, Some(id))?;
    tx.commit()?;
    Ok(json!({"runs": list}))
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

pub(super) fn file_url(file: &str) -> String {
    format!("/api/files/{}", file.split('.').next().unwrap_or(""))
}

pub(super) fn runs(
    connection: &rusqlite::Connection,
    deck: &Deck,
    id: Option<i64>,
) -> Result<Vec<Value>> {
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

pub(super) fn page_job(store: &Store, deck: &Deck, page: &Page, svg: &Path) -> Result<Value> {
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
        let (packed, png, mut checked, comparison) =
            native_result(&store, id, page, source, &data, temporary.path())?;
        let submitted: NativePack = serde_json::from_slice(&packed)?;
        let plans = result_plans(&store, id, page_id, Some(&submitted.plan))?;
        let layout = shared_layout_warnings(&plan_refs(&plans))
            .into_iter()
            .filter(|warning| warning.get("page_id").and_then(Value::as_str) == Some(page_id))
            .collect();
        append_findings_warnings(&mut checked, layout);
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
        // Decode and normalize EXIF orientation on the exact saved bytes, not a mutable Host file.
        let bitmap = temporary.path().join("image");
        let normalized = temporary.path().join("image-normalized");
        std::fs::write(&bitmap, &data)?;
        let info = crate::tools::invoke(
            "normalize-image",
            &json!({"path": bitmap, "output": normalized, "svg": false}),
        )?;
        if info["normalized"].as_bool() == Some(true) {
            data = std::fs::read(&normalized)?;
        }
        match info["format"].as_str() {
            Some("PNG") => "png",
            Some("JPEG") => "jpg",
            _ => {
                return Err(Error::Tool(
                    "normalize-image 未返回 PNG 或 JPEG 格式".into(),
                ));
            }
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
        let adopted_changed = snapshot.deck != store::current(&tx)?.deck;
        if adopted_changed {
            store::append(&tx, &mut snapshot.deck, "采用生成结果")?;
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
    let mut store = Store::open(project)?;
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
    let confirmation_only = note.is_some_and(is_confirmation_only);
    let (old, _, file) = run_page(&store.connection, id, page_id)?;
    let file = file.ok_or_else(|| Error::Input("此页尚无结果；请先交回文件".into()))?;
    if expected_file.is_some_and(|expected| expected != file) {
        return Err(Error::Conflict(
            "候选已更新；请读取当前候选后重新采用".into(),
        ));
    }
    store.file(&file)?;
    let layout_warnings = if kind == "native" {
        let plans = result_plans(&store, id, "", None)?;
        shared_layout_warnings(&plan_refs(&plans))
    } else {
        Vec::new()
    };
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
    let tx = store.transaction()?;
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
    let adopt_changed = snapshot.deck != store::current(&tx)?.deck;
    if adopt_changed {
        store::append(&tx, &mut snapshot.deck, "手动采用生成结果")?;
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
    let mut shown = run_show(project, Some(id))?;
    if kind == "native" {
        let mut warnings = Vec::new();
        if confirmation_only {
            warnings.push(note_unspecific_warning(page_id));
        }
        warnings.extend(layout_warnings);
        if !warnings.is_empty() {
            shown["warnings"] = json!(warnings);
        }
    }
    Ok(shown)
}
