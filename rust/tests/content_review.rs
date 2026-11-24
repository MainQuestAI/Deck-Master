use deck::{
    error::Error,
    ops,
    store::{self, Store},
};
use rusqlite::params;
use serde_json::{Value, json};
use std::path::Path;
use std::process::Command;

fn setup(path: &Path) -> i64 {
    ops::new(path, "合成出稿".into()).unwrap();
    ops::put(
        path,
        1,
        serde_json::from_value(json!({
            "brief": {
                "title": "合成出稿",
                "audience": "业务负责人",
                "decision": "是否采用该方案",
                "concerns": ["成本是否可控", "时间是否来得及"],
                "narrator": {"role": "项目负责人", "tone": "直接说明判断"}
            },
            "framing": {
                "thesis": "原主张",
                "pillars": [{"title": "支柱", "points": ["一点"]}],
                "storyline": ["先说明问题", "再给出判断"]
            },
            "order": ["b", "a"],
            "pages": [
                {"id": "b", "kind": "explanation", "content": {"title": "乙"}},
                {"id": "a", "kind": "explanation", "content": {"title": "甲"}}
            ]
        }))
        .unwrap(),
    )
    .unwrap()
    .version
}

fn current(path: &Path) -> deck::model::Snapshot {
    Store::open(path).unwrap().current().unwrap()
}

fn put_brief(path: &Path, edit: impl FnOnce(&mut Value)) {
    let snapshot = current(path);
    let mut brief = serde_json::to_value(&snapshot.deck.brief).unwrap();
    edit(&mut brief);
    ops::put(
        path,
        snapshot.version,
        serde_json::from_value(json!({"brief": brief})).unwrap(),
    )
    .unwrap();
}

fn put_framing(path: &Path, edit: impl FnOnce(&mut Value)) {
    let snapshot = current(path);
    let mut framing = serde_json::to_value(&snapshot.deck.framing).unwrap();
    edit(&mut framing);
    ops::put(
        path,
        snapshot.version,
        serde_json::from_value(json!({"framing": framing})).unwrap(),
    )
    .unwrap();
}

fn put_pages(path: &Path, value: Value) {
    let version = current(path).version;
    ops::put(path, version, serde_json::from_value(value).unwrap()).unwrap();
}

fn six_checks() -> Value {
    json!([
        {"id":"storyline_coherence","title":"主线是否连贯","conclusion":"主线不断","pages":["b","a"]},
        {"id":"evidence_supports_claim","title":"证据能否推出结论","conclusion":"证据够用","pages":["a"]},
        {"id":"anticipated_objections","title":"可预见的质疑是否已回答","conclusion":"已回答","pages":[]},
        {"id":"overdefense","title":"去防御检查","conclusion":"没有堆砌","pages":[]},
        {"id":"no_internal_notes","title":"读者可见页面上没有内部备注","conclusion":"没有内部备注","pages":[]},
        {"id":"final_pages_viewed","title":"最终页确实被看过","conclusion":"两页都看过","pages":["b","a"]}
    ])
}

fn write_checks(path: &Path, checks: &Value) -> std::path::PathBuf {
    let file = path.join("checks.json");
    std::fs::write(&file, checks.to_string()).unwrap();
    file
}

fn record(path: &Path, method: &str, text: &str) -> ops::Review {
    let file = write_checks(path, &six_checks());
    ops::review_add_content(path, text, "author", method, &file).unwrap()
}

fn status_of(path: &Path) -> Value {
    ops::export_markdown(path).unwrap().1["content_review"].clone()
}

fn input_text<T: std::fmt::Debug>(result: Result<T, Error>) -> String {
    match result {
        Err(Error::Input(text)) => text,
        other => panic!("expected input error, got {other:?}"),
    }
}

fn user_version(path: &Path) -> i64 {
    Store::open(path)
        .unwrap()
        .connection
        .pragma_query_value(None, "user_version", |row| row.get(0))
        .unwrap()
}

fn review_count(path: &Path) -> i64 {
    Store::open(path)
        .unwrap()
        .connection
        .query_row("SELECT COUNT(*) FROM reviews", [], |row| row.get(0))
        .unwrap()
}

fn latest_snapshot(path: &Path) -> Value {
    let json: String = Store::open(path)
        .unwrap()
        .connection
        .query_row(
            "SELECT snapshot_json FROM reviews WHERE record_kind='content_review' ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    serde_json::from_str(&json).unwrap()
}

#[test]
fn export_without_a_content_review_is_unreviewed() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let (markdown, status) = ops::export_markdown(path).unwrap();
    assert!(markdown.contains("甲"));
    assert_eq!(
        status["content_review"],
        json!({"status":"unreviewed","methods":[],"version_id":null,"unreviewed_pages":[]})
    );
    assert!(status.get("warnings").is_none());
    assert_eq!(user_version(path), 7);
}

