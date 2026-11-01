use deck::{
    error::Error,
    ops,
    store::{self, Store},
};
use rusqlite::params;
use serde_json::{Value, json};

fn setup(path: &std::path::Path) {
    ops::new(path, "合成审阅".into()).unwrap();
    ops::put(
        path,
        1,
        serde_json::from_value(json!({
            "order":["p1","p3"], "pages":[{"id":"p1"},{"id":"p3"}]
        }))
        .unwrap(),
    )
    .unwrap();
}

#[test]
fn reviews_preserve_text_bind_current_version_and_resolve_without_editing_deck() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let before = ops::get(path, None).unwrap();
    let text = "  收入 100 元 , 需复核。\n";
    let self_check = ops::review_add(path, Some("p3"), text, "author", "self_check").unwrap();
    assert_eq!(self_check.version_id, before["version"]);
    assert_eq!(self_check.text, text);
    assert_eq!(self_check.method, "self_check");
    assert_eq!(self_check.page_id.as_deref(), Some("p3"));
    assert_eq!(self_check.status, "open");
    assert!(self_check.resolved_at.is_none());
    let global = ops::review_add(path, None, "全稿意见", "editor", "human").unwrap();
    ops::put(
        path,
        self_check.version_id,
        serde_json::from_value(json!({"pages":[{"id":"p1","notes":"讲稿"}]})).unwrap(),
    )
    .unwrap();
    let current = ops::get(path, None).unwrap();
    let other = ops::review_add(path, Some("p1"), "另一模型", "model", "other_model").unwrap();
    assert_eq!(other.version_id, current["version"]);
    let listed = ops::review_list(path, None, None).unwrap();
    assert_eq!(
        listed["reviews"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| r["id"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![self_check.id, global.id, other.id]
    );
    assert_eq!(
        ops::review_list(path, Some("open"), Some("p3")).unwrap()["reviews"][0]["text"],
        text
    );
    assert_eq!(
        ops::review_list(path, Some("resolved"), None).unwrap()["reviews"],
        json!([])
    );
    let show = ops::show(path).unwrap();
    assert_eq!(show["open_reviews_total"], 3);
    assert_eq!(show["pages"][0]["open_reviews"], 1);
    assert_eq!(show["pages"][1]["open_reviews"], 1);
    let workspace = ops::workspace(path).unwrap();
    assert_eq!(workspace["reviews"], listed["reviews"]);
    assert_eq!(workspace["deck"]["pages"][1]["open_reviews"], 1);
    assert_eq!(workspace["open_reviews_total"], 3);
    assert_eq!(ops::get(path, None).unwrap(), current);
    assert!(current["deck"]["pages"][0].get("open_reviews").is_none());
    let resolved = serde_json::to_value(ops::review_resolve(path, self_check.id).unwrap()).unwrap();
    let mut expected = serde_json::to_value(self_check).unwrap();
    expected["status"] = json!("resolved");
    expected["resolved_at"] = resolved["resolved_at"].clone();
    assert!(resolved["resolved_at"].is_string());
    assert_eq!(resolved, expected);
    assert_eq!(
        serde_json::to_value(ops::review_resolve(path, resolved["id"].as_i64().unwrap()).unwrap())
            .unwrap(),
        resolved
    );
    assert_eq!(
        ops::review_list(path, Some("resolved"), Some("p3")).unwrap()["reviews"],
        json!([resolved])
    );
    let show = ops::show(path).unwrap();
    assert_eq!(show["open_reviews_total"], 2);
    assert_eq!(show["pages"][1]["open_reviews"], 0);
    assert_eq!(
        ops::workspace(path).unwrap()["reviews"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(ops::get(path, None).unwrap(), current);
}

#[test]
fn invalid_reviews_are_rejected_and_sql_enforces_method_and_status() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    for (page, text, method) in [
        (None, "", "human"),
        (None, " \n\t", "human"),
        (None, "意见", "pass"),
        (Some("missing"), "意见", "human"),
    ] {
        assert!(matches!(
            ops::review_add(path, page, text, "author", method),
            Err(Error::Input(_))
        ));
    }
    assert!(matches!(
        ops::review_list(path, Some("pass"), None),
        Err(Error::Input(_))
    ));
    assert!(matches!(
        ops::review_resolve(path, 99),
        Err(Error::Missing(_))
    ));
    assert_eq!(
        ops::review_list(path, None, None).unwrap()["reviews"],
        json!([])
    );
    let store = Store::open(path).unwrap();
    for (method, status) in [("pass", "open"), ("human", "pass")] {
        assert!(store.connection.execute("INSERT INTO reviews(version_id,reviewer,method,text,status) VALUES (2,'author',?,'意见',?)", params![method, status]).is_err());
    }
    assert_eq!(store.current().unwrap().version, 2);
}

#[test]
fn concurrent_v2_upgrade_preserves_versions_runs_builds_and_files() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let store = Store::open(path).unwrap();
    let before = ops::get(path, None).unwrap();
    let history: Value = serde_json::to_value(store.history().unwrap()).unwrap();
    let file = store.add_file(b"retained build", "pptx").unwrap();
    store.connection.execute_batch("DROP TABLE reviews; PRAGMA user_version=2;
        INSERT INTO runs(id,kind,status,max_calls,calls_used) VALUES (5,'image','cancelled',2,1);
        INSERT INTO run_pages(run_id,page_id,basis,status,result_file) VALUES (5,'p3','basis','unadopted','saved.png');").unwrap();
    store.connection.execute("INSERT INTO builds(id,version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (7,2,'digest',?,'[]','[\"p1\"]')", [&file]).unwrap();
    let dump = |store: &Store, table: &str| {
        let mut query = store
            .connection
            .prepare(&format!("SELECT * FROM {table}"))
            .unwrap();
        let count = query.column_count();
        query
            .query_map([], |row| {
                Ok((0..count)
                    .map(|i| row.get::<_, rusqlite::types::Value>(i).unwrap())
                    .collect::<Vec<_>>())
            })
            .unwrap()
            .collect::<std::result::Result<Vec<_>, _>>()
            .unwrap()
    };
    let tables = ["runs", "run_pages", "builds"];
    let rows: Vec<_> = tables.iter().map(|table| dump(&store, table)).collect();
    drop(store);
    let barrier = std::sync::Arc::new(std::sync::Barrier::new(2));
    let threads: Vec<_> = (0..2)
        .map(|_| {
            let path = path.to_path_buf();
            let barrier = barrier.clone();
            std::thread::spawn(move || {
                barrier.wait();
                Store::open(&path).unwrap().current().unwrap().version
            })
        })
        .collect();
    for thread in threads {
        assert_eq!(thread.join().unwrap(), 2);
    }
    let store = Store::open(path).unwrap();
    assert_eq!(ops::get(path, None).unwrap(), before);
    assert_eq!(
        serde_json::to_value(store.history().unwrap()).unwrap(),
        history
    );
    assert_eq!(
        store
            .connection
            .pragma_query_value(None, "user_version", |row| row.get::<_, i64>(0))
            .unwrap(),
        store::FORMAT_VERSION
    );
    for (table, expected) in tables.iter().zip(rows) {
        assert_eq!(dump(&store, table), expected);
    }
    assert_eq!(
        std::fs::read(store.file(&file).unwrap()).unwrap(),
        b"retained build"
    );
    ops::review_add(path, Some("p3"), "迁移后意见", "author", "human").unwrap();
    assert_eq!(
        ops::review_list(path, None, None).unwrap()["reviews"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
}