#[test]
fn readable_draft_lists_evidence_gaps_and_todos() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    put_pages(
        path,
        json!({
            "pages": [{
                "id": "a",
                "kind": "judgment",
                "argument": {"evidence": [{"text": "营收增长", "gap": "缺官方财报来源"}]},
                "todo": ["补一张趋势图"]
            }]
        }),
    );
    let (markdown, _status) = ops::export_markdown(path).unwrap();
    assert!(markdown.contains("缺官方财报来源"));
    assert!(markdown.contains("补一张趋势图"));
}

#[test]
fn storyline_change_is_stale_with_an_empty_page_list() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    let version = setup(path);
    let saved = record(path, "human", "");
    assert_eq!(saved.version_id, version);
    assert_eq!(saved.page_id, None);
    assert_eq!(saved.text, "");
    assert_eq!(current(path).version, version);
    assert_eq!(
        status_of(path),
        json!({"status":"reviewed","methods":["human"],"version_id":version,"unreviewed_pages":[]})
    );
    put_framing(path, |framing| {
        framing["storyline"] = json!(["先说明问题", "再给出另一判断"]);
    });
    assert!(current(path).version > version);
    let (markdown, status) = ops::export_markdown(path).unwrap();
    assert!(markdown.contains("甲"));
    assert_eq!(status["content_review"]["status"], "stale");
    assert_eq!(status["content_review"]["unreviewed_pages"], json!([]));
    assert_eq!(status["content_review"]["version_id"], version);
    assert_eq!(status["content_review"]["methods"], json!(["human"]));
    assert!(status["stale_pages"].is_array());
    assert!(status.get("warnings").is_none());
}

#[test]
fn frame_fields_stale_and_thesis_preview_and_version_do_not() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    record(path, "self_check", "看过");

    put_brief(path, |brief| brief["audience"] = json!("财务负责人"));
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    record(path, "self_check", "看过");

    put_brief(path, |brief| brief["decision"] = json!("是否延期"));
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    assert_eq!(status_of(path)["status"], "stale");
    record(path, "other_model", "看过");
    assert_eq!(status_of(path)["methods"], json!(["other_model"]));

    put_brief(path, |brief| {
        brief["concerns"] = json!(["时间是否来得及", "成本是否可控"]);
    });
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    record(path, "self_check", "看过");

    put_brief(path, |brief| brief["narrator"]["role"] = json!("外部顾问"));
    assert_eq!(status_of(path)["status"], "stale");
    record(path, "self_check", "看过");
    put_brief(path, |brief| brief["narrator"]["tone"] = json!("先讲风险"));
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    record(path, "self_check", "看过");

    put_framing(path, |framing| {
        framing["storyline"] = json!(["先说明问题 ", "再给出判断"]);
    });
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    record(path, "self_check", "看过");

    let bound = current(path).version;
    put_framing(path, |framing| {
        framing["thesis"] = json!("另一主张");
        framing["pillars"] = json!([{"title": "另一支柱", "points": ["两点"]}]);
    });
    assert_eq!(status_of(path)["status"], "reviewed");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    assert_eq!(status_of(path)["version_id"], bound);

    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    snapshot.deck.pages[0].preview = Some("not-a-real-preview.png".into());
    let tx = store.transaction().unwrap();
    store::append(&tx, &mut snapshot.deck, "只改预览").unwrap();
    tx.commit().unwrap();
    drop(store);
    assert!(current(path).version > bound);
    assert_eq!(status_of(path)["status"], "reviewed");
    assert_eq!(status_of(path)["version_id"], bound);
}

#[test]
fn changed_pages_are_listed_in_deck_order() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let version = record(path, "human", "看过").version_id;
    put_pages(
        path,
        json!({"pages":[{"id":"a","notes":"甲的讲稿"},{"id":"b","notes":"乙的讲稿"}]}),
    );
    let status = status_of(path);
    assert_eq!(status["status"], "stale");
    assert_eq!(status["unreviewed_pages"], json!(["b", "a"]));
    assert_eq!(status["version_id"], version);
    record(path, "human", "再看");
    put_pages(path, json!({"pages":[{"id":"a","notes":"只改甲"}]}));
    assert_eq!(status_of(path)["unreviewed_pages"], json!(["a"]));
    assert_eq!(status_of(path)["status"], "stale");
}

#[test]
fn added_page_is_listed_and_removed_page_stales() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    record(path, "human", "看过");
    put_pages(path, json!({"order":["b"],"pages":[{"id":"a"}]}));
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    put_pages(
        path,
        json!({"order":["c","b"],"pages":[{"id":"c","kind":"reference","content":{"title":"丙"}}]}),
    );
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!(["c"]));
}

#[test]
fn recreated_page_with_the_same_id_is_stale() {
    // A rebuilt page reuses the id; historical author fields must detect the replacement.
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    record(path, "self_check", "看过");
    put_pages(path, json!({"order":["b"],"pages":[{"id":"a"}]}));
    put_pages(
        path,
        json!({
            "order":["b","a"],
            "pages":[{"id":"a","kind":"explanation","notes":"重做后的讲稿","content":{"title":"甲二"}}]
        }),
    );
    let page = current(path)
        .deck
        .pages
        .into_iter()
        .find(|page| page.id == "a")
        .unwrap();
    assert_eq!(page.notes, "重做后的讲稿");
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!(["a"]));
}

#[test]
fn adopt_changes_only_the_version_and_stays_reviewed() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    put_pages(path, json!({"order":["a"],"pages":[{"id":"b"}]}));
    let version = current(path).version;
    let started = ops::run_start(path, "image", &["a".into()], None).unwrap();
    let id = started["runs"][0]["id"].as_i64().unwrap();
    ops::run_call(path, id, "a", false).unwrap();
    ops::run_cancel(path, id).unwrap();
    let image = path.join("result.png");
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect("DECK_TOOLS_PYTHON");
    assert!(
        Command::new(python)
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8),'teal').save(sys.argv[1])"
            ])
            .arg(&image)
            .status()
            .unwrap()
            .success()
    );
    let returned = ops::run_result(path, id, "a", &image).unwrap();
    assert_eq!(returned["adopted"], false);
    assert_eq!(current(path).version, version);
    record(path, "self_check", "采用前看过");
    ops::run_adopt(path, id, "a").unwrap();
    let after = current(path);
    assert!(after.version > version);
    let page = after.deck.pages.iter().find(|page| page.id == "a").unwrap();
    assert!(page.image.is_some());
    assert_eq!(page.notes, "");
    let status = status_of(path);
    assert_eq!(status["status"], "reviewed");
    assert_eq!(status["unreviewed_pages"], json!([]));
    assert_eq!(status["version_id"], version);
    assert_eq!(status["methods"], json!(["self_check"]));
}

#[test]
fn snapshot_records_frame_text_and_old_records_use_historical_framing() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    let version = setup(path);
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    snapshot.deck.pages[0].preview = Some("kept.png".into());
    let tx = store.transaction().unwrap();
    let preview_version = store::append(&tx, &mut snapshot.deck, "带预览").unwrap();
    tx.commit().unwrap();
    drop(store);
    record(path, "human", "  简短说明  ");
    let stored = latest_snapshot(path);
    assert_eq!(stored["version_id"], preview_version);
    assert_ne!(stored["version_id"], version);
    assert_eq!(stored["framing"]["audience"], "业务负责人");
    assert_eq!(stored["framing"]["decision"], "是否采用该方案");
    assert_eq!(
        stored["framing"]["concerns"],
        json!(["成本是否可控", "时间是否来得及"])
    );
    assert_eq!(stored["framing"]["narrator"]["role"], "项目负责人");
    assert_eq!(stored["framing"]["narrator"]["tone"], "直接说明判断");
    assert_eq!(
        stored["framing"]["storyline"],
        json!(["先说明问题", "再给出判断"])
    );
    assert!(stored.get("framing").unwrap().get("thesis").is_none());
    assert_eq!(stored["pages"][0]["id"], "b");
    assert_eq!(stored["pages"][0]["preview"], "kept.png");
    assert_eq!(stored["pages"][1]["preview"], Value::Null);
    let checks: String = Store::open(path)
        .unwrap()
        .connection
        .query_row(
            "SELECT checks_json FROM reviews WHERE record_kind='content_review'",
            [],
            |row| row.get(0),
        )
        .unwrap();
    let checks: Value = serde_json::from_str(&checks).unwrap();
    assert_eq!(checks.as_array().unwrap().len(), 6);

    let mut without_frame = stored.clone();
    without_frame.as_object_mut().unwrap().remove("framing");
    Store::open(path)
        .unwrap()
        .connection
        .execute(
            "UPDATE reviews SET snapshot_json=? WHERE record_kind='content_review'",
            params![without_frame.to_string()],
        )
        .unwrap();
    put_framing(path, |framing| {
        framing["storyline"] = json!(["完全不同的主线"]);
        framing["thesis"] = json!("也改主张");
    });
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
    put_pages(path, json!({"pages":[{"id":"b","notes":"乙改了"}]}));
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!(["b"]));

    Store::open(path)
        .unwrap()
        .connection
        .execute(
            "UPDATE reviews SET snapshot_json=? WHERE record_kind='content_review'",
            params!["{"],
        )
        .unwrap();
    let (markdown, status) = ops::export_markdown(path).unwrap();
    assert!(markdown.contains("甲"));
    assert_eq!(status["content_review"]["status"], "stale");
    assert_eq!(status["content_review"]["unreviewed_pages"], json!([]));
    assert_eq!(status["content_review"]["version_id"], Value::Null);
}

#[test]
fn latest_content_review_binds_and_an_older_one_does_not() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    record(path, "human", "第一次");
    put_framing(path, |framing| framing["storyline"] = json!(["中途改过"]));
    assert_eq!(status_of(path)["status"], "stale");
    let second = current(path).version;
    record(path, "other_model", "第二次");
    let status = status_of(path);
    assert_eq!(status["status"], "reviewed");
    assert_eq!(status["methods"], json!(["other_model"]));
    assert_eq!(status["version_id"], second);
    assert_eq!(status["unreviewed_pages"], json!([]));
}

#[test]
fn v6_content_review_is_rejected_without_upgrade_or_insert() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let store = Store::open(path).unwrap();
    store
        .connection
        .execute_batch(
            "CREATE TABLE reviews_v6 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL, page_id TEXT,
                reviewer TEXT NOT NULL,
                method TEXT NOT NULL CHECK (method IN ('self_check','other_model','human')),
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                resolved_at TEXT
            );
            INSERT INTO reviews_v6 (id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at)
                SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at FROM reviews;
            DROP TABLE reviews;
            ALTER TABLE reviews_v6 RENAME TO reviews;
            PRAGMA user_version = 6;",
        )
        .unwrap();
    drop(store);
    let file = write_checks(path, &six_checks());
    let message = input_text(ops::review_add_content(
        path, "说明", "author", "human", &file,
    ));
    assert!(message.contains("deck put"), "{message}");
    assert_eq!(user_version(path), 6);
    assert_eq!(review_count(path), 0);
    ops::review_add(path, None, "仍是意见", "author", "human").unwrap();
    assert_eq!(user_version(path), 6);
    assert_eq!(review_count(path), 1);
    let status = status_of(path);
    assert_eq!(status["status"], "unreviewed");
    assert_eq!(user_version(path), 6);
}

#[test]
fn bad_checks_write_nothing_and_comments_stay_separate() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    let version = setup(path);
    let mut missing = six_checks();
    missing.as_array_mut().unwrap().pop();
    let file = write_checks(path, &missing);
    let message = input_text(ops::review_add_content(
        path, "说明", "author", "human", &file,
    ));
    assert!(message.contains("final_pages_viewed"), "{message}");
    assert_eq!(review_count(path), 0);

    let mut checks = six_checks();
    checks.as_array_mut().unwrap()[0]["conclusion"] = json!("  ");
    let file = write_checks(path, &checks);
    assert!(matches!(
        ops::review_add_content(path, "说明", "author", "human", &file),
        Err(Error::Input(_))
    ));
    assert_eq!(review_count(path), 0);
    assert_eq!(current(path).version, version);

    let mut checks = six_checks();
    checks.as_array_mut().unwrap().push(json!({
        "id": "host_note",
        "conclusion": "额外一项",
        "pages": []
    }));
    let file = write_checks(path, &checks);
    let saved = ops::review_add_content(path, "说明", "author", "self_check", &file).unwrap();
    assert_eq!(saved.page_id, None);
    let stored: Value = serde_json::from_str(
        &Store::open(path)
            .unwrap()
            .connection
            .query_row(
                "SELECT checks_json FROM reviews WHERE id=?",
                [saved.id],
                |row| row.get::<_, String>(0),
            )
            .unwrap(),
    )
    .unwrap();
    assert_eq!(stored.as_array().unwrap().len(), 7);

    let comment = ops::review_add(path, Some("a"), "页上意见", "author", "human").unwrap();
    let listed = ops::review_list(path, None, None).unwrap();
    assert_eq!(listed["reviews"].as_array().unwrap().len(), 1);
    assert_eq!(listed["reviews"][0]["id"], comment.id);
    assert_eq!(ops::show(path).unwrap()["open_reviews_total"], 1);
    ops::review_resolve(path, saved.id).unwrap();
    assert_eq!(status_of(path)["status"], "reviewed");
    ops::review_resolve(path, comment.id).unwrap();
    assert_eq!(ops::show(path).unwrap()["open_reviews_total"], 0);
    assert_eq!(current(path).version, version);
}

#[test]
fn cli_accepts_content_review_and_rejects_a_page_or_checks_on_a_comment() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let file = write_checks(path, &six_checks());
    let bin = env!("CARGO_BIN_EXE_deck");
    let run = |args: &[&str]| {
        Command::new(bin)
            .arg("--project")
            .arg(path)
            .args(args)
            .output()
            .unwrap()
    };
    let missing = run(&[
        "review",
        "add",
        "--record",
        "content_review",
        "--method",
        "human",
    ]);
    assert_eq!(missing.status.code(), Some(2));
    let paged = run(&[
        "review",
        "add",
        "--record",
        "content_review",
        "--method",
        "human",
        "--page",
        "a",
        "--checks",
        file.to_str().unwrap(),
        "说明",
    ]);
    assert_eq!(paged.status.code(), Some(2));
    assert_eq!(review_count(path), 0);
    let added = run(&[
        "review",
        "add",
        "--record",
        "content_review",
        "--method",
        "self_check",
        "--checks",
        file.to_str().unwrap(),
        "命令说明",
    ]);
    assert_eq!(
        added.status.code(),
        Some(0),
        "{}",
        String::from_utf8_lossy(&added.stderr)
    );
    let body: Value = serde_json::from_slice(&added.stdout).unwrap();
    assert_eq!(body["text"], "命令说明");
    assert_eq!(body["page_id"], Value::Null);
    assert_eq!(body["method"], "self_check");
    assert_eq!(body["record_kind"], "content_review");
    assert_eq!(body["checks"], six_checks());
    assert_eq!(body["snapshot"]["version_id"], current(path).version);
    let id = body["id"].as_i64().unwrap().to_string();
    let detail: Value = serde_json::from_slice(&run(&["review", "get", &id]).stdout).unwrap();
    assert_eq!(detail, body);
    let records: Value =
        serde_json::from_slice(&run(&["review", "list", "--record", "content_review"]).stdout)
            .unwrap();
    assert_eq!(records["reviews"], json!([body]));

    assert_eq!(status_of(path)["status"], "reviewed");
    let comment_checks = run(&[
        "review",
        "add",
        "--method",
        "human",
        "--checks",
        file.to_str().unwrap(),
        "意见",
    ]);
    assert_eq!(comment_checks.status.code(), Some(2));
    let comment = run(&["review", "add", "--method", "human", "意见"]);
    assert_eq!(comment.status.code(), Some(0));
    let listed: Value = serde_json::from_slice(&run(&["review", "list"]).stdout).unwrap();
    assert_eq!(listed["reviews"].as_array().unwrap().len(), 1);
    assert_eq!(listed["reviews"][0]["text"], "意见");
}

#[test]
fn reorder_stales_the_whole_manuscript() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    record(path, "human", "看过");
    put_pages(path, json!({"order":["a","b"]}));
    assert_eq!(status_of(path)["status"], "stale");
    assert_eq!(status_of(path)["unreviewed_pages"], json!([]));
}

// Synthetic build records isolate selection; they do not prove PPTX rendering.
#[test]
fn historical_download_review_is_bound_to_its_source_version() {
    for (review_old, review_new) in [(false, true), (true, false), (true, true)] {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path();
        let old = setup(path);
        let store = Store::open(path).unwrap();
        let file = store.add_file(b"synthetic build", "pptx").unwrap();
        store.connection.execute(
            "INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,'old-input',?,'{}','[]')",
            params![old, file],
        ).unwrap();
        if review_old {
            record(path, "human", "看过旧稿");
        }
        put_pages(path, json!({"pages":[{"id":"a","notes":"新讲稿"}]}));
        if review_new {
            record(path, "other_model", "看过新稿");
        }
        let exported = ops::export_pptx(path).unwrap();
        assert_eq!(exported["version_id"], old);
        assert_eq!(exported["input_changed"], true);
        assert_eq!(
            exported["content_review"]["status"],
            if review_old { "reviewed" } else { "unreviewed" }
        );
        assert_eq!(
            exported["content_review"]["version_id"],
            if review_old { json!(old) } else { Value::Null }
        );
        assert_eq!(
            exported["current_content_review"]["status"],
            if review_new { "reviewed" } else { "stale" }
        );
        assert_eq!(
            std::fs::read(exported["path"].as_str().unwrap()).unwrap(),
            b"synthetic build"
        );
    }
}
